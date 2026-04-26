"""
09_plot_graph.py
-------------
Visualizza le entità DXF e il grafo topologico degli endpoint.

Per ogni endpoint mostra il grado (numero di connessioni):
  - grado 1 = endpoint libero (non connesso ad altri)
  - grado 2 = endpoint connesso correttamente a un'altra entità
  - grado 3+ = nodo ambiguo (tre o più entità si incontrano)

Uso:
    python plot_graph.py

Modifica INPUT_DXF con il percorso del tuo file.
"""

import os
import math
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from collections import defaultdict
import ezdxf
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from dxf_forge.geometry import arc_endpoints
from dxf_forge.graph import round_point, spline_endpoints

# ← CAMBIA QUI
INPUT_DXF = r"tests/examples/flangia_scantonata.DXF"
DECIMALS  = 1   # stesso valore usato dall'healer
TOLERANCE = 5   # tolleranza heal — mostrata nel titolo


# ---------------------------------------------------------------------------
# Costruisce il grafo (copia locale per debug, senza esclusioni)
# ---------------------------------------------------------------------------

def build_graph(msp, decimals):
    graph = defaultdict(list)

    for entity in msp.query('LINE ARC'):
        if entity.dxftype() == 'LINE':
            s = round_point((entity.dxf.start.x, entity.dxf.start.y), decimals)
            e = round_point((entity.dxf.end.x,   entity.dxf.end.y),   decimals)
        else:
            s_pt, e_pt = arc_endpoints(entity)
            s = round_point(s_pt, decimals)
            e = round_point(e_pt, decimals)
        graph[s].append((entity, e))
        graph[e].append((entity, s))

    for entity in msp.query('SPLINE'):
        s_pt, e_pt = spline_endpoints(entity)
        if s_pt and e_pt:
            s = round_point(s_pt, decimals)
            e = round_point(e_pt, decimals)
            graph[s].append((entity, e))
            graph[e].append((entity, s))

    return graph


# ---------------------------------------------------------------------------
# Disegna un ARC come curva
# ---------------------------------------------------------------------------

def _arc_points(entity, n=60):
    cx, cy = entity.dxf.center.x, entity.dxf.center.y
    r = entity.dxf.radius
    a0 = math.radians(entity.dxf.start_angle)
    a1 = math.radians(entity.dxf.end_angle)
    if a1 < a0:
        a1 += 2 * math.pi
    angles = np.linspace(a0, a1, n)
    xs = cx + r * np.cos(angles)
    ys = cy + r * np.sin(angles)
    return xs, ys


def zoom_factory(ax, base_scale=1.5):
    def zoom(event):
        if event.inaxes != ax:
            return

        xdata = event.xdata
        ydata = event.ydata

        cur_xlim = ax.get_xlim()
        cur_ylim = ax.get_ylim()

        x_range = (cur_xlim[1] - cur_xlim[0])
        y_range = (cur_ylim[1] - cur_ylim[0])

        if event.button == 'up':  # zoom in
            scale_factor = 1 / base_scale
        elif event.button == 'down':  # zoom out
            scale_factor = base_scale
        else:
            scale_factor = 1

        new_width = x_range * scale_factor
        new_height = y_range * scale_factor

        relx = (cur_xlim[1] - xdata) / x_range
        rely = (cur_ylim[1] - ydata) / y_range

        ax.set_xlim([xdata - new_width * (1-relx), xdata + new_width * relx])
        ax.set_ylim([ydata - new_height * (1-rely), ydata + new_height * rely])
        ax.figure.canvas.draw()

    fig = ax.get_figure()
    fig.canvas.mpl_connect('scroll_event', zoom)

    return zoom

# ---------------------------------------------------------------------------
# Plot principale
# ---------------------------------------------------------------------------

