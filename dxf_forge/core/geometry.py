
"""
geometry.py
-----------
Funzioni geometriche pure per dxf-forge.

Nessuna dipendenza da modelli o layer — solo geometria.
Importato da healer.py, graph.py e chiunque abbia bisogno
di convertire entità DXF in geometria Shapely.
"""

import math
import numpy as np
from ezdxf.math import bulge_to_arc
from typing import Optional
from shapely.geometry import Point, MultiPoint, Polygon

# ---------------------------------------------------------------------------
# Registries
# ---------------------------------------------------------------------------

_LENGTH_HANDLERS    = {}
_POLYGON_HANDLERS   = {}
_REPR_PT_HANDLERS   = {}
_COPY_HANDLERS = {}


def register_length(dxftype: str):
    def decorator(fn):
        _LENGTH_HANDLERS[dxftype] = fn
        return fn
    return decorator


def register_polygon(dxftype: str):
    def decorator(fn):
        _POLYGON_HANDLERS[dxftype] = fn
        return fn
    return decorator


def register_repr_pt(*dxftypes: str):
    def decorator(fn):
        for t in dxftypes:
            _REPR_PT_HANDLERS[t] = fn
        return fn
    return decorator


# ---------------------------------------------------------------------------
# Endpoint di entità
# ---------------------------------------------------------------------------

def arc_endpoints(entity):
    """Restituisce (start_pt, end_pt) di un ARC come tuple (x, y)."""
    cx, cy = entity.dxf.center.x, entity.dxf.center.y
    r = entity.dxf.radius
    start_pt = (
        cx + r * np.cos(np.radians(entity.dxf.start_angle)),
        cy + r * np.sin(np.radians(entity.dxf.start_angle)),
    )
    end_pt = (
        cx + r * np.cos(np.radians(entity.dxf.end_angle)),
        cy + r * np.sin(np.radians(entity.dxf.end_angle)),
    )
    return start_pt, end_pt


def arc_to_bulge(entity, reversed=False):
    """
    Converte un ARC in (entry_pt, exit_pt, bulge) per LWPOLYLINE.
    Se reversed=True, inverte direzione e segno del bulge.
    """
    start_angle = entity.dxf.start_angle
    end_angle   = entity.dxf.end_angle
    if end_angle < start_angle:
        end_angle += 360.0
    delta = end_angle - start_angle
    bulge = np.tan(np.radians(delta) / 4.0)
    start_pt, end_pt = arc_endpoints(entity)
    if reversed:
        return end_pt, start_pt, -bulge
    return start_pt, end_pt, bulge


def arc_to_linestrings(entity, num_segments=8):
    """
    Approssima un ARC in segmenti LineString Shapely.
    Usato nel fallback polygonize.
    """
    from shapely.geometry import LineString
    cx, cy = entity.dxf.center.x, entity.dxf.center.y
    r = entity.dxf.radius
    start = np.radians(entity.dxf.start_angle)
    end   = np.radians(entity.dxf.end_angle)
    if start > end:
        end += 2 * np.pi
    angles = np.linspace(start, end, num_segments + 1)
    pts = [(cx + r * np.cos(a), cy + r * np.sin(a)) for a in angles]
    return [LineString([pts[i], pts[i + 1]]) for i in range(len(pts) - 1)]


# ---------------------------------------------------------------------------
# Conversione entità → Polygon Shapely
# ---------------------------------------------------------------------------

def entity_to_polygon(entity) -> Optional[Polygon]:
    """
    Converte qualsiasi entità strutturale in un Polygon Shapely.
    Usa registry handlers per dxftype(). Restituisce None se non riesce.
    """
    handler = _POLYGON_HANDLERS.get(entity.dxftype())
    if handler is None:
        return None
    try:
        return handler(entity)
    except Exception:
        return None


@register_polygon('LWPOLYLINE')
@register_polygon('POLYLINE')
def _polygon_pline(entity) -> Optional[Polygon]:
    return pline_to_polygon(entity)


