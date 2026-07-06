

"""
core/geometry.py
----------------
Funzioni geometriche pure per dxf-forge.

Nessuna dipendenza da ezdxf o da modelli di dominio.
Solo math, numpy, shapely.

Importato da:
    - adapters/dxf/geometry_adapter.py  (calcoli geometrici su entità)
    - core/graph.py                     (utilità topologiche)
"""

import math
from typing import Optional, Tuple, List

Point = Tuple[float, float]


# ---------------------------------------------------------------------------
# Arrotondamento
# ---------------------------------------------------------------------------

def round_point(pt, decimals: int = 1) -> Tuple:
    return (round(float(pt[0]), decimals), round(float(pt[1]), decimals))


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

def _line_direction(line) -> Tuple[float, float]:
    """
    Vettore direzione normalizzato di una LINE, orientato canonicamente
    (dx >= 0; se dx==0 allora dy > 0).
    Due segmenti paralleli opposti hanno lo stesso vettore.
    """
    dx = line.dxf.end.x - line.dxf.start.x
    dy = line.dxf.end.y - line.dxf.start.y
    length = (dx**2 + dy**2) ** 0.5
    if length == 0:
        return (0.0, 0.0)
    dx, dy = dx / length, dy / length
    if dx < 0 or (dx == 0 and dy < 0):
        dx, dy = -dx, -dy
    return (dx, dy)


def _point_to_line_distance(px: float, py: float, line) -> float:
    """Distanza di un punto dalla retta infinita definita da line."""
    ax, ay = line.dxf.start.x, line.dxf.start.y
    bx, by = line.dxf.end.x,   line.dxf.end.y
    dx, dy = bx - ax, by - ay
    length = (dx**2 + dy**2) ** 0.5
    if length == 0:
        return ((px - ax)**2 + (py - ay)**2) ** 0.5
    cross = abs(dx * (ay - py) - dy * (ax - px))
    return cross / length


def are_collinear(line_a, line_b, tolerance: float = 0.1) -> bool:
    """
    Restituisce True se due LINE giacciono sulla stessa retta infinita.
    Criteri: stessa direzione + distanza punto-retta entro tolleranza (mm).
    """
    dir_a = _line_direction(line_a)
    dir_b = _line_direction(line_b)
    cross = abs(dir_a[0] * dir_b[1] - dir_a[1] * dir_b[0])
    if cross > 1e-6:
        return False
    dist = _point_to_line_distance(
        line_b.dxf.start.x, line_b.dxf.start.y, line_a
    )
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
# Intersezioni geometriche pure — usate da geometry_adapter (gap closing)
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

# ---------------------------------------------------------------------------
# spline_endpoints — helper per geometry_adapter e graph_adapter
# ---------------------------------------------------------------------------

def spline_endpoints(spline):
    """
    Restituisce (start, end) come tuple (x, y) di una SPLINE ezdxf.
    Unica funzione di questo modulo che tocca ezdxf — accetta l'entity
    ma legge solo i punti flattening, non entity.dxf.
    """
    try:
        pts = list(spline.flattening(0.01))
        if len(pts) < 2:
            return None, None
        return (pts[0][0], pts[0][1]), (pts[-1][0], pts[-1][1])
    except Exception:
        return None, None