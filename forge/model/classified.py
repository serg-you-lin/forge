"""
model/classified.py

DTO di risultato: una entità classificata da `tools/detect()` senza una classe
di dominio dedicata (marking, work_type custom). Vive in `model/` perché
`ForgeResult.classified_entities` la contiene — spostarla in `tools/`
significherebbe far dipendere `model/` da `tools/`.
"""
from dataclasses import dataclass
from dataclasses import field
from typing import Any, Optional, Tuple


@dataclass
class ClassifiedEntity:
    """
    Risultato della classificazione di una entità da detect().

    Prodotto da detect(), consumato da inject() e write().

    Campi:
        work_type  : tipo lavorazione — chiave di WORK_TYPE_TO_LAYER
        confidence : 1.0 da special_layers, < 1.0 da geometria o agente
        source     : "special_layers" | "geometric" | "agent"
        data       : dati estratti pronti per CAM — inject() li usa direttamente
    """       
    work_type:  str
    confidence: float
    source:     str
    data:       dict = field(default_factory=dict)
    polygon:    Any  = None
    representative_point: Optional[Tuple[float, float]] = None