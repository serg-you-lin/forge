# model/forge_text.py

from dataclasses import dataclass
from typing import Any, Optional
from shapely.geometry import Point

@dataclass
class ForgeText:
    """
    Testo estratto da una fonte (DXF, PDF, SVG, ...).
    Prodotto dall'adapter, consumato da inject().

    Campi:
        content    : testo grezzo già pulito (strip, plain_mtext applicati)
        position   : Point shapely — per containment check nel core
        source_ref : entità originale opaca — per write-back se serve
    """
    content:    str
    position:   Point
    source_ref: Optional[Any] = None