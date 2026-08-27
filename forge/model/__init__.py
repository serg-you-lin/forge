# model/__init__.py
from .hole import (
    Hole,
    HOLE_TYPE_UNKNOWN,
    HOLE_TYPE_PLAIN,
    HOLE_TYPE_COUNTERSINK,
    HOLE_TYPE_THREADED,
    VALID_HOLE_TYPES,
)
from .classified import ClassifiedEntity, BaseInterpreter
from .document import ForgeDocument, Annotation
from .part import ForgeContour, ForgePart
from .result import ForgeResult
from .engraving import Engraving
from .bending_line import BendingLine
from .feature import Feature, ClosedFeature, OpenFeature

__all__ = [
    "Hole",
    "HOLE_TYPE_UNKNOWN",
    "HOLE_TYPE_PLAIN",
    "HOLE_TYPE_COUNTERSINK",
    "HOLE_TYPE_THREADED",
    "VALID_HOLE_TYPES",
    "ClassifiedEntity",
    "BaseInterpreter",
    "ForgeDocument",
    "Annotation",
    "ForgeContour",
    "ForgePart",
    "ForgeResult",
    "Engraving",
    "BendingLine",
    "Feature",
    "ClosedFeature",
    "OpenFeature",
]


def __getattr__(name):
    if name == "Edge":
        from ..adapters.bridge.edge import Edge
        return Edge
    if name in {"ClosedShape", "OpenShape"}:
        from ..adapters.bridge.shape import ClosedShape, OpenShape
        return {"ClosedShape": ClosedShape, "OpenShape": OpenShape}[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")