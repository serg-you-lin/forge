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
from .part import ForgeContour, ForgePart
from .result import ForgeResult
from .engraving import Engraving

__all__ = [
    "Hole",
    "HOLE_TYPE_UNKNOWN",
    "HOLE_TYPE_PLAIN",
    "HOLE_TYPE_COUNTERSINK",
    "HOLE_TYPE_THREADED",
    "VALID_HOLE_TYPES",
    "ClassifiedEntity",
    "BaseInterpreter",
    "ForgeContour",
    "ForgePart",
    "ForgeResult",
    "Engraving",
    "Edge",
    "BendingLine",
    "ClosedShape",
    "OpenShape",
]


def __getattr__(name):
    if name in {"Edge", "BendingLine"}:
        from ..bridge.edge import Edge, BendingLine
        return {"Edge": Edge, "BendingLine": BendingLine}[name]
    if name in {"ClosedShape", "OpenShape"}:
        from ..bridge.shape import ClosedShape, OpenShape
        return {"ClosedShape": ClosedShape, "OpenShape": OpenShape}[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")