

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


# ---------------------------------------------------------------------------
# Costanti
# ---------------------------------------------------------------------------

_SUPPORTED_TYPES = frozenset({'LINE', 'ARC', 'SPLINE'})


# ---------------------------------------------------------------------------
# TRADUZIONE DXF → PRIMITIVE (UNICO PUNTO)
# ---------------------------------------------------------------------------

def entity_to_primitive(entity, rev: bool = False):
    """
    Traduce un'entità DXF in una primitiva Forge.
    
    IMPORTANTE: 
    - CIRCLE → CircleSeg (NON 2 ArcSeg!)
    - SPLINE → SplineSeg
    - LINE → LineSeg
    - ARC → ArcSeg
    - LWPOLYLINE/POLYLINE → List[LineSeg | ArcSeg]
    
    Questa è l'UNICA sede di questa traduzione.
    """
    t = entity.dxftype()
    
    if t == 'LINE':
        if rev:
            return LineSeg(
                start=(entity.dxf.end.x, entity.dxf.end.y),
                end=(entity.dxf.start.x, entity.dxf.start.y),
            )
        return LineSeg(
            start=(entity.dxf.start.x, entity.dxf.start.y),
            end=(entity.dxf.end.x, entity.dxf.end.y),
        )
    
    elif t == 'ARC':
        sa = math.radians(entity.dxf.start_angle)
        ea = math.radians(entity.dxf.end_angle)
        ccw = True
        if rev:
            sa, ea = ea, sa
            ccw = False
        return ArcSeg(
            center=(entity.dxf.center.x, entity.dxf.center.y),
            radius=entity.dxf.radius,
            start_angle=sa,
            end_angle=ea,
            ccw=ccw,
        )
    
    elif t == 'CIRCLE':
        # CERCHIO → CircleSeg (preservato!)
        return CircleSeg(
            center=(entity.dxf.center.x, entity.dxf.center.y),
            radius=entity.dxf.radius
        )
    
    elif t == 'SPLINE':
        return _spline_to_primitive(entity, rev)
    
    elif t in ('LWPOLYLINE', 'POLYLINE'):
        return _polyline_to_primitives(entity, rev)
    
    return None


def _spline_to_primitive(entity, rev: bool = False) -> Optional[SplineSeg]:
    """Traduce SPLINE in SplineSeg."""
    try:
        cps = [_vec3_to_tuple(p) for p in entity.control_points]
        approx_points = [(float(p[0]), float(p[1])) for p in entity.flattening(DEFAULT_TOLERANCE)]
        knots = [float(k) for k in entity.knots]
        weights = [float(w) for w in entity.weights] if len(entity.weights) else None
        fit_points = [_vec3_to_tuple(p) for p in entity.fit_points] if len(entity.fit_points) else None
        flags = int(getattr(entity.dxf, "flags", 0) or 0)
        periodic = bool(flags & 2)
        closed = bool(getattr(entity, "closed", False) or (flags & 1))

        start_tangent = None
        if entity.dxf.hasattr("start_tangent"):
            st = entity.dxf.start_tangent
            start_tangent = (float(st.x), float(st.y), float(st.z))

        end_tangent = None
        if entity.dxf.hasattr("end_tangent"):
            et = entity.dxf.end_tangent
            end_tangent = (float(et.x), float(et.y), float(et.z))
    except Exception:
        cps = []
        approx_points = []
        knots = []
        weights = None
        fit_points = None
        flags = 0
        periodic = False
        closed = False
        start_tangent = None
        end_tangent = None
    
    if rev:
        cps = list(reversed(cps))
        if approx_points:
            approx_points = list(reversed(approx_points))
        if fit_points:
            fit_points = list(reversed(fit_points))
    
    if not cps and not fit_points:
        return None
    
    return SplineSeg(
        degree=int(getattr(entity.dxf, "degree", 3) or 3),
        control_points=[(p[0], p[1]) for p in cps],
        knots=knots,
        weights=weights,
        approx_points=approx_points or None,
        fit_points=fit_points,
        closed=closed,
        periodic=periodic,
        flags=flags,
        knot_tolerance=float(entity.dxf.knot_tolerance) if entity.dxf.hasattr("knot_tolerance") else None,
        fit_tolerance=float(entity.dxf.fit_tolerance) if entity.dxf.hasattr("fit_tolerance") else None,
        control_point_tolerance=float(entity.dxf.control_point_tolerance) if entity.dxf.hasattr("control_point_tolerance") else None,
        start_tangent=start_tangent,
        end_tangent=end_tangent,
    )


