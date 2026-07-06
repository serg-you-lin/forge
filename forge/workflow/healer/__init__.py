
from __future__ import annotations

from ...rules.layers import LAYER_OUTER, LAYER_HOLE
from ._pipeline import HealerPipeline


def heal(
    msp,
    tolerance:       float = 0.05,
    ignore_layers:   list  = None,
    label:           str   = "",
    source_file:     str   = "",
    explode_inserts: bool  = False,
    special_layers:  dict  = None,
):
    pipeline = HealerPipeline(
        msp, tolerance,
        label=label,
        source_file=source_file,
        explode_inserts=explode_inserts,
        ignore_layers=ignore_layers,
        special_layers=special_layers,
    )
    return pipeline.run()
