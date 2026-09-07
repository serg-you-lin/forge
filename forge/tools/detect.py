"""
forge/tools/detect.py
"""

from __future__ import annotations

import math
from typing import Optional

from shapely.geometry import LineString, Point

from ..model import (
    ForgeResult,
    ForgeCluster,
    BendingLine,
    ClassifiedEntity,
    HOLE_TYPE_PLAIN,
    HOLE_TYPE_COUNTERSINK,
    HOLE_TYPE_THREADED,
)
from ..model.engraving import Engraving
from ..model.feature import OpenFeature
from ..model.role import ContourRole
from ..core.classification.hole_detector import is_threaded_hole
from ..core.geometry import (
    track_points, track_length, track_shape_type, circular_geometry,
)
from ..rules.thresholds import STRUCTURAL_ROLES, HOLE_DIAMETER_THRESHOLD


# Lane geometriche attivabili da detect(). `detect(result)` nudo non ne esegue
# nessuna: fa solo la lane label_map (autoritativa) + la pulizia topologia.
ALL_FEATURES = frozenset({"holes", "bending", "engrave"})


def _normalize_features(features) -> frozenset:
    """
    Normalizza l'argomento `features` di detect() in un set di stringhe.

    Accetta: None/() → nessuna lane; True o "all"/"*" → tutte;
    una stringa singola ("holes"); un iterabile di stringhe.
    """
    if features is None:
        return frozenset()
    if features is True:
        return ALL_FEATURES
    if isinstance(features, str):
        f = features.strip().lower()
        return ALL_FEATURES if f in ("all", "*") else frozenset({f})
    return frozenset(str(f).strip().lower() for f in features)


def _proxy_pts(proxy) -> list:
    """Vertici di un proxy aperto (OpenFeature), derivati dai suoi segmenti nativi."""
    return track_points(getattr(proxy, "segments", []) or [])

_ROLE_TO_HOLE_TYPE = {
    ContourRole.COUNTERSINK:   HOLE_TYPE_COUNTERSINK,
    ContourRole.THREADED_HOLE: HOLE_TYPE_THREADED,
}


# ---------------------------------------------------------------------------
# API pubblica
# ---------------------------------------------------------------------------

def detect(
    result:            ForgeResult,
    features=None,
    *,
    max_drill_diameter: float = HOLE_DIAMETER_THRESHOLD,
    bending_tolerance: float = 1.0,
    engrave_tolerance: float = 1.0,
    deduplicate_boundary_open: bool = True,
    boundary_tolerance: float = 0.05,
) -> ForgeResult:
    """
    Classifica le feature dentro le parti già trovate da heal().

    `detect(result)` nudo esegue solo la lane `label_map` (autoritativa) e la
    pulizia della topologia: i contorni circolari restano `inners`, nessun
    `Hole`. È il default per il taglio laser (`laser-cutting-default`).

    Le lane geometriche sono opt-in via `features`:
        detect(result, "holes")           → promozione fori (Ø < max_drill_diameter)
        detect(result, "all")             → fori + pieghe + incisioni
        detect(result, {"holes", "bending"})

    `max_drill_diameter` (default `HOLE_DIAMETER_THRESHOLD`, 32.1 mm) è un
    parametro di processo: sotto soglia il contorno circolare è un foro da
    punta, sopra resta un contorno interno.

    Muta `result` in-place (parti, trash_entities, classified_entities) e lo
    ritorna, così la catena resta esplicita: `result = forge.detect(result)`.
    """
    feats = _normalize_features(features)

    _detect_labeled(result)
    if deduplicate_boundary_open:
        _deduplicate_boundary_open_segments(result, tolerance=boundary_tolerance)
    if "bending" in feats:
        _detect_bending(result, bending_tolerance=bending_tolerance)
    if "engrave" in feats:
        _detect_engrave(result, engrave_tolerance=engrave_tolerance)
    if "holes" in feats:
        _detect_holes(result, max_drill_diameter=max_drill_diameter)
    return result


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

    _LABELED_HOLE_ROLES = (
        ContourRole.HOLE, ContourRole.COUNTERSINK, ContourRole.THREADED_HOLE,
    )

    for cluster in result.clusters:
        remaining = []
        for inner in cluster.inners:
            # Lane label_map (autoritativa): un contorno con ruolo foro
            # assegnato da label_map diventa un Hole a prescindere dai
            # `features` richiesti (D15).
            if inner.role in _LABELED_HOLE_ROLES:
                cluster.holes.append(_labeled_hole_from_contour(inner))
                continue

            if inner.role == ContourRole.UNKNOWN or inner.role in STRUCTURAL_ROLES:
                remaining.append(inner)
                continue

            if inner.role == ContourRole.ENGRAVE:
                _handle_engrave_closed(inner, cluster)
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
        cluster.inners = remaining


