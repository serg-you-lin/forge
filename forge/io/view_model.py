"""
io/view_model.py
----------------
`to_view_model(result)` — serializza un `ForgeResult` in un dizionario JSON
**orientato al rendering**: coordinate di OGNI feature (outer, inner, fori,
pieghe, incisioni, trash) + ruolo + colore, pronto da disegnare.

È il pendant di `to_json` (che dà solo metadati, zero geometria) e la versione
completa di `to_nester_input` (che dà solo outer + fori). Lo consumano `to_svg`
e qualunque front-end esterno (una dashboard JS che renderizza con SVG/Canvas).

Tutta la geometria è **discretizzata a polilinee** (liste di punti `[x, y]`):
archi, cerchi e spline vengono appiattiti (MAP.md D12). Per i fori si riporta
anche `center` + `diameter`, così un renderer può disegnare un cerchio vero
invece del poligono a N lati.

Sistema di coordinate: quello del modello = quello del file sorgente (Y verso
l'alto). Un renderer SVG deve ribaltare la Y (lo fa `to_svg`).
"""

from __future__ import annotations

from typing import Optional

from ..model import ForgeResult
from ..model.role import ContourRole
from ..rules.palette import role_to_hex
from ..core.geometry import track_points


def _role_str(role) -> str:
    """Valore stringa di un ContourRole (o la stringa stessa)."""
    return getattr(role, "value", str(role))


def _xy(seq) -> list:
    """Lista di punti (2D o 3D) → lista di [x, y] arrotondati."""
    return [[round(p[0], 4), round(p[1], 4)] for p in seq]


def _poly_points(polygon) -> list:
    """Vertici dell'anello esterno di un polygon shapely come lista di [x, y]."""
    if polygon is None or polygon.is_empty:
        return []
    return _xy(polygon.exterior.coords)


def _track(segments, tolerance: float) -> list:
    """Traccia aperta (lista di segmenti nativi) discretizzata a lista di [x, y]."""
    return _xy(track_points(segments, tolerance))


def _contour_entry(contour, tolerance: float) -> dict:
    role = getattr(contour, "role", ContourRole.UNKNOWN)
    pts = _poly_points(getattr(contour, "polygon", None)) or _track(
        getattr(contour, "segments", []), tolerance
    )
    return {"role": _role_str(role), "color": role_to_hex(role), "points": pts, "closed": True}


def _hole_entry(hole, tolerance: float) -> dict:
    entry = _contour_entry(hole, tolerance)
    entry.update({
        "hole_type":  hole.hole_type,
        "diameter":   round(hole.diameter, 4),
        "center":     [round(hole.center[0], 4), round(hole.center[1], 4)],
        "source":     hole.source,
        "confidence": round(hole.confidence, 4),
    })
    if hole.outer_diameter is not None:
        entry["outer_diameter"] = round(hole.outer_diameter, 4)
    return entry


def _bending_entry(bl) -> dict:
    coords = _xy(bl.geometry.coords) if bl.geometry else []
    return {
        "role":       ContourRole.BEND.value,
        "color":      role_to_hex(ContourRole.BEND),
        "points":     coords,
        "closed":     False,
        "length":     round(bl.length, 4),
        "angle_deg":  round(bl.angle_deg, 4),
        "source":     bl.source,
        "confidence": round(bl.confidence, 4),
    }


def _engrave_entry(eng, tolerance: float) -> dict:
    role = getattr(eng, "role", ContourRole.ENGRAVE)
    if eng.polygon is not None:
        pts = _poly_points(eng.polygon)
    elif eng.pts:
        pts = _xy(eng.pts)
    else:
        pts = _track(getattr(eng, "segments", []), tolerance)
    return {
        "role":       _role_str(role),
        "color":      role_to_hex(role),
        "points":     pts,
        "closed":     eng.closed,
        "length":     round(eng.length or 0.0, 4),
        "source":     eng.source,
        "confidence": round(eng.confidence, 4),
    }


def _trash_entry(trash, tolerance: float) -> dict:
    role = getattr(trash, "role", ContourRole.UNKNOWN)
    poly = getattr(trash, "polygon", None)
    if poly is not None:
        pts, closed = _poly_points(poly), True
    else:
        pts, closed = _track(getattr(trash, "segments", []), tolerance), False
    return {"role": _role_str(role), "color": role_to_hex(role), "points": pts, "closed": closed}


def _annotation_entry(ann) -> dict:
    return {
        "kind":     ann.kind,
        "position": [round(ann.position[0], 4), round(ann.position[1], 4)],
        "text":     ann.display_text,
        "height":   getattr(ann, "height", 2.5) or 2.5,
        "rotation": getattr(ann, "rotation", 0.0) or 0.0,
    }


def _bbox_of(clusters) -> Optional[list]:
    boxes = [p.outer.bbox for p in clusters if p.outer is not None and p.outer.polygon is not None]
    if not boxes:
        return None
    return [
        round(min(b[0] for b in boxes), 4),
        round(min(b[1] for b in boxes), 4),
        round(max(b[2] for b in boxes), 4),
        round(max(b[3] for b in boxes), 4),
    ]


def to_view_model(
    result: ForgeResult,
    tolerance: float = 0.05,
    include_trash: bool = True,
    include_annotations: bool = True,
) -> dict:
    """
    `ForgeResult` → dizionario JSON-ready con la geometria di ogni feature.

    Args:
        result:              il `ForgeResult` da serializzare.
        tolerance:           tolleranza di discretizzazione per archi/cerchi/
                             spline delle tracce aperte (le tracce chiuse usano
                             il polygon già discretizzato al load).
        include_trash:       includi `result.trash_entities`.
        include_annotations: includi `result.annotations`.

    Non muta `result`. Non solleva su `result` non valido — ritorna comunque il
    dizionario con `is_valid=False` e le parti che ci sono (utile per debuggare
    un file che non healizza).
    """
    parts_out = []
    for cluster in result.clusters:
        parts_out.append({
            "label":  cluster.label,
            "bbox":   list(cluster.bbox),
            "area":   round(cluster.area, 4),
            "outer":  _contour_entry(cluster.outer, tolerance),
            "inners": [_contour_entry(i, tolerance) for i in cluster.inners],
            "holes":  [_hole_entry(h, tolerance) for h in cluster.holes],
            "bending_lines": [_bending_entry(b) for b in cluster.bending_lines],
            "engrave_lines": [_engrave_entry(e, tolerance) for e in cluster.engrave_lines],
            "summary": cluster.summary,
            "custom":  cluster.custom,
        })

    vm = {
        "source_file": result.source_file,
        "is_valid":    result.is_valid,
        "cluster_count":  result.cluster_count,
        "bbox":        _bbox_of(result.clusters),
        "warnings":    list(result.warnings),
        "errors":      list(result.errors),
        "clusters":       parts_out,
        "palette":     _palette_dict(),
    }
    if include_trash:
        vm["trash"] = [_trash_entry(t, tolerance) for t in result.trash_entities]
    if include_annotations:
        vm["annotations"] = [_annotation_entry(a) for a in result.annotations]
    return vm


def _palette_dict() -> dict:
    """role (stringa) → colore hex, per la legenda di un renderer."""
    return {r.value: role_to_hex(r) for r in ContourRole}
