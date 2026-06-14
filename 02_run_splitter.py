"""
run_splitter.py
---------------
Testa lo splitter su un file DXF reale con più polilinee.
Produce un file separato per ogni pezzo trovato in output_dir/.

Lancia:
    python run_splitter.py

Modifica input_dxf e output_dir con i tuoi percorsi.
"""

import ezdxf
import dxf_forge as forge
import os

# ← CAMBIA QUI con il tuo file
input_dxf  = r"c:\Users\FEDERICO\Documents\Python_Scripts\Projects\DXF\ProTest\Ostici\fa_che_non_mi_incazzi.dxf"
#input_dir = os.path.abspath(input_dxf)
output_dir = os.path.join(os.path.dirname(input_dxf), os.path.splitext(os.path.basename(input_dxf))[0])

print(f"Apertura: {input_dxf}")
doc = ezdxf.readfile(input_dxf)
msp = doc.modelspace()

from collections import Counter
print("--- MSP GREZZO ---")
types = Counter(e.dxftype() for e in msp)
for t, count in sorted(types.items()):
    print(f"  {t}: {count}")

# Guarda dentro gli INSERT
for e in msp:
    if e.dxftype() == 'INSERT':
        try:
            block = doc.blocks.get(e.dxf.name)
            inner = Counter(sub.dxftype() for sub in block)
            print(f"  INSERT '{e.dxf.name}' contiene: {dict(inner)}")
        except Exception as ex:
            print(f"  INSERT error: {ex}")

# Valida prima
print("\n--- VALIDAZIONE ---")
check = forge.validate_msp(msp)
if check.warnings:
    for w in check.warnings:
        print(f"  WARN: {w}")
if check.errors:
    for e in check.errors:
        print(f"  ERROR: {e}")
    print("Errori bloccanti trovati, interrompo.")
    exit(1)
print("  OK")

# Split — salva ogni pezzo in un file separato
print(f"\n--- SPLIT → {output_dir} ---")
import os
label = os.path.splitext(os.path.basename(input_dxf))[0]
label = label.replace(" Sviluppo", "")

result = forge.split_to_files(
    msp,
    output_folder=output_dir,
    explode_inserts=True,
    label=label,
    source_file=input_dxf,
    include_annotations=True,
    # namer=lambda i, part: f"{label}_PART{i}",
)
# DEBUG — cosa c'è nel msp dopo split_to_files?
print("\n--- DEBUG MSP DOPO SPLIT ---")
from collections import Counter
types = Counter(e.dxftype() for e in msp)
for t, count in sorted(types.items()):
    print(f"  {t}: {count}")

for pline in msp.query('LWPOLYLINE'):
    pts = list(pline.get_points())
    print(f"  LWPOLYLINE: {len(pts)} vertici, layer={pline.dxf.layer}")
print(f"\nRisultato:")
print(f"  Pezzi trovati : {result.part_count}")
print(f"  Valido        : {result.is_valid}")
if result.warnings:
    for w in result.warnings:
        print(f"  WARN: {w}")

for i, part in enumerate(result.parts):
    print(f"\n  Pezzo {i+1}: {part.label}")
    print(f"    Area netta : {part.area:.1f}")
    print(f"    Area outer raw : {part.outer.polygon.area:.4f}")
    for j, inner in enumerate(part.inners):
        print(f"    Inner {j}: area={inner.polygon.area:.4f}")
    for j, hole in enumerate(part.holes):
        print(f"    Hole  {j}: area={hole.entity and hole.polygon.area:.4f}")
    print(f"    Fori       : {len(part.inners)}")
    print(f"    Bbox       : {part.bbox}")

# Esporta metadati JSON
forge.save_json(result, "split_metadata.json")
print(f"\nMetadati salvati: split_metadata.json")
print(f"File DXF salvati in: {output_dir}/")
