"""
model/contour.py

Contorno chiuso generico — un loop con un ruolo, senza semantica di feature.

È il tipo che `heal()` produce per l'outer del cluster e per i suoi loop
interni non ancora classificati (`cluster.inners`). `detect()` promuove un
`ForgeContour` circolare sotto soglia a `Hole`; quello che resta è un taglio a
contorno. Sorella di `Hole` / `Engraving`: sta in un file proprio, non annidata
in `cluster.py` che definisce solo il contenitore.
"""
from __future__ import annotations

from dataclasses import dataclass

from forge.model.feature import ClosedFeature


@dataclass
class ForgeContour(ClosedFeature):

    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "area": round(self.area, 4),
        }
