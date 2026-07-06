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
        entity   : entità ezdxf originale (LINE, ARC, SPLINE)
        layer    : layer DXF — cached per non rileggere entity.dxf.layer
        start    : endpoint arrotondato alla tolerance
        end      : endpoint arrotondato alla tolerance
        geometry : LineString shapely — approssimazione per calcoli topologici
                   (mai usata per ricostruzione del file, che usa sempre entity)
    """
    entity:   Any
    layer:    str
    start:    Tuple[float, float]
    end:      Tuple[float, float]
    geometry: Optional['LineString'] = None


@dataclass
class BendingLine:
    """
    Rappresenta una linea di piega estratta dal DXF.

    Attributi:
        entity      : entità ezdxf originale (LINE)
        geometry    : LineString shapely — la geometria canonica
        length      : lunghezza in mm
        layer       : layer DXF originale
        angle_deg   : angolo rispetto all'asse X (0–180°)
        part_label  : label del ForgePart a cui è assegnata
    """
    entity:     object
    geometry:   LineString
    length:     float
    layer:      str
    angle_deg:  float
    part_label: str = ""

    def to_dict(self) -> dict:
        """Serializzazione per part.custom['bending_lines']."""
        coords = list(self.geometry.coords)
        return {
            "start":      coords[0],
            "end":        coords[-1],
            "length":     round(self.length, 4),
            "angle_deg":  round(self.angle_deg, 4),
            "layer":      self.layer,
            "part_label": self.part_label,
        }