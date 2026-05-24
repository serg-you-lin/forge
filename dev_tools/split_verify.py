# split_verify.py
# ---------------------------------------------------------------------------
# Dashboard di verifica post-split.
#
# Per ogni ForgePart confronta la geometria originale (ForgeResult in memoria)
# con quella esportata (DXF figlio su disco o doc ezdxf in memoria).
#
# Layout per pezzo (1 riga × 4 colonne):
#   [Originale] [Esportato] [Overlay] [Diff Shapely] | colonna numerica
#
# Uso rapido:
#   from split_verify import run
#
#   # modalità A — tutto da disco
#   run("sorgente.dxf", output_folder="./out")
#
#   # modalità B — file figli già in memoria
#   result = forge.split_to_files(msp, "./out", label="pezzo")
#   run("sorgente.dxf", result=result, child_docs=[doc1, doc2])
#
# ---------------------------------------------------------------------------

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path
from typing import Optional

import ezdxf
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.gridspec import GridSpec, GridSpecFromSubplotSpec
from shapely.geometry import Polygon
from shapely.ops import unary_union

project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

import dxf_forge as forge
from dxf_forge.io.exporter import build_metadata
from dxf_forge.models import ForgePart, ForgeResult
from dxf_forge.rules.layers import LAYER_HOLE, LAYER_INNER, LAYER_OUTER

# ---------------------------------------------------------------------------
# Palette (coerente con dashboard.py)
# ---------------------------------------------------------------------------

BG_DARK  = '#0d1117'
BG_PANEL = '#161b22'
BG_CARD  = '#1c2128'
BORDER   = '#30363d'
C_TEXT   = '#e6edf3'
C_DIM    = '#8b949e'
C_ACCENT = '#f78166'

C_ORIG     = '#3fb950'   # verde  — originale
C_EXP      = '#58a6ff'   # blu    — esportato
C_OVERLAY  = '#ffa657'   # arancio — overlay
C_DIFF     = '#f78166'   # rosso  — diff (ideale: assente)
C_HOLE     = '#ff7b72'
ALPHA_FILL = 0.18

PASS_COLOR = '#3fb950'
FAIL_COLOR = '#f78166'

# soglia default: diff area < 0.1 mm² → PASS
DEFAULT_DIFF_THRESHOLD = 0.1


# ---------------------------------------------------------------------------
# Helpers geometrici (stessa logica di dashboard.py)
# ---------------------------------------------------------------------------

def _arc_points(entity, n: int = 64):
    cx, cy = entity.dxf.center.x, entity.dxf.center.y
    r  = entity.dxf.radius
    a0 = math.radians(entity.dxf.start_angle)
    a1 = math.radians(entity.dxf.end_angle)
    if a1 < a0:
        a1 += 2 * math.pi
    angles = np.linspace(a0, a1, n)
    return cx + r * np.cos(angles), cy + r * np.sin(angles)


def _lwpoly_points(entity):
    pts = list(entity.get_points('xy'))
    if entity.closed and pts:
        pts.append(pts[0])
    return [p[0] for p in pts], [p[1] for p in pts]


def _spline_points(entity):
    pts = list(entity.flattening(0.01))
    return [p[0] for p in pts], [p[1] for p in pts]


# ---------------------------------------------------------------------------
# Estrazione polygon da ForgePart (originale, già in memoria)
# ---------------------------------------------------------------------------

def _polygon_from_part(part: ForgePart) -> Optional[Polygon]:
    """
    Restituisce il polygon Shapely dell'outer di un ForgePart.
    I fori (inners) vengono sottratti → polygon "reale" del pezzo.
    """
    try:
        outer = part.outer.polygon
        holes = [c.polygon for c in part.inners if c.polygon is not None]
        if holes:
            outer = outer.difference(unary_union(holes))
        return outer
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Estrazione polygon da un DXF figlio (esportato)
# ---------------------------------------------------------------------------

def _heal_child_doc(doc) -> Optional[Polygon]:
    """
    Re-heal di un documento figlio ezdxf per estrarne il polygon Shapely.
    Il figlio ha già un solo pezzo → prendiamo parts[0].
    """
    try:
        msp    = doc.modelspace()
        result = forge.heal(msp, tolerance=0.05)
        if result.parts:
            return _polygon_from_part(result.parts[0])
    except Exception:
        pass
    return None


