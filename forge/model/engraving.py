"""
model/engraving.py

Incisione rilevata da detect().

EngravingClosed : contorno chiuso  → ClosedFeature (ha polygon)
EngravingOpen   : traccia aperta   → OpenFeature   (ha pts + geometry)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from shapely.geometry import LineString

from forge.model.feature import ClosedFeature, OpenFeature
from forge.model.role import ContourRole


@dataclass
class EngravingClosed(ClosedFeature):
    length:     float = 0.0
    part_label: str   = ""

    def __post_init__(self):
        if self.role == ContourRole.UNKNOWN:
            self.role = ContourRole.ENGRAVE

    def to_dict(self) -> dict:
        return {
            "closed":     True,
            "length":     round(self.length, 4),
            "part_label": self.part_label,
        }


@dataclass
class EngravingOpen(OpenFeature):
    length:     float                     = 0.0
    part_label: str                       = ""
    pts:        List[Tuple[float, float]] = field(default_factory=list)
    geometry:   Optional[LineString]      = None

    def __post_init__(self):
        if self.role == ContourRole.UNKNOWN:
            self.role = ContourRole.ENGRAVE

    def to_dict(self) -> dict:
        d = {
            "closed":     False,
            "length":     round(self.length, 4),
            "part_label": self.part_label,
        }
        if self.pts:
            d["start"] = self.pts[0]
            d["end"]   = self.pts[-1]
        return d