# """
# workflow/detection.py
# ---------------------
# Step semantico post-heal: rileva il significato delle entità geometriche.

# Posizione nella pipeline:
#     heal()      → geometria pura — crea Hole(hole_type=UNKNOWN, geometric_hint=...)
#     detect()    → semantica — promuove Hole.hole_type al tipo definitivo
#     inject()    → serializzazione dati CAM

# Responsabilità di detect() sui fori:
#     1. Special layers (certezza 1.0)
#        Hole su layer noto → hole_type promosso immediatamente.
#        Priorità assoluta su hint geometrico e inferenza.

#     2. Hint geometrico da heal() (certezza < 1.0)
#        heal() ha già identificato la struttura: Hole.geometric_hint != ""
#        detect() legge l'hint e promuove senza ricalcolare la geometria.
#        Confidenza: countersink 0.85, threaded 0.80.

# NON è responsabilità di detect():
#     - costruire loop o topologia               → heal()
#     - aprire o salvare file                    → il chiamante
#     - scrivere layer/colore nel DXF            → write()
#     - serializzare metriche nel JSON           → inject()

# Nota su special_layers:
#     special_layers viene passato a heal() e salvato in result.special_layers.
#     detect() lo legge da lì — non va passato di nuovo.
# """

# from __future__ import annotations

# import math
# from typing import Optional

# from shapely.geometry import LineString, Point

# from ..core.models import (
#     ForgeResult,
#     ForgePart,
#     ForgeContour,
#     # GeometryHints,
#     Hole,
#     BendingLine,
#     ClassifiedEntity,
#     HOLE_TYPE_PLAIN,
#     HOLE_TYPE_COUNTERSINK,
#     HOLE_TYPE_THREADED,
#     HOLE_TYPE_UNKNOWN,
# )
# # from ..core.geometry import (
# #     is_threaded_hole,
# # )
# from ..adapters.dxf.geometry_adapter import (
#     is_threaded_hole,
#     is_threaded_arc,
#     is_countersink_outer,
#     entity_length,
#     get_representative_point,
#     entity_midpoint,
# )
# from ..rules.layers import WORK_TYPE_TO_LAYER, VALID_WORK_TYPES

# # Work type → hole_type: mappa per special_layers sui fori
# _WORK_TYPE_TO_HOLE_TYPE = {
#     "countersink":   HOLE_TYPE_COUNTERSINK,
#     "threaded_hole": HOLE_TYPE_THREADED,
# }


# # ---------------------------------------------------------------------------
# # API pubblica
# # ---------------------------------------------------------------------------

# def detect(
#     result:            ForgeResult,
#     msp,
#     bending_tolerance: float = 1.0,
# ) -> None:
#     """
#     Rileva la semantica geometrica e popola geometry_hints e part.custom.

#     Legge special_layers da result.special_layers, popolato da heal().
#     Sovrascrive geometry_hints esistenti — idempotente per design.

#     Args:
#         result:            ForgeResult prodotto da heal()
#         msp:               modelspace ezdxf — stesso oggetto passato a heal()
#         bending_tolerance: tolleranza mm per rilevamento linee di piega
#     """
#     sl = result.special_layers or {}

#     if sl:
#         unknown = {v.lower() for v in sl.values()} - VALID_WORK_TYPES
#         if unknown:
#             result.warnings.append(
#                 f"detect(): work_type sconosciuti in special_layers: {unknown}. "
#                 f"Valori validi: {VALID_WORK_TYPES}"
#             )

#     all_arcs = list(msp.query("ARC"))

#     if sl:
#         _detect_special_layers(result, msp, sl)

#     _detect_bending_lines(result, bending_tolerance=bending_tolerance)

#     _detect_holes(result, all_arcs)


# # ---------------------------------------------------------------------------
# # Step 1 — special layers (certezza 1.0)
# # ---------------------------------------------------------------------------

# def _detect_special_layers(
#     result:         ForgeResult,
#     msp,
#     special_layers: dict,
# ) -> None:
#     """
#     Classifica entità trash e Hole su layer speciali noti.

#     Per i Hole: promuove hole_type direttamente.
#     Per le entità trash (bending, engrave, ecc.): crea ClassifiedEntity.
#     """
#     layer_to_work  = {k.lower(): v.lower() for k, v in special_layers.items()}
#     classified_ids = set()

