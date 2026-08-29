"""
09_export.py — metadati fuori da forge
======================================

API forge usate:
    to_json           ForgeResult -> str  (metadati per parte, NIENTE coordinate)
    save_json          idem, scritto su file
    save_xml           stessi campi, in XML
    to_nester_input    list[dict] con le COORDINATE (per un nesting tool)

json/xml seguono lo schema in forge/rules/metadata_schema.py — una sola fonte
per i nomi dei campi. to_nester_input NON usa lo schema: il nester vuole
coordinate, non nomi.

    python 09_export.py
"""

import os
import forge

# --- CONFIG ----------------------------------------------------------------
INPUT     = r"tests/examples/Multifeature.dxf"
TOLERANCE = 0.5
LABEL_MAP = {"Filettati": "threaded_hole", "Svasati": "countersink",
             "Piega": "bending", "MARK": "engrave"}
OUTDIR = "pipeline_output"
# -------------------------------------------------------------------------

os.makedirs(OUTDIR, exist_ok=True)
base = os.path.splitext(os.path.basename(INPUT))[0]

doc = forge.load_dxf(INPUT, tolerance=TOLERANCE, label_map=LABEL_MAP)
result = forge.heal_and_detect(doc, label=base, source_file=base, features="all")

# JSON su stdout
print(forge.to_json(result, indent=2)[:600], "...\n")

# JSON + XML su file
forge.save_json(result, os.path.join(OUTDIR, f"{base}.json"))
forge.save_xml(result,  os.path.join(OUTDIR, f"{base}.xml"))
print(f"scritti {base}.json e {base}.xml in {OUTDIR}/")

# input per un nester: coordinate, non nomi
nester = forge.to_nester_input(result)
p0 = nester[0]
print(f"\nnester_input[0]: label={p0['label']}  area={p0['area']:.0f}  "
      f"outer_coords={len(p0['outer_coords'])} punti  "
      f"holes={len(p0['holes_coords'])}")
