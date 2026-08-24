"""
adapters/pdf/graph_adapter.py
------------------------------
Traduce entità vettoriali sanificate del PDF in Edge topologici per il core.
"""

from shapely.geometry import LineString
from ..bridge.edge import Edge
from ...core.geometry import round_point


def map_sanitized_item_to_edge(item: tuple, decimals: int, page_idx: int) -> Edge | None:
    """
    Prende un comando geometrico già sanificato e in mm, e lo mappa in un Edge del core.
    """
    cmd = item[0]
    layer = f"PDF_PAGE_{page_idx}"

    if cmd == "l":  # Linea (cmd, p1, p2)
        p1, p2 = item[1], item[2]
        s = round_point(p1, decimals)
        e = round_point(p2, decimals)
        geom = LineString([p1, p2])
        return Edge(entity=item, layer=layer, start=s, end=e, geometry=geom)

    elif cmd == "re":  # Rettangolo (cmd, [p0, p1, p2, p3])
        pts = item[1]
        pts_closed = pts + [pts[0]]
        geom = LineString(pts_closed)
        start_node = round_point(pts[0], decimals)
        return Edge(entity=item, layer=layer, start=start_node, end=start_node, geometry=geom)

    elif cmd == "qu":  # Quadrilatero (cmd, [p0, p1, p2, p3])
        pts = item[1]
        pts_closed = pts + [pts[0]]
        geom = LineString(pts_closed)
        start_node = round_point(pts[0], decimals)
        return Edge(entity=item, layer=layer, start=start_node, end=start_node, geometry=geom)

    elif cmd == "c_poly":  # Curva di Bezier già discretizzata (cmd, [p0, p1, ...])
        pts = item[1]
        s = round_point(pts[0], decimals)
        e = round_point(pts[-1], decimals)
        geom = LineString(pts)
        return Edge(entity=item, layer=layer, start=s, end=e, geometry=geom)

    return None