# tools/model/__init__.py
#
# Tipi prodotti da detect() — non geometria di heal(), quindi non in
# forge/model/ (branch refactor/detect-overlay, MAP.md D44).
from .hole import (
    Hole,
    HOLE_TYPE_UNKNOWN,
    HOLE_TYPE_PLAIN,
    HOLE_TYPE_COUNTERSINK,
    HOLE_TYPE_THREADED,
    VALID_HOLE_TYPES,
)
from .bending_line import BendingLine
from .engraving import Engraving
from .classified import ClassifiedEntity
from .detected_features import DetectedFeature, DetectedFeatures

__all__ = [
    "Hole",
    "HOLE_TYPE_UNKNOWN",
    "HOLE_TYPE_PLAIN",
    "HOLE_TYPE_COUNTERSINK",
    "HOLE_TYPE_THREADED",
    "VALID_HOLE_TYPES",
    "BendingLine",
    "Engraving",
    "ClassifiedEntity",
    "DetectedFeature",
    "DetectedFeatures",
]
