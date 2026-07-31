"""
model/shape.py

Due tipi distinti per due concetti distinti:
  - ClosedShape : contorno chiuso → ha un Polygon shapely
  - OpenShape   : traccia aperta  → ha pts e length

L'adapter popola `role` prima di consegnare le shape al core.
`origin` è deprecato — rimane temporaneamente per backward compat
durante il refactor, ma detect.py non deve leggerlo.
"""

from dataclasses import dataclass, field
from typing import Optional, Tuple, List, Any
from shapely.geometry import Polygon

from .role import ContourRole


@dataclass
class ClosedShape:
    """
    Forma chiusa pronta per la hierarchy.

    Prodotta dall'adapter (DXF, PDF, …) — il core la tratta come opaca
    rispetto al formato.

    Campi:
        polygon    : Polygon shapely — forma chiusa già calcolata
        role       : ruolo semantico — impostato dall'adapter prima del core
        source_ref : oggetto originale (entità ezdxf, DxfWriteContext, …)
                     — serve per traceability e writeback
        shape_type : categoria geometrica — "circle" | "polyline" |
                     "spline" | "ellipse" | "virtual"
        diameter   : diametro in unità documento — solo per cerchi, None altrimenti
        center     : centro (x, y) — solo per cerchi, None altrimenti
        is_virtual : True se generata dal core (non da un'entità sorgente)
        origin     : DEPRECATO — layer/classe di origine, usato solo dall'adapter
                     per traceability/debug via source_ref; detect.py non lo legge
    """
    polygon:    Polygon
    source_ref: Any
    role:       ContourRole                   = field(default=ContourRole.UNKNOWN)
    shape_type: str                           = ""
    is_virtual: bool                          = False
    diameter:   Optional[float]               = None
    center:     Optional[Tuple[float, float]] = None
    # DEPRECATO: tenuto per compat durante refactor — non aggiungere nuovi usi
    origin:     str                           = ""


@dataclass
class OpenShape:
    """
    Traccia aperta — tipicamente una bending line o un segmento non chiuso.

    Non ha Polygon: la gerarchia non la tocca, serve a detect() e inject().

    Campi:
        pts        : lista di vertici (x, y) nell'ordine della traccia
        length     : lunghezza totale in unità documento
        role       : ruolo semantico — impostato dall'adapter prima del core
        source_ref : oggetto originale — serve per traceability e writeback
        shape_type : categoria geometrica — "line" | "arc" | "polyline" | …
        origin     : DEPRECATO — layer/classe di origine; detect.py non lo legge
    """
    pts:        List[Tuple[float, float]]
    length:     float
    source_ref: Any
    role:       ContourRole                   = field(default=ContourRole.UNKNOWN)
    shape_type: str                           = ""
    diameter:   Optional[float]               = None
    center:     Optional[Tuple[float, float]] = None
    # DEPRECATO: tenuto per compat durante refactor — non aggiungere nuovi usi
    origin:     str                           = ""