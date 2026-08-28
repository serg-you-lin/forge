"""
adapters/dxf/annotation_extractor.py
------------------------------------
Estrae le annotazioni di un modelspace DXF come list[Annotation].

È l'equivalente per testi e quote di quello che DxfAdapter.to_edges() è per la
geometria di taglio: l'unico punto in cui le entità di annotazione DXF vengono
lette e tradotte in dati di dominio puri. Dopo extract() il modelspace sorgente
non serve più.

Tipi gestiti: TEXT, MTEXT, DIMENSION, LEADER, MULTILEADER.
Non gestisce INSERT — si assume siano già stati esplosi da load_dxf().

TEXT / MTEXT → `Annotation` con `content` + posizione: `write` li riscrive come
un unico TEXT/MTEXT.

DIMENSION / LEADER / MULTILEADER non hanno una geometria "propria" nei campi
DXF: la loro immagine (linee di misura, direttrici, frecce, testo) sta in un
blocco anonimo che ezdxf sa espandere con `virtual_entities()`. La
appiattiamo QUI in primitive pure (segmenti + testi) e la conserviamo in
`data["strokes"] / data["fills"] / data["texts"]`, così `write` la
ri-materializza fedele all'originale invece di piazzare un numero a caso.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from ...model.document import Annotation
from ...io.text_utils import clean_mtext, handle_mleader
from .geometry_adapter import get_representative_point

ANNOTATION_TYPES = frozenset({"TEXT", "MTEXT", "DIMENSION", "LEADER", "MULTILEADER"})

# Tipi che portano l'immagine in un blocco anonimo, non nei campi DXF.
RENDERED_TYPES = frozenset({"DIMENSION", "LEADER", "MULTILEADER"})

# Errore massimo di corda per discretizzare archi/curve (mm).
_ARC_SAGITTA = 0.1


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

            if kind in RENDERED_TYPES:
                # position può essere None per un LEADER: la si ricava dalla
                # geometria appiattita.
                ann = _rendered_annotation(entity, position)
                if ann is not None:
                    annotations.append(ann)
                continue

            if position is None:
                continue

            content = _extract_content(entity)
            if not content:
                continue

            data = _extract_attribs(entity)
            data["content"] = content
            annotations.append(Annotation(kind=kind, position=position, data=data))
        return annotations


# ---------------------------------------------------------------------------
# TEXT / MTEXT — testo semplice
# ---------------------------------------------------------------------------

def _extract_content(entity) -> str:
    """Testo pulito dell'annotazione, stringa vuota se non ne ha."""
    t = entity.dxftype()
    if t == "TEXT":
        return (entity.dxf.get("text", "") or "").strip()
    if t == "MTEXT":
        return clean_mtext(entity.text)
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


# ---------------------------------------------------------------------------
# DIMENSION / LEADER / MULTILEADER — immagine appiattita in primitive pure
# ---------------------------------------------------------------------------

def _rendered_annotation(entity, position) -> Optional[Annotation]:
    """
    Appiattisce l'immagine di una quota/direttrice in segmenti + testi puri.

    Ripiega su `_dimension_text()` (solo valore misurato) se `virtual_entities()`
    non produce nulla — meglio un numero che il nulla.
    """
    strokes: List[List[Tuple[float, float]]] = []
    fills: List[List[Tuple[float, float]]] = []
    texts: List[dict] = []

    try:
        vents = list(_flatten_virtual(entity))
    except Exception:
        vents = []

    for v in vents:
        t = v.dxftype()
        if t == "LINE":
            strokes.append([_xy(v.dxf.start), _xy(v.dxf.end)])
        elif t == "ARC":
            pts = _arc_points(v)
            if len(pts) >= 2:
                strokes.append(pts)
        elif t == "CIRCLE":
            pts = _circle_points(v)
            if pts:
                fills.append(pts)
        elif t in ("LWPOLYLINE", "POLYLINE"):
            pts, closed = _polyline_points(v)
            if len(pts) >= 2:
                (fills if closed else strokes).append(pts)
        elif t in ("SOLID", "TRACE"):
            pts = _solid_points(v)
            if len(pts) >= 3:
                fills.append(pts)
        elif t in ("TEXT", "MTEXT"):
            item = _text_item(v)
            if item is not None:
                texts.append(item)

    if not strokes and not fills and not texts and entity.dxftype() == "DIMENSION":
        # Nessun blocco geometria (dim non pre-renderizzata): ricostruiamo
        # direttrici + linea di misura dai def-point. Meglio del numero solo.
        syn_strokes, syn_text = _synthesize_dimension(entity)
        strokes.extend(syn_strokes)
        if syn_text is not None:
            texts.append(syn_text)

    if not strokes and not fills and not texts:
        content = _dimension_text(entity) if entity.dxftype() == "DIMENSION" else ""
        if not content or position is None:
            return None
        data = {"layer": entity.dxf.get("layer", "0"), "content": content}
        return Annotation(kind=entity.dxftype(), position=position, data=data)

    if position is None:
        position = _bbox_center(strokes + fills + [[t["position"]] for t in texts])
        if position is None:
            return None

    return Annotation(
        kind=entity.dxftype(),
        position=position,
        data={
            "layer": entity.dxf.get("layer", "0"),
            "content": "",
            "strokes": strokes,
            "fills": fills,
            "texts": texts,
        },
    )


