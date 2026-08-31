

"""
forge/adapters/dxf/adapter.py
--------------------------------
Traduce entità DXF in primitive Forge.
UNICO punto di conversione DXF → primitive.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from ...core.primitives.segments import LineSeg, ArcSeg, SplineSeg, CircleSeg, DEFAULT_TOLERANCE
from ...core.adapter_base import ForgeAdapter
from ...core.geometry import round_point
from ..bridge.edge import Edge, Segment
from ...model.role import ContourRole, WORK_TYPE_TO_ROLE, layer_to_role
from ...model.style import EdgeStyle

from .geometry_adapter import (
    entity_endpoints,
    get_representative_point,
    entity_to_polygon,
    spline_is_closed,
)
from .parser import DxfEntityDispatcher


# ---------------------------------------------------------------------------
# Costanti
# ---------------------------------------------------------------------------

_SUPPORTED_TYPES = frozenset({'LINE', 'ARC', 'SPLINE'})

# Layer che forge produce in output per contenuti NON di taglio: se un file già
# passato da forge viene riletto (round-trip, ri-heal), la loro geometria non è
# geometria di parte e va sempre ignorata, senza doverlo chiedere al chiamante.
_NON_STRUCTURAL_LAYERS = frozenset({'trash', 'annotation'})

# Linetype "di sistema": non hanno una entry propria nella tabella o non
# portano un pattern (BYLAYER/BYBLOCK ereditano; CONTINUOUS è sempre presente
# in ogni documento ezdxf.new()). Nessun pattern da catturare per questi.
_STANDARD_LINETYPES = frozenset({'BYLAYER', 'BYBLOCK', 'CONTINUOUS'})


# ---------------------------------------------------------------------------
# Aspetto grezzo (linetype/colore) — Cluster E
# ---------------------------------------------------------------------------

def _raw_linetype_pattern(lt_entry) -> Optional[Tuple[float, ...]]:
    """
    Pattern grezzo (lunghezza totale + tratti con segno, `+` = tratto,
    `-` = spazio) di un `Linetype` — lo stesso formato voluto da
    `doc.linetypes.add(name, pattern=[...])`.

    NON `Linetype.simplified_line_pattern()`: quello è un rendering per sola
    lettura, ha già perso i segni e la lunghezza totale (pensato per essere
    letto, non per essere ri-registrato) — ri-passarlo a `.add()` produce un
    pattern degenere (tutti tratti pieni, nessun vuoto).
    """
    pattern_length = 0.0
    elements = []
    for tag in lt_entry.pattern_tags.tags:
        if tag.code == 40:
            pattern_length = tag.value
        elif tag.code == 49:
            elements.append(tag.value)
    if len(elements) < 2:
        return None
    return (pattern_length, *elements)


def _entity_style(entity) -> EdgeStyle:
    """
    Cattura l'aspetto EFFETTIVO (linetype/colore) di un'entità DXF in un
    `EdgeStyle` puro — quello che si vede davvero in CAD, non solo l'attributo
    grezzo dell'entità.

    Caso comune: il disegno mette lo stile sul LAYER, non sulla singola
    entità (`entity.dxf.linetype == "ByLayer"`) — il tratteggio vero vive
    nella entry del layer (`doc.layers.get(layer).dxf.linetype`), l'attributo
    dell'entità da solo non lo dice. Senza risolvere BYLAYER al valore del
    layer, ogni entità che eredita lo stile (il caso tipico) sfuggirebbe sia a
    `linetype_map`/`color_map` sia al ripristino fedele in output (Cluster E):
    scritta su un layer forge diverso (Trash/Bending/...), che di default è
    continuo, perderebbe silenziosamente il tratteggio.

    Se il linetype risolto non è uno standard, ne risolve anche il pattern
    (durate dei tratti) dalla tabella del documento sorgente — l'unico
    momento in cui forge può ancora leggerla, prima che il riferimento a
    ezdxf sparisca (`model-is-provenance-free-edges`). Il pattern risolto
    viaggia come dato puro fino a write(), che lo ri-registra nel documento
    di output.
    """
    try:
        linetype = entity.dxf.linetype if entity.dxf.hasattr("linetype") else "BYLAYER"
    except Exception:
        linetype = "BYLAYER"

    try:
        color = entity.dxf.color if entity.dxf.hasattr("color") else 256
    except Exception:
        color = 256

    true_color = None
    try:
        if entity.dxf.hasattr("true_color"):
            true_color = entity.dxf.true_color
    except Exception:
        pass

    doc = None
    try:
        doc = entity.doc
    except Exception:
        pass

    layer_entry = None
    if doc is not None and (linetype.upper() == "BYLAYER" or (color == 256 and true_color is None)):
        try:
            layer_entry = doc.layers.get(entity.dxf.layer)
        except Exception:
            layer_entry = None

    if linetype.upper() == "BYLAYER" and layer_entry is not None:
        linetype = layer_entry.dxf.linetype

    if color == 256 and true_color is None and layer_entry is not None:
        color = layer_entry.dxf.color

    desc = ""
    pattern = None
    if linetype.upper() not in _STANDARD_LINETYPES:
        try:
            lt_entry = doc.linetypes.get(linetype) if doc is not None else None
            if lt_entry is not None:
                pattern = _raw_linetype_pattern(lt_entry)
                desc = lt_entry.dxf.description
        except Exception:
            pass

    return EdgeStyle(
        linetype=linetype,
        linetype_desc=desc,
        linetype_pattern=pattern,
        color=color,
        true_color=true_color,
    )


# ---------------------------------------------------------------------------
# Classificazione da aspetto — linetype_map / color_map (seconda lane)
# ---------------------------------------------------------------------------
# Stesso principio di label_map (nome_layer → work_type), ma quando il layer
# non dice nulla: linetype_map matcha sul nome del linetype (case-insensitive),
# color_map sul colore ACI dell'entità (nome standard, es. "cyan", o intero).
# Il layer resta la lane autoritativa — questa lane si applica solo se
# layer_to_role() non ha già deciso (D5, doppio binario di provenienza).

# Nomi colore ACI standard (1-9 + il rosa "pink" usato da rules/palette.py),
# stesso vocabolario di ACI_TO_HEX letto al contrario — qui serve solo per
# risolvere le chiavi di color_map, non per scrivere output.
_ACI_NAME_TO_INT = {
    "red": 1, "yellow": 2, "green": 3, "cyan": 4, "blue": 5,
    "magenta": 6, "white": 7, "black": 7,
    "gray": 8, "grey": 8, "darkgray": 8, "darkgrey": 8,
    "lightgray": 9, "lightgrey": 9,
    "pink": 11,
}


def _normalize_linetype_map(linetype_map: Optional[Dict[str, str]]) -> Dict[str, str]:
    return {str(k).upper(): v for k, v in (linetype_map or {}).items()}


def _normalize_color_map(color_map) -> Dict[int, str]:
    """
    Traduce le chiavi di `color_map` in interi ACI: nome standard ("cyan"),
    intero o stringa numerica ("4"). Chiavi non risolvibili sono ignorate.
    """
    out: Dict[int, str] = {}
    for key, work_type in (color_map or {}).items():
        if isinstance(key, int):
            out[key] = work_type
            continue
        k = str(key).strip().lower()
        if k.lstrip("-").isdigit():
            out[int(k)] = work_type
        elif k in _ACI_NAME_TO_INT:
            out[_ACI_NAME_TO_INT[k]] = work_type
    return out


def _style_role(style: EdgeStyle, linetype_map: Dict[str, str], color_map: Dict[int, str]) -> ContourRole:
    """
    Ruolo dedotto dall'aspetto grezzo di un'entità (linetype poi colore),
    chiamata solo quando layer_to_role() non ha già assegnato un ruolo.
    """
    if linetype_map:
        work_type = linetype_map.get((style.linetype or "").upper())
        if work_type:
            role = WORK_TYPE_TO_ROLE.get(work_type.lower())
            if role is not None:
                return role

    if color_map:
        work_type = color_map.get(style.color)
        if work_type:
            role = WORK_TYPE_TO_ROLE.get(work_type.lower())
            if role is not None:
                return role

    return ContourRole.UNKNOWN


# ---------------------------------------------------------------------------
# TRADUZIONE DXF → PRIMITIVE
# ---------------------------------------------------------------------------
# La traduzione entità DXF → primitiva vive in UN SOLO posto:
# `adapters/dxf/parser.py::DxfEntityDispatcher` (MAP.md D7). Prima ce n'erano
# due copie quasi identiche — una qui (`entity_to_primitive`), una in parser.py.


def _segment_endpoints(segment: Segment) -> Tuple[Tuple[float, float], Tuple[float, float]]:
    """Endpoint di un segmento Forge."""
    if isinstance(segment, LineSeg):
        return segment.start, segment.end
    if isinstance(segment, ArcSeg):
        start = (
            segment.center[0] + segment.radius * math.cos(segment.start_angle),
            segment.center[1] + segment.radius * math.sin(segment.start_angle),
        )
        end = (
            segment.center[0] + segment.radius * math.cos(segment.end_angle),
            segment.center[1] + segment.radius * math.sin(segment.end_angle),
        )
        return start, end
    if isinstance(segment, SplineSeg):
        if segment.fit_points:
            start = segment.fit_points[0]
            end = segment.fit_points[-1]
            return (start[0], start[1]), (end[0], end[1])
        if not segment.control_points:
            return (0.0, 0.0), (0.0, 0.0)
        return segment.control_points[0], segment.control_points[-1]
    if isinstance(segment, CircleSeg):
        pt = (segment.center[0] + segment.radius, segment.center[1])
        return pt, pt
    return (0.0, 0.0), (0.0, 0.0)


def _segment_key(segment: Segment) -> tuple:
    """Chiave univoca per deduplicazione."""
    if isinstance(segment, LineSeg):
        pts = tuple(sorted((
            (round(segment.start[0], 6), round(segment.start[1], 6)),
            (round(segment.end[0], 6), round(segment.end[1], 6)),
        )))
        return ("LINE", pts)
    if isinstance(segment, ArcSeg):
        return (
            "ARC",
            round(segment.center[0], 6),
            round(segment.center[1], 6),
            round(segment.radius, 6),
            round(segment.start_angle, 6),
            round(segment.end_angle, 6),
            segment.ccw,
        )
    if isinstance(segment, SplineSeg):
        return (
            "SPLINE",
            int(segment.degree),
            tuple((round(x, 6), round(y, 6)) for x, y in segment.control_points),
            tuple(round(k, 9) for k in segment.knots),
            tuple(round(w, 9) for w in (segment.weights or [])),
            bool(segment.closed),
            bool(segment.periodic),
            int(segment.flags),
        )
    if isinstance(segment, CircleSeg):
        return (
            "CIRCLE",
            round(segment.center[0], 6),
            round(segment.center[1], 6),
            round(segment.radius, 6)
        )
    return (type(segment).__name__, repr(segment))


# ---------------------------------------------------------------------------
# DxfAdapter
# ---------------------------------------------------------------------------

class DxfAdapter(ForgeAdapter):
    """
    Adapter DXF che traduce entità DXF in Edge del dominio Forge.

    Il ruolo di ogni Edge viene deciso in due lane, in ordine:
      1. `label_map`    — {nome_layer: work_type}, autoritativa (D5)
      2. `linetype_map` / `color_map` — {linetype o colore: work_type},
         usata solo se il layer non ha già deciso. Stesso vocabolario di
         work_type (WORK_TYPE_TO_ROLE), stessa semantica: un modo di
         classificare quando il disegno usa lo stile della linea invece del
         layer per portare intenzione ("le tratteggiate sono pieghe").
    """

    def __init__(
        self,
        msp,
        tolerance: float = 0.05,
        exclude_ids: Optional[set] = None,
        ignore_layers: Optional[set] = None,
        label_map: Optional[Dict[str, str]] = None,
        linetype_map: Optional[Dict[str, str]] = None,
        color_map: Optional[Dict] = None,
    ):
        super().__init__(tolerance)
        self.msp = msp
        self.exclude_ids = exclude_ids or set()
        self.ignore_layers = ignore_layers or set()
        self._label_map = {
            k.lower(): v
            for k, v in (label_map or {}).items()
        }
        self._linetype_map = _normalize_linetype_map(linetype_map)
        self._color_map = _normalize_color_map(color_map)

    # ------------------------------------------------------------------
    # ForgeAdapter contract
    # ------------------------------------------------------------------

    def to_edges(self) -> List[Edge]:
        """Traduce entità DXF in Edge."""
        ignore = {s.lower() for s in self.ignore_layers}

        def _is_excluded(entity) -> bool:
            if id(entity) in self.exclude_ids:
                return True
            layer = (
                entity.dxf.layer.lower()
                if entity.dxf.hasattr("layer")
                else ""
            )
            if layer in _NON_STRUCTURAL_LAYERS:
                return True
            if not ignore:
                return False
            return any(sl in layer for sl in ignore)

        edges = []
        seen_segment_keys = set()

        def _append_edge(role, segment, closed_path=False, style=None):
            key = _segment_key(segment)
            if key in seen_segment_keys:
                return
            seen_segment_keys.add(key)
            start, end = _segment_endpoints(segment)
            start_r = round_point(start, self.node_decimals)
            end_r = round_point(end, self.node_decimals)
            if start_r is None or end_r is None:
                return
            edges.append(Edge(
                role=role,
                start=start_r,
                end=end_r,
                segment=segment,
                closed_path=closed_path,
                style=style or EdgeStyle(),
            ))

        for entity in self.msp:
            if _is_excluded(entity):
                continue

            dtype = entity.dxftype()
            layer = (
                entity.dxf.layer
                if entity.dxf.hasattr("layer")
                else ""
            )
            role = layer_to_role(layer, self._label_map)
            style = _entity_style(entity)
            if role == ContourRole.UNKNOWN and (self._linetype_map or self._color_map):
                role = _style_role(style, self._linetype_map, self._color_map)

            # CIRCLE → CircleSeg (preservato!)
            if dtype == "CIRCLE":
                prim = DxfEntityDispatcher(entity).parse()
                if isinstance(prim, CircleSeg):
                    start, end = _segment_endpoints(prim)
                    pt = round_point(start, self.node_decimals)
                    if pt is not None:
                        edges.append(Edge(
                            role=role,
                            start=pt,
                            end=pt,
                            segment=prim,
                            style=style,
                        ))
                continue

            # SPLINE chiusa → loop degenere
            if dtype == "SPLINE" and spline_is_closed(entity):
                prim = DxfEntityDispatcher(entity).parse()
                if isinstance(prim, SplineSeg):
                    start, _ = _segment_endpoints(prim)
                    pt = round_point(start, self.node_decimals)
                    if pt is not None:
                        edges.append(Edge(
                            role=role,
                            start=pt,
                            end=pt,
                            segment=prim,
                            style=style,
                        ))
                continue

            # LWPOLYLINE / POLYLINE → segmenti
            if dtype in ("LWPOLYLINE", "POLYLINE"):
                primitives = DxfEntityDispatcher(entity).parse() or []
                if not isinstance(primitives, list):
                    primitives = [primitives]
                poly_closed = bool(
                    getattr(entity, "is_closed", False)
                    or getattr(entity, "closed", False)
                )
                for segment in primitives:
                    _append_edge(role, segment, closed_path=poly_closed, style=style)
                continue

            # LINE / ARC / SPLINE aperta
            if dtype not in _SUPPORTED_TYPES:
                continue

            start, end = entity_endpoints(entity)
            if start is None or end is None:
                continue

            prim = DxfEntityDispatcher(entity).parse()
            if prim is None:
                continue

            start_r = round_point(start, self.node_decimals)
            end_r = round_point(end, self.node_decimals)
            if start_r is None or end_r is None:
                continue

            edges.append(Edge(
                role=role,
                start=start_r,
                end=end_r,
                segment=prim,
                style=style,
            ))

        return edges

    def source_context(self, ref: Any) -> str:
        """Layer dell'entità sorgente."""
        if isinstance(ref, str):
            return ref
        try:
            return (
                ref.dxf.layer
                if ref.dxf.hasattr("layer")
                else ""
            )
        except AttributeError:
            return ""

