"""
forge/tools/rotate.py
-----------------------
Ruota la geometria di un ForgeResult (o di un singolo ForgeCluster) attorno a
un centro — allineando opzionalmente il segmento strutturale più lungo
all'orizzontale.

Un solo heal(), non due: una rotazione rigida NON cambia la topologia (chi
contiene chi, quali loop esistono restano identici — solo le coordinate
cambiano), quindi non c'è bisogno di ricostruire l'albero di contenimento
dopo aver ruotato. `rotate_result`/`rotate_cluster` trasformano DIRETTAMENTE
le strutture che `heal()` ha già prodotto (poligoni, segmenti, gli `all_arcs`
grezzi che `detect()` userà) — non tornano alla geometria grezza pre-heal e
non richiamano `heal()`. Per lo stesso motivo `rotate_cluster` è economico e
ripetibile: un futuro nester può chiamarlo in un ciclo per provare molti
angoli su una singola parte, senza pagare il costo di un `heal()` ad ogni
tentativo.

Cosa NON viene ruotato, di proposito, non per svista:
- `cluster.detected`/`cluster.custom` — overlay a schema libero (D44), forge
  non sa cosa contengono; se hai già fatto `detect()`, quei dati (bending
  line, fori tipizzati, ...) restano nelle coordinate vecchie dopo una
  rotazione. Fai `detect()` DOPO aver ruotato, non prima.
- `result.annotations` — stesso limite di `rotate_document`: nessun caso
  reale le ha ancora richieste. Se presenti, viene aggiunto un warning
  invece di lasciarle silenziosamente nel posto sbagliato.

Nato dalla discussione "funzioni geometriche" (TODO.md) — orientamento
canonico per un futuro nester: la meccanica sta qui (`rotate_cluster`,
pensato per essere richiamato molte volte con angoli diversi), la decisione
di quanti gradi provare / l'ottimizzazione di impacchettamento restano fuori
scope (nesting resta fuori da forge).
"""

from __future__ import annotations

import math
from dataclasses import replace
from typing import List, Optional, Tuple

from shapely.affinity import rotate as _shapely_rotate

from ..core.geometry import longest_segment, chord_angle_deg, round_point, node_decimals_for
from ..core.primitives.segments import segment_endpoints
from ..model.cluster import ForgeCluster
from ..model.contour import ForgeContour
from ..model.document import ForgeDocument
from ..model.feature import OpenFeature
from ..model.result import ForgeResult

Point = Tuple[float, float]


# ---------------------------------------------------------------------------
# Selezione del segmento — "quale entità allineare"
# ---------------------------------------------------------------------------
# Filtro STRUTTURALE (cluster.outer vs cluster.inners), non su `contour.role`:
# `role` non distingue in modo affidabile outer/inner. `cluster.outer` è
# sempre inequivocabilmente l'outer (`hierarchy._build_parts` glielo assegna
# così, indipendentemente da come l'input era etichettato) — ma un `inner`
# senza ruolo proprio EREDITA il ruolo del padre se il padre ne aveva uno
# esplicito (`hierarchy._make_inner`, verificato leggendo il codice): un
# outer etichettato "outer" produce fori interni anch'essi "outer" se non
# hanno un ruolo loro. Filtrare per stringa sarebbe quindi ambiguo proprio
# nel caso comune (input senza label_map dedicato ai fori).
#
# Per un criterio più fine di "outer" / "outer+inner" (es. solo certi ruoli
# dopo un detect(), o qualunque altra logica) componi la lista da solo:
# `cluster.outer.segments`/`cluster.inners[i].segments` sono già pubblici, e
# `longest_segment()`/`chord_angle_deg()` (core/geometry.py) sono già
# generici — non serve altra API qui, forge dà i mattoncini.

def structural_segments(result: ForgeResult, include_inners: bool = False) -> list:
    """
    Segmenti nativi dei contorni strutturali di ogni cluster: sempre
    `cluster.outer`; anche `cluster.inners` (fori/loop interni non ancora
    tipizzati — la tipizzazione hole/countersink/... vive in `detect()`,
    un overlay separato, vedi il modulo) se `include_inners=True`.
    """
    segments = []
    for cluster in result.clusters:
        segments.extend(cluster.outer.segments)
        if include_inners:
            for inner in cluster.inners:
                segments.extend(inner.segments)
    return segments


