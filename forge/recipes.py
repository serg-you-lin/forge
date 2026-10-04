"""
forge/recipes.py
----------------
Le scorciatoie: mettono in fila i passi che stanno altrove (``core.heal``,
``io.dxf``) per il caller che non ha bisogno di orchestrarli a mano.

Non c'è logica nuova qui — solo l'ordine comodo. Una lettura di processo
(fori, pieghe: snapbend) si fa sul result prima di ``split``, non qui
(MAP.md D88).
"""

from __future__ import annotations

import os

from .core.heal import heal
from .io.dxf import split, cluster_passes_min_area, DEFAULT_MIN_CLUSTER_AREA
from .adapters.dxf.layers import LAYER_ANNOTATION
from .model.result import ForgeResult
from .model.document import ForgeDocument


def split_to_files(doc: ForgeDocument, output_folder, label="", source_file="",
                   tolerance=None, namer=None,
                   include_annotations=True,
                   min_area=DEFAULT_MIN_CLUSTER_AREA,
                   exclude_types=None,
                   annotation_layer=LAYER_ANNOTATION,
                   is_structural=None) -> ForgeResult:
    """
    Pipeline multi-pezzo + salvataggio su disco: heal → split → `.saveas()` per
    cluster. È l'unica funzione che tocca il filesystem: `split()` resta puro.
    Il nome file è `f"{cluster.label}.dxf"` (cluster.label lo assegna `namer`).
    `is_structural` passa a `heal()` (vedi lì).
    """
    result = heal(doc, tolerance=tolerance, label=label, source_file=source_file,
                  is_structural=is_structural)

    if not result.is_valid or not result.clusters:
        return result

    drawings = split(result, doc, namer=namer,
                     include_annotations=include_annotations,
                     min_area=min_area, exclude_types=exclude_types,
                     annotation_layer=annotation_layer)

    os.makedirs(output_folder, exist_ok=True)
    kept = [c for c in result.clusters if cluster_passes_min_area(c, min_area)]
    for cluster, drawing in zip(kept, drawings):
        drawing.saveas(os.path.join(output_folder, f"{cluster.label}.dxf"))

    return result
