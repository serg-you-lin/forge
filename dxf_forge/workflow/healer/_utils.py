from shapely.geometry import Polygon, Point
from ...core.geometry import arc_to_bulge, entity_midpoint
from ...core.graph import spline_to_points, loop_to_points


def _deduplicate_loops(loops):
    """Per ogni coppia diretta/inversa, tieni solo quella con area maggiore."""
    
    seen = {}  # frozenset(id) -> (loop, area)
    for loop in loops:
        key = frozenset(id(e) for e, _ in loop)
        pts = []
        for entity, rev in loop:
            if entity.dxftype() == 'LINE':
                pts.append(
                    (entity.dxf.end.x, entity.dxf.end.y) if rev
                    else (entity.dxf.start.x, entity.dxf.start.y)
                )
            elif entity.dxftype() == 'ARC':
                entry_pt, _, _ = arc_to_bulge(entity, reversed=rev)
                pts.append(entry_pt)
            elif entity.dxftype() == 'SPLINE':
                spline_pts = spline_to_points(entity)
                if rev:
                    spline_pts = list(reversed(spline_pts))
                pts.extend(spline_pts)
        poly = Polygon(pts) if len(pts) >= 3 else None
        area = poly.area if poly and poly.is_valid else 0.0
        if key not in seen or area > seen[key][1]:
            seen[key] = (loop, area)
    return [loop for loop, _ in seen.values()]

def _deduplicate_entities(msp, tolerance: float = 0.01) -> int:
    """
    Rimuove entità geometricamente identiche dal msp.
    Va chiamata subito dopo _explode_inserts, prima del grafo.
    Restituisce il numero di entità rimosse.
    """
    def entity_key(e):
        t = e.dxftype()
        layer = e.dxf.get("layer", "0")
        try:
            if t == "LINE":
                s = (round(e.dxf.start.x, 2), round(e.dxf.start.y, 2))
                end = (round(e.dxf.end.x, 2), round(e.dxf.end.y, 2))
                pts = tuple(sorted([s, end]))  # normalizza direzione A→B == B→A
                return (t, layer, pts)
            elif t in ("LWPOLYLINE", "POLYLINE"):
                pts = tuple((round(p[0], 2), round(p[1], 2)) for p in e.get_points())
                return (t, layer, pts)
            elif t == "CIRCLE":
                c = e.dxf.center
                return (t, layer, round(c.x, 2), round(c.y, 2), round(e.dxf.radius, 2))
            elif t == "ARC":
                c = e.dxf.center
                return (t, layer, round(c.x, 2), round(c.y, 2),
                        round(e.dxf.radius, 2),
                        round(e.dxf.start_angle, 1),
                        round(e.dxf.end_angle, 1))
        except Exception:
            return None
        return None

    seen = set()
    to_delete = []
    for entity in msp:
        key = entity_key(entity)
        if key is None:
            continue
        if key in seen:
            to_delete.append(entity)
        else:
            seen.add(key)

    for entity in to_delete:
        msp.delete_entity(entity)

    return len(to_delete)

def _filter_spurious_loops(loops):
    """
    Scarta i loop in cui almeno un'entità ha il midpoint fuori dal poligono
    formato dal loop stesso. Tipico di rettangoli con angoli raggiati dove
    il greedy chiude un loop spurio tra uno stub e un arco.

    Returns:
        (valid, spurious): due liste separate
    """

    valid, spurious = [], []

    for loop in loops:
        pts = loop_to_points(loop)
        if len(pts) < 3:
            spurious.append(loop)
            continue

        try:
            poly = Polygon(pts)
            if not poly.is_valid:
                poly = poly.buffer(0)
        except Exception:
            valid.append(loop)
            continue

        is_spurious = False
        for entity, _ in loop:
            mid = entity_midpoint(entity)
            if mid is None:
                continue
            pt = Point(mid)
            dist = poly.exterior.distance(pt)
            inside = poly.contains(pt)
            print(f"    [DEBUG] {entity.dxftype()} mid={mid} inside={inside} dist_border={dist:.4f}")

            # tolleriamo punti sul bordo (distanza < 1e-3): sono endpoint connessi
            if not poly.contains(pt) and poly.exterior.distance(pt) > 1e-3:
                is_spurious = True
                break

        (spurious if is_spurious else valid).append(loop)

    return valid, spurious

def _explode_inserts(msp) -> int:
    """
    Esplode tutti gli INSERT (blocchi) nel modelspace in entità primitive.
    Restituisce il numero di INSERT esplosi.
 
    Chiamato come primo pre-processing in heal() se explode_inserts=True.
    Le entità risultanti vengono aggiunte al msp e l'INSERT originale rimosso.
    """
    inserts = list(msp.query('INSERT'))
    if not inserts:
        return 0
 
    for insert in inserts:
        try:
            insert.explode()   # ezdxf aggiunge le entità al msp e rimuove l'INSERT
        except Exception as ex:
            print(f"  [WARN] Esplosione INSERT fallita: {ex}")
 
    return len(inserts)