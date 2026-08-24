# forge/core/adapter_base.py
"""
Contratto base per gli adapter di input di Forge.

Un adapter traduce la geometria di una sorgente nel vocabolario
geometrico che il Core può elaborare.

L'adapter NON costruisce ClosedShape/OpenShape e non conosce
la topologia del Core: produce Edge e fornisce il contesto della
sorgente quando necessario.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import numpy as np

from ..adapters.bridge.edge import Edge


class ForgeAdapter(ABC):

    def __init__(self, tolerance: float = 0.05):
        self.tolerance = tolerance
        self.node_decimals = max(round(-np.log10(tolerance * 2)), 1)

    @abstractmethod
    def to_edges(self) -> list[Edge]:
        """Converte la geometria della sorgente in Edge topologici."""
        ...

    @abstractmethod
    def source_context(self, ref: Any) -> str:
        """Restituisce il contesto della sorgente associata a un Edge."""
        ...