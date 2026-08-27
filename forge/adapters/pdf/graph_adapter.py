"""
adapters/pdf/graph_adapter.py
------------------------------
Traduce entità vettoriali sanificate del PDF in Edge topologici per il core.
"""

from ..bridge.edge import Edge
from ...core.geometry import round_point
from ...core.primitives.segments import LineSeg, SplineSeg
from ...model.role import ContourRole


def map_sanitized_item_to_edge(item: tuple, decimals: int, page_idx: int) -> Edge | None:
    cmd = item[0]

    if cmd == "l":
        p1, p2 = item[1], item[2]
        s = round_point(p1, decimals)
        e = round_point(p2, decimals)
        return Edge(
            role=ContourRole.UNKNOWN,
            start=s,
            end=e,
            segment=LineSeg(start=p1, end=p2),
        )

    elif cmd in ("re", "qu"):
        pts = item[1]
        pt = round_point(pts[0], decimals)
        # poligono chiuso → segmenti separati
        edges = []
        for i in range(len(pts)):
            s = pts[i]
            e = pts[(i + 1) % len(pts)]
            s_r = round_point(s, decimals)
            e_r = round_point(e, decimals)
            edges.append(Edge(
                role=ContourRole.UNKNOWN,
                start=s_r,
                end=e_r,
                segment=LineSeg(start=s, end=e),
            ))
        return edges

    elif cmd == "c_poly":
        pts = item[1]
        s = round_point(pts[0], decimals)
        e = round_point(pts[-1], decimals)
        return Edge(
            role=ContourRole.UNKNOWN,
            start=s,
            end=e,
            segment=SplineSeg(degree=3, control_points=pts, knots=[]),
        )

    return None