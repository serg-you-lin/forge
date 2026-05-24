"""
ARC_splitter_injecter.py
---------------
Testa lo splitter su un file DXF del cliente che utilizza i dati su ogni figlio per riempire i dati.
Produce un file separato per ogni pezzo trovato con il nome che trova nel txt del file, e crea una subfolder con il nome dell'originale.
"""

import ezdxf
import dxf_forge as forge
import os
from dxf_forge.io.text_utils import clean_mtext
import re
import json
from dxf_forge.io.exporter import build_metadata
import snapmark as sm


# ← CAMBIA QUI con il tuo file
input_dxf  = r"c:\Users\FEDERICO\Documents\Python_Scripts\Projects\DXF\TON_06_05_2026\6200012914 Sviluppo.dxf"
output_dir = os.path.join(os.path.dirname(input_dxf), os.path.splitext(os.path.basename(input_dxf))[0])

###########################################################
# Funzioni per estrarre i dati dai testi e iniettarli nei custom dei pezzi
###########################################################
customer = 'ARC02'
drawing  = os.path.basename(os.path.dirname(input_dxf))


def estrai_materiale(doc) -> str:
    for block in doc.blocks:
        print(f"  [block] {block.name}")
        if 'cartiglio' in block.name.lower():
            for e in block:
                print(f"    [entity] {e.dxftype()}")
                if e.dxftype() == 'MTEXT':
                    txt = clean_mtext(e.text)
                    print(f"    [mtext] '{txt}' → materiale in txt: {'materiale' in txt.lower()}")
                    if 'materiale' in txt.lower():
                        return txt.split(':', 1)[-1].strip()
    return "N/D"


PATTERNS = {
    "codice":   r'cod(?:ice)?\s*[:\-]?\s*(\S+)',
    "spessore": r'spes(?:sore)?\s*[:\-]?\s*([\d.,]+)',
    "materiale":r'mat(?:eriale)?\s*[:\-]?\s*(.+)',
    "quantity": r'pez(?:zi)[^\d]*([\d]+)',
}


def parse_testi(testi: list[str]) -> dict:
    info = {"codice": "", "thickness": 0.0, "quantity": 1, "material": "N/D"}
    righe = []
    for t in testi:
        righe.extend(t.splitlines())
    righe = [r.strip() for r in righe if r.strip()]
    blob = '\n'.join(righe)
    for key, pattern in PATTERNS.items():
        m = re.search(pattern, blob, re.IGNORECASE)
        if m:
            val = m.group(1).strip()
            if key == "codice":
                info["codice"] = val
            elif key == "spessore":
                info["thickness"] = float(val.replace(',', '.').split()[0])
            elif key == "materiale":
                info["material"] = val
            elif key == "quantity":
                info["quantity"] = int(val)
    return info


def sanitize_filename(name: str) -> str:
    """Rimuove/sostituisce caratteri illegali nei nomi file Windows."""
    name = name.strip()
    name = re.sub(r'[\\/:"*?<>|\n\r\t]', '_', name)
    name = re.sub(r'_+', '_', name)
    name = name.strip('_.')
    return name or "UNNAMED"


def make_data_injector(doc):
    materiale = estrai_materiale(doc)

    def data_injector(part, testi) -> dict:
        info = parse_testi(testi)
        print(f"  [injector] {part.label} → codice={info['codice']} "
              f"sp={info['thickness']} q={info['quantity']} mat={info['material']}")
        return {
            "material" : materiale,
            "thickness": info["thickness"],
            "quantity" : info["quantity"],
            "_codice"  : info["codice"],
        }
    return data_injector


# Configura il marker UNA VOLTA sola, fuori dal loop
marker = sm.AddMark(
    sequence=sm.SequenceBuilder().file_name(trim_start=5).build(),
    max_height=9,
    min_height=7,
    down_to=5,
    margin=4,
    scale_factor=50,
    avoid_layers=["Trash"],
    start_y=5,
)

#############################################################
print(f"Apertura: {input_dxf}")
doc = ezdxf.readfile(input_dxf)
if doc.dxfversion < 'AC1015':
    doc = forge.upgrade_to_r2010(doc)
msp = doc.modelspace()

from collections import Counter
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

print("\n--- VALIDAZIONE ---")
check = forge.validate_msp(msp)
for w in check.warnings:
    print(f"  WARN: {w}")
for e in check.errors:
    print(f"  ERROR: {e}")
if check.errors:
    print("Errori bloccanti trovati, interrompo.")
    exit(1)
print("  OK")

print(f"\n--- SPLIT → {output_dir} ---")
label = os.path.splitext(os.path.basename(input_dxf))[0]
label = label.replace(" Sviluppo", "")

# --- NUOVA PIPELINE ---
# 1. Heal
result = forge.heal(
    msp,
    tolerance=.2,
    write_to_msp=True,
    explode_inserts=True,
    label=label,
    source_file=input_dxf,
)
for w in result.warnings:
    print(f"  [heal] {w}")

# 2. Inject — dati custom + special layers
forge.inject(
    msp,
    result,
    data_injector=make_data_injector(doc),
)

# 3. Split — namer usa part.custom già popolato da inject
forge.split_to_files(
    msp,
    output_folder=output_dir,
    label=label,
    source_file=input_dxf,
    include_annotations=True,
    heal_result=result,
    namer=lambda i, part: sanitize_filename(
        part.custom.get("_codice") or f"{label}_PART{i}"
    ),
)

# 4. Post-processing per ogni pezzo
for part in result.parts:
    filepath = os.path.join(output_dir, f"{part.label}.dxf")
    if not os.path.exists(filepath):
        continue
    child_doc = ezdxf.readfile(filepath)

    marker.execute_on_doc(
        child_doc,
        file_name=f"{part.label}.dxf",
        folder=output_dir,
    )
    marker.message(f"{part.label}.dxf")

    text_op = sm.AddText(
        text_sequence=sm.TextBuilder()
            .static(f"Material:{part.custom.get('material', 'N/D')}")
            .static(f"Thickness:{part.custom.get('thickness', 0.0)}")
            .static(f"Quantity:{part.custom.get('quantity', 1)}")
            .static(f"Customer:{customer}")
            .static(f"Drawing:{drawing}")
            .build(),
        char_height=.2,
        text_layer="TEXT",
        text_color=3,
    )
    text_op.execute_on_doc(
        child_doc,
        file_name=f"{part.label}.dxf",
        folder=output_dir,
    )

    child_doc.saveas(filepath)

    meta = build_metadata(part)
    json_path = os.path.join(output_dir, f"{part.label}.json")
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
    print(f"  salvato: {part.label}")

forge.save_json(result, "split_metadata.json")
print(f"\nMetadati salvati: split_metadata.json")
print(f"File DXF salvati in: {output_dir}/")