@register_polygon('CIRCLE')
def _polygon_circle(entity) -> Optional[Polygon]:
    return Point(entity.dxf.center.x, entity.dxf.center.y).buffer(entity.dxf.radius)


@register_polygon('SPLINE')
@register_polygon('ELLIPSE')
def _polygon_flattened(entity) -> Optional[Polygon]:
    pts = [(p[0], p[1]) for p in entity.flattening(0.01)]
    if len(pts) < 3:
        return None
    poly = Polygon(pts)
    if not poly.is_valid:
        poly = poly.buffer(0)
    return poly if not poly.is_empty else None


def pline_to_polygon(pline) -> Optional[Polygon]:
    if pline.dxftype() == 'POLYLINE':
        pts = [(v.dxf.location.x, v.dxf.location.y) for v in pline.vertices]
    else:
        pts = []
        points = list(pline.get_points('xyb'))
        n = len(points)
        for i in range(n):
            x1, y1, bulge = points[i]
            x2, y2, _     = points[(i + 1) % n]
            pts.append((x1, y1))
            if abs(bulge) > 1e-6:
                center, start_angle, end_angle, radius = bulge_to_arc(
                    (x1, y1), (x2, y2), bulge
                )
                cx, cy = center.x, center.y
                a1 = math.atan2(y1 - cy, x1 - cx)
                a2 = math.atan2(y2 - cy, x2 - cx)
                if bulge > 0:
                    if a2 <= a1:
                        a2 += 2 * math.pi
                else:
                    if a2 >= a1:
                        a2 -= 2 * math.pi
                angle = a2 - a1
                num_seg = num_segments_for_bulge(bulge)
    
                for j in range(1, num_seg):
                    a = a1 + angle * j / num_seg
                    pts.append((cx + radius * math.cos(a),
                                cy + radius * math.sin(a)))

    if len(pts) < 3:
        return None
    try:
        poly = Polygon(pts)
        if not poly.is_valid:
            poly = poly.buffer(0)
        if poly.geom_type == 'MultiPolygon':
            poly = max(poly.geoms, key=lambda p: p.area)
        if poly and not poly.is_empty:
            pass
        return poly if not poly.is_empty else None
    except Exception:
        return None


def circle_to_polygon(entity, num_segments=64) -> Optional[Polygon]:
    """Converte un CIRCLE in Polygon Shapely."""
    cx, cy = entity.dxf.center.x, entity.dxf.center.y
    r = entity.dxf.radius
    angles = np.linspace(0, 2 * np.pi, num_segments, endpoint=False)
    pts = [(cx + r * np.cos(a), cy + r * np.sin(a)) for a in angles]
    try:
        poly = Polygon(pts)
        if not poly.is_valid:
            poly = poly.buffer(0)
        return poly if not poly.is_empty else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Lunghezza entità
# ---------------------------------------------------------------------------

def entity_length(entity) -> float:
    """
    Calcola la lunghezza di una entità DXF.
    Usa registry handlers per dxftype().
    Restituisce 0.0 se il tipo non è supportato o il calcolo fallisce.
    """
    handler = _LENGTH_HANDLERS.get(entity.dxftype())
    if handler is None:
        return 0.0
    try:
        return handler(entity)
    except Exception:
        return 0.0


@register_length('LINE')
def _line_length(entity) -> float:
    s = entity.dxf.start
    e = entity.dxf.end
    return math.hypot(e.x - s.x, e.y - s.y)


@register_length('ARC')
def _arc_length(entity) -> float:
    angle = entity.dxf.end_angle - entity.dxf.start_angle
    if angle < 0:
        angle += 360
    return math.radians(angle) * entity.dxf.radius


@register_length('CIRCLE')
def _circle_length(entity) -> float:
    return 2 * math.pi * entity.dxf.radius


