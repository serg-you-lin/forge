# """
# debug_small_contours.py
# -----------------
# Visualizza i contorni trovati dall'healer su un file DXF,
# colorandoli in base alla soglia di area.

#     VERDE  → pezzo reale (area >= min_area)
#     ROSSO  → artefatto   (area <  min_area) — verrebbe scartato da split_to_files
#     GRIGIO → inner/hole contenuti in un outer

# Produce un SVG nella stessa cartella del DXF con suffisso _debug_contours.svg.

# Uso:
#     python debug_contours.py <file.dxf> [--min-area 10] [--tolerance 0.05]

# Dipendenze: ezdxf, shapely, forge (la tua libreria)
# """

# import argparse
# import os
# import sys
# import ezdxf
# from shapely.geometry import MultiPolygon

# # --- Adatta questo import al percorso reale della tua libreria ---
# # Se lanci lo script dalla root del progetto con `python -m scripts.debug_contours`
# # puoi usare import assoluti. Altrimenti modifica sys.path qui sotto.
# # sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# from dxf_forge.workflow.healer import heal
# from dxf_forge.workflow.splitter import DEFAULT_MIN_PART_AREA
# from dxf_forge.core.geometry import entity_to_polygon


# # ---------------------------------------------------------------------------
# # Palette colori SVG
# # ---------------------------------------------------------------------------
# COLOR_REAL   = "#2ecc71"   # verde — pezzo reale
# COLOR_TRASH  = "#e74c3c"   # rosso — artefatto sotto soglia
# COLOR_INNER  = "#95a5a6"   # grigio — inner/hole
# COLOR_LABEL  = "#2c3e50"   # testo etichette
# COLOR_BG     = "#fafafa"


# # ---------------------------------------------------------------------------
# # SVG helpers
# # ---------------------------------------------------------------------------

# def _poly_to_svg_path(polygon) -> str:
#     """Converte un Shapely Polygon in un path SVG (exterior + holes)."""
#     def ring_to_d(coords):
#         pts = list(coords)
#         if not pts:
#             return ""
#         d = f"M {pts[0][0]:.3f} {pts[0][1]:.3f}"
#         for x, y in pts[1:]:
#             d += f" L {x:.3f} {y:.3f}"
#         d += " Z"
#         return d

#     d = ring_to_d(polygon.exterior.coords)
#     for interior in polygon.interiors:
#         d += " " + ring_to_d(interior.coords)
#     return d


# def _bbox_all(polygons):
#     """Restituisce (minx, miny, maxx, maxy) dell'insieme di polygon."""
#     minx = min(p.bounds[0] for p in polygons)
#     miny = min(p.bounds[1] for p in polygons)
#     maxx = max(p.bounds[2] for p in polygons)
#     maxy = max(p.bounds[3] for p in polygons)
#     return minx, miny, maxx, maxy


# # ---------------------------------------------------------------------------
# # Core
# # ---------------------------------------------------------------------------

# def debug_contours(
#     dxf_path: str,
#     min_area: float = DEFAULT_MIN_PART_AREA,
#     tolerance: float = 0.05,
#     output_path: str = None,
# ) -> str:
#     """
#     Heala il DXF, raccoglie tutti i contorni outer e inner,
#     e produce un SVG di debug.

#     Returns:
#         Percorso del file SVG prodotto.
#     """
#     # 1. Carica il DXF
#     doc = ezdxf.readfile(dxf_path)
#     msp = doc.modelspace()

#     # 2. Heal — write_to_msp=False perché non vogliamo modificare nulla
#     result = heal(
#         msp,
#         tolerance=tolerance,
#         write_to_msp=False,
#         label=os.path.splitext(os.path.basename(dxf_path))[0],
#     )

#     if not result.parts:
#         print("Nessun contorno trovato dall'healer.")
#         return ""

#     # 3. Raccoglie tutti i polygon per il calcolo del viewport
#     all_polys = []
#     for part in result.parts:
#         if part.outer.polygon and not part.outer.polygon.is_empty:
#             all_polys.append(part.outer.polygon)
#         for inner in part.inners:
#             if inner.polygon and not inner.polygon.is_empty:
#                 all_polys.append(inner.polygon)

#     if not all_polys:
#         print("Nessun polygon valido trovato.")
#         return ""

