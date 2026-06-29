"""
frame_adapter_dxf.py — adapters/dxf/frame_adapter_dxf.py

Adapter DXF per il frame detector.

Responsabilità:
    - Estrae LINE e LWPOLYLINE dal modelspace ezdxf
    - Le converte in RawSegment (formato agnostico del core)
    - Chiama detect_frame() e restituisce gli handle da escludere

Non contiene logica di rilevamento — quella sta in core/frame_detector.py.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import ezdxf

from ...core.frame_detector import (
    RawPoint,
    RawSegment,
    FrameDetectionResult,
    detect_frame,
)

from dxf_forge.workflow.healer._utils import _explode_inserts

if TYPE_CHECKING:
    from ezdxf.layouts import Modelspace


# ---------------------------------------------------------------------------
# Tipi di entity geometrica considerati per la cornice
# ---------------------------------------------------------------------------

FRAME_ENTITY_TYPES = {"LINE", "LWPOLYLINE"}


# ---------------------------------------------------------------------------
# Conversione entity → RawSegment
# ---------------------------------------------------------------------------

def _line_to_raw(entity) -> RawSegment | None:
    try:
        start = entity.dxf.start
        end = entity.dxf.end
        handle = entity.dxf.handle
        return RawSegment(
            handle=handle,
            points=[
                RawPoint(start.x, start.y),
                RawPoint(end.x, end.y),
            ],
            is_closed=False,
        )
    except Exception:
        return None


def _lwpoly_to_raw(entity) -> RawSegment | None:
    try:
        handle = entity.dxf.handle
        points = [RawPoint(x, y) for x, y, *_ in entity.get_points()]
        if len(points) < 2:
            return None
        is_closed = bool(entity.dxf.flags & 1)  # bit 0 = closed
        return RawSegment(
            handle=handle,
            points=points,
            is_closed=is_closed,
        )
    except Exception:
        return None


def _entity_to_raw(entity) -> RawSegment | None:
    t = entity.dxftype()
    if t == "LINE":
        return _line_to_raw(entity)
    elif t == "LWPOLYLINE":
        return _lwpoly_to_raw(entity)
    return None


# ---------------------------------------------------------------------------
# Entry point pubblico
# ---------------------------------------------------------------------------

def extract_frame_handles(msp: "Modelspace", **detector_kwargs) -> FrameDetectionResult:
    """
    Estrae le entity geometriche dal modelspace, le passa al core detector,
    e restituisce il risultato con gli handle da escludere.

    Args:
        msp: modelspace ezdxf
        **detector_kwargs: parametri opzionali passati a detect_frame()
                           (ratio_tolerance, border_tolerance_factor, min_coverage)

    Returns:
        FrameDetectionResult — .excluded_handles contiene gli handle da ignorare,
        .found indica se una cornice è stata rilevata con sufficiente confidenza.

    Uso tipico:
        result = extract_frame_handles(msp)
        if result.found:
            # escludi result.excluded_handles da heal()
    """
    _explode_inserts(msp)
    segments = []
    for entity in msp:
        if entity.dxftype() not in FRAME_ENTITY_TYPES:
            continue
        raw = _entity_to_raw(entity)
        if raw is not None:
            segments.append(raw)

    return detect_frame(segments, **detector_kwargs)
