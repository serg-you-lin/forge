"""
forge/tools/anchor.py
---------------------------
Ancoraggio delle annotazioni: collega ogni annotazione del modello alla
geometria che la riguarda. Prima chiamato `interpret_annotations()`,
rinominato (MAP.md D43) perché "interpret" era già usato per tre cose diverse
(questa funzione, il futuro progetto interprete, il concetto generico di
interpretazione discusso in MAP.md D39-D42) — pura ricostruzione geometrica,
zero giudizio, non ha niente a che fare col significato del disegno.

Fase separata e opzionale — NON viene chiamata da heal_and_detect(). `detect()`
fa già abbastanza (geometria + feature); l'ancoraggio delle annotazioni è
un concern a sé, che il chiamante attiva quando gli serve
(es. prima di split() o di inject(), per sapere quale nota va con quale pezzo).

Popola ``Annotation.cluster_ref`` (indice della parte contenitrice) e
``Leader.target`` (l'elemento su cui cade la punta della direttrice, D66).
``Dimension.references`` è predisposto nel modello ma non ancora calcolato.
"""

from __future__ import annotations

import re
from typing import Any, Iterator, Optional, Tuple

from shapely.geometry import LineString, Point

from ..model.annotation import Leader
from ..model.result import ForgeResult

LEADER_TARGET_DISTANCE = 0.5   # mm — la punta di una freccia sta sulla linea che indica


def anchor_annotations(result: ForgeResult, snap_distance: float = 0.0,
                       leader_distance: float = LEADER_TARGET_DISTANCE) -> ForgeResult:
    """
    Assegna ``cluster_ref`` a ogni annotazione di ``result.annotations``.

    ``cluster_ref`` è l'indice in ``result.clusters`` della parte il cui contorno
    esterno contiene la posizione dell'annotazione. Le annotazioni fuori da
    ogni parte (es. il cartiglio) restano con ``cluster_ref = None``.

    ``snap_distance`` > 0: un'annotazione non contenuta da nessuna parte viene
    comunque assegnata alla parte più vicina se dista meno di ``snap_distance``
    dal suo contorno — utile per i callout che il CAD posiziona appena fuori dal
    pezzo. Con il default 0.0 vale solo il contenimento stretto.

    Per ogni ``Leader`` con vertici calcola anche ``target``: vedi
    `leader_target`.

    Muta le annotazioni in-place e ritorna il ``result``.
    """
    refs = [
        (i, p.outer.polygon)
        for i, p in enumerate(result.clusters)
        if p.outer is not None and p.outer.polygon is not None
        and not p.outer.polygon.is_empty
    ]
    if not refs:
        return result

    for ann in result.annotations:
        ann.cluster_ref = _assign(ann.position, refs, snap_distance)
        if isinstance(ann, Leader):
            ann.target = leader_target(result, ann, leader_distance)

    return result


def leader_target(result: ForgeResult, leader: Leader,
                  distance: float = LEADER_TARGET_DISTANCE) -> Optional[str]:
    """
    L'elemento indicato dalla punta (``vertices[0]``) di ``leader``, come
    percorso in ``result``: ``"clusters[0].outer"``, ``"clusters[0].inners[3]"``,
    ``"clusters[1].holes[2]"`` (qualunque collezione di ``cluster.detected``).

    Il bordo più vicino alla punta, se entro ``distance``; altrimenti il più
    piccolo elemento chiuso (non il contorno esterno) che contiene la punta —
    una freccia che finisce dentro un foro; altrimenti ``None`` (una freccia
    di sezione, fuori dal pezzo). ``resolve_target`` fa il passo inverso.
    """
    if not leader.vertices:
        return None
    tip = Point(leader.vertices[0])
    elements = list(_elements(result))
    if not elements:
        return None

    near = [(geom.boundary.distance(tip) if poly else geom.distance(tip), _size(geom, poly), path)
            for path, geom, poly in elements]
    dist, _, path = min(near)
    if dist <= distance:
        return path

    inside = [(geom.area, path) for path, geom, poly in elements
              if poly and not path.endswith(".outer") and geom.covers(tip)]
    return min(inside)[1] if inside else None


def resolve_target(result: ForgeResult, target: Optional[str]) -> Any:
    """L'oggetto (contorno o feature) a cui punta un ``target``, o ``None``."""
    if not target:
        return None
    m = _TARGET.fullmatch(target)
    if m is None:
        return None
    ci, name, k = int(m.group(1)), m.group(2), m.group(3)
    if ci >= len(result.clusters):
        return None
    cluster = result.clusters[ci]
    if name == "outer":
        return cluster.outer
    items = cluster.inners if name == "inners" else cluster.features(name)
    k = int(k) if k is not None else -1
    return items[k] if 0 <= k < len(items) else None


_TARGET = re.compile(r"clusters\[(\d+)\]\.(\w+)(?:\[(\d+)\])?")


def _elements(result: ForgeResult) -> Iterator[Tuple[str, Any, bool]]:
    """(percorso, geometria shapely, è chiuso) per contorni e feature di ogni cluster."""
    for ci, cluster in enumerate(result.clusters):
        if cluster.outer is not None and cluster.outer.polygon is not None:
            yield f"clusters[{ci}].outer", cluster.outer.polygon, True
        collections = [("inners", cluster.inners)]
        if cluster.detected is not None:
            collections += list(cluster.detected.items())
        for name, items in collections:
            for k, item in enumerate(items):
                geom = _geometry(item)
                if geom is not None:
                    yield f"clusters[{ci}].{name}[{k}]", geom, geom.geom_type == "Polygon"


def _geometry(item):
    polygon = getattr(item, "polygon", None)
    if polygon is not None and not polygon.is_empty:
        return polygon
    points = [p for seg in getattr(item, "segments", None) or [] for p in seg.discretize()]
    return LineString(points) if len(points) >= 2 else None


def _size(geom, closed: bool) -> float:
    """A parità di distanza vince l'elemento più piccolo: un foro sul bordo del pezzo."""
    return geom.area if closed else geom.length


def _assign(position, refs, snap_distance: float) -> Optional[int]:
    probe = Point(position)

    covering = [i for i, poly in refs if poly.covers(probe)]
    if covering:
        return covering[0]

    if snap_distance > 0.0:
        idx, dist = min(
            ((i, poly.distance(probe)) for i, poly in refs),
            key=lambda pair: pair[1],
        )
        if dist <= snap_distance:
            return idx

    return None
