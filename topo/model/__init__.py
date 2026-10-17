# model/__init__.py
from .annotation import (
    Annotation, Note, Dimension, Leader, RenderedGeometry, RenderedText,
)
from .document import Document
from .contour import Contour
from .cluster import Cluster
from .result import Result
from .curve import Curve, ClosedCurve, OpenCurve
from .style import EdgeStyle
from .detected import DetectedFeature, DetectedFeatures

__all__ = [
    "Document",
    "Annotation",
    "Note",
    "Dimension",
    "Leader",
    "RenderedGeometry",
    "RenderedText",
    "Contour",
    "Cluster",
    "Result",
    "Curve",
    "ClosedCurve",
    "OpenCurve",
    "EdgeStyle",
    "DetectedFeature",
    "DetectedFeatures",
]


def __getattr__(name):
    if name == "Edge":
        from ..core.topology.edge import Edge
        return Edge
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
