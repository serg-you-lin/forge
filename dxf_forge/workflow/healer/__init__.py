
from __future__ import annotations

from ...rules.layers import LAYER_OUTER, LAYER_HOLE
from ._pipeline import HealerPipeline


def heal(msp, tolerance=0.05, ignore_layers=None, label="", source_file="", explode_inserts=False):
    pipeline = HealerPipeline(
        msp, tolerance,
        label=label,
        source_file=source_file,
        explode_inserts=explode_inserts,
        ignore_layers=ignore_layers,
    )
    return pipeline.run()
