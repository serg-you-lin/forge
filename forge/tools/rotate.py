"""
forge/tools/rotate.py
-----------------------
Ruota l'intera geometria di un ForgeDocument attorno a un centro, allineando
opzionalmente il lato OUTER più lungo del disegno all'orizzontale.

Due passate, non una rotazione in-place del ForgeResult: la prima heal()
serve solo a scoprire quale entità è "outer" (quella classificazione esiste
solo dopo la topologia) e a misurarne l'angolo; la rotazione vera si applica
alla geometria grezza (`ForgeDocument.edges`, pre-heal) — il chiamante rifà
heal() sul documento ruotato per ottenere un ForgeResult altrettanto valido
di quello di partenza, con la stessa identica logica di classificazione.
Ruotare invece un ForgeResult già sano (poligoni, feature, gerarchia di
contenimento) richiederebbe toccare a mano ogni struttura derivata — più
lavoro, più superficie di bug, per lo stesso risultato finale.

Nato dalla discussione "funzioni geometriche" (TODO.md) — orientamento
canonico per un futuro nester: la meccanica sta qui, la decisione di quanti
gradi provare/l'ottimizzazione di impacchettamento restano fuori scope
(nesting resta fuori da forge).
"""

from __future__ import annotations

import math
from dataclasses import replace
from typing import List, Optional, Tuple

from ..core.geometry import segment_length, chord_angle_deg, round_point, node_decimals_for
from ..core.primitives.segments import segment_endpoints
from ..core.heal import heal
from ..model.document import ForgeDocument
from ..model.result import ForgeResult

Point = Tuple[float, float]


def longest_outer_segment(result: ForgeResult) -> Tuple[Optional[object], float, Optional[float]]:
    """
    `(segment, length, angle_deg)` del segmento OUTER più lungo su TUTTI i
    cluster di `result` — filtrato a `cluster.outer.segments`, non a
    qualunque geometria del disegno (una bending line interna, per quanto
    lunga, non conta). `(None, 0.0, None)` se non c'è nessun outer.
    """
    best_seg, best_len, best_angle = None, 0.0, None
    for cluster in result.clusters:
        for seg in cluster.outer.segments:
            length = segment_length(seg)
            if length > best_len:
                start, end = segment_endpoints(seg)
                best_seg, best_len, best_angle = seg, length, chord_angle_deg(start, end)
    return best_seg, best_len, best_angle


def rotate_document(
    doc: ForgeDocument,
    angle_rad: float,
    origin: Point = (0.0, 0.0),
    tolerance: float = 0.05,
) -> ForgeDocument:
    """
    Nuovo ForgeDocument con ogni `edge.segment` ruotato di `angle_rad`
    (radianti, CCW) attorno a `origin` — stesso arrotondamento degli
    endpoint (`round_point`/`node_decimals_for`) usato dall'adapter al
    caricamento, perché la topologia ricostruita da un heal() successivo
    veda gli stessi nodi coincidenti di prima della rotazione.

    Le annotazioni non sono ruotate (nessun caso reale le ha ancora
    richieste): se `doc.annotations` non è vuoto, restano ferme nella loro
    posizione originale e viene aggiunto un warning — silenziarlo sarebbe
    dare per buona una geometria annotata scorretta.
    """
    decimals = node_decimals_for(tolerance)
    new_edges: List = []
    for edge in doc.edges:
        seg = edge.segment.rotated(angle_rad, origin)
        start, end = segment_endpoints(seg)
        new_edges.append(replace(
            edge,
            segment=seg,
            start=round_point(start, decimals),
            end=round_point(end, decimals),
        ))

    new_warnings = list(doc.warnings)
    if doc.annotations:
        new_warnings.append(
            f"rotate_document(): {len(doc.annotations)} annotazioni non ruotate (non ancora supportato)"
        )

    return replace(doc, edges=new_edges, warnings=new_warnings)


def _document_bbox_center(doc: ForgeDocument) -> Point:
    """Centro del bbox approssimato di tutti gli edge — vedi `rotate_to_longest_outer`."""
    xs: List[float] = []
    ys: List[float] = []
    for edge in doc.edges:
        start, end = segment_endpoints(edge.segment)
        xs.extend([start[0], end[0]])
        ys.extend([start[1], end[1]])
    if not xs:
        return (0.0, 0.0)
    return ((min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0)


def rotate_to_longest_outer(
    doc: ForgeDocument,
    origin: Optional[Point] = None,
    target_angle_deg: float = 0.0,
    tolerance: Optional[float] = None,
) -> Tuple[ForgeDocument, float]:
    """
    Ruota `doc` in modo che il suo lato OUTER più lungo diventi orizzontale
    (o `target_angle_deg`, se dato).

    Prima passata: `heal(doc)` SOLO per scoprire l'angolo dell'outer più
    lungo — quella classificazione esiste solo dopo la topologia. La
    rotazione si applica poi alla geometria grezza originale (non al
    ForgeResult della prima passata): il chiamante deve rifare `heal()` sul
    documento ruotato per ottenere un ForgeResult valido.

    `origin` di default è il centro del bounding box grezzo di `doc.edges`
    (approssimato dagli estremi dei segmenti, non un bbox esatto su archi —
    va bene per un centro di rotazione: la forma non cambia con `origin`,
    solo dove finisce nel piano). `tolerance` di default riprende
    `doc.source_meta["tolerance"]` (quella usata da `load_dxf`), come fa
    `heal()` stesso.

    Ritorna `(documento_ruotato, angle_deg_applicato)` — `angle_deg` è
    quanto si è ruotato, non l'angolo del lato (utile per un log/CLI). Se
    non c'è nessun outer (documento vuoto o senza cluster), ritorna `doc`
    invariato e `0.0`.
    """
    result = heal(doc, tolerance=tolerance)
    _, _, angle_deg = longest_outer_segment(result)
    if angle_deg is None:
        return doc, 0.0

    if origin is None:
        origin = _document_bbox_center(doc)

    tol = tolerance if tolerance is not None else doc.source_meta.get("tolerance", 0.05)
    rotation_deg = target_angle_deg - angle_deg
    rotated = rotate_document(doc, math.radians(rotation_deg), origin, tol)
    return rotated, rotation_deg
