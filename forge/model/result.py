from dataclasses import dataclass
from dataclasses import field
from typing import List, Set, Any
from .part import ForgePart
from .classified import ClassifiedEntity


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