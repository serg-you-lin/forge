# forge/adapters/dxf/adapter.py

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from shapely.geometry import LineString

from ...core.primitives.segments import ArcSeg, DEFAULT_TOLERANCE
from ...core.adapter_base import ForgeAdapter
from .geometry_adapter import (
    arc_endpoints,
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
from ...core.primitives.segments import ArcSeg


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


def _entity_to_linestring(entity) -> LineString:
    t = entity.dxftype()

    if t == 'LINE':
        return LineString([
            (entity.dxf.start.x, entity.dxf.start.y),
            (entity.dxf.end.x,   entity.dxf.end.y),
        ])

    if t == 'ARC':
        # Usa ArcSeg.discretize() centralizzato
        arc = ArcSeg(
            center=(entity.dxf.center.x, entity.dxf.center.y),
            radius=entity.dxf.radius,
            start_angle=math.radians(entity.dxf.start_angle),
            end_angle=math.radians(entity.dxf.end_angle),
            ccw=True,
        )
        pts = arc.discretize(DEFAULT_TOLERANCE)
        return LineString(pts)

    if t == 'SPLINE':
        try:
            pts = [(p[0], p[1]) for p in entity.flattening(DEFAULT_TOLERANCE)]
            if len(pts) >= 2:
                return LineString(pts)
        except Exception:
            pass

    s, e = entity_endpoints(entity)
    if s and e:
        return LineString([s, e])
    return LineString([(0, 0), (0, 0)])


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

        for entity in self.msp:
            if _is_excluded(entity):
                continue

            dtype = entity.dxftype()
            layer = (
                entity.dxf.layer
                if entity.dxf.hasattr("layer")
                else ""
            )

            # CIRCLE → loop degenere (start == end)
            if dtype == "CIRCLE":
                poly = entity_to_polygon(entity)
                if poly is not None and not poly.is_empty:
                    coords = list(poly.exterior.coords)
                    pt = round_point(coords[0], self.node_decimals)

                    edges.append(Edge(
                        source_ref=entity,
                        layer=layer,
                        start=pt,
                        end=pt,
                        geometry=LineString(coords),
                    ))
                continue

            # SPLINE chiusa → loop degenere
            if dtype == "SPLINE" and _spline_is_closed(entity):
                poly = entity_to_polygon(entity)
                if poly is not None and not poly.is_empty:
                    coords = list(poly.exterior.coords)
                    pt = round_point(coords[0], self.node_decimals)

                    edges.append(Edge(
                        source_ref=entity,
                        layer=layer,
                        start=pt,
                        end=pt,
                        geometry=LineString(coords),
                    ))
                continue

            # LWPOLYLINE / POLYLINE → segmenti
            if dtype in ("LWPOLYLINE", "POLYLINE"):
                if _polyline_is_closed(entity):
                    poly = pline_to_polygon(entity)

                    if poly is not None and not poly.is_empty:
                        coords = list(poly.exterior.coords)

                        for i in range(len(coords) - 1):
                            s_raw = coords[i]
                            e_raw = coords[i + 1]

                            s_r = round_point(
                                s_raw, self.node_decimals
                            )
                            e_r = round_point(
                                e_raw, self.node_decimals
                            )

                            if s_r is None or e_r is None:
                                continue

                            edges.append(Edge(
                                source_ref=entity,
                                layer=layer,
                                start=s_r,
                                end=e_r,
                                geometry=LineString([
                                    s_raw,
                                    e_raw,
                                ]),
                            ))

                else:
                    pts = _polyline_points_xy(entity)

                    for i in range(len(pts) - 1):
                        s_raw = pts[i]
                        e_raw = pts[i + 1]

                        s_r = round_point(
                            s_raw, self.node_decimals
                        )
                        e_r = round_point(
                            e_raw, self.node_decimals
                        )

                        if s_r is None or e_r is None:
                            continue

                        edges.append(Edge(
                            source_ref=entity,
                            layer=layer,
                            start=s_r,
                            end=e_r,
                            geometry=LineString([
                                s_raw,
                                e_raw,
                            ]),
                        ))

                continue

            # LINE / ARC / SPLINE aperta
            if dtype not in _SUPPORTED_TYPES:
                continue

            start, end = entity_endpoints(entity)

            if start is None or end is None:
                continue

            start_r = round_point(
                start, self.node_decimals
            )
            end_r = round_point(
                end, self.node_decimals
            )

            if start_r is None or end_r is None:
                continue

            edges.append(Edge(
                source_ref=entity,
                layer=layer,
                start=start_r,
                end=end_r,
                geometry=_entity_to_linestring(entity),
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