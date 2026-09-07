"""
forge/tools/interpret.py
---------------------------
Interpretazione delle annotazioni: collega ogni annotazione del modello alla
geometria che la riguarda.

Fase separata e opzionale — NON viene chiamata da heal_and_detect(). `detect()`
fa già abbastanza (geometria + feature); l'interpretazione delle annotazioni è
un concern a sé, che il chiamante attiva quando gli serve
(es. prima di split() o di inject(), per sapere quale nota va con quale pezzo).

Oggi popola solo ``Annotation.cluster_ref`` (indice della parte contenitrice).
I riferimenti alle feature per quote e direttrici (``references`` / ``target``)
sono predisposti nel modello ma non ancora calcolati qui.
"""

from __future__ import annotations

from typing import Optional

from shapely.geometry import Point

from ..model.result import ForgeResult


def interpret_annotations(result: ForgeResult, snap_distance: float = 0.0) -> ForgeResult:
    """
    Assegna ``cluster_ref`` a ogni annotazione di ``result.annotations``.

    ``cluster_ref`` è l'indice in ``result.clusters`` della parte il cui contorno
    esterno contiene la posizione dell'annotazione. Le annotazioni fuori da
    ogni parte (es. il cartiglio) restano con ``cluster_ref = None``.

    ``snap_distance`` > 0: un'annotazione non contenuta da nessuna parte viene
    comunque assegnata alla parte più vicina se dista meno di ``snap_distance``
    dal suo contorno — utile per i callout che il CAD posiziona appena fuori dal
    pezzo. Con il default 0.0 vale solo il contenimento stretto.

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

    return result


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
