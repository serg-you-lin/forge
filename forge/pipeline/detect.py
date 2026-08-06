"""
pipeline/detect.py
"""

from __future__ import annotations

import math
from typing import Optional

from shapely.geometry import LineString, Point, Polygon

from ..model import (
    ForgeResult,
    ForgePart,
    Hole,
    BendingLine,
    ClassifiedEntity,
    HOLE_TYPE_PLAIN,
    HOLE_TYPE_COUNTERSINK,
    HOLE_TYPE_THREADED,
    HOLE_TYPE_UNKNOWN,
)
from ..model.role import ContourRole
from ..model.shape import OpenShape, ClosedShape
from ..model.engraving import Engraving
from ..core.topology.classify.hole_detector import is_threaded_hole
from ..adapters.dxf.bending_adapter import bending_line_from_proxy
from ..rules.thresholds import STRUCTURAL_ROLES

_ROLE_TO_HOLE_TYPE = {
    ContourRole.COUNTERSINK:   HOLE_TYPE_COUNTERSINK,
    ContourRole.THREADED_HOLE: HOLE_TYPE_THREADED,
}


# ---------------------------------------------------------------------------
# API pubblica
# ---------------------------------------------------------------------------

def detect(
    result:            ForgeResult,
    bending_tolerance: float = 1.0,
) -> None:
    _detect_labeled(result)
    _detect_bending(result, bending_tolerance=bending_tolerance)
    _detect_holes(result)


# ---------------------------------------------------------------------------
# Step 1 — labeled shapes (certezza 1.0)
# ---------------------------------------------------------------------------

def _detect_labeled(result: ForgeResult) -> None:
    classified_ids = set()

    for proxy in result.trash_entities:
        if proxy.role == ContourRole.UNKNOWN:
            continue

        if proxy.role == ContourRole.ENGRAVE:
            _handle_engrave_open(proxy, result)
            classified_ids.add(id(proxy))
            continue

        work_type = proxy.role.value
        data = _extract_data(proxy, work_type)
        rep  = data.pop("representative_point", None)
        ce   = ClassifiedEntity(
            source_ref=proxy.source_ref,
            work_type=work_type,
            confidence=1.0,
            source="labeled",
            data=data,
            representative_point=rep,
        )
        result.classified_entities.append(ce)
        _assign_to_part(ce, result)
        classified_ids.add(id(proxy))

    result.trash_entities = [
        p for p in result.trash_entities if id(p) not in classified_ids
    ]

    for part in result.parts:
        for hole in part.holes:
            hole_type = _ROLE_TO_HOLE_TYPE.get(hole.role)
            if hole_type is None:
                continue
            hole.hole_type  = hole_type
            hole.confidence = 1.0
            hole.source     = "labeled"

        remaining = []
        for inner in part.inners:
            if inner.role == ContourRole.UNKNOWN or inner.role in STRUCTURAL_ROLES:
                remaining.append(inner)
                continue

            if inner.role == ContourRole.ENGRAVE:
                _handle_engrave_closed(inner, part)
                if inner.vs_id is not None:
                    result._suppressed_vs_ids.add(inner.vs_id)
                continue

            work_type = inner.role.value
            data = _extract_data_from_source(
                inner.source_ref, work_type, polygon=inner.polygon
            )
            rep  = data.pop("representative_point", None)
            ce = ClassifiedEntity(
                source_ref=inner.source_ref,
                work_type=work_type,
                confidence=1.0,
                source="labeled",
                data=data,
                polygon=inner.polygon,
                representative_point=rep,
            )
            result.classified_entities.append(ce)
            if inner.vs_id is not None:
                result._suppressed_vs_ids.add(inner.vs_id)
            _assign_to_part(ce, result)
        part.inners = remaining


# ---------------------------------------------------------------------------
# Step 2 — bending geometrico
# ---------------------------------------------------------------------------

def _detect_bending(result: ForgeResult, bending_tolerance: float = 1.0) -> None:
    classified_ids = {id(ce.source_ref) for ce in result.classified_entities}

    for proxy in result.trash_entities:
        if proxy.shape_type != "line":
            continue
        if id(proxy.source_ref) in classified_ids:
            continue
        if len(proxy.pts) < 2:
            continue
        if proxy.length < bending_tolerance:
            continue

        s = Point(proxy.pts[0])
        e = Point(proxy.pts[-1])

        for part in result.parts:
            outer    = part.outer.polygon
            boundary = outer.boundary

            if boundary.distance(s) < 1.0 and boundary.distance(e) < 1.0:
                midpoint = Point(
                    (proxy.pts[0][0] + proxy.pts[-1][0]) / 2,
                    (proxy.pts[0][1] + proxy.pts[-1][1]) / 2,
                )
                if outer.contains(midpoint):
                    part.bending_lines.append(bending_line_from_proxy(proxy, part.label))
                    break


# ---------------------------------------------------------------------------
# Step 3 — promozione fori da geometric_hint
# ---------------------------------------------------------------------------

