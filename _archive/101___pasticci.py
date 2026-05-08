"""
explore_models.py
-----------------
Esplora le classi di models.py:
- crea oggetti di esempio
- stampa campi
- stampa metodi e proprietà
- stampa output to_dict
"""

import inspect
from shapely.geometry import Polygon
from pathlib import Path
import sys

project_root = Path(__file__).resolve().parent
print(f"project root: {project_root}")
sys.path.insert(0, str(project_root))


from dxf_forge.models import ForgeContour, ForgePart, ForgeResult
from dxf_forge.core.virtual import VirtualShape

def print_attributes(obj):
    """Stampa gli attributi di un oggetto."""
    print("\nATTRIBUTES:")
    for k, v in vars(obj).items():
        print(f"{k:15} -> {v}")

def print_methods(obj):
    """Stampa i metodi di un oggetto."""
    print("\nMETHODS:")
    for name, member in inspect.getmembers(obj, predicate=inspect.ismethod):
        if not name.startswith("__"):
            print(name)

def print_properties(obj):
    """Stampa le proprietà di un oggetto."""
    print("\nPROPERTIES:")
    for name, member in inspect.getmembers(type(obj)):
        if isinstance(member, property):
            print(name)

def main():

    # -------------------------
    # 1 contorno esterno
    # -------------------------

    square = Polygon([
        (0, 0),
        (100, 0),
        (100, 100),
        (0, 100),
        (0, 0)
    ])

    outer = ForgeContour(
        polygon=square,
        layer="CUT"
    )

    # -------------------------
    # 1 foro
    # -------------------------

    hole_poly = Polygon([
        (40, 40),
        (60, 40),
        (60, 60),
        (40, 60),
        (40, 40)
    ])

    hole = ForgeContour(
        polygon=hole_poly,
        is_inner=True,
        layer="HOLES"
    )

    # -------------------------
    # ForgePart
    # -------------------------

    part = ForgePart(
        outer=outer,
        inners=[hole],
        label="TEST_PART",
        source_file="test.dxf"
    )

    # -------------------------
    # ForgeResult
    # -------------------------

    result = ForgeResult(
        parts=[part],
        source_file="test.dxf"
    )

    # -------------------------
    # INSPECTION
    # -------------------------

    # print_attributes(outer)
    # print_methods(outer)
    # print_properties(outer)

    # print_attributes(part)
    # print_methods(part)
    # print_properties(part)

    # print_attributes(result)
    # print_methods(result)
    # print_properties(result)
    #print(inspect.getmembers(VirtualShape))
    #help(VirtualShape)

    print(dir(VirtualShape))

    methods = inspect.getmembers(VirtualShape, predicate=inspect.isfunction)

    for name, _ in methods:
        print(name)
    # -------------------------
    # OUTPUT LOGICO
    # -------------------------

    # print("\n\n--- PART DATA ---")
    # print("Area netta:", part.area)
    # print("BBox:", part.bbox)
    # print("Polygon with holes:", part.polygon_with_holes)

    # print("\n--- PART JSON ---")
    # print(part.to_dict())

    # print("\n--- RESULT JSON ---")
    # print(result.to_dict())


if __name__ == "__main__":
    main()