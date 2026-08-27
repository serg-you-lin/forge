"""
model/part.py
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional, Set, Tuple

from shapely.geometry import Polygon

from forge.core.primitives import LineSeg, ArcSeg, CircleSeg, SplineSeg
from forge.model.feature import ClosedFeature
from forge.model.role import ContourRole
from forge.model.hole import Hole
from forge.model.bending_line import BendingLine
from forge.model.engraving import EngravingClosed, EngravingOpen


@dataclass
class ForgeContour(ClosedFeature):

    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "area": round(self.area, 4),
        }


@dataclass
class ForgePart:
    outer:         ForgeContour
    holes:         List[Hole]                              = field(default_factory=list)
    inners:        List[ForgeContour]                      = field(default_factory=list)
    bending_lines: List[BendingLine]                       = field(default_factory=list)
    engrave_lines: List[EngravingClosed | EngravingOpen]   = field(default_factory=list)
    label:         str                                     = ""
    source_file:   str                                     = ""
    custom:        dict                                    = field(default_factory=dict)

    @property
    def polygon_with_holes(self) -> Polygon:
        all_inners = (
            [h.polygon for h in self.holes]
            + [i.polygon for i in self.inners]
        )
        if not all_inners:
            return self.outer.polygon
        return Polygon(
            self.outer.polygon.exterior.coords,
            [p.exterior.coords for p in all_inners],
        )

    @property
    def bbox(self):
        return self.outer.bbox

    @property
    def area(self) -> float:
        return (
            self.outer.area
            - sum(h.area for h in self.holes)
            - sum(i.area for i in self.inners)
        )

    def to_dict(self) -> dict:
        return {
            "label":                self.label,
            "source_file":          self.source_file,
            "area":                 round(self.area, 4),
            "holes_count":          len(self.holes),
            "inner_contours_count": len(self.inners),
            "bbox": {
                "minx": round(self.bbox[0], 4),
                "miny": round(self.bbox[1], 4),
                "maxx": round(self.bbox[2], 4),
                "maxy": round(self.bbox[3], 4),
            },
            "outer":  list(self.outer.polygon.exterior.coords),
            "holes":  [h.to_dict() for h in self.holes],
            "inners": [list(i.polygon.exterior.coords) for i in self.inners],
            "custom": self.custom,
        }