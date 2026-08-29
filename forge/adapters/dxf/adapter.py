

"""
forge/adapters/dxf/adapter.py
--------------------------------
Traduce entità DXF in primitive Forge.
UNICO punto di conversione DXF → primitive.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from ...core.primitives.segments import LineSeg, ArcSeg, SplineSeg, CircleSeg, DEFAULT_TOLERANCE
from ...core.adapter_base import ForgeAdapter
from ...core.geometry import round_point
from ..bridge.edge import Edge, Segment
from ...model.role import WORK_TYPE_TO_ROLE, layer_to_role

from .geometry_adapter import (
    entity_endpoints,
    get_representative_point,
    entity_to_polygon,
    spline_is_closed,
)
from .parser import DxfEntityDispatcher


# ---------------------------------------------------------------------------
# Costanti
# ---------------------------------------------------------------------------

_SUPPORTED_TYPES = frozenset({'LINE', 'ARC', 'SPLINE'})

# Layer che forge produce in output per contenuti NON di taglio: se un file già
# passato da forge viene riletto (round-trip, ri-heal), la loro geometria non è
# geometria di parte e va sempre ignorata, senza doverlo chiedere al chiamante.
_NON_STRUCTURAL_LAYERS = frozenset({'trash', 'annotation'})


# ---------------------------------------------------------------------------
# TRADUZIONE DXF → PRIMITIVE
# ---------------------------------------------------------------------------
# La traduzione entità DXF → primitiva vive in UN SOLO posto:
# `adapters/dxf/parser.py::DxfEntityDispatcher` (MAP.md D7). Prima ce n'erano
# due copie quasi identiche — una qui (`entity_to_primitive`), una in parser.py.


def _segment_endpoints(segment: Segment) -> Tuple[Tuple[float, float], Tuple[float, float]]:
    """Endpoint di un segmento Forge."""
    if isinstance(segment, LineSeg):
        return segment.start, segment.end
    if isinstance(segment, ArcSeg):
        start = (
            segment.center[0] + segment.radius * math.cos(segment.start_angle),
            segment.center[1] + segment.radius * math.sin(segment.start_angle),
        )
        end = (
            segment.center[0] + segment.radius * math.cos(segment.end_angle),
            segment.center[1] + segment.radius * math.sin(segment.end_angle),
        )
        return start, end
    if isinstance(segment, SplineSeg):
        if segment.fit_points:
            start = segment.fit_points[0]
            end = segment.fit_points[-1]
            return (start[0], start[1]), (end[0], end[1])
        if not segment.control_points:
            return (0.0, 0.0), (0.0, 0.0)
        return segment.control_points[0], segment.control_points[-1]
    if isinstance(segment, CircleSeg):
        pt = (segment.center[0] + segment.radius, segment.center[1])
        return pt, pt
    return (0.0, 0.0), (0.0, 0.0)


def _segment_key(segment: Segment) -> tuple:
    """Chiave univoca per deduplicazione."""
    if isinstance(segment, LineSeg):
        pts = tuple(sorted((
            (round(segment.start[0], 6), round(segment.start[1], 6)),
            (round(segment.end[0], 6), round(segment.end[1], 6)),
        )))
        return ("LINE", pts)
    if isinstance(segment, ArcSeg):
        return (
            "ARC",
            round(segment.center[0], 6),
            round(segment.center[1], 6),
            round(segment.radius, 6),
            round(segment.start_angle, 6),
            round(segment.end_angle, 6),
            segment.ccw,
        )
    if isinstance(segment, SplineSeg):
        return (
            "SPLINE",
            int(segment.degree),
            tuple((round(x, 6), round(y, 6)) for x, y in segment.control_points),
            tuple(round(k, 9) for k in segment.knots),
            tuple(round(w, 9) for w in (segment.weights or [])),
            bool(segment.closed),
            bool(segment.periodic),
            int(segment.flags),
        )
    if isinstance(segment, CircleSeg):
        return (
            "CIRCLE",
            round(segment.center[0], 6),
            round(segment.center[1], 6),
            round(segment.radius, 6)
        )
    return (type(segment).__name__, repr(segment))


# ---------------------------------------------------------------------------
# DxfAdapter
# ---------------------------------------------------------------------------

class DxfAdapter(ForgeAdapter):
    """
    Adapter DXF che traduce entità DXF in Edge del dominio Forge.
    """

    def __init__(
        self,
        msp,
        tolerance: float = 0.05,
        exclude_ids: Optional[set] = None,
        ignore_layers: Optional[set] = None,
        label_map: Optional[Dict[str, str]] = None,
    ):
        super().__init__(tolerance)
        self.msp = msp
        self.exclude_ids = exclude_ids or set()
        self.ignore_layers = ignore_layers or set()
        self._label_map = {
            k.lower(): v
            for k, v in (label_map or {}).items()
        }

    # ------------------------------------------------------------------
    # ForgeAdapter contract
    # ------------------------------------------------------------------

    def to_edges(self) -> List[Edge]:
        """Traduce entità DXF in Edge."""
        ignore = {s.lower() for s in self.ignore_layers}

        def _is_excluded(entity) -> bool:
            if id(entity) in self.exclude_ids:
                return True
            layer = (
                entity.dxf.layer.lower()
                if entity.dxf.hasattr("layer")
                else ""
            )
            if layer in _NON_STRUCTURAL_LAYERS:
                return True
            if not ignore:
                return False
            return any(sl in layer for sl in ignore)

        edges = []
        seen_segment_keys = set()

        def _append_edge(role, segment, closed_path=False):
            key = _segment_key(segment)
            if key in seen_segment_keys:
                return
            seen_segment_keys.add(key)
            start, end = _segment_endpoints(segment)
            start_r = round_point(start, self.node_decimals)
            end_r = round_point(end, self.node_decimals)
            if start_r is None or end_r is None:
                return
            edges.append(Edge(
                role=role,
                start=start_r,
                end=end_r,
                segment=segment,
                closed_path=closed_path,
            ))

        for entity in self.msp:
            if _is_excluded(entity):
                continue

            dtype = entity.dxftype()
            layer = (
                entity.dxf.layer
                if entity.dxf.hasattr("layer")
                else ""
            )
            role = layer_to_role(layer, self._label_map)

            # CIRCLE → CircleSeg (preservato!)
            if dtype == "CIRCLE":
                prim = DxfEntityDispatcher(entity).parse()
                if isinstance(prim, CircleSeg):
                    start, end = _segment_endpoints(prim)
                    pt = round_point(start, self.node_decimals)
                    if pt is not None:
                        edges.append(Edge(
                            role=role,
                            start=pt,
                            end=pt,
                            segment=prim,
                        ))
                continue

            # SPLINE chiusa → loop degenere
            if dtype == "SPLINE" and spline_is_closed(entity):
                prim = DxfEntityDispatcher(entity).parse()
                if isinstance(prim, SplineSeg):
                    start, _ = _segment_endpoints(prim)
                    pt = round_point(start, self.node_decimals)
                    if pt is not None:
                        edges.append(Edge(
                            role=role,
                            start=pt,
                            end=pt,
                            segment=prim,
                        ))
                continue

            # LWPOLYLINE / POLYLINE → segmenti
            if dtype in ("LWPOLYLINE", "POLYLINE"):
                primitives = DxfEntityDispatcher(entity).parse() or []
                if not isinstance(primitives, list):
                    primitives = [primitives]
                poly_closed = bool(
                    getattr(entity, "is_closed", False)
                    or getattr(entity, "closed", False)
                )
                for segment in primitives:
                    _append_edge(role, segment, closed_path=poly_closed)
                continue

            # LINE / ARC / SPLINE aperta
            if dtype not in _SUPPORTED_TYPES:
                continue

            start, end = entity_endpoints(entity)
            if start is None or end is None:
                continue

            prim = DxfEntityDispatcher(entity).parse()
            if prim is None:
                continue

            start_r = round_point(start, self.node_decimals)
            end_r = round_point(end, self.node_decimals)
            if start_r is None or end_r is None:
                continue

            edges.append(Edge(
                role=role,
                start=start_r,
                end=end_r,
                segment=prim,
            ))

        return edges

    def source_context(self, ref: Any) -> str:
        """Layer dell'entità sorgente."""
        if isinstance(ref, str):
            return ref
        try:
            return (
                ref.dxf.layer
                if ref.dxf.hasattr("layer")
                else ""
            )
        except AttributeError:
            return ""

