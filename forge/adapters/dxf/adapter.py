# # adapters/dxf/adapter.py

# from typing import Any, List, Optional

# from ...core.adapter_base import ForgeAdapter
# from ...model.edge import Edge
# from ...model.shape_proxy import ShapeProxy
# from .graph_adapter import edges_from_msp
# from .proxy_adapter import entity_to_proxy, contour_to_proxy


# class DxfAdapter(ForgeAdapter):
#     """
#     Adapter DXF → core.
#     Unico punto del progetto che conosce ezdxf e produce tipi core.
#     """

#     def __init__(
#         self,
#         msp,
#         node_decimals: int,
#         exclude_ids: Optional[set] = None,
#         ignore_layers: Optional[set] = None,
#     ):
#         self.msp           = msp
#         self.node_decimals = node_decimals
#         self.exclude_ids   = exclude_ids or set()
#         self.ignore_layers = ignore_layers or set()

#     # ------------------------------------------------------------------
#     # ForgeAdapter contract
#     # ------------------------------------------------------------------

#     def to_edges(self) -> List[Edge]:
#         return edges_from_msp(
#             self.msp,
#             self.node_decimals,
#             self.exclude_ids,
#             self.ignore_layers,
#         )

#     def to_proxies(self) -> List[ShapeProxy]:
#         proxies = []
#         for entity in self.msp:
#             proxy = entity_to_proxy(entity)
#             if proxy is not None:
#                 proxies.append(proxy)
#         return proxies

#     def source_context(self, ref: Any) -> str:
#         if isinstance(ref, str):
#             return ref                         # virtual — layer già stringa
#         try:
#             return ref.dxf.layer if ref.dxf.hasattr("layer") else ""
#         except AttributeError:
#             return ""


# forge/adapters/dxf/adapter.py

from typing import Any, List, Optional

from ...core.adapter_base import ForgeAdapter
from ...model.edge import Edge
from ...model.shape_proxy import ShapeProxy
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
    
    def collect_proxies(self, open_splines: list, virtual_shapes: list) -> list[ShapeProxy]:
        from .proxy_adapter import entity_to_proxy, contour_to_proxy
        from .geometry_adapter import _spline_is_closed

        open_spline_ids = {id(s) for s in open_splines}
        proxies = []
        for entity in self.msp:
            proxy = entity_to_proxy(entity)
            if proxy is None:
                continue
            entity_type = entity.dxftype()
            if entity_type == "SPLINE" and id(entity) in open_spline_ids:
                continue
            proxies.append(proxy)

        virtual = [contour_to_proxy(ctx) for ctx in virtual_shapes]
        return virtual + proxies