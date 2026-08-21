import sys
from pathlib import Path
import matplotlib.pyplot as plt
import ezdxf

# Impostazione root del progetto
project_root = Path(".").resolve()
sys.path.insert(0, str(project_root))

from forge.adapters.dxf.adapter import DxfAdapter
from forge.core.topology.graph import build_node_graph
from forge.core.topology.loop_finder import find_closed_loops, classify_loops
from forge.core.geometry import edges_to_polygon, circle_to_polygon
from forge.adapters.dxf.layers import LAYER_OUTER

# 1. Caricamento del documento DXF
input_dxf = r"tests/examples/archi_bastardi_xdata_test_healed.dxf"
doc = ezdxf.readfile(input_dxf)
msp = doc.modelspace()

# 2. Inizializzazione dell'Adapter DXF
# L'adapter gestisce la conversione di LINE, ARC, SPLINE, CIRCLE e POLYLINE in istanze di Edge
adapter = DxfAdapter(
    msp=msp,
    tolerance=0.05,
    # Se la tua nuova gestione layer si basa su label_map o ignore_layers, puoi passarli qui:
    # label_map={"outer": "outer"}, 
)

# 3. Estrazione degli Edge
all_edges = adapter.to_edges()

# Filtriamo gli edge appartenenti al layer OUTER (gestito secondo le tue nuove definizioni)
outer_edges = [edge for edge in all_edges if edge.layer == LAYER_OUTER]

if not outer_edges:
    print(f"Nessun edge trovato per il layer '{LAYER_OUTER}'")
    sys.exit(1)

# 4. Costruzione del Grafo Topologico e Pruning
raw_graph = build_node_graph(outer_edges)
clean_graph = raw_graph.pruned()  # Elimina rami morti e linee spuri (degree <= 1)

# 5. Estrazione e Classificazione dei Loop
loops = find_closed_loops(clean_graph)
outer_loops, _ = classify_loops(loops)

if not outer_loops:
    print("Nessun loop esterno valido trovato.")
    sys.exit(1)

# Conversione del loop in Polygon Shapely tramite la geometria degli Edge
outer_poly = edges_to_polygon(outer_loops[0])

# 6. Visualizzazione e Rendering (Matplotlib)
fig, ax = plt.subplots(figsize=(12, 8))

# Disegno dell'Outer Polygon
x, y = outer_poly.exterior.xy
ax.fill(x, y, alpha=0.3, color='blue', label='Outer Polygon (DxfAdapter)')
ax.plot(x, y, 'b-', linewidth=1.5)

# Annotazione dei vertici del poligono
for i, (px, py) in enumerate(zip(x, y)):
    ax.annotate(str(i), (px, py), fontsize=8, color='black', ha='center', va='bottom')

# Controllo e disegno dei Cerchi dal Modello DXF
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
plt.title("Visualizzazione Debug — DxfAdapter + Graph Topology")
plt.tight_layout()

# Salvataggio e Output
output_img = "debug_polygon_adapter.png"
plt.savefig(output_img, dpi=150)
plt.show()

print(f"Salvato con successo in {output_img}")