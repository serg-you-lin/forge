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
from typing import Callable, Optional, Set
from shapely.geometry import Point, MultiPoint, Polygon


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
    return [LineString([pts[i], pts[i+1]]) for i in range(len(pts) - 1)]




# ---------------------------------------------------------------------------
# Conversione entità → Polygon Shapely
# ---------------------------------------------------------------------------
def entity_to_polygon(entity) -> Optional[Polygon]:
    """
    Converte qualsiasi entità strutturale (LWPOLYLINE, CIRCLE, SPLINE, ELLIPSE)
    in un Polygon Shapely. Restituisce None se non riesce.
    """
    t = entity.dxftype()
    try:
        if t in ('LWPOLYLINE', 'POLYLINE'):
            return pline_to_polygon(entity)
        elif t == 'CIRCLE':
            return Point(entity.dxf.center.x, entity.dxf.center.y).buffer(entity.dxf.radius)
        elif t == 'SPLINE':
            pts = [(p[0], p[1]) for p in entity.flattening(0.01)]
            if len(pts) < 3:
                return None
            poly = Polygon(pts)
            if not poly.is_valid:
                poly = poly.buffer(0)
            return poly if not poly.is_empty else None
        elif t == 'ELLIPSE':
            pts = [(p[0], p[1]) for p in entity.flattening(0.01)]
            if len(pts) < 3:
                return None
            poly = Polygon(pts)
            if not poly.is_valid:
                poly = poly.buffer(0)
            return poly if not poly.is_empty else None
    except Exception:
        pass
    return None

from ezdxf.math import bulge_to_arc

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
                
                # Ricalcola angoli direttamente dai punti — ignora start/end_angle di ezdxf
                a1 = math.atan2(y1 - cy, x1 - cx)
                a2 = math.atan2(y2 - cy, x2 - cx)
                
                if bulge > 0:  # antiorario
                    if a2 <= a1:
                        a2 += 2 * math.pi
                else:          # orario
                    if a2 >= a1:
                        a2 -= 2 * math.pi

                angle = a2 - a1
                num_seg = max(8, int(abs(angle) / math.pi * 32))
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
        return poly if not poly.is_empty else None
    except Exception:
        return None
# def pline_to_polygon(pline) -> Polygon:
#     """
#     Converte una LWPOLYLINE o POLYLINE in Polygon Shapely.
#     Gestisce i segmenti con bulge (archi) discretizzandoli.
#     """
#     if pline.dxftype() == 'POLYLINE':
#         pts = [(v.dxf.location.x, v.dxf.location.y) for v in pline.vertices]
#     else:
#         pts = []
#         points = list(pline.get_points('xyb'))
#         n = len(points)
#         for i in range(n):
#             x1, y1, bulge = points[i]
#             x2, y2, _     = points[(i + 1) % n]
#             pts.append((x1, y1))
#             if abs(bulge) > 1e-6:
#                 angle = 4 * math.atan(bulge)
#                 cx = ((x1 + x2) / 2) + ((y2 - y1) / 2) * ((1 - bulge**2) / (2 * bulge))
#                 cy = ((y1 + y2) / 2) - ((x2 - x1) / 2) * ((1 - bulge**2) / (2 * bulge))
#                 r  = math.sqrt((x1 - cx)**2 + (y1 - cy)**2)
#                 a1 = math.atan2(y1 - cy, x1 - cx)
#                 num_seg = max(8, int(abs(angle) / math.pi * 32))
#                 for j in range(1, num_seg):
#                     a = a1 + angle * j / num_seg
#                     pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))

#     if len(pts) < 3:
#         return None
#     try:
#         poly = Polygon(pts)
#         if not poly.is_valid:
#             poly = poly.buffer(0)
#         if poly.geom_type == 'MultiPolygon':
#             poly = max(poly.geoms, key=lambda p: p.area)
#         return poly if not poly.is_empty else None
#     except Exception:
#         return None
    

