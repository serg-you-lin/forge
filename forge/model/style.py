"""
model/style.py
---------------
Aspetto visivo grezzo di un'entità sorgente — linetype e colore.

Dato di dominio puro, zero riferimenti a ezdxf: il pattern del linetype (se
non è uno dei tre standard BYLAYER/BYBLOCK/CONTINUOUS) è già risolto in una
tupla di lunghezze (`linetype_pattern`), pronta per essere ri-registrata in un
documento di output senza mai riaprire la sorgente. Captato dall'adapter al
load (`Edge.style`), sopravvive nel modello come `styles` — lista parallela a
`segments` su ClosedFeature/OpenFeature — fino a write(), che ripristina
sempre il linetype (Cluster E). Il colore NON viene mai riapplicato in
output: resta quello del layer forge di destinazione, una decisione di
dominio per ruolo (`rules/palette.py`) — trash compreso. `color`/`true_color`
restano comunque catturati qui perché `detect()` potrà usarli in futuro come
segnale addizionale per dedurre il ruolo, insieme al linetype.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

# Forma del tratto (D64): continua, tratteggio uniforme (un solo segno ripetuto:
# tratti tutti uguali, o solo punti), catena (segni diversi alternati: tratto
# lungo + tratto corto o punto).
DASH_CONTINUOUS = "continuous"
DASH_UNIFORM    = "uniform"
DASH_CHAIN      = "chain"
VALID_DASH_KINDS = {DASH_CONTINUOUS, DASH_UNIFORM, DASH_CHAIN}

# Due segni sono "diversi" se differiscono più di questa frazione della
# lunghezza totale del pattern: relativo, così la scala del pattern non conta.
_MARK_REL_TOL = 0.05


@dataclass
class EdgeStyle:
    linetype:         str                          = "BYLAYER"
    linetype_desc:    str                           = ""
    linetype_pattern: Optional[Tuple[float, ...]]   = None
    color:            int                           = 256   # ACI, 256 = BYLAYER
    true_color:       Optional[int]                 = None  # 24-bit RGB, None = non impostato

    @property
    def is_dashed(self) -> bool:
        """True se il pattern ha almeno un vuoto (elemento negativo, D63)."""
        if not self.linetype_pattern:
            return False
        return any(element < 0 for element in self.linetype_pattern[1:])

    @property
    def dash_kind(self) -> str:
        """Forma del tratto: `continuous`, `uniform` o `chain` (D64)."""
        if not self.is_dashed:
            return DASH_CONTINUOUS
        elements = self.linetype_pattern[1:]
        marks = [e for e in elements if e >= 0]    # tratti (> 0) e punti (= 0)
        total = self.linetype_pattern[0] or sum(abs(e) for e in elements)
        if max(marks, default=0.0) - min(marks, default=0.0) > _MARK_REL_TOL * total:
            return DASH_CHAIN
        return DASH_UNIFORM
