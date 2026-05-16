# """
# models.py
# ---------
# Strutture dati condivise di dxf-forge.

# Questi oggetti sono il "linguaggio comune" tra healer, splitter,
# validator, exporter, injector.
# Nessuno di questi moduli dipende dagli altri — dipendono tutti da models.py.

# """

# from dataclasses import dataclass, field
# from typing import List, Optional, Tuple, Any, Set
# from abc import ABC, abstractmethod
# from shapely.geometry import Polygon, LineString
# import math


# @dataclass
# class ForgeContour:
#     """
#     Un singolo contorno geometrico: esterno o foro.

#     Contiene il poligono Shapely (che è il dato canonico)
#     e i metadati derivati utili per nester, MES, ERP.
#     """
#     polygon:  Polygon
#     is_inner: bool  = False
#     layer:    str   = ""       # layer DXF di provenienza
#     is_hole:  bool  = False    # True solo per CIRCLE classificati come fori
#     area:     float = field(init=False)
#     bbox:     Tuple[float, float, float, float] = field(init=False)  # (minx, miny, maxx, maxy)

#     def __post_init__(self):
#         self.area = self.polygon.area
#         self.bbox = self.polygon.bounds


# @dataclass
# class GeometryHints:
#     """
#     Indizi geometrici prodotti da heal() e conservati per tutta la vita del msp.

#     heal() li popola perché è l'unico che ha fatto il containment check e sa
#     dove si trovano queste entità rispetto alla geometria strutturale.
#     classify() li consuma per scrivere i metadati su part.custom.
#     snapmark.execute() li usa per posizionare le marcature senza rileggere il msp.

#     Analogia: è il verbale del sopralluogo — l'operaio che ha visitato il
#     cantiere lo scrive una volta sola, poi tutti gli altri lo leggono.

#     Campi:
#         countersink_ids   : id() delle entità CIRCLE classificate come svasature
#         threaded_hole_ids : id() delle entità CIRCLE con filettatura rilevata
#         bend_line_ids     : id() delle entità LINE su layer bending
#                             (da special_layers — geometria pura, niente semantica)
#     """
#     countersink_ids:   Set[int] = field(default_factory=set)
#     threaded_hole_ids: Set[int] = field(default_factory=set)
#     bend_line_ids:     Set[int] = field(default_factory=set)


# @dataclass
# class ForgePart:
#     """
#     Un pezzo completo: contorno esterno + fori + metadati.

#     È l'unità di lavoro di dxf-forge.
#     Il nester consuma ForgePart.
#     Snapmark riceve ForgePart per sapere dove mettere la marcatura.

#     Campi:
#         outer          : contorno esterno
#         inners         : fori e contorni interni
#         label          : nome del file o del layer
#         source_file    : percorso del DXF originale
#         custom         : metadati liberi — scritti da classify() e inject()
#         geometry_hints : indizi geometrici scritti da heal(), letti da classify()
#                          e snapmark. Conservati per tutta la vita del msp in memoria.
#     """
#     outer:          ForgeContour
#     inners:         List[ForgeContour] = field(default_factory=list)
#     label:          str               = ""
#     source_file:    str               = ""
#     custom:         dict              = field(default_factory=dict)
#     geometry_hints: GeometryHints     = field(default_factory=GeometryHints)

#     @property
#     def polygon_with_holes(self) -> Polygon:
#         """Restituisce il Polygon Shapely completo con i fori."""
#         if not self.inners:
#             return self.outer.polygon
#         return Polygon(
#             self.outer.polygon.exterior.coords,
#             [h.polygon.exterior.coords for h in self.inners],
#         )

#     @property
#     def bbox(self):
#         return self.outer.bbox

#     @property
#     def area(self):
#         """Area netta: outer meno i fori."""
#         return self.outer.area - sum(h.area for h in self.inners)

#     def to_dict(self) -> dict:
#         """
#         Esporta il pezzo come dizionario — fonte di verità per JSON, XDATA, MES, ERP.

#         Struttura canonica — tutti i moduli usano questa, non riscrivono la logica.
#         GeometryHints non è serializzato: sono id() in memoria, non hanno senso su disco.
#         """
#         return {
#             "label":                self.label,
#             "source_file":          self.source_file,
#             "area":                 round(self.area, 4),
#             "holes_count":          len([i for i in self.inners if i.is_hole]),
#             "inner_contours_count": len([i for i in self.inners if not i.is_hole]),
#             "bbox": {
#                 "minx": round(self.bbox[0], 4),
#                 "miny": round(self.bbox[1], 4),
#                 "maxx": round(self.bbox[2], 4),
#                 "maxy": round(self.bbox[3], 4),
#             },
#             "outer":  list(self.outer.polygon.exterior.coords),
#             "inners": [list(h.polygon.exterior.coords) for h in self.inners],
#             "custom": self.custom,
#         }


