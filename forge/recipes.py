"""
forge/recipes.py
----------------
Le scorciatoie della "via del 90%": mettono in fila i passi che stanno altrove
(``core.heal``, ``tools.detect``, ``io.dxf``) per il caller che non ha bisogno
di orchestrarli a mano.

Non c'è logica nuova qui — solo l'ordine comodo. Un consumatore che vuole solo
la topologia si ferma a ``forge.heal``; uno che compone i suoi passi usa
``detect`` / ``split`` direttamente.
"""

from __future__ import annotations

import os

from .core.heal import heal
from .tools.detect import detect
from .io.dxf import split, cluster_passes_min_area, DEFAULT_MIN_CLUSTER_AREA
from .rules.thresholds import HOLE_DIAMETER_THRESHOLD
from .adapters.dxf.layers import LAYER_ANNOTATION
from .model.result import ForgeResult
from .model.document import ForgeDocument


def heal_and_detect(doc: ForgeDocument, tolerance=None, label="", source_file="",
                    features="all",
                    max_drill_diameter: float = HOLE_DIAMETER_THRESHOLD,
                    bending_tolerance: float = 1.0,
                    engrave_tolerance: float = 1.0,
                    deduplicate_boundary_open: bool = True,
                    boundary_tolerance: float = 0.05) -> ForgeResult:
    """
    heal() + detect() in un colpo solo — la via del 90% dei chiamanti.

    Equivale a:
        result = forge.heal(doc, tolerance=..., label=..., source_file=...)
        if result.is_valid and result.clusters:
            forge.detect(result, features="all", ...)

    A differenza di `detect()` nudo (che fa solo la lane label_map + pulizia
    topologia), qui `features` è `"all"` di default: fori, pieghe e incisioni
    vengono classificati. Passare `features=None` per la sola topologia pulita.

    `detect()` viene saltato se `heal()` non produce cluster validi (il result
    torna comunque, con `is_valid=False` e gli errori popolati). I parametri
    `features` / `max_drill_diameter` / `*_tolerance` / `deduplicate_boundary_open`
    / `boundary_tolerance` sono quelli di `detect()`.

    Restano disponibili `heal()` e `detect()` separati: un renderer o un
    nesting tool possono volere la sola topologia.
    """
    result = heal(doc, tolerance=tolerance, label=label, source_file=source_file)

    if result.is_valid and result.clusters:
        detect(result,
               features=features,
               max_drill_diameter=max_drill_diameter,
               bending_tolerance=bending_tolerance,
               engrave_tolerance=engrave_tolerance,
               deduplicate_boundary_open=deduplicate_boundary_open,
               boundary_tolerance=boundary_tolerance)

    return result


def split_to_files(doc: ForgeDocument, output_folder, label="", source_file="",
                   tolerance=None, namer=None,
                   include_annotations=True,
                   min_area=DEFAULT_MIN_CLUSTER_AREA,
                   exclude_types=None,
                   annotation_layer=LAYER_ANNOTATION) -> ForgeResult:
    """
    Pipeline completa multi-pezzo + salvataggio su disco.

    heal → detect → split → `.saveas()` per cluster. È l'unica funzione che
    tocca il filesystem: `split()` resta puro.
    Il nome file è `f"{cluster.label}.dxf"` (cluster.label lo assegna `namer`).
    """
    result = heal(doc, tolerance=tolerance, label=label, source_file=source_file)

    if not result.is_valid or not result.clusters:
        return result

    detect(result, features="all")
    drawings = split(result, doc, namer=namer,
                     include_annotations=include_annotations,
                     min_area=min_area, exclude_types=exclude_types,
                     annotation_layer=annotation_layer)

    os.makedirs(output_folder, exist_ok=True)
    kept = [c for c in result.clusters if cluster_passes_min_area(c, min_area)]
    for cluster, drawing in zip(kept, drawings):
        drawing.saveas(os.path.join(output_folder, f"{cluster.label}.dxf"))

    return result
