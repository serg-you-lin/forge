
from __future__ import annotations

from typing import Callable, Optional

from .heal import HealStep
from .detect import detect
from .write import write, split, DEFAULT_MIN_PART_AREA
from .inject import inject
from ..model.result import ForgeResult


def heal(msp, tolerance=0.05, ignore_layers=None, label="",
         source_file="", explode_inserts=False, special_layers=None) -> ForgeResult:
    return HealStep(msp, tolerance, label=label, source_file=source_file,
                    explode_inserts=explode_inserts, ignore_layers=ignore_layers,
                    special_layers=special_layers).run()


def split_to_files(msp, output_folder, label="", source_file="",
                   tolerance=0.05, explode_inserts=False, special_layers=None,
                   namer=None, keep_trash=False, include_annotations=True,
                   min_area=DEFAULT_MIN_PART_AREA) -> ForgeResult:
    result = heal(msp, tolerance=tolerance, explode_inserts=explode_inserts,
                  label=label, source_file=source_file, special_layers=special_layers)

    if not result.is_valid or not result.parts:
        return result

    detect(result, msp)
    split(msp, result, output_folder=output_folder, namer=namer,
          keep_trash=keep_trash, include_annotations=include_annotations,
          min_area=min_area)

    return result