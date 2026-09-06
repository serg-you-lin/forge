"""
model/document.py
-----------------
Il ForgeDocument — output di forge.load_dxf() e unico input di forge.heal().

load_dxf() non restituisce un modelspace ezdxf: restituisce questo oggetto di
dominio. Dopo load_dxf() il riferimento al documento ezdxf sorgente sparisce e
non viene più toccato fino a write().

    edges       : geometria parsata (Edge puri) — input per heal()
    annotations : testi, quote, leader — dati puri, input per write()
    source_meta : header rilevanti del file sorgente ($INSUNITS, $MEASUREMENT, …)
    source_path : percorso del file aperto
    warnings    : diagnostica raccolta da load_dxf() sul file grezzo — audit,
                  INSERT non esplosi, entità con Z != 0 riportate sul piano,
                  duplicati rimossi. forge.validate(doc) le rilancia.

Nessun campo porta un riferimento a ezdxf: edges e annotations sono dati puri
prodotti dall'adapter, source_meta è un dizionario di primitivi.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List

from .annotation import Annotation

if TYPE_CHECKING:
    from ..core.topology.edge import Edge


@dataclass
class ForgeDocument:
    """
    Documento di dominio prodotto da load_dxf() / load_svg() / load_pdf().

    Contratto: heal(), detect() e write() lavorano solo su questo oggetto e sul
    ForgeResult che ne deriva — mai su entità ezdxf.
    """
    edges:       List["Edge"]        = field(default_factory=list)
    annotations: List[Annotation]    = field(default_factory=list)
    source_meta: Dict[str, Any]      = field(default_factory=dict)
    source_path: str                 = ""
    warnings:    List[str]           = field(default_factory=list)
