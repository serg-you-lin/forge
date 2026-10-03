"""
core/heal.py
------------
Primo modo di leggere un ForgeDocument, accanto a island(): dall'interno.

heal() ricostruisce la topologia (chi tocca chi, quali giri si chiudono, come
stanno uno dentro l'altro) e trova il pezzo per contenimento. È la ricetta per
un disegno piano — un file di taglio, un nesting di pezzi separati. I passi
sono in `healing/steps.py`, pubblici: qui c'è solo la loro composizione di
default, più i warning che la raccontano.

Puro: solo Edge, primitive e modello, nessun formato.
"""

from __future__ import annotations

from typing import Callable, Optional

from ..model.document import ForgeDocument
from ..model.result import ForgeResult
from ..model.role import is_structural_role
from .primitives.segments import ArcSeg
from .topology.loop_finder import edges_to_open_features
from .healing.normalizer import (
    merge_collinear_overlaps, merge_cocircular_overlaps, weld_degenerate_linesegs,
)
from .healing.steps import (
    LoopSearch, split_labeled, close_free_gaps, dangling_splines, find_non_contour_edges,
    find_loops, structural_loops, loops_to_features, polygonize_edges,
    polygons_to_features, labeled_features, build_hierarchy,
)


# ---------------------------------------------------------------------------
# API pubblica
# ---------------------------------------------------------------------------

def heal(doc: ForgeDocument, tolerance: Optional[float] = None, label: str = "",
         source_file: str = "",
         is_structural: Optional[Callable[[str], bool]] = None) -> ForgeResult:
    """
    Legge `doc` dall'interno: un ForgeCluster per contorno esterno chiuso,
    con gli inners per contenimento.

    tolerance: se None viene ripresa da doc.source_meta['tolerance']
               (quella usata per arrotondare i nodi in load_dxf).
    I ruoli arrivano già sugli Edge: li assegna il loader (role_rules, D63).
    is_structural: predicato `Callable[[str], bool]` — "questo ruolo è
               topologia di contorno di pezzo?" — usato per decidere quali
               Edge già etichettati restano nel grafo prima della ricerca
               loop. Il motore da solo conosce solo outer/inner; passa
               `tools.manufacturing_role.is_structural` per riconoscere anche
               hole/countersink/threaded_hole (quello che fa
               `heal_and_detect()` automaticamente). Senza, un edge etichettato
               "hole" viene trattato come non strutturale e heal() lo segnala
               con un warning.
    """
    if not isinstance(doc, ForgeDocument):
        raise TypeError(
            "forge.heal() richiede un ForgeDocument da forge.load_dxf(); "
            f"ricevuto {type(doc).__name__}"
        )
    tol = doc.node_tolerance(tolerance)
    structural = is_structural or is_structural_role

    result = ForgeResult(source_file=source_file)
    result.annotations = list(doc.annotations)
    if not doc.edges:
        result.errors.append("Modelspace vuoto: nessuna geometria trovata.")
        result.is_valid = False
        return result

    edges = list(doc.edges)
    for merge, what in ((merge_collinear_overlaps, "segmenti collineari sovrapposti fusi"),
                        (merge_cocircular_overlaps, "archi co-circolari sovrapposti fusi"),
                        (weld_degenerate_linesegs, "LineSeg degeneri (sub-tolleranza) saldati")):
        merged = merge(edges)
        if len(edges) > len(merged):
            result.warnings.append(f"{len(edges) - len(merged)} {what} prima della ricerca loop.")
        edges = merged

    edges, labeled = split_labeled(edges, structural)
    if labeled and is_structural is None:
        result.warnings.append(_LABELED_WITHOUT_PREDICATE.format(n=len(labeled)))

    edges = close_free_gaps(edges, tol)
    if dangling_splines(edges):
        result.warnings.append(
            "SPLINE con endpoint non connesso trovata — "
            "gap tra SPLINE e altre entità gestito con una linea di congiunzione. "
            "Verificare manualmente la correttezza del file."
        )

    non_contour_ids = find_non_contour_edges(edges, tol)
    if non_contour_ids:
        result.warnings.append(
            f"{len(non_contour_ids)} edge non di contorno "
            f"esclusi dal grafo (entrambi gli endpoint su nodi di branching)."
        )

    search = find_loops(edges, non_contour_ids, tol)
    edges = search.edges
    result.all_arcs = [e.segment for e in edges if isinstance(e.segment, ArcSeg)]
    result.warnings += _search_warnings(search, tol)

    # Scala finita senza loop: ultima spiaggia polygonize, che dà già i
    # ClosedFeature (OUTER dal bordo, INNER dai buchi) — nessun edge "in loop".
    loop_edge_ids = set()
    closed = []
    if search.loops:
        kept = structural_loops(search.loops, structural)
        loop_edge_ids = {id(e) for loop in kept for e, _ in loop}
        closed = loops_to_features(kept)
    elif edges:
        result.warnings.append("Nessun loop trovato via grafo, uso polygonize come fallback.")
        polygons = polygonize_edges(edges, tol)
        closed = polygons_to_features(polygons)
        if polygons:
            result.warnings.append(
                f"Geometria ricostruita via fallback polygonize "
                f"({len(polygons)} poligoni). Verificare il risultato."
            )
        else:
            result.warnings.append(
                "LINE/ARC non formano loop chiusi — "
                "potrebbero essere marcature o geometria aperta."
            )

    features = closed + edges_to_open_features(edges, exclude_ids=loop_edge_ids)
    if not features:
        result.errors.append("Nessuna geometria chiusa trovata dopo healing.")
        result.is_valid = False
        return result

    clusters, trash = build_hierarchy(features, label=label, source_file=source_file,
                                      is_structural=structural)
    result.clusters = clusters
    result.trash_entities = trash + labeled_features(labeled)
    if not clusters:
        # La geometria non compone nessun contorno esterno chiuso: il
        # risultato non è un pezzo, è un file non lavorabile. La trash resta
        # per la diagnostica, ma to_dxf() si rifiuta di scrivere solo quella.
        result.errors.append(
            "Nessun contorno esterno chiuso: nessuna parte generabile dal file. "
            "Gli endpoint liberi non si congiungono entro la tolleranza richiesta."
        )
        result.is_valid = False
        return result

    from ..rules.validator import validate_result
    validate_result(result)
    return result


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

_LABELED_WITHOUT_PREDICATE = (
    "{n} edge con un ruolo diverso da "
    "outer/inner/unknown, trattati come non strutturali di "
    "default (heal() chiamato senza is_structural=...): un "
    "ruolo manifatturiero come 'hole' non viene riconosciuto "
    "come contorno di pezzo qui e finisce in trash. Passa "
    "is_structural=tools.manufacturing_role.is_structural, o "
    "chiama heal_and_detect() che lo fa automaticamente."
)


def _search_warnings(search: LoopSearch, tolerance: float) -> list[str]:
    """Cosa racconta heal() dei gradini della scala di find_loops()."""
    warnings = []
    if search.repaired:
        warnings.append(
            f"{search.repaired} angoli chiusi all'intersezione reale dopo "
            f"detection via clustering (epsilon={tolerance})."
        )
    if search.method == "tolerant":
        warnings.append(
            "Loop trovati solo dopo clustering tollerante "
            f"(epsilon={tolerance}); angoli non riparati: "
            f"{search.unrepaired_corners[:8]}. La discrepanza sopravvive nell'output."
        )
    if search.open_nodes:
        warnings.append(
            f"Grafo con {len(search.open_nodes)} estremi liberi dopo "
            f"clustering (prime coordinate: {search.open_nodes[:8]})."
        )
    return warnings
