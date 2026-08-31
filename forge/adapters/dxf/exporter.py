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
from ...model.style import EdgeStyle

_STANDARD_LINETYPES = frozenset({"BYLAYER", "BYBLOCK", "CONTINUOUS"})


# ---------------------------------------------------------------------------
# Aspetto grezzo (linetype/colore) — Cluster E
# ---------------------------------------------------------------------------

def _ensure_linetype(doc, style: Optional[EdgeStyle]) -> str:
    """
    Registra (se serve) il linetype di `style` nel documento di output e ne
    ritorna il nome da usare in dxfattribs.

    Un documento ezdxf nuovo conosce solo ByLayer/ByBlock/Continuous: un
    linetype con tratteggio (DASHED, CENTER, ...) non esiste finché non lo si
    aggiunge alla tabella, col pattern catturato dall'adapter al load
    (`style.linetype_pattern`). Senza pattern noto non c'è nulla da
    registrare — meglio BYLAYER esplicito che un riferimento pendente.
    """
    if style is None:
        return "BYLAYER"
    name = style.linetype or "BYLAYER"
    if name.upper() in _STANDARD_LINETYPES:
        return name
    if doc is None:
        return "BYLAYER"
    if name not in doc.linetypes:
        if not style.linetype_pattern:
            return "BYLAYER"
        doc.linetypes.add(
            name,
            pattern=list(style.linetype_pattern),
            description=style.linetype_desc or "",
        )
    return name


def _style_attribs(doc, layer: str, style: Optional[EdgeStyle] = None) -> dict:
    """
    dxfattribs per una entità in output: layer + linetype della sorgente, se
    noto. Il colore resta SEMPRE BYLAYER (256) — anche per il trash: il
    colore è una decisione di dominio per layer (verde outer, rosso trash,
    ... — `rules/palette.py`), mai quello, eventualmente diverso, della
    sorgente. Solo l'aspetto del tratto (continuo/tratteggiato/...) va
    ripristinato fedele.
    """
    attribs = {"layer": layer, "color": 256}
    if style is None:
        return attribs

    linetype = _ensure_linetype(doc, style)
    if linetype.upper() != "BYLAYER":
        attribs["linetype"] = linetype

    return attribs


# ---------------------------------------------------------------------------
# ArcSeg → bulge DXF
# ---------------------------------------------------------------------------

def arc_seg_to_bulge(arc: ArcSeg) -> float:
    # L'angolo spazzato dipende dal verso: per un arco CW il tratto reale è
    # start_angle → end_angle percorso in senso orario, NON il complemento a
    # 2π. ArcSeg._sweep() è l'unica sede di questo calcolo — riusarla qui
    # evita che un arco invertito (ccw=False, prodotto da segments_from_loop
    # quando il loop viene orientato CCW) venga scritto con il bulge dell'arco
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

def _add_spline(spline: SplineSeg, msp, layer: str,
                 style: Optional[EdgeStyle] = None) -> object:
    """
    Materializza una SplineSeg come SPLINE nativa, ricostruita dalla primitiva
    (control points / knots / weights / degree / tangenti) — non è una copia
    dell'entità sorgente, è la stessa curva riespressa. Identico trattamento a
    quello della spline chiusa singola.
    """
    attribs = _style_attribs(msp.doc, layer, style)
    entity = msp.add_spline(dxfattribs=attribs)
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


def write_segments(segments: List, msp, layer: str, styles: Optional[List] = None) -> Optional[object]:
    """
    Materializza una lista di segmenti puri su msp.

    - CircleSeg → CIRCLE
    - SplineSeg singola → SPLINE nativa
    - SplineSeg mista a linee/archi → SPLINE native + LWPOLYLINE aperte che
      condividono gli endpoint (il loop chiuso è dato dall'insieme delle
      entità, non discretizziamo mai la spline in polilinea). Restituisce la
      lista delle entità create.
    - LineSeg / ArcSeg → LWPOLYLINE (o POLYLINE2D per R12)

    `styles` (allineata a `segments`, opzionale) porta il linetype grezzo
    della sorgente: un contorno strutturale (outer/inner/hole) è una geometria
    già classificata, quindi il colore resta sempre BYLAYER (colore semantico
    di ruolo, `rules/palette.py`) — solo il linetype viene ripristinato, preso
    dal primo segmento come rappresentante dell'intero contorno (un contorno
    di taglio reale non mischia mai tratteggi diversi al suo interno).

    Restituisce l'entità creata (o la lista, per i contorni misti), o None se
    non c'è nulla da scrivere.
    """
    if not segments:
        return None

    style = styles[0] if styles else None

    if len(segments) == 1 and isinstance(segments[0], CircleSeg):
        circle = segments[0]
        return msp.add_circle(
            center=circle.center,
            radius=circle.radius,
            dxfattribs=_style_attribs(msp.doc, layer, style),
        )

    if len(segments) == 1 and isinstance(segments[0], SplineSeg):
        return _add_spline(segments[0], msp, layer, style)

    if any(isinstance(s, SplineSeg) for s in segments):
        # Contorno misto: nessuna entità DXF singola può contenere insieme una
        # spline e una polilinea. Lo materializziamo come più entità native
        # (SPLINE + LWPOLYLINE aperte) con endpoint coincidenti — il grafo di
        # reload ricuce il loop. Mai discretizzare la spline.
        created = write_open_segments(segments, msp, layer, styles)
        return created or None

    pts = segments_to_pts_with_bulge(segments)
    if not pts:
        return None

    attribs = _style_attribs(msp.doc, layer, style)
    is_r12 = msp.doc is not None and msp.doc.dxfversion < "AC1015"
    if is_r12:
        pline = msp.add_polyline2d(
            [(p[0], p[1]) for p in pts],
            dxfattribs=attribs,
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
            dxfattribs=attribs,
            close=True,
        )


