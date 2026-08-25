"""
adapters/dxf/exporter.py
------------------------
Esporta primitive geometriche pure (LineSeg, ArcSeg, SplineSeg) in formato DXF.
Unico file che tocca ezdxf per il write-back.
"""

from __future__ import annotations

import math
from typing import Optional

from ...core.primitives import LineSeg, ArcSeg, SplineSeg, CircleSeg


# ---------------------------------------------------------------------------
# ArcSeg → bulge DXF
# ---------------------------------------------------------------------------

def arc_seg_to_bulge(arc: ArcSeg) -> float:
    """
    Converte ArcSeg in valore bulge DXF.

    bulge = tan(Δθ / 4)
    Positivo = CCW, negativo = CW.
    """
    delta = arc.end_angle - arc.start_angle
    delta = delta % (2 * math.pi)
    if delta == 0.0:
        delta = 2 * math.pi  # arco completo

    bulge = math.tan(delta / 4.0)
    if not arc.ccw:
        bulge = -bulge
    return bulge


def _arc_start_point(arc: ArcSeg) -> tuple:
    """Punto sul cerchio all'angolo start_angle."""
    x = arc.center[0] + arc.radius * math.cos(arc.start_angle)
    y = arc.center[1] + arc.radius * math.sin(arc.start_angle)
    return (x, y)


def segments_to_pts_with_bulge(segments: list) -> list:
    """
    Converte List[LineSeg | ArcSeg] in lista di tuple
    (x, y, s, e, bulge) pronte per LWPOLYLINE format='xyseb'.

    CircleSeg e SplineSeg non vengono gestiti:
    - CircleSeg va esportato come CIRCLE, non come LWPOLYLINE
    - SplineSeg ignorato — has_spline va controllato a monte
    """
    pts = []
    for seg in segments:
        if isinstance(seg, LineSeg):
            pts.append((seg.start[0], seg.start[1], 0.0, 0.0, 0.0))
        elif isinstance(seg, ArcSeg):
            start = _arc_start_point(seg)
            pts.append((start[0], start[1], 0.0, 0.0, arc_seg_to_bulge(seg)))
        # CircleSeg: skip, va esportato come CIRCLE
        # SplineSeg: skip, has_spline controllato a monte
    return pts


# ---------------------------------------------------------------------------
# Write-back — unico punto che tocca ezdxf per le forme chiuse
# ---------------------------------------------------------------------------

def write_contour_to_msp(msp, contour, layer: str) -> Optional[object]:
    """
    Materializza un ForgeContour o Hole su msp.

    - CircleSeg → CIRCLE
    - LineSeg / ArcSeg → LWPOLYLINE (o POLYLINE2D per R12)
    - SplineSeg → None (non supportato)

    Restituisce l'entità creata, o None se:
      - segments è vuoto
      - tutti i segmenti sono SplineSeg
    """
    from ...core.primitives import CircleSeg, SplineSeg

    segments = getattr(contour, "segments", [])
    if not segments:
        return None

    # Se è un singolo cerchio, esporta come CIRCLE
    if len(segments) == 1 and isinstance(segments[0], CircleSeg):
        circle = segments[0]
        return msp.add_circle(
            center=circle.center,
            radius=circle.radius,
            dxfattribs={"layer": layer, "color": 256}
        )

    # Se è una singola SplineSeg, esporta SPLINE nativa con i dati originali.
    if len(segments) == 1 and isinstance(segments[0], SplineSeg):
        spline = segments[0]
        entity = msp.add_spline(dxfattribs={"layer": layer, "color": 256})
        entity.dxf.degree = int(spline.degree)

        cps3d = [(float(x), float(y), 0.0) for x, y in spline.control_points]
        entity.control_points = cps3d

        if spline.knots:
            entity.knots = [float(k) for k in spline.knots]

        if spline.weights:
            entity.weights = [float(w) for w in spline.weights]

        if spline.fit_points:
            entity.fit_points = [
                (float(p[0]), float(p[1]), float(p[2]))
                for p in spline.fit_points
            ]

        flags = int(spline.flags or 0)
        if spline.closed:
            flags |= 1
        if spline.periodic:
            flags |= 2
        if spline.weights:
            flags |= 4
        entity.dxf.flags = flags

        if spline.knot_tolerance is not None:
            entity.dxf.knot_tolerance = float(spline.knot_tolerance)
        if spline.fit_tolerance is not None:
            entity.dxf.fit_tolerance = float(spline.fit_tolerance)
        if spline.control_point_tolerance is not None:
            entity.dxf.control_point_tolerance = float(spline.control_point_tolerance)

        if spline.start_tangent is not None:
            entity.dxf.start_tangent = tuple(float(v) for v in spline.start_tangent)
        if spline.end_tangent is not None:
            entity.dxf.end_tangent = tuple(float(v) for v in spline.end_tangent)

        return entity

    # Se c'è una Spline mista ad altre primitive, non esportiamo ancora.
    has_spline = any(isinstance(s, SplineSeg) for s in segments)
    if has_spline:
        return None

    # Caso generale: LWPOLYLINE con bulge
    pts = segments_to_pts_with_bulge(segments)
    if not pts:
        return None

    is_r12 = msp.doc is not None and msp.doc.dxfversion < "AC1015"
    if is_r12:
        pline = msp.add_polyline2d(
            [(p[0], p[1]) for p in pts],
            dxfattribs={"layer": layer, "color": 256},
        )
        for vertex, pt in zip(pline.vertices, pts):
            if pt[4] != 0.0:
                vertex.dxf.bulge = pt[4]
        pline.close(True)
        return pline
    else:
        return msp.add_lwpolyline(
            pts,
            format="xyseb",
            dxfattribs={"layer": layer, "color": 256},
            close=True,
        )