# @dataclass
# class BendingLine:
#     """
#     Rappresenta una linea di piega estratta dal DXF.

#     Analogia: è come un righello posizionato sul pezzo —
#     ha una posizione, una lunghezza, un angolo, e puoi
#     decidere di usarne solo le estremità (trim).

#     Attributi:
#         entity      : entità ezdxf originale (LINE)
#         geometry    : LineString shapely — la geometria canonica
#         length      : lunghezza in mm
#         layer       : layer DXF originale
#         angle_deg   : angolo rispetto all'asse X (0–180°)
#         part_label  : label del ForgePart a cui è assegnata
#     """
#     entity:     object
#     geometry:   LineString
#     length:     float
#     layer:      str
#     angle_deg:  float
#     part_label: str = ""

#     def trim(self, margin: float) -> List[LineString]:
#         """
#         Restituisce le due estremità della BL, ciascuna lunga `margin` mm.
#         Il segmento centrale viene scartato.

#         Analogia: prendi la striscia adesiva da 100mm, tieni solo
#         i 25mm iniziali e i 25mm finali, butti il centro da 50mm.

#         Args:
#             margin: lunghezza da tenere per ogni estremità (mm)

#         Returns:
#             [self.geometry]          se margin * 2 >= length
#             [start_seg, end_seg]     nel caso normale

#         Raises:
#             ValueError: se margin <= 0
#         """
#         if margin <= 0:
#             raise ValueError(f"margin deve essere > 0, ricevuto {margin}")
#         if margin * 2 >= self.length:
#             return [self.geometry]

#         total     = self.length
#         start_seg = LineString([
#             self.geometry.interpolate(0.0),
#             self.geometry.interpolate(margin),
#         ])
#         end_seg = LineString([
#             self.geometry.interpolate(total - margin),
#             self.geometry.interpolate(total),
#         ])
#         return [start_seg, end_seg]

#     def to_dict(self) -> dict:
#         """Serializzazione per part.custom['bending_lines_data']."""
#         coords = list(self.geometry.coords)
#         return {
#             "start":      coords[0],
#             "end":        coords[-1],
#             "length":     round(self.length, 4),
#             "angle_deg":  round(self.angle_deg, 4),
#             "layer":      self.layer,
#             "part_label": self.part_label,
#         }


# def bending_line_from_entity(entity, part_label: str = "") -> "BendingLine":
#     """
#     Factory: LINE ezdxf → BendingLine.
#     Calcola geometria, lunghezza e angolo automaticamente.
#     """
#     s      = entity.dxf.start
#     e      = entity.dxf.end
#     geom   = LineString([(s.x, s.y), (e.x, e.y)])
#     length = geom.length
#     dx     = e.x - s.x
#     dy     = e.y - s.y
#     angle  = math.degrees(math.atan2(dy, dx)) % 180.0  # 0–180°, direzione non conta

#     return BendingLine(
#         entity=entity,
#         geometry=geom,
#         length=length,
#         layer=entity.dxf.layer if entity.dxf.hasattr("layer") else "",
#         angle_deg=angle,
#         part_label=part_label,
#     )


# @dataclass
# class ClassifiedEntity:
#     """
#     Risultato della classificazione di una entità in Trash.
#     Prodotto dall'interpreter, consumato da inject() e da _apply_to_msp().
#     """
#     entity:    Any
#     work_type: str    # "bending", "countersink", ... stringa libera
#     confidence: float  # 0.0 - 1.0
#     source:    str    # "fuzzy", "geometric", "agent"


# class BaseInterpreter(ABC):
#     """
#     Interfaccia che ogni interpreter deve implementare.

#     classify() in workflow/classifier.py non sa quale interpreter sta usando
#     — chiama questo metodo e basta.
#     L'agente futuro implementa questa stessa interfaccia.
#     """
#     @abstractmethod
#     def classify(
#         self,
#         entities:    list,          # entità in Trash
#         outer_poly:  Polygon,       # contesto geometrico dell'outer
#         inner_polys: list,          # fori e contorni interni già classificati
#         msp,                        # accesso completo al modelspace se serve
#         hints:       dict = None,   # GeometryHints.* come dict per l'interpreter
#     ) -> list:                      # list[ClassifiedEntity]
#         ...