# ---------------------------------------------------------------------------
# Write-back — incisioni (engrave / marking)
# ---------------------------------------------------------------------------

def write_engrave_segments(segments: List, msp, layer: str, styles: Optional[List] = None) -> List[object]:
    """
    Materializza un'incisione come geometria NATIVA, una entità DXF per
    primitiva — mai LWPOLYLINE, nemmeno per un run di linee/archi contigui e
    nemmeno se in ingresso era una polilinea.

    Un'incisione è concettualmente N segmenti separati (scelta di modello,
    vedi `model/engraving.py`): il rendering fedele è una entità per segmento.
    È anche coerente con le bending line (emesse come `LINE`) e con quello che
    un CAM si aspetta di trovare sul layer di marcatura.

      - LineSeg   → LINE
      - ArcSeg    → ARC
      - SplineSeg → SPLINE nativa (mai discretizzata)
      - CircleSeg → CIRCLE

    Una entità per primitiva significa anche uno stile per primitiva: il
    linetype della sorgente (`styles`, allineata a `segments`) è ripristinato
    esatto per ognuna. Il colore resta BYLAYER — l'incisione è geometria già
    classificata, il suo colore è semantico (`rules/palette.py`), non quello
    della sorgente.

    Restituisce la lista delle entità create.
    """
    created: List[object] = []
    styles = styles or []

    for i, seg in enumerate(segments or []):
        style = styles[i] if i < len(styles) else None
        attribs = _style_attribs(msp.doc, layer, style)

        if isinstance(seg, LineSeg):
            created.append(msp.add_line(seg.start, seg.end, dxfattribs=attribs))
        elif isinstance(seg, ArcSeg):
            # In DXF un ARC è sempre percorso CCW da start_angle a end_angle.
            # Un ArcSeg CW copre lo stesso luogo geometrico se lo si legge
            # CCW da end_angle a start_angle: basta scambiare gli angoli.
            if seg.ccw:
                sa, ea = seg.start_angle, seg.end_angle
            else:
                sa, ea = seg.end_angle, seg.start_angle
            created.append(msp.add_arc(
                center=seg.center,
                radius=seg.radius,
                start_angle=math.degrees(sa),
                end_angle=math.degrees(ea),
                dxfattribs=attribs,
            ))
        elif isinstance(seg, CircleSeg):
            created.append(msp.add_circle(
                center=seg.center, radius=seg.radius, dxfattribs=attribs,
            ))
        elif isinstance(seg, SplineSeg):
            created.append(_add_spline(seg, msp, layer, style))

    return created


# ---------------------------------------------------------------------------
# Write-back — tracce APERTE (trash, frammenti di profilo, centerline, ...)
# ---------------------------------------------------------------------------

def write_open_segments(segments: List, msp, layer: str, styles: Optional[List] = None) -> List[object]:
    """
    Materializza una lista di segmenti puri come geometria APERTA su msp.

    A differenza di `write_segments` non chiude il contorno: serve per le
    entità che il pipeline lascia non classificate (`result.trash_entities`),
    dove chiudere il loop falserebbe la forma, e come fallback di
    `write_segments` per i contorni misti spline+linee. Ogni segmento resta
    fedele:

      - LineSeg / ArcSeg → una LWPOLYLINE aperta con bulge
      - SplineSeg        → SPLINE nativa (una per spline)
      - CircleSeg        → CIRCLE

    Il linetype (`styles`, allineata a `segments`) è sempre ripristinato — un
    run di LineSeg/ArcSeg consecutivi diventa una sola LWPOLYLINE, quindi
    prende lo stile del primo segmento del run come rappresentante. Il
    colore resta sempre BYLAYER, trash compreso: quella geometria non ha un
    ruolo classificato, ma il rosso di `Trash` è comunque una decisione di
    layer, non un colore da ripristinare entità per entità.

    Restituisce la lista delle entità create (vuota se non c'è nulla da
    scrivere).
    """
    if not segments:
        return []

    styles = styles or []
    created: List[object] = []
    poly_run: List = []
    poly_run_style: Optional[EdgeStyle] = None

    def _flush_poly_run():
        if not poly_run:
            return
        pts = segments_to_pts_with_bulge(poly_run)
        if pts:
            end = _seg_end_point(poly_run[-1])
            if end is not None:
                pts.append((end[0], end[1], 0.0, 0.0, 0.0))
            attribs = _style_attribs(msp.doc, layer, poly_run_style)
            created.append(msp.add_lwpolyline(
                pts,
                format="xyseb",
                dxfattribs=attribs,
                close=False,
            ))
        poly_run.clear()

    for i, seg in enumerate(segments):
        style = styles[i] if i < len(styles) else None
        if isinstance(seg, (LineSeg, ArcSeg)):
            if not poly_run:
                poly_run_style = style
            poly_run.append(seg)
            continue
        _flush_poly_run()
        attribs = _style_attribs(msp.doc, layer, style)
        if isinstance(seg, CircleSeg):
            created.append(msp.add_circle(
                center=seg.center, radius=seg.radius,
                dxfattribs=attribs,
            ))
        elif isinstance(seg, SplineSeg):
            created.append(_add_spline(seg, msp, layer, style))

    _flush_poly_run()
    return created