#     # --- entità trash (bending, engrave, marking, ecc.) ---
#     for entity in result.trash_entities:
#         if not entity.dxf.hasattr("layer"):
#             continue
#         layer     = entity.dxf.layer.lower()
#         work_type = layer_to_work.get(layer)
#         if work_type is None:
#             continue
#         data = _extract_data(entity, work_type)
#         ce   = ClassifiedEntity(
#             entity=entity,
#             work_type=work_type,
#             confidence=1.0,
#             source="special_layers",
#             data=data,
#         )
#         result.classified_entities.append(ce)
#         _assign_to_part(ce, result)
#         classified_ids.add(id(entity))

#     result.trash_entities = [
#         e for e in result.trash_entities if id(e) not in classified_ids
#     ]

#     # --- Hole sui part: promozione diretta da layer speciale ---
#     for part in result.parts:
#         for hole in part.holes:
#             check_layer = (hole.source_layer or hole.layer).lower()
#             work_type   = layer_to_work.get(check_layer)
#             if work_type is None:
#                 continue
#             hole_type = _WORK_TYPE_TO_HOLE_TYPE.get(work_type)
#             if hole_type is None:
#                 continue
#             hole.hole_type  = hole_type
#             hole.confidence = 1.0
#             hole.source     = "special_layers"

#         # --- contorni inner non-foro su layer speciale ---
#         remaining = []
#         for inner in part.inners:
#             check_layer = (inner.source_layer or inner.layer).lower()
#             work_type   = layer_to_work.get(check_layer)
#             if work_type is None:
#                 remaining.append(inner)
#                 continue
#             data = _extract_data(inner.entity, work_type) if inner.entity is not None else {
#                 "length": round(inner.polygon.exterior.length, 4),
#                 "layer":  inner.source_layer,
#             }
#             ce = ClassifiedEntity(
#                 entity=inner.entity,
#                 work_type=work_type,
#                 confidence=1.0,
#                 source="special_layers",
#                 data=data,
#                 polygon=inner.polygon,
#             )
#             result.classified_entities.append(ce)
#             if inner.vs_id is not None:
#                 result._suppressed_vs_ids.add(inner.vs_id)
#             _assign_to_part(ce, result)
#         part.inners = remaining


# # ---------------------------------------------------------------------------
# # Step 2 — bending geometrico
# # ---------------------------------------------------------------------------

# def _detect_bending_lines(result: ForgeResult, bending_tolerance: float = 1.0) -> None:
#     classified_ids = {id(ce.entity) for ce in result.classified_entities}

#     for entity in result.trash_entities:
#         if entity.dxftype() != "LINE":
#             continue
#         if id(entity) in classified_ids:
#             continue

#         s = Point(entity.dxf.start.x, entity.dxf.start.y)
#         e = Point(entity.dxf.end.x,   entity.dxf.end.y)

#         for part in result.parts:
#             outer    = part.outer.polygon
#             boundary = outer.boundary

#             if s.distance(e) < bending_tolerance:
#                 continue
#             if boundary.distance(s) < 1.0 and boundary.distance(e) < 1.0:
#                 midpoint = Point(
#                     (entity.dxf.start.x + entity.dxf.end.x) / 2,
#                     (entity.dxf.start.y + entity.dxf.end.y) / 2,
#                 )
#                 if outer.contains(midpoint):
#                     geom = LineString([
#                         (entity.dxf.start.x, entity.dxf.start.y),
#                         (entity.dxf.end.x,   entity.dxf.end.y),
#                     ])
#                     angle = math.degrees(math.atan2(
#                         entity.dxf.end.y - entity.dxf.start.y,
#                         entity.dxf.end.x - entity.dxf.start.x,
#                     )) % 180

#                     bl = BendingLine(
#                         entity=entity,
#                         geometry=geom,
#                         length=geom.length,
#                         layer=entity.dxf.layer,
#                         angle_deg=angle,
#                         part_label=part.label,
#                     )
#                     part.bending_lines.append(bl)
#                     break


# # ---------------------------------------------------------------------------
# # Step 3 — promozione fori da geometric_hint
# # ---------------------------------------------------------------------------

# def _detect_holes(result: ForgeResult, all_arcs: list) -> None:
#     for part in result.parts:
#         for hole in part.holes:
#             if hole.source == "special_layers":
#                 continue
#             if hole.hole_type != HOLE_TYPE_UNKNOWN:
#                 continue