def _detect_holes(result: ForgeResult) -> None:
    for part in result.parts:
        for hole in part.holes:
            if hole.source == "labeled":
                continue
            if hole.hole_type != HOLE_TYPE_UNKNOWN:
                continue

            threaded = is_threaded_hole(
                center=hole.center,
                radius=hole.diameter / 2,
                all_arcs=result.all_arcs,
            )

            if hole.geometric_hint == "countersink":
                hole.hole_type  = HOLE_TYPE_COUNTERSINK
                hole.confidence = 0.85
                hole.source     = "geometric"
                continue

            if hole.geometric_hint == "threaded":
                hole.hole_type  = HOLE_TYPE_THREADED
                hole.confidence = 0.85
                hole.source     = "geometric"
                continue

            if hole.source_ref is not None and threaded:
                hole.hole_type  = HOLE_TYPE_THREADED
                hole.confidence = 0.80
                hole.source     = "geometric"
            else:
                hole.hole_type  = HOLE_TYPE_PLAIN
                hole.confidence = 1.0
                hole.source     = "geometric"


# ---------------------------------------------------------------------------
# Engrave handlers
# ---------------------------------------------------------------------------

def _handle_engrave_open(proxy: OpenShape, result: ForgeResult) -> None:
    """Proxy da trash_entities — traccia aperta."""
    if len(proxy.pts) >= 2:
        rep = (
            sum(p[0] for p in proxy.pts) / len(proxy.pts),
            sum(p[1] for p in proxy.pts) / len(proxy.pts),
        )
    else:
        rep = proxy.pts[0] if proxy.pts else None

    engraving = Engraving(
        closed=False,
        length=round(proxy.length, 4),
        source_ref=proxy.source_ref,
        pts=list(proxy.pts),
        geometry=LineString(proxy.pts) if len(proxy.pts) >= 2 else None,
    )

    probe = Point(rep) if rep else None
    for part in result.parts:
        if probe and part.outer.polygon.contains(probe):
            engraving.part_label = part.label
            part.engrave_lines.append(engraving)
            return

    result.warnings.append(
        f"detect(): engrave open non contenuto in nessun part (source_ref={proxy.source_ref})"
    )


def _handle_engrave_closed(inner, part: ForgePart) -> None:
    """Inner da part.inners — contorno chiuso."""
    engraving = Engraving(
        closed=True,
        length=round(inner.polygon.exterior.length, 4),
        part_label=part.label,
        source_ref=inner.source_ref,
        polygon=inner.polygon,
    )
    part.engrave_lines.append(engraving)


# ---------------------------------------------------------------------------
# Assegnazione al part contenitore
# ---------------------------------------------------------------------------

def _assign_to_part(ce: ClassifiedEntity, result: ForgeResult) -> None:
    probe = _probe_point(ce)
    if probe is None:
        return

    work_type = ce.work_type.lower()

    for part in result.parts:
        if not part.outer.polygon.contains(probe):
            continue

        if work_type == "bending":
            part.bending_lines.append(
                _bending_line_from_data(ce.data, ce.source_ref, part.label)
            )
            if ce.source_ref is not None:
                part.entity_ids.add(id(ce.source_ref))

        _write_custom(ce, part)
        return

    result.warnings.append(
        f"detect(): forma {ce.work_type} non contenuta in nessun part "
        f"(source={ce.source}). Registrata in classified_entities."
    )


def _write_custom(ce: ClassifiedEntity, part: ForgePart) -> None:
    key_map = {
        "bending": "bending_lines",
        "marking": "marking_entities",
    }
    key = key_map.get(ce.work_type.lower(), f"{ce.work_type.lower()}_entities")

    if key not in part.custom:
        part.custom[key] = []

    part.custom[key].append({
        **ce.data,
        "confidence": ce.confidence,
        "source":     ce.source,
    })


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _probe_point(ce: ClassifiedEntity) -> Optional[Point]:
    if ce.representative_point is not None:
        return Point(ce.representative_point)
    if ce.polygon is not None:
        return ce.polygon.centroid
    return None


def _extract_data(proxy: OpenShape, work_type: str) -> dict:
    work_type = work_type.lower()
    pts = proxy.pts

    if len(pts) >= 2:
        rep = (
            sum(p[0] for p in pts) / len(pts),
            sum(p[1] for p in pts) / len(pts),
        )
    else:
        rep = pts[0] if pts else None

    if work_type == "bending" and proxy.shape_type == "line" and len(pts) >= 2:
        start = pts[0]
        end   = pts[-1]
        dx    = end[0] - start[0]
        dy    = end[1] - start[1]
        return {
            "start":                start,
            "end":                  end,
            "length":               round(proxy.length, 4),
            "angle_deg":            round(math.degrees(math.atan2(dy, dx)) % 180, 4),
            "representative_point": rep,
        }

    if work_type == "marking":
        return {
            "length":               round(proxy.length, 4),
            "representative_point": rep,
        }

    return {
        "representative_point": rep,
    }


def _extract_data_from_source(source_ref, work_type: str, polygon=None) -> dict:
    work_type = work_type.lower()

    rep = None
    if polygon is not None:
        c   = polygon.centroid
        rep = (c.x, c.y)

    if work_type == "marking":
        length = None
        if polygon is not None:
            length = round(polygon.exterior.length, 4)
        return {
            "length":               length,
            "representative_point": rep,
        }

    return {
        "representative_point": rep,
    }


def _bending_line_from_data(data: dict, source_ref, part_label: str) -> BendingLine:
    start = data["start"]
    end   = data["end"]
    return BendingLine(
        source_ref=source_ref,
        geometry=LineString([start, end]),
        length=data["length"],
        angle_deg=data["angle_deg"],
        part_label=part_label,
    )