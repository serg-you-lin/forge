"""
io/svg.py
---------
`to_svg(result)` — renderer SVG del modello forge (MAP.md D12).

SVG **solo in uscita**: è una rappresentazione visiva del `ForgeResult`, per una
UI, un report, un'anteprima rapida. Non serve al taglio — archi, cerchi e spline
sono discretizzati a polilinea (via `to_view_model`).

Un colore per ruolo (stessa palette semantica del DXF di output). La Y viene
ribaltata (il modello ha Y verso l'alto, SVG verso il basso).
"""

from __future__ import annotations

import html
from typing import Optional

from ..model import ForgeResult
from .view_model import to_view_model


def _fmt(pts) -> str:
    """Lista di [x, y] → stringa 'x0,y0 x1,y1 …' per points= di polyline/polygon."""
    return " ".join(f"{x:.4f},{y:.4f}" for x, y in pts)


def _shape(entry: dict, stroke_w: float, holes_as_circles: bool) -> str:
    pts = entry.get("points") or []
    color = entry.get("color", "#ff0000")

    if holes_as_circles and entry.get("diameter", 0) > 0 and entry.get("center"):
        cx, cy = entry["center"]
        r = entry["diameter"] / 2.0
        return (f'<circle cx="{cx:.4f}" cy="{cy:.4f}" r="{r:.4f}" '
                f'fill="none" stroke="{color}" stroke-width="{stroke_w:.4f}"/>')

    if len(pts) < 2:
        return ""
    tag = "polygon" if entry.get("closed") else "polyline"
    return (f'<{tag} points="{_fmt(pts)}" fill="none" '
            f'stroke="{color}" stroke-width="{stroke_w:.4f}"/>')


def to_svg(
    result: ForgeResult,
    tolerance: float = 0.05,
    include_trash: bool = True,
    include_annotations: bool = True,
    padding: float = 0.03,
    background: Optional[str] = "#1e1e1e",
    holes_as_circles: bool = True,
    stroke_width: Optional[float] = None,
    size: Optional[str] = None,
    units: Optional[str] = None,
) -> str:
    """
    `ForgeResult` → stringa SVG completa (`<svg>…</svg>`).

    Args:
        tolerance:           discretizzazione di archi/spline nelle tracce aperte.
        include_trash:       disegna anche `result.trash_entities` (rosso).
        include_annotations: disegna i testi della sorgente.
        padding:             margine attorno al disegno, frazione del lato bbox.
        background:          colore di sfondo (`None` = trasparente).
        holes_as_circles:    disegna i fori come `<circle>` vero quando si conosce
                             Ø/centro, invece del poligono a N lati.
        stroke_width:        spessore linea in unità disegno; `None` = auto
                             (diagonale bbox / 400).
        size:                attributi `width`/`height` dell'`<svg>`. `None`
                             (default) li OMETTE: l'SVG scala a riempire il
                             contenitore (o la finestra del browser) — è
                             vettoriale, lo zoomi quanto vuoi. Passa una stringa
                             come `"800"` per fissare la larghezza in px
                             (l'altezza segue il rapporto del `viewBox`).
        units:               `"mm"` → SVG **in scala reale** per un import CAM/
                             laser 1:1 (`width="…mm" height="…mm"`, padding e
                             sfondo forzati a 0/None). Ignora `size` e `padding`.
                             NB: archi/cerchi/spline restano discretizzati (D12) —
                             per il taglio ad alta fedeltà usa `to_dxf`, non
                             l'SVG. `None` = SVG per visualizzazione.

    Se `result` non ha parti valide, ritorna comunque un SVG (vuoto o con la sola
    trash) — non solleva.
    """
    cam = units == "mm"
    if cam:
        padding = 0.0
        background = None
    vm = to_view_model(
        result, tolerance=tolerance,
        include_trash=include_trash, include_annotations=include_annotations,
    )

    bbox = vm.get("bbox") or _scan_bbox(vm)
    if bbox is None:
        return '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"/>'

    minx, miny, maxx, maxy = bbox
    w = max(maxx - minx, 1e-6)
    h = max(maxy - miny, 1e-6)
    pad = max(w, h) * padding
    vminx, vminy = minx - pad, miny - pad
    vw, vh = w + 2 * pad, h + 2 * pad
    sw = stroke_width if stroke_width is not None else (w * w + h * h) ** 0.5 / 400.0

    if cam:
        dims = f' width="{vw:.4f}mm" height="{vh:.4f}mm"'
    elif size is None:
        dims = ""
    else:
        wpx = float(size)
        dims = f' width="{wpx:.0f}" height="{wpx * vh / vw:.0f}"'
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vminx:.4f} {vminy:.4f} '
        f'{vw:.4f} {vh:.4f}"{dims} preserveAspectRatio="xMidYMid meet">'
    ]
    if background:
        out.append(f'<rect x="{vminx:.4f}" y="{vminy:.4f}" width="{vw:.4f}" '
                   f'height="{vh:.4f}" fill="{background}"/>')

    # Y-flip: (x, y) → (x, miny+maxy - y), resta dentro [miny, maxy]
    flip = miny + maxy
    out.append(f'<g transform="matrix(1 0 0 -1 0 {flip:.4f})" '
               f'stroke-linejoin="round" stroke-linecap="round">')

    for i, part in enumerate(vm["parts"]):
        out.append(f'<g data-part="{html.escape(str(part.get("label") or i))}">')
        out.append(_shape(part["outer"], sw, False))
        for inner in part["inners"]:
            out.append(_shape(inner, sw, False))
        for hole in part["holes"]:
            out.append(_shape(hole, sw, holes_as_circles))
        for bl in part["bending_lines"]:
            out.append(_shape(bl, sw, False))
        for eng in part["engrave_lines"]:
            out.append(_shape(eng, sw, False))
        out.append("</g>")

    for t in vm.get("trash", []):
        out.append(_shape(t, sw, False))

    out.append("</g>")  # end flipped group

    # Annotazioni: testo fuori dal gruppo ribaltato (altrimenti sarebbe speculare)
    for ann in vm.get("annotations", []):
        txt = (ann.get("text") or "").strip()
        if not txt:
            continue
        x, y = ann["position"]
        fy = flip - y
        size = ann.get("height") or 2.5
        rot = ann.get("rotation") or 0.0
        transform = f' transform="rotate({-rot:.2f} {x:.4f} {fy:.4f})"' if rot else ""
        out.append(
            f'<text x="{x:.4f}" y="{fy:.4f}" font-size="{size:.4f}" '
            f'fill="#c8c8c8" font-family="sans-serif"{transform}>{html.escape(txt)}</text>'
        )

    out.append("</svg>")
    return "\n".join(s for s in out if s)


def save_svg(result: ForgeResult, path: str, **kwargs) -> None:
    """Scrive `to_svg(result, **kwargs)` su file."""
    with open(path, "w", encoding="utf-8") as f:
        f.write(to_svg(result, **kwargs))
    print(f"[forge] SVG salvato in {path}")


def _scan_bbox(vm: dict) -> Optional[list]:
    """bbox da tutti i punti del view model — fallback quando vm['bbox'] è None."""
    xs, ys = [], []

    def _collect(entry):
        for p in entry.get("points") or []:
            xs.append(p[0]); ys.append(p[1])

    for part in vm.get("parts", []):
        _collect(part["outer"])
        for group in ("inners", "holes", "bending_lines", "engrave_lines"):
            for e in part[group]:
                _collect(e)
    for t in vm.get("trash", []):
        _collect(t)

    if not xs:
        return None
    return [min(xs), min(ys), max(xs), max(ys)]
