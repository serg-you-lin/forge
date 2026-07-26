# forge/adapters/dxf/adapter.py

from typing import Any, List, Optional

from ...core.adapter_base import ForgeAdapter
from ...model.edge import Edge
from ...model.shape import ClosedShape, OpenShape
from ...core.primitives.segments import CircularArcSeg
from .graph_adapter import edges_from_msp
from .closed_adapter import entity_to_closed, contour_to_closed


class DxfAdapter(ForgeAdapter):

    def __init__(
        self,
        msp,
        tolerance: float = 0.05,
        exclude_ids: Optional[set] = None,
        ignore_layers: Optional[set] = None,
    ):
        super().__init__(tolerance)
        self.msp           = msp
        self.exclude_ids   = exclude_ids or set()
        self.ignore_layers = ignore_layers or set()

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
            shape = entity_to_closed(entity)   # rinomineremo dopo
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
        """Converte LINE e ARC in OpenShape — pts e length calcolati qui."""
        dtype = entity.dxftype()
        if dtype == "LINE":
            start = (entity.dxf.start.x, entity.dxf.start.y)
            end   = (entity.dxf.end.x,   entity.dxf.end.y)
            pts    = [start, end]
            length = entity.dxf.start.distance(entity.dxf.end)
            return OpenShape(
                pts=pts, length=length,
                origin=entity.dxf.layer if entity.dxf.hasattr("layer") else "",
                source_ref=entity, shape_type="line",
            )
        if dtype == "ARC":
            import math
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
                origin=entity.dxf.layer if entity.dxf.hasattr("layer") else "",
                source_ref=entity, shape_type="arc",
                center=(cx, cy), diameter=r * 2,
            )
        return None

    def collect_closed(self, open_splines: list, virtual_shapes: list) -> list[ClosedShape]:
        """
        Raccoglie tutte le ClosedShape: entità chiuse da msp + virtual dal core.
        Esclude le spline aperte (già finite in to_open via il chiamante).
        """

        open_spline_ids = {id(s) for s in open_splines}
        shapes = []
        for entity in self.msp:
            shape = entity_to_closed(entity)
            if shape is None:
                continue
            if entity.dxftype() == "SPLINE" and id(entity) in open_spline_ids:
                continue
            shapes.append(shape)

        virtual = [contour_to_closed(ctx) for ctx in virtual_shapes]
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