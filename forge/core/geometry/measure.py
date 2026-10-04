"""
forge/core/geometry/measure.py
------------------------------
Misure di primitive e tracce: arrotondamento dei nodi, lunghezza e angolo di
un segmento, vertici e tipo di una traccia aperta, "è circolare?".
"""

import math
from typing import Optional, Tuple, List

from ..primitives.segments import LineSeg, ArcSeg, CircleSeg

Point = Tuple[float, float]


# ---------------------------------------------------------------------------
# Arrotondamento
# ---------------------------------------------------------------------------

def round_point(pt, decimals: int = 1) -> Tuple:
    return (round(float(pt[0]), decimals), round(float(pt[1]), decimals))


def node_decimals_for(tolerance: float) -> int:
    """
    Numero di decimali a cui arrotondare gli endpoint per la topologia.

    Unica fonte di verità — usata da ForgeAdapter e dai passi di heal() perché
    producano nodi coerenti a parità di tolleranza.
    """
    return max(round(-math.log10(tolerance * 2)), 1)


# ---------------------------------------------------------------------------
# Archi e bulge
# ---------------------------------------------------------------------------

def num_segments_for_bulge(bulge: float) -> int:
    """Numero di segmenti per discretizzare un arco dato il suo bulge."""
    angle = 4 * math.atan(abs(bulge))
    return max(8, int(angle / math.pi * 32))


# ---------------------------------------------------------------------------
# Tracce aperte — vertici / lunghezza / tipo da segmenti nativi
# ---------------------------------------------------------------------------
# Una traccia aperta (bending line, incisione, frammento non chiuso) nel modello
# è una lista di segmenti nativi (LineSeg / ArcSeg / SplineSeg / CircleSeg).
# `pts`, `length`, `shape_type` sono valori DERIVATI da quei segmenti: qui, non
# stoccati sul modello. Chi li consuma — detect_flat(), write._write_trash,
# inspect() — li ricava con queste funzioni.

def track_points(segments, tolerance: Optional[float] = None) -> List[Point]:
    """
    Vertici di una traccia aperta come catena di segmenti nativi.

    Concatena `seg.discretize()` di ogni segmento, deduplicando il vertice
    condiviso alla giunzione fra un segmento e il successivo.
    """
    pts: List[Point] = []
    for seg in segments or []:
        seg_pts = seg.discretize() if tolerance is None else seg.discretize(tolerance)
        if not seg_pts:
            continue
        if pts and math.dist(pts[-1], seg_pts[0]) < 1e-9:
            pts.extend(seg_pts[1:])
        else:
            pts.extend(seg_pts)
    return pts


def track_length(pts) -> float:
    """Lunghezza totale di una polilinea (somma delle corde)."""
    return sum(
        math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1])
        for i in range(len(pts) - 1)
    )


def track_shape_type(pts) -> str:
    """`"line"` se la traccia è un solo segmento retto (2 vertici), altrimenti `"curve"`."""
    return "line" if len(pts) == 2 else "curve"


# ---------------------------------------------------------------------------
# Lunghezza e angolo di UNA primitiva nativa — mai stoccati sul modello,
# sempre derivati (stesso principio di track_length/track_shape_type sopra,
# ma su un singolo segmento invece che su una catena)
# ---------------------------------------------------------------------------

def segment_length(segment) -> float:
    """
    Lunghezza reale di una primitiva nativa singola (`LineSeg`/`ArcSeg`/
    `SplineSeg`/`CircleSeg`/`EllipseSeg`). `LineSeg`/`ArcSeg`/`CircleSeg`
    hanno una formula chiusa; `SplineSeg`/`EllipseSeg` (curvatura non
    costante, nessuna formula chiusa comoda) riusano la stessa polilinea di
    `discretize()`, sommata come `track_length`.
    """
    if isinstance(segment, LineSeg):
        return math.hypot(segment.end[0] - segment.start[0], segment.end[1] - segment.start[1])
    if isinstance(segment, ArcSeg):
        return segment.radius * segment._sweep()
    if isinstance(segment, CircleSeg):
        return 2 * math.pi * segment.radius
    return track_length(segment.discretize())


def longest_segment(segments) -> Tuple[Optional[object], float]:
    """
    `(segment, length)` del segmento più lungo in `segments` — `(None, 0.0)`
    se la lista è vuota. Confronto lineare via `segment_length`.
    """
    best_seg, best_len = None, 0.0
    for seg in segments or []:
        length = segment_length(seg)
        if best_seg is None or length > best_len:
            best_seg, best_len = seg, length
    return best_seg, best_len


def chord_angle_deg(a: Point, b: Point) -> float:
    """
    Angolo (gradi, 0-180°) della corda da `a` a `b`. Modulo 180 perché una
    linea non ha un verso proprio (`a->b` e `b->a` sono lo stesso
    orientamento) — stesso calcolo già usato da `detect._detect_bending` per
    l'angolo di una bending line, ora condiviso qui invece che duplicato.
    """
    return math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])) % 180


# ---------------------------------------------------------------------------
# Geometria circolare — diametro / centro di un contorno chiuso ~circolare
# ---------------------------------------------------------------------------
# Serve alla regola di processo `Ø < max_drill_diameter → foro` che vive in
# detect_flat(): dato un contorno interno, questo helper dice se è geometricamente
# un cerchio e con quale diametro/centro. Prima la stessa logica stava in
# `hierarchy._single_loop_geometry` e i valori erano stoccati su ClosedFeature
# (campi rimossi in D15) — ora si ricava qui, al momento della classificazione.

CIRCULAR_BBOX_ASPECT_TOLERANCE = 0.15


def circular_geometry(polygon, segments=None):
    """
    (diameter, center) se il contorno è ~circolare, altrimenti (None, None).

    Un contorno è "circolare" (candidato foro da punta) solo se:
      - è fatto di UNA sola primitiva nativa (`len(segments) == 1`) — un CIRCLE
        o un arco chiuso, non una polilinea multi-lato; e
      - il suo bounding box è ~quadrato (larghezza e altezza combaciano entro
        `CIRCULAR_BBOX_ASPECT_TOLERANCE`).
    Diametro = min(width, height) del bbox, centro = centro del bbox.

    È la stessa regola del vecchio `hierarchy._single_loop_geometry`
    (gate `len(loop) == 1` + aspect ratio): D15 la sposta qui senza cambiarne
    i numeri, così i golden non si spostano per la sola misura.
    """
    if len(list(segments or [])) != 1:
        return None, None

    if polygon is None or polygon.is_empty:
        return None, None

    minx, miny, maxx, maxy = polygon.bounds
    width  = maxx - minx
    height = maxy - miny
    if width <= 0 or height <= 0:
        return None, None
    if abs(width - height) / max(width, height) > CIRCULAR_BBOX_ASPECT_TOLERANCE:
        return None, None

    return min(width, height), ((minx + maxx) / 2, (miny + maxy) / 2)