def _synthesize_dimension(entity):
    """
    Ricostruisce l'immagine di una DIMENSION lineare dai def-point, quando il
    blocco geometria manca. Ritorna (strokes, text_item | None).

    Solo per le quote lineari/allineate/ruotate (dimtype & 7 in {0, 1}); per
    radiali/diametrali/angolari lasciamo il fallback al solo valore.
    """
    import math

    try:
        dimtype = int(entity.dxf.get("dimtype", 0)) & 7
    except (TypeError, ValueError):
        dimtype = 0
    if dimtype not in (0, 1):
        return [], None

    dxf = entity.dxf
    p  = dxf.get("defpoint")   # punto sulla linea di misura
    e1 = dxf.get("defpoint2")  # origine 1ª direttrice
    e2 = dxf.get("defpoint3")  # origine 2ª direttrice
    if p is None or e1 is None or e2 is None:
        return [], None

    p  = (float(p[0]), float(p[1]))
    e1 = (float(e1[0]), float(e1[1]))
    e2 = (float(e2[0]), float(e2[1]))

    ang = dxf.get("angle")
    if ang is None:
        # allineata: direzione lungo i due punti origine
        dx, dy = e2[0] - e1[0], e2[1] - e1[1]
        norm = math.hypot(dx, dy) or 1.0
        d = (dx / norm, dy / norm)
    else:
        a = math.radians(float(ang))
        d = (math.cos(a), math.sin(a))

    def _proj(q):
        t = (q[0] - p[0]) * d[0] + (q[1] - p[1]) * d[1]
        return (p[0] + t * d[0], p[1] + t * d[1])

    f1, f2 = _proj(e1), _proj(e2)
    strokes = [[e1, f1], [e2, f2], [f1, f2]]

    text_item = None
    tm = dxf.get("text_midpoint")
    content = _dimension_text(entity)
    if content:
        pos = (float(tm[0]), float(tm[1])) if tm is not None else _bbox_center(strokes)
        text_item = {"content": content, "position": pos, "height": 2.5, "rotation": 0.0}

    return strokes, text_item


def _bbox_center(polylines) -> Optional[Tuple[float, float]]:
    xs = [p[0] for pl in polylines for p in pl]
    ys = [p[1] for pl in polylines for p in pl]
    if not xs:
        return None
    return ((min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0)


def _flatten_virtual(entity):
    """Espande `virtual_entities()` ricorsivamente sugli INSERT (frecce a blocco)."""
    for v in entity.virtual_entities():
        if v.dxftype() == "INSERT":
            yield from _flatten_virtual(v)
        else:
            yield v


def _text_item(v) -> Optional[dict]:
    t = v.dxftype()
    content = clean_mtext(v.text) if t == "MTEXT" else (v.dxf.get("text", "") or "").strip()
    if not content:
        return None
    ins = v.dxf.get("insert") or v.dxf.get("align_point")
    if ins is None:
        return None
    if t == "MTEXT":
        height = _f(v.dxf.get("char_height", 2.5))
    else:
        height = _f(v.dxf.get("height", 2.5))
    return {
        "content": content,
        "position": (float(ins[0]), float(ins[1])),
        "height": height or 2.5,
        "rotation": _f(v.dxf.get("rotation", 0.0)) or 0.0,
    }


def _xy(p) -> Tuple[float, float]:
    return (float(p[0]), float(p[1]))


def _arc_points(arc) -> List[Tuple[float, float]]:
    try:
        return [(float(p[0]), float(p[1])) for p in arc.flattening(_ARC_SAGITTA)]
    except Exception:
        return []


def _circle_points(circle) -> List[Tuple[float, float]]:
    try:
        return [(float(p[0]), float(p[1])) for p in circle.flattening(_ARC_SAGITTA)]
    except Exception:
        return []


def _polyline_points(pl) -> Tuple[List[Tuple[float, float]], bool]:
    t = pl.dxftype()
    try:
        if t == "LWPOLYLINE":
            pts = [(float(x), float(y)) for x, y, *_ in pl.get_points("xyb")]
            return pts, bool(pl.closed)
        pts = [(float(p[0]), float(p[1])) for p in pl.points()]
        return pts, bool(pl.is_closed)
    except Exception:
        return [], False


def _solid_points(solid) -> List[Tuple[float, float]]:
    """SOLID/TRACE: 4 vertici in ordine 'a farfalla' → poligono convesso."""
    vs = []
    for name in ("vtx0", "vtx1", "vtx3", "vtx2"):  # 3<->2 per de-farfallare
        p = solid.dxf.get(name)
        if p is not None:
            vs.append((float(p[0]), float(p[1])))
    # scarta il 4° vertice se coincide col 3° (SOLID triangolare)
    if len(vs) == 4 and vs[2] == vs[3]:
        vs = vs[:3]
    return vs


def _dimension_text(entity) -> str:
    """
    Fallback: solo il valore della quota, quando l'immagine non è espandibile.

    Regole DXF sul campo `text`:
      - "" / "<>" → misura calcolata (`get_measurement()`)
      - " "       → testo soppresso → nessun testo
      - "...<>"   → prefisso/suffisso attorno alla misura
      - altro     → override esplicito
    """
    raw = entity.dxf.get("text", "") or ""
    if raw == " ":
        return ""
    measure = _dimension_measurement(entity)
    if raw and raw != "<>":
        return raw.replace("<>", measure) if "<>" in raw else raw
    return measure


def _dimension_measurement(entity) -> str:
    try:
        m = entity.get_measurement()
    except Exception:
        return ""
    if isinstance(m, (int, float)):
        return f"{m:.2f}".rstrip("0").rstrip(".")
    return ""


def _f(value) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
