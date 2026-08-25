"""DXF-specific entity materialization helpers for split output."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .copy_adapter import copy_entity
from .geometry_adapter import entity_to_primitive
from .exporter import write_contour_to_msp
from ...core.primitives import SplineSeg


@dataclass
class _ContourProxy:
    segments: list


def materialize_entity_for_split(entity, msp_out) -> Optional[object]:
    """
    Materialize a source DXF entity into split output modelspace.

    - SPLINE: rebuild from primitive spline data via exporter
    - Others: copy as-is via copy adapter
    """
    if entity.dxftype() == "SPLINE":
        primitive = entity_to_primitive(entity)
        if isinstance(primitive, SplineSeg):
            return write_contour_to_msp(
                msp_out,
                _ContourProxy(segments=[primitive]),
                entity.dxf.layer,
            )
        return None

    return copy_entity(entity, msp_out)
