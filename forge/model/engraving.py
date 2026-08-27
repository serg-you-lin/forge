"""
model/engraving.py

Incisione rilevata da detect().

Un solo tipo: `Engraving`. Un'incisione è concettualmente una traccia aperta
(N segmenti su layer engrave). Un contorno chiuso su layer engrave NON viene
riassemblato in un loop unico — resta N segmenti separati (scelta di progetto).
`polygon` è valorizzato solo quando la traccia era già degenere in origine
(CIRCLE, SPLINE chiusa): serve al contenimento, non è un loop strutturale.
`closed` non è uno stato a sé: è `polygon is not None`, esposto come property.

Doppio binario di provenienza, identico a Hole:
    source="labeled"   → ruolo assegnato da label_map al load   (confidence 1.0)
    source="geometric" → inferenza geometrica in detect()        (confidence < 1.0)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from shapely.geometry import LineString, Polygon

from forge.model.feature import OpenFeature
from forge.model.role import ContourRole


@dataclass
class Engraving(OpenFeature):
    length:     float                    = 0.0
    part_label: str                      = ""
    pts:        List[Tuple[float, float]] = field(default_factory=list)
    geometry:   Optional[LineString]     = None
    polygon:    Optional[Polygon]        = None
    confidence: float                    = 1.0
    source:     str                      = "labeled"

    def __post_init__(self):
        if self.role == ContourRole.UNKNOWN:
            self.role = ContourRole.ENGRAVE

    @property
    def closed(self) -> bool:
        """Traccia già chiusa in origine (CIRCLE / SPLINE chiusa) ⇔ ha un polygon."""
        return self.polygon is not None

    def to_dict(self) -> dict:
        d = {
            "closed":     self.closed,
            "length":     round(self.length, 4),
            "part_label": self.part_label,
            "source":     self.source,
            "confidence": round(self.confidence, 4),
        }
        if self.pts and not self.closed:
            d["start"] = self.pts[0]
            d["end"]   = self.pts[-1]
        return d
