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

Nessun campo porta un riferimento a ezdxf: edges e annotations sono dati puri
prodotti dall'adapter, source_meta è un dizionario di primitivi.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Tuple

if TYPE_CHECKING:
    from ..adapters.bridge.edge import Edge


@dataclass
class Annotation:
    """
    Annotazione testuale estratta dalla sorgente (TEXT, MTEXT, DIMENSION, …).

    Non porta source_ref: `data` contiene tutto il necessario per ricreare
    l'entità nel documento di output.

        kind     : tipo entità sorgente — "TEXT" | "MTEXT" | "DIMENSION" | …
        position : punto rappresentativo (x, y) — per il containment check
        data     : contenuto e attributi necessari alla riscrittura
                   (testo, altezza, rotazione, allineamento, …)
    """
    kind:     str
    position: Tuple[float, float]
    data:     Dict[str, Any] = field(default_factory=dict)


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
