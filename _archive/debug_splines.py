import ezdxf
from pathlib import Path
import sys

project_root = Path(".").resolve()
sys.path.insert(0, str(project_root))

import dxf_forge.workflow.healer as healer_module

input_dxf = r"c:\Users\FEDERICO\Documents\Python_Scripts\Projects\DXF\TON_23_04_2026\BAR2.00079-ZN 42D025Z00I.dxf"
doc = ezdxf.readfile(input_dxf)
msp = doc.modelspace()

# Chiama heal direttamente dal modulo, non da forge
result = healer_module.heal(msp, tolerance=0.05)



print("=== DOPO HEAL — ENTITÀ MARK ===")
entities_in_loops = result._entities_in_loops_ids

# Ricostruisci classified_entity_ids dai part
classified_entity_ids = set()
for part in result.parts:
    if part.outer.entity is not None:
        classified_entity_ids.add(id(part.outer.entity))
    for inner in part.inners:
        if inner.entity is not None:
            classified_entity_ids.add(id(inner.entity))
    for hole in part.holes:
        if hole.entity is not None:
            classified_entity_ids.add(id(hole.entity))

trash_ids = {id(t) for t in result.trash_entities}

for e in msp:
    if not e.dxf.hasattr("layer"):
        continue
    if e.dxf.layer.lower() != "mark":
        continue
    print(
        f"  {e.dxftype()} | "
        f"classified_entity={id(e) in classified_entity_ids} | "
        f"in_loops={id(e) in entities_in_loops} | "
        f"in_trash={id(e) in trash_ids}"
    )

print()
print("=== INNERS ===")
for i, part in enumerate(result.parts):
    for inner in part.inners:
        print(f"  part[{i}] inner source_layer={inner.source_layer!r} entity_type={inner.entity.dxftype() if inner.entity else None}")

print()
print("=== TRASH ===")
for e in result.trash_entities:
    layer = e.dxf.layer if e.dxf.hasattr("layer") else "?"
    print(f"  {e.dxftype()} layer={layer}")