"""
core/geometry.py
----------------
Funzioni geometriche pure per dxf-forge.

Nessuna dipendenza da ezdxf o da modelli di dominio.
Solo math, numpy, shapely.

Importato da:
    - core/healing/gap_solver.py  (intersezioni per la chiusura dei gap)
    - core/topology/               (utilità topologiche)
    - tools/simplify_points.py     (spigoli/fit su una sequenza di punti)
"""

import math
from typing import Optional, Tuple, List
import numpy as np
from shapely.geometry import LineString

from .primitives.segments import LineSeg, ArcSeg, CircleSeg

Point = Tuple[float, float]


# ---------------------------------------------------------------------------
# Arrotondamento
# ---------------------------------------------------------------------------

def round_point(pt, decimals: int = 1) -> Tuple:
    return (round(float(pt[0]), decimals), round(float(pt[1]), decimals))


def node_decimals_for(tolerance: float) -> int:
    """
    Numero di decimali a cui arrotondare gli endpoint per la topologia.

    Unica fonte di verità — usata da ForgeAdapter e da HealStep perché
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
# Collinearità e distanze — usate da healer e injector
# ---------------------------------------------------------------------------

def _line_direction(line: 'LineString') -> Tuple[float, float]:
    """
    Vettore direzione normalizzato di una LineString, orientato canonicamente
    (dx >= 0; se dx==0 allora dy > 0).
    """
    coords = list(line.coords)
    dx = coords[-1][0] - coords[0][0]
    dy = coords[-1][1] - coords[0][1]
    length = (dx**2 + dy**2) ** 0.5
    if length == 0:
        return (0.0, 0.0)
    dx, dy = dx / length, dy / length
    if dx < 0 or (dx == 0 and dy < 0):
        dx, dy = -dx, -dy
    return (dx, dy)


def _point_to_line_distance(px: float, py: float, line: 'LineString') -> float:
    """Distanza di un punto dalla retta infinita definita da una LineString."""
    coords = list(line.coords)
    ax, ay = coords[0]
    bx, by = coords[-1]
    dx, dy = bx - ax, by - ay
    length = (dx**2 + dy**2) ** 0.5
    if length == 0:
        return ((px - ax)**2 + (py - ay)**2) ** 0.5
    cross = abs(dx * (ay - py) - dy * (ax - px))
    return cross / length


def are_collinear(line_a: 'LineString', line_b: 'LineString', tolerance: float = 0.1) -> bool:
    """
    Restituisce True se due LineString giacciono sulla stessa retta infinita.
    """
    dir_a = _line_direction(line_a)
    dir_b = _line_direction(line_b)
    cross = abs(dir_a[0] * dir_b[1] - dir_a[1] * dir_b[0])
    if cross > 1e-6:
        return False
    coords_b = list(line_b.coords)
    dist = _point_to_line_distance(coords_b[0][0], coords_b[0][1], line_a)
    return dist <= tolerance


def group_collinear_lines(lines: list, tolerance: float = 0.1) -> list:
    """
    Raggruppa LINE in gruppi collineari (stessa retta infinita).
    Restituisce lista di gruppi: [[L1, L2], [L3], ...]
    """
    groups   = []
    assigned = set()
    for i, line in enumerate(lines):
        if i in assigned:
            continue
        group = [line]
        assigned.add(i)
        for j, other in enumerate(lines):
            if j in assigned:
                continue
            if are_collinear(line, other, tolerance):
                group.append(other)
                assigned.add(j)
        groups.append(group)
    return groups


# ---------------------------------------------------------------------------
# Tracce aperte — vertici / lunghezza / tipo da segmenti nativi
# ---------------------------------------------------------------------------
# Una traccia aperta (bending line, incisione, frammento non chiuso) nel modello
# è una lista di segmenti nativi (LineSeg / ArcSeg / SplineSeg / CircleSeg).
# `pts`, `length`, `shape_type` sono valori DERIVATI da quei segmenti: qui, non
# stoccati sul modello. Chi li consuma — detect(), write._write_trash,
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
        if pts and _distance(pts[-1], seg_pts[0]) < 1e-9:
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
# detect(): dato un contorno interno, questo helper dice se è geometricamente
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


# ---------------------------------------------------------------------------
# Sequenze di punti — angolo interno, deduplica, fit a cerchio (D38)
# ---------------------------------------------------------------------------
# Matematica generica su una sequenza ordinata di punti (x, y): non sa nulla
# di primitive forge (LineSeg/ArcSeg/...) né di come il chiamante la userà.
# Nata dentro tools/simplify_points.py (D33/D36), spostata qui perché un
# secondo consumatore (un futuro tool linguette) ne ha bisogno senza
# duplicarla — `tools/simplify_points.py` resta l'orchestratore che decide
# quando/come usarla per ricostruire linee/archi/spline.

DEFAULT_ANGLE_THRESHOLD_DEG = 50.0
DEFAULT_DUPLICATE_TOLERANCE = 1e-6


def interior_angle_deg(prev_pt: Point, curr_pt: Point, next_pt: Point) -> float:
    """Angolo interno (gradi) in curr_pt fra i lati verso prev_pt e next_pt."""
    v1 = (prev_pt[0] - curr_pt[0], prev_pt[1] - curr_pt[1])
    v2 = (next_pt[0] - curr_pt[0], next_pt[1] - curr_pt[1])
    n1, n2 = math.hypot(*v1), math.hypot(*v2)
    if n1 == 0 or n2 == 0:
        return 180.0
    cos_a = (v1[0] * v2[0] + v1[1] * v2[1]) / (n1 * n2)
    cos_a = max(-1.0, min(1.0, cos_a))
    return math.degrees(math.acos(cos_a))


def detect_corners(
    points: List[Point],
    angle_threshold_deg: float = DEFAULT_ANGLE_THRESHOLD_DEG,
    closed: bool = True,
) -> List[bool]:
    """
    Per ogni punto, True se l'angolo formato dai due lati adiacenti è sotto
    `angle_threshold_deg` (spigolo vivo da non smussare via col refit spline).

    Args:
        points:               sequenza di punti (x, y), ordinata
        angle_threshold_deg:  soglia in gradi sotto cui un punto è uno spigolo
        closed:               True se `points` è un contorno chiuso (il primo
                               e l'ultimo punto sono adiacenti). False per una
                               polilinea aperta: i due estremi non hanno due
                               lati adiacenti veri e non sono mai spigoli.
    """
    n = len(points)
    if n < 3:
        return [False] * n

    corners = [False] * n
    rng = range(n) if closed else range(1, n - 1)
    for i in rng:
        prev_pt = points[(i - 1) % n]
        curr_pt = points[i]
        next_pt = points[(i + 1) % n]
        if interior_angle_deg(prev_pt, curr_pt, next_pt) < angle_threshold_deg:
            corners[i] = True
    return corners


def drop_duplicate_points(
    points: List[Point], tolerance: float = DEFAULT_DUPLICATE_TOLERANCE
) -> List[Point]:
    """Rimuove punti consecutivi coincidenti entro `tolerance`."""
    if not points:
        return []
    cleaned = [points[0]]
    for p in points[1:]:
        last = cleaned[-1]
        if math.hypot(p[0] - last[0], p[1] - last[1]) > tolerance:
            cleaned.append(p)
    return cleaned


def fit_circle_kasa(points: List[Point]) -> Optional[Tuple[Point, float, float]]:
    """
    Fit algebrico (Kasa) ai minimi quadrati di un cerchio su `points`: minimizza
    `x²+y²+Dx+Ey+F=0`, che è un cerchio di centro `(-D/2,-E/2)` e raggio
    ricavabile da `D,E,F`. Ritorna `(center, radius, max_residual)` —
    `max_residual` è lo scostamento massimo di un punto dal cerchio fittato,
    per decidere se accettarlo. `None` se il fit è degenere (meno di 3 punti,
    punti quasi collineari, raggio non reale).
    """
    if len(points) < 3:
        return None

    pts = np.asarray(points, dtype=float)
    x, y = pts[:, 0], pts[:, 1]
    a_matrix = np.column_stack([x, y, np.ones_like(x)])
    b_vector = -(x**2 + y**2)
    try:
        (d, e, f), *_ = np.linalg.lstsq(a_matrix, b_vector, rcond=None)
    except np.linalg.LinAlgError:
        return None

    center = (-d / 2.0, -e / 2.0)
    radius_sq = (d**2 + e**2) / 4.0 - f
    if radius_sq <= 0:
        return None
    radius = math.sqrt(radius_sq)

    residuals = np.hypot(x - center[0], y - center[1]) - radius
    max_residual = float(np.max(np.abs(residuals)))
    return center, radius, max_residual


def arc_angles(points: List[Point], center: Point) -> Tuple[float, float, bool]:
    """
    `(start_angle, end_angle, ccw)` in radianti di un arco che passa per
    `points` (in ordine) intorno a `center`. Segue la rotazione reale della
    sequenza "srotolando" gli angoli (come `numpy.unwrap`) invece di guardare
    solo primo e ultimo punto — altrimenti un arco sopra i 180° si confonde
    con uno più corto nel verso sbagliato.
    """
    raw = [math.atan2(p[1] - center[1], p[0] - center[0]) for p in points]
    unwrapped = [raw[0]]
    for angle in raw[1:]:
        delta = angle - unwrapped[-1]
        # riporta il delta fra due punti consecutivi in (-pi, pi]
        while delta > math.pi:
            delta -= 2 * math.pi
        while delta <= -math.pi:
            delta += 2 * math.pi
        unwrapped.append(unwrapped[-1] + delta)

    total = unwrapped[-1] - unwrapped[0]
    ccw = total >= 0
    return raw[0], raw[0] + total, ccw


# ---------------------------------------------------------------------------
# Intersezioni geometriche pure — usate da core/healing/gap_solver.py
# ---------------------------------------------------------------------------

def _line_intersection(p1: Point, p2: Point,
                       p3: Point, p4: Point) -> Optional[Point]:
    """Intersezione tra retta (p1,p2) e retta (p3,p4). None se parallele."""
    x1, y1 = p1
    x2, y2 = p2
    x3, y3 = p3
    x4, y4 = p4
    denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(denom) < 1e-10:
        return None
    t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denom
    return (x1 + t * (x2 - x1), y1 + t * (y2 - y1))


def _distance(p1: Point, p2: Point) -> float:
    return math.sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)


def _circle_line_intersections(cx: float, cy: float, r: float,
                                p1: Point, p2: Point) -> List[Point]:
    """
    Intersezioni tra la circonferenza (cx, cy, r) e la retta infinita (p1, p2).
    Restituisce lista di 0, 1 o 2 punti.
    """
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    fx = p1[0] - cx
    fy = p1[1] - cy

    a = dx * dx + dy * dy
    if a < 1e-12:
        return []
    b = 2 * (fx * dx + fy * dy)
    c = fx * fx + fy * fy - r * r

    discriminant = b * b - 4 * a * c
    if discriminant < 0:
        return []

    results = []
    for sign in (-1, 1):
        t = (-b + sign * math.sqrt(max(discriminant, 0))) / (2 * a)
        results.append((p1[0] + t * dx, p1[1] + t * dy))

    if discriminant < 1e-10:
        return [results[0]]
    return results


def _circle_circle_intersections(cx1: float, cy1: float, r1: float,
                                  cx2: float, cy2: float, r2: float) -> List[Point]:
    """Intersezioni tra due circonferenze. Restituisce 0, 1 o 2 punti."""
    d = _distance((cx1, cy1), (cx2, cy2))
    if d < 1e-10 or d > r1 + r2 + 1e-10 or d < abs(r1 - r2) - 1e-10:
        return []

    a    = (r1 * r1 - r2 * r2 + d * d) / (2 * d)
    h_sq = r1 * r1 - a * a
    if h_sq < 0:
        return []
    h = math.sqrt(max(h_sq, 0))

    mx = cx1 + a * (cx2 - cx1) / d
    my = cy1 + a * (cy2 - cy1) / d

    if h < 1e-10:
        return [(mx, my)]

    px = h * (cy2 - cy1) / d
    py = h * (cx2 - cx1) / d
    return [(mx + px, my - py), (mx - px, my + py)]


def _closest_to(candidates: List[Point], ref: Point) -> Optional[Point]:
    """Restituisce il punto più vicino a ref tra i candidati."""
    if not candidates:
        return None
    return min(candidates, key=lambda p: _distance(p, ref))


def polyline_line_intersections(
    points: List[Point], closed: bool, p1: Point, p2: Point
) -> List[Tuple[Point, int]]:
    """
    Intersezioni fra la retta infinita (p1, p2) e la spezzata `points` (ogni
    coppia di punti consecutivi è un lato; se `closed`, anche l'ultimo->primo).

    Generalizza `_circle_line_intersections` a qualunque contorno già
    discretizzato in punti — arco, polilinea, cerchio: una volta discretizzato
    è comunque solo una sequenza di lati retti, a prescindere da cos'era in
    origine (usato da `tools/tabs.py::bridge_tabs`).

    Ritorna `(punto, indice)` per ogni intersezione che cade DENTRO il lato
    (non sul suo prolungamento infinito) — `indice` è `i` tale che il lato è
    `(points[i], points[(i+1) % n])`.
    """
    n = len(points)
    if n < 2:
        return []
    edge_indices = range(n) if closed else range(n - 1)
    results: List[Tuple[Point, int]] = []
    for i in edge_indices:
        a, b = points[i], points[(i + 1) % n]
        if a == b:
            continue
        ix = _line_intersection(a, b, p1, p2)
        if ix is None:
            continue
        eps = 1e-9
        if (min(a[0], b[0]) - eps <= ix[0] <= max(a[0], b[0]) + eps
                and min(a[1], b[1]) - eps <= ix[1] <= max(a[1], b[1]) + eps):
            results.append((ix, i))
    return results