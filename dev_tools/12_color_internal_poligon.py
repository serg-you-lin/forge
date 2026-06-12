import ezdxf
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from shapely.geometry import Polygon
from shapely.plotting import plot_polygon, plot_points
import sys
from pathlib import Path
from dxf_forge.core.geometry import pline_to_polygon
from dxf_forge.rules.layers import LAYER_OUTER
from ezdxf.math import bulge_to_arc

project_root = Path(".").resolve()
sys.path.insert(0, str(project_root))

import dxf_forge as forge
from dxf_forge.adapters.dxf.virtual import _loop_to_virtual_shape
from dxf_forge.core.graph import build_node_graph, find_closed_loops, classify_loops
from dxf_forge.core.geometry import circle_to_polygon

input_dxf = r"tests/examples/archi_bastardi_xdata_test_healed.dxf"

doc = ezdxf.readfile(input_dxf)
msp = doc.modelspace()

# # Costruisci il polygon dell'outer
# node_decimals = 1
# graph = build_node_graph(msp, decimals=node_decimals)
# loops = find_closed_loops(graph)
# outer_loops, _ = classify_loops(loops)

# vs = _loop_to_virtual_shape(outer_loops[0], '', 0)

# outer_poly = vs.polygon

# Prendi direttamente l'outer dal layer
outer_entity = next(
    (e for e in msp.query('LWPOLYLINE') if e.dxf.layer == LAYER_OUTER),
    None
)

if outer_entity is None:
    print("Nessun OuterContour trovato")
    exit(1)

# DEBUG — metti questo prima di outer_poly = pline_to_polygon(outer_entity)
print("\n--- DEBUG BULGE ---")
points = list(outer_entity.get_points('xyb'))
n = len(points)
for i in range(n):
    x1, y1, bulge = points[i]
    x2, y2, _     = points[(i + 1) % n]
    if abs(bulge) > 1e-6:
        center, start_angle, end_angle, radius = bulge_to_arc(
            (x1, y1), (x2, y2), bulge
        )
        print(f"  seg {i}: ({x1:.1f},{y1:.1f}) → ({x2:.1f},{y2:.1f})")
        print(f"    bulge={bulge:.4f}")
        print(f"    center=({center.x:.1f},{center.y:.1f})")
        print(f"    radius={radius:.1f}")
        print(f"    start={start_angle:.1f}°  end={end_angle:.1f}°")

outer_poly = pline_to_polygon(outer_entity)

# Plot
fig, ax = plt.subplots(figsize=(12, 8))

# Outer — fill per vedere esattamente i bordi
x, y = outer_poly.exterior.xy
ax.fill(x, y, alpha=0.3, color='blue', label='outer polygon')
ax.plot(x, y, 'b-', linewidth=1)

x, y = outer_poly.exterior.xy
for i, (px, py) in enumerate(zip(x, y)):
    ax.annotate(str(i), (px, py), fontsize=8, color='black',
                ha='center', va='bottom')
    
# Cerchi
for circle in msp.query('CIRCLE'):
    cx, cy = circle.dxf.center.x, circle.dxf.center.y
    r = circle.dxf.radius
    poly = circle_to_polygon(circle)
    inside = outer_poly.contains(poly)
    color = 'green' if inside else 'red'
    patch = plt.Circle((cx, cy), r, color=color, fill=False, linewidth=2)
    ax.add_patch(patch)
    ax.plot(cx, cy, 'x', color=color)
    ax.annotate(f"({cx:.0f},{cy:.0f})\n{'IN' if inside else 'OUT'}", 
                (cx, cy), fontsize=7, ha='center')

ax.set_aspect('equal')
ax.legend()
plt.title("Outer polygon + circles — verde=inside, rosso=outside")
plt.tight_layout()
plt.savefig("debug_polygon.png", dpi=150)
plt.show()
print("Salvato debug_polygon.png")