"""
adapters/dxf/annotation_extractor.py
------------------------------------
Legge le entità di annotazione di un modelspace DXF e le traduce nel modello di
dominio tipato (``Note`` / ``Dimension`` / ``Leader`` di ``model/annotation.py``).

È l'equivalente per testi e quote di quello che ``DxfAdapter.to_edges()`` è per
la geometria di taglio: l'unico punto in cui le annotazioni DXF vengono lette.
Dopo ``extract()`` il modelspace sorgente non serve più.

Compito: solo conoscenza di formato — dove sta il testo, come si appiattisce il
blocco anonimo di una quota. NON decide cosa un'annotazione significhi per il
pezzo: quello è la fase ``interpret_annotations()`` della pipeline.

Tipi gestiti: TEXT, MTEXT, DIMENSION, LEADER, MULTILEADER.
Non gestisce INSERT — si assume siano già stati esplosi da load_dxf().

DIMENSION / LEADER / MULTILEADER non hanno una geometria "propria" nei campi
DXF: la loro immagine (linee di misura, direttrici, frecce, testo) sta in un
blocco anonimo espandibile con ``virtual_entities()``. La appiattiamo qui in
primitive pure e la conserviamo in ``annotation.rendered`` (RenderedGeometry),
così ``write()`` la ri-materializza fedele all'originale.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from ...model.annotation import (
    Annotation, Note, Dimension, Leader, RenderedGeometry, RenderedText,
)
from ...io.text_utils import clean_mtext

ANNOTATION_TYPES = frozenset({"TEXT", "MTEXT", "DIMENSION", "LEADER", "MULTILEADER"})

# Errore massimo di corda per discretizzare archi/curve (mm).
_ARC_SAGITTA = 0.1


class DxfAnnotationExtractor:
    """Traduce le entità di annotazione di un msp in list[Annotation]."""

    def __init__(self, msp):
        self.msp = msp

    def extract(self) -> List[Annotation]:
        out: List[Annotation] = []
        for entity in self.msp:
            if entity.dxftype() not in ANNOTATION_TYPES:
                continue
            ann = _to_annotation(entity)
            if ann is not None:
                out.append(ann)
        return out


def _to_annotation(entity) -> Optional[Annotation]:
    kind = entity.dxftype()
    layer = entity.dxf.get("layer", "0")
    pos = annotation_anchor(entity)

    if kind in ("TEXT", "MTEXT"):
        content = _extract_content(entity)
        if not content or pos is None:
            return None
        dxf = entity.dxf
        raw_h = dxf.get("char_height", 2.5) if kind == "MTEXT" else dxf.get("height", 2.5)
        return Note(
            position=pos,
            layer=layer,
            text=content,
            height=_f(raw_h) or 2.5,
            rotation=_f(dxf.get("rotation", 0.0)) or 0.0,
            source_kind=kind,
        )

    if kind == "DIMENSION":
        return _dimension_annotation(entity, pos, layer)

    if kind in ("LEADER", "MULTILEADER"):
        return _leader_annotation(entity, pos, layer, kind)

    return None


# ---------------------------------------------------------------------------
# Punto d'ancoraggio — dove `write` riposiziona il testo dell'annotazione
# ---------------------------------------------------------------------------

def annotation_anchor(entity) -> Optional[Tuple[float, float]]:
    """
    Punto d'ancoraggio XY di un'entità di annotazione.

    TEXT/MTEXT hanno il punto d'inserimento nei campi DXF; MULTILEADER e
    DIMENSION lo tengono in strutture annidate; LEADER non ce l'ha e ricade
    sul fallback (poi lo si ricava dalla geometria appiattita).
    Ritorna None se nessuna fonte è disponibile.
    """
    t = entity.dxftype()
    if t in ("TEXT", "MTEXT"):
        return (entity.dxf.insert.x, entity.dxf.insert.y)
    if t == "MULTILEADER":
        return _mleader_anchor(entity)
    if t == "DIMENSION":
        return _dimension_anchor(entity)
    return _fallback_anchor(entity)


def _mleader_anchor(entity) -> Optional[Tuple[float, float]]:
    """Primo vertice della direttrice di un MULTILEADER."""
    try:
        leader = entity.context.mleader
        if leader and leader.vertices:
            v = leader.vertices[0]
            return (v[0], v[1])
    except Exception:
        pass
    return None


def _dimension_anchor(entity) -> Optional[Tuple[float, float]]:
    """Def-point di una DIMENSION."""
    try:
        return (entity.dxf.defpoint.x, entity.dxf.defpoint.y)
    except Exception:
        return None


def _fallback_anchor(entity) -> Optional[Tuple[float, float]]:
    """Cerca un qualsiasi attributo-punto usabile."""
    for attr in ("center", "insert", "start", "defpoint"):
        if hasattr(entity.dxf, attr):
            try:
                pt = getattr(entity.dxf, attr)
                return (pt.x, pt.y)
            except Exception:
                continue
    return None


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


# ---------------------------------------------------------------------------
# DIMENSION
# ---------------------------------------------------------------------------

def _dimension_annotation(entity, pos, layer) -> Optional[Dimension]:
    rendered = _render_block(entity)

    if rendered.is_empty():
        # Nessun blocco geometria: ricostruiamo direttrici + linea di misura
        # dai def-point. Meglio del solo numero.
        syn_strokes, syn_text = _synthesize_dimension(entity)
        rendered.strokes.extend(syn_strokes)
        if syn_text is not None:
            rendered.texts.append(syn_text)

    dim_type, measured = _dimension_semantics(entity)
    override = _dimension_override(entity)

    if rendered.is_empty():
        # Nemmeno i def-point: almeno il valore come testo alla sua posizione.
        content = _dimension_text(entity)
        if not content or pos is None:
            return None
        rendered.texts.append(RenderedText(content=content, position=pos))

    if pos is None:
        pos = _bbox_center(
            rendered.strokes + rendered.fills + [[t.position] for t in rendered.texts]
        )
        if pos is None:
            return None

    return Dimension(
        position=pos,
        layer=layer,
        source_kind="DIMENSION",
        measured_value=measured,
        dim_type=dim_type,
        text_override=override,
        rendered=rendered,
    )


def _dimension_semantics(entity) -> Tuple[str, Optional[float]]:
    """(dim_type, valore misurato) di una DIMENSION."""
    kinds = {0: "linear", 1: "aligned", 2: "angular", 3: "diameter",
             4: "radius", 5: "angular3p", 6: "ordinate"}
    try:
        dim_type = kinds.get(int(entity.dxf.get("dimtype", 0)) & 7, "linear")
    except (TypeError, ValueError):
        dim_type = "linear"
    measured: Optional[float] = None
    try:
        m = entity.get_measurement()
        if isinstance(m, (int, float)):
            measured = float(m)
    except Exception:
        pass
    return dim_type, measured


def _dimension_override(entity) -> Optional[str]:
    """
    Override esplicito del testo quota, o None se la quota mostra la misura.

    Campo DXF `text`: "" / "<>" → misura calcolata (nessun override);
    " " → testo soppresso; "...<>" → prefisso/suffisso; altro → override.
    `write()` risolve "<>" con la misura.
    """
    raw = entity.dxf.get("text", "") or ""
    return None if raw in ("", "<>") else raw


def _synthesize_dimension(entity):
    """
    Ricostruisce l'immagine di una DIMENSION lineare dai def-point, quando il
    blocco geometria manca. Ritorna (strokes, RenderedText | None).

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
        text_item = RenderedText(content=content, position=pos)

    return strokes, text_item


