import sys
from pathlib import Path

import ezdxf
import matplotlib.pyplot as plt

# ---------------------------------------------------------------------------
# Forge
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from forge.adapters.dxf.adapter import DxfAdapter
from forge.core.topology.graph import build_node_graph
from forge.core.topology.loop_finder import LoopFinder
from forge.core.healing.hierarchy import (
    HierarchyBuilder,
    loop_to_closed_shape,
)


# ===========================================================================
# CONFIGURAZIONE
# ===========================================================================

# INCOLLA QUI IL FILE DXF
InputPath = r"C:\Users\FEDERICO\Documents\Python_Scripts\Projects\GitHub\dxf-forge\tests\examples"
FileName = "cerchi_ciambella.dxf"

INPUT_DXF = Path(InputPath) / FileName

TOLERANCE = 0.05


# ===========================================================================
# LOAD DXF
# ===========================================================================

doc = ezdxf.readfile(INPUT_DXF)
msp = doc.modelspace()

print(f"DXF: {INPUT_DXF}")


# ===========================================================================
# ADAPTER
# ===========================================================================

adapter = DxfAdapter(
    msp=msp,
    tolerance=TOLERANCE,
)

all_edges = adapter.to_edges()

if not all_edges:
    print("Nessun Edge prodotto dal DxfAdapter.")
    sys.exit(1)

print(f"Edge prodotti: {len(all_edges)}")


# ===========================================================================
# GRAPH
# ===========================================================================

graph = build_node_graph(all_edges)


# ===========================================================================
# LOOP FINDER
# ===========================================================================

finder = LoopFinder()

loops = finder.find(graph)

if not loops:
    print("Nessun loop trovato.")
    sys.exit(1)

print(f"Loop trovati: {len(loops)}")


# ===========================================================================
# LOOP → CLOSED SHAPE
# ===========================================================================

closed_shapes = []

for loop in loops:
    shape = loop_to_closed_shape(loop)

    if shape is not None:
        closed_shapes.append(shape)

print(f"ClosedShape valide: {len(closed_shapes)}")

if not closed_shapes:
    print("Nessuna ClosedShape valida.")
    sys.exit(1)


# ===========================================================================
# ENTITY IDS
# ===========================================================================

entities_in_loops = {
    id(edge.source_ref)
    for loop in loops
    for edge, _ in loop
    if edge.source_ref is not None
}


# ===========================================================================
# HIERARCHY
# ===========================================================================

hierarchy = HierarchyBuilder(
    label="DEBUG",
    source_file=str(INPUT_DXF),
    label_map={},
    entities_in_loops=entities_in_loops,
)

parts, trash = hierarchy.build(closed_shapes)

print(f"ForgePart: {len(parts)}")

if not parts:
    print("Nessuna ForgePart.")
    sys.exit(1)


# ===========================================================================
# DEBUG INFO
# ===========================================================================

for i, part in enumerate(parts):

    print(
        f"\nPART {i}"
        f"\n  OUTER : area={part.outer.polygon.area:.3f}"
        f"\n  INNER : {len(part.inners)}"
        f"\n  HOLE  : {len(part.holes)}"
    )

    for j, inner in enumerate(part.inners):
        print(
            f"    INNER {j}: "
            f"area={inner.polygon.area:.3f}"
        )

    for j, hole in enumerate(part.holes):
        print(
            f"    HOLE {j}: "
            f"area={hole.polygon.area:.3f}"
        )


# ===========================================================================
# PLOT
# ===========================================================================

fig, ax = plt.subplots(figsize=(14, 10))


def draw_polygon(
    polygon,
    face_color,
    edge_color,
    alpha,
    label=None,
    linewidth=2.0,
):
    if polygon.is_empty:
        return

    x, y = polygon.exterior.xy

    ax.fill(
        x,
        y,
        color=face_color,
        alpha=alpha,
        label=label,
    )

    ax.plot(
        x,
        y,
        color=edge_color,
        linewidth=linewidth,
    )


# ---------------------------------------------------------------------------
# Disegna PART
# ---------------------------------------------------------------------------

for part_index, part in enumerate(parts):

    # OUTER
    draw_polygon(
        part.outer.polygon,
        face_color="blue",
        edge_color="blue",
        alpha=0.20,
        label="OUTER" if part_index == 0 else None,
        linewidth=2.5,
    )

    # INNER
    for inner_index, inner in enumerate(part.inners):

        draw_polygon(
            inner.polygon,
            face_color="orange",
            edge_color="orange",
            alpha=0.45,
            label="INNER" if (
                part_index == 0 and inner_index == 0
            ) else None,
            linewidth=2.0,
        )

        centroid = inner.polygon.centroid

        ax.annotate(
            f"INNER {inner_index}",
            (centroid.x, centroid.y),
            fontsize=9,
            ha="center",
            va="center",
        )

    # HOLE
    for hole_index, hole in enumerate(part.holes):

        draw_polygon(
            hole.polygon,
            face_color="red",
            edge_color="red",
            alpha=0.45,
            label="HOLE" if (
                part_index == 0 and hole_index == 0
            ) else None,
            linewidth=2.0,
        )

        centroid = hole.polygon.centroid

        ax.annotate(
            f"HOLE {hole_index}",
            (centroid.x, centroid.y),
            fontsize=8,
            ha="center",
            va="center",
        )


# ===========================================================================
# VIEW
# ===========================================================================

ax.set_aspect("equal")
ax.legend()
ax.set_title("Forge — Polygon Hierarchy")

plt.tight_layout()

OUTPUT = PROJECT_ROOT / "debug_polygon_hierarchy.png"

plt.savefig(
    OUTPUT,
    dpi=150,
)

print(f"\nSalvato: {OUTPUT}")

plt.show()