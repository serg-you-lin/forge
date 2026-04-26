"""
ARC_splitter_injecter.py
---------------
Testa lo splitter su un file DXF del cliente che utilizaz i dati su ogni figlio per riempire i dati.
Produce un file separato per ogni pezzo trovato con il nome che trova nel txt del file, e crea una subfolder con il nome dell'originale.


"""

import ezdxf
import dxf_forge as forge
import os
from dxf_forge.text_utils import clean_mtext, handle_mleader
from shapely.geometry import Point
import re
import json
from dxf_forge.exporter import build_metadata


# ← CAMBIA QUI con il tuo file
input_dxf  = r"c:\Users\FEDERICO\Documents\Python_Scripts\Projects\DXF\ARC - Copia\ARC.6200012802 Nipote\6200012802 Sviluppo.dxf"
#input_dir = os.path.abspath(input_dxf)
output_dir = os.path.join(os.path.dirname(input_dxf), os.path.splitext(os.path.basename(input_dxf))[0])

###########################################################
# Funzioni per estrarre i dati dai testi e iniettarli nei custom dei pezzi
###########################################################

def estrai_materiale(doc) -> str:
    """Legge il materiale dal blocco Cartiglio_sviluppo del padre."""
    try:
        block = doc.blocks.get('Cartiglio_sviluppo')
        for e in block:
            if e.dxftype() == 'MTEXT':
                txt = clean_mtext(e.text)
                if txt.lower().startswith('materiale'):
                    return txt.split(':', 1)[-1].strip()
    except Exception:
        pass
    return "N/D"


def parse_testi(testi: list[str]) -> dict:
    info = {"codice": "", "thickness": 0.0, "quantity": 1}
    
    # Unisci tutto e risplittalo riga per riga, così gestisci
    # sia testi già separati che blob MTEXT multi-riga
    righe = []
    for t in testi:
        righe.extend(t.splitlines())
    righe = [r.strip() for r in righe if r.strip()]
    
    for r in righe:
        r_low = r.lower()
        if r_low.startswith('codice'):
            info["codice"] = r.split(':', 1)[-1].strip()
        elif r_low.startswith('spessore'):
            numero = re.search(r'[\d.,]+', r.split(':', 1)[-1])
            if numero:
                info["thickness"] = float(numero.group().replace(',', '.'))
        elif 'pezzi' in r_low:
            numero = re.search(r'\d+', r.split(':', 1)[-1])
            if numero:
                info["quantity"] = int(numero.group())
    return info


def sanitize_filename(name: str) -> str:
    """Rimuove/sostituisce caratteri illegali nei nomi file Windows."""
    name = name.strip()
    name = re.sub(r'[\\/:"*?<>|\n\r\t]', '_', name)
    name = re.sub(r'_+', '_', name)   # collassa underscore multipli
    name = name.strip('_.')
    return name or "UNNAMED"


# Il namer ora sanifica sempre l'output
namer=lambda i, part: sanitize_filename(
    part.custom.get("_codice") or f"{label}_PART{i}"
),


def make_data_injector(doc):
    materiale = estrai_materiale(doc)  # una volta sola sul padre
    print(f"  [injector] materiale: {materiale}")

    def data_injector(part, testi) -> dict:  # testi arriva da split_to_files
        info = parse_testi(testi)
        print(f"  [injector] {part.label} → codice={info['codice']} sp={info['thickness']} q={info['quantity']}")
        return {
            "material" : materiale,
            "thickness": info["thickness"],
            "quantity" : info["quantity"],
            "_codice"  : info["codice"],  # usato dal namer, non finisce nel JSON
        }

    return data_injector

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

# Guarda dentro gli INSERT
for e in msp:
    if e.dxftype() == 'INSERT':
        try:
            block = doc.blocks.get(e.dxf.name)
            inner = Counter(sub.dxftype() for sub in block)
            print(f"  INSERT '{e.dxf.name}' contiene: {dict(inner)}")
        except Exception as ex:
            print(f"  INSERT error: {ex}")

# Valida prima
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

# Split — salva ogni pezzo in un file separato
print(f"\n--- SPLIT → {output_dir} ---")
import os
label = os.path.splitext(os.path.basename(input_dxf))[0]
label = label.replace(" Sviluppo", "")

result = forge.split_to_files(
    msp,
    output_folder=output_dir,
    explode_inserts=True,
    label=label,
    source_file=input_dxf,
    include_annotations=True,
    data_injector=make_data_injector(doc),
    namer=lambda i, part: part.custom.get("_codice") or f"{label}_PART{i}",
)

for part in result.parts:
    filepath = os.path.join(output_dir, f"{part.label}.dxf")
    child_doc = ezdxf.readfile(filepath)
    #forge.write_metadata_to_dxf(child_doc, part)
    child_doc.saveas(filepath)  # salva PRIMA gli xdata
    
    # JSON per pezzo
    meta = build_metadata(part)
    json_path = os.path.join(output_dir, f"{part.label}.json")
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
    print(f"  salvato: {part.label}")
    
# # DEBUG — cosa c'è nel msp dopo split_to_files?
# print("\n--- DEBUG MSP DOPO SPLIT ---")
# from collections import Counter
# types = Counter(e.dxftype() for e in msp)
# for t, count in sorted(types.items()):
#     print(f"  {t}: {count}")

# for pline in msp.query('LWPOLYLINE'):
#     pts = list(pline.get_points())
#     print(f"  LWPOLYLINE: {len(pts)} vertici, layer={pline.dxf.layer}")
# print(f"\nRisultato:")
# print(f"  Pezzi trovati : {result.part_count}")
# print(f"  Valido        : {result.is_valid}")
# if result.warnings:
#     for w in result.warnings:
#         print(f"  WARN: {w}")

# for i, part in enumerate(result.parts):
#     print(f"\n  Pezzo {i+1}: {part.label}")
#     print(f"    Area netta : {part.area:.1f}")
#     print(f"    Fori       : {len(part.inners)}")
#     print(f"    Bbox       : {part.bbox}")

# Esporta metadati JSON
forge.save_json(result, "split_metadata.json")
print(f"\nMetadati salvati: split_metadata.json")
print(f"File DXF salvati in: {output_dir}/")





