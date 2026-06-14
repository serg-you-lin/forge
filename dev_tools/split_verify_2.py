# split_verify.py
# ---------------------------------------------------------------------------
# Dashboard di verifica post-split.
#
# Per ogni ForgePart confronta la geometria originale (ForgeResult in memoria)
# con quella esportata (DXF figlio su disco o doc ezdxf in memoria).
#
# Layout per pezzo (1 riga × 2 colonne geometriche + metriche):
#   [Overlay con toggle orig/exp] [Diff Shapely] | Metriche
#
# Toggle interattivi (Button matplotlib) per mostrare/nascondere
# il layer originale e/o esportato nell'overlay — uno per riga/pezzo.
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
from matplotlib.widgets import Button
from shapely.geometry import Polygon
from shapely.ops import unary_union

project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

import dxf_forge as forge
from dxf_forge.core.models import ForgePart, ForgeResult

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

C_ORIG   = '#3fb950'   # verde   — originale
C_EXP    = '#58a6ff'   # blu     — esportato
C_DIFF   = '#f78166'   # rosso   — diff
C_HOLE   = '#ff7b72'
ALPHA_FILL = 0.20

PASS_COLOR = '#3fb950'
FAIL_COLOR = '#f78166'

DEFAULT_DIFF_THRESHOLD = 0.1  # mm²


# ---------------------------------------------------------------------------
# Helpers geometrici
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
# Estrazione polygon Shapely
# ---------------------------------------------------------------------------

def _polygon_from_part(part: ForgePart) -> Optional[Polygon]:
    """Polygon dell'outer con fori sottratti."""
    try:
        outer = part.outer.polygon
        holes = [c.polygon for c in part.inners if c.polygon is not None]
        if holes:
            outer = outer.difference(unary_union(holes))
        return outer
    except Exception:
        return None


def _lwpoly_to_shapely(entity) -> Optional[Polygon]:
    """Converte una LWPOLYLINE chiusa in Polygon Shapely."""
    try:
        pts = list(entity.get_points('xy'))
        if len(pts) < 3:
            return None
        return Polygon(pts)
    except Exception:
        return None


def _read_child_polygon(doc) -> Optional[Polygon]:
    """
    Legge il polygon dal DXF figlio già scritto da write().
    Le LWPOLYLINE sono già sui layer forge (OuterContour, InnerContour, Hole).
    Nessun re-heal: leggiamo direttamente e costruiamo il polygon Shapely.

    Analogia: write() ha già stampato il risultato sul DXF —
    noi lo rileggiamo come testo stampato, non lo rielaboriamo da zero.
    """
    from dxf_forge.rules.layers import LAYER_OUTER, LAYER_INNER, LAYER_HOLE

    try:
        msp = doc.modelspace()
        outer_poly = None
        hole_polys = []

        for entity in msp:
            if entity.dxftype() != 'LWPOLYLINE':
                continue
            layer = (entity.dxf.layer or '').upper()
            poly  = _lwpoly_to_shapely(entity)
            if poly is None or not poly.is_valid or poly.is_empty:
                continue
            if layer == LAYER_OUTER.upper():
                if outer_poly is None or poly.area > outer_poly.area:
                    outer_poly = poly
            elif layer in (LAYER_INNER.upper(), LAYER_HOLE.upper()):
                hole_polys.append(poly)

        if outer_poly is None:
            return None
        if hole_polys:
            outer_poly = outer_poly.difference(unary_union(hole_polys))
        return outer_poly

    except Exception as e:
        print(f'[split_verify] _read_child_polygon error: {e}')
        return None


def _load_child_doc(dxf_path: str):
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
                  lw: float = 1.5, zorder: int = 3) -> list:
    """
    Disegna un Polygon Shapely su ax.
    Restituisce la lista degli Artist creati (per poterli nascondere/mostrare).
    """
    artists = []
    if poly is None or poly.is_empty:
        return artists
    geoms = list(poly.geoms) if poly.geom_type == 'MultiPolygon' else [poly]
    for g in geoms:
        x, y = g.exterior.xy
        artists.append(ax.fill(x, y, color=color, alpha=alpha, zorder=zorder)[0])
        artists.append(ax.plot(x, y, color=color, linewidth=lw, zorder=zorder + 1)[0])
        for interior in g.interiors:
            ix, iy = interior.xy
            artists.append(ax.fill(ix, iy, color=BG_PANEL, alpha=1.0, zorder=zorder + 1)[0])
            artists.append(ax.plot(ix, iy, color=C_HOLE, linewidth=lw * 0.8, zorder=zorder + 2)[0])
    return artists