def _load_child_doc(dxf_path: str):
    """Carica un DXF figlio da disco."""
    doc = ezdxf.readfile(dxf_path)
    if doc.dxfversion < 'AC1015':
        doc = forge.upgrade_to_r2010(doc)
    return doc


# ---------------------------------------------------------------------------
# Ax helpers
# ---------------------------------------------------------------------------

def _setup_ax(ax, title: str, subtitle: str = ''):
    ax.set_facecolor(BG_PANEL)
    ax.tick_params(colors=C_DIM, labelsize=6)
    for spine in ax.spines.values():
        spine.set_color(BORDER)
    full_title = f"{title}\n{subtitle}" if subtitle else title
    ax.set_title(full_title, color=C_TEXT, fontsize=7.5,
                 fontweight='bold', pad=6, fontfamily='monospace')
    ax.set_aspect('equal')


def _draw_polygon(ax, poly: Polygon, color: str, alpha: float,
                  lw: float = 1.5, zorder: int = 3):
    """Disegna un Polygon Shapely (con eventuali fori) su ax."""
    if poly is None or poly.is_empty:
        return
    geoms = list(poly.geoms) if poly.geom_type == 'MultiPolygon' else [poly]
    for g in geoms:
        x, y = g.exterior.xy
        ax.fill(x, y, color=color, alpha=alpha, zorder=zorder)
        ax.plot(x, y, color=color, linewidth=lw, zorder=zorder + 1)
        for interior in g.interiors:
            ix, iy = interior.xy
            ax.fill(ix, iy, color=BG_PANEL, alpha=1.0, zorder=zorder + 1)
            ax.plot(ix, iy, color=C_HOLE, linewidth=lw * 0.8,
                    zorder=zorder + 2)


def _sync_axes(axes):
    """Imposta limiti uguali su una lista di assi (scala condivisa)."""
    all_xlim = [ax.get_xlim() for ax in axes]
    all_ylim = [ax.get_ylim() for ax in axes]
    xmin = min(x[0] for x in all_xlim)
    xmax = max(x[1] for x in all_xlim)
    ymin = min(y[0] for y in all_ylim)
    ymax = max(y[1] for y in all_ylim)
    span   = max(xmax - xmin, ymax - ymin)
    margin = span * 0.08
    for ax in axes:
        ax.set_xlim(xmin - margin, xmax + margin)
        ax.set_ylim(ymin - margin, ymax + margin)


# ---------------------------------------------------------------------------
# Pannelli per singolo pezzo
# ---------------------------------------------------------------------------

def _panel_original(ax, poly_orig: Optional[Polygon], part_label: str):
    _setup_ax(ax, 'ORIGINALE', part_label)
    if poly_orig:
        _draw_polygon(ax, poly_orig, C_ORIG, ALPHA_FILL)
        ax.autoscale()
    else:
        ax.text(0.5, 0.5, 'n/d', transform=ax.transAxes,
                color=C_DIM, ha='center', va='center', fontsize=9)


def _panel_exported(ax, poly_exp: Optional[Polygon], child_label: str):
    _setup_ax(ax, 'ESPORTATO', child_label)
    if poly_exp:
        _draw_polygon(ax, poly_exp, C_EXP, ALPHA_FILL)
        ax.autoscale()
    else:
        ax.text(0.5, 0.5, 'n/d', transform=ax.transAxes,
                color=C_DIM, ha='center', va='center', fontsize=9)


def _panel_overlay(ax, poly_orig: Optional[Polygon],
                   poly_exp: Optional[Polygon]):
    _setup_ax(ax, 'OVERLAY')
    if poly_orig:
        _draw_polygon(ax, poly_orig, C_ORIG, 0.25, lw=1.8)
    if poly_exp:
        _draw_polygon(ax, poly_exp, C_EXP,  0.25, lw=1.2)
    ax.autoscale()
    handles = [
        mpatches.Patch(color=C_ORIG, label='originale', alpha=0.7),
        mpatches.Patch(color=C_EXP,  label='esportato', alpha=0.7),
    ]
    ax.legend(handles=handles, loc='upper right',
              facecolor=BG_CARD, edgecolor=BORDER,
              labelcolor=C_TEXT, fontsize=6, framealpha=0.9)


