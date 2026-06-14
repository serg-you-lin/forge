"""
models.py
---------
Strutture dati condivise di dxf-forge.

Questi oggetti sono il "linguaggio comune" tra healer, detector,
validator, exporter, injector.
Nessuno di questi moduli dipende dagli altri — dipendono tutti da models.py.

"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Any, Set
from abc import ABC, abstractmethod
from shapely.geometry import Polygon, LineString
import math


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

# Hint geometrici che heal() può produrre — sottoinsieme di VALID_HOLE_TYPES
# senza "unknown" e "plain" (quelli non sono hint, sono stati definitivi)
VALID_GEOMETRIC_HINTS = {"countersink", "threaded"}


@dataclass
class ForgeContour:
    """
    Un singolo contorno geometrico: esterno o contorno interno NON foro.

    I fori usano la classe Hole — ForgeContour è per contorni strutturali
    (profili interni complessi, tasche, ecc.) che non sono fori circolari.

    Campi:
        entity : entità ezdxf originale — riferimento in memoria, può essere None.
                 Usato da detect() per accedere alla geometria ezdxf senza
                 rileggere il msp. Non serializzato: id() non ha senso su disco.
    """
    polygon:      Polygon
    is_inner:     bool    = False
    layer:        str     = ""
    is_hole:      bool    = False   # sempre False su ForgeContour — i fori usano Hole
    entity:       Any     = None
    area:         float   = field(init=False)
    bbox:         Tuple[float, float, float, float] = field(init=False)
    source_layer: str     = ""
    vs_id: Optional[int] = None

    def __post_init__(self):
        self.area = self.polygon.area
        self.bbox = self.polygon.bounds


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

    layer:          str   = ""
    source_layer:   str   = ""
    entity:         Any   = None   # CIRCLE ezdxf — non serializzato

    outer_diameter: Optional[float] = None   # solo countersink
    outer_entity:   Any             = None   # CIRCLE ezdxf del cerchio esterno — solo countersink, non serializzato
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
            "layer":      self.layer,
            "confidence": round(self.confidence, 4),
            "source":     self.source,
        }
        if self.outer_diameter is not None:
            d["outer_diameter"] = round(self.outer_diameter, 4)
        return d


@dataclass
class GeometryHints:
    """
    Indizi geometrici prodotti da detect() per ogni ForgePart.

    Con l'introduzione di Hole, countersink_ids e threaded_hole_ids sono stati
    rimossi — quelle informazioni vivono direttamente su Hole.hole_type e
    Hole.geometric_hint. GeometryHints conserva solo bend_line_ids perché
    le linee di piega non hanno ancora una classe dedicata.

    Campi:
        bend_line_ids : id() delle entità LINE classificate come linee di piega
    """
    bend_line_ids: Set[int] = field(default_factory=set)


@dataclass
class ForgePart:
    """
    Un pezzo completo: contorno esterno + fori + contorni interni + metadati.

    È l'unità di lavoro di dxf-forge.

    Campi:
        outer          : contorno esterno
        holes          : fori — istanze di Hole, gestite da heal() e detect()
        inners         : contorni interni NON foro (tasche complesse, ecc.)
        label          : nome del file o del layer
        source_file    : percorso del DXF originale
        custom         : metadati lavorazione — scritti da detect() e inject()
        geometry_hints : indizi semantici scritti da detect(), letti da inject()
                         e snapmark.
        entity_ids     : id() di tutte le entità ezdxf appartenenti a questo part,
                         popolato da heal() durante la costruzione della gerarchia.
                         Dopo write(), viene aggiornato con gli id() delle LWPOLYLINE
                         materializzate dai VirtualShape (swap VS → LWPOLYLINE).
                         Usato da split() per copiare le entità corrette senza
                         ricalcolare l'appartenenza geometrica.
                         Non serializzato: id() non ha senso su disco.
    """
    outer:          ForgeContour
    holes:          List[Hole]         = field(default_factory=list)
    inners:         List[ForgeContour] = field(default_factory=list)
    label:          str                = ""
    source_file:    str                = ""
    custom:         dict               = field(default_factory=dict)
    geometry_hints: GeometryHints      = field(default_factory=GeometryHints)
    entity_ids:     Set[int]           = field(default_factory=set)

    @property
    def polygon_with_holes(self) -> Polygon:
        """Restituisce il Polygon Shapely completo con i fori."""
        all_inners = (
            [h.polygon for h in self.holes]
            + [i.polygon for i in self.inners]
        )
        if not all_inners:
            return self.outer.polygon
        return Polygon(
            self.outer.polygon.exterior.coords,
            [p.exterior.coords for p in all_inners],
        )

    @property
    def bbox(self):
        return self.outer.bbox

    @property
    def area(self) -> float:
        """Area netta: outer meno fori meno contorni interni."""
        return (
            self.outer.area
            - sum(h.area for h in self.holes)
            - sum(i.area for i in self.inners)
        )

    def to_dict(self) -> dict:
        """
        Esporta il pezzo come dizionario — fonte di verità per JSON, XDATA, MES, ERP.

        GeometryHints e entity_ids non sono serializzati: sono id() in memoria.
        """
        return {
            "label":                self.label,
            "source_file":          self.source_file,
            "area":                 round(self.area, 4),
            "holes_count":          len(self.holes),
            "inner_contours_count": len(self.inners),
            "bbox": {
                "minx": round(self.bbox[0], 4),
                "miny": round(self.bbox[1], 4),
                "maxx": round(self.bbox[2], 4),
                "maxy": round(self.bbox[3], 4),
            },
            "outer":  list(self.outer.polygon.exterior.coords),
            "holes":  [h.to_dict() for h in self.holes],
            "inners": [list(i.polygon.exterior.coords) for i in self.inners],
            "custom": self.custom,
        }


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


@dataclass
class ClassifiedEntity:
    """
    Risultato della classificazione di una entità da detect().

    Prodotto da detect(), consumato da inject() e write().

    Campi:
        entity     : entità ezdxf originale
        work_type  : tipo lavorazione — chiave di WORK_TYPE_TO_LAYER
        confidence : 1.0 da special_layers, < 1.0 da geometria o agente
        source     : "special_layers" | "geometric" | "agent"
        data       : dati estratti pronti per CAM — inject() li usa direttamente
    """
    entity:     Any
    work_type:  str
    confidence: float
    source:     str
    data:       dict = field(default_factory=dict)
    polygon:    Any  = None  # Polygon shapely — solo per VirtualShape (entity=None)


class BaseInterpreter(ABC):
    """
    Interfaccia che ogni interpreter deve implementare.

    detect() non sa quale interpreter sta usando — chiama questo metodo e basta.
    """
    @abstractmethod
    def classify(
        self,
        entities:    list,
        outer_poly:  Polygon,
        inner_polys: list,
        msp,
        hints:       dict = None,
    ) -> list:  # list[ClassifiedEntity]
        ...


@dataclass
class ForgeResult:
    """
    Risultato completo di una sessione forge su un file DXF.

    Contiene tutti i pezzi trovati + info di validazione.
    È quello che forge.heal() restituisce al chiamante.

    Campi:
        special_layers         : dict {nome_layer: tipo_lavorazione} passato a detect().
                                 Salvato qui da detect() — inject() e write()
                                 lo leggono senza che il chiamante lo ripassi.
                                 Non serializzato in to_dict(): è configurazione di sessione.
        _virtual_shapes        : lista di VirtualShape prodotti da heal() per i loop LINE/ARC.
                                 Stato di sessione — write() li materializza come LWPOLYLINE
                                 nel msp. Non serializzato.
        _entities_in_loops_ids : id() di LINE/ARC assorbite in loop — eliminate da write().
        _vs_to_part            : mappa id(VirtualShape) → ForgePart — usata da write()
                                 per fare lo swap id(VS) → id(LWPOLYLINE) in part.entity_ids.
                                 Non serializzato.
    """
    parts:               List[ForgePart]        = field(default_factory=list)
    source_file:         str                    = ""
    is_valid:            bool                   = True
    warnings:            List[str]              = field(default_factory=list)
    errors:              List[str]              = field(default_factory=list)
    trash_entities:      List[Any]              = field(default_factory=list)
    classified_entities: List[ClassifiedEntity] = field(default_factory=list)
    special_layers:      dict                   = field(default_factory=dict)
    _virtual_shapes:        List[Any]        = field(default_factory=list)
    _entities_in_loops_ids: Set[int]         = field(default_factory=set)
    _vs_to_part:            dict             = field(default_factory=dict)   # id(VS) → ForgePart
    _suppressed_vs_ids: set = field(default_factory=set)

    @property
    def part_count(self) -> int:
        return len(self.parts)

    @property
    def has_issues(self) -> bool:
        return bool(self.warnings or self.errors)

    def to_dict(self) -> dict:
        """Esporta tutto come dizionario — pronto per JSON."""
        return {
            "source_file": self.source_file,
            "is_valid":    self.is_valid,
            "part_count":  self.part_count,
            "warnings":    self.warnings,
            "errors":      self.errors,
            "parts":       [p.to_dict() for p in self.parts],
        }