#             if hole.geometric_hint == "countersink":
#                 hole.hole_type  = HOLE_TYPE_COUNTERSINK
#                 hole.confidence = 0.85
#                 hole.source     = "geometric"
#                 continue

#             if hole.geometric_hint == "threaded":
#                 hole.hole_type  = HOLE_TYPE_THREADED
#                 hole.confidence = 0.85
#                 hole.source     = "geometric"
#                 continue

#             if hole.entity is not None and is_threaded_hole(hole.entity, all_arcs):
#                 hole.hole_type  = HOLE_TYPE_THREADED
#                 hole.confidence = 0.80
#                 hole.source     = "geometric"
#             else:
#                 hole.hole_type  = HOLE_TYPE_PLAIN
#                 hole.confidence = 1.0
#                 hole.source     = "geometric"


# # ---------------------------------------------------------------------------
# # Assegnazione al part contenitore
# # ---------------------------------------------------------------------------

# def _assign_to_part(ce: ClassifiedEntity, result: ForgeResult) -> None:
#     probe = _entity_probe_point(ce)
#     if probe is None:
#         return

#     work_type = ce.work_type.lower()

#     for part in result.parts:
#         if not part.outer.polygon.contains(probe):
#             continue

#         if work_type == "bending":
#             part.geometry_hints.bend_line_ids.add(id(ce.entity))
#             part.entity_ids.add(id(ce.entity))

#         _write_custom(ce, part)
#         return

#     result.warnings.append(
#         f"detect(): entità {ce.work_type} non contenuta in nessun part "
#         f"(source={ce.source}). Registrata in classified_entities."
#     )


# def _write_custom(ce: ClassifiedEntity, part: ForgePart) -> None:
#     key_map = {
#         "bending": "bending_lines",
#         "engrave": "engrave_entities",
#         "marking": "marking_entities",
#     }

#     work_type = ce.work_type.lower()
#     key       = key_map.get(work_type, f"{work_type}_entities")

#     if key not in part.custom:
#         part.custom[key] = []

#     part.custom[key].append({
#         **ce.data,
#         "confidence": ce.confidence,
#         "source":     ce.source,
#     })


# # ---------------------------------------------------------------------------
# # Helpers
# # ---------------------------------------------------------------------------

# def _extract_data(entity, work_type: str) -> dict:
#     work_type = work_type.lower()

#     if work_type == "bending" and entity is not None and entity.dxftype() == "LINE":
#         start = (entity.dxf.start.x, entity.dxf.start.y)
#         end   = (entity.dxf.end.x,   entity.dxf.end.y)
#         geom  = LineString([start, end])
#         dx    = end[0] - start[0]
#         dy    = end[1] - start[1]
#         return {
#             "start":     start,
#             "end":       end,
#             "length":    round(geom.length, 4),
#             "angle_deg": round(math.degrees(math.atan2(dy, dx)) % 180, 4),
#             "layer":     entity.dxf.layer,
#         }

#     if work_type in ("engrave", "marking"):
#         return {
#             "length": round(_entity_length(entity), 4) if entity is not None and _entity_length(entity) else None,
#             "layer":  entity.dxf.layer if entity is not None and entity.dxf.hasattr("layer") else "",
#         }

#     return {
#         "layer": entity.dxf.layer if entity is not None and entity.dxf.hasattr("layer") else "",
#     }


# def _entity_probe_point(ce: ClassifiedEntity) -> Optional[Point]:
#     if ce.entity is None:
#         if ce.polygon is not None:
#             return ce.polygon.centroid
#         return None
#     entity = ce.entity
#     try:
#         dtype = entity.dxftype()
#         if dtype == "LINE":
#             return Point(
#                 (entity.dxf.start.x + entity.dxf.end.x) / 2,
#                 (entity.dxf.start.y + entity.dxf.end.y) / 2,
#             )
#         if dtype in ("CIRCLE", "ARC"):
#             return Point(entity.dxf.center.x, entity.dxf.center.y)
#         if dtype == "LWPOLYLINE":
#             pts = list(entity.get_points())
#             if pts:
#                 return Point(
#                     sum(p[0] for p in pts) / len(pts),
#                     sum(p[1] for p in pts) / len(pts),
#                 )
#     except Exception:
#         pass
#     return None