def _panel_diff(ax, diff_poly: Optional[Polygon]):
    _setup_ax(ax, 'DIFF (sym)')
    if diff_poly and not diff_poly.is_empty:
        _draw_polygon(ax, diff_poly, C_DIFF, 0.45, lw=1.2)
        ax.autoscale()
    else:
        # nessuna diff → PASS visivo
        ax.text(0.5, 0.5, '✓ IDENTICI', transform=ax.transAxes,
                color=PASS_COLOR, ha='center', va='center',
                fontsize=11, fontweight='bold', fontfamily='monospace')


# ---------------------------------------------------------------------------
# Colonna numerica
# ---------------------------------------------------------------------------

def _compute_metrics(poly_orig: Optional[Polygon],
                     poly_exp:  Optional[Polygon],
                     diff_poly: Optional[Polygon],
                     threshold: float) -> dict:
    """Calcola le metriche di confronto."""
    m = {}
    m['area_orig']    = poly_orig.area      if poly_orig else None
    m['area_exp']     = poly_exp.area       if poly_exp  else None
    m['perim_orig']   = poly_orig.length    if poly_orig else None
    m['perim_exp']    = poly_exp.length     if poly_exp  else None
    m['diff_area']    = diff_poly.area      if (diff_poly and not diff_poly.is_empty) else 0.0

    def delta_pct(a, b):
        if a and b and a != 0:
            return abs(b - a) / a * 100
        return None

    m['delta_area_pct']  = delta_pct(m['area_orig'],  m['area_exp'])
    m['delta_perim_pct'] = delta_pct(m['perim_orig'], m['perim_exp'])
    m['pass']            = (m['diff_area'] <= threshold
                            and poly_orig is not None
                            and poly_exp  is not None)
    return m


def _panel_metrics(ax, metrics: dict, part_idx: int, threshold: float):
    ax.set_facecolor(BG_PANEL)
    ax.axis('off')

    verdict       = '✓  PASS' if metrics['pass'] else '✗  FAIL'
    verdict_color = PASS_COLOR if metrics['pass'] else FAIL_COLOR

    ax.text(0.5, 0.97, f'PART {part_idx + 1}', transform=ax.transAxes,
            color=C_TEXT, ha='center', va='top',
            fontsize=8, fontweight='bold', fontfamily='monospace')
    ax.text(0.5, 0.88, verdict, transform=ax.transAxes,
            color=verdict_color, ha='center', va='top',
            fontsize=10, fontweight='bold', fontfamily='monospace')

    def _fmt(v, decimals=2):
        return f'{v:.{decimals}f}' if v is not None else '—'

    def _fmt_pct(v):
        return f'{v:.3f} %' if v is not None else '—'

    rows = [
        ('area orig',   f"{_fmt(metrics['area_orig'])} mm²"),
        ('area exp',    f"{_fmt(metrics['area_exp'])} mm²"),
        ('Δ area',      _fmt_pct(metrics['delta_area_pct'])),
        ('',            ''),
        ('perim orig',  f"{_fmt(metrics['perim_orig'])} mm"),
        ('perim exp',   f"{_fmt(metrics['perim_exp'])} mm"),
        ('Δ perim',     _fmt_pct(metrics['delta_perim_pct'])),
        ('',            ''),
        ('diff area',   f"{_fmt(metrics['diff_area'])} mm²"),
        ('soglia',      f'{threshold} mm²'),
    ]

    n    = len(rows)
    step = 0.68 / max(n, 1)
    for i, (k, v) in enumerate(rows):
        y = 0.76 - i * step
        if not k:
            continue
        ax.text(0.04, y, k, transform=ax.transAxes,
                color=C_DIM, fontsize=6.5, fontfamily='monospace', va='center')
        ax.text(0.96, y, v, transform=ax.transAxes,
                color=C_TEXT, fontsize=6.5, fontfamily='monospace',
                va='center', ha='right', fontweight='bold')

    # linea separatrice verticale sinistra
    ax.axvline(0, color=BORDER, linewidth=0.8)