def circle_to_polygon(entity, num_segments=64) -> Polygon:
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
    Supporta LINE, ARC, CIRCLE, LWPOLYLINE, POLYLINE, SPLINE.
    Restituisce 0.0 se non calcolabile.
    """
    dxftype = entity.dxftype()
    try:
        if dxftype == 'LINE':
            s = entity.dxf.start
            e = entity.dxf.end
            return math.sqrt((e.x - s.x)**2 + (e.y - s.y)**2)

        elif dxftype == 'ARC':
            angle = entity.dxf.end_angle - entity.dxf.start_angle
            if angle < 0:
                angle += 360
            return math.radians(angle) * entity.dxf.radius

        elif dxftype == 'CIRCLE':
            return 2 * math.pi * entity.dxf.radius

        elif dxftype in ('LWPOLYLINE', 'POLYLINE'):
            pts = [p[:2] for p in entity.get_points()]
            length = 0.0
            for i in range(len(pts) - 1):
                dx = pts[i+1][0] - pts[i][0]
                dy = pts[i+1][1] - pts[i][1]
                length += math.sqrt(dx*dx + dy*dy)
            return length

        elif dxftype == 'SPLINE':
            pts = list(entity.flattening(distance=0.01))
            length = 0.0
            for i in range(len(pts) - 1):
                dx = pts[i+1][0] - pts[i][0]
                dy = pts[i+1][1] - pts[i][1]
                length += math.sqrt(dx*dx + dy*dy)
            return length

    except Exception:
        pass
    return 0.0



# ---------------------------------------------------------------------------
# Utilità
# ---------------------------------------------------------------------------


def round_point(pt, decimals=1):
    return (round(float(pt[0]), decimals), round(float(pt[1]), decimals))


def get_representative_point(entity) -> Optional[Point]:
    dxftype = entity.dxftype()
    try:
        if dxftype == 'LINE':
            s, e = entity.dxf.start, entity.dxf.end
            return Point((s.x + e.x) / 2, (s.y + e.y) / 2)
        elif dxftype in ('CIRCLE', 'ARC', 'ELLIPSE'):
            c = entity.dxf.center
            return Point(c.x, c.y)
        elif dxftype in ('TEXT', 'MTEXT'):
            p = entity.dxf.insert
            return Point(p.x, p.y)
        elif dxftype == 'MULTILEADER':
            try:
                pt = entity.context.mtext.insert
                return Point(pt.x, pt.y)
            except Exception:
                pass
            try:
                # fallback: primo punto della leader line
                pt = entity.context.leaders[0].lines[0].vertices[0]
                return Point(pt.x, pt.y)
            except Exception:
                pass
            return None

        elif dxftype == 'INSERT':
            p = entity.dxf.insert
            return Point(p.x, p.y)
        elif dxftype == 'LWPOLYLINE':
            pts = [(p[0], p[1]) for p in entity.get_points()]
            return MultiPoint(pts).convex_hull.representative_point()
        elif dxftype == 'SPLINE':
            pts = [(p[0], p[1]) for p in entity.control_points]
            return MultiPoint(pts).convex_hull.representative_point()
        elif dxftype == 'HATCH':
            if entity.seeds:
                return Point(entity.seeds[0][0], entity.seeds[0][1])
        elif dxftype == 'DIMENSION':
            p = entity.dxf.defpoint
            return Point(p.x, p.y)
        else:
            for attr in ('insert', 'start', 'center'):
                if entity.dxf.hasattr(attr):
                    p = getattr(entity.dxf, attr)
                    return Point(p.x, p.y)
    except Exception:
        pass
    return None



def copy_entity(entity, target_msp) -> None:
    """
    Copia una singola entità DXF nel target_msp.
    Gestisce: LINE, CIRCLE, ARC, TEXT, MTEXT, INSERT,
              LWPOLYLINE (preserva closed), SPLINE, ELLIPSE.
    """
    dxftype = entity.dxftype()
    attribs = entity.dxfattribs()
    attribs.pop('handle', None)
    attribs.pop('owner', None)
    attribs.pop('color', None)
    attribs.pop('true_color', None)
    try:
        if dxftype == 'LINE':
            target_msp.add_line(entity.dxf.start, entity.dxf.end,
                                dxfattribs=attribs)
        elif dxftype == 'CIRCLE':
            target_msp.add_circle(entity.dxf.center, entity.dxf.radius,
                                  dxfattribs=attribs)
        elif dxftype == 'ARC':
            target_msp.add_arc(entity.dxf.center, entity.dxf.radius,
                               entity.dxf.start_angle, entity.dxf.end_angle,
                               dxfattribs=attribs)
        elif dxftype == 'TEXT':
            target_msp.add_text(entity.dxf.text, dxfattribs=attribs)
        elif dxftype == 'MTEXT':
            target_msp.add_mtext(entity.text, dxfattribs=attribs)
        elif dxftype == 'MULTILEADER':
            try:
                target_msp.doc.entitydb  # verifica che il doc sia disponibile
                new_entity = entity.copy()
                target_msp.add_entity(new_entity)
            except Exception as ex:
                print(f"  [WARN] Copia MULTILEADER fallita: {ex}")
        elif dxftype == 'INSERT':
            target_msp.add_blockref(entity.dxf.name, entity.dxf.insert,
                                    dxfattribs=attribs)
        elif dxftype == 'LWPOLYLINE':
            pts = list(entity.get_points(format='xyseb'))
            target_msp.add_lwpolyline(pts, format='xyseb', dxfattribs=attribs,
                                      close=entity.closed)
            
        elif dxftype == 'SPLINE':
            attribs.pop('degree', None)
            attribs.pop('closed', None)      # ← rimuovi anche questo da attribs
            attribs.pop('n_knots', None)     # altri che potrebbero dare fastidio
            attribs.pop('n_control_points', None)
            attribs.pop('n_fit_points', None)
            
            degree = entity.dxf.get('degree', 3)
            new_spline = target_msp.add_spline(degree=degree, dxfattribs=attribs)
            
            new_spline.control_points = entity.control_points
            
            if entity.knots:
                new_spline.knots = entity.knots
            if entity.weights:
                new_spline.weights = entity.weights
            if entity.fit_points:
                new_spline.fit_points = entity.fit_points
                
            # closed si imposta tramite il flag, non come dxf attribute
            if entity.closed:
                new_spline.closed = True
        # elif dxftype == 'SPLINE':
        #     spline = target_msp.add_spline(entity.control_points, dxfattribs=attribs)
        #     spline.degree = entity.degree
        #     spline.closed = entity.closed
        #     if entity.knots:
        #         spline.knots = entity.knots
        #     if entity.weights:
        #         spline.weights = entity.weights

        elif dxftype == 'ELLIPSE':
            target_msp.add_ellipse(
                entity.dxf.center,
                entity.dxf.major_axis,
                entity.dxf.ratio,
                entity.dxf.start_param,
                entity.dxf.end_param,
                dxfattribs=attribs,
            )
    except Exception as ex:
        print(f"  [WARN] Copia {dxftype} fallita: {ex}")


def _line_direction(line) -> tuple:
    """
    Restituisce il vettore direzione normalizzato di una LINE ezdxf.
    Sempre orientato in modo canonico (dx >= 0, se dx==0 allora dy > 0)
    così due segmenti paralleli opposti hanno lo stesso vettore.
    """
    dx = line.dxf.end.x - line.dxf.start.x
    dy = line.dxf.end.y - line.dxf.start.y
    length = (dx**2 + dy**2) ** 0.5
    if length == 0:
        return (0.0, 0.0)
    dx, dy = dx / length, dy / length
    # canonicalizza: dx sempre >= 0
    if dx < 0 or (dx == 0 and dy < 0):
        dx, dy = -dx, -dy
    return (dx, dy)


def _point_to_line_distance(px, py, line) -> float:
    """
    Distanza di un punto (px, py) dalla retta infinita definita da line.
    Formula: |cross(AB, AP)| / |AB|
    """
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
    Restituisce True se due LINE ezdxf giacciono sulla stessa retta infinita.

    Due segmenti sono collineari se:
    1. Hanno la stessa direzione (paralleli)
    2. Un punto di line_b è sulla retta di line_a (entro tolleranza)

    Args:
        line_a:    entità LINE ezdxf
        line_b:    entità LINE ezdxf
        tolerance: distanza massima mm per considerarli sulla stessa retta

    Returns:
        True se collineari, False altrimenti.
    """
    dir_a = _line_direction(line_a)
    dir_b = _line_direction(line_b)

    # cross product tra versori — soglia angolare, NON in mm
    cross = abs(dir_a[0] * dir_b[1] - dir_a[1] * dir_b[0])
    if cross > 1e-6:
        return False

    # distanza punto-retta — questa sì è in mm
    dist = _point_to_line_distance(
        line_b.dxf.start.x, line_b.dxf.start.y, line_a
    )
    return dist <= tolerance


def group_collinear_lines(lines: list, tolerance: float = 0.1) -> list:
    """
    Raggruppa una lista di LINE ezdxf in gruppi collineari.

    Linee sulla stessa retta infinita finiscono nello stesso gruppo,
    indipendentemente da gap o sovrapposizioni tra i segmenti.

    Args:
        lines:     lista di entità LINE ezdxf
        tolerance: tolleranza mm per are_collinear()

    Returns:
        Lista di gruppi, ogni gruppo è una lista di LINE collineari.
        Esempio: 6 segmenti su 3 rette → [[L1,L2], [L3,L4], [L5,L6]]
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