# def _entity_length(entity) -> Optional[float]:
#     try:
#         dtype = entity.dxftype()
#         if dtype == "LINE":
#             dx = entity.dxf.end.x - entity.dxf.start.x
#             dy = entity.dxf.end.y - entity.dxf.start.y
#             return math.sqrt(dx * dx + dy * dy)
#         if dtype == "ARC":
#             start_a = math.radians(entity.dxf.start_angle)
#             end_a   = math.radians(entity.dxf.end_angle)
#             delta   = (end_a - start_a) % (2 * math.pi)
#             return entity.dxf.radius * delta
#     except Exception:
#         pass
#     return None



# def _make_bending_line(entity, part_label: str) -> BendingLine:
#     geom = LineString([
#         (entity.dxf.start.x, entity.dxf.start.y),
#         (entity.dxf.end.x,   entity.dxf.end.y),
#     ])
#     return BendingLine(
#         entity=entity,
#         geometry=geom,
#         length=geom.length,
#         layer=entity.dxf.layer,
#         angle_deg=math.degrees(math.atan2(
#             entity.dxf.end.y - entity.dxf.start.y,
#             entity.dxf.end.x - entity.dxf.start.x,
#         )) % 180,
#         part_label=part_label,
#     )


"""
workflow/detection.py
---------------------
Step semantico post-heal: rileva il significato delle entità geometriche.

Posizione nella pipeline:
    heal()      → geometria pura — crea Hole(hole_type=UNKNOWN, geometric_hint=...)
    detect()    → semantica — promuove Hole.hole_type al tipo definitivo
    inject()    → serializzazione dati CAM

Responsabilità di detect() sui fori:
    1. Special layers (certezza 1.0)
       Hole su layer noto → hole_type promosso immediatamente.
       Priorità assoluta su hint geometrico e inferenza.

    2. Hint geometrico da heal() (certezza < 1.0)
       heal() ha già identificato la struttura: Hole.geometric_hint != ""
       detect() legge l'hint e promuove senza ricalcolare la geometria.
       Confidenza: countersink 0.85, threaded 0.80.

NON è responsabilità di detect():
    - costruire loop o topologia               → heal()
    - aprire o salvare file                    → il chiamante
    - scrivere layer/colore nel DXF            → write()
    - serializzare metriche nel JSON           → inject()

Nota su special_layers:
    special_layers viene passato a heal() e salvato in result.special_layers.
    detect() lo legge da lì — non va passato di nuovo.
"""

from __future__ import annotations

import math
from typing import Optional

from shapely.geometry import LineString, Point

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
from ..adapters.dxf.geometry_adapter import (
    is_threaded_hole,
    is_threaded_arc,
    is_countersink_outer,
    entity_length,
    get_representative_point,
    entity_midpoint,
)
from ..rules.layers import WORK_TYPE_TO_LAYER, VALID_WORK_TYPES

# Work type → hole_type: mappa per special_layers sui fori
_WORK_TYPE_TO_HOLE_TYPE = {
    "countersink":   HOLE_TYPE_COUNTERSINK,
    "threaded_hole": HOLE_TYPE_THREADED,
}


# ---------------------------------------------------------------------------
# API pubblica
# ---------------------------------------------------------------------------

def detect(
    result:            ForgeResult,
    msp,
    bending_tolerance: float = 1.0,
) -> None:
    """
    Rileva la semantica geometrica e popola part.bending_lines e part.custom.

    Legge special_layers da result.special_layers, popolato da heal().
    Idempotente per design.

    Args:
        result:            ForgeResult prodotto da heal()
        msp:               modelspace ezdxf — stesso oggetto passato a heal()
        bending_tolerance: tolleranza mm per rilevamento linee di piega
    """
    sl = result.special_layers or {}

    if sl:
        unknown = {v.lower() for v in sl.values()} - VALID_WORK_TYPES
        if unknown:
            result.warnings.append(
                f"detect(): work_type sconosciuti in special_layers: {unknown}. "
                f"Valori validi: {VALID_WORK_TYPES}"
            )

    all_arcs = list(msp.query("ARC"))

    if sl:
        _detect_special_layers(result, msp, sl)

    _detect_bending_lines(result, bending_tolerance=bending_tolerance)

    _detect_holes(result, all_arcs)


# ---------------------------------------------------------------------------
# Step 1 — special layers (certezza 1.0)
# ---------------------------------------------------------------------------

