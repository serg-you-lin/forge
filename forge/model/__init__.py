# model/__init__.py
from .hole import (
    Hole,
    HOLE_TYPE_UNKNOWN,
    HOLE_TYPE_PLAIN,
    HOLE_TYPE_COUNTERSINK,
    HOLE_TYPE_THREADED,
    VALID_HOLE_TYPES,
)
from .classified import ClassifiedEntity
from .annotation import (
    Annotation, Note, Dimension, Leader, RenderedGeometry, RenderedText,
)
from .document import ForgeDocument
from .contour import ForgeContour
from .cluster import ForgeCluster
from .result import ForgeResult
from .engraving import Engraving
from .bending_line import BendingLine
from .feature import Feature, ClosedFeature, OpenFeature
from .style import EdgeStyle

__all__ = [
    "Hole",
    "HOLE_TYPE_UNKNOWN",
    "HOLE_TYPE_PLAIN",
    "HOLE_TYPE_COUNTERSINK",
    "HOLE_TYPE_THREADED",
    "VALID_HOLE_TYPES",
    "ClassifiedEntity",
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
    "Engraving",
    "BendingLine",
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