@register_length('LWPOLYLINE')
@register_length('POLYLINE')
def _polyline_length(entity) -> float:
    pts = [p[:2] for p in entity.get_points()]
    length = 0.0
    for i in range(len(pts) - 1):
        dx = pts[i + 1][0] - pts[i][0]
        dy = pts[i + 1][1] - pts[i][1]
        length += math.hypot(dx, dy)
    return length


@register_length('SPLINE')
def _spline_length(entity) -> float:
    pts = list(entity.flattening(distance=0.01))
    length = 0.0
    for i in range(len(pts) - 1):
        dx = pts[i + 1][0] - pts[i][0]
        dy = pts[i + 1][1] - pts[i][1]
        length += math.hypot(dx, dy)
    return length


# ---------------------------------------------------------------------------
# Punto rappresentativo
# ---------------------------------------------------------------------------

def get_representative_point(entity) -> Optional[Point]:
    """
    Restituisce un punto rappresentativo dell'entità.
    Usa registry handlers per dxftype(). Restituisce None se non riesce.
    """
    handler = _REPR_PT_HANDLERS.get(entity.dxftype())
    if handler is None:
        return _repr_pt_fallback(entity)
    try:
        return handler(entity)
    except Exception:
        return None


@register_repr_pt('LINE')
def _repr_pt_line(entity) -> Optional[Point]:
    s, e = entity.dxf.start, entity.dxf.end
    return Point((s.x + e.x) / 2, (s.y + e.y) / 2)


@register_repr_pt('CIRCLE', 'ARC', 'ELLIPSE')
def _repr_pt_centered(entity) -> Optional[Point]:
    c = entity.dxf.center
    return Point(c.x, c.y)


@register_repr_pt('TEXT', 'MTEXT')
def _repr_pt_text(entity) -> Optional[Point]:
    p = entity.dxf.insert
    return Point(p.x, p.y)


@register_repr_pt('MULTILEADER')
def _repr_pt_multileader(entity) -> Optional[Point]:
    try:
        pt = entity.context.mtext.insert
        return Point(pt.x, pt.y)
    except Exception:
        pass
    try:
        pt = entity.context.leaders[0].lines[0].vertices[0]
        return Point(pt.x, pt.y)
    except Exception:
        return None


@register_repr_pt('INSERT')
def _repr_pt_insert(entity) -> Optional[Point]:
    p = entity.dxf.insert
    return Point(p.x, p.y)


@register_repr_pt('LWPOLYLINE')
def _repr_pt_lwpolyline(entity) -> Optional[Point]:
    pts = [(p[0], p[1]) for p in entity.get_points()]
    return MultiPoint(pts).convex_hull.representative_point()


@register_repr_pt('SPLINE')
def _repr_pt_spline(entity) -> Optional[Point]:
    pts = [(p[0], p[1]) for p in entity.control_points]
    return MultiPoint(pts).convex_hull.representative_point()


@register_repr_pt('HATCH')
def _repr_pt_hatch(entity) -> Optional[Point]:
    if entity.seeds:
        return Point(entity.seeds[0][0], entity.seeds[0][1])
    return None


@register_repr_pt('DIMENSION')
def _repr_pt_dimension(entity) -> Optional[Point]:
    p = entity.dxf.defpoint
    return Point(p.x, p.y)


def _repr_pt_fallback(entity) -> Optional[Point]:
    """Fallback per tipi non registrati: cerca insert/start/center."""
    try:
        for attr in ('insert', 'start', 'center'):
            if entity.dxf.hasattr(attr):
                p = getattr(entity.dxf, attr)
                return Point(p.x, p.y)
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Copia entità — registry
# ---------------------------------------------------------------------------

def register_copy(*dxftypes: str):
    """Decorator per registrare un handler di copia per uno o più dxftype."""
    def decorator(fn):
        for t in dxftypes:
            _COPY_HANDLERS[t] = fn
        return fn
    return decorator
 
 