def _detect_special_layers(
    result:         ForgeResult,
    msp,
    special_layers: dict,
) -> None:
    """
    Classifica entità trash e Hole su layer speciali noti.

    Per i Hole: promuove hole_type direttamente.
    Per le entità trash (bending, engrave, ecc.): crea ClassifiedEntity.
    """
    layer_to_work  = {k.lower(): v.lower() for k, v in special_layers.items()}
    classified_ids = set()

    # --- entità trash (bending, engrave, marking, ecc.) ---
    for entity in result.trash_entities:
        if not entity.dxf.hasattr("layer"):
            continue
        layer     = entity.dxf.layer.lower()
        work_type = layer_to_work.get(layer)
        if work_type is None:
            continue
        data = _extract_data(entity, work_type)
        ce   = ClassifiedEntity(
            entity=entity,
            work_type=work_type,
            confidence=1.0,
            source="special_layers",
            data=data,
        )
        result.classified_entities.append(ce)
        _assign_to_part(ce, result)
        classified_ids.add(id(entity))

    result.trash_entities = [
        e for e in result.trash_entities if id(e) not in classified_ids
    ]

    # --- Hole sui part: promozione diretta da layer speciale ---
    for part in result.parts:
        for hole in part.holes:
            check_layer = (hole.source_layer or hole.layer).lower()
            work_type   = layer_to_work.get(check_layer)
            if work_type is None:
                continue
            hole_type = _WORK_TYPE_TO_HOLE_TYPE.get(work_type)
            if hole_type is None:
                continue
            hole.hole_type  = hole_type
            hole.confidence = 1.0
            hole.source     = "special_layers"

        # --- contorni inner non-foro su layer speciale ---
        remaining = []
        for inner in part.inners:
            check_layer = (inner.source_layer or inner.layer).lower()
            work_type   = layer_to_work.get(check_layer)
            if work_type is None:
                remaining.append(inner)
                continue
            data = _extract_data(inner.entity, work_type) if inner.entity is not None else {
                "length": round(inner.polygon.exterior.length, 4),
                "layer":  inner.source_layer,
            }
            ce = ClassifiedEntity(
                entity=inner.entity,
                work_type=work_type,
                confidence=1.0,
                source="special_layers",
                data=data,
                polygon=inner.polygon,
            )
            result.classified_entities.append(ce)
            if inner.vs_id is not None:
                result._suppressed_vs_ids.add(inner.vs_id)
            _assign_to_part(ce, result)
        part.inners = remaining


# ---------------------------------------------------------------------------
# Step 2 — bending geometrico
# ---------------------------------------------------------------------------

def _detect_bending_lines(result: ForgeResult, bending_tolerance: float = 1.0) -> None:
    """
    Individua LINE interne all'outer di ogni part e popola part.bending_lines.
    """
    classified_ids = {id(ce.entity) for ce in result.classified_entities}

    for entity in result.trash_entities:
        if entity.dxftype() != "LINE":
            continue
        if id(entity) in classified_ids:
            continue

        s = Point(entity.dxf.start.x, entity.dxf.start.y)
        e = Point(entity.dxf.end.x,   entity.dxf.end.y)

        for part in result.parts:
            outer    = part.outer.polygon
            boundary = outer.boundary

            if s.distance(e) < bending_tolerance:
                continue
            if boundary.distance(s) < 1.0 and boundary.distance(e) < 1.0:
                midpoint = Point(
                    (entity.dxf.start.x + entity.dxf.end.x) / 2,
                    (entity.dxf.start.y + entity.dxf.end.y) / 2,
                )
                if outer.contains(midpoint):
                    part.bending_lines.append(_make_bending_line(entity, part.label))
                    break


# ---------------------------------------------------------------------------
# Step 3 — promozione fori da geometric_hint
# ---------------------------------------------------------------------------

def _detect_holes(result: ForgeResult, all_arcs: list) -> None:
    for part in result.parts:
        for hole in part.holes:
            if hole.source == "special_layers":
                continue
            if hole.hole_type != HOLE_TYPE_UNKNOWN:
                continue

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

            if hole.entity is not None and is_threaded_hole(hole.entity, all_arcs):
                hole.hole_type  = HOLE_TYPE_THREADED
                hole.confidence = 0.80
                hole.source     = "geometric"
            else:
                hole.hole_type  = HOLE_TYPE_PLAIN
                hole.confidence = 1.0
                hole.source     = "geometric"


