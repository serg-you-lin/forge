"""
model/contour.py

Contorno chiuso generico — un loop con un ruolo, senza semantica di feature.

È il tipo che `heal()` produce per l'outer del cluster e per i suoi loop
interni non ancora classificati (`cluster.inners`). `detect_flat()` promuove un
`Contour` circolare sotto soglia a `Hole`; quello che resta è un taglio a
contorno. Sorella di `Hole` / `Engraving`: sta in un file proprio, non annidata
in `cluster.py` che definisce solo il contenitore.

`depth` e `parent` portano l'albero di contenimento che `HierarchyBuilder`
costruisce internamente (padre → figli → nipoti, a profondità arbitraria) e
che altrimenti verrebbe perso appiattendo tutto in `cluster.inners`: l'outer
ha `depth=0`/`parent=None`, un figlio diretto `depth=1`, un nipote `depth=2`,
e così via. Puramente geometrico (contenimento fra poligoni, calcolato in
`heal()`), non semantico — `detect_flat()` può ricostruire il ruolo che vuole,
questi due campi non cambiano.

`Contour.from_segments()` costruisce un contorno da un anello di
primitive scritto da un chiamante (D118): controlla l'anello e calcola il
poligono, così nessuno passa `polygon` a mano.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Sequence

from topo.core.primitives.polygon_builder import build_polygon
from topo.core.primitives.segments import DEFAULT_TOLERANCE, segment_endpoints
from topo.model.curve import ClosedCurve


@dataclass
class Contour(ClosedCurve):
    depth:  int                        = 0
    parent: Optional["Contour"]   = None

    @classmethod
    def from_segments(cls, segments: Sequence, role: str, depth: int = 0,
                      parent: Optional["Contour"] = None,
                      tolerance: float = DEFAULT_TOLERANCE) -> "Contour":
        """
        Contorno da un anello di primitive testa-coda: ogni segmento parte
        dove finisce il precedente (entro `tolerance`), l'ultimo chiude sul
        primo. Il poligono lo calcola topo. ValueError se l'anello non chiude
        o non racchiude un poligono valido.
        """
        segs = list(segments)
        for k, seg in enumerate(segs):
            end, start = segment_endpoints(seg)[1], segment_endpoints(segs[(k + 1) % len(segs)])[0]
            if math.dist(end, start) > tolerance:
                raise ValueError(f"from_segments: il segmento {k} finisce a {end}, "
                                 f"il successivo parte da {start}: non è un anello")
        polygon = build_polygon(segs, tolerance)
        if polygon is None:
            raise ValueError("from_segments: i segmenti non racchiudono un poligono valido")
        return cls(role=role, polygon=polygon, segments=segs, depth=depth, parent=parent)

    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "area": round(self.area, 4),
            "depth": self.depth,
        }
