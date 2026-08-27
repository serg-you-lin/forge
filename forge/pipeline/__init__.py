
from __future__ import annotations

from .heal import HealStep
from .detect import detect
from .write import write, split, DEFAULT_MIN_PART_AREA
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
    return HealStep(doc, tol, label=label, source_file=source_file).run()


def split_to_files(doc: ForgeDocument, output_folder, label="", source_file="",
                   tolerance=None, namer=None, keep_trash=False,
                   include_annotations=True,
                   min_area=DEFAULT_MIN_PART_AREA,
                   exclude_types=None) -> ForgeResult:
    result = heal(doc, tolerance=tolerance, label=label, source_file=source_file)

    if not result.is_valid or not result.parts:
        return result

    detect(result)
    split(result, doc, output_folder=output_folder, namer=namer,
          keep_trash=keep_trash, include_annotations=include_annotations,
          min_area=min_area, exclude_types=exclude_types)

    return result
