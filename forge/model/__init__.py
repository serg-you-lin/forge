# model/__init__.py
from .annotation import (
    Annotation, Note, Dimension, Leader, RenderedGeometry, RenderedText,
)
from .document import ForgeDocument
from .contour import ForgeContour
from .cluster import ForgeCluster
from .result import ForgeResult
from .feature import Feature, ClosedFeature, OpenFeature
from .style import EdgeStyle

__all__ = [
    "ForgeDocument",
    "Annotation",
    "Note",
    "Dimension",
    "Leader",
    "RenderedGeometry",
    "RenderedText",
    "ForgeContour",
    "ForgeCluster",
    "ForgeResult",
    "Feature",
    "ClosedFeature",
    "OpenFeature",
    "EdgeStyle",
]


def __getattr__(name):
    if name == "Edge":
        from ..core.topology.edge import Edge
        return Edge
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
