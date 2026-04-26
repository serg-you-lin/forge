"""
debug_xdata.py
--------------
Debug scrittura e lettura XDATA FORGE su un singolo file DXF.
"""

import ezdxf
import json
import dxf_forge as forge

# ← CAMBIA QUI
INPUT_DXF  = r"tests/examples/older_dxf_file.DXF"
OUTPUT_DXF = r"tests/examples/older_dxf_file_xdata_test.dxf"
tolerance  = 0.05

# ---------------------------------------------------------------------------
# 1. Apri e heala
# ---------------------------------------------------------------------------
print(f"Apertura: {INPUT_DXF}")
doc = ezdxf.readfile(INPUT_DXF)

# Converti a R2010 se necessario
if doc.dxfversion < 'AC1015':
    doc = forge.upgrade_to_r2010(doc)
    msp = doc.modelspace()
else:
    msp = doc.modelspace()

result = forge.heal(msp, tolerance=tolerance, write_to_msp=True)
print(f"Pezzi trovati: {result.part_count}")
for w in result.warnings:
    print(f"  WARN: {w}")
for e in result.errors:
    print(f"  ERROR: {e}")

# ---------------------------------------------------------------------------
# 2. Tenta scrittura XDATA e mostra errori reali
# ---------------------------------------------------------------------------
print("\n--- SCRITTURA XDATA ---")
for i, part in enumerate(result.parts):
    print(f"\nParte {i+1}: {part.label}")
    try:
        msp2 = doc.modelspace()
        plines = list(msp2.query('LWPOLYLINE'))
        circles = list(msp2.query('CIRCLE'))
        print(f"  LWPOLYLINE nel msp: {len(plines)}")
        print(f"  CIRCLE nel msp: {len(circles)}")

        app_id = 'FORGE'
        if app_id not in doc.appids:
            doc.appids.add(app_id)
            print(f"  AppID '{app_id}' registrato")
        else:
            print(f"  AppID '{app_id}' già presente")

        # Cerca la LWPOLYLINE outer
        outer_entity = None
        for pline in plines:
            if pline.dxf.layer == forge.LAYER_OUTER:
                outer_entity = pline
                break

        if outer_entity is None:
            print(f"  WARN: nessuna LWPOLYLINE su layer {forge.LAYER_OUTER}")
            print(f"  Layer presenti: {set(p.dxf.layer for p in plines)}")
            # Fallback: prima LWPOLYLINE disponibile
            if plines:
                outer_entity = plines[0]
                print(f"  Fallback: uso prima LWPOLYLINE layer={outer_entity.dxf.layer}")
        else:
            print(f"  Entità target: LWPOLYLINE layer={outer_entity.dxf.layer}")

        if outer_entity is None:
            print(f"  ERRORE: nessuna entità disponibile per XDATA")
            continue

        d = part.to_dict()
        meta = {
            'label':       d['label'],
            'source_file': d['source_file'],
            'area':        d['area'],
            'bbox':        d['bbox'],
        }
        json_str = json.dumps(meta, ensure_ascii=False)
        print(f"  JSON da scrivere: {json_str[:80]}...")

        outer_entity.set_xdata(app_id, [(1000, json_str)])
        print(f"  XDATA scritta OK")

    except Exception as ex:
        print(f"  ERRORE reale: {type(ex).__name__}: {ex}")

# ---------------------------------------------------------------------------
# 3. Salva
# ---------------------------------------------------------------------------
doc.saveas(OUTPUT_DXF)
print(f"\nSalvato: {OUTPUT_DXF}")

# ---------------------------------------------------------------------------
# 4. Rileggi e verifica
# ---------------------------------------------------------------------------
print("\n--- VERIFICA LETTURA XDATA ---")
doc2 = ezdxf.readfile(OUTPUT_DXF)
msp2 = doc2.modelspace()

found = 0
for entity in msp2:
    try:
        xdata = entity.get_xdata('FORGE')
    except Exception:
        continue
    if not xdata:
        continue
    for tag in xdata:
        if tag.code == 1000:
            found += 1
            try:
                meta = json.loads(tag.value)
                print(f"\nEntità: {entity.dxftype()}  layer={entity.dxf.layer}")
                print(json.dumps(meta, indent=2, ensure_ascii=False))
            except Exception as ex:
                print(f"  ERRORE parsing: {ex}")
                print(f"  raw: {tag.value}")

if found == 0:
    print("Nessuna XDATA FORGE trovata nel file salvato.")
else:
    print(f"\nTotale XDATA trovate: {found}")