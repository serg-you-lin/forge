"""
model/curve.py

Gerarchia base del dominio topo: una curva è una sequenza di segmenti,
chiusa o aperta. Nome geometrico, non di processo (MAP.md D114).

Curve
├── ClosedCurve   — contorno chiuso (loop), ha polygon e segments
└── OpenCurve     — tracciato aperto, ha segments ma non polygon

Tutte le entità del modello ereditano da qui:
    Hole(ClosedCurve), Contour(ClosedCurve)
    BendingLine(OpenCurve), Engraving(OpenCurve)

Note:
    - segments è List[LineSeg | ArcSeg | SplineSeg] — primitive pure, zero ezdxf
    - styles è List[EdgeStyle], allineata 1:1 a segments — aspetto grezzo
      (linetype/colore) dell'entità sorgente di ogni segmento (Cluster E).
      Può essere più corta di segments o vuota (geometria sintetizzata, es.
      ponti di gap-closing o il fallback polygonize): chi la consuma in
      write() tratta un indice mancante come "nessuno stile noto".
    - polygon è Shapely Polygon — calcolato dall'adapter, non dal core
    - role è l'unico canale semantico interno — mai leggere layer DXF nel core
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from shapely.geometry import Polygon

from topo.core.primitives.segments import ArcSeg, LineSeg, SplineSeg
from topo.model.style import EdgeStyle


@dataclass
class Curve:
    """
    Radice della gerarchia. Porta solo identità semantica e traceability.

    Non istanziare direttamente — usare ClosedCurve o OpenCurve.
    """
    role:       str          # costante ContourRole, o slug di un consumatore


@dataclass
class ClosedCurve(Curve):
    """
    Curva chiusa: ha un polygon e una lista di segmenti.

    Il polygon è prodotto dall'adapter (o dal polygon_builder) e passato
    al costruttore — il core non lo ricalcola mai.

    Non porta `diameter` / `center`: la geometria circolare di un contorno è
    ricavata al bisogno da `core.geometry.measure.circular_geometry()` e stoccata
    sull'oggetto `Hole` da `detect_flat()` (D15), non sul contorno grezzo.
    """
    polygon:  Polygon                          = field(default=None)
    segments: List[LineSeg | ArcSeg | SplineSeg] = field(default_factory=list)
    styles:   List[EdgeStyle]                  = field(default_factory=list)

    @property
    def area(self) -> float:
        return self.polygon.area if self.polygon is not None else 0.0

    @property
    def bbox(self) -> Tuple[float, float, float, float]:
        return self.polygon.bounds if self.polygon is not None else (0.0, 0.0, 0.0, 0.0)


@dataclass
class OpenCurve(Curve):
    """
    Curva aperta: ha segmenti ma non un polygon.
    """
    segments:    List[LineSeg | ArcSeg | SplineSeg] = field(default_factory=list)
    styles:      List[EdgeStyle]                  = field(default_factory=list)
    cluster_ref: Optional[int]                    = None   # indice in result.clusters dell'isola che la contiene (island, D99)