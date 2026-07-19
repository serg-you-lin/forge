from dataclasses import dataclass, field
from typing import Any, List, Set, Tuple, Optional
from shapely.geometry import Polygon
from .hole import Hole
from .edge import BendingLine

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
    role:         str     = ""
    source_ref:   Any = None
    area:         float   = field(init=False)
    bbox:         Tuple[float, float, float, float] = field(init=False)
    origin: str     = ""
    vs_id: Optional[int] = None

    def __post_init__(self):
        self.area = self.polygon.area
        self.bbox = self.polygon.bounds


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
    bending_lines:  List[BendingLine] = field(default_factory=list)
    label:          str                = ""
    source_file:    str                = ""
    custom:         dict               = field(default_factory=dict)
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