# ---------------------------------------------------------------------------
# LEADER / MULTILEADER
# ---------------------------------------------------------------------------

def _leader_annotation(entity, pos, layer, source_kind) -> Optional[Leader]:
    rendered = _render_block(entity)
    if rendered.is_empty():
        return None

    text = rendered.texts[0].content if rendered.texts else ""
    vertices = _leader_vertices(entity)

    if pos is None:
        pos = (vertices[0] if vertices
               else _bbox_center(rendered.strokes + rendered.fills))
        if pos is None:
            return None

    return Leader(
        position=pos,
        layer=layer,
        source_kind=source_kind,
        text=text,
        vertices=vertices,
        rendered=rendered,
    )


def _leader_vertices(entity) -> List[Tuple[float, float]]:
    t = entity.dxftype()
    try:
        if t == "LEADER":
            return [(float(v[0]), float(v[1])) for v in entity.vertices]
        if t == "MULTILEADER":
            return [(float(v[0]), float(v[1]))
                    for v in entity.context.mleader.vertices]
    except Exception:
        pass
    return []


# ---------------------------------------------------------------------------
# Appiattimento del blocco anonimo (DIMENSION / LEADER / MULTILEADER)
# ---------------------------------------------------------------------------

def _render_block(entity) -> RenderedGeometry:
    """Espande l'immagine dell'entità in strokes/fills/texts puri."""
    strokes: List[List[Tuple[float, float]]] = []
    fills: List[List[Tuple[float, float]]] = []
    texts: List[RenderedText] = []

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

    return RenderedGeometry(strokes=strokes, fills=fills, texts=texts)


def _flatten_virtual(entity):
    """Espande `virtual_entities()` ricorsivamente sugli INSERT (frecce a blocco)."""
    for v in entity.virtual_entities():
        if v.dxftype() == "INSERT":
            yield from _flatten_virtual(v)
        else:
            yield v


def _text_item(v) -> Optional[RenderedText]:
    t = v.dxftype()
    content = clean_mtext(v.text) if t == "MTEXT" else (v.dxf.get("text", "") or "").strip()
    if not content:
        return None
    ins = v.dxf.get("insert") or v.dxf.get("align_point")
    if ins is None:
        return None
    raw_h = v.dxf.get("char_height", 2.5) if t == "MTEXT" else v.dxf.get("height", 2.5)
    return RenderedText(
        content=content,
        position=(float(ins[0]), float(ins[1])),
        height=_f(raw_h) or 2.5,
        rotation=_f(v.dxf.get("rotation", 0.0)) or 0.0,
    )


def _bbox_center(polylines) -> Optional[Tuple[float, float]]:
    xs = [p[0] for pl in polylines for p in pl]
    ys = [p[1] for pl in polylines for p in pl]
    if not xs:
        return None
    return ((min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0)


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
    if len(vs) == 4 and vs[2] == vs[3]:
        vs = vs[:3]
    return vs


def _dimension_text(entity) -> str:
    """
    Testo visualizzato della quota, quando l'immagine non è espandibile.

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
