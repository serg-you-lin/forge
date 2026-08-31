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


@dataclass
class EdgeStyle:
    linetype:         str                          = "BYLAYER"
    linetype_desc:    str                           = ""
    linetype_pattern: Optional[Tuple[float, ...]]   = None
    color:            int                           = 256   # ACI, 256 = BYLAYER
    true_color:       Optional[int]                 = None  # 24-bit RGB, None = non impostato
