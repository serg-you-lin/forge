
from shapely.geometry import Polygon, Point
from ..adapters.dxf.geometry_adapter import arc_to_bulge, entity_midpoint, spline_to_points
from ..core.topology.loops import loop_to_points


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
                pts = tuple(sorted([s, end]))
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


# def _explode_inserts(msp) -> int:
#     """
#     Esplode tutti gli INSERT (blocchi) nel modelspace in entità primitive.
#     Restituisce il numero di INSERT esplosi.
#     """
#     inserts = list(msp.query('INSERT'))
#     if not inserts:
#         return 0

#     for insert in inserts:
#         try:
#             insert.explode()
#         except Exception as ex:
#             print(f"  [WARN] Esplosione INSERT fallita: {ex}")

#     return len(inserts)