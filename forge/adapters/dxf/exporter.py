"""
adapters/dxf/exporter.py
------------------------
Esporta primitive geometriche pure (LineSeg, ArcSeg, SplineSeg) in formato DXF.
Unico file che tocca ezdxf per il write-back.
"""

from __future__ import annotations

import math
from typing import List, Optional

from ...core.primitives import LineSeg, ArcSeg, SplineSeg, CircleSeg


# ---------------------------------------------------------------------------
# ArcSeg → bulge DXF
# ---------------------------------------------------------------------------

def arc_seg_to_bulge(arc: ArcSeg) -> float:
    # L'angolo spazzato dipende dal verso: per un arco CW il tratto reale è
    # start_angle → end_angle percorso in senso orario, NON il complemento a
    # 2π. ArcSeg._sweep() è l'unica sede di questo calcolo — riusarla qui
    # evita che un arco invertito (ccw=False, prodotto da parse_loop quando il
    # loop viene orientato CCW) venga scritto con il bulge dell'arco
    # complementare, cioè "alla rovescia".
    sweep = arc._sweep()
    if sweep <= 1e-12:
        sweep = 2 * math.pi
    bulge = math.tan(sweep / 4.0)
    if not arc.ccw:
        bulge = -bulge
    return bulge


def _arc_start_point(arc: ArcSeg) -> tuple:
    x = arc.center[0] + arc.radius * math.cos(arc.start_angle)
    y = arc.center[1] + arc.radius * math.sin(arc.start_angle)
    return (x, y)


def _arc_end_point(arc: ArcSeg) -> tuple:
    x = arc.center[0] + arc.radius * math.cos(arc.end_angle)
    y = arc.center[1] + arc.radius * math.sin(arc.end_angle)
    return (x, y)


def _seg_end_point(seg) -> Optional[tuple]:
    if isinstance(seg, LineSeg):
        return (seg.end[0], seg.end[1])
    if isinstance(seg, ArcSeg):
        return _arc_end_point(seg)
    return None


def segments_to_pts_with_bulge(segments: list) -> list:
    pts = []
    for seg in segments:
        if isinstance(seg, LineSeg):
            pts.append((seg.start[0], seg.start[1], 0.0, 0.0, 0.0))
        elif isinstance(seg, ArcSeg):
            start = _arc_start_point(seg)
            pts.append((start[0], start[1], 0.0, 0.0, arc_seg_to_bulge(seg)))
    return pts


# ---------------------------------------------------------------------------
# Write-back — unico punto che tocca ezdxf per le forme chiuse
# ---------------------------------------------------------------------------

def _add_spline(spline: SplineSeg, msp, layer: str) -> object:
    """
    Materializza una SplineSeg come SPLINE nativa, ricostruita dalla primitiva
    (control points / knots / weights / degree / tangenti) — non è una copia
    dell'entità sorgente, è la stessa curva riespressa. Identico trattamento a
    quello della spline chiusa singola.
    """
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
    if spline.closed:    flags |= 1
    if spline.periodic:  flags |= 2
    if spline.weights:   flags |= 4
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


def write_segments(segments: List, msp, layer: str) -> Optional[object]:
    """
    Materializza una lista di segmenti puri su msp.

    - CircleSeg → CIRCLE
    - SplineSeg singola → SPLINE nativa
    - SplineSeg mista a linee/archi → SPLINE native + LWPOLYLINE aperte che
      condividono gli endpoint (il loop chiuso è dato dall'insieme delle
      entità, non discretizziamo mai la spline in polilinea). Restituisce la
      lista delle entità create.
    - LineSeg / ArcSeg → LWPOLYLINE (o POLYLINE2D per R12)

    Restituisce l'entità creata (o la lista, per i contorni misti), o None se
    non c'è nulla da scrivere.
    """
    if not segments:
        return None

    if len(segments) == 1 and isinstance(segments[0], CircleSeg):
        circle = segments[0]
        return msp.add_circle(
            center=circle.center,
            radius=circle.radius,
            dxfattribs={"layer": layer, "color": 256},
        )

    if len(segments) == 1 and isinstance(segments[0], SplineSeg):
        return _add_spline(segments[0], msp, layer)

    if any(isinstance(s, SplineSeg) for s in segments):
        # Contorno misto: nessuna entità DXF singola può contenere insieme una
        # spline e una polilinea. Lo materializziamo come più entità native
        # (SPLINE + LWPOLYLINE aperte) con endpoint coincidenti — il grafo di
        # reload ricuce il loop. Mai discretizzare la spline.
        created = write_open_segments(segments, msp, layer)
        return created or None

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


# ---------------------------------------------------------------------------
# Write-back — tracce APERTE (trash, frammenti di profilo, centerline, ...)
# ---------------------------------------------------------------------------

def write_open_segments(segments: List, msp, layer: str) -> List[object]:
    """
    Materializza una lista di segmenti puri come geometria APERTA su msp.

    A differenza di `write_segments` non chiude il contorno: serve per le
    entità che il pipeline lascia non classificate (`result.trash_entities`),
    dove chiudere il loop falserebbe la forma. Ogni segmento resta fedele:

      - LineSeg / ArcSeg → una LWPOLYLINE aperta con bulge
      - SplineSeg        → SPLINE nativa (una per spline)
      - CircleSeg        → CIRCLE

    Restituisce la lista delle entità create (vuota se non c'è nulla da
    scrivere).
    """
    if not segments:
        return []

    created: List[object] = []
    poly_run: List = []

    def _flush_poly_run():
        if not poly_run:
            return
        pts = segments_to_pts_with_bulge(poly_run)
        if pts:
            end = _seg_end_point(poly_run[-1])
            if end is not None:
                pts.append((end[0], end[1], 0.0, 0.0, 0.0))
            created.append(msp.add_lwpolyline(
                pts,
                format="xyseb",
                dxfattribs={"layer": layer, "color": 256},
                close=False,
            ))
        poly_run.clear()

    for seg in segments:
        if isinstance(seg, (LineSeg, ArcSeg)):
            poly_run.append(seg)
            continue
        _flush_poly_run()
        if isinstance(seg, CircleSeg):
            created.append(msp.add_circle(
                center=seg.center, radius=seg.radius,
                dxfattribs={"layer": layer, "color": 256},
            ))
        elif isinstance(seg, SplineSeg):
            created.append(_add_spline(seg, msp, layer))

    _flush_poly_run()
    return created