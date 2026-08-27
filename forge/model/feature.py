"""
model/feature.py

Gerarchia base del dominio forge.

Feature
├── ClosedFeature   — contorno chiuso (loop), ha polygon e segments
└── OpenFeature     — tracciato aperto, ha segments ma non polygon

Tutte le entità del modello ereditano da qui:
    Hole(ClosedFeature), ForgeContour(ClosedFeature), EngravingClosed(ClosedFeature)
    BendingLine(OpenFeature), EngravingOpen(OpenFeature)

Note:
    - segments è List[LineSeg | ArcSeg | SplineSeg] — primitive pure, zero ezdxf
    - polygon è Shapely Polygon — calcolato dall'adapter, non dal core
    - source_ref è opaco — solo adapters/dxf/ lo legge/scrive
    - role è l'unico canale semantico interno — mai leggere layer DXF nel core
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional, Tuple

from shapely.geometry import Polygon

from forge.core.primitives.segments import ArcSeg, LineSeg, SplineSeg
from forge.model.role import ContourRole


@dataclass
class Feature:
    """
    Radice della gerarchia. Porta solo identità semantica e traceability.

    Non istanziare direttamente — usare ClosedFeature o OpenFeature.
    """
    role:       ContourRole


@dataclass
class ClosedFeature(Feature):
    """
    Feature con geometria chiusa: ha un polygon e una lista di segmenti.

    Il polygon è prodotto dall'adapter (o dal polygon_builder) e passato
    al costruttore — il core non lo ricalcola mai.
    """
    polygon:  Polygon                          = field(default=None)
    segments: List[LineSeg | ArcSeg | SplineSeg] = field(default_factory=list)

    @property
    def area(self) -> float:
        return self.polygon.area if self.polygon is not None else 0.0

    @property
    def bbox(self) -> Tuple[float, float, float, float]:
        return self.polygon.bounds if self.polygon is not None else (0.0, 0.0, 0.0, 0.0)


@dataclass
class OpenFeature(Feature):
    """
    Feature con geometria aperta: ha segmenti ma non un polygon.
    """
    segments: List[LineSeg | ArcSeg | SplineSeg] = field(default_factory=list)