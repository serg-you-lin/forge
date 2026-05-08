# dashboard.py
# ---------------------------------------------------------------------------
# Separazione netta delle responsabilità:
#
#   PANNELLO INPUT  → logica raw DXF, identica a 09_plot_graph.py
#                     LINE/ARC/LWPOLYLINE diretti, CIRCLE come patch
#
#   PANNELLO OUTPUT → geometria Shapely dall'healer
#                     polygon.exterior.xy per fill, circle_to_polygon per cerchi
#
# entity_to_xy rimosso — non serve qui.
# ---------------------------------------------------------------------------

import os
import sys
import math
import argparse
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.gridspec import GridSpec
from pathlib import Path

project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

import ezdxf
import dxf_forge as forge
from dxf_forge.rules.layers import (
    LAYER_OUTER, LAYER_INNER, LAYER_HOLE, LAYER_BENDING, LAYER_MARKING, TRASH_LAYER,
    STRUCTURAL_LAYERS,
)
from dxf_forge.io.exporter import build_metadata

# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------

BG_DARK  = '#0d1117'
BG_PANEL = '#161b22'
BG_CARD  = '#1c2128'
BORDER   = '#30363d'
C_TEXT   = '#e6edf3'
C_DIM    = '#8b949e'
C_ACCENT = '#f78166'

LAYER_COLORS = {
    LAYER_OUTER   : ('#3fb950', 0.12, 2.0),
    LAYER_INNER   : ('#58a6ff', 0.12, 1.5),
    LAYER_HOLE    : ('#ff7b72', 0.15, 1.5),
    LAYER_BENDING : ('#ffa657', 0.0,  1.5),   # arancio — linee di piega, no fill
    LAYER_MARKING : ('#d2a8ff', 0.0,  1.2),   # viola  — marcature, no fill
    TRASH_LAYER   : ('#484f58', 0.0,  0.7),
}

_PALETTE = ['#ffa657', '#d2a8ff', '#79c0ff', '#56d364',
            '#e3b341', '#ff7b72', '#58a6ff', '#bc8cff']
_layer_color_cache = {}

def _layer_color(layer_name):
    key = layer_name.upper()
    if key not in _layer_color_cache:
        _layer_color_cache[key] = _PALETTE[len(_layer_color_cache) % len(_PALETTE)]
    return _layer_color_cache[key]

# ---------------------------------------------------------------------------
# Helpers geometrici raw — identici a 09_plot_graph.py
# (nessuna astrazione, nessun entity_to_xy)
# ---------------------------------------------------------------------------

def _arc_points(entity, n=64):
    """Punti (xs, ys) di un ARC — copia diretta da 09_plot_graph.py."""
    cx, cy = entity.dxf.center.x, entity.dxf.center.y
    r = entity.dxf.radius
    a0 = math.radians(entity.dxf.start_angle)
    a1 = math.radians(entity.dxf.end_angle)
    if a1 < a0:
        a1 += 2 * math.pi
    angles = np.linspace(a0, a1, n)
    return cx + r * np.cos(angles), cy + r * np.sin(angles)


def _spline_points(entity):
    """Punti (xs, ys) di una SPLINE tramite flattening."""
    pts = list(entity.flattening(0.01))
    return [p[0] for p in pts], [p[1] for p in pts]


def _lwpoly_points(entity):
    """Punti (xs, ys) di una LWPOLYLINE — grezzi, senza bulge."""
    pts = list(entity.get_points('xy'))
    if entity.closed and pts:
        pts.append(pts[0])
    return [p[0] for p in pts], [p[1] for p in pts]


# ---------------------------------------------------------------------------
# Ax setup
# ---------------------------------------------------------------------------

def _setup_ax(ax, title):
    ax.set_facecolor(BG_PANEL)
    ax.tick_params(colors=C_DIM, labelsize=7)
    for spine in ax.spines.values():
        spine.set_color(BORDER)
    ax.set_title(title, color=C_TEXT, fontsize=9,
                 fontweight='bold', pad=8, fontfamily='monospace')
    ax.set_aspect('equal')

# ---------------------------------------------------------------------------
# Pannello 1 — INPUT (logica raw DXF, stile 09_plot_graph.py)
# ---------------------------------------------------------------------------

def plot_original(ax, msp, filename):
    _setup_ax(ax, f"INPUT  ·  {filename}")
    legend_seen = {}

    for entity in msp:
        layer    = entity.dxf.layer if entity.dxf.hasattr('layer') else '0'
        color    = _layer_color(layer)
        dxftype  = entity.dxftype()

        try:
            if dxftype == 'LINE':
                ax.plot(
                    [entity.dxf.start.x, entity.dxf.end.x],
                    [entity.dxf.start.y, entity.dxf.end.y],
                    color=color, linewidth=1.2, zorder=3,
                )

            elif dxftype == 'ARC':
                xs, ys = _arc_points(entity)
                ax.plot(xs, ys, color=color, linewidth=1.2, zorder=3)

            elif dxftype == 'CIRCLE':
                patch = plt.Circle(
                    (entity.dxf.center.x, entity.dxf.center.y),
                    entity.dxf.radius,
                    fill=False, color=color, linewidth=1.2, zorder=3,
                )
                ax.add_patch(patch)

            elif dxftype == 'LWPOLYLINE':
                xs, ys = _lwpoly_points(entity)
                ax.plot(xs, ys, color=color, linewidth=1.2, zorder=3)

            elif dxftype == 'SPLINE':
                xs, ys = _spline_points(entity)
                ax.plot(xs, ys, color=color, linewidth=1.2, zorder=3)

            else:
                continue

            if layer not in legend_seen:
                legend_seen[layer] = color

        except Exception:
            pass

    _add_legend(ax, legend_seen)