def copy_entity(entity, target_msp) -> None:
    """
    Copia una singola entità DXF nel target_msp.
    Gestisce: LINE, CIRCLE, ARC, TEXT, MTEXT, MULTILEADER, INSERT,
              LWPOLYLINE (preserva closed), SPLINE, ELLIPSE.
    Tipi non registrati vengono ignorati silenziosamente.
    """
    dxftype = entity.dxftype()
    handler = _COPY_HANDLERS.get(dxftype)
    if handler is None:
        return
 
    attribs = entity.dxfattribs()
    attribs.pop('handle', None)
    attribs.pop('owner', None)
    attribs.pop('color', None)
    attribs.pop('true_color', None)
 
    try:
        handler(entity, target_msp, attribs)
    except Exception as ex:
        print(f"  [WARN] Copia {dxftype} fallita: {ex}")
 
 
@register_copy('LINE')
def _copy_line(entity, msp, attribs) -> None:
    msp.add_line(entity.dxf.start, entity.dxf.end, dxfattribs=attribs)
 
 
@register_copy('CIRCLE')
def _copy_circle(entity, msp, attribs) -> None:
    msp.add_circle(entity.dxf.center, entity.dxf.radius, dxfattribs=attribs)
 
 
@register_copy('ARC')
def _copy_arc(entity, msp, attribs) -> None:
    msp.add_arc(
        entity.dxf.center, entity.dxf.radius,
        entity.dxf.start_angle, entity.dxf.end_angle,
        dxfattribs=attribs,
    )
 
 
@register_copy('TEXT')
def _copy_text(entity, msp, attribs) -> None:
    msp.add_text(entity.dxf.text, dxfattribs=attribs)
 
 
@register_copy('MTEXT')
def _copy_mtext(entity, msp, attribs) -> None:
    msp.add_mtext(entity.text, dxfattribs=attribs)
 
 
@register_copy('MULTILEADER')
def _copy_multileader(entity, msp, attribs) -> None:
    try:
        msp.doc.entitydb
        new_entity = entity.copy()
        msp.add_entity(new_entity)
    except Exception as ex:
        print(f"  [WARN] Copia MULTILEADER fallita: {ex}")
 
 
@register_copy('INSERT')
def _copy_insert(entity, msp, attribs) -> None:
    msp.add_blockref(entity.dxf.name, entity.dxf.insert, dxfattribs=attribs)
 
 
@register_copy('LWPOLYLINE')
def _copy_lwpolyline(entity, msp, attribs) -> None:
    pts = list(entity.get_points(format='xyseb'))
    msp.add_lwpolyline(pts, format='xyseb', dxfattribs=attribs, close=entity.closed)
 


@register_copy('SPLINE')
def _copy_spline(entity, msp, attribs) -> None:
    new_entity = entity.copy()
    new_entity.dxf.layer = attribs.get('layer', entity.dxf.layer)
    new_entity.dxf.color = attribs.get('color', entity.dxf.color)
    msp.add_entity(new_entity)


@register_copy('ELLIPSE')
def _copy_ellipse(entity, msp, attribs) -> None:
    msp.add_ellipse(
        entity.dxf.center,
        entity.dxf.major_axis,
        entity.dxf.ratio,
        entity.dxf.start_param,
        entity.dxf.end_param,
        dxfattribs=attribs,
    )

# ---------------------------------------------------------------------------
# Utilità
# ---------------------------------------------------------------------------

def round_point(pt, decimals=1):
    return (round(float(pt[0]), decimals), round(float(pt[1]), decimals))

def num_segments_for_bulge(bulge: float) -> int:
    """Numero di segmenti per discretizzare un arco dato il suo bulge."""
    angle = 4 * math.atan(abs(bulge))
    return max(8, int(angle / math.pi * 32))


def _line_direction(line) -> tuple:
    """
    Vettore direzione normalizzato di una LINE, orientato canonicamente
    (dx >= 0; se dx==0 allora dy > 0) — così due segmenti paralleli opposti
    hanno lo stesso vettore.
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


def _point_to_line_distance(px, py, line) -> float:
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
    Restituisce lista di gruppi: [[L1,L2], [L3,L4], ...]
    """
    groups = []
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

