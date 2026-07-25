

# forge/adapters/dxf/adapter.py

from typing import Any, List, Optional

from ...core.adapter_base import ForgeAdapter
from ...model.edge import Edge
from ...model.shape_proxy import ShapeProxy
from ...core.primitives.segments import CircularArcSeg
from .graph_adapter import edges_from_msp
from .proxy_adapter import entity_to_proxy


class DxfAdapter(ForgeAdapter):
    """
    Adapter DXF → core.
    Unico punto del progetto che conosce ezdxf e produce tipi core.
    """

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

    def to_proxies(self) -> List[ShapeProxy]:
        proxies = []
        for entity in self.msp:
            proxy = entity_to_proxy(entity)
            if proxy is not None:
                proxies.append(proxy)
        return proxies

    def source_context(self, ref: Any) -> str:
        if isinstance(ref, str):
            return ref
        try:
            return ref.dxf.layer if ref.dxf.hasattr("layer") else ""
        except AttributeError:
            return ""
        
    def load_entity_lists(self) -> dict:
        return {
            "lines":   list(self.msp.query("LINE")),
            "arcs":    list(self.msp.query("ARC")),
            "plines":  list(self.msp.query("LWPOLYLINE POLYLINE")),
            "circles": list(self.msp.query("CIRCLE")),
            "splines": list(self.msp.query("SPLINE")),
        }
    
    def _open_entity_to_proxy(self, entity) -> Optional[ShapeProxy]:
        """Proxy minimale per entità aperte (LINE, ARC) — polygon=None."""
        dtype = entity.dxftype()
        if dtype not in ("LINE", "ARC"):
            return None
        return ShapeProxy(
            polygon=None,
            origin=entity.dxf.layer if entity.dxf.hasattr("layer") else "",
            source_ref=entity,
            shape_type=dtype.lower(),   # "line" | "arc"
        )
    # def collect_proxies(self, open_splines: list, virtual_shapes: list) -> list[ShapeProxy]:
    #     from .proxy_adapter import entity_to_proxy, contour_to_proxy
    #     from .geometry_adapter import _spline_is_closed

    #     open_spline_ids = {id(s) for s in open_splines}
    #     proxies = []
    #     for entity in self.msp:
    #         proxy = entity_to_proxy(entity)
    #         if proxy is None:
    #             continue
    #         entity_type = entity.dxftype()
    #         if entity_type == "SPLINE" and id(entity) in open_spline_ids:
    #             continue
    #         proxies.append(proxy)

    #     virtual = [contour_to_proxy(ctx) for ctx in virtual_shapes]
    #     return virtual + proxies

    def collect_proxies(self, open_splines: list, virtual_shapes: list) -> list[ShapeProxy]:
        from .proxy_adapter import entity_to_proxy, contour_to_proxy

        open_spline_ids = {id(s) for s in open_splines}
        proxies = []
        for entity in self.msp:
            proxy = entity_to_proxy(entity)
            if proxy is not None:
                # entità chiusa riconosciuta
                if entity.dxftype() == "SPLINE" and id(entity) in open_spline_ids:
                    continue
                proxies.append(proxy)
            else:
                # entità aperta — proxy minimale per _build_trash
                open_proxy = self._open_entity_to_proxy(entity)
                if open_proxy is not None:
                    proxies.append(open_proxy)

        virtual = [contour_to_proxy(ctx) for ctx in virtual_shapes]
        return virtual + proxies
    

    def to_circular_arcs(self) -> list[CircularArcSeg]:
        from ...core.primitives.segments import CircularArcSeg
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