def plot(input_dxf, decimals, tolerance):
    doc = ezdxf.readfile(input_dxf)
    msp = doc.modelspace()
    graph = build_graph(msp, decimals)

    fig, ax = plt.subplots(figsize=(14, 10))
    zoom_factory(ax)
    #plt.get_current_fig_manager().toolbar.pan()
    ax.set_aspect('equal')
    ax.set_facecolor('#1a1a2e')
    fig.patch.set_facecolor('#1a1a2e')

    # --- Disegna entità ---

    for entity in msp.query('LINE'):
        x = [entity.dxf.start.x, entity.dxf.end.x]
        y = [entity.dxf.start.y, entity.dxf.end.y]
        ax.plot(x, y, color='#4fc3f7', linewidth=1.5, zorder=2)

    for entity in msp.query('ARC'):
        xs, ys = _arc_points(entity)
        ax.plot(xs, ys, color='#81c784', linewidth=1.5, zorder=2)

    for entity in msp.query('LWPOLYLINE'):
        pts = list(entity.get_points('xy'))
        if entity.closed:
            pts.append(pts[0])
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        ax.plot(xs, ys, color='#ce93d8', linewidth=1.2,
                linestyle='--', zorder=2)

    for entity in msp.query('CIRCLE'):
        cx, cy = entity.dxf.center.x, entity.dxf.center.y
        r = entity.dxf.radius
        circle = plt.Circle((cx, cy), r, fill=False,
                             color='#ffb74d', linewidth=1.2, zorder=2)
        ax.add_patch(circle)

    # --- Disegna nodi con grado ---

    color_by_degree = {
        1: '#ff5252',   # rosso — endpoint libero
        2: '#69f0ae',   # verde — connesso correttamente
    }
    default_color = '#ffd740'  # giallo — ambiguo (grado 3+)

    offset = 1.5  # offset testo in mm

    for node, connections in graph.items():
        degree = len(connections)
        color = color_by_degree.get(degree, default_color)

        ax.scatter(node[0], node[1], s=60, color=color,
                   zorder=5, edgecolors='white', linewidths=0.5)

        label = f"grado {degree}"
        ax.annotate(
            label,
            xy=(node[0], node[1]),
            xytext=(node[0] + offset, node[1] + offset),
            fontsize=6,
            color=color,
            zorder=6,
            bbox=dict(boxstyle='round,pad=0.2', facecolor='#1a1a2e',
                      edgecolor='none', alpha=0.7),
        )

    # --- Legenda ---

    legend_elements = [
        mpatches.Patch(color='#4fc3f7', label='LINE'),
        mpatches.Patch(color='#81c784', label='ARC'),
        mpatches.Patch(color='#ce93d8', label='LWPOLYLINE'),
        mpatches.Patch(color='#ffb74d', label='CIRCLE'),
        plt.Line2D([0], [0], marker='o', color='w',
                   markerfacecolor='#ff5252', markersize=8,
                   label='grado 1 — endpoint libero'),
        plt.Line2D([0], [0], marker='o', color='w',
                   markerfacecolor='#69f0ae', markersize=8,
                   label='grado 2 — connesso'),
        plt.Line2D([0], [0], marker='o', color='w',
                   markerfacecolor='#ffd740', markersize=8,
                   label='grado 3+ — ambiguo'),
    ]
    ax.legend(handles=legend_elements, loc='upper right',
              facecolor='#16213e', edgecolor='#4fc3f7',
              labelcolor='white', fontsize=8)

    title = (f"{os.path.basename(input_dxf)}\n"
             f"node_decimals={decimals}  tolerance={tolerance}mm")
    ax.set_title(title, color='white', fontsize=10, pad=12)
    ax.tick_params(colors='#888')
    ax.spines[:].set_color('#333')

    plt.tight_layout()
    out = os.path.splitext(input_dxf)[0] + "_graph.png"
    plt.savefig(out, dpi=150, bbox_inches='tight',
                facecolor=fig.get_facecolor())
    print(f"Salvato: {out}")
    plt.show()


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    plot(INPUT_DXF, DECIMALS, TOLERANCE)