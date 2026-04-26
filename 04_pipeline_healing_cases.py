"""
run_healer_batch.py
-------------------

Batch healer per tutti i DXF in una cartella.

Regole:
- ignora i file *_healed.dxf
- sovrascrive i *_healed.dxf esistenti
- processa solo file modificati dopo l'ultimo heal

Output:
    nomefile_healed.dxf
    nomefile_healed_metadata.json
"""

import ezdxf
import dxf_forge as forge
from dxf_forge.dxf_inspect import DxfInspector
from pathlib import Path


# ------------------------------------------------
# CARTELLA DA PROCESSARE
# ------------------------------------------------

input_dir = Path(r"c:\Users\FEDERICO\Documents\Python_Scripts\Projects\DXF\33-24\prove\prove").resolve()

tolerance = 5


# ------------------------------------------------
# INSPECTOR CONFIG
# ------------------------------------------------

inspector = DxfInspector(
    summary=False,
    lines=False,
    arcs=False,
    polylines=False,
    circles=False,
    splines=False,
    graph=False,
)

print(f"\nCartella analizzata: {input_dir}\n")


# ------------------------------------------------
# TROVA FILE DXF
# ------------------------------------------------

dxf_files = [
    f for f in input_dir.glob("*")
    if f.is_file() and f.suffix.lower() == ".dxf"
]

if not dxf_files:
    print("Nessun file DXF trovato.")
    raise SystemExit(0)

print(f"Trovati {len(dxf_files)} file\n")


# ------------------------------------------------
# PROCESSAMENTO
# ------------------------------------------------

for input_dxf in dxf_files:

    # ignora file già healati
    if input_dxf.stem.endswith("_healed"):
        continue

    base_name = input_dxf.stem

    output_dxf = input_dxf.parent / f"{base_name}_healed.dxf"
    output_json = input_dxf.parent / f"{base_name}_healed_metadata.json"
    output_xml = input_dxf.parent / f"{base_name}_healed_metadata.xml"


    print("\n===================================")
    print(f"Apertura: {input_dxf.name}")

    try:

        doc = ezdxf.readfile(input_dxf)

        if doc.dxfversion < 'AC1015':
            doc = forge.upgrade_to_r2010(doc)

        msp = doc.modelspace()

        inspector.analyze(msp, title=str(input_dxf.name))

        # ---------------- VALIDAZIONE ----------------

        print("\n--- VALIDAZIONE ---")

        check = forge.validate_msp(msp)

        for w in check.warnings:
            print(f"  WARN: {w}")

        for e in check.errors:
            print(f"  ERROR: {e}")

        if not check.errors:
            print("  OK: nessun errore bloccante")

        # ---------------- HEALING ----------------

        for entity in msp:
            layer = entity.dxf.layer if entity.dxf.hasattr("layer") else ""
            if layer.upper() in ("MARK", "MARCATURA"):
                print(f"  Entità speciale: {entity.dxftype()} layer={layer}")
        
        print("\n--- HEALING ---")

        result = forge.heal(
            msp,
            tolerance=tolerance,
            write_to_msp=True,
            label=base_name,
            source_file=Path(input_dxf).name,
            special_layers={
                "MARK": "engrave",                
                "MARCATURA": "bending",
            }
        )

        # Scrive XDATA sul documento
        for part in result.parts:
            forge.write_metadata_to_dxf(doc, part)

        # debug XDATA
        for entity in msp:
            try:
                xdata = entity.get_xdata('FORGE')
                if xdata:
                    print(f"  XDATA scritta su: {entity.dxftype()} layer={entity.dxf.layer}")
            except Exception:
                pass

        print(f"\n  Pezzi trovati : {result.part_count}")
        print(f"  Valido        : {result.is_valid}")

        for w in result.warnings:
            print(f"  WARN: {w}")

        for e in result.errors:
            print(f"  ERROR: {e}")

        for i, part in enumerate(result.parts):

            print(f"\n  Pezzo {i+1}:")
            print(f"    Area outer : {part.outer.area:.1f}")
            print(f"    Fori       : {len(part.inners)}")
            print(f"    Bbox       : {part.bbox}")

        # salva metadata
        forge.save_json(result, str(output_json))
        forge.save_xml(result, str(output_xml)) 

        if not result.is_valid:
            print("File non valido — non salvato.")
            continue

        # salva DXF
        doc.saveas(output_dxf)

        #print(f"\nSalvato: {output_dxf.name}")

        # ---------------- DEBUG OUTPUT ----------------

        print("\n--- LWPOLYLINE RISULTANTI ---")

        inspector_out = DxfInspector(polylines=True, summary=False)

        saved_doc = ezdxf.readfile(output_dxf)

        inspector_out.analyze(
            saved_doc.modelspace(),
            title=str(output_dxf.name)
        )

    except Exception as e:

        print(f"\nERRORE su {input_dxf.name}")
        print(e)


print("\nBatch completato.\n")