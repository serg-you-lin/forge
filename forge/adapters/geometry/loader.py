"""
adapters/geometry/loader.py
----------------------------
Punto di ingresso per costruire un ForgeDocument da geometria già nota — non da
un file. Stesso contratto di load_dxf/load_pdf (produce un ForgeDocument, non
tipi interni), ma la "sorgente" è chi chiama: un generatore parametrico (es. uno
sviluppo di cono/cilindro calcolato altrove) o un ricostruttore di geometria da
punti (es. un contorno da computer vision già vettorializzato).

Chi chiama non importa NESSUN tipo interno di forge: le entità sono dict Python
puri. La traduzione in Edge (arrotondamento nodi, ruolo semantico) è identica
nello spirito a quella di DxfAdapter — stessa tolleranza, stessa logica di
arrotondamento — cambia solo la sorgente da tradurre.

SPERIMENTALE: come load_pdf, è fuori dal contratto pubblico documentato
(forge.__all__) finché non è stato usato da un caso reale (vedi MAP.md). Resta
importabile come forge.load_geometry.

Funzioni pubbliche:
    load_geometry — traduce una lista di descrizioni geometriche in ForgeDocument
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Tuple

from ...core.adapter_base import ForgeAdapter
from ...core.geometry import round_point
from ...core.primitives.segments import LineSeg, ArcSeg, CircleSeg, segment_endpoints
from ...core.topology.edge import Edge
from ...model.document import ForgeDocument
from ...model.role import normalize_role

_SUPPORTED_TYPES = frozenset({"line", "arc", "circle", "polyline"})


def _role_from(entity: Dict[str, Any]) -> str:
    """
    work_type stringa (stesso vocabolario di label_map) → ruolo. Un work_type
    sconosciuto viene conservato (via normalize_role), non schiacciato a UNKNOWN.
    """
    return normalize_role(entity.get("role"))


class GeometryAdapter(ForgeAdapter):
    """
    Traduce descrizioni geometriche pure (dict) in Edge del dominio forge.

    Schema di ogni entità, per "type":
        line:     {"type": "line", "start": (x,y), "end": (x,y), "role": "outer"}
        arc:      {"type": "arc", "center": (x,y), "radius": r,
                   "start_angle": gradi, "end_angle": gradi,
                   "ccw": True, "role": "outer"}
        circle:   {"type": "circle", "center": (x,y), "radius": r, "role": "hole"}
        polyline: {"type": "polyline", "points": [(x,y), ...],
                   "closed": True, "role": "outer"}

    "role" è opzionale — stesso vocabolario di label_map (work_type stringa:
    "outer", "hole", "inner", "bending", "engrave", ...). Se omesso resta
    "unknown": non è un problema per il contorno più esterno di una
    parte, a cui HierarchyBuilder assegna comunque OUTER per posizione
    nell'albero di contenimento — serve solo per far riconoscere fori/inner
    espliciti prima che detect() li riclassifichi.

    Gli angoli di "arc" sono in GRADI (convenzione DXF/CAD, non i radianti di
    ArcSeg) — più naturale per chi consegna numeri calcolati a mano.
    """

    def __init__(self, entities: List[Dict[str, Any]], tolerance: float = 0.05):
        super().__init__(tolerance)
        self.entities = entities

    # ------------------------------------------------------------------
    # ForgeAdapter contract
    # ------------------------------------------------------------------

    def to_edges(self) -> List[Edge]:
        edges: List[Edge] = []
        for i, entity in enumerate(self.entities):
            kind = str(entity.get("type", "")).lower()
            role = _role_from(entity)

            if kind == "line":
                edges.append(self._line_edge(entity, role))
            elif kind == "arc":
                edges.append(self._arc_edge(entity, role))
            elif kind == "circle":
                edges.append(self._circle_edge(entity, role))
            elif kind == "polyline":
                edges.extend(self._polyline_edges(entity, role))
            else:
                raise ValueError(
                    f"load_geometry(): tipo non supportato all'indice {i}: "
                    f"{entity.get('type')!r} — validi: {sorted(_SUPPORTED_TYPES)}"
                )
        return edges

    def source_context(self, ref: Any) -> str:
        return "load_geometry"

    # ------------------------------------------------------------------
    # Costruzione dei singoli Edge
    # ------------------------------------------------------------------

    def _round(self, pt: Tuple[float, float]) -> Tuple[float, float]:
        return round_point(pt, self.node_decimals)

    def _line_edge(self, entity: Dict[str, Any], role: str) -> Edge:
        start = tuple(entity["start"])
        end = tuple(entity["end"])
        return Edge(
            role=role,
            start=self._round(start),
            end=self._round(end),
            segment=LineSeg(start=start, end=end),
        )

    def _arc_edge(self, entity: Dict[str, Any], role: str) -> Edge:
        seg = ArcSeg(
            center=tuple(entity["center"]),
            radius=float(entity["radius"]),
            start_angle=math.radians(float(entity["start_angle"])),
            end_angle=math.radians(float(entity["end_angle"])),
            ccw=bool(entity.get("ccw", True)),
        )
        start, end = segment_endpoints(seg)
        return Edge(role=role, start=self._round(start), end=self._round(end), segment=seg)

    def _circle_edge(self, entity: Dict[str, Any], role: str) -> Edge:
        seg = CircleSeg(center=tuple(entity["center"]), radius=float(entity["radius"]))
        start, _ = segment_endpoints(seg)
        pt = self._round(start)
        return Edge(role=role, start=pt, end=pt, segment=seg)

    def _polyline_edges(self, entity: Dict[str, Any], role: str) -> List[Edge]:
        points = [tuple(p) for p in entity["points"]]
        closed = bool(entity.get("closed", False))
        if closed and points and points[0] != points[-1]:
            points = points + [points[0]]

        edges: List[Edge] = []
        for a, b in zip(points, points[1:]):
            edges.append(Edge(
                role=role,
                start=self._round(a),
                end=self._round(b),
                segment=LineSeg(start=a, end=b),
                closed_path=closed,
            ))
        return edges


# ---------------------------------------------------------------------------
# Entry point pubblico
# ---------------------------------------------------------------------------

def load_geometry(
    entities: List[Dict[str, Any]],
    tolerance: float = 0.05,
    source_path: str = "",
) -> ForgeDocument:
    """
    Costruisce un ForgeDocument da una lista di descrizioni geometriche pure —
    stesso contratto di load_dxf, ma la sorgente non è un file: è geometria già
    calcolata o ricostruita altrove (generatori parametrici, contorni
    vettorializzati da immagine, ...).

    Vedi GeometryAdapter per lo schema di ogni "type" di entità supportato
    (line / arc / circle / polyline).

    Esempio — settore anulare di uno sviluppo di cono:
        doc = forge.load_geometry([
            {"type": "arc",  "center": (0,0), "radius": r_est,
             "start_angle": -a/2, "end_angle": a/2, "role": "outer"},
            {"type": "line", "start": p_int_1, "end": p_est_1, "role": "outer"},
            {"type": "arc",  "center": (0,0), "radius": r_int,
             "start_angle": -a/2, "end_angle": a/2, "role": "outer"},
            {"type": "line", "start": p_int_2, "end": p_est_2, "role": "outer"},
        ])
        result = forge.heal_and_detect(doc, label="sviluppo_cono")
        forge.to_dxf(result)

    Args:
        entities:    lista di dict geometrici (vedi GeometryAdapter)
        tolerance:   tolleranza di arrotondamento dei nodi topologici — stesso
                     significato di load_dxf(tolerance=...); passala identica
                     a heal() se la personalizzi
        source_path: etichetta libera per ForgeDocument.source_path — non è un
                     file, serve solo per diagnostica/tracciabilità

    Returns:
        ForgeDocument (edges + source_meta), pronto per heal()/heal_and_detect().
    """
    edges = GeometryAdapter(entities, tolerance=tolerance).to_edges()
    return ForgeDocument(
        edges=edges,
        source_path=source_path or "<load_geometry>",
        source_meta={"tolerance": tolerance, "label_map": {}},
    )