def _sync_axes(axes):
    """Scala condivisa su una lista di assi."""
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
# Pannello overlay con toggle
# ---------------------------------------------------------------------------

class OverlayToggle:
    """
    Gestisce i due Button (ORIG / EXP) per accendere/spegnere i layer
    nell'overlay di un singolo pezzo.

    Pensalo come un interruttore della luce con due circuiti indipendenti:
    ogni pulsante controlla la visibilità di un gruppo di Artist matplotlib,
    senza toccare l'altro.
    """

    def __init__(self, fig, ax_overlay,
                 artists_orig: list, artists_exp: list,
                 btn_ax_orig, btn_ax_exp):
        self._ax      = ax_overlay
        self._fig     = fig
        self._groups  = {
            'orig': {'artists': artists_orig, 'visible': True},
            'exp':  {'artists': artists_exp,  'visible': True},
        }

        self._btn_orig = Button(btn_ax_orig, 'ORIG ●',
                                color=BG_CARD, hovercolor='#21262d')
        self._btn_exp  = Button(btn_ax_exp,  'EXP  ●',
                                color=BG_CARD, hovercolor='#21262d')

        _style_btn(self._btn_orig, C_ORIG)
        _style_btn(self._btn_exp,  C_EXP)

        # closure per evitare problemi di riferimento nel loop
        self._btn_orig.on_clicked(lambda _: self._toggle('orig'))
        self._btn_exp.on_clicked( lambda _: self._toggle('exp'))

    def _toggle(self, key: str):
        group   = self._groups[key]
        new_vis = not group['visible']
        group['visible'] = new_vis
        for a in group['artists']:
            a.set_visible(new_vis)
        # aggiorna colore pulsante: pieno = acceso, vuoto = spento
        btn = self._btn_orig if key == 'orig' else self._btn_exp
        c   = C_ORIG if key == 'orig' else C_EXP
        btn.label.set_color(c if new_vis else C_DIM)
        self._fig.canvas.draw_idle()


def _style_btn(btn, label_color: str):
    btn.label.set_fontfamily('monospace')
    btn.label.set_fontsize(7)
    btn.label.set_color(label_color)
    btn.ax.set_facecolor(BG_CARD)
    for spine in btn.ax.spines.values():
        spine.set_color(BORDER)


# ---------------------------------------------------------------------------
# Pannello diff
# ---------------------------------------------------------------------------

def _panel_diff(ax, diff_poly: Optional[Polygon]):
    _setup_ax(ax, 'DIFF  (sym)')
    if diff_poly and not diff_poly.is_empty:
        _draw_polygon(ax, diff_poly, C_DIFF, 0.45, lw=1.2)
        ax.autoscale()
    else:
        ax.text(0.5, 0.5, '✓  IDENTICI', transform=ax.transAxes,
                color=PASS_COLOR, ha='center', va='center',
                fontsize=11, fontweight='bold', fontfamily='monospace')


# ---------------------------------------------------------------------------
# Colonna metriche
# ---------------------------------------------------------------------------

