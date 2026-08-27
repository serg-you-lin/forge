"""
pipeline/detect.py
"""

from __future__ import annotations

import math
from typing import Optional

from shapely.geometry import LineString, Point

from ..model import (
    ForgeResult,
    ForgePart,
    BendingLine,
    ClassifiedEntity,
    HOLE_TYPE_PLAIN,
    HOLE_TYPE_COUNTERSINK,
    HOLE_TYPE_THREADED,
    HOLE_TYPE_UNKNOWN,
)
from ..model.engraving import EngravingClosed, EngravingOpen
from ..model.role import ContourRole
from ..adapters.bridge.shape import OpenShape
from ..core.classification.hole_detector import is_threaded_hole
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
    deduplicate_boundary_open: bool = True,
    boundary_tolerance: float = 0.05,
) -> None:
    _detect_labeled(result)
    if deduplicate_boundary_open:
        _deduplicate_boundary_open_segments(result, tolerance=boundary_tolerance)
    _detect_bending(result, bending_tolerance=bending_tolerance)
    _detect_holes(result)


# ---------------------------------------------------------------------------
# Step 1 — labeled shapes
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
                continue

            work_type = inner.role.value
            data = _extract_data_from_source(work_type, polygon=inner.polygon)
            rep  = data.pop("representative_point", None)
            ce = ClassifiedEntity(
                work_type=work_type,
                confidence=1.0,
                source="labeled",
                data=data,
                polygon=inner.polygon,
                representative_point=rep,
            )
            result.classified_entities.append(ce)
            _assign_to_part(ce, result)
        part.inners = remaining


# ---------------------------------------------------------------------------
# Step 2 — bending geometrico
# ---------------------------------------------------------------------------

def _deduplicate_boundary_open_segments(result: ForgeResult, tolerance: float = 0.05) -> None:
    if not result.parts or not result.trash_entities:
        return

    kept    = []
    removed = 0

    for proxy in result.trash_entities:
        if proxy.shape_type != "line" or len(proxy.pts) < 2:
            kept.append(proxy)
            continue

        segment = LineString([proxy.pts[0], proxy.pts[-1]])
        on_boundary = False
        for part in result.parts:
            if part.outer.polygon.boundary.buffer(tolerance).covers(segment):
                on_boundary = True
                break

        if on_boundary:
            removed += 1
        else:
            kept.append(proxy)

    if removed:
        result.warnings.append(
            f"detect(): rimossi {removed} segmenti aperti sovrapposti al bordo outer"
        )

    result.trash_entities = kept


def _detect_bending(result: ForgeResult, bending_tolerance: float = 1.0) -> None:
    for proxy in result.trash_entities:
        if proxy.shape_type != "line":
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
                    part.bending_lines.append(BendingLine(
                        role=ContourRole.BEND,
                        geometry=LineString([proxy.pts[0], proxy.pts[-1]]),
                        length=proxy.length,
                        angle_deg=math.degrees(math.atan2(
                            proxy.pts[-1][1] - proxy.pts[0][1],
                            proxy.pts[-1][0] - proxy.pts[0][0],
                        )) % 180,
                        part_label=part.label,
                    ))
                    break


# ---------------------------------------------------------------------------
# Step 3 — promozione fori
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

            if threaded:
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
    if len(proxy.pts) >= 2:
        rep = (
            sum(p[0] for p in proxy.pts) / len(proxy.pts),
            sum(p[1] for p in proxy.pts) / len(proxy.pts),
        )
    else:
        rep = proxy.pts[0] if proxy.pts else None

    engraving = EngravingOpen(
        role=ContourRole.ENGRAVE,
        length=round(proxy.length, 4),
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
        "detect(): engrave open non contenuto in nessun part"
    )


def _handle_engrave_closed(inner, part: ForgePart) -> None:
    engraving = EngravingClosed(
        role=ContourRole.ENGRAVE,
        polygon=inner.polygon,
        length=round(inner.polygon.exterior.length, 4),
        part_label=part.label,
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
            part.bending_lines.append(_bending_line_from_data(ce.data, part.label))

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

    return {"representative_point": rep}


def _extract_data_from_source(work_type: str, polygon=None) -> dict:
    work_type = work_type.lower()

    rep = None
    if polygon is not None:
        c   = polygon.centroid
        rep = (c.x, c.y)

    if work_type == "marking":
        length = round(polygon.exterior.length, 4) if polygon is not None else None
        return {
            "length":               length,
            "representative_point": rep,
        }

    return {"representative_point": rep}


def _bending_line_from_data(data: dict, part_label: str) -> BendingLine:
    start = data["start"]
    end   = data["end"]
    return BendingLine(
        role=ContourRole.BEND,
        geometry=LineString([start, end]),
        length=data["length"],
        angle_deg=data["angle_deg"],
        part_label=part_label,
    )