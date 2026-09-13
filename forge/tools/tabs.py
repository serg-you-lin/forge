"""
forge/tools/tabs.py
--------------------
Linguette (tab) fra due contorni annidati (genitore diretto e figlio nella
gerarchia di contenimento) — tengono un'isola attaccata al resto della
lamiera dopo il taglio laser, anche a profondità di annidamento arbitraria
(nipote<->figlio, pro-pronipote<->pronipote, ...). Mai un gap dentro un
contorno solo (nome storico `cut_tabs`, cancellato — MAP.md D40): il bisogno
reale è sempre un ponte fra DUE contorni distinti.

Meccanica di `bridge_tabs` (una coppia, una posizione): linea ideale fra un
punto del figlio e il punto corrispondente del genitore -> offset di
`±tab_width/2` -> intersezione delle due linee reali coi due contorni (via
`core.geometry.polyline_line_intersections`) -> due nuovi `LineSeg` (i fianchi
della linguetta) + i punti di taglio su entrambi i contorni. Genitore e figlio
possono essere linea, arco, polilinea o cerchio, GIA' discretizzati in punti —
non spline (nessuna intersezione retta-spline in core).

`bridge_nested_tabs` cammina la gerarchia di un `ForgeCluster`
(`ForgeContour.depth`/`.parent`) e applica `bridge_tabs` a ogni coppia
isola/genitore-diretto trovata (profondità pari, >= 2), con `tab_count`
linguette equispaziate per coppia.

Va applicata sui punti GREZZI, prima di qualunque fit — il contenimento/
gerarchia (`heal_and_detect`) va calcolato PRIMA, sugli stessi punti grezzi
non ancora modificati (vedi smoother/MAP.md D5).

Non è nel contratto pubblico flat di forge (`forge.*`): va importato
esplicitamente da `forge.tools.tabs` — un utente che si aspetta `forge.*`
sempre puramente ricostruttivo non deve incappare per caso in qualcosa che
aggiunge un ponte che nel disegno sorgente non c'era (MAP.md D39/D40).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Tuple

from ..core.primitives.segments import LineSeg, Point
from ..core.geometry import _distance, track_points, polyline_line_intersections

__all__ = ["bridge_tabs", "bridge_nested_tabs", "BridgeTab", "NestedBridgeResult"]


# ---------------------------------------------------------------------------
# Vettori 2D minimi — bookkeeping locale a questo tool, non geometria generica
# ---------------------------------------------------------------------------

def _sub(a: Point, b: Point) -> Point:
    return (a[0] - b[0], a[1] - b[1])


def _add(a: Point, b: Point) -> Point:
    return (a[0] + b[0], a[1] + b[1])


def _scale(v: Point, s: float) -> Point:
    return (v[0] * s, v[1] * s)


def _dot(a: Point, b: Point) -> float:
    return a[0] * b[0] + a[1] * b[1]


def _normalize(v: Point) -> Point:
    length = math.hypot(v[0], v[1])
    if length < 1e-12:
        raise ValueError("direzione nulla: anchor_parent e anchor_child coincidono")
    return (v[0] / length, v[1] / length)


def _perp(v: Point) -> Point:
    """Ruota `v` di 90° (verso arbitrario, coerente fra le due chiamate)."""
    return (-v[1], v[0])


# ---------------------------------------------------------------------------
# bridge_tabs — una coppia genitore/figlio, una posizione
# ---------------------------------------------------------------------------

@dataclass
class BridgeTab:
    """
    Risultato di un singolo ponte. `*_cut_{a,b}` sono `(punto, indice_lato)`
    su `child_points`/`parent_points` — l'indice serve a chi deve poi spezzare
    il contorno in più punti contemporaneamente (`bridge_nested_tabs`), non
    a chi vuole un solo ponte isolato.
    """
    child_cut_a:  Tuple[Point, int]
    child_cut_b:  Tuple[Point, int]
    parent_cut_a: Tuple[Point, int]
    parent_cut_b: Tuple[Point, int]
    tab_edges:    List[LineSeg] = field(default_factory=list)


def bridge_tabs(
    parent_points: List[Point],
    child_points: List[Point],
    anchor_parent: Point,
    anchor_child: Point,
    tab_width: float,
) -> BridgeTab:
    """
    Costruisce UNA linguetta fra `child_points` (contorno chiuso, il figlio
    nella gerarchia) e `parent_points` (contorno chiuso, il suo genitore
    diretto), nella posizione indicata da `anchor_child`/`anchor_parent` (due
    punti approssimativamente sui due contorni, nella direzione in cui va
    piazzata la linguetta — vicini ma non necessariamente esatti: la funzione
    trova i veri punti di attacco intersecando).

    Non modifica `parent_points`/`child_points` né decide gli stretch
    risultanti — quello è compito del chiamante (`bridge_nested_tabs` per il
    caso con più linguette sulla stessa coppia), perché una singola chiamata
    non sa se altre linguette condividono lo stesso contorno.

    Solleva `ValueError` se la linea offsettata non interseca uno dei due
    contorni (es. `tab_width` troppo grande, o anchor fuori posto).
    """
    direction = _normalize(_sub(anchor_parent, anchor_child))
    perp = _perp(direction)
    offset = _scale(perp, tab_width / 2.0)

    line_a = (_add(anchor_child, offset), _add(anchor_parent, offset))
    line_b = (_sub(anchor_child, offset), _sub(anchor_parent, offset))

    def _pick(points: List[Point], line: Tuple[Point, Point], ref: Point) -> Tuple[Point, int]:
        hits = polyline_line_intersections(points, True, line[0], line[1])
        if not hits:
            raise ValueError(
                f"nessuna intersezione trovata: tab_width={tab_width} troppo largo "
                f"o anchor non sul contorno"
            )
        return min(hits, key=lambda h: _distance(h[0], ref))

    child_cut_a = _pick(child_points, line_a, anchor_child)
    child_cut_b = _pick(child_points, line_b, anchor_child)
    parent_cut_a = _pick(parent_points, line_a, anchor_parent)
    parent_cut_b = _pick(parent_points, line_b, anchor_parent)

    tab_edges = [
        LineSeg(start=child_cut_a[0], end=parent_cut_a[0]),
        LineSeg(start=child_cut_b[0], end=parent_cut_b[0]),
    ]

    return BridgeTab(
        child_cut_a=child_cut_a, child_cut_b=child_cut_b,
        parent_cut_a=parent_cut_a, parent_cut_b=parent_cut_b,
        tab_edges=tab_edges,
    )


# ---------------------------------------------------------------------------
# Split di un contorno chiuso su N coppie di tagli (una coppia per linguetta)
# ---------------------------------------------------------------------------

def _cumulative_lengths_closed(points: List[Point]) -> List[float]:
    """`cum[i]` = distanza cumulata da `points[0]` a `points[i]` (lato i-1->i)."""
    cum = [0.0]
    for a, b in zip(points, points[1:]):
        cum.append(cum[-1] + _distance(a, b))
    return cum


def _split_closed_polyline_at_cuts(
    points: List[Point], cuts: List[Tuple[int, Point, int]]
) -> List[List[Point]]:
    """
    Spezza il contorno chiuso `points` sui tagli in `cuts` — ognuno
    `(indice_lato, punto, indice_linguetta)`, due tagli per linguetta (i suoi
    due fianchi). Ritorna solo gli stretch **fra due linguette diverse**
    (quello "sotto" una linguetta, fra i suoi due stessi tagli, si scarta: è
    lì che passa il ponte, non serve più come contorno).
    """
    cum = _cumulative_lengths_closed(points)
    enriched = sorted(
        (cum[edge_idx] + _distance(points[edge_idx], pt), edge_idx, pt, tab_idx)
        for edge_idx, pt, tab_idx in cuts
    )

    n = len(points)
    n_cuts = len(enriched)
    stretches: List[List[Point]] = []
    for k in range(n_cuts):
        _, edge_a, pt_a, tab_a = enriched[k]
        _, edge_b, pt_b, tab_b = enriched[(k + 1) % n_cuts]
        if tab_a == tab_b:
            continue  # arco sotto la linguetta: qui ci passa il ponte, si scarta

        stretch = [pt_a]
        i = (edge_a + 1) % n
        while True:
            stretch.append(points[i])
            if i == edge_b:
                break
            i = (i + 1) % n
        stretch.append(pt_b)
        stretches.append(stretch)
    return stretches


# ---------------------------------------------------------------------------
# bridge_nested_tabs — cammina la gerarchia, N linguette per coppia
# ---------------------------------------------------------------------------

@dataclass
class NestedBridgeResult:
    """Risultato per UNA coppia isola/genitore-diretto trovata nella gerarchia."""
    child_contour:    "ForgeContour"
    parent_contour:   "ForgeContour"
    child_stretches:  List[List[Point]]
    parent_stretches: List[List[Point]]
    tab_edges:        List[LineSeg]


def _discretize_closed(contour, tolerance: float) -> List[Point]:
    """Punti grezzi chiusi di un `ForgeContour` (senza il punto di chiusura duplicato)."""
    pts = track_points(contour.segments, tolerance)
    if len(pts) > 1 and _distance(pts[0], pts[-1]) < 1e-9:
        pts = pts[:-1]
    return pts


def _ray_exit_point(points: List[Point], center: Point, direction: Point) -> Point:
    """Punto in cui il raggio da `center` verso `direction` esce dal contorno chiuso `points`."""
    span = max(_distance(p, center) for p in points)
    far = _add(center, _scale(direction, span * 10.0))
    hits = polyline_line_intersections(points, True, center, far)
    forward = [(pt, idx) for pt, idx in hits if _dot(_sub(pt, center), direction) > 0]
    if not forward:
        raise ValueError("nessuna intersezione nella direzione data — geometria degenere")
    return min(forward, key=lambda h: _distance(h[0], center))[0]


def bridge_nested_tabs(
    cluster,
    tab_width: float,
    tab_count: int = 4,
    discretize_tolerance: float = 0.05,
) -> List[NestedBridgeResult]:
    """
    Cammina `cluster.inners` (che porta `depth`/`parent` per ogni contorno,
    D34) e collega ogni isola (profondità pari, >= 2 — un'isola sotto la
    profondità 0 rischia di staccarsi, una profondità dispari è un vuoto, non
    materiale) al suo genitore diretto, con `tab_count` linguette equispaziate
    attorno al centroide dell'isola. A qualunque profondità: nipote<->figlio,
    pro-pronipote<->pronipote, mai un livello saltato.
    """
    results: List[NestedBridgeResult] = []

    for contour in cluster.inners:
        if contour.depth < 2 or contour.depth % 2 != 0:
            continue
        parent = contour.parent
        if parent is None:
            continue

        child_points = _discretize_closed(contour, discretize_tolerance)
        parent_points = _discretize_closed(parent, discretize_tolerance)
        center = (contour.polygon.centroid.x, contour.polygon.centroid.y)

        bridges: List[BridgeTab] = []
        for k in range(tab_count):
            angle = 2 * math.pi * k / tab_count
            direction = (math.cos(angle), math.sin(angle))
            anchor_child = _ray_exit_point(child_points, center, direction)
            anchor_parent = _ray_exit_point(parent_points, center, direction)
            bridges.append(bridge_tabs(parent_points, child_points, anchor_parent, anchor_child, tab_width))

        child_cuts, parent_cuts, tab_edges = [], [], []
        for tab_idx, b in enumerate(bridges):
            child_cuts.append((b.child_cut_a[1], b.child_cut_a[0], tab_idx))
            child_cuts.append((b.child_cut_b[1], b.child_cut_b[0], tab_idx))
            parent_cuts.append((b.parent_cut_a[1], b.parent_cut_a[0], tab_idx))
            parent_cuts.append((b.parent_cut_b[1], b.parent_cut_b[0], tab_idx))
            tab_edges.extend(b.tab_edges)

        results.append(NestedBridgeResult(
            child_contour=contour,
            parent_contour=parent,
            child_stretches=_split_closed_polyline_at_cuts(child_points, child_cuts),
            parent_stretches=_split_closed_polyline_at_cuts(parent_points, parent_cuts),
            tab_edges=tab_edges,
        ))

    return results