def longest_structural_segment(
    result: ForgeResult, include_inners: bool = False
) -> Tuple[Optional[object], float, Optional[float]]:
    """
    `(segment, length, angle_deg)` del segmento più lungo fra
    `structural_segments(result, include_inners)`. `(None, 0.0, None)` se
    non c'è nessun cluster.
    """
    seg, length = longest_segment(structural_segments(result, include_inners))
    if seg is None:
        return None, 0.0, None
    start, end = segment_endpoints(seg)
    return seg, length, chord_angle_deg(start, end)


# ---------------------------------------------------------------------------
# Rotazione — primitive pure, riusabili in un ciclo (nester)
# ---------------------------------------------------------------------------

def _rotate_contour(contour: ForgeContour, angle_rad: float, origin: Point) -> ForgeContour:
    return replace(
        contour,
        segments=[s.rotated(angle_rad, origin) for s in contour.segments],
        polygon=_shapely_rotate(contour.polygon, angle_rad, origin=origin, use_radians=True)
                if contour.polygon is not None else None,
    )


def rotate_cluster(cluster: ForgeCluster, angle_rad: float, origin: Point = (0.0, 0.0)) -> ForgeCluster:
    """
    Nuovo `ForgeCluster` con `outer`/`inners` ruotati di `angle_rad` (radianti,
    CCW) attorno a `origin` — segmenti nativi (`.rotated()`) e poligono
    (`shapely.affinity.rotate`) in un colpo solo, nessun `heal()`.

    `cluster.detected`/`cluster.custom` NON sono toccati — vedi il modulo.
    L'albero `depth`/`parent` fra outer e inner è preservato (i nuovi
    `ForgeContour` puntano ai NUOVI oggetti ruotati, non a quelli vecchi).

    Primitiva pensata per un ciclo: economica (solo trasformazioni
    geometriche, zero ricostruzione di topologia), quindi adatta a provare
    molti angoli sulla stessa parte (nester).
    """
    new_outer = _rotate_contour(cluster.outer, angle_rad, origin)
    id_map = {id(cluster.outer): new_outer}

    new_inners: List[ForgeContour] = []
    for inner in cluster.inners:
        new_inner = _rotate_contour(inner, angle_rad, origin)
        id_map[id(inner)] = new_inner
        new_inners.append(new_inner)

    new_outer.parent = None
    for old_inner, new_inner in zip(cluster.inners, new_inners):
        new_inner.parent = id_map.get(id(old_inner.parent)) if old_inner.parent is not None else None

    return replace(cluster, outer=new_outer, inners=new_inners)


def rotate_result(result: ForgeResult, angle_rad: float, origin: Point = (0.0, 0.0)) -> ForgeResult:
    """
    Nuovo `ForgeResult` con ogni cluster (`rotate_cluster`), `trash_entities`
    e `all_arcs` (usati da `detect()` per i fori filettati — vanno ruotati
    anche loro o un `detect()` successivo leggerebbe coordinate vecchie)
    ruotati di `angle_rad` attorno a `origin`. Nessun `heal()` richiamato: una
    rotazione rigida non cambia la topologia, solo le coordinate.

    `result.annotations` non sono ruotate (vedi il modulo) — se presenti,
    aggiunge un warning invece di lasciarle ferme senza avvisare.
    `cluster.detected` non è toccato — se presente su qualche cluster, un
    warning ricorda di rifare `detect()` dopo la rotazione.
    """
    new_clusters = [rotate_cluster(c, angle_rad, origin) for c in result.clusters]
    new_trash = [
        replace(t, segments=[s.rotated(angle_rad, origin) for s in t.segments])
        if isinstance(t, OpenFeature) else t
        for t in result.trash_entities
    ]
    new_arcs = [a.rotated(angle_rad, origin) for a in result.all_arcs]

    new_warnings = list(result.warnings)
    if result.annotations:
        new_warnings.append(
            f"rotate_result(): {len(result.annotations)} annotazioni non ruotate (non ancora supportato)"
        )
    if any(c.detected is not None for c in result.clusters):
        new_warnings.append(
            "rotate_result(): detected features non ruotate — richiama detect() DOPO la rotazione"
        )

    return replace(
        result,
        clusters=new_clusters,
        trash_entities=new_trash,
        all_arcs=new_arcs,
        warnings=new_warnings,
    )


