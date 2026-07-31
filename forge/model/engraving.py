"""
model/engraving.py
------------------
Rappresenta un'incisione (engrave) rilevata da detect().

Può essere open (traccia aperta, es. linea/arco) o closed (contorno chiuso).
Per ora il campo `closed` è puramente semantico — in futuro potrà
guidare la scelta della geometria canonica.

Campi comuni a entrambi i casi:
    closed     : True se il percorso è chiuso (semantico)
    part_label : label del ForgePart a cui è assegnato
    source_ref : riferimento all'entità originale — opaco, usato dall'adapter
    length     : lunghezza del percorso in mm

Campi per open (closed=False):
    pts        : lista di vertici (x, y) nell'ordine della traccia
    geometry   : LineString shapely — None se non ancora calcolata

Campi per closed (closed=True):
    polygon    : Polygon shapely — None se non ancora calcolato
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional, Tuple

from shapely.geometry import LineString, Polygon


@dataclass
class Engraving:
    """
    Incisione rilevata da detect() — open o closed.

    Open  → pts + geometry (LineString)
    Closed → polygon (Polygon)

    In entrambi i casi: length, part_label, source_ref, closed.
    """
    closed:     bool
    length:     float
    part_label: str                           = ""
    source_ref: Optional[Any]                 = None

    # open
    pts:        List[Tuple[float, float]]     = field(default_factory=list)
    geometry:   Optional[LineString]          = None

    # closed
    polygon:    Optional[Polygon]             = None

    def source_layer(self) -> str: 
        """ Restituisce il layer dell'entità sorgente, se disponibile. 
        Per entità DXF ezdxf: self.source_ref.dxf.layer 
        Non fallisce se la sorgente non è una entità DXF. """ 
        try: 
            return self.source_ref.dxf.layer 
        except Exception: 
            return ""

    def to_dict(self) -> dict:
        d: dict = {
            "closed":     self.closed,
            "length":     round(self.length, 4),
            "part_label": self.part_label,
        }
        layer = self.source_layer() 
        if layer: 
            d["origin"] = layer
            
        if not self.closed and self.pts:
            d["start"] = self.pts[0]
            d["end"]   = self.pts[-1]
        return d