# ---------------------------------------------------------------------------
# Risoluzione dei child: disco o memoria
# ---------------------------------------------------------------------------

def _resolve_children(
    result:       ForgeResult,
    output_folder: Optional[str],
    child_docs:    Optional[list],
) -> list:
    """
    Restituisce una lista di (doc_or_None, label_str) allineata a result.parts.

    Priorità:
      1. child_docs in memoria (se fornita)
      2. output_folder su disco  (cerca file per label/index)
      3. None se nessuno dei due disponibile
    """
    children = []

    if child_docs is not None:
        # modalità B — in memoria: allineamento posizionale
        for i, part in enumerate(result.parts):
            doc   = child_docs[i] if i < len(child_docs) else None
            label = getattr(part, 'label', None) or f'part_{i + 1}'
            children.append((doc, label))
        return children

    if output_folder is not None:
        folder = Path(output_folder)
        for i, part in enumerate(result.parts):
            label = getattr(part, 'label', None) or f'part_{i + 1}'
            # cerca file: label.dxf, label.DXF, o part_{i+1}.dxf
            candidates = [
                folder / f'{label}.dxf',
                folder / f'{label}.DXF',
                folder / f'part_{i + 1}.dxf',
                folder / f'part_{i + 1}.DXF',
            ]
            doc = None
            for path in candidates:
                if path.exists():
                    try:
                        doc = _load_child_doc(str(path))
                        label = path.name
                    except Exception:
                        pass
                    break
            children.append((doc, label))
        return children

    # nessuna sorgente → tutto None
    return [(None, getattr(p, 'label', f'part_{i+1}'))
            for i, p in enumerate(result.parts)]


# ---------------------------------------------------------------------------
# MAIN — run()
# ---------------------------------------------------------------------------

