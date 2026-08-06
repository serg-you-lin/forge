# forge/adapters/dxf/adapter.py

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from ...core.adapter_base import ForgeAdapter
from ...core.geometry import round_point
from ...core.healing.gap_solver import (
    GapEndpoint,
    MoveEndpoint,
    AddSegment,
    GapFix,
)
from ...model.edge import Edge
from ...model.role import ContourRole
from ...model.shape import ClosedShape, OpenShape
from ...core.primitives.segments import CircularArcSeg
from .graph_adapter import edges_from_msp, entity_endpoints
from .closed_adapter import entity_to_closed, contour_to_closed


# ---------------------------------------------------------------------------
# Costanti modulo — gap healing
# ---------------------------------------------------------------------------

_GAP_KIND_MAP: Dict[str, str] = {
    'LINE':   'line',
    'ARC':    'arc',
    'SPLINE': 'spline',
}


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
# Layer → role
# ---------------------------------------------------------------------------

_WORK_TYPE_TO_ROLE: Dict[str, ContourRole] = {
    "outer":         ContourRole.OUTER,
    "hole":          ContourRole.HOLE,
    "bending":       ContourRole.BEND,
    "frame":         ContourRole.FRAME,
    "inner":         ContourRole.INNER,
    "countersink":   ContourRole.COUNTERSINK,
    "threaded_hole": ContourRole.THREADED_HOLE,
    "engrave":       ContourRole.ENGRAVE,
    "marking":       ContourRole.MARKING,
}


def _layer_to_role(layer: str, label_map: Dict[str, str]) -> ContourRole:
    """
    Traduce un layer DXF in ContourRole tramite label_map.

    label_map: {layer_name: work_type}  es. {"TAGLIO": "outer", "FORI": "hole"}
    Se il layer non è mappato → UNKNOWN.
    """
    work_type = label_map.get(layer, label_map.get(layer.lower(), ""))
    return _WORK_TYPE_TO_ROLE.get(work_type.lower(), ContourRole.UNKNOWN)


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
        self.msp           = msp
        self.exclude_ids   = exclude_ids or set()
        self.ignore_layers = ignore_layers or set()
        self._label_map    = {k.lower(): v for k, v in (label_map or {}).items()}

    # ------------------------------------------------------------------
    # ForgeAdapter contract
    # ------------------------------------------------------------------

    def to_edges(self) -> List[Edge]:
        return edges_from_msp(
            self.msp,
            self.node_decimals,
            self.exclude_ids,
            self.ignore_layers,
        )

    def to_closed(self) -> List[ClosedShape]:
        shapes = []
        for entity in self.msp:
            layer = entity.dxf.layer if entity.dxf.hasattr("layer") else ""
            role  = _layer_to_role(layer, self._label_map)
            shape = entity_to_closed(entity, role=role)
            if shape is not None:
                shapes.append(shape)
        return shapes

    def to_open(self) -> List[OpenShape]:
        shapes = []
        for entity in self.msp:
            shape = self._open_entity_to_shape(entity)
            if shape is not None:
                shapes.append(shape)
        return shapes

    def source_context(self, ref: Any) -> str:
        if isinstance(ref, str):
            return ref
        try:
            return ref.dxf.layer if ref.dxf.hasattr("layer") else ""
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

    def _open_entity_to_shape(self, entity) -> Optional[OpenShape]:
        dtype = entity.dxftype()
        layer = entity.dxf.layer if entity.dxf.hasattr("layer") else ""
        role  = _layer_to_role(layer, self._label_map)

        if dtype == "LINE":
            start  = (entity.dxf.start.x, entity.dxf.start.y)
            end    = (entity.dxf.end.x,   entity.dxf.end.y)
            pts    = [start, end]
            length = entity.dxf.start.distance(entity.dxf.end)
            return OpenShape(
                pts=pts, length=length,
                source_ref=entity, role=role, shape_type="line",
            )

        if dtype == "ARC":
            cx, cy = entity.dxf.center.x, entity.dxf.center.y
            r      = entity.dxf.radius
            a0     = math.radians(entity.dxf.start_angle)
            a1     = math.radians(entity.dxf.end_angle)
            pts    = [
                (cx + r * math.cos(a0), cy + r * math.sin(a0)),
                (cx + r * math.cos(a1), cy + r * math.sin(a1)),
            ]
            span   = (a1 - a0) % (2 * math.pi)
            length = r * span
            return OpenShape(
                pts=pts, length=length,
                source_ref=entity, role=role, shape_type="arc",
                center=(cx, cy), diameter=r * 2,
            )

        return None

    def collect_closed(self, open_splines: list, virtual_shapes: list) -> list[ClosedShape]:
        open_spline_ids = {id(s) for s in open_splines}
        shapes = []

        for entity in self.msp:
            layer = entity.dxf.layer if entity.dxf.hasattr("layer") else ""
            role  = _layer_to_role(layer, self._label_map)
            shape = entity_to_closed(entity, role=role)
            if shape is None:
                continue
            if entity.dxftype() == "SPLINE" and id(entity) in open_spline_ids:
                continue
            shapes.append(shape)

        virtual = []
        for ctx in virtual_shapes:
            loop_layer = (
                ctx.loop[0][0].source_ref.dxf.layer
                if ctx.loop and ctx.loop[0][0].source_ref is not None
                else ""
            )
            role = _layer_to_role(loop_layer, self._label_map)
            virtual.append(contour_to_closed(ctx, role=role))
        return virtual + shapes

    def to_circular_arcs(self) -> List[CircularArcSeg]:
        result = []
        for entity in self.msp:
            if entity.dxftype() != "ARC":
                continue
            result.append(CircularArcSeg(
                center=(entity.dxf.center.x, entity.dxf.center.y),
                radius=entity.dxf.radius,
                start_angle=entity.dxf.start_angle,
                end_angle=entity.dxf.end_angle,
            ))
        return result

    # ------------------------------------------------------------------
    # Gap healing — ex gap_adapter.py
    # ------------------------------------------------------------------

    def extract_free_endpoints(self, graph) -> List[GapEndpoint]:
        """
        Restituisce i GapEndpoint liberi (grado < 2 nel grafo) per LINE, ARC, SPLINE.

        Parametri:
            graph : dict prodotto da build_node_graph
        """
        free: List[GapEndpoint] = []

        for entity in self.msp.query('LINE ARC SPLINE'):
            kind = _GAP_KIND_MAP.get(entity.dxftype())
            if kind is None:
                continue

            s, e = entity_endpoints(entity)
            if s is None or e is None:
                continue

            s_r  = round_point(s, self.node_decimals)
            e_r  = round_point(e, self.node_decimals)
            meta = _gap_meta_for(entity)

            if len(graph.get(s_r, [])) < 2:
                print(f"[FREE] {entity.dxftype()} start {s_r} grado {len(graph.get(s_r, []))}")
                free.append(GapEndpoint(pt=s, ref=entity, role='start', kind=kind, meta=meta))
            if len(graph.get(e_r, [])) < 2:
                print(f"[FREE] {entity.dxftype()} end {e_r} grado {len(graph.get(e_r, []))}")
                free.append(GapEndpoint(pt=e, ref=entity, role='end',   kind=kind, meta=meta))

        return free

    def apply_gap_fixes(self, fixes: List[GapFix]) -> int:
        """
        Applica i GapFix al modelspace in-place.

        Restituisce il numero di fix applicati con successo.
        """
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

            return False  # SPLINE o tipo non gestito

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