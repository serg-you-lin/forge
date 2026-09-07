"""
model/cluster.py
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional, Set, Tuple

from shapely.geometry import Polygon

from forge.core.primitives import LineSeg, ArcSeg, CircleSeg, SplineSeg
from forge.model.feature import ClosedFeature
from forge.model.role import ContourRole
from forge.model.hole import (
    Hole, HOLE_TYPE_PLAIN, HOLE_TYPE_COUNTERSINK, HOLE_TYPE_THREADED,
)
from forge.model.bending_line import BendingLine
from forge.model.engraving import Engraving

# Tolleranza per raggruppare le bending line collineari in un'unica piega
# logica. Era il default di `inject()` prima che il conteggio diventasse
# `cluster.summary` (MAP.md D8).
_BENDING_GROUP_TOLERANCE = 0.1


@dataclass
class ForgeContour(ClosedFeature):

    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "area": round(self.area, 4),
        }


@dataclass
class ForgeCluster:
    outer:         ForgeContour
    holes:         List[Hole]                              = field(default_factory=list)
    inners:        List[ForgeContour]                      = field(default_factory=list)
    bending_lines: List[BendingLine]                       = field(default_factory=list)
    engrave_lines: List[Engraving]                         = field(default_factory=list)
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

    @property
    def summary(self) -> dict:
        """
        Conteggi delle feature, derivati al volo dalle liste tipate del cluster.

        Sostituisce il lavoro di conteggio che `inject()` faceva copiando in
        `cluster.custom` (MAP.md D8): gli stessi numeri, ma calcolati dal modello
        invece che tenuti in uno stato a parte che poteva desincronizzarsi.
        `inject()` resta solo per il `data_injector` esterno (materiale,
        spessore, codice pezzo dai testi).
        """
        from collections import Counter
        from forge.core.geometry import group_collinear_lines

        htypes = Counter(h.hole_type for h in self.holes)

        bending_groups = (
            len(group_collinear_lines(
                [bl.geometry for bl in self.bending_lines],
                tolerance=_BENDING_GROUP_TOLERANCE,
            ))
            if self.bending_lines else 0
        )

        marking = self.custom.get("marking_entities", []) or []

        return {
            "plain_holes_count":    htypes.get(HOLE_TYPE_PLAIN, 0),
            "countersink_count":    htypes.get(HOLE_TYPE_COUNTERSINK, 0),
            "threaded_holes_count": htypes.get(HOLE_TYPE_THREADED, 0),
            "bending_lines":        bending_groups,
            "total_engrave_length": round(
                sum(e.length or 0.0 for e in self.engrave_lines), 4
            ),
            "total_marking_length": round(
                sum(m.get("length") or 0.0 for m in marking), 4
            ),
        }

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