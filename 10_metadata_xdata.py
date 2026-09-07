"""
10_metadata_xdata.py — metadati DENTRO il DXF (XDATA) + schema custom
====================================================================

API forge usate:
    write_metadata_to_dxf    scrive i metadati come XDATA "FORGE" sull'entità outer
    read_metadata_from_dxf   li rilegge da un Drawing ezdxf ({} se non trova niente)
    set_schema               sostituisce lo schema metadati attivo a runtime

Utile quando il DXF deve portarsi dietro i propri dati (materiale, spessore,
conteggi) senza un JSON a fianco.

    python 10_metadata_xdata.py
"""

import ezdxf
import forge

from _paths import EXAMPLES, OUTPUT

# --- CONFIG ----------------------------------------------------------------
INPUT     = EXAMPLES / "Multifeature.dxf"
TOLERANCE = 0.5
LABEL_MAP = {"Filettati": "threaded_hole", "Svasati": "countersink",
             "Piega": "bending", "MARK": "engrave"}
OUTDIR = OUTPUT
# -------------------------------------------------------------------------

OUTDIR.mkdir(parents=True, exist_ok=True)
base = INPUT.stem

# set_schema: rimappa i nomi dei campi in output sul tuo CAM/gestionale.
# struttura: {chiave_interna: (nome_output, default, sorgente)}
# sorgente ∈ {"cluster", "custom", "calculated"}
forge.set_schema({
    "label":        ("codice",        "",       "cluster"),
    "material":     ("materiale",     "S275JR", "custom"),
    "thickness":    ("spessore_mm",   0.0,      "custom"),
    "area":         ("area_mm2",      None,     "calculated"),
    "holes_count":  ("n_fori",        None,     "calculated"),
    "bbox":         ("ingombro",      None,     "calculated"),
})

doc = forge.load_dxf(INPUT, tolerance=TOLERANCE, label_map=LABEL_MAP)
result = forge.heal_and_detect(doc, label=base, features="all")
forge.inject(result, data_injector=lambda cluster, txt: {"material": "AISI304", "thickness": 3.0})

out = forge.to_dxf(result, doc)
for cluster in result.clusters:
    forge.write_metadata_to_dxf(out, cluster)

path = OUTDIR / f"{base}_xdata.dxf"
out.saveas(path)
print(f"scritto: {path}")

# rilettura da file
reloaded = ezdxf.readfile(path)
meta = forge.read_metadata_from_dxf(reloaded)
print("XDATA riletto:")
for k, v in meta.items():
    print(f"   {k}: {v}")

# NB: set_schema() sostituisce lo schema globale per tutto il processo. Per
# ripristinare quello di default:
#     from forge.rules.metadata_schema import METADATA_FIELDS
#     forge.set_schema(METADATA_FIELDS)
