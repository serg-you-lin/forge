"""
gap.py
------
Gestione dei gap e overlap tra segmenti LINE e ARC.

Caso 1 — GAP/OVERLAP tra LINE e LINE:
    Calcola l'intersezione delle rette infinite e sposta entrambi gli endpoint.
    Rette parallele → aggiunge LINE di chiusura.

Caso 2 — GAP/OVERLAP tra ARC e LINE:
    Calcola l'intersezione tra la retta infinita della LINE
    e la circonferenza dell'ARC. Sposta l'angolo dell'ARC e l'endpoint della LINE.

Caso 3 — GAP/OVERLAP tra ARC e ARC:
    Calcola l'intersezione tra le due circonferenze.
    Sposta gli angoli di entrambi gli ARC.

Caso 4 — Entità parallele/coincidenti senza intersezione:
    Aggiunge LINE di chiusura tra i due endpoint liberi.

IMPORTANTE: close_gaps lavora SOLO sugli endpoint liberi
(grado < 2 nel grafo topologico — già filtrati dal chiamante).
Gli endpoint già connessi non vengono mai toccati.

TODO: gestire gap tra SPLINE e altre entità.
"""

import math
from typing import Optional, Tuple, List


Point = Tuple[float, float]


# ---------------------------------------------------------------------------
# Geometria — rette
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


# ---------------------------------------------------------------------------
# Geometria — cerchi e archi
# ---------------------------------------------------------------------------

def _arc_endpoint(arc, role: str) -> Point:
    """
    Restituisce il punto geometrico dell'endpoint dell'ARC.
    role='start' → punto all'angolo start_angle
    role='end'   → punto all'angolo end_angle
    """
    cx, cy = arc.dxf.center.x, arc.dxf.center.y
    r = arc.dxf.radius
    angle = arc.dxf.start_angle if role == 'start' else arc.dxf.end_angle
    rad = math.radians(angle)
    return (cx + r * math.cos(rad), cy + r * math.sin(rad))


def _point_to_arc_angle(arc, pt: Point) -> float:
    """
    Dato un punto sulla circonferenza dell'ARC, restituisce l'angolo in gradi.
    """
    cx, cy = arc.dxf.center.x, arc.dxf.center.y
    return math.degrees(math.atan2(pt[1] - cy, pt[0] - cx)) % 360


def _circle_line_intersections(cx: float, cy: float, r: float,
                                p1: Point, p2: Point) -> List[Point]:
    """
    Intersezioni tra la circonferenza (cx,cy,r) e la retta infinita (p1,p2).
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
    """
    Intersezioni tra due circonferenze. Restituisce 0, 1 o 2 punti.
    """
    d = _distance((cx1, cy1), (cx2, cy2))
    if d < 1e-10 or d > r1 + r2 + 1e-10 or d < abs(r1 - r2) - 1e-10:
        return []

    a = (r1 * r1 - r2 * r2 + d * d) / (2 * d)
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
# Endpoint per entity generica
# ---------------------------------------------------------------------------

def _entity_endpoint(entity, role: str) -> Point:
    """Restituisce l'endpoint geometrico di LINE o ARC."""
    if entity.dxftype() == 'LINE':
        if role == 'start':
            return (entity.dxf.start.x, entity.dxf.start.y)
        else:
            return (entity.dxf.end.x, entity.dxf.end.y)
    elif entity.dxftype() == 'ARC':
        return _arc_endpoint(entity, role)
    raise ValueError(f"Tipo entità non supportato: {entity.dxftype()}")


def _line_endpoints(line) -> Tuple[Point, Point]:
    return (line.dxf.start.x, line.dxf.start.y), \
           (line.dxf.end.x,   line.dxf.end.y)


def _set_endpoint(entity, role: str, pt: Point):
    """Sposta l'endpoint dell'entità al punto pt."""
    if entity.dxftype() == 'LINE':
        if role == 'start':
            entity.dxf.start = (pt[0], pt[1], entity.dxf.start.z)
        else:
            entity.dxf.end = (pt[0], pt[1], entity.dxf.end.z)
    elif entity.dxftype() == 'ARC':
        angle = _point_to_arc_angle(entity, pt)
        if role == 'start':
            entity.dxf.start_angle = angle
        else:
            entity.dxf.end_angle = angle


# ---------------------------------------------------------------------------
# Correzione delle coppie
# ---------------------------------------------------------------------------

