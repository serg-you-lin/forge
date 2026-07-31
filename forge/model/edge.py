"""
core/model/edge.py
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


@dataclass
@dataclass
class BendingLine:
    """
    Rappresenta una linea di piega.

    Attributi:
        geometry    : LineString shapely — la geometria canonica
        length      : lunghezza in mm
        angle_deg   : angolo rispetto all'asse X (0–180°)
        part_label  : label del ForgePart a cui è assegnata
        source_ref  : riferimento all'entità originale — usato per traceability
    """
    geometry:   LineString
    length:     float
    angle_deg:  float
    part_label: str = ""
    source_ref: Optional[Any] = None

    def source_layer(self) -> str:
        """
        Restituisce il layer dell'entità sorgente, se disponibile.
        """
        try:
            return self.source_ref.dxf.layer
        except Exception:
            return ""

    def to_dict(self) -> dict:
        coords = list(self.geometry.coords)

        d = {
            "start":      coords[0],
            "end":        coords[-1],
            "length":     round(self.length, 4),
            "angle_deg":  round(self.angle_deg, 4),
            "part_label": self.part_label,
        }

        layer = self.source_layer()
        if layer:
            d["origin"] = layer

        return d