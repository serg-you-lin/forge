

"""
forge/adapters/dxf/adapter.py
--------------------------------
Traduce entità DXF in primitive Forge.
UNICO punto di conversione DXF → primitive.
"""

from __future__ import annotations

from typing import Any, List, Optional, Sequence, Tuple

from shapely.geometry import Polygon

from ...core.primitives.segments import (
    LineSeg, ArcSeg, SplineSeg, CircleSeg, EllipseSeg, DEFAULT_TOLERANCE,
    segment_endpoints, segment_is_closed,
)
from ...core.primitives.polygon_builder import build_polygon
from ...core.adapter_base import ForgeAdapter
from ...core.geometry import round_point
from ...core.topology.edge import Edge, Segment
from ...model.role_rule import RoleRule, resolve_role
from ...model.style import EdgeStyle

from .parser import DxfEntityDispatcher


# ---------------------------------------------------------------------------
# Costanti
# ---------------------------------------------------------------------------

_SUPPORTED_TYPES = frozenset({'LINE', 'ARC', 'SPLINE', 'ELLIPSE'})

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
    `role_rules` sia al ripristino fedele in output (Cluster E):
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
# TRADUZIONE DXF → PRIMITIVE
# ---------------------------------------------------------------------------
# La traduzione entità DXF → primitiva vive in UN SOLO posto:
# `adapters/dxf/parser.py::DxfEntityDispatcher` (MAP.md D7). Prima ce n'erano
# due copie quasi identiche — una qui (`entity_to_primitive`), una in parser.py.


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
    if isinstance(segment, EllipseSeg):
        return (
            "ELLIPSE",
            round(segment.center[0], 6),
            round(segment.center[1], 6),
            round(segment.major_axis[0], 6),
            round(segment.major_axis[1], 6),
            round(segment.ratio, 6),
            round(segment.start_param, 6),
            round(segment.end_param, 6),
            segment.ccw,
        )
    return (type(segment).__name__, repr(segment))


def entity_to_polygon(entity, tolerance: float = DEFAULT_TOLERANCE) -> Optional[Polygon]:
    """
    Converte un'entità DXF chiusa in un `Polygon` shapely, passando per le
    primitive del core (parser + `build_polygon`). None se l'entità non è
    parsabile o non forma un poligono valido.
    """
    prim = DxfEntityDispatcher(entity).parse()
    if prim is None:
        return None
    primitives = prim if isinstance(prim, list) else [prim]
    return build_polygon(primitives, tolerance)


# ---------------------------------------------------------------------------
# DxfAdapter
# ---------------------------------------------------------------------------

class DxfAdapter(ForgeAdapter):
    """
    Adapter DXF che traduce entità DXF in Edge del dominio Forge.

    Il ruolo di ogni Edge viene da `role_rules` (D63), valutate sul nome del
    layer e sull'aspetto effettivo dell'entità: la prima che matcha vince,
    nessuna → `unknown`. Il layer non esce dall'adapter.
    """

    def __init__(
        self,
        msp,
        tolerance: float = 0.05,
        exclude_ids: Optional[set] = None,
        ignore_layers: Optional[set] = None,
        role_rules: Sequence[RoleRule] = (),
    ):
        super().__init__(tolerance)
        self.msp = msp
        self.exclude_ids = exclude_ids or set()
        self.ignore_layers = ignore_layers or set()
        self.role_rules = list(role_rules)

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

        def _append_edge(role, segment, style=None):
            key = _segment_key(segment)
            if key in seen_segment_keys:
                return
            seen_segment_keys.add(key)
            start, end = segment_endpoints(segment)
            start_r = round_point(start, self.node_decimals)
            end_r = round_point(end, self.node_decimals)
            if start_r is None or end_r is None:
                return
            edges.append(Edge(
                role=role,
                start=start_r,
                end=end_r,
                segment=segment,
                style=style or EdgeStyle(),
            ))

        for entity in self.msp:
            if _is_excluded(entity):
                continue

            dtype = entity.dxftype()
            label = (
                entity.dxf.layer
                if entity.dxf.hasattr("layer")
                else ""
            )
            style = _entity_style(entity)
            role = resolve_role(self.role_rules, label, style)

            # CIRCLE → CircleSeg (preservato!)
            if dtype == "CIRCLE":
                prim = DxfEntityDispatcher(entity).parse()
                if isinstance(prim, CircleSeg):
                    start, end = segment_endpoints(prim)
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

            # SPLINE / ELLIPSE: parse una volta sola, poi distingui chiusa
            # (loop degenere, come CIRCLE) da aperta (gestita più sotto come
            # LINE/ARC) — a differenza di CIRCLE, che in DXF è sempre chiuso,
            # sia SPLINE che ELLIPSE possono essere l'una o l'altra a seconda
            # dell'entità, quindi la si scopre solo dopo averla parsata.
            curved_prim: Optional[Segment] = None
            if dtype in ("SPLINE", "ELLIPSE"):
                curved_prim = DxfEntityDispatcher(entity).parse()
                if curved_prim is not None and segment_is_closed(curved_prim):
                    start, _ = segment_endpoints(curved_prim)
                    pt = round_point(start, self.node_decimals)
                    if pt is not None:
                        edges.append(Edge(
                            role=role,
                            start=pt,
                            end=pt,
                            segment=curved_prim,
                            style=style,
                        ))
                    continue

            # LWPOLYLINE / POLYLINE → segmenti
            if dtype in ("LWPOLYLINE", "POLYLINE"):
                primitives = DxfEntityDispatcher(entity).parse() or []
                if not isinstance(primitives, list):
                    primitives = [primitives]
                for segment in primitives:
                    _append_edge(role, segment, style=style)
                continue

            # LINE / ARC / SPLINE / ELLIPSE aperta
            if dtype not in _SUPPORTED_TYPES:
                continue

            prim = curved_prim if curved_prim is not None else DxfEntityDispatcher(entity).parse()
            if prim is None:
                continue

            start, end = segment_endpoints(prim)
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

