
from __future__ import annotations

from typing import Callable, Optional

from .heal import HealStep
from .detect import detect
from .write import write, split, DEFAULT_MIN_PART_AREA
from .inject import inject
from ..model.result import ForgeResult
from ..adapters.dxf.adapter import DxfAdapter


def heal(msp, tolerance=0.05, ignore_layers=None, label="",
         source_file="", label_map=None) -> ForgeResult:
    adapter = DxfAdapter(msp, tolerance=tolerance,
                     ignore_layers={l.lower() for l in (ignore_layers or [])},
                     label_map=label_map)
    return HealStep(adapter, tolerance, label=label, source_file=source_file,
                    ignore_layers=ignore_layers,
                    special_layers=label_map).run()
    # return HealStep(adapter, msp, tolerance, label=label, source_file=source_file,
    #                 ignore_layers=ignore_layers,
    #                 special_layers=label_map).run()

def split_to_files(msp, output_folder, label="", source_file="",
                   tolerance=0.05, label_map=None,
                   namer=None, keep_trash=False, include_annotations=True,
                   min_area=DEFAULT_MIN_PART_AREA,
                   exclude_types=None) -> ForgeResult:
    result = heal(msp, tolerance=tolerance,
                  label=label, source_file=source_file, label_map=label_map)

    if not result.is_valid or not result.parts:
        return result

    detect(result)
    split(msp, result, output_folder=output_folder, namer=namer,
          keep_trash=keep_trash, include_annotations=include_annotations,
          min_area=min_area, exclude_types=exclude_types)

    return result