"""
pipeline_demo.py
----------------
Demo della pipeline dxf-forge.

Flusso per ogni file:
    1. validate_msp  -> filtra file problematici
    2. heal()        -> pulisce la geometria
    3. classify()    -> classifica entita extra, aggiunge metadati custom
    4. exporter      -> scrive XDATA nel DXF + JSON su disco

Uso:
    python pipeline_demo.py
    python pipeline_demo.py --input mia_cartella --output risultati
    python pipeline_demo.py --input mia_cartella --material S235 --thickness 2.0
"""

import argparse
import json
from pathlib import Path

import ezdxf
import forge

GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
CYAN   = "\033[96m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

def ok(msg):   print(f"  {GREEN}OK{RESET}  {msg}")
def warn(msg): print(f"  {YELLOW}WARN{RESET} {msg}")
def err(msg):  print(f"  {RED}FAIL{RESET} {msg}")
def info(msg): print(f"  {CYAN}INFO{RESET} {msg}")

# Mappa entita di default — personalizzabile per officina
ENTITY_MAP = {
    "fold_lines": {"layers": ["BEND", "PIEGA", "FOLD", "PIEGATURA"], "colors": []},
    "punch":      {"layers": ["PUNCH", "BULIN", "PUNCHING"],          "colors": []},
    "mark":       {"layers": ["MARK", "MARCA", "MARKING"],            "colors": []},
}


def process_file(dxf_path, output_dir, extra_metadata=None, entity_map=None):
    """Processa un singolo DXF attraverso l'intera pipeline."""
    name = dxf_path.stem
    print(f"\n{BOLD}--- {dxf_path.name} ---{RESET}")

    summary = {
        "file": dxf_path.name, "status": "ok",
        "parts": 0, "warnings": [], "errors": [], "metadata": [],
    }

    # 1. Apertura
    try:
        doc = ezdxf.readfile(str(dxf_path))
        msp = doc.modelspace()
    except Exception as e:
        err(f"Impossibile aprire: {e}")
        summary["status"] = "error"
        summary["errors"].append(str(e))
        return summary

    # 2. Validazione
    check = forge.validate_msp(msp)
    for w in check.warnings:
        warn(f"[validate] {w}")
    for e in check.errors:
        err(f"[validate] {e}")
    if not check.is_valid:
        err("File non valido - skippato.")
        summary["status"] = "invalid"
        summary["errors"] = check.errors
        return summary

    # 3. Healing
    result = forge.heal(msp, label=name, source_file=str(dxf_path), write_to_msp=True)
    for w in result.warnings:
        warn(f"[heal] {w}")
    for e in result.errors:
        err(f"[heal] {e}")
    if not result.is_valid or not result.parts:
        err("Healing fallito o nessun pezzo - skippato.")
        summary["status"] = "error"
        summary["errors"] = result.errors or ["Nessun pezzo trovato."]
        return summary

    info(f"Pezzi trovati: {result.part_count}")

    # 4. Classificazione entita extra + metadati custom
    forge.classify(
        msp, result.parts,
        entity_map=entity_map or ENTITY_MAP,
        extra_metadata=extra_metadata,
        result=result,
    )
    seen = set()
    for w in result.warnings:
        if w not in seen:
            warn(f"[classify] {w}")
            seen.add(w)

    summary["parts"]    = result.part_count
    summary["warnings"] = result.warnings

    # 5. Export
    if result.part_count > 1:
        # Multi-pezzo: split in sottocartella
        split_dir = output_dir / name
        info(f"Multi-pezzo -> split in {split_dir.name}/")
        split_result = forge.split_to_files(
            msp, output_folder=str(split_dir),
            label=name, source_file=str(dxf_path), write_metadata=True,
        )
        for part in split_result.parts:
            part_path = split_dir / f"{part.label}.dxf"
            if part_path.exists():
                part_doc = ezdxf.readfile(str(part_path))
                meta = forge.read_metadata_from_dxf(part_doc)
                if meta:
                    _print_metadata(meta)
                    summary["metadata"].append(meta)
        json_path = output_dir / f"{name}_split.json"
        forge.save_json(split_result, str(json_path))
        ok(f"JSON: {json_path.name}")

    else:
        # File singolo: salva DXF healed con metadati XDATA
        healed_path = output_dir / f"{name}_healed.dxf"
        forge.write_metadata_to_dxf(doc, result.parts[0])
        doc.saveas(str(healed_path))
        ok(f"DXF healed: {healed_path.name}")

        # Verifica metadati rileggendo il file
        saved_doc = ezdxf.readfile(str(healed_path))
        meta = forge.read_metadata_from_dxf(saved_doc)
        if meta:
            _print_metadata(meta)
            summary["metadata"].append(meta)

        json_path = output_dir / f"{name}.json"
        forge.save_json(result, str(json_path))
        ok(f"JSON: {json_path.name}")

    return summary