def rotate_document(
    doc: ForgeDocument,
    angle_rad: float,
    origin: Point = (0.0, 0.0),
    tolerance: float = 0.05,
) -> ForgeDocument:
    """
    Nuovo `ForgeDocument` con ogni `edge.segment` ruotato di `angle_rad`
    (radianti, CCW) attorno a `origin` — stesso arrotondamento degli endpoint
    (`round_point`/`node_decimals_for`) usato dall'adapter al caricamento.

    Primitiva pre-heal: utile quando l'angolo è già noto da altrove (non
    serve misurarlo su questo stesso documento) e si vuole ruotare prima di
    passare a `heal()` la prima volta. Per "misura l'angolo sull'outer più
    lungo E ruota", vedi `rotate_to_longest` — che lavora su un
    `ForgeResult` già sano, un solo `heal()` in tutto.

    Le annotazioni non sono ruotate — stesso limite di `rotate_result`.
    """
    decimals = node_decimals_for(tolerance)
    new_edges: List = []
    for edge in doc.edges:
        seg = edge.segment.rotated(angle_rad, origin)
        start, end = segment_endpoints(seg)
        new_edges.append(replace(
            edge,
            segment=seg,
            start=round_point(start, decimals),
            end=round_point(end, decimals),
        ))

    new_warnings = list(doc.warnings)
    if doc.annotations:
        new_warnings.append(
            f"rotate_document(): {len(doc.annotations)} annotazioni non ruotate (non ancora supportato)"
        )

    return replace(doc, edges=new_edges, warnings=new_warnings)


# ---------------------------------------------------------------------------
# Orchestratore — "allinea il segmento più lungo", un solo heal() a monte
# ---------------------------------------------------------------------------

def _result_bbox_center(result: ForgeResult) -> Point:
    """Centro del bbox unito degli outer di tutti i cluster — vedi `rotate_to_longest`."""
    boxes = [
        c.outer.polygon.bounds
        for c in result.clusters
        if c.outer.polygon is not None and not c.outer.polygon.is_empty
    ]
    if not boxes:
        return (0.0, 0.0)
    minx = min(b[0] for b in boxes)
    miny = min(b[1] for b in boxes)
    maxx = max(b[2] for b in boxes)
    maxy = max(b[3] for b in boxes)
    return ((minx + maxx) / 2.0, (miny + maxy) / 2.0)


def rotate_to_longest(
    result: ForgeResult,
    include_inners: bool = False,
    target_angle_deg: float = 0.0,
    origin: Optional[Point] = None,
) -> Tuple[ForgeResult, float]:
    """
    Ruota `result` (già sano, da un `heal()` già fatto dal chiamante) in modo
    che il suo segmento strutturale più lungo — vedi `structural_segments`:
    solo gli outer per default, anche gli inner se `include_inners=True` —
    diventi orizzontale (o `target_angle_deg`, se dato). Un solo `heal()` in
    tutto: quello che il chiamante ha già fatto per produrre `result`.

    `origin` di default è il centro del bbox unito degli outer (la forma non
    cambia con `origin`, solo dove finisce nel piano).

    Ritorna `(result_ruotato, angle_deg_applicato)`. Se non c'è nessun
    cluster, ritorna `result` invariato e `0.0`.
    """
    _, _, angle_deg = longest_structural_segment(result, include_inners)
    if angle_deg is None:
        return result, 0.0

    if origin is None:
        origin = _result_bbox_center(result)

    rotation_deg = target_angle_deg - angle_deg
    rotated = rotate_result(result, math.radians(rotation_deg), origin)
    return rotated, rotation_deg
