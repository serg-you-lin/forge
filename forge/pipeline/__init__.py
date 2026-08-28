
from __future__ import annotations

import os

from .heal import HealStep
from .detect import detect
from .write import to_dxf, split, part_passes_min_area, DEFAULT_MIN_PART_AREA
from ..adapters.dxf.layers import LAYER_ANNOTATION
from .inject import inject
from ..model.result import ForgeResult
from ..model.document import ForgeDocument


def heal(doc: ForgeDocument, tolerance=None, label="", source_file="") -> ForgeResult:
    """
    Esegue l'healing su un ForgeDocument prodotto da forge.load_dxf().

    tolerance: se None viene ripresa da doc.source_meta['tolerance']
               (quella usata per arrotondare i nodi in load_dxf).
    label_map: NON è un parametro — va passato a load_dxf(), che assegna
               i ruoli agli Edge in fase di traduzione.
    """
    if not isinstance(doc, ForgeDocument):
        raise TypeError(
            "forge.heal() richiede un ForgeDocument da forge.load_dxf(); "
            f"ricevuto {type(doc).__name__}"
        )

    tol = tolerance if tolerance is not None else doc.source_meta.get("tolerance", 0.05)
    result = HealStep(doc, tol, label=label, source_file=source_file).run()

    if result.is_valid and result.parts:
        from ..rules.validator import validate_result
        validate_result(result)

    return result


def split_to_files(doc: ForgeDocument, output_folder, label="", source_file="",
                   tolerance=None, namer=None,
                   include_annotations=True,
                   min_area=DEFAULT_MIN_PART_AREA,
                   exclude_types=None,
                   annotation_layer=LAYER_ANNOTATION) -> ForgeResult:
    """
    Pipeline completa multi-pezzo + salvataggio su disco.

    heal → detect → split → `.saveas()` per parte. È l'unica funzione della
    pipeline che tocca il filesystem: `split()` resta puro.
    Il nome file è `f"{part.label}.dxf"` (part.label lo assegna `namer`).
    """
    result = heal(doc, tolerance=tolerance, label=label, source_file=source_file)

    if not result.is_valid or not result.parts:
        return result

    detect(result)
    drawings = split(result, doc, namer=namer,
                     include_annotations=include_annotations,
                     min_area=min_area, exclude_types=exclude_types,
                     annotation_layer=annotation_layer)

    os.makedirs(output_folder, exist_ok=True)
    kept = [p for p in result.parts if part_passes_min_area(p, min_area)]
    for part, drawing in zip(kept, drawings):
        drawing.saveas(os.path.join(output_folder, f"{part.label}.dxf"))

    return result
