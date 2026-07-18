from dataclasses import dataclass
from typing import Optional, Tuple, Any
from shapely.geometry import Polygon

# ---------------------------------------------------------------------------
# Tipi di foro — valori validi per Hole.hole_type
# ---------------------------------------------------------------------------

HOLE_TYPE_UNKNOWN      = "unknown"       # heal() non ha info sufficienti
HOLE_TYPE_PLAIN        = "plain"         # foro liscio standard
HOLE_TYPE_COUNTERSINK  = "countersink"   # svasatura (cerchio esterno + interno)
HOLE_TYPE_THREADED     = "threaded"      # foro filettato (arco ~270° concentrico)

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

    Analogia: il tecnico di radiologia (heal) vede la geometria e scrive
    un hint. Il medico (detect) firma la diagnosi ufficiale — hole_type.
    Se non chiami detect(), hole_type resta "unknown": nessuna diagnosi.

    Ciclo di vita:
        heal()   → crea Hole con hole_type=UNKNOWN, geometric_hint opzionale
        detect() → promuove hole_type al tipo definitivo leggendo l'hint
                   o i layer speciali, senza ricalcolare la geometria

    Campi:
        polygon         : poligono Shapely del foro (dal cerchio o dal contorno)
        diameter        : diametro del cerchio principale in mm
        center          : centro (x, y) in coordinate DXF
        hole_type       : tipo definitivo — assegnato da detect()
        geometric_hint  : hint prodotto da heal() — "" | "countersink" | "threaded"
                          Separato da hole_type: hint != diagnosi
        confidence      : 0.0 da heal(), > 0.0 da detect()
        source          : "" | "geometric" | "special_layers" | "agent"
        outer_diameter  : solo countersink — diametro del cerchio esterno (svasatura)
        entity          : CIRCLE ezdxf originale — non serializzato
        is_hole         : sempre True — per compatibilità con codice che itera inners
    """
    polygon:        Polygon
    diameter:       float
    center:         Tuple[float, float]

    hole_type:      str   = HOLE_TYPE_UNKNOWN
    geometric_hint: str   = ""
    confidence:     float = 0.0
    source:         str   = ""

    role:          str   = ""
    source_layer:   str   = ""
    source_ref:     Any   = None

    outer_diameter: Optional[float] = None   # solo countersink
    outer_source_ref: Any   = None
    is_hole:        bool            = True   # sempre True — compatibilità

    @property
    def area(self) -> float:
        return self.polygon.area

    @property
    def bbox(self) -> Tuple[float, float, float, float]:
        return self.polygon.bounds

    def to_dict(self) -> dict:
        """
        Serializzazione canonica — inject() e to_dict() di ForgePart la usano.

        Non serializza: entity (id() senza senso su disco), polygon (ridondante
        con center + diameter per i cerchi).
        """
        d = {
            "hole_type":  self.hole_type,
            "diameter":   round(self.diameter, 4),
            "center":     (round(self.center[0], 4), round(self.center[1], 4)),
            "role":       self.role,
            "confidence": round(self.confidence, 4),
            "source":     self.source,
        }
        if self.outer_diameter is not None:
            d["outer_diameter"] = round(self.outer_diameter, 4)
        return d