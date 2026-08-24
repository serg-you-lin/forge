"""
bridge/edge.py
"""

from dataclasses import dataclass
from typing import Optional, Tuple, Any
from shapely.geometry import LineString

@dataclass
class Edge:
    """
    Rappresentazione topologica di una entità geometrica lineare.

    Layer intermedio tra l'entità DXF grezza e il topology engine.
    Il riferimento all'entità originale non viene mai perso.

    Campi:
        source_ref : riferimento all'entità ezdxf originale (LINE, ARC, SPLINE)
        layer    : layer DXF — cached per non rileggere source_ref.dxf.layer
        start    : endpoint arrotondato alla tolerance
        end      : endpoint arrotondato alla tolerance
        geometry : LineString shapely — approssimazione per calcoli topologici
                   (mai usata per ricostruzione del file, che usa sempre source_ref)
    """
    source_ref:   Any
    layer:        str
    start:        Tuple[float, float]
    end:          Tuple[float, float]
    geometry:     Optional['LineString'] = None