# ---------------------------------------------------------------------------
# Step 2 — bending geometrico
# ---------------------------------------------------------------------------

def _deduplicate_boundary_open_segments(result: ForgeResult, tolerance: float = 0.05) -> None:
    if not result.clusters or not result.trash_entities:
        return

    kept    = []
    removed = 0

    for proxy in result.trash_entities:
        pts = _proxy_pts(proxy)
        if track_shape_type(pts) != "line" or len(pts) < 2:
            kept.append(proxy)
            continue

        segment = LineString([pts[0], pts[-1]])
        on_boundary = False
        for cluster in result.clusters:
            if cluster.outer.polygon.boundary.buffer(tolerance).covers(segment):
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
        pts = _proxy_pts(proxy)
        if track_shape_type(pts) != "line" or len(pts) < 2:
            continue
        length = track_length(pts)
        if length < bending_tolerance:
            continue

        s = Point(pts[0])
        e = Point(pts[-1])

        for cluster in result.clusters:
            outer    = cluster.outer.polygon
            boundary = outer.boundary

            if boundary.distance(s) < 1.0 and boundary.distance(e) < 1.0:
                midpoint = Point(
                    (pts[0][0] + pts[-1][0]) / 2,
                    (pts[0][1] + pts[-1][1]) / 2,
                )
                if outer.contains(midpoint):
                    cluster.bending_lines.append(BendingLine(
                        role=ContourRole.BEND,
                        geometry=LineString([pts[0], pts[-1]]),
                        length=length,
                        angle_deg=math.degrees(math.atan2(
                            pts[-1][1] - pts[0][1],
                            pts[-1][0] - pts[0][0],
                        )) % 180,
                        cluster_label=cluster.label,
                        source="geometric",
                        confidence=0.9,
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

_CONCENTRIC_TOLERANCE = 1.0   # mm — distanza max fra i centri per un countersink


def _detect_holes(result: ForgeResult, max_drill_diameter: float = HOLE_DIAMETER_THRESHOLD) -> None:
    """
    Lane geometrica: promuove a `Hole` i contorni interni circolari.

    heal() non produce più `Hole` (D15): consegna solo l'albero di contenimento
    con `cluster.inners` piatto. Qui:
      - coppie concentriche (cerchio piccolo dentro cerchio grande) → countersink
        (il piccolo diventa `Hole`, l'anello grande viene assorbito);
      - contorni circolari con Ø < `max_drill_diameter` → foro (plain / threaded);
      - Ø >= `max_drill_diameter` → restano `ForgeContour` in `cluster.inners`.
    """
    for cluster in result.clusters:
        _promote_geometric_holes(cluster, result, max_drill_diameter)


def _circular_inners(cluster: ForgeCluster) -> list:
    """(contour, diameter, center) per ogni inner geometricamente circolare."""
    out = []
    for c in cluster.inners:
        if c.role not in (ContourRole.UNKNOWN, ContourRole.INNER):
            continue
        dia, ctr = circular_geometry(c.polygon, getattr(c, "segments", []))
        if dia is not None:
            out.append((c, dia, ctr))
    return out


def _promote_geometric_holes(cluster: ForgeCluster, result: ForgeResult,
                             max_drill_diameter: float) -> None:
    circ = _circular_inners(cluster)
    if not circ:
        return

    swallowed: set = set()      # id(contour) degli anelli esterni di countersink
    promoted:  dict = {}        # id(contour) -> Hole

    # --- countersink: cerchio piccolo concentrico dentro cerchio grande ---
    for outer_c, outer_d, outer_ctr in circ:
        for inner_c, inner_d, inner_ctr in circ:
            if inner_c is outer_c or inner_d >= outer_d:
                continue
            if id(inner_c) in promoted or id(outer_c) in swallowed:
                continue
            if not outer_c.polygon.contains(inner_c.polygon):
                continue
            if math.hypot(outer_ctr[0] - inner_ctr[0],
                          outer_ctr[1] - inner_ctr[1]) > _CONCENTRIC_TOLERANCE:
                continue
            swallowed.add(id(outer_c))
            promoted[id(inner_c)] = _hole_from_contour(
                inner_c, inner_d, inner_ctr,
                hole_type=HOLE_TYPE_COUNTERSINK, confidence=0.85,
                geometric_hint="countersink", outer_diameter=outer_d,
            )

    # --- fori piatti / filettati ---
    for c, dia, ctr in circ:
        if id(c) in promoted or id(c) in swallowed:
            continue
        if dia >= max_drill_diameter:
            continue    # sopra la capacità di foratura → resta contorno interno
        threaded = is_threaded_hole(
            center=ctr, radius=dia / 2, all_arcs=result.all_arcs,
        )
        promoted[id(c)] = _hole_from_contour(
            c, dia, ctr,
            hole_type=HOLE_TYPE_THREADED if threaded else HOLE_TYPE_PLAIN,
            confidence=0.80 if threaded else 1.0,
        )

    if not promoted and not swallowed:
        return

    new_inners = []
    for c in cluster.inners:
        if id(c) in swallowed:
            continue
        hole = promoted.get(id(c))
        if hole is not None:
            cluster.holes.append(hole)
        else:
            new_inners.append(c)
    cluster.inners = new_inners


def _hole_from_contour(contour, diameter, center, *, hole_type, confidence,
                       geometric_hint="", outer_diameter=None):
    from ..model import Hole
    return Hole(
        role=ContourRole.HOLE,
        polygon=contour.polygon,
        segments=list(getattr(contour, "segments", []) or []),
        styles=list(getattr(contour, "styles", []) or []),
        diameter=diameter,
        center=center,
        hole_type=hole_type,
        geometric_hint=geometric_hint,
        confidence=confidence,
        source="geometric",
        outer_diameter=outer_diameter,
    )


def _labeled_hole_from_contour(contour):
    """`ForgeContour` con ruolo foro da label_map → `Hole(source="labeled")`."""
    from ..model import Hole

    dia, ctr = circular_geometry(contour.polygon, getattr(contour, "segments", []))
    hole_type = _ROLE_TO_HOLE_TYPE.get(contour.role, HOLE_TYPE_PLAIN)
    return Hole(
        role=contour.role,
        polygon=contour.polygon,
        segments=list(getattr(contour, "segments", []) or []),
        styles=list(getattr(contour, "styles", []) or []),
        diameter=dia or 0.0,
        center=ctr or (0.0, 0.0),
        hole_type=hole_type,
        confidence=1.0,
        source="labeled",
    )


# ---------------------------------------------------------------------------
# Step — inferenza engrave (PLACEHOLDER)
# ---------------------------------------------------------------------------

def _detect_engrave(result: ForgeResult, engrave_tolerance: float = 1.0) -> None:
    """
    Inferenza geometrica delle incisioni — NON ANCORA IMPLEMENTATA.

    Stesso pattern di `_detect_holes` / `_detect_bending`: le incisioni con
    ruolo esplicito (label_map) sono già state promosse da `_detect_labeled`
    con `source="labeled"`. Qui si guarda ciò che è rimasto non etichettato —
    `cluster.inners` con role UNKNOWN e `result.trash_entities` — e si promuove a
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

def _engraving_from_open(proxy, cluster_label: str = "",
                         source: str = "labeled", confidence: float = 1.0) -> Engraving:
    pts = _proxy_pts(proxy)
    return Engraving(
        role=ContourRole.ENGRAVE,
        segments=list(getattr(proxy, "segments", []) or []),
        styles=list(getattr(proxy, "styles", []) or []),
        length=round(track_length(pts), 4),
        pts=pts,
        geometry=LineString(pts) if len(pts) >= 2 else None,
        cluster_label=cluster_label,
        source=source,
        confidence=confidence,
    )


def _engraving_from_closed(polygon, segments, cluster_label: str = "",
                           source: str = "labeled", confidence: float = 1.0,
                           styles=None) -> Engraving:
    return Engraving(
        role=ContourRole.ENGRAVE,
        segments=list(segments or []),
        styles=list(styles or []),
        length=round(polygon.exterior.length, 4),
        pts=list(polygon.exterior.coords),
        polygon=polygon,
        cluster_label=cluster_label,
        source=source,
        confidence=confidence,
    )


def _handle_engrave_open(proxy: OpenFeature, result: ForgeResult) -> bool:
    """
    Smista una traccia engrave aperta per contenimento.

    Dentro un cluster → cluster.engrave_lines (ritorna True).
    Fuori da ogni cluster → resta trash: è geometria orfana come ogni altra
    entità che non sta dentro un outer (ritorna False).
    """
    pts = _proxy_pts(proxy)
    if len(pts) >= 2:
        rep = (
            sum(p[0] for p in pts) / len(pts),
            sum(p[1] for p in pts) / len(pts),
        )
    else:
        rep = pts[0] if pts else None

    probe = Point(rep) if rep else None
    for cluster in result.clusters:
        if probe and cluster.outer.polygon.contains(probe):
            cluster.engrave_lines.append(_engraving_from_open(proxy, cluster_label=cluster.label))
            return True

    return False


def _handle_engrave_closed_trash(proxy, result: ForgeResult) -> bool:
    """
    Come _handle_engrave_open ma per una traccia engrave già chiusa
    (CIRCLE / SPLINE chiusa su layer engrave). Contenimento sul
    representative point del polygon.
    """
    probe = proxy.polygon.representative_point()
    for cluster in result.clusters:
        if cluster.outer.polygon.contains(probe):
            cluster.engrave_lines.append(_engraving_from_closed(
                proxy.polygon,
                getattr(proxy, "segments", []),
                cluster_label=cluster.label,
                styles=getattr(proxy, "styles", []),
            ))
            return True
    return False


def _handle_engrave_closed(inner, cluster: ForgeCluster) -> None:
    cluster.engrave_lines.append(_engraving_from_closed(
        inner.polygon,
        getattr(inner, "segments", []),
        cluster_label=cluster.label,
        styles=getattr(inner, "styles", []),
    ))


# ---------------------------------------------------------------------------
# Assegnazione al cluster contenitore
# ---------------------------------------------------------------------------

def _assign_to_part(ce: ClassifiedEntity, result: ForgeResult) -> None:
    probe = _probe_point(ce)
    if probe is None:
        return

    work_type = ce.work_type.lower()

    for cluster in result.clusters:
        if not cluster.outer.polygon.contains(probe):
            continue

        if work_type == "bending":
            cluster.bending_lines.append(_bending_line_from_data(ce.data, cluster.label))

        _write_custom(ce, cluster)
        return

    result.warnings.append(
        f"detect(): forma {ce.work_type} non contenuta in nessun cluster "
        f"(source={ce.source}). Registrata in classified_entities."
    )


def _write_custom(ce: ClassifiedEntity, cluster: ForgeCluster) -> None:
    key_map = {
        "bending": "bending_lines",
        "marking": "marking_entities",
    }
    key = key_map.get(ce.work_type.lower(), f"{ce.work_type.lower()}_entities")

    if key not in cluster.custom:
        cluster.custom[key] = []

    cluster.custom[key].append({
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


def _extract_data(proxy: OpenFeature, work_type: str) -> dict:
    work_type = work_type.lower()
    pts = _proxy_pts(proxy)
    length = track_length(pts)

    if len(pts) >= 2:
        rep = (
            sum(p[0] for p in pts) / len(pts),
            sum(p[1] for p in pts) / len(pts),
        )
    else:
        rep = pts[0] if pts else None

    if work_type == "bending" and track_shape_type(pts) == "line" and len(pts) >= 2:
        start = pts[0]
        end   = pts[-1]
        dx    = end[0] - start[0]
        dy    = end[1] - start[1]
        return {
            "start":                start,
            "end":                  end,
            "length":               round(length, 4),
            "angle_deg":            round(math.degrees(math.atan2(dy, dx)) % 180, 4),
            "representative_point": rep,
        }

    if work_type == "marking":
        return {
            "length":               round(length, 4),
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


def _bending_line_from_data(data: dict, cluster_label: str) -> BendingLine:
    start = data["start"]
    end   = data["end"]
    return BendingLine(
        role=ContourRole.BEND,
        geometry=LineString([start, end]),
        length=data["length"],
        angle_deg=data["angle_deg"],
        cluster_label=cluster_label,
        source="labeled",
        confidence=1.0,
    )