"""
adapters/dxf/annotation_extractor.py
------------------------------------
Estrae le annotazioni testuali di un modelspace DXF come list[Annotation].

È l'equivalente per i testi di quello che DxfAdapter.to_edges() è per la
geometria: l'unico punto in cui le entità di annotazione DXF vengono lette e
tradotte in dati di dominio puri. Dopo extract() il modelspace sorgente non
serve più.

Tipi gestiti: TEXT, MTEXT, DIMENSION, LEADER, MULTILEADER.
Non gestisce INSERT — si assume siano già stati esplosi da load_dxf().
"""

from __future__ import annotations

from typing import List, Optional

from ...model.document import Annotation
from ...io.text_utils import clean_mtext, handle_mleader
from .geometry_adapter import get_representative_point

ANNOTATION_TYPES = frozenset({"TEXT", "MTEXT", "DIMENSION", "LEADER", "MULTILEADER"})


class DxfAnnotationExtractor:
    """Traduce le entità di annotazione di un msp in list[Annotation]."""

    def __init__(self, msp):
        self.msp = msp

    def extract(self) -> List[Annotation]:
        annotations: List[Annotation] = []
        for entity in self.msp:
            kind = entity.dxftype()
            if kind not in ANNOTATION_TYPES:
                continue

            position = get_representative_point(entity)
            if position is None:
                continue

            content = _extract_content(entity)
            data = _extract_attribs(entity)
            data["content"] = content

            # Una DIMENSION senza testo di override resta valida (il testo è
            # calcolato dalla quota); un TEXT/MTEXT vuoto no.
            if not content and kind not in ("DIMENSION", "LEADER", "MULTILEADER"):
                continue

            annotations.append(Annotation(kind=kind, position=position, data=data))
        return annotations


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_content(entity) -> str:
    """Testo pulito dell'annotazione, stringa vuota se non ne ha."""
    t = entity.dxftype()
    if t == "TEXT":
        return (entity.dxf.get("text", "") or "").strip()
    if t == "MTEXT":
        return clean_mtext(entity.text)
    if t == "MULTILEADER":
        raw = handle_mleader(entity)
        return clean_mtext(raw) if raw else ""
    if t == "DIMENSION":
        txt = entity.dxf.get("text", "") or ""
        return txt if txt and txt != "<>" else ""
    return ""


def _extract_attribs(entity) -> dict:
    """
    Attributi minimi per riscrivere l'entità nel documento di output.
    Solo primitivi — nessun riferimento a ezdxf.
    """
    dxf = entity.dxf
    data: dict = {"layer": dxf.get("layer", "0")}

    t = entity.dxftype()
    if t == "TEXT":
        data["height"] = _f(dxf.get("height", 2.5))
        data["rotation"] = _f(dxf.get("rotation", 0.0))
        data["style"] = dxf.get("style", "Standard")
        data["halign"] = int(dxf.get("halign", 0) or 0)
        data["valign"] = int(dxf.get("valign", 0) or 0)
    elif t == "MTEXT":
        data["height"] = _f(dxf.get("char_height", 2.5))
        data["rotation"] = _f(dxf.get("rotation", 0.0))
        data["style"] = dxf.get("style", "Standard")
        data["width"] = _f(dxf.get("width", 0.0))
        data["attachment_point"] = int(dxf.get("attachment_point", 1) or 1)

    return data


def _f(value) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