def spline_to_points(spline, tolerance=0.01):
    """
    Discretizza una SPLINE in una lista di punti (x, y).
    Restituisce lista vuota se fallisce.
    """
    try:
        pts = list(spline.flattening(tolerance))
        return [(p[0], p[1]) for p in pts]
    except Exception:
        return []
    
# ---------------------------------------------------------------------------
# Rilevamento fori speciali
# ---------------------------------------------------------------------------

def is_threaded_arc(arc, angle_tolerance: float = 20.0) -> bool:
    if arc.dxftype() != 'ARC':
        return False
    cx, cy = arc.dxf.center.x, arc.dxf.center.y
    r = arc.dxf.radius
    start_rad = math.radians(arc.dxf.start_angle)
    end_rad   = math.radians(arc.dxf.end_angle)
    p_start = (cx + r * math.cos(start_rad), cy + r * math.sin(start_rad))
    p_end   = (cx + r * math.cos(end_rad),   cy + r * math.sin(end_rad))
    a1 = math.atan2(p_start[1] - cy, p_start[0] - cx)
    a2 = math.atan2(p_end[1] - cy,   p_end[0] - cx)
    gap   = math.degrees(abs(a1 - a2)) % 360
    swept = 360 - gap
    return abs(swept - 270) < angle_tolerance


def is_threaded_hole(circle, all_arcs, tolerance_center: float = 1.0) -> bool:
    cx = circle.dxf.center.x
    cy = circle.dxf.center.y
    for arc in all_arcs:
        dist = np.hypot(cx - arc.dxf.center.x, cy - arc.dxf.center.y)
        if dist < tolerance_center \
           and arc.dxf.radius > circle.dxf.radius \
           and is_threaded_arc(arc):
            return True
    return False


def is_countersink_outer(circle, siblings: list, tolerance: float = 1.0) -> bool:
    """
    Restituisce True se `circle` è il cerchio esterno di una svasatura.
 
    Una svasatura è composta da due cerchi concentrici (stesso centro,
    raggi diversi). Il cerchio esterno contiene il cerchio interno.
 
    Args:
        circle:    entità CIRCLE ezdxf da testare
        siblings:  lista di ForgeContour — gli altri inner dello stesso ForgePart.
                   Ogni ForgeContour deve avere .entity popolato (non None).
        tolerance: distanza massima tra centri per considerarli concentrici (mm)
 
    Returns:
        True se esiste almeno un altro CIRCLE concentrico con raggio minore.
    """
    cx = circle.dxf.center.x
    cy = circle.dxf.center.y
    cr = circle.dxf.radius
 
    for sibling in siblings:
        other = sibling.entity
        if other is None:
            continue
        if other.dxftype() != "CIRCLE":
            continue
        if other is circle:
            continue
 
        ox  = other.dxf.center.x
        oy  = other.dxf.center.y
        or_ = other.dxf.radius
 
        if or_ >= cr:
            continue  # cerca solo cerchi interni (raggio minore)
 
        dist = np.hypot(cx - ox, cy - oy)
        if dist < tolerance:
            return True
 
    return False



# ---------------------------------------------------------------------------
# Deprecated
# ---------------------------------------------------------------------------

def circle_to_lwpolyline(msp, entity, layer, color):
    """
    Converte un CIRCLE in LWPOLYLINE chiusa con bulge=1 (2 semicerchi).
    """
    cx, cy = entity.dxf.center.x, entity.dxf.center.y
    r = entity.dxf.radius
    pts_with_bulge = [
        (cx - r, cy, 0.0, 0.0, 1.0),
        (cx + r, cy, 0.0, 0.0, 1.0),
    ]
    msp.add_lwpolyline(
        pts_with_bulge,
        format='xyseb',
        dxfattribs={'layer': layer, 'color': color},
        close=True,
    )