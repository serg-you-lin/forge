# model/forge_text.py

from dataclasses import dataclass
from shapely.geometry import Point

@dataclass
class ForgeText:
    """
    Testo estratto da una fonte (DXF, PDF, SVG, ...).
    Prodotto dall'adapter, consumato da inject().

    Campi:
        content    : testo grezzo già pulito (strip, plain_mtext applicati)
        position   : Point shapely — per containment check nel core
    """
    content:    str
    position:   Point
