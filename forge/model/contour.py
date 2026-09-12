"""
model/contour.py

Contorno chiuso generico — un loop con un ruolo, senza semantica di feature.

È il tipo che `heal()` produce per l'outer del cluster e per i suoi loop
interni non ancora classificati (`cluster.inners`). `detect()` promuove un
`ForgeContour` circolare sotto soglia a `Hole`; quello che resta è un taglio a
contorno. Sorella di `Hole` / `Engraving`: sta in un file proprio, non annidata
in `cluster.py` che definisce solo il contenitore.

`depth` e `parent` portano l'albero di contenimento che `HierarchyBuilder`
costruisce internamente (padre → figli → nipoti, a profondità arbitraria) e
che altrimenti verrebbe perso appiattendo tutto in `cluster.inners`: l'outer
ha `depth=0`/`parent=None`, un figlio diretto `depth=1`, un nipote `depth=2`,
e così via. Puramente geometrico (contenimento fra poligoni, calcolato in
`heal()`), non semantico — `detect()` può ricostruire il ruolo che vuole,
questi due campi non cambiano.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from forge.model.feature import ClosedFeature


@dataclass
class ForgeContour(ClosedFeature):
    depth:  int                        = 0
    parent: Optional["ForgeContour"]   = None

    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "area": round(self.area, 4),
            "depth": self.depth,
        }
