"""
rules/validator.py
------------------
Validazione della salute geometrica — non modifica nulla, solo legge e
restituisce warning/errori dentro un ForgeResult.

Due validazioni distinte, entrambe utili:

    validate(doc)        — INPUT, prima di heal(). Prende il ForgeDocument di
                           forge.load_dxf() e segnala i problemi che
                           renderebbero l'healing inutile o sbagliato.
    validate_result(res) — OUTPUT, dopo heal(). Controlla che i cluster prodotti
                           siano sani (poligono valido, fori contenuti, area).
                           Chiamata automaticamente da pipeline.heal().
"""

import math

from ..model import ForgeResult
from ..model.document import ForgeDocument
from ..core.topology.graph import build_node_graph
from ..core.primitives.segments import LineSeg, ArcSeg, SplineSeg, CircleSeg


# ---------------------------------------------------------------------------
# INPUT — prima di heal()
# ---------------------------------------------------------------------------

def validate(doc: ForgeDocument) -> ForgeResult:
    """
    Valida l'input prima di heal().

    Restituisce un ForgeResult con solo warnings / errors / is_valid
    (clusters vuoto). Non modifica il documento.

    Errori (is_valid = False) — il file non è lavorabile:
      - nessuna geometria
      - coordinate non finite (NaN / inf)
      - tutti i segmenti degeneri

    Warning — lavorabile ma da tenere d'occhio:
      - LINE/ARC ancora fuori da un contorno chiuso → serve la ricostruzione
      - endpoint che non si toccano nemmeno alla tolleranza dichiarata →
        heal() rischia di non chiudere nulla
      - segmenti di lunghezza nulla
    """
    if not isinstance(doc, ForgeDocument):
        raise TypeError(
            "forge.validate() richiede un ForgeDocument da forge.load_dxf(); "
            f"ricevuto {type(doc).__name__}"
        )

    result = ForgeResult(source_file=doc.source_path)
    edges = doc.edges

    # diagnostica raccolta da load_dxf() sul file grezzo (audit, INSERT,
    # Z != 0, duplicati): la rilanciamo così validate() è l'unico punto da
    # guardare prima di heal().
    result.warnings.extend(doc.warnings)

    if not edges:
        result.errors.append(
            "Documento senza geometria: solo annotazioni."
            if doc.annotations
            else "Documento vuoto: nessuna geometria trovata."
        )
        result.is_valid = False
        return result

    # --- coordinate non finite -----------------------------------------
    non_finite = sum(
        1 for e in edges for x, y in (e.start, e.end)
        if not (math.isfinite(x) and math.isfinite(y))
    )
    if non_finite:
        result.errors.append(
            f"{non_finite} endpoint con coordinate non finite (NaN/inf)."
        )
        result.is_valid = False

    # --- segmenti di lunghezza nulla ----------------------------------
    zero_len = [
        e for e in edges
        if e.start == e.end
        and not isinstance(e.segment, (CircleSeg, SplineSeg))
    ]
    if zero_len:
        result.warnings.append(
            f"{len(zero_len)} segmenti di lunghezza nulla — saranno ignorati."
        )

    if zero_len and len(zero_len) == len(edges):
        result.errors.append("Tutti i segmenti sono degeneri.")
        result.is_valid = False
        return result

    # --- gli endpoint si toccano? ------------------------------------
    # Alla tolleranza dichiarata: è quello che heal() può davvero sfruttare.
    tol = doc.source_meta.get("tolerance", 0.05)
    graph = build_node_graph(edges, epsilon=tol)
    has_junction = any(len(conn) >= 2 for conn in graph.nodes.values())
    has_closed_prim = bool(graph.degenerate_loops) or any(
        getattr(e, "closed_path", False) for e in edges
    )
    if not has_junction and not has_closed_prim:
        result.warnings.append(
            "Nessun endpoint condiviso alla tolleranza dichiarata e nessuna "
            "primitiva chiusa: heal() potrebbe non chiudere alcun contorno. "
            "Verificare tolleranza e unità di misura."
        )

    # --- geometria aperta da ricostruire ----------------------------
    open_prims = sum(
        1 for e in edges
        if isinstance(e.segment, (LineSeg, ArcSeg))
        and not getattr(e, "closed_path", False)
    )
    if open_prims:
        result.warnings.append(
            f"{open_prims} tra LINE e ARC non ancora in un contorno chiuso — "
            "heal() proverà a ricostruire i loop."
        )

    return result


# ---------------------------------------------------------------------------
# OUTPUT — dopo heal()
# ---------------------------------------------------------------------------

def validate_result(result: ForgeResult) -> ForgeResult:
    """
    Valida i ForgeCluster dentro un ForgeResult già popolato da heal().
    Aggiunge warning ed errori direttamente nel result passato.

    Controlli per ogni cluster:
      - poligono outer valido (non self-intersecting) e non vuoto
      - area outer > 0
      - fori effettivamente contenuti nell'outer
    """
    for i, cluster in enumerate(result.clusters):
        label = cluster.label or f"Part {i}"

        poly = cluster.outer.polygon
        if poly is None:
            result.errors.append(f"{label}: poligono outer è None.")
            result.is_valid = False
            continue

        if not poly.is_valid:
            result.warnings.append(
                f"{label}: poligono outer non valido (self-intersection?)."
            )

        if poly.is_empty:
            result.errors.append(f"{label}: poligono outer è vuoto.")
            result.is_valid = False
            continue

        if poly.area <= 0:
            result.errors.append(f"{label}: area outer <= 0.")
            result.is_valid = False

        for j, hole in enumerate(cluster.inners):
            if not poly.contains(hole.polygon):
                result.warnings.append(
                    f"{label}: foro {j} non completamente contenuto nell'outer."
                )

    return result
