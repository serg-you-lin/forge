# forge/core/adapter_base.py

import numpy as np
from abc import ABC, abstractmethod
from typing import Any, List
from ..bridge.edge import Edge
from ..bridge.shape import ClosedShape, OpenShape


class ForgeAdapter(ABC):

    def __init__(self, tolerance: float = 0.05):
        self.tolerance = tolerance
        self.node_decimals = max(round(-np.log10(tolerance * 2)), 1)

    @abstractmethod
    def to_edges(self) -> List[Edge]:
        """Produce gli archi per il grafo topologico."""
        ...

    @abstractmethod
    def to_closed(self) -> List[ClosedShape]:
        """Produce le forme chiuse (cerchi, polyline chiuse, spline chiuse, virtual)."""
        ...

    @abstractmethod
    def to_open(self) -> List[OpenShape]:
        """Produce le tracce aperte (LINE, ARC, spline aperte)."""
        ...

    @abstractmethod
    def source_context(self, ref: Any) -> str:
        ...