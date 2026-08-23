"""
debug_lineette.py
-----------------
Debug per capire perché le lineette bastarde finiscono su Trash invece di Bending.
"""

import ezdxf
import math
from collections import Counter

import forge

FILE = r"tests/examples/6200012964_lineette_bastarde.dxf"


def main():
    doc = ezdxf.readfile(FILE)
    msp = doc.modelspace()

    # ── ENTITÀ PER LAYER ──
    print(f"\n--- ENTITÀ PER LAYER ---")
    layer_count = Counter()
    for e in msp:
        layer_count[e.dxf.layer] += 1
        print(f"  {e.dxftype():10s} layer={e.dxf.layer:10s} id={id(e)}")
    print(f"  TOTALE: {dict(layer_count)}")

    # ── HEALING ──
    print(f"\n--- HEALING ---")
    result = forge.heal(msp, tolerance=0.2)

    print(f"  parts: {len(result.parts)}")
    for i, p in enumerate(result.parts):
        print(f"  Part {i}: area={p.outer.polygon.area:.2f}")
        print(f"    entity_ids ({len(p.entity_ids)}):")
        for eid in p.entity_ids:
            for e in msp:
                if id(e) == eid:
                    print(f"      {e.dxftype()} layer={e.dxf.layer}")
                    break

    # ── BENDING E TRASH DOPO HEALING ──
    print(f"\n--- BENDING E TRASH DOPO HEALING ---")
    bending = [e for e in msp if e.dxf.layer == 'Bending']
    trash = [e for e in msp if e.dxf.layer == 'Trash']
    print(f"  Bending: {len(bending)}")
    for e in bending:
        print(f"    {e.dxftype()} id={id(e)}")
    print(f"  Trash: {len(trash)}")
    for e in trash:
        print(f"    {e.dxftype()} id={id(e)}")

    # ── VIRTUAL SHAPES ──
    print(f"\n--- VIRTUAL SHAPES ---")
    for vs in result._virtual_shapes:
        print(f"  layer={vs.layer} area={vs.polygon.area:.2f}")


if __name__ == "__main__":
    main()