# ---------------------------------------------------------------------------
# Pannello 2 — OUTPUT (geometria Shapely dall'healer)
# ---------------------------------------------------------------------------

def plot_healed(ax, msp_healed, result, filename):
    _setup_ax(ax, f"OUTPUT  ·  {filename}")
    legend_seen = {}

    # --- Contorni strutturali dall'healer (ForgeContour → polygon Shapely) ---
    for part in result.parts:
        for contour in [part.outer] + part.inners:
            _draw_contour(ax, contour, legend_seen)

        # label centroide
        try:
            cx = part.outer.polygon.centroid.x
            cy = part.outer.polygon.centroid.y
            ax.annotate(
                f"A = {part.area:.0f} mm²\n{len(part.inners)} holes",
                (cx, cy),
                fontsize=7, color=C_TEXT, ha='center', va='center',
                fontfamily='monospace',
                bbox=dict(boxstyle='round,pad=0.3',
                          facecolor=BG_CARD, edgecolor='#3fb950',
                          alpha=0.88),
                zorder=6,
            )
        except Exception:
            pass

    # --- Entità residue dal msp: Trash + Special layers (entità raw) ---
    # I contorni strutturali sono già nei ForgeContour sopra.
    # Qui disegniamo tutto il resto: Trash, Bending, Marking, ecc.
    SKIP_LAYERS = STRUCTURAL_LAYERS  # OuterContour, InnerContour, Hole già nei ForgeContour
    for entity in msp_healed:
        layer = entity.dxf.layer if entity.dxf.hasattr('layer') else ''
        if layer.upper() in SKIP_LAYERS:
            continue
        lname, (color, _alpha, lw) = _get_layer_cfg(layer)
        dxftype = entity.dxftype()
        try:
            if dxftype == 'LINE':
                ax.plot(
                    [entity.dxf.start.x, entity.dxf.end.x],
                    [entity.dxf.start.y, entity.dxf.end.y],
                    color=color, linewidth=lw, zorder=4,
                )
            elif dxftype == 'ARC':
                xs, ys = _arc_points(entity)
                ax.plot(xs, ys, color=color, linewidth=lw, zorder=4)
            elif dxftype == 'LWPOLYLINE':
                xs, ys = _lwpoly_points(entity)
                ax.plot(xs, ys, color=color, linewidth=lw, zorder=4)
            elif dxftype == 'SPLINE':
                xs, ys = _spline_points(entity)
                ax.plot(xs, ys, color=color, linewidth=lw, zorder=4)
            else:
                continue
            if lname not in legend_seen:
                legend_seen[lname] = color
        except Exception:
            pass

    _add_legend(ax, legend_seen)


def _draw_contour(ax, contour, legend_seen):
    """
    Disegna un ForgeContour (outer o inner) dal suo polygon Shapely.
    ForgeContour ha .layer e .polygon direttamente — nessun .entity.
    """
    layer          = contour.layer or ''
    lname, (color, alpha, lw) = _get_layer_cfg(layer)

    try:
        x, y = contour.polygon.exterior.xy
        if alpha > 0:
            ax.fill(x, y, color=color, alpha=alpha, zorder=2)
        ax.plot(x, y, color=color, linewidth=lw, zorder=3)
        if lname not in legend_seen:
            legend_seen[lname] = color
    except Exception:
        pass


def _get_layer_cfg(layer: str):
    """Restituisce (lname, (color, alpha, lw)) per un dato layer."""
    for lname, lcfg in LAYER_COLORS.items():
        if lname.lower() == layer.lower():
            return lname, lcfg
    color = _layer_color(layer)
    return layer, (color, 0.05, 1.0)

# ---------------------------------------------------------------------------
# Legenda condivisa
# ---------------------------------------------------------------------------

def _add_legend(ax, legend_seen):
    if not legend_seen:
        return
    handles = [mpatches.Patch(color=c, label=n)
               for n, c in legend_seen.items()]
    ax.legend(handles=handles, loc='upper right',
              facecolor=BG_CARD, edgecolor=BORDER,
              labelcolor=C_TEXT, fontsize=6.5, framealpha=0.92)

# ---------------------------------------------------------------------------
# Pannello 3 — METADATA
# ---------------------------------------------------------------------------

