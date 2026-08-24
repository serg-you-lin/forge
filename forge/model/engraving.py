"""
model/engraving.py

Incisione rilevata da detect().

EngravingClosed : contorno chiuso  → ClosedFeature (ha polygon)
EngravingOpen   : traccia aperta   → OpenFeature   (ha pts + geometry)

ForgePart usa List[EngravingClosed | EngravingOpen] — sono sempre
trattate insieme perché semanticamente identiche.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional, Tuple

from shapely.geometry import LineString, Polygon

from forge.model.feature import ClosedFeature, OpenFeature
from forge.model.role import ContourRole


@dataclass
class EngravingClosed(ClosedFeature):
    length:     float = 0.0
    part_label: str   = ""

    def __post_init__(self):
        if self.role == ContourRole.UNKNOWN:
            self.role = ContourRole.ENGRAVE

    def source_layer(self) -> str:
        try:
            if self.source_ref is not None and self.source_ref.dxf.hasattr("layer"):
                layer = self.source_ref.dxf.layer
                if layer:
                    return str(layer)
        except Exception:
            pass
        if self.role is not None and self.role != ContourRole.UNKNOWN:
            return self.role.value
        return ""

    def to_dict(self) -> dict:
        d = {
            "closed":     True,
            "length":     round(self.length, 4),
            "part_label": self.part_label,
        }
        layer = self.source_layer()
        if layer:
            d["origin"] = layer
        return d


@dataclass
class EngravingOpen(OpenFeature):
    length:     float                         = 0.0
    part_label: str                           = ""
    pts:        List[Tuple[float, float]]     = field(default_factory=list)
    geometry:   Optional[LineString]          = None

    def __post_init__(self):
        if self.role == ContourRole.UNKNOWN:
            self.role = ContourRole.ENGRAVE

    def source_layer(self) -> str:
        try:
            if self.source_ref is not None and self.source_ref.dxf.hasattr("layer"):
                layer = self.source_ref.dxf.layer
                if layer:
                    return str(layer)
        except Exception:
            pass
        if self.role is not None and self.role != ContourRole.UNKNOWN:
            return self.role.value
        return ""

    def to_dict(self) -> dict:
        d = {
            "closed":     False,
            "length":     round(self.length, 4),
            "part_label": self.part_label,
        }
        layer = self.source_layer()
        if layer:
            d["origin"] = layer
        if self.pts:
            d["start"] = self.pts[0]
            d["end"]   = self.pts[-1]
        return d