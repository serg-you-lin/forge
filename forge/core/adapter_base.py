from abc import ABC, abstractmethod
from typing import Any, List
from ..model.edge import Edge
from ..model.shape_proxy import ShapeProxy


class ForgeAdapter(ABC):

    @abstractmethod
    def to_edges(self) -> List["Edge"]:
        """Produce gli archi per il grafo topologico."""
        ...

    @abstractmethod
    def to_proxies(self) -> List["ShapeProxy"]:
        """Produce le forme chiuse pre-esistenti (cerchi, polyline chiuse, spline chiuse)."""
        ...

    @abstractmethod
    def source_context(self, ref: Any) -> str:
        """
        Estrae il contesto semantico di origine dall'oggetto originale.
        Per DXF: entity.dxf.layer
        Per SVG: stroke-color, group id, ecc.
        """
        ...