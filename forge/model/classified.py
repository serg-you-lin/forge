from dataclasses import dataclass
from dataclasses import field
from typing import Any, Optional, Tuple
from abc import ABC, abstractmethod
from shapely.geometry import Polygon

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