"""
model/hole.py
"""
from dataclasses import dataclass, field
from typing import Optional, Tuple, Any
from shapely.geometry import Polygon

from forge.model.feature import ClosedFeature
from forge.model.role import ContourRole

HOLE_TYPE_UNKNOWN      = "unknown"
HOLE_TYPE_PLAIN        = "plain"
HOLE_TYPE_COUNTERSINK  = "countersink"
HOLE_TYPE_THREADED     = "threaded"

VALID_HOLE_TYPES = {
    HOLE_TYPE_UNKNOWN,
    HOLE_TYPE_PLAIN,
    HOLE_TYPE_COUNTERSINK,
    HOLE_TYPE_THREADED,
}


@dataclass
class Hole(ClosedFeature):
    diameter:       float                     = 0.0
    center:         Tuple[float, float]       = field(default_factory=lambda: (0.0, 0.0))
    hole_type:      str                       = HOLE_TYPE_UNKNOWN
    geometric_hint: str                       = ""
    confidence:     float                     = 0.0
    source:         str                       = ""
    vs_id:          Optional[int]             = None
    origin:         str                       = ""
    outer_diameter:   Optional[float]         = None
    outer_source_ref: Any                     = None
    is_hole:          bool                    = True

    def __post_init__(self):
        if self.role == ContourRole.UNKNOWN:
            self.role = ContourRole.HOLE

    def source_layer(self) -> str:
        try:
            return self.source_ref.dxf.layer
        except Exception:
            return self.origin

    def to_dict(self) -> dict:
        d = {
            "hole_type":  self.hole_type,
            "diameter":   round(self.diameter, 4),
            "center":     (round(self.center[0], 4), round(self.center[1], 4)),
            "role":       self.role,
            "confidence": round(self.confidence, 4),
            "source":     self.source,
        }
        layer = self.source_layer()
        if layer:
            d["origin"] = layer
        if self.outer_diameter is not None:
            d["outer_diameter"] = round(self.outer_diameter, 4)
        return d