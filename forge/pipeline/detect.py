

"""
pipeline/detect.py
------------------
Step semantico post-heal: rileva il significato delle forme geometriche.

Posizione nella pipeline:
    heal()      → geometria pura — crea Hole(hole_type=UNKNOWN, geometric_hint=...)
    detect()    → semantica — promuove Hole.hole_type al tipo definitivo
    inject()    → serializzazione dati CAM

Responsabilità di detect() sui fori:
    1. Labeled shapes (certezza 1.0)
       Forma con origin mappata in label_map → work_type promosso immediatamente.
       Priorità assoluta su hint geometrico e inferenza.

    2. Hint geometrico da heal() (certezza < 1.0)
       heal() ha già identificato la struttura: Hole.geometric_hint != ""
       detect() legge l'hint e promuove senza ricalcolare la geometria.
       Confidenza: countersink 0.85, threaded 0.80.

NON è responsabilità di detect():
    - costruire loop o topologia               → heal()
    - aprire o salvare file                    → il chiamante
    - scrivere layer/colore nel documento      → write()
    - serializzare metriche nel JSON           → inject()

Nota su label_map:
    label_map è una dict {origin: work_type} — in DXF origin è il layer,
    in SVG sarà il colore o la classe CSS.
    Viene passato a heal() e salvato in result.label_map.
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
from ..model.shape import OpenShape
from ..adapters.dxf.hole_detector import (
    is_threaded_hole,
)
from ..adapters.dxf.bending_adapter import bending_line_from_proxy
from ..rules.layers import VALID_WORK_TYPES

# work_type → hole_type per le forme foro con label esplicita
_WORK_TYPE_TO_HOLE_TYPE = {
    "countersink":   HOLE_TYPE_COUNTERSINK,
    "threaded_hole": HOLE_TYPE_THREADED,
}


# ---------------------------------------------------------------------------
# API pubblica
# ---------------------------------------------------------------------------

def detect(
    result:            ForgeResult,
    bending_tolerance: float = 1.0,
) -> None:
    """
    Rileva la semantica geometrica e popola part.bending_lines e part.custom.

    Legge label_map da result.label_map, popolato da heal().
    Idempotente per design.

    Args:
        result:            ForgeResult prodotto da heal()
        bending_tolerance: tolleranza mm per rilevamento linee di piega
    """
    label_map = result.label_map or {}

    if label_map:
        unknown = {v.lower() for v in label_map.values()} - VALID_WORK_TYPES
        if unknown:
            result.warnings.append(
                f"detect(): work_type sconosciuti in label_map: {unknown}. "
                f"Valori validi: {VALID_WORK_TYPES}"
            )

    if label_map:
        _detect_labeled(result, label_map)

    _detect_bending(result, bending_tolerance=bending_tolerance)

    _detect_holes(result)


# ---------------------------------------------------------------------------
# Step 1 — labeled shapes (certezza 1.0)
# ---------------------------------------------------------------------------

def _detect_labeled(
    result:    ForgeResult,
    label_map: dict,
) -> None:
    """
    Classifica le forme in trash_entities e i Hole con origin mappata in label_map.

    Per i Hole: promuove hole_type direttamente.
    Per le forme libere (bending, engrave, ecc.): crea ClassifiedEntity.
    """
    origin_to_work = {k.lower(): v.lower() for k, v in label_map.items()}
    classified_ids = set()

    # --- forme libere (bending, engrave, marking, ecc.) ---
    for proxy in result.trash_entities:
        if proxy.origin == "":
            continue
        work_type = origin_to_work.get(proxy.origin.lower())
        if work_type is None:
            continue
        data = _extract_data(proxy, work_type)
        ce   = ClassifiedEntity(
            source_ref=proxy.source_ref,
            work_type=work_type,
            confidence=1.0,
            source="labeled",
            data=data,
        )
        result.classified_entities.append(ce)
        _assign_to_part(ce, result)
        classified_ids.add(id(proxy))

    result.trash_entities = [
        p for p in result.trash_entities if id(p) not in classified_ids
    ]

    # --- Hole sui part: promozione diretta da label ---
    for part in result.parts:
        for hole in part.holes:
            work_type = origin_to_work.get(hole.origin.lower())
            if work_type is None:
                continue
            hole_type = _WORK_TYPE_TO_HOLE_TYPE.get(work_type)
            if hole_type is None:
                continue
            hole.hole_type  = hole_type
            hole.confidence = 1.0
            hole.source     = "labeled"

        # --- contorni inner su origin labeled → ClassifiedEntity ---
        remaining = []
        for inner in part.inners:
            work_type = origin_to_work.get(inner.origin.lower())
            if work_type is None:
                remaining.append(inner)
                continue
            # data = _extract_data_from_source(inner.source_ref, inner.origin, work_type)
            data = _extract_data_from_source(inner.source_ref, inner.origin, work_type, polygon=inner.polygon)
            ce = ClassifiedEntity(
                source_ref=inner.source_ref,
                work_type=work_type,
                confidence=1.0,
                source="labeled",
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

def _detect_bending(result: ForgeResult, bending_tolerance: float = 1.0) -> None:
    """
    Individua LINE interne all'outer di ogni part e popola part.bending_lines.
    """
    classified_ids = {id(ce.source_ref) for ce in result.classified_entities}

    for proxy in result.trash_entities:
        if proxy.shape_type != "line":
            continue
        if id(proxy.source_ref) in classified_ids:
            continue

        entity = proxy.source_ref
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

        if work_type == "bending" and ce.source_ref is not None:
            # source_ref è un'entità LINE — bending_line_from_proxy richiede proxy;
            # qui abbiamo già il source_ref direttamente, usiamo il costruttore interno
            part.bending_lines.append(_bending_line_from_source(ce.source_ref, part.label))
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
        "engrave": "engrave_entities",
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
    """Punto rappresentativo della ClassifiedEntity per il containment check."""
    if ce.source_ref is None:
        if ce.polygon is not None:
            return ce.polygon.centroid
        return None
    entity = ce.source_ref
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


def _extract_data(proxy: OpenShape, work_type: str) -> dict:
    """Estrae dati serializzabili da un proxy per ClassifiedEntity.data."""
    work_type = work_type.lower()

    if work_type == "bending" and proxy.shape_type == "line":
        entity = proxy.source_ref
        start  = (entity.dxf.start.x, entity.dxf.start.y)
        end    = (entity.dxf.end.x,   entity.dxf.end.y)
        geom   = LineString([start, end])
        dx     = end[0] - start[0]
        dy     = end[1] - start[1]
        return {
            "start":     start,
            "end":       end,
            "length":    round(geom.length, 4),
            "angle_deg": round(math.degrees(math.atan2(dy, dx)) % 180, 4),
            "origin":    proxy.origin,
        }

    if work_type in ("engrave", "marking"):
        return {
            "length": round(_shape_length(proxy.source_ref), 4) if proxy.source_ref is not None else None,
            "origin": proxy.origin,
        }

    return {"origin": proxy.origin}


def _extract_data_from_source(source_ref, origin: str, work_type: str, polygon=None) -> dict:
    work_type = work_type.lower()
    if work_type in ("engrave", "marking"):
        length = None
        if source_ref is not None:
            length = _shape_length(source_ref)
        elif polygon is not None:
            length = round(polygon.exterior.length, 4)  # ← fallback virtual
        return {
            "length": round(length, 4) if length is not None else None,
            "origin": origin,
        }
    return {"origin": origin}



def _shape_length(source_ref) -> Optional[float]:
    """Lunghezza approssimata di una forma da source_ref opaco."""
    if source_ref is None:
        return None
    try:
        dtype = source_ref.dxftype()
        # print(f"DEBUG _shape_length: {dtype}")
        if dtype == "LINE":
            dx = source_ref.dxf.end.x - source_ref.dxf.start.x
            dy = source_ref.dxf.end.y - source_ref.dxf.start.y
            return math.sqrt(dx * dx + dy * dy)
        if dtype == "ARC":
            start_a = math.radians(source_ref.dxf.start_angle)
            end_a   = math.radians(source_ref.dxf.end_angle)
            delta   = (end_a - start_a) % (2 * math.pi)
            return source_ref.dxf.radius * delta
    except Exception:
        pass
    return None


def _bending_line_from_source(source_ref, part_label: str) -> BendingLine:
    """
    Costruisce BendingLine direttamente da source_ref LINE.
    Usato quando _assign_to_part riceve una ClassifiedEntity già estratta
    (non un proxy grezzo).
    """
    entity = source_ref
    geom   = LineString([
        (entity.dxf.start.x, entity.dxf.start.y),
        (entity.dxf.end.x,   entity.dxf.end.y),
    ])
    return BendingLine(
        source_ref=entity,
        geometry=geom,
        length=geom.length,
        angle_deg=math.degrees(math.atan2(
            entity.dxf.end.y - entity.dxf.start.y,
            entity.dxf.end.x - entity.dxf.start.x,
        )) % 180,
        part_label=part_label,
    )