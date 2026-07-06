"""
run_splitter.py
---------------
Testa lo splitter su un file DXF reale con più polilinee.
Produce un file separato per ogni pezzo trovato in output_dir/.

Lancia:
    python run_splitter.py

Modifica input_dxf con il tuo percorso.
"""

import forge
import os
from collections import Counter

# ---------------------------------------------------------------------------
# CAMBIA QUI
# ---------------------------------------------------------------------------

input_dxf = r"c:\Users\FEDERICO\Documents\Python_Scripts\Projects\DXF\ProTest\intricato_doppio.dxf"

# ---------------------------------------------------------------------------

output_dir = os.path.join(
    os.path.dirname(input_dxf),
    os.path.splitext(os.path.basename(input_dxf))[0],
)

label = os.path.splitext(os.path.basename(input_dxf))[0]
label = label.replace(" Sviluppo", "")

# ---------------------------------------------------------------------------
# Apertura
# ---------------------------------------------------------------------------

print(f"Apertura: {input_dxf}")
doc, msp = forge.load_dxf(input_dxf, upgrade=True, verbose=True)

print("--- MSP GREZZO ---")
types = Counter(e.dxftype() for e in msp)
for t, count in sorted(types.items()):
    print(f"  {t}: {count}")

for e in msp:
    if e.dxftype() == 'INSERT':
        try:
            block = doc.blocks.get(e.dxf.name)
            inner = Counter(sub.dxftype() for sub in block)
            print(f"  INSERT '{e.dxf.name}' contiene: {dict(inner)}")
        except Exception as ex:
            print(f"  INSERT error: {ex}")

# ---------------------------------------------------------------------------
# Validazione
# ---------------------------------------------------------------------------

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

# ---------------------------------------------------------------------------
# Split
# ---------------------------------------------------------------------------

print(f"\n--- SPLIT → {output_dir} ---")
result = forge.split_to_files(
    msp,
    output_folder=output_dir,
    explode_inserts=True,
    label=label,
    source_file=input_dxf,
    include_annotations=True,
    # namer=lambda i, part: f"{label}_PART{i}",
)

# ---------------------------------------------------------------------------
# Debug MSP dopo split
# ---------------------------------------------------------------------------

print("\n--- DEBUG MSP DOPO SPLIT ---")
types = Counter(e.dxftype() for e in msp)
for t, count in sorted(types.items()):
    print(f"  {t}: {count}")

for pline in msp.query('LWPOLYLINE'):
    pts = list(pline.get_points())
    print(f"  LWPOLYLINE: {len(pts)} vertici, layer={pline.dxf.layer}")

# ---------------------------------------------------------------------------
# Risultato
# ---------------------------------------------------------------------------

print(f"\nRisultato:")
print(f"  Pezzi trovati : {result.part_count}")
print(f"  Valido        : {result.is_valid}")
if result.warnings:
    for w in result.warnings:
        print(f"  WARN: {w}")

for i, part in enumerate(result.parts):
    print(f"\n  Pezzo {i+1}: {part.label}")
    print(f"    Area netta     : {part.area:.1f}")
    print(f"    Area outer raw : {part.outer.polygon.area:.4f}")
    for j, inner in enumerate(part.inners):
        print(f"    Inner {j}: area={inner.polygon.area:.4f}")
    for j, hole in enumerate(part.holes):
        print(f"    Hole  {j}: area={hole.polygon.area:.4f}")
    print(f"    Fori           : {len(part.inners)}")
    print(f"    Bbox           : {part.bbox}")

# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

forge.save_json(result, "split_metadata.json")
print(f"\nMetadati salvati: split_metadata.json")
print(f"File DXF salvati in: {output_dir}/")