"""
tools/model/classified.py

DTO di risultato: una entità classificata da `tools/detect()` senza una classe
di dominio dedicata (marking, work_type custom).

Spostato da model/classified.py (branch refactor/detect-overlay): la ragione
per cui era rimasto in model/ (`ForgeResult.classified_entities` lo conteneva,
e far dipendere model/ da tools/ era vietato) non vale più — `result.py` ora
importa questo tipo solo sotto `TYPE_CHECKING` (`from __future__ import
annotations` rende l'annotazione una stringa pigra, zero import a runtime),
stesso trucco usato per `ForgeCluster.detected`.
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