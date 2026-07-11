"""
ARC_splitter.py
---------------
Pipeline forge completa su file DXF cliente.
Produce un file separato per ogni pezzo con nome dal codice nel testo,
in una subfolder con il nome dell'originale.

Nota: write() e inject() rimossi — split() materializza i VS internamente,
snapmark lavora sul doc figlio dentro on_part.
"""

import ezdxf
import forge
import os
import re
import json
from forge.io.text_utils import clean_mtext
from forge.io.exporter import build_metadata
import sys

sys.path.insert(
    0,
    r"C:\Users\luca\Documents\python\snapmark"
)
import snapmark as sm


# ← CAMBIA QUI
input_dxf  = r"\\192.10.10.180\Azerouno\Tecnico\ARC02  dal 02-26 creiamo cartella vecchi dis\4477\6200013067 Sviluppo.dxf"
output_dir = os.path.join(os.path.dirname(input_dxf), os.path.splitext(os.path.basename(input_dxf))[0])
folder_name = os.path.basename(os.path.dirname(input_dxf))

customer = 'ARC02'
drawing  = os.path.basename(os.path.dirname(input_dxf))

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PATTERNS = {
    "codice":   r'cod(?:ice)?\s*[:\-]?\s*(\S+)',
    "spessore": r'spes(?:sore)?\s*[:\-]?\s*([\d.,]+)',
    "materiale":r'mat(?:eriale)?\s*[:\-]?\s*(.+)',
    "quantity": r'pez(?:zi)[^\d]*([\d]+)',
}

MATERIAL_MAP = {
    "s235": "FE-DECAPATO",
    "aisi 304": "I304",
    "aisi304": "I304",
}

if re.fullmatch(r'ARC\.\d{5}', folder_name):
    drawing = folder_name
elif folder_name.isdigit():
    drawing = f"ARC.{folder_name.zfill(5)}"
else:
    drawing = "ARC.00000"

def sanitize_filename(name: str) -> str:
    name = name.strip()
    name = re.sub(r'[\\/:"*?<>|\n\r\t]', '_', name)
    name = re.sub(r'_+', '_', name)
    return name.strip('_.') or "UNNAMED"

def normalizza_materiale(raw_material: str) -> str:
    if not raw_material:
        return "N/D"
    mat_clean = raw_material.strip().lower()
    for chiave, valore_mappato in MATERIAL_MAP.items():
        if chiave in mat_clean:
            return valore_mappato
    return raw_material.strip()

def estrai_materiale(doc) -> str:
    for block in doc.blocks:
        if 'cartiglio' in block.name.lower():
            for e in block:
                if e.dxftype() == 'MTEXT':
                    txt = clean_mtext(e.text)
                    if 'materiale' in txt.lower():
                        raw_mat = txt.split(':', 1)[-1].strip()
                        return normalizza_materiale(raw_mat)
    return "N/D"


def parse_testi(testi: list[str]) -> dict:
    info = {"codice": "", "thickness": 0.0, "quantity": 1, "material": "N/D"}
    righe = [r.strip() for t in testi for r in t.splitlines() if r.strip()]
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
                info["material"] = normalizza_materiale(val)
            elif key == "quantity":
                info["quantity"] = int(val)
    return info


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


# ---------------------------------------------------------------------------
# Apertura
# ---------------------------------------------------------------------------

print(f"Apertura: {input_dxf}")
doc = ezdxf.readfile(input_dxf)
if doc.dxfversion < 'AC1015':
    doc = forge.upgrade_to_r2010(doc)
msp = doc.modelspace()

# ---------------------------------------------------------------------------
# Validazione
# ---------------------------------------------------------------------------

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

# ---------------------------------------------------------------------------
# Pipeline forge
# ---------------------------------------------------------------------------

label = os.path.splitext(os.path.basename(input_dxf))[0].replace(" Sviluppo", "")

print(f"\n--- HEAL ---")
result = forge.heal(
    msp,
    tolerance=.2,
    explode_inserts=True,
    label=label,
    source_file=input_dxf,
)
for w in result.warnings:
    print(f"  [heal] {w}")
for e in result.errors:
    print(f"  [heal ERROR] {e}")

if not result.is_valid or not result.parts:
    print("Healing fallito, interrompo.")
    exit(1)

print(f"trash count: {len(result.trash_entities)}")
for e in result.trash_entities:
    print(f"  {e.dxftype()} layer={e.dxf.layer}")

print(f"\n--- DETECT ---")
forge.detect(result, msp)

print(f"\n--- INJECT ---")
forge.inject(msp, result, data_injector=make_data_injector(doc))

# ---------------------------------------------------------------------------
# Snapmark — configurato una volta sola
# ---------------------------------------------------------------------------

marker = sm.AddMark(
    sequence=sm.SequenceBuilder().file_name(trim_start=5, trim_end=0).build(),
    max_height=9,
    min_height=7,
    down_to=4,
    margin=4,
    scale_factor=50,
    avoid_layers=["Trash", "Bending"],
    start_y=5,
)

# ---------------------------------------------------------------------------
# Split — snapmark e post-processing lavorano sul doc figlio
# ---------------------------------------------------------------------------

print(f"\n--- SPLIT → {output_dir} ---")


def post_process(part, doc_out, path):
    file_name = os.path.basename(path)

    # marker = sm.AddMark(
    #     sequence=sm.SequenceBuilder().file_name(trim_start=5).build(),
    #     max_height=9,
    #     min_height=7,
    #     down_to=5,
    #     margin=4,
    #     scale_factor=50,
    #     avoid_layers=["Trash", "Bending"],
    #     start_y=5,
    # )

    marker.execute_on_doc(doc_out, file_name=file_name, folder=output_dir)
    marker.message(file_name)
    
    sm.AddText(
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
    ).execute_on_doc(doc_out, file_name=file_name, folder=output_dir)

    sm.TrimBendLines(
        layers="Bending",
        start_length=25,
        end_length=25,
    ).execute_on_doc(
        doc_out,
        file_name=file_name,
        folder=output_dir,
    )

    meta = build_metadata(part)
    json_path = os.path.splitext(path)[0] + ".json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    print(f"  salvato: {part.label}")


forge.split(
    msp,
    result,
    output_folder=output_dir,
    namer=lambda i, part: sanitize_filename(
        part.custom.get("_codice") or f"{label}_P{i + 1}"
    ),
    on_part=post_process,
)

forge.save_json(result, "split_metadata.json")
print(f"\nMetadati salvati: split_metadata.json")
print(f"File DXF salvati in: {output_dir}/")