#     minx, miny, maxx, maxy = _bbox_all(all_polys)
#     padding = max((maxx - minx), (maxy - miny)) * 0.05

#     # 4. Viewport SVG — flippa Y perché SVG ha Y verso il basso
#     vw = maxx - minx + 2 * padding
#     vh = maxy - miny + 2 * padding
#     SVG_W = 1200
#     SVG_H = int(SVG_W * vh / vw)

#     scale = SVG_W / vw
#     tx = -minx + padding   # traslazione X
#     ty = maxy + padding    # traslazione Y (per il flip)

#     def to_svg(x, y):
#         """Coordinate DXF → coordinate SVG."""
#         return (x + tx) * scale, (ty - y) * scale

#     def poly_to_svg_flipped(polygon):
#         """Converte polygon con flip Y."""
#         def ring_to_d(coords):
#             pts = [to_svg(x, y) for x, y in coords]
#             if not pts:
#                 return ""
#             d = f"M {pts[0][0]:.2f} {pts[0][1]:.2f}"
#             for sx, sy in pts[1:]:
#                 d += f" L {sx:.2f} {sy:.2f}"
#             d += " Z"
#             return d

#         d = ring_to_d(polygon.exterior.coords)
#         for interior in polygon.interiors:
#             d += " " + ring_to_d(interior.coords)
#         return d

#     # 5. Costruisce SVG
#     font_size = max(8, int(SVG_W * 0.012))
#     lines = [
#         f'<svg xmlns="http://www.w3.org/2000/svg" '
#         f'width="{SVG_W}" height="{SVG_H}" '
#         f'viewBox="0 0 {SVG_W} {SVG_H}">',
#         f'<rect width="100%" height="100%" fill="{COLOR_BG}"/>',
#         f'<!-- Debug contorni: {os.path.basename(dxf_path)} -->',
#         f'<!-- min_area={min_area} mm²  tolerance={tolerance} mm -->',
#         # Titolo
#         f'<text x="10" y="{font_size + 4}" '
#         f'font-family="monospace" font-size="{font_size}" fill="{COLOR_LABEL}">'
#         f'{os.path.basename(dxf_path)} — min_area={min_area} mm²</text>',
#         # Legenda
#         f'<text x="10" y="{font_size * 2 + 8}" '
#         f'font-family="monospace" font-size="{int(font_size*0.85)}" fill="{COLOR_REAL}">■ pezzo reale (≥ soglia)</text>',
#         f'<text x="200" y="{font_size * 2 + 8}" '
#         f'font-family="monospace" font-size="{int(font_size*0.85)}" fill="{COLOR_TRASH}">■ artefatto (< soglia, scartato)</text>',
#         f'<text x="480" y="{font_size * 2 + 8}" '
#         f'font-family="monospace" font-size="{int(font_size*0.85)}" fill="{COLOR_INNER}">■ inner/hole</text>',
#     ]

#     for i, part in enumerate(result.parts, start=1):
#         outer_poly = part.outer.polygon
#         if outer_poly is None or outer_poly.is_empty:
#             continue

#         area = outer_poly.area
#         is_trash = min_area > 0 and area < min_area
#         fill_color   = "#ffecec" if is_trash else "#eafaf1"
#         stroke_color = COLOR_TRASH if is_trash else COLOR_REAL
#         stroke_w     = 1.5

#         d = poly_to_svg_flipped(outer_poly)
#         lines.append(
#             f'<path d="{d}" fill="{fill_color}" '
#             f'stroke="{stroke_color}" stroke-width="{stroke_w}" '
#             f'fill-rule="evenodd" opacity="0.85"/>'
#         )

#         # Etichetta centroide
#         cx, cy = to_svg(*outer_poly.centroid.coords[0])
#         label = f"P{i}  {area:.1f} mm²"
#         suffix = " ← SCARTATO" if is_trash else ""
#         lines.append(
#             f'<text x="{cx:.1f}" y="{cy:.1f}" '
#             f'text-anchor="middle" dominant-baseline="middle" '
#             f'font-family="monospace" font-size="{font_size}" '
#             f'fill="{stroke_color}">{label}{suffix}</text>'
#         )

