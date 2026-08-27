"""
model/bending_line.py

Linea di piega — OpenFeature.
Spostata da bridge/edge.py dove conviveva con Edge (topologia adapter).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from shapely.geometry import LineString

from forge.model.feature import OpenFeature
from forge.model.role import ContourRole


@dataclass
class BendingLine(OpenFeature):
    geometry:   LineString    = field(default=None)
    length:     float         = 0.0
    angle_deg:  float         = 0.0
    part_label: str           = ""

    def __post_init__(self):
        if self.role == ContourRole.UNKNOWN:
            self.role = ContourRole.BEND

    def to_dict(self) -> dict:
        coords = list(self.geometry.coords)
        return {
            "start":      coords[0],
            "end":        coords[-1],
            "length":     round(self.length, 4),
            "angle_deg":  round(self.angle_deg, 4),
            "part_label": self.part_label,
        }
