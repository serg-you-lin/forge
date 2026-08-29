"""
01_load_and_validate.py — aprire un file e controllarlo
======================================================

API forge usate:
    load_dxf            unico punto che legge ezdxf → ForgeDocument
    document_from_msp   costruisce un ForgeDocument da un msp già aperto (test / geometria a mano)
    validate           valida l'INPUT prima di heal() — non modifica niente

Dopo load_dxf il documento ezdxf sorgente sparisce: heal()/detect() lavorano
solo su ForgeDocument.edges (primitive pure) e ForgeDocument.annotations.

    python 01_load_and_validate.py
"""

import ezdxf
import forge

# --- CONFIG ----------------------------------------------------------------
INPUT     = r"tests/examples/Linee_piegatura.dxf"
TOLERANCE = 0.5
LABEL_MAP = {"Piega": "bending", "MARK": "engrave"}   # {layer: work_type}, case-insensitive
# -------------------------------------------------------------------------

# 1. load_dxf --------------------------------------------------------------
doc = forge.load_dxf(
    INPUT,
    tolerance=TOLERANCE,        # salvata in source_meta, riusata da heal()
    label_map=LABEL_MAP,        # assegna il ruolo agli Edge già in fase di traduzione
    explode_inserts=True,
    flatten_z_flag=True,
    verbose=False,
)

print(f"file            : {doc.source_path}")
print(f"edges           : {len(doc.edges)}")
print(f"annotations     : {len(doc.annotations)}")
print(f"source_meta     : {doc.source_meta}")
print(f"loader warnings : {len(doc.warnings)}")
for w in doc.warnings:
    print(f"   - {w}")

# gli Edge sono primitive pure — nessun riferimento a ezdxf
print("\nprimi 5 edge:")
for e in doc.edges[:5]:
    print(f"   role={e.role:<8} {type(e.segment).__name__:<10} "
          f"{tuple(round(c, 1) for c in e.start)} -> {tuple(round(c, 1) for c in e.end)}")

# 2. validate (input) ----------------------------------------------------
check = forge.validate(doc)
print(f"\nvalidate.is_valid : {check.is_valid}")
for e in check.errors:
    print(f"   ERROR: {e}")
for w in check.warnings:
    print(f"   warn : {w}")
if not check.is_valid:
    raise SystemExit("file non lavorabile")

# 3. document_from_msp — stessa cosa, ma da un msp già in memoria ---------
ez = ezdxf.new("R2010")
msp = ez.modelspace()
msp.add_lwpolyline([(0, 0), (100, 0), (100, 50), (0, 50)], close=True)
doc2 = forge.document_from_msp(msp, tolerance=0.5, source_path="<generato a mano>")
print(f"\ndocument_from_msp : {len(doc2.edges)} edge da un rettangolo costruito a mano")