#         # Inner/hole
#         for inner in part.inners:
#             if inner.polygon is None or inner.polygon.is_empty:
#                 continue
#             d_inner = poly_to_svg_flipped(inner.polygon)
#             lines.append(
#                 f'<path d="{d_inner}" fill="#ecf0f1" '
#                 f'stroke="{COLOR_INNER}" stroke-width="1" opacity="0.7"/>'
#             )

#     lines.append('</svg>')

#     # 6. Salva
#     if output_path is None:
#         stem = os.path.splitext(dxf_path)[0]
#         output_path = stem + "_debug_contours.svg"

#     with open(output_path, "w", encoding="utf-8") as f:
#         f.write("\n".join(lines))

#     print(f"SVG salvato: {output_path}")

#     # 7. Stampa sommario a console
#     print(f"\n{'─'*55}")
#     print(f"{'#':<4} {'Area mm²':>10}  {'Fori':>5}  {'Stato'}")
#     print(f"{'─'*55}")
#     for i, part in enumerate(result.parts, start=1):
#         poly = part.outer.polygon
#         if poly is None:
#             continue
#         area   = poly.area
#         n_hole = len(part.inners)
#         stato  = "SCARTATO (< soglia)" if (min_area > 0 and area < min_area) else "OK"
#         print(f"{i:<4} {area:>10.2f}  {n_hole:>5}  {stato}")
#     print(f"{'─'*55}")
#     if result.warnings:
#         print("\nWarnings healer:")
#         for w in result.warnings:
#             print(f"  {w}")

#     return output_path


# # ---------------------------------------------------------------------------
# # CLI
# # ---------------------------------------------------------------------------

# if __name__ == "__main__":
#     parser = argparse.ArgumentParser(
#         description="Visualizza i contorni healati di un DXF con evidenziazione soglia."
#     )
#     parser.add_argument("dxf", help="Percorso del file DXF")
#     parser.add_argument(
#         "--min-area", type=float, default=DEFAULT_MIN_PART_AREA,
#         help=f"Soglia area mm² (default: {DEFAULT_MIN_PART_AREA})"
#     )
#     parser.add_argument(
#         "--tolerance", type=float, default=0.05,
#         help="Tolleranza healing mm (default: 0.05)"
#     )
#     parser.add_argument(
#         "--output", type=str, default=None,
#         help="Percorso SVG output (default: <stem>_debug_contours.svg)"
#     )
#     args = parser.parse_args()

#     if not os.path.isfile(args.dxf):
#         print(f"File non trovato: {args.dxf}", file=sys.stderr)
#         sys.exit(1)

#     debug_contours(
#         dxf_path=args.dxf,
#         min_area=args.min_area,
#         tolerance=args.tolerance,
#         output_path=args.output,
#     )


"""
debug_small_contours.py
-----------------
Visualizza i contorni trovati dall'healer su un file DXF,
colorandoli in base alla soglia di area.

    VERDE  → pezzo reale (area >= min_area)
    ROSSO  → artefatto   (area <  min_area)
    GRIGIO → inner/hole contenuti in un outer

Produce un SVG nella stessa cartella del DXF con suffisso _debug_contours.svg.

Dipendenze: ezdxf, shapely, forge (la tua libreria)
"""

import os
import ezdxf

from dxf_forge.workflow.healer import heal
from dxf_forge.workflow.splitter import DEFAULT_MIN_PART_AREA


# =========================================================
# INCOLLA QUI IL PATH
# =========================================================
dxf_path = r"c:\Users\FEDERICO\Documents\Python_Scripts\Projects\DXF\TON_23_04_2026\j0080281_nocornice.dxf"
min_area = DEFAULT_MIN_PART_AREA
tolerance = 0.05
output_path = None
# =========================================================


COLOR_REAL   = "#2ecc71"
COLOR_TRASH  = "#e74c3c"
COLOR_INNER  = "#95a5a6"
COLOR_LABEL  = "#2c3e50"
COLOR_BG     = "#fafafa"


def _poly_to_svg_path(polygon) -> str:
    def ring_to_d(coords):
        pts = list(coords)
        if not pts:
            return ""
        d = f"M {pts[0][0]:.3f} {pts[0][1]:.3f}"
        for x, y in pts[1:]:
            d += f" L {x:.3f} {y:.3f}"
        d += " Z"
        return d

    d = ring_to_d(polygon.exterior.coords)
    for interior in polygon.interiors:
        d += " " + ring_to_d(interior.coords)
    return d


