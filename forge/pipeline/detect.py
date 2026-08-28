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
from ..model.engraving import Engraving
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
    engrave_tolerance: float = 1.0,
    deduplicate_boundary_open: bool = True,
    boundary_tolerance: float = 0.05,
) -> None:
    _detect_labeled(result)
    if deduplicate_boundary_open:
        _deduplicate_boundary_open_segments(result, tolerance=boundary_tolerance)
    _detect_bending(result, bending_tolerance=bending_tolerance)
    _detect_engrave(result, engrave_tolerance=engrave_tolerance)
    _detect_holes(result)


# ---------------------------------------------------------------------------
# Step 1 — labeled shapes
# ---------------------------------------------------------------------------

def _detect_labeled(result: ForgeResult) -> None:
    classified_ids = set()

    for proxy in result.trash_entities:
        if proxy.role == ContourRole.UNKNOWN:
            continue

        is_closed = getattr(proxy, "polygon", None) is not None

        if proxy.role == ContourRole.ENGRAVE:
            placed = (
                _handle_engrave_closed_trash(proxy, result) if is_closed
                else _handle_engrave_open(proxy, result)
            )
            if placed:
                classified_ids.add(id(proxy))
            continue

        if is_closed:
            work_type = proxy.role.value
            data = _extract_data_from_source(work_type, polygon=proxy.polygon)
            rep  = data.pop("representative_point", None)
            ce = ClassifiedEntity(
                work_type=work_type,
                confidence=1.0,
                source="labeled",
                data=data,
                polygon=proxy.polygon,
                representative_point=rep,
            )
            result.classified_entities.append(ce)
            _assign_to_part(ce, result)
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
    promoted_ids: set[int] = set()

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
                    promoted_ids.add(id(proxy))
                    break

    # La linea promossa a bending NON deve restare anche in trash: `to_dxf`
    # la scriverebbe due volte (LINE su Bending + LWPOLYLINE su Trash,
    # sovrapposte). Stesso pattern di `_detect_labeled`.
    if promoted_ids:
        result.trash_entities = [
            p for p in result.trash_entities if id(p) not in promoted_ids
        ]


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
# Step — inferenza engrave (PLACEHOLDER)
# ---------------------------------------------------------------------------

def _detect_engrave(result: ForgeResult, engrave_tolerance: float = 1.0) -> None:
    """
    Inferenza geometrica delle incisioni — NON ANCORA IMPLEMENTATA.

    Stesso pattern di `_detect_holes` / `_detect_bending`: le incisioni con
    ruolo esplicito (label_map) sono già state promosse da `_detect_labeled`
    con `source="labeled"`. Qui si guarda ciò che è rimasto non etichettato —
    `part.inners` con role UNKNOWN e `result.trash_entities` — e si promuove a
    `Engraving(source="geometric")` quello che geometricamente È un'incisione,
    es.:
      - inner contour costituito da due polilinee ~parallele a distanza
        < engrave_tolerance → traccia di incisione, non un inner/foro
      - coppie di segmenti aperti ravvicinati e paralleli nella trash

    Finché è un placeholder non muta nulla.
    """
    return


# ---------------------------------------------------------------------------
# Engrave handlers
# ---------------------------------------------------------------------------

def _engraving_from_open(proxy, part_label: str = "",
                         source: str = "labeled", confidence: float = 1.0) -> Engraving:
    pts = list(getattr(proxy, "pts", []) or [])
    return Engraving(
        role=ContourRole.ENGRAVE,
        segments=list(getattr(proxy, "segments", []) or []),
        length=round(getattr(proxy, "length", 0.0), 4),
        pts=pts,
        geometry=LineString(pts) if len(pts) >= 2 else None,
        part_label=part_label,
        source=source,
        confidence=confidence,
    )


def _engraving_from_closed(polygon, segments, part_label: str = "",
                           source: str = "labeled", confidence: float = 1.0) -> Engraving:
    return Engraving(
        role=ContourRole.ENGRAVE,
        segments=list(segments or []),
        length=round(polygon.exterior.length, 4),
        pts=list(polygon.exterior.coords),
        polygon=polygon,
        part_label=part_label,
        source=source,
        confidence=confidence,
    )


def _handle_engrave_open(proxy: OpenShape, result: ForgeResult) -> bool:
    """
    Smista una traccia engrave aperta per contenimento.

    Dentro un part → part.engrave_lines (ritorna True).
    Fuori da ogni part → resta trash: è geometria orfana come ogni altra
    entità che non sta dentro un outer (ritorna False).
    """
    if len(proxy.pts) >= 2:
        rep = (
            sum(p[0] for p in proxy.pts) / len(proxy.pts),
            sum(p[1] for p in proxy.pts) / len(proxy.pts),
        )
    else:
        rep = proxy.pts[0] if proxy.pts else None

    probe = Point(rep) if rep else None
    for part in result.parts:
        if probe and part.outer.polygon.contains(probe):
            part.engrave_lines.append(_engraving_from_open(proxy, part_label=part.label))
            return True

    return False


def _handle_engrave_closed_trash(proxy, result: ForgeResult) -> bool:
    """
    Come _handle_engrave_open ma per una traccia engrave già chiusa
    (CIRCLE / SPLINE chiusa su layer engrave). Contenimento sul
    representative point del polygon.
    """
    probe = proxy.polygon.representative_point()
    for part in result.parts:
        if part.outer.polygon.contains(probe):
            part.engrave_lines.append(_engraving_from_closed(
                proxy.polygon,
                getattr(proxy, "segments", []),
                part_label=part.label,
            ))
            return True
    return False


def _handle_engrave_closed(inner, part: ForgePart) -> None:
    part.engrave_lines.append(_engraving_from_closed(
        inner.polygon,
        getattr(inner, "segments", []),
        part_label=part.label,
    ))


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