# ---------------------------------------------------------------------------
# Assegnazione al part contenitore
# ---------------------------------------------------------------------------

def _assign_to_part(ce: ClassifiedEntity, result: ForgeResult) -> None:
    probe = _entity_probe_point(ce)
    if probe is None:
        return

    work_type = ce.work_type.lower()

    for part in result.parts:
        if not part.outer.polygon.contains(probe):
            continue

        if work_type == "bending" and ce.entity is not None:
            part.bending_lines.append(_make_bending_line(ce.entity, part.label))
            part.entity_ids.add(id(ce.entity))

        _write_custom(ce, part)
        return

    result.warnings.append(
        f"detect(): entità {ce.work_type} non contenuta in nessun part "
        f"(source={ce.source}). Registrata in classified_entities."
    )


def _write_custom(ce: ClassifiedEntity, part: ForgePart) -> None:
    key_map = {
        "bending": "bending_lines",
        "engrave": "engrave_entities",
        "marking": "marking_entities",
    }

    work_type = ce.work_type.lower()
    key       = key_map.get(work_type, f"{work_type}_entities")

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

def _make_bending_line(entity, part_label: str) -> BendingLine:
    """Costruisce una BendingLine da una entità LINE ezdxf."""
    geom = LineString([
        (entity.dxf.start.x, entity.dxf.start.y),
        (entity.dxf.end.x,   entity.dxf.end.y),
    ])
    return BendingLine(
        entity=entity,
        geometry=geom,
        length=geom.length,
        layer=entity.dxf.layer,
        angle_deg=math.degrees(math.atan2(
            entity.dxf.end.y - entity.dxf.start.y,
            entity.dxf.end.x - entity.dxf.start.x,
        )) % 180,
        part_label=part_label,
    )


def _extract_data(entity, work_type: str) -> dict:
    work_type = work_type.lower()

    if work_type == "bending" and entity is not None and entity.dxftype() == "LINE":
        start = (entity.dxf.start.x, entity.dxf.start.y)
        end   = (entity.dxf.end.x,   entity.dxf.end.y)
        geom  = LineString([start, end])
        dx    = end[0] - start[0]
        dy    = end[1] - start[1]
        return {
            "start":     start,
            "end":       end,
            "length":    round(geom.length, 4),
            "angle_deg": round(math.degrees(math.atan2(dy, dx)) % 180, 4),
            "layer":     entity.dxf.layer,
        }

    if work_type in ("engrave", "marking"):
        return {
            "length": round(_entity_length(entity), 4) if entity is not None and _entity_length(entity) else None,
            "layer":  entity.dxf.layer if entity is not None and entity.dxf.hasattr("layer") else "",
        }

    return {
        "layer": entity.dxf.layer if entity is not None and entity.dxf.hasattr("layer") else "",
    }


def _entity_probe_point(ce: ClassifiedEntity) -> Optional[Point]:
    if ce.entity is None:
        if ce.polygon is not None:
            return ce.polygon.centroid
        return None
    entity = ce.entity
    try:
        dtype = entity.dxftype()
        if dtype == "LINE":
            return Point(
                (entity.dxf.start.x + entity.dxf.end.x) / 2,
                (entity.dxf.start.y + entity.dxf.end.y) / 2,
            )
        if dtype in ("CIRCLE", "ARC"):
            return Point(entity.dxf.center.x, entity.dxf.center.y)
        if dtype == "LWPOLYLINE":
            pts = list(entity.get_points())
            if pts:
                return Point(
                    sum(p[0] for p in pts) / len(pts),
                    sum(p[1] for p in pts) / len(pts),
                )
    except Exception:
        pass
    return None


def _entity_length(entity) -> Optional[float]:
    try:
        dtype = entity.dxftype()
        if dtype == "LINE":
            dx = entity.dxf.end.x - entity.dxf.start.x
            dy = entity.dxf.end.y - entity.dxf.start.y
            return math.sqrt(dx * dx + dy * dy)
        if dtype == "ARC":
            start_a = math.radians(entity.dxf.start_angle)
            end_a   = math.radians(entity.dxf.end_angle)
            delta   = (end_a - start_a) % (2 * math.pi)
            return entity.dxf.radius * delta
    except Exception:
        pass
    return None