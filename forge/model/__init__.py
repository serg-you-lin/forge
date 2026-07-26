# model/__init__.py
from .hole import (
    Hole,
    HOLE_TYPE_UNKNOWN,
    HOLE_TYPE_PLAIN,
    HOLE_TYPE_COUNTERSINK,
    HOLE_TYPE_THREADED,
    VALID_HOLE_TYPES,
)
from .edge import Edge, BendingLine
from .classified import ClassifiedEntity, BaseInterpreter
from .part import ForgeContour, ForgePart
from .result import ForgeResult
from .shape import ClosedShape, OpenShape