def plot_metadata(ax, result, filename, tolerance):
    ax.set_facecolor(BG_PANEL)
    ax.axis('off')
    ax.set_title('METADATA', color=C_TEXT, fontsize=9,
                 fontweight='bold', pad=8, fontfamily='monospace')

    rows = []
    rows.append(('FILE',      Path(filename).name, C_TEXT))
    rows.append(('TOLERANCE', f'{tolerance} mm',   C_DIM))
    rows.append(('VALID',     str(result.is_valid),
                 '#3fb950' if result.is_valid else C_ACCENT))
    rows.append(('PARTS',     str(result.part_count), C_TEXT))
    rows.append(('', '', C_DIM))

    for i, part in enumerate(result.parts):
        meta = build_metadata(part)
        rows.append((f'── PART {i+1}', meta.get('label', '—'), C_ACCENT))

        # mostra tutti i campi nell'ordine in cui li esporti
        for key, val in meta.items():
            if key == 'label':
                continue  # già nel titolo del part
            if isinstance(val, dict):
                # bbox → espansa su una riga compatta
                inner = '  '.join(f"{k}={round(v,1)}" for k, v in val.items())
                rows.append((f'   {key}', inner, C_DIM))
            elif isinstance(val, float):
                rows.append((f'   {key}', f'{val:.2f}', C_TEXT))
            else:
                rows.append((f'   {key}', str(val), C_TEXT))

        rows.append(('', '', C_DIM))

    n    = len(rows)
    step = 1.0 / max(n, 1)
    for i, (key, val, color) in enumerate(rows):
        y = 1.0 - (i + 0.5) * step
        if key:
            ax.text(0.03, y, key, transform=ax.transAxes,
                    fontsize=7, color=C_DIM,
                    fontfamily='monospace', va='center')
            ax.text(0.52, y, val, transform=ax.transAxes,
                    fontsize=7, color=color,
                    fontfamily='monospace', va='center',
                    fontweight='bold')

# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def run(input_dxf, tolerance=0.05, output_png=None, special_layers=None):
    # --- Carica il DXF originale (solo per il pannello INPUT) ---
    doc_orig = ezdxf.readfile(input_dxf)
    if doc_orig.dxfversion < 'AC1015':
        doc_orig = forge.upgrade_to_r2010(doc_orig)
    msp_orig = doc_orig.modelspace()

    # --- Heal su una copia (per il pannello OUTPUT) ---
    doc_healed = ezdxf.readfile(input_dxf)
    if doc_healed.dxfversion < 'AC1015':
        doc_healed = forge.upgrade_to_r2010(doc_healed)
    msp_healed = doc_healed.modelspace()

    result = forge.heal(
        msp_healed,
        tolerance=tolerance,
        write_to_msp=True,
        label=Path(input_dxf).stem,
        source_file=Path(input_dxf).name,
        special_layers=special_layers,
    )

    # --- Layout ---
    fig = plt.figure(figsize=(20, 9), facecolor=BG_DARK)
    gs  = GridSpec(1, 3, figure=fig,
                   width_ratios=[2.5, 2.5, .8],
                   wspace=0.03,
                   left=0.01, right=0.99,
                   top=0.91, bottom=0.06)

    ax_orig   = fig.add_subplot(gs[0])
    ax_healed = fig.add_subplot(gs[1])
    ax_meta   = fig.add_subplot(gs[2])

    filename = Path(input_dxf).name

    plot_original(ax_orig,   msp_orig,                    filename)
    plot_healed(ax_healed,   msp_healed, result,           filename)
    plot_metadata(ax_meta,   result,     filename,         tolerance)

    # --- Scala condivisa INPUT / OUTPUT ---
    for ax in (ax_orig, ax_healed):
        ax.autoscale()

    all_xlims = [ax_orig.get_xlim(), ax_healed.get_xlim()]
    all_ylims = [ax_orig.get_ylim(), ax_healed.get_ylim()]

    xmin = min(x[0] for x in all_xlims)
    xmax = max(x[1] for x in all_xlims)
    ymin = min(y[0] for y in all_ylims)
    ymax = max(y[1] for y in all_ylims)

    margin = max(xmax - xmin, ymax - ymin) * 0.06

    for ax in (ax_orig, ax_healed):
        ax.set_xlim(xmin - margin, xmax + margin)
        ax.set_ylim(ymin - margin, ymax + margin)

    # --- Salva ---
    if output_png is None:
        output_png = str(Path(input_dxf).with_suffix('')) + '_dashboard.png'

    plt.savefig(output_png, dpi=150, bbox_inches='tight', facecolor=BG_DARK)
    plt.show()
    return output_png


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--dxf',       default=r'c:\Users\FEDERICO\Documents\Python_Scripts\Projects\DXF\ARC\6200012808 Sviluppo\6200012808_2.dxf')
    parser.add_argument('--tolerance', type=float, default=5)
    parser.add_argument('--output',    default=None)
    args = parser.parse_args()

    run(
        input_dxf=args.dxf,
        tolerance=args.tolerance,
        output_png=args.output,
        special_layers={
            'MARK':      'engrave',
            'MARCATURA': 'bending',
        },
    )