def run(
    source_dxf:    str,
    output_folder: Optional[str]       = None,
    result:        Optional[ForgeResult] = None,
    child_docs:    Optional[list]      = None,
    tolerance:     float               = 0.05,
    diff_threshold: float              = DEFAULT_DIFF_THRESHOLD,
    special_layers: Optional[dict]     = None,
    output_png:    Optional[str]       = None,
) -> str:
    """
    Genera la dashboard di verifica post-split.

    Args:
        source_dxf:     percorso del DXF sorgente
        output_folder:  cartella con i DXF figli (modalità disco)
        result:         ForgeResult già calcolato (opzionale — se None viene
                        ricalcolato internamente da source_dxf)
        child_docs:     lista di doc ezdxf in memoria (modalità in-memory)
        tolerance:      tolleranza per l'heal interno (usata se result=None)
        diff_threshold: area max della symmetric_difference per PASS [mm²]
        special_layers: dict {layer: work_type} passato a heal
        output_png:     path PNG di output (default: source_dxf + _verify.png)

    Returns:
        Path del PNG salvato.
    """

    # ------------------------------------------------------------------ #
    # STEP 1 — heal del sorgente (se non già fatto)
    # ------------------------------------------------------------------ #
    doc_src = ezdxf.readfile(source_dxf)
    if doc_src.dxfversion < 'AC1015':
        doc_src = forge.upgrade_to_r2010(doc_src)
    msp_src = doc_src.modelspace()

    if result is None:
        result = forge.heal(
            msp_src,
            tolerance=tolerance,
            label=Path(source_dxf).stem,
            source_file=Path(source_dxf).name,
        )

    if not result.parts:
        print('[split_verify] Nessun pezzo trovato nel sorgente — uscita.')
        return ''

    # ------------------------------------------------------------------ #
    # STEP 2 — risolvi i figli
    # ------------------------------------------------------------------ #
    children = _resolve_children(result, output_folder, child_docs)

    n_parts = len(result.parts)

    # ------------------------------------------------------------------ #
    # STEP 3 — layout matplotlib
    #
    # Griglia:  n_parts righe × 2 colonne principali
    #           colonna 0 (larga): 4 pannelli geometrici side-by-side
    #           colonna 1 (stretta): metriche numeriche
    # ------------------------------------------------------------------ #
    fig = plt.figure(
        figsize=(22, 5.5 * n_parts),
        facecolor=BG_DARK,
    )

    # titolo globale
    fig.suptitle(
        f'SPLIT VERIFY  ·  {Path(source_dxf).name}'
        f'   |   {n_parts} part{"i" if n_parts != 1 else "e"}'
        f'   |   soglia diff = {diff_threshold} mm²',
        color=C_TEXT, fontsize=10, fontweight='bold',
        fontfamily='monospace', y=0.995,
    )

    outer_gs = GridSpec(
        n_parts, 2,
        figure=fig,
        width_ratios=[5, 1],          # 4 pannelli geo : 1 colonna metriche
        hspace=0.35,
        wspace=0.03,
        left=0.01, right=0.99,
        top=0.97, bottom=0.03,
    )

    for i, (part, (child_doc, child_label)) in enumerate(
            zip(result.parts, children)):

        # ---- polygon originale ----
        poly_orig = _polygon_from_part(part)

        # ---- polygon esportato ----
        poly_exp = _heal_child_doc(child_doc) if child_doc is not None else None

        # ---- symmetric difference ----
        diff_poly = None
        if poly_orig is not None and poly_exp is not None:
            try:
                diff_poly = poly_orig.symmetric_difference(poly_exp)
            except Exception:
                pass

        # ---- metriche ----
        metrics = _compute_metrics(poly_orig, poly_exp, diff_poly,
                                   diff_threshold)

        # ---- subgrid 1×4 per i pannelli geometrici ----
        inner_gs = GridSpecFromSubplotSpec(
            1, 4,
            subplot_spec=outer_gs[i, 0],
            wspace=0.04,
        )

        ax_orig    = fig.add_subplot(inner_gs[0])
        ax_exp     = fig.add_subplot(inner_gs[1])
        ax_overlay = fig.add_subplot(inner_gs[2])
        ax_diff    = fig.add_subplot(inner_gs[3])

        part_label = getattr(part, 'label', None) or f'part_{i + 1}'

        _panel_original(ax_orig,    poly_orig, part_label)
        _panel_exported(ax_exp,     poly_exp,  child_label)
        _panel_overlay(ax_overlay,  poly_orig, poly_exp)
        _panel_diff(ax_diff,        diff_poly)

        # scala condivisa sui 4 pannelli geometrici
        for ax in (ax_orig, ax_exp, ax_overlay, ax_diff):
            ax.autoscale()
        _sync_axes([ax_orig, ax_exp, ax_overlay, ax_diff])

        # ---- colonna metriche ----
        ax_meta = fig.add_subplot(outer_gs[i, 1])
        _panel_metrics(ax_meta, metrics, i, diff_threshold)

    # ------------------------------------------------------------------ #
    # STEP 4 — salva
    # ------------------------------------------------------------------ #
    if output_png is None:
        output_png = str(Path(source_dxf).with_suffix('')) + '_verify.png'

    plt.savefig(output_png, dpi=150, bbox_inches='tight', facecolor=BG_DARK)
    plt.show()
    print(f'[split_verify] Salvato: {output_png}')
    return output_png


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Verifica visiva + numerica del post-split DXF'
    )
    parser.add_argument(
        '--dxf',
        default=r'c:\Users\FEDERICO\Documents\Python_Scripts\Projects\DXF\TON_06_05_2026\intricato_doppio.dxf',
        help='DXF sorgente',
    )
    parser.add_argument(
        '--folder',
        default=None,
        help='Cartella con i DXF figli (se già splittati su disco)',
    )
    parser.add_argument(
        '--tolerance',
        type=float,
        default=0.05,
        help='Tolleranza heal [mm]',
    )
    parser.add_argument(
        '--threshold',
        type=float,
        default=DEFAULT_DIFF_THRESHOLD,
        help='Soglia area diff per PASS [mm²]',
    )
    parser.add_argument('--output', default=None, help='PNG di output')
    args = parser.parse_args()

    run(
        source_dxf=args.dxf,
        output_folder=args.folder,
        tolerance=args.tolerance,
        diff_threshold=args.threshold,
        output_png=args.output,
    )