def _print_metadata(meta):
    """Stampa i metadati in modo leggibile."""
    bbox = meta.get("bbox", {})
    w = bbox.get("maxx", 0) - bbox.get("minx", 0)
    h = bbox.get("maxy", 0) - bbox.get("miny", 0)
    print(f"    label      : {meta.get('label', '-')}")
    print(f"    area       : {meta.get('area', 0):.2f} mm2")
    print(f"    dimensioni : {w:.2f} x {h:.2f} mm")
    print(f"    fori       : {meta.get('holes_count', 0)}")
    custom = meta.get("custom", {})
    if custom:
        if custom.get("material"):  print(f"    materiale  : {custom['material']}")
        if custom.get("thickness"): print(f"    spessore   : {custom['thickness']} mm")
        fold  = custom.get("fold_lines", [])
        punch = custom.get("punch", [])
        mark  = custom.get("mark", [])
        trash = custom.get("trash", [])
        if fold:  print(f"    piegature  : {len(fold)}")
        if punch: print(f"    punching   : {len(punch)}")
        if mark:  print(f"    marcature  : {len(mark)}")
        if trash: print(f"    trash      : {len(trash)} entita non riconosciute")


def run_pipeline(input_dir, output_dir, extra_metadata=None, entity_map=None):
    """Processa tutti i DXF in input_dir."""
    output_dir.mkdir(parents=True, exist_ok=True)
    dxf_files = sorted(input_dir.glob("*.dxf")) + sorted(input_dir.glob("*.DXF"))
    if not dxf_files:
        print(f"{RED}Nessun DXF trovato in {input_dir}{RESET}")
        return

    print(f"{BOLD}\ndxf-forge pipeline{RESET}")
    print(f"Input    : {input_dir}")
    print(f"Output   : {output_dir}")
    print(f"Files    : {len(dxf_files)}")
    if extra_metadata:
        print(f"Metadati : {extra_metadata}")

    summaries = []
    for dxf_path in dxf_files:
        summary = process_file(dxf_path, output_dir, extra_metadata, entity_map)
        summaries.append(summary)

    print(f"\n{BOLD}=== RIEPILOGO ==={RESET}")
    ok_count    = sum(1 for s in summaries if s["status"] == "ok")
    warn_count  = sum(1 for s in summaries if s["warnings"])
    err_count   = sum(1 for s in summaries if s["status"] in ("error", "invalid"))
    total_parts = sum(s["parts"] for s in summaries)

    print(f"  File processati : {len(summaries)}")
    print(f"  {GREEN}OK{RESET}              : {ok_count}")
    print(f"  {YELLOW}Con warning{RESET}     : {warn_count}")
    print(f"  {RED}Errori/skippati{RESET} : {err_count}")
    print(f"  Pezzi totali    : {total_parts}")

    report_path = output_dir / "pipeline_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(summaries, f, indent=2, ensure_ascii=False)
    print(f"\n  Report: {report_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="dxf-forge pipeline")
    parser.add_argument("--input",     default="tests/examples/batch")
    parser.add_argument("--output",    default="pipeline_output")
    parser.add_argument("--material",  default=None, help="Es: S235")
    parser.add_argument("--thickness", default=None, type=float, help="Es: 2.0")
    args = parser.parse_args()

    extra = {}
    if args.material:  extra["material"]  = args.material
    if args.thickness: extra["thickness"] = args.thickness

    run_pipeline(
        Path(args.input), Path(args.output),
        extra_metadata=extra or None,
        entity_map=ENTITY_MAP,
    )