# @dataclass
# class ForgeResult:
#     """
#     Risultato completo di una sessione forge su un file DXF.

#     Contiene tutti i pezzi trovati + info di validazione.
#     È quello che forge.heal() restituisce al chiamante.
#     """
#     parts:                List[ForgePart]        = field(default_factory=list)
#     source_file:          str                    = ""
#     is_valid:             bool                   = True
#     warnings:             List[str]              = field(default_factory=list)
#     errors:               List[str]              = field(default_factory=list)
#     trash_entities:       List[Any]              = field(default_factory=list)
#     classified_entities:  List[ClassifiedEntity] = field(default_factory=list)

#     @property
#     def part_count(self) -> int:
#         return len(self.parts)

#     @property
#     def has_issues(self) -> bool:
#         return bool(self.warnings or self.errors)

#     def to_dict(self) -> dict:
#         """Esporta tutto come dizionario — pronto per JSON."""
#         return {
#             "source_file": self.source_file,
#             "is_valid":    self.is_valid,
#             "part_count":  self.part_count,
#             "warnings":    self.warnings,
#             "errors":      self.errors,
#             "parts":       [p.to_dict() for p in self.parts],
#         }



"""
models.py
---------
Strutture dati condivise di dxf-forge.

Questi oggetti sono il "linguaggio comune" tra healer, splitter,
validator, exporter, injector.
Nessuno di questi moduli dipende dagli altri — dipendono tutti da models.py.

"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Any, Set
from abc import ABC, abstractmethod
from shapely.geometry import Polygon, LineString
import math


@dataclass
class ForgeContour:
    """
    Un singolo contorno geometrico: esterno o foro.

    Contiene il poligono Shapely (che è il dato canonico)
    e i metadati derivati utili per nester, MES, ERP.
    """
    polygon:  Polygon
    is_inner: bool  = False
    layer:    str   = ""       # layer DXF di provenienza
    is_hole:  bool  = False    # True solo per CIRCLE classificati come fori
    area:     float = field(init=False)
    bbox:     Tuple[float, float, float, float] = field(init=False)  # (minx, miny, maxx, maxy)

    def __post_init__(self):
        self.area = self.polygon.area
        self.bbox = self.polygon.bounds


@dataclass
class GeometryHints:
    """
    Indizi geometrici prodotti da heal() e conservati per tutta la vita del msp.

    heal() li popola perché è l'unico che ha fatto il containment check e sa
    dove si trovano queste entità rispetto alla geometria strutturale.
    classify() li consuma per scrivere i metadati su part.custom.
    snapmark.execute() li usa per posizionare le marcature senza rileggere il msp.

    Analogia: è il verbale del sopralluogo — l'operaio che ha visitato il
    cantiere lo scrive una volta sola, poi tutti gli altri lo leggono.

    Campi:
        countersink_ids   : id() delle entità CIRCLE classificate come svasature
        threaded_hole_ids : id() delle entità CIRCLE con filettatura rilevata
        bend_line_ids     : id() delle entità LINE su layer bending
                            (da special_layers — geometria pura, niente semantica)
    """
    countersink_ids:   Set[int] = field(default_factory=set)
    threaded_hole_ids: Set[int] = field(default_factory=set)
    bend_line_ids:     Set[int] = field(default_factory=set)


@dataclass
class ForgePart:
    """
    Un pezzo completo: contorno esterno + fori + metadati.

    È l'unità di lavoro di dxf-forge.
    Il nester consuma ForgePart.
    Snapmark riceve ForgePart per sapere dove mettere la marcatura.

    Campi:
        outer          : contorno esterno
        inners         : fori e contorni interni
        label          : nome del file o del layer
        source_file    : percorso del DXF originale
        custom         : metadati liberi — scritti da classify() e inject()
        geometry_hints : indizi geometrici scritti da heal(), letti da classify()
                         e snapmark. Conservati per tutta la vita del msp in memoria.
    """
    outer:          ForgeContour
    inners:         List[ForgeContour] = field(default_factory=list)
    label:          str               = ""
    source_file:    str               = ""
    custom:         dict              = field(default_factory=dict)
    geometry_hints: GeometryHints     = field(default_factory=GeometryHints)

    @property
    def polygon_with_holes(self) -> Polygon:
        """Restituisce il Polygon Shapely completo con i fori."""
        if not self.inners:
            return self.outer.polygon
        return Polygon(
            self.outer.polygon.exterior.coords,
            [h.polygon.exterior.coords for h in self.inners],
        )

    @property
    def bbox(self):
        return self.outer.bbox

    @property
    def area(self):
        """Area netta: outer meno i fori."""
        return self.outer.area - sum(h.area for h in self.inners)

    def to_dict(self) -> dict:
        """
        Esporta il pezzo come dizionario — fonte di verità per JSON, XDATA, MES, ERP.

        Struttura canonica — tutti i moduli usano questa, non riscrivono la logica.
        GeometryHints non è serializzato: sono id() in memoria, non hanno senso su disco.
        """
        return {
            "label":                self.label,
            "source_file":          self.source_file,
            "area":                 round(self.area, 4),
            "holes_count":          len([i for i in self.inners if i.is_hole]),
            "inner_contours_count": len([i for i in self.inners if not i.is_hole]),
            "bbox": {
                "minx": round(self.bbox[0], 4),
                "miny": round(self.bbox[1], 4),
                "maxx": round(self.bbox[2], 4),
                "maxy": round(self.bbox[3], 4),
            },
            "outer":  list(self.outer.polygon.exterior.coords),
            "inners": [list(h.polygon.exterior.coords) for h in self.inners],
            "custom": self.custom,
        }


@dataclass
class BendingLine:
    """
    Rappresenta una linea di piega estratta dal DXF.

    Analogia: è come un righello posizionato sul pezzo —
    ha una posizione, una lunghezza, un angolo, e puoi
    decidere di usarne solo le estremità (trim).

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

    def trim(self, margin: float) -> List[LineString]:
        """
        Restituisce le due estremità della BL, ciascuna lunga `margin` mm.
        Il segmento centrale viene scartato.

        Analogia: prendi la striscia adesiva da 100mm, tieni solo
        i 25mm iniziali e i 25mm finali, butti il centro da 50mm.

        Args:
            margin: lunghezza da tenere per ogni estremità (mm)

        Returns:
            [self.geometry]          se margin * 2 >= length
            [start_seg, end_seg]     nel caso normale

        Raises:
            ValueError: se margin <= 0
        """
        if margin <= 0:
            raise ValueError(f"margin deve essere > 0, ricevuto {margin}")
        if margin * 2 >= self.length:
            return [self.geometry]

        total     = self.length
        start_seg = LineString([
            self.geometry.interpolate(0.0),
            self.geometry.interpolate(margin),
        ])
        end_seg = LineString([
            self.geometry.interpolate(total - margin),
            self.geometry.interpolate(total),
        ])
        return [start_seg, end_seg]

    def to_dict(self) -> dict:
        """Serializzazione per part.custom['bending_lines_data']."""
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
    Risultato della classificazione di una entità in Trash.
    Prodotto dall'interpreter, consumato da inject() e da _apply_to_msp().
    """
    entity:    Any
    work_type: str    # "bending", "countersink", ... stringa libera
    confidence: float  # 0.0 - 1.0
    source:    str    # "fuzzy", "geometric", "agent"


class BaseInterpreter(ABC):
    """
    Interfaccia che ogni interpreter deve implementare.

    classify() in workflow/classifier.py non sa quale interpreter sta usando
    — chiama questo metodo e basta.
    L'agente futuro implementa questa stessa interfaccia.
    """
    @abstractmethod
    def classify(
        self,
        entities:    list,          # entità in Trash
        outer_poly:  Polygon,       # contesto geometrico dell'outer
        inner_polys: list,          # fori e contorni interni già classificati
        msp,                        # accesso completo al modelspace se serve
        hints:       dict = None,   # GeometryHints.* come dict per l'interpreter
    ) -> list:                      # list[ClassifiedEntity]
        ...


@dataclass
class ForgeResult:
    """
    Risultato completo di una sessione forge su un file DXF.

    Contiene tutti i pezzi trovati + info di validazione.
    È quello che forge.heal() restituisce al chiamante.

    Campi:
        special_layers : dict {nome_layer: tipo_lavorazione} passato a heal().
                         Salvato qui perché classify() ne ha bisogno — così
                         il chiamante non deve ripassarlo a mano.
                         Non viene serializzato in to_dict(): è configurazione
                         di sessione, non dato del pezzo.
    """
    parts:                List[ForgePart]        = field(default_factory=list)
    source_file:          str                    = ""
    is_valid:             bool                   = True
    warnings:             List[str]              = field(default_factory=list)
    errors:               List[str]              = field(default_factory=list)
    trash_entities:       List[Any]              = field(default_factory=list)
    classified_entities:  List[ClassifiedEntity] = field(default_factory=list)
    special_layers:       dict                   = field(default_factory=dict)

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