def _fix_pair(msp, entity_a, role_a, pt_a, entity_b, role_b, pt_b) -> bool:
    """
    Corregge una coppia di endpoint liberi vicini.
    Restituisce True se la coppia è stata corretta.

    Strategia per tipo:
      LINE+LINE  → intersezione rette infinite
      ARC+LINE   → intersezione circonferenza ARC con retta LINE
      ARC+ARC    → intersezione delle due circonferenze
      paralleli  → LINE di chiusura
    """
    type_a = entity_a.dxftype()
    type_b = entity_b.dxftype()

    # ------- LINE + LINE -------
    if type_a == 'LINE' and type_b == 'LINE':
        s_a, e_a = _line_endpoints(entity_a)
        s_b, e_b = _line_endpoints(entity_b)
        ix = _line_intersection(s_a, e_a, s_b, e_b)
        if ix is None:
            msp.add_line((pt_a[0], pt_a[1], 0.0), (pt_b[0], pt_b[1], 0.0))
            return True
        _set_endpoint(entity_a, role_a, ix)
        _set_endpoint(entity_b, role_b, ix)
        return True

    # ------- ARC + LINE  o  LINE + ARC -------
    if (type_a == 'ARC' and type_b == 'LINE') or \
       (type_a == 'LINE' and type_b == 'ARC'):
        arc  = entity_a if type_a == 'ARC' else entity_b
        line = entity_a if type_a == 'LINE' else entity_b
        arc_role  = role_a if type_a == 'ARC' else role_b
        line_role = role_a if type_a == 'LINE' else role_b
        pt_arc    = pt_a if type_a == 'ARC' else pt_b

        s_l, e_l = _line_endpoints(line)
        candidates = _circle_line_intersections(
            arc.dxf.center.x, arc.dxf.center.y, arc.dxf.radius,
            s_l, e_l
        )
        ix = _closest_to(candidates, pt_arc)
        if ix is None:
            msp.add_line((pt_a[0], pt_a[1], 0.0), (pt_b[0], pt_b[1], 0.0))
            return True
        _set_endpoint(arc,  arc_role,  ix)
        _set_endpoint(line, line_role, ix)
        return True

    # ------- ARC + ARC -------
    if type_a == 'ARC' and type_b == 'ARC':
        candidates = _circle_circle_intersections(
            entity_a.dxf.center.x, entity_a.dxf.center.y, entity_a.dxf.radius,
            entity_b.dxf.center.x, entity_b.dxf.center.y, entity_b.dxf.radius,
        )
        ix = _closest_to(candidates, pt_a)
        if ix is None:
            msp.add_line((pt_a[0], pt_a[1], 0.0), (pt_b[0], pt_b[1], 0.0))
            return True
        _set_endpoint(entity_a, role_a, ix)
        _set_endpoint(entity_b, role_b, ix)
        return True

    # ------- SPLINE + qualsiasi -------
    if type_a == 'SPLINE' or type_b == 'SPLINE':
        msp.add_line((pt_a[0], pt_a[1], 0.0), (pt_b[0], pt_b[1], 0.0))
        return True
    
    return False


# ---------------------------------------------------------------------------
# API pubblica
# ---------------------------------------------------------------------------

def close_gaps(msp, free_endpoints: List, tolerance: float) -> int:
    """
    Corregge gap e overlap tra LINE e ARC usando solo gli endpoint liberi
    (grado < 2 nel grafo — già filtrati da _free_endpoints in healer.py).

    Args:
        msp:            modelspace ezdxf
        free_endpoints: lista di (point, entity, role) — endpoint liberi
                        entity può essere LINE o ARC
        tolerance:      distanza massima per considerare una coppia correggibile

    Returns:
        Numero di coppie corrette.
    """

    if len(free_endpoints) < 2:
        return 0

    fixed = 0
    checked = set()

    for i, (pt_a, entity_a, role_a) in enumerate(free_endpoints):
        for j, (pt_b, entity_b, role_b) in enumerate(free_endpoints):
            if i >= j:
                continue
            if entity_a is entity_b:
                continue
            pair_key = (id(entity_a), id(entity_b), role_a, role_b)
            if pair_key in checked:
                continue
            checked.add(pair_key)

            if _distance(pt_a, pt_b) > tolerance:
                continue

            if _fix_pair(msp, entity_a, role_a, pt_a, entity_b, role_b, pt_b):
                fixed += 1

    return fixed