def _polyline_to_primitives(entity, rev: bool = False) -> List[Segment]:
    """Traduce LWPOLYLINE/POLYLINE in List[LineSeg | ArcSeg]."""
    if entity.dxftype() == 'POLYLINE':
        pts = [(v.dxf.location.x, v.dxf.location.y, getattr(v.dxf, "bulge", 0.0)) 
               for v in entity.vertices]
    else:
        pts = list(entity.get_points('xyb'))
    
    if not pts:
        return []
    
    is_closed = bool(getattr(entity, "is_closed", False) or getattr(entity, "closed", False))

    if is_closed and len(pts) > 1:
        first_xy = (pts[0][0], pts[0][1])
        last_xy = (pts[-1][0], pts[-1][1])
        if first_xy == last_xy:
            pts = pts[:-1]

    if rev:
        n = len(pts)
        new_pts = []
        for i in range(n):
            idx = (-i) % n
            x, y, _ = pts[idx]
            if is_closed:
                prev_idx = (idx - 1) % n
                bulge = -pts[prev_idx][2]
            else:
                prev_idx = idx - 1
                bulge = -pts[prev_idx][2] if prev_idx >= 0 else 0.0
            new_pts.append((x, y, bulge))
        pts = new_pts
    
    primitives = []
    n = len(pts)
    edge_count = n if is_closed else max(0, n - 1)
    for i in range(edge_count):
        x1, y1, bulge = pts[i]
        if is_closed:
            x2, y2, _ = pts[(i + 1) % n]
        else:
            x2, y2, _ = pts[i + 1]
        
        if abs(bulge) > 1e-6:
            arc = _bulge_to_arc((x1, y1), (x2, y2), bulge)
            if arc:
                primitives.append(arc)
        else:
            primitives.append(LineSeg(start=(x1, y1), end=(x2, y2)))
    
    return primitives


def _bulge_to_arc(p1: Tuple[float, float], p2: Tuple[float, float], bulge: float) -> Optional[ArcSeg]:
    """Converte bulge DXF in ArcSeg."""
    x1, y1 = p1
    x2, y2 = p2
    
    included_angle = 4 * math.atan(abs(bulge))
    if included_angle < 1e-12:
        return None
    
    chord = math.hypot(x2 - x1, y2 - y1)
    if chord < 1e-12:
        return None
    
    radius = chord / (2 * math.sin(included_angle / 2))
    
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    dx, dy = x2 - x1, y2 - y1
    px, py = -dy / chord, dx / chord
    dist = radius * math.cos(included_angle / 2)
    
    if bulge > 0:
        cx, cy = mx + px * dist, my + py * dist
        ccw = True
    else:
        cx, cy = mx - px * dist, my - py * dist
        ccw = False
    
    start_angle = math.atan2(y1 - cy, x1 - cx)
    end_angle = math.atan2(y2 - cy, x2 - cx)
    
    if ccw:
        while end_angle <= start_angle:
            end_angle += 2 * math.pi
    else:
        while end_angle >= start_angle:
            end_angle -= 2 * math.pi
    
    return ArcSeg(
        center=(cx, cy),
        radius=radius,
        start_angle=start_angle,
        end_angle=end_angle,
        ccw=ccw,
    )


def _vec3_to_tuple(point) -> Tuple[float, float, float]:
    return (float(point[0]), float(point[1]), float(point[2] if len(point) > 2 else 0.0))


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
            if not ignore:
                return False
            layer = (
                entity.dxf.layer.lower()
                if entity.dxf.hasattr("layer")
                else ""
            )
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
                prim = entity_to_primitive(entity)
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
                prim = entity_to_primitive(entity)
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
                primitives = entity_to_primitive(entity) or []
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

            prim = entity_to_primitive(entity)
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

