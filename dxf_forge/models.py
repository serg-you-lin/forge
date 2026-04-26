"""
models.py
---------
Strutture dati condivise di dxf-forge.

Questi oggetti sono il "linguaggio comune" tra healer, splitter,
validator, exporter e i consumatori esterni (nester, snapmark).
Nessuno di questi moduli dipende dagli altri — dipendono tutti da models.py.

Analogia: sono come i mattoni LEGO standard — healer li produce,
nester li consuma, e i mattoni non sanno nulla di chi li usa.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from shapely.geometry import Polygon


@dataclass
class ForgeContour:
    """
    Un singolo contorno geometrico: esterno o foro.
    
    Contiene il poligono Shapely (che è il dato canonico)
    e i metadati derivati utili per nester, MES, ERP.
    """
    polygon: Polygon
    is_inner: bool = False
    layer: str = ""                    # layer DXF di provenienza
    area: float = field(init=False)
    bbox: Tuple[float, float, float, float] = field(init=False)  # (minx, miny, maxx, maxy)

    def __post_init__(self):
        self.area = self.polygon.area
        self.bbox = self.polygon.bounds  # (minx, miny, maxx, maxy)


@dataclass
class ForgePart:
    """
    Un pezzo completo: contorno esterno + fori + metadati.
    
    È l'unità di lavoro di dxf-forge.
    Il nester consuma ForgePart.
    Snapmark riceve ForgePart per sapere dove mettere la marcatura.
    """
    outer: ForgeContour
    inners: List[ForgeContour] = field(default_factory=list)
    label: str = ""                    # nome del file o del layer
    source_file: str = ""              # percorso del DXF originale
    custom: dict = field(default_factory=dict)  # metadati liberi: material, thickness, fold_lines, ecc.

    @property
    def polygon_with_holes(self) -> Polygon:
        """Restituisce il Polygon Shapely completo con i fori."""
        if not self.inners:
            return self.outer.polygon
        return Polygon(
            self.outer.polygon.exterior.coords,
            [h.polygon.exterior.coords for h in self.inners]
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
        """
        return {
            "label":       self.label,
            "source_file": self.source_file,
            "area":        round(self.area, 4),
            "holes_count": len(self.inners),
            "bbox": {
                "minx": round(self.bbox[0], 4),
                "miny": round(self.bbox[1], 4),
                "maxx": round(self.bbox[2], 4),
                "maxy": round(self.bbox[3], 4),
            },
            "outer": list(self.outer.polygon.exterior.coords),
            "inners": [list(h.polygon.exterior.coords) for h in self.inners],
            "custom": self.custom,
        }


@dataclass
class ForgeResult:
    """
    Risultato completo di una sessione forge su un file DXF.
    
    Contiene tutti i pezzi trovati + info di validazione.
    È quello che forge.process() restituisce al chiamante.
    """
    parts: List[ForgePart] = field(default_factory=list)
    source_file: str = ""
    is_valid: bool = True
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

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
            "is_valid": self.is_valid,
            "part_count": self.part_count,
            "warnings": self.warnings,
            "errors": self.errors,
            "parts": [p.to_dict() for p in self.parts],
        }