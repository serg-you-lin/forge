"""
model/shape.py

Sostituisce model/shape_proxy.py.

Due tipi distinti per due concetti distinti:
  - ClosedShape : contorno chiuso → ha un Polygon shapely
  - OpenShape   : traccia aperta  → ha pts e length

Entrambi condividono i campi di provenienza e traceability.
"""

from dataclasses import dataclass, field
from typing import Optional, Tuple, List, Any
from shapely.geometry import Polygon


@dataclass
class ClosedShape:
    """
    Forma chiusa pronta per la hierarchy.

    Prodotta dall'adapter (DXF, PDF, …) — il core la tratta come opaca
    rispetto al formato.

    Campi:
        polygon    : Polygon shapely — forma chiusa già calcolata
        origin     : layer/classe di origine (stringa vuota se non disponibile)
        source_ref : oggetto originale (entità ezdxf, DxfWriteContext, …)
                     — serve per traceability e writeback
        shape_type : categoria geometrica — "circle" | "polyline" |
                     "spline" | "ellipse" | "virtual"
        diameter   : diametro in unità documento — solo per cerchi, None altrimenti
        center     : centro (x, y) — solo per cerchi, None altrimenti
        is_virtual : True se generata dal core (non da un'entità sorgente)
    """
    polygon:    Polygon
    origin:     str
    source_ref: Any
    shape_type: str                          = ""
    is_virtual: bool                         = False
    diameter:   Optional[float]              = None
    center:     Optional[Tuple[float, float]] = None


@dataclass
class OpenShape:
    """
    Traccia aperta — tipicamente una bending line o un segmento non chiuso.

    Non ha Polygon: la gerarchia non la tocca, serve a detect() e inject().

    Campi:
        pts        : lista di vertici (x, y) nell'ordine della traccia
        length     : lunghezza totale in unità documento
        origin     : layer/classe di origine (stringa vuota se non disponibile)
        source_ref : oggetto originale — serve per traceability e writeback
        shape_type : categoria geometrica — "line" | "arc" | "polyline" | …
    """
    pts:        List[Tuple[float, float]]
    length:     float
    origin:     str
    source_ref: Any
    shape_type: str                           = ""
    diameter:   Optional[float]               = None
    center:     Optional[Tuple[float, float]] = None