
from __future__ import annotations

import os

from .heal import HealStep
from .detect import detect, ALL_FEATURES
from .interpret import interpret_annotations
from .write import to_dxf, split, part_passes_min_area, DEFAULT_MIN_PART_AREA
from ..rules.thresholds import HOLE_DIAMETER_THRESHOLD
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
        if result.is_valid and result.parts:
            forge.detect(result, features="all", ...)

    A differenza di `detect()` nudo (che fa solo la lane label_map + pulizia
    topologia), qui `features` è `"all"` di default: fori, pieghe e incisioni
    vengono classificati. Passare `features=None` per la sola topologia pulita.

    `detect()` viene saltato se `heal()` non produce parti valide (il result
    torna comunque, con `is_valid=False` e gli errori popolati). I parametri
    `features` / `max_drill_diameter` / `*_tolerance` / `deduplicate_boundary_open`
    / `boundary_tolerance` sono quelli di `detect()`.

    Restano disponibili `heal()` e `detect()` separati: un renderer o un
    nesting tool possono volere la sola topologia.
    """
    result = heal(doc, tolerance=tolerance, label=label, source_file=source_file)

    if result.is_valid and result.parts:
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

    detect(result, features="all")
    drawings = split(result, doc, namer=namer,
                     include_annotations=include_annotations,
                     min_area=min_area, exclude_types=exclude_types,
                     annotation_layer=annotation_layer)

    os.makedirs(output_folder, exist_ok=True)
    kept = [p for p in result.parts if part_passes_min_area(p, min_area)]
    for part, drawing in zip(kept, drawings):
        drawing.saveas(os.path.join(output_folder, f"{part.label}.dxf"))

    return result