def _compute_metrics(poly_orig, poly_exp, diff_poly, threshold) -> dict:
    m = {}
    m['area_orig']  = poly_orig.area   if poly_orig else None
    m['area_exp']   = poly_exp.area    if poly_exp  else None
    m['perim_orig'] = poly_orig.length if poly_orig else None
    m['perim_exp']  = poly_exp.length  if poly_exp  else None
    m['diff_area']  = (diff_poly.area
                       if (diff_poly and not diff_poly.is_empty) else 0.0)

    def pct(a, b):
        return abs(b - a) / a * 100 if (a and b and a != 0) else None

    m['delta_area_pct']  = pct(m['area_orig'],  m['area_exp'])
    m['delta_perim_pct'] = pct(m['perim_orig'], m['perim_exp'])
    m['pass'] = (m['diff_area'] <= threshold
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

    def fmt(v, d=2):  return f'{v:.{d}f}' if v is not None else '—'
    def fpct(v):      return f'{v:.3f} %'  if v is not None else '—'

    rows = [
        ('area orig',  f"{fmt(metrics['area_orig'])} mm²"),
        ('area exp',   f"{fmt(metrics['area_exp'])} mm²"),
        ('Δ area',     fpct(metrics['delta_area_pct'])),
        ('', ''),
        ('perim orig', f"{fmt(metrics['perim_orig'])} mm"),
        ('perim exp',  f"{fmt(metrics['perim_exp'])} mm"),
        ('Δ perim',    fpct(metrics['delta_perim_pct'])),
        ('', ''),
        ('diff area',  f"{fmt(metrics['diff_area'])} mm²"),
        ('soglia',     f'{threshold} mm²'),
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

    ax.axvline(0, color=BORDER, linewidth=0.8)


# ---------------------------------------------------------------------------
# Risoluzione dei child
# ---------------------------------------------------------------------------

def _resolve_children(result, output_folder, child_docs) -> list:
    """
    Restituisce [(doc_or_None, label_str), ...] allineato a result.parts.
    Priorità: child_docs in memoria > output_folder su disco > None.
    """
    if child_docs is not None:
        out = []
        for i, part in enumerate(result.parts):
            doc   = child_docs[i] if i < len(child_docs) else None
            label = getattr(part, 'label', None) or f'part_{i + 1}'
            out.append((doc, label))
        return out

    if output_folder is not None:
        folder = Path(output_folder)
        out = []
        for i, part in enumerate(result.parts):
            label = getattr(part, 'label', None) or f'part_{i + 1}'
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
                        doc   = _load_child_doc(str(path))
                        label = path.name
                    except Exception:
                        pass
                    break
            out.append((doc, label))
        return out

    return [(None, getattr(p, 'label', f'part_{i+1}'))
            for i, p in enumerate(result.parts)]


# ---------------------------------------------------------------------------
# MAIN — run()
# ---------------------------------------------------------------------------

def run(
    source_dxf:     str,
    output_folder:  Optional[str]        = None,
    result:         Optional[ForgeResult] = None,
    child_docs:     Optional[list]       = None,
    tolerance:      float                = 0.05,
    diff_threshold: float                = DEFAULT_DIFF_THRESHOLD,
    special_layers: Optional[dict]       = None,
    output_png:     Optional[str]        = None,
) -> str:
    """
    Genera la dashboard interattiva di verifica post-split.

    Layout per riga (= per pezzo):
        [Overlay  +  pulsanti ORIG/EXP]  [Diff sym]  |  Metriche

    Args:
        source_dxf:     percorso DXF sorgente
        output_folder:  cartella DXF figli (modalità disco)
        result:         ForgeResult già calcolato (opzionale)
        child_docs:     lista doc ezdxf in memoria (modalità in-memory)
        tolerance:      tolleranza heal [mm]
        diff_threshold: soglia area diff per PASS [mm²]
        special_layers: {layer: work_type} per heal
        output_png:     path PNG (default: source_dxf + _verify.png)

    Returns:
        Path del PNG salvato.
    """

    # ── STEP 1: heal sorgente ────────────────────────────────────────────
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
        print('[split_verify] Nessun pezzo trovato — uscita.')
        return ''

    # ── STEP 2: risolvi figli ────────────────────────────────────────────
    children = _resolve_children(result, output_folder, child_docs)
    n_parts  = len(result.parts)

    # ── STEP 3: layout ───────────────────────────────────────────────────
    #
    # Per ogni riga (pezzo):
    #   outer_gs[i, 0]  →  subgrid 1×2  [overlay | diff]
    #   outer_gs[i, 1]  →  metriche
    #
    # Sopra ogni riga, due Button (ORIG / EXP) per il toggle overlay.
    # I Button vivono in assi dedicati fuori dalla GridSpec principale,
    # posizionati con fig.add_axes([left, bottom, w, h]) in coordinate
    # figura — calcolati dopo aver definito outer_gs.
    #
    ROW_H     = 5.5          # altezza per riga [pollici]
    BTN_H_IN  = 0.28         # altezza pulsanti [pollici]
    FIG_H     = n_parts * ROW_H + BTN_H_IN * n_parts

    fig = plt.figure(figsize=(18, FIG_H), facecolor=BG_DARK)

    fig.suptitle(
        f'SPLIT VERIFY  ·  {Path(source_dxf).name}'
        f'   |   {n_parts} part{"i" if n_parts != 1 else "e"}'
        f'   |   soglia diff = {diff_threshold} mm²',
        color=C_TEXT, fontsize=10, fontweight='bold',
        fontfamily='monospace', y=0.999,
    )

    outer_gs = GridSpec(
        n_parts, 2,
        figure=fig,
        width_ratios=[4, 0.9],
        hspace=0.42,
        wspace=0.03,
        left=0.01, right=0.99,
        top=0.97, bottom=0.04,
    )

    # Teniamo i toggle in vita (matplotlib GC li eliminerebbe altrimenti)
    _toggles: list[OverlayToggle] = []

    for i, (part, (child_doc, child_label)) in enumerate(
            zip(result.parts, children)):

        # ── poligoni ────────────────────────────────────────────────────
        poly_orig = _polygon_from_part(part)
        poly_exp  = _read_child_polygon(child_doc) if child_doc is not None else None

        diff_poly = None
        if poly_orig is not None and poly_exp is not None:
            try:
                diff_poly = poly_orig.symmetric_difference(poly_exp)
            except Exception:
                pass

        metrics = _compute_metrics(poly_orig, poly_exp, diff_poly,
                                   diff_threshold)

        # ── subgrid geometrica ──────────────────────────────────────────
        inner_gs = GridSpecFromSubplotSpec(
            1, 2,
            subplot_spec=outer_gs[i, 0],
            wspace=0.05,
        )
        ax_overlay = fig.add_subplot(inner_gs[0])
        ax_diff    = fig.add_subplot(inner_gs[1])

        part_label = getattr(part, 'label', None) or f'part_{i + 1}'
        _setup_ax(ax_overlay, 'OVERLAY', f'{part_label}  ↔  {child_label}')

        # disegna i due layer e tieni gli artist
        artists_orig = _draw_polygon(ax_overlay, poly_orig, C_ORIG,
                                     ALPHA_FILL, lw=1.8, zorder=3)
        artists_exp  = _draw_polygon(ax_overlay, poly_exp,  C_EXP,
                                     ALPHA_FILL, lw=1.2, zorder=4)

        # legenda fissa
        handles = [
            mpatches.Patch(color=C_ORIG, label='originale', alpha=0.7),
            mpatches.Patch(color=C_EXP,  label='esportato', alpha=0.7),
        ]
        ax_overlay.legend(handles=handles, loc='upper right',
                          facecolor=BG_CARD, edgecolor=BORDER,
                          labelcolor=C_TEXT, fontsize=6, framealpha=0.9)

        _panel_diff(ax_diff, diff_poly)

        for ax in (ax_overlay, ax_diff):
            ax.autoscale()
        _sync_axes([ax_overlay, ax_diff])

        # ── metriche ────────────────────────────────────────────────────
        ax_meta = fig.add_subplot(outer_gs[i, 1])
        _panel_metrics(ax_meta, metrics, i, diff_threshold)

        # ── pulsanti toggle ──────────────────────────────────────────────
        # Recupera la posizione in coordinate figura dell'ax_overlay
        # per posizionare i bottoni subito sopra di esso.
        # (I valori precisi si ottengono dopo draw; usiamo get_position()
        #  che restituisce Bbox in coordinate figura 0-1.)
        fig.canvas.draw()                           # forza il layout
        pos    = ax_overlay.get_position()          # Bbox figura
        btn_h  = BTN_H_IN / FIG_H                  # altezza relativa
        btn_w  = 0.07
        gap    = 0.005
        b_top  = pos.y1 + gap

        ax_btn_orig = fig.add_axes([pos.x0,           b_top, btn_w, btn_h])
        ax_btn_exp  = fig.add_axes([pos.x0 + btn_w + gap, b_top, btn_w, btn_h])

        toggle = OverlayToggle(
            fig, ax_overlay,
            artists_orig, artists_exp,
            ax_btn_orig, ax_btn_exp,
        )
        _toggles.append(toggle)   # mantieni riferimento

    # ── STEP 4: salva ────────────────────────────────────────────────────
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
    )
    parser.add_argument('--folder',    default=None)
    parser.add_argument('--tolerance', type=float, default=0.05)
    parser.add_argument('--threshold', type=float, default=DEFAULT_DIFF_THRESHOLD)
    parser.add_argument('--output',    default=None)
    args = parser.parse_args()

    run(
        source_dxf=args.dxf,
        output_folder=args.folder,
        tolerance=args.tolerance,
        diff_threshold=args.threshold,
        output_png=args.output,
    )