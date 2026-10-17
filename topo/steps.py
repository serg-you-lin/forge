"""
topo/steps.py
-------------
I passi di `heal()` e della lettura per isole, uno per funzione (MAP.md D117).

`topo.heal()` e `topo.island()` sono le composizioni di default; chi compone
la sua ricetta (D58, D62) prende i mattoni da qui — per esempio senza
`build_hierarchy`, finché non ha deciso da sé cosa significa un contorno
dentro un altro:

    import topo

    finite, broken = topo.steps.split_non_finite(doc.edges)
    ...

Si scrive sempre per intero, `topo.steps.<passo>`: "steps" da solo, letto a
metà di uno script, non dice di chi sono i passi (D119).

La top-level resta per chi usa la pipeline: caricare, heal, island, export,
validazione, i tipi del modello, `topo.geometry`.
"""
# isole spaziali, rete piana, faccia esterna, tassellature (D58)
from .core.healing.islands import spatial_islands, Island
from .core.topology.noding import split_at_crossings, NodedEdges
from .core.topology.outer_face import outer_face, OuterFace
from .core.healing.normalizer import refit_tessellations
# normalizzazione e passi di heal() (D62)
from .core.healing.normalizer import (
    merge_collinear_overlaps, merge_cocircular_overlaps, weld_degenerate_linesegs,
)
from .core.healing.steps import (
    split_non_finite, split_labeled, close_free_gaps, dangling_splines, find_non_contour_edges,
    find_joining_edges, free_ends, close_near_full_arcs, NEAR_FULL_ARC_MISSING,
    repair_merged_corners, find_loops, LoopSearch, structural_loops,
    loops_to_curves, polygonize_edges, polygons_to_curves,
    labeled_curves, build_hierarchy,
)
from .core.topology.loop_finder import edges_to_open_curves

__all__ = [
    "spatial_islands", "Island",
    "split_at_crossings", "NodedEdges",
    "outer_face", "OuterFace",
    "refit_tessellations",
    "merge_collinear_overlaps", "merge_cocircular_overlaps", "weld_degenerate_linesegs",
    "split_non_finite", "split_labeled", "close_free_gaps", "dangling_splines",
    "find_non_contour_edges", "find_joining_edges", "free_ends",
    "close_near_full_arcs", "NEAR_FULL_ARC_MISSING", "repair_merged_corners",
    "find_loops", "LoopSearch", "structural_loops",
    "loops_to_curves", "polygonize_edges", "polygons_to_curves",
    "edges_to_open_curves", "labeled_curves", "build_hierarchy",
]
