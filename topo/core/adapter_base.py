# topo/core/adapter_base.py
"""
Contratto base per gli adapter di input di Topo.

Un adapter traduce la geometria di una sorgente nel vocabolario
geometrico che il Core può elaborare.

L'adapter NON costruisce feature di dominio e non conosce
la topologia del Core: produce Edge e fornisce il contesto della
sorgente quando necessario.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from .topology.edge import Edge
from .geometry.measure import NODE_DECIMALS
from ..model.document import DEFAULT_NODE_TOLERANCE


class Adapter(ABC):

    def __init__(self, tolerance: float = DEFAULT_NODE_TOLERANCE):
        # `tolerance` è il gap che heal() chiuderà di default, non la griglia dei nodi (D113)
        self.tolerance = tolerance
        self.node_decimals = NODE_DECIMALS

    @abstractmethod
    def to_edges(self) -> list[Edge]:
        """Converte la geometria della sorgente in Edge topologici."""
        ...

    @abstractmethod
    def source_context(self, ref: Any) -> str:
        """Restituisce il contesto della sorgente associata a un Edge."""
        ...