def _bbox_all(polygons):
    minx = min(p.bounds[0] for p in polygons)
    miny = min(p.bounds[1] for p in polygons)
    maxx = max(p.bounds[2] for p in polygons)
    maxy = max(p.bounds[3] for p in polygons)
    return minx, miny, maxx, maxy


def debug_contours(
    dxf_path: str,
    min_area: float = DEFAULT_MIN_PART_AREA,
    tolerance: float = 0.05,
    output_path: str = None,
) -> str:

    doc = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()

    result = heal(
        msp,
        tolerance=tolerance,
        write_to_msp=False,
        label=os.path.splitext(os.path.basename(dxf_path))[0],
    )

    if not result.parts:
        print("Nessun contorno trovato dall'healer.")
        return ""

    all_polys = []
    for part in result.parts:
        if part.outer.polygon and not part.outer.polygon.is_empty:
            all_polys.append(part.outer.polygon)
        for inner in part.inners:
            if inner.polygon and not inner.polygon.is_empty:
                all_polys.append(inner.polygon)

    if not all_polys:
        print("Nessun polygon valido trovato.")
        return ""

    minx, miny, maxx, maxy = _bbox_all(all_polys)
    padding = max((maxx - minx), (maxy - miny)) * 0.05

    vw = maxx - minx + 2 * padding
    vh = maxy - miny + 2 * padding

    SVG_W = 1200
    SVG_H = int(SVG_W * vh / vw)

    scale = SVG_W / vw
    tx = -minx + padding
    ty = maxy + padding

    def to_svg(x, y):
        return (x + tx) * scale, (ty - y) * scale

    def poly_to_svg_flipped(polygon):
        def ring_to_d(coords):
            pts = [to_svg(x, y) for x, y in coords]
            if not pts:
                return ""
            d = f"M {pts[0][0]:.2f} {pts[0][1]:.2f}"
            for x, y in pts[1:]:
                d += f" L {x:.2f} {y:.2f}"
            d += " Z"
            return d

        d = ring_to_d(polygon.exterior.coords)
        for interior in polygon.interiors:
            d += " " + ring_to_d(interior.coords)
        return d

    font_size = max(8, int(SVG_W * 0.012))

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{SVG_W}" height="{SVG_H}">',
        f'<rect width="100%" height="100%" fill="{COLOR_BG}"/>',
        f'<text x="10" y="{font_size + 4}" font-size="{font_size}">{os.path.basename(dxf_path)}</text>',
    ]

    for i, part in enumerate(result.parts, start=1):
        outer_poly = part.outer.polygon
        if outer_poly is None or outer_poly.is_empty:
            continue

        area = outer_poly.area
        is_trash = min_area > 0 and area < min_area

        fill_color = "#ffecec" if is_trash else "#eafaf1"
        stroke_color = COLOR_TRASH if is_trash else COLOR_REAL

        d = poly_to_svg_flipped(outer_poly)

        lines.append(
            f'<path d="{d}" fill="{fill_color}" stroke="{stroke_color}" stroke-width="1.5" opacity="0.85"/>'
        )

        cx, cy = to_svg(*outer_poly.centroid.coords[0])
        lines.append(
            f'<text x="{cx:.1f}" y="{cy:.1f}" text-anchor="middle" font-size="{font_size}" fill="{stroke_color}">'
            f'P{i} {area:.1f}{" SCARTO" if is_trash else ""}</text>'
        )

        for inner in part.inners:
            if inner.polygon is None or inner.polygon.is_empty:
                continue
            d_inner = poly_to_svg_flipped(inner.polygon)
            lines.append(
                f'<path d="{d_inner}" fill="#ecf0f1" stroke="{COLOR_INNER}" stroke-width="1" opacity="0.7"/>'
            )

    lines.append("</svg>")

    if output_path is None:
        output_path = os.path.splitext(dxf_path)[0] + "_debug_contours.svg"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"SVG salvato: {output_path}")

    return output_path


# RUN DIRETTO
debug_contours(dxf_path, min_area, tolerance, output_path)