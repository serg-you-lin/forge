"""
10_metadata_xdata.py — metadati DENTRO il DXF (XDATA) + schema custom
====================================================================

API topo usate:
    write_metadata_to_dxf    scrive i metadati come XDATA "TOPO" sull'entità outer
    read_metadata_from_dxf   li rilegge da un Drawing ezdxf ({} se non trova niente)
    set_schema               sostituisce lo schema metadati attivo a runtime

Utile quando il DXF deve portarsi dietro i propri dati (materiale, spessore,
conteggi) senza un JSON a fianco.

    python 10_metadata_xdata.py
"""

import _paths  # noqa: F401  — chdir alla radice del repo

import os
import ezdxf
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

# set_schema: rimappa i nomi dei campi in output sul tuo CAM/gestionale.
# struttura: {chiave_interna: (nome_output, default, sorgente)}
# sorgente ∈ {"cluster", "custom", "calculated"}
topo.set_schema({
    "label":        ("codice",        "",       "cluster"),
    "material":     ("materiale",     "S275JR", "custom"),
    "thickness":    ("spessore_mm",   0.0,      "custom"),
    "area":         ("area_mm2",      None,     "calculated"),
    "holes_count":  ("n_fori",        None,     "calculated"),
    "bbox":         ("ingombro",      None,     "calculated"),
})

doc = topo.load_dxf(INPUT, tolerance=TOLERANCE, role_rules=topo.name_rules(NAME_ROLES))
result = topo.heal(doc, label=base)
topo.inject(result, data_injector=lambda cluster, txt: {"material": "AISI304", "thickness": 3.0})

out = topo.to_dxf(result, doc)
for cluster in result.clusters:
    topo.write_metadata_to_dxf(out, cluster)

path = os.path.join(OUTDIR, f"{base}_xdata.dxf")
out.saveas(path)
print(f"scritto: {path}")

# rilettura da file
reloaded = ezdxf.readfile(path)
meta = topo.read_metadata_from_dxf(reloaded)
print("XDATA riletto:")
for k, v in meta.items():
    print(f"   {k}: {v}")

# NB: set_schema() sostituisce lo schema globale per tutto il processo. Per
# ripristinare quello di default:
#     from topo.rules.metadata_schema import METADATA_FIELDS
#     topo.set_schema(METADATA_FIELDS)
