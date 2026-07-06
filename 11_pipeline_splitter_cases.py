"""
run_splitter_batch.py
---------------------

Batch splitter per tutti i DXF in una cartella.

Flusso:
  1. Tutti i DXF della cartella entrano in queue come "originali"
  2. Ogni file viene healato
  3. is_multi?
       SÌ  → split_to_files (riusa heal_result, non heala due volte)
              → figli aggiunti ad already_split + queue
       NO  → metadati (JSON/XML) + salva

  I file in already_split sono figli già splittati:
  vengono healati e portati ai metadati, MAI risplittati.
  Questo impedisce la catena P1_P1_P1.

  Se il batch viene rilancito, i figli esistenti vengono sovrascritti
  da split_to_files — comportamento corretto e idempotente.
"""

import ezdxf
from pathlib import Path
from collections import deque
import forge

# ------------------------------------------------
# CARTELLA DA PROCESSARE
# ------------------------------------------------
input_dir = Path("tests/examples/files_multipli").resolve()
tolerance = 1

# ------------------------------------------------
# TROVA FILE DXF
# ------------------------------------------------
dxf_files = [f for f in input_dir.glob("*.dxf") if f.is_file()]

if not dxf_files:
    print("Nessun file DXF da processare.")
    raise SystemExit(0)

print(f"\nCartella analizzata: {input_dir}")
print(f"Trovati {len(dxf_files)} file DXF\n")

# ------------------------------------------------
# QUEUE + SET DEI FIGLI
# ------------------------------------------------
queue: deque[Path] = deque(dxf_files)
already_split: set[Path] = set()

while queue:
    file_path = queue.popleft()
    base_name = file_path.stem

    print("===================================")
    print(f"Processing: {file_path.name}")

    try:
        doc = ezdxf.readfile(file_path)
        msp = doc.modelspace()

        # ---------------- HEALING ----------------
        heal_result = forge.heal(msp, tolerance=tolerance, write_to_msp=True)

        # ---------------- MULTI o SINGOLO? ----------------
        if forge.is_multi(heal_result) and file_path not in already_split:
            # PADRE: splitta, non salvare, non fare metadati
            split_result = forge.split_to_files(
                msp,
                output_folder=str(file_path.parent),
                label=base_name,
                source_file=str(file_path),
                heal_result=heal_result,
            )
            print(f"  Split → {split_result.part_count} figli generati")

            for part in split_result.parts:
                child_path = file_path.parent / f"{part.label}.dxf"
                already_split.add(child_path)
                queue.append(child_path)

        else:
            # FIGLIO o file singolo: metadati + salva
            for part in heal_result.parts:
                forge.write_metadata_to_dxf(doc, part)

            output_json = file_path.parent / f"{base_name}_metadata.json"
            output_xml  = file_path.parent / f"{base_name}_metadata.xml"
            forge.save_json(heal_result, str(output_json))
            forge.save_xml(heal_result, str(output_xml))

            doc.saveas(file_path)  # sovrascrive il figlio sul posto
            print(f"  Metadati: {output_json.name}, {output_xml.name}")
            print(f"  Salvato:  {file_path.name}")

    except Exception as e:
        print(f"  ERRORE: {e}")

print("\nBatch splitter completato.\n")