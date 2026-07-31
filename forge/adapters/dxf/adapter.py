# forge/adapters/dxf/adapter.py

import math
from typing import Any, Dict, List, Optional

from ...core.adapter_base import ForgeAdapter
from ...model.edge import Edge
from ...model.role import ContourRole
from ...model.shape import ClosedShape, OpenShape
from ...core.primitives.segments import CircularArcSeg
from .graph_adapter import edges_from_msp
from .closed_adapter import entity_to_closed, contour_to_closed

# Mappa work_type stringa → ContourRole
# Unica fonte di verità per la traduzione label_map → role in ambito DXF.
_WORK_TYPE_TO_ROLE: Dict[str, ContourRole] = {
    "outer":        ContourRole.OUTER,
    "hole":         ContourRole.HOLE,
    "bending":      ContourRole.BEND,   # alias comune nei file DXF
    "frame":        ContourRole.FRAME,
    "inner":        ContourRole.INNER,
    "countersink":   ContourRole.COUNTERSINK,    
    "threaded_hole": ContourRole.THREADED_HOLE,    
    "engrave": ContourRole.ENGRAVE,
    "marking": ContourRole.MARKING,
}


def _layer_to_role(layer: str, label_map: Dict[str, str]) -> ContourRole:
    """
    Traduce un layer DXF in ContourRole tramite label_map.

    label_map: {layer_name: work_type}  es. {"TAGLIO": "outer", "FORI": "hole"}
    Se il layer non è mappato → UNKNOWN.
    """
    work_type = label_map.get(layer, label_map.get(layer.lower(), ""))
    return _WORK_TYPE_TO_ROLE.get(work_type.lower(), ContourRole.UNKNOWN)


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
        # label_map è configurazione dell'adapter — non esce mai verso il core
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
        """
        Converte LINE e ARC in OpenShape.

        Il role viene tradotto da label_map qui — detect.py non toccherà
        mai origin né farà lookup sul layer.
        """
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
        """
        Raccoglie tutte le ClosedShape: entità chiuse da msp + virtual dal core.

        Ogni shape esce già con role tradotto da label_map — il core non
        vedrà mai layer DXF.
        """

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

        # virtual = [contour_to_closed(ctx) for ctx in virtual_shapes]
        virtual = []
        for ctx in virtual_shapes:
            loop_layer = ctx.loop[0][0].source_ref.dxf.layer if ctx.loop and ctx.loop[0][0].source_ref is not None else ""
            role = _layer_to_role(loop_layer, self._label_map)
            virtual.append(contour_to_closed(ctx, role=role))
        return virtual + shapes

    def to_circular_arcs(self) -> list[CircularArcSeg]:
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