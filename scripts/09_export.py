"""
09_export.py — metadati fuori da topo
======================================

API topo usate:
    to_json           Result -> str  (metadati per parte, NIENTE coordinate)
    save_json          idem, scritto su file
    save_xml           stessi campi, in XML
    to_nester_input    list[dict] con le COORDINATE (per un nesting tool)

json/xml seguono lo schema in topo/rules/metadata_schema.py — una sola fonte
per i nomi dei campi. to_nester_input NON usa lo schema: il nester vuole
coordinate, non nomi.

    python 09_export.py
"""

import _paths  # noqa: F401  — chdir alla radice del repo

import os
import topo

# --- CONFIG ----------------------------------------------------------------
INPUT     = r"tests/data/Multifeature.dxf"
TOLERANCE = 0.5
NAME_ROLES = {"Filettati": "threaded_hole", "Svasati": "countersink",
             "Piega": "bending", "MARK": "engrave"}
OUTDIR = "pipeline_output"
# -------------------------------------------------------------------------

os.makedirs(OUTDIR, exist_ok=True)
base = os.path.splitext(os.path.basename(INPUT))[0]

doc = topo.load_dxf(INPUT, tolerance=TOLERANCE, role_rules=topo.name_rules(NAME_ROLES))
result = topo.heal(doc, label=base, source_file=base)

# JSON su stdout
print(topo.to_json(result, indent=2)[:600], "...\n")

# JSON + XML su file
topo.save_json(result, os.path.join(OUTDIR, f"{base}.json"))
topo.save_xml(result,  os.path.join(OUTDIR, f"{base}.xml"))
print(f"scritti {base}.json e {base}.xml in {OUTDIR}/")

# input per un nester: coordinate, non nomi
nester = topo.to_nester_input(result)
p0 = nester[0]
print(f"\nnester_input[0]: label={p0['label']}  area={p0['area']:.0f}  "
      f"outer_coords={len(p0['outer_coords'])} punti  "
      f"holes={len(p0['holes_coords'])}")
