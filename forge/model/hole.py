from dataclasses import dataclass
from typing import Optional, Tuple, Any
from shapely.geometry import Polygon

from .role import ContourRole

# ---------------------------------------------------------------------------
# Tipi di foro — valori validi per Hole.hole_type
# ---------------------------------------------------------------------------

HOLE_TYPE_UNKNOWN      = "unknown"
HOLE_TYPE_PLAIN        = "plain"
HOLE_TYPE_COUNTERSINK  = "countersink"
HOLE_TYPE_THREADED     = "threaded"

VALID_HOLE_TYPES = {
    HOLE_TYPE_UNKNOWN,
    HOLE_TYPE_PLAIN,
    HOLE_TYPE_COUNTERSINK,
    HOLE_TYPE_THREADED,
}


@dataclass
class Hole:
    """
    Un foro nel pezzo: entità di primo livello nel dominio forge.

    Ciclo di vita:
        heal()   → crea Hole con hole_type=UNKNOWN, geometric_hint opzionale
        detect() → promuove hole_type al tipo definitivo leggendo l'hint
                   o shape.role, senza ricalcolare la geometria

    Campi:
        polygon         : poligono Shapely del foro
        diameter        : diametro del cerchio principale in mm
        center          : centro (x, y) in coordinate documento
        hole_type       : tipo definitivo — assegnato da detect()
        geometric_hint  : hint prodotto da heal() — "" | "countersink" | "threaded"
        confidence      : 0.0 da heal(), > 0.0 da detect()
        source          : "" | "geometric" | "labeled" | "agent"
        role            : ruolo semantico — tradotto da DxfAdapter, letto da detect()
        source_ref      : entità originale opaca — per traceability e writeback
        outer_diameter  : solo countersink — diametro cerchio esterno
        outer_source_ref: entità esterna opaca — solo countersink
        is_hole         : sempre True — compatibilità con codice che itera inners
        origin          : DEPRECATO — layer DXF di provenienza; non leggere in detect()
    """
    polygon:        Polygon
    diameter:       float
    center:         Tuple[float, float]

    hole_type:      str          = HOLE_TYPE_UNKNOWN
    geometric_hint: str          = ""
    confidence:     float        = 0.0
    source:         str          = ""

    role:           ContourRole  = ContourRole.UNKNOWN
    source_ref:     Any          = None

    outer_diameter:   Optional[float] = None
    outer_source_ref: Any             = None
    is_hole:          bool            = True

    @property
    def area(self) -> float:
        return self.polygon.area

    @property
    def bbox(self) -> Tuple[float, float, float, float]:
        return self.polygon.bounds

    def source_layer(self) -> str:
        """
        Restituisce il layer DXF della sorgente, se disponibile.
        """
        try:
            return self.source_ref.dxf.layer
        except Exception:
            return ""
    
    def to_dict(self) -> dict:
        d = {
            "hole_type":  self.hole_type,
            "diameter":   round(self.diameter, 4),
            "center":     (round(self.center[0], 4), round(self.center[1], 4)),
            "role":       self.role,   # str mixin — serializza "hole" non <ContourRole.HOLE>
            "confidence": round(self.confidence, 4),
            "source":     self.source,
        }
        layer = self.source_layer()
        if layer:
            d["origin"] = layer
        if self.outer_diameter is not None:
            d["outer_diameter"] = round(self.outer_diameter, 4)
        return d