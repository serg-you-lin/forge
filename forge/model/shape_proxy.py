from dataclasses import dataclass
from typing import Optional, Tuple, Any
from shapely.geometry import Polygon


@dataclass
class ShapeProxy:
    """
    Rappresentazione agnostica di una forma chiusa pronta per la hierarchy.

    Prodotto dall'adapter (DXF, PDF, …) prima che il core la tocchi.
    Il core non sa nulla del formato sottostante — lavora solo su questo.

    Campi:
        polygon      : Polygon shapely — forma chiusa già calcolata
        source_layer : layer di origine (stringa vuota se non disponibile)
        shape_type   : categoria della forma — "circle", "polyline",
                       "spline", "virtual"
        diameter     : diametro in unità documento — solo per cerchi,
                       None altrimenti
        center       : centro (x, y) — solo per cerchi, None altrimenti
        source_ref   : oggetto originale (entità ezdxf, DxfWriteContext, …)
                       mai None — serve per traceability e writeback
    """
    polygon:      Polygon
    source_layer: str
    shape_type:   str                        # "circle" | "polyline" | "spline" | "virtual"
    source_ref:   Any
    diameter:     Optional[float]       = None
    center:       Optional[Tuple[float, float]] = None
