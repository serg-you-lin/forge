# forge/adapters/dxf/adapter.py

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from ...core.primitives.segments import ArcSeg, DEFAULT_TOLERANCE
from ...core.adapter_base import ForgeAdapter
from .geometry_adapter import (
    arc_endpoints,
    entity_to_primitive,
    entity_to_polygon,
    pline_to_polygon,
    _spline_is_closed,
)
from ...core.geometry import round_point
from ...core.healing.gap_solver import (
    GapEndpoint,
    MoveEndpoint,
    AddSegment,
    GapFix,
)
from ..bridge.edge import Edge
from ...core.primitives.segments import ArcSeg, LineSeg, SplineSeg, CircleSeg, DEFAULT_TOLERANCE
from ..bridge.edge import Segment


# ---------------------------------------------------------------------------
# Costanti — tipi DXF supportati per la topologia
# ---------------------------------------------------------------------------

_SUPPORTED_TYPES = frozenset({'LINE', 'ARC', 'SPLINE'})

_GAP_KIND_MAP: Dict[str, str] = {
    'LINE':   'line',
    'ARC':    'arc',
    'SPLINE': 'spline',
}


# ---------------------------------------------------------------------------
# Layer → role
# ---------------------------------------------------------------------------
# La mappatura vive in model/role.py (pura, zero dipendenze DXF).
# Riesportata qui solo per backward compatibility di eventuali import esterni.
from ...model.role import WORK_TYPE_TO_ROLE as _WORK_TYPE_TO_ROLE
from ...model.role import layer_to_role as _layer_to_role


# ---------------------------------------------------------------------------
# Gap healing — metadati per entità
# ---------------------------------------------------------------------------

def _gap_meta_for(entity) -> dict:
    t = entity.dxftype()
    if t == 'LINE':
        return {
            'start': (entity.dxf.start.x, entity.dxf.start.y),
            'end':   (entity.dxf.end.x,   entity.dxf.end.y),
        }
    if t == 'ARC':
        return {
            'cx':     entity.dxf.center.x,
            'cy':     entity.dxf.center.y,
            'radius': entity.dxf.radius,
        }
    return {}


# ---------------------------------------------------------------------------
# Geometria DXF → Edge
# ---------------------------------------------------------------------------

def _spline_endpoints(spline):
    try:
        pts = list(spline.flattening(0.01))
        if len(pts) < 2:
            return None, None
        return (pts[0][0], pts[0][1]), (pts[-1][0], pts[-1][1])
    except Exception:
        return None, None


def _entity_to_segment(entity) -> Segment:
    t = entity.dxftype()

    if t == 'LINE':
        return LineSeg(
            start=(entity.dxf.start.x, entity.dxf.start.y),
            end=(entity.dxf.end.x,     entity.dxf.end.y),
        )

    if t == 'ARC':
        return ArcSeg(
            center=(entity.dxf.center.x, entity.dxf.center.y),
            radius=entity.dxf.radius,
            start_angle=math.radians(entity.dxf.start_angle),
            end_angle=math.radians(entity.dxf.end_angle),
            ccw=True,
        )

    if t == 'SPLINE':
        try:
            pts = [(p[0], p[1]) for p in entity.flattening(DEFAULT_TOLERANCE)]
            if len(pts) >= 2:
                return SplineSeg(
                    degree=entity.dxf.degree,
                    control_points=pts,
                    knots=[],
                )
        except Exception:
            pass

    # fallback
    s, e = entity_endpoints(entity)
    if s and e:
        return LineSeg(start=s, end=e)
    return LineSeg(start=(0, 0), end=(0, 0))


def _segment_endpoints(segment: Segment) -> tuple[tuple[float, float], tuple[float, float]]:
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
        if not segment.control_points:
            return (0.0, 0.0), (0.0, 0.0)
        return segment.control_points[0], segment.control_points[-1]
    if isinstance(segment, CircleSeg):
        pt = (segment.center[0] + segment.radius, segment.center[1])
        return pt, pt
    return (0.0, 0.0), (0.0, 0.0)


def _segment_key(segment: Segment) -> tuple:
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
        return ("SPLINE", tuple((round(x, 6), round(y, 6)) for x, y in segment.control_points))
    if isinstance(segment, CircleSeg):
        return ("CIRCLE", round(segment.center[0], 6), round(segment.center[1], 6), round(segment.radius, 6))
    return (type(segment).__name__, repr(segment))


def entity_endpoints(entity):
    t = entity.dxftype()
    if t == 'LINE':
        return (
            (entity.dxf.start.x, entity.dxf.start.y),
            (entity.dxf.end.x,   entity.dxf.end.y),
        )
    if t == 'ARC':
        return arc_endpoints(entity)
    if t == 'SPLINE':
        return _spline_endpoints(entity)
    return None, None


def _polyline_is_closed(entity) -> bool:
    if hasattr(entity, "is_closed"):
        try:
            return bool(entity.is_closed)
        except Exception:
            pass
    return bool(getattr(entity, "closed", False))


def _polyline_points_xy(entity) -> list[tuple[float, float]]:
    if entity.dxftype() == 'POLYLINE':
        return [(v.dxf.location.x, v.dxf.location.y) for v in entity.vertices]
    try:
        return [(p[0], p[1]) for p in entity.get_points('xy')]
    except Exception:
        return [(p[0], p[1]) for p in entity.get_points()]


# ---------------------------------------------------------------------------
# DxfAdapter
# ---------------------------------------------------------------------------

class DxfAdapter(ForgeAdapter):

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

        def _append_edge(source_ref, role, segment):
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
                source_ref=source_ref,
                role=role,
                start=start_r,
                end=end_r,
                segment=segment,
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
            role = _layer_to_role(layer, self._label_map)

            # CIRCLE → loop degenere (start == end)
            if dtype == "CIRCLE":
                cx, cy = entity.dxf.center.x, entity.dxf.center.y
                pt = round_point((cx, cy), self.node_decimals)
                edges.append(Edge(
                    source_ref=entity,
                    role=role,
                    start=pt,
                    end=pt,
                    segment=CircleSeg(
                        center=(cx, cy),
                        radius=entity.dxf.radius,
                    ),
                ))
                continue

            # SPLINE chiusa → loop degenere
            if dtype == "SPLINE" and _spline_is_closed(entity):
                try:
                    pts = [(p[0], p[1]) for p in entity.flattening(DEFAULT_TOLERANCE)]
                    if len(pts) >= 2:
                        pt = round_point(pts[0], self.node_decimals)
                        edges.append(Edge(
                            source_ref=entity,
                            role=role,
                            start=pt,
                            end=pt,
                            segment=SplineSeg(
                                degree=entity.dxf.degree,
                                control_points=pts,
                                knots=[],
                            ),
                        ))
                except Exception:
                    pass
                continue

            # LWPOLYLINE / POLYLINE → segmenti
            if dtype in ("LWPOLYLINE", "POLYLINE"):
                primitives = entity_to_primitive(entity) or []
                if not isinstance(primitives, list):
                    primitives = [primitives]
                for segment in primitives:
                    _append_edge(entity, role, segment)
                continue

            # LINE / ARC / SPLINE aperta
            if dtype not in _SUPPORTED_TYPES:
                continue

            start, end = entity_endpoints(entity)
            if start is None or end is None:
                continue

            start_r = round_point(start, self.node_decimals)
            end_r   = round_point(end,   self.node_decimals)
            if start_r is None or end_r is None:
                continue

            edges.append(Edge(
                source_ref=entity,
                role=role,
                start=start_r,
                end=end_r,
                segment=_entity_to_segment(entity),
            ))

        return edges

    
    def source_context(self, ref: Any) -> str:
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

    # ------------------------------------------------------------------
    # Metodi specifici DXF
    # ------------------------------------------------------------------

    def load_entity_lists(self) -> dict:
        return {
            "lines":   list(self.msp.query("LINE")),
            "arcs":    list(self.msp.query("ARC")),
            "plines":  list(self.msp.query("LWPOLYLINE POLYLINE")),
            "circles": list(self.msp.query("CIRCLE")),
            "splines": list(self.msp.query("SPLINE")),
        }

    def to_circular_arcs(self) -> List[ArcSeg]:
        result = []
        for entity in self.msp:
            if entity.dxftype() != "ARC":
                continue
            result.append(ArcSeg(
                center=(entity.dxf.center.x, entity.dxf.center.y),
                radius=entity.dxf.radius,
                start_angle=math.radians(entity.dxf.start_angle),
                end_angle=math.radians(entity.dxf.end_angle),
                ccw=True,
            ))
        return result

    # ------------------------------------------------------------------
    # Gap healing
    # ------------------------------------------------------------------

    def extract_free_endpoints(self, graph) -> List[GapEndpoint]:
        free: List[GapEndpoint] = []

        for entity in self.msp.query('LINE ARC SPLINE'):
            kind = _GAP_KIND_MAP.get(entity.dxftype())
            if kind is None:
                continue

            s, e = entity_endpoints(entity)
            if s is None or e is None:
                continue

            s_r = round_point(s, self.node_decimals)
            e_r = round_point(e, self.node_decimals)
            meta = _gap_meta_for(entity)

            if len(graph.get(s_r, [])) < 2:
                free.append(GapEndpoint(pt=s, ref=entity, role='start', kind=kind, meta=meta))
            if len(graph.get(e_r, [])) < 2:
                free.append(GapEndpoint(pt=e, ref=entity, role='end', kind=kind, meta=meta))

        return free

    def apply_gap_fixes(self, fixes: List[GapFix]) -> int:
        def _apply_move(fix: MoveEndpoint) -> bool:
            entity = fix.ref
            t      = entity.dxftype()
            pt     = fix.new_pt

            if t == 'LINE':
                if fix.role == 'start':
                    entity.dxf.start = (pt[0], pt[1], entity.dxf.start.z)
                else:
                    entity.dxf.end   = (pt[0], pt[1], entity.dxf.end.z)
                return True

            if t == 'ARC':
                cx    = entity.dxf.center.x
                cy    = entity.dxf.center.y
                angle = math.degrees(math.atan2(pt[1] - cy, pt[0] - cx)) % 360
                if fix.role == 'start':
                    entity.dxf.start_angle = angle
                else:
                    entity.dxf.end_angle   = angle
                return True

            return False

        def _apply_add_segment(fix: AddSegment) -> bool:
            self.msp.add_line(
                (fix.pt_a[0], fix.pt_a[1], 0.0),
                (fix.pt_b[0], fix.pt_b[1], 0.0),
            )
            return True

        _handlers = {
            MoveEndpoint: _apply_move,
            AddSegment:   _apply_add_segment,
        }

        applied = 0
        for fix in fixes:
            handler = _handlers.get(type(fix))
            if handler and handler(fix):
                applied += 1
        return applied