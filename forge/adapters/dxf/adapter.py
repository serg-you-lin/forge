# adapters/dxf/adapter.py

from typing import Any, List, Optional

from ...core.adapter_base import ForgeAdapter
from ...model.edge import Edge
from ...model.shape_proxy import ShapeProxy
from .graph_adapter import edges_from_msp
from .proxy_adapter import entity_to_proxy, contour_to_proxy


class DxfAdapter(ForgeAdapter):
    """
    Adapter DXF → core.
    Unico punto del progetto che conosce ezdxf e produce tipi core.
    """

    def __init__(
        self,
        msp,
        node_decimals: int,
        exclude_ids: Optional[set] = None,
        ignore_layers: Optional[set] = None,
    ):
        self.msp           = msp
        self.node_decimals = node_decimals
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
            return ref                         # virtual — layer già stringa
        try:
            return ref.dxf.layer if ref.dxf.hasattr("layer") else ""
        except AttributeError:
            return ""