"""
generate_golden_annotations.py
------------------------------
Genera i golden file per il test di regressione sulle annotazioni
(model/annotation.py: Note / Dimension / Leader prodotti dall'adapter DXF).

Snapshot di `forge.load_dxf(...).annotations` — l'estrazione grezza, prima di
heal() e prima della futura fase interpret_annotations(). Quando quella fase
esisterà, questo script si estende con part_ref / target / references.

DXF sorgente: tests/examples/*.dxf (quelli che contengono annotazioni)
Golden JSON:  tests/examples/golden/annotations/

Runna UNA VOLTA quando sei soddisfatto dell'estrazione corrente, e mai per far
passare un test senza aver prima verificato che l'output è giusto.

    python generate_golden_annotations.py            # genera solo i mancanti
    python generate_golden_annotations.py --force    # rigenera tutti
    python generate_golden_annotations.py --only gamba_tavolo
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import ezdxf

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import forge
from forge.model.annotation import Note, Dimension, Leader

EXAMPLES_DIR = project_root / "tests" / "examples"
GOLDEN_DIR = EXAMPLES_DIR / "golden" / "annotations"

# I DXF sorgente vivono sotto tests/examples/ o tests/examples/golden/.
_SOURCE_DIRS = [EXAMPLES_DIR, EXAMPLES_DIR / "golden"]

_ANNOTATION_DXF_TYPES = {"TEXT", "MTEXT", "DIMENSION", "LEADER", "MULTILEADER"}


def _has_annotations(dxf_path: Path) -> bool:
    try:
        msp = ezdxf.readfile(dxf_path).modelspace()
    except Exception:
        return False
    return any(e.dxftype() in _ANNOTATION_DXF_TYPES for e in msp)


def _rendered_counts(r) -> dict:
    return {"strokes": len(r.strokes), "fills": len(r.fills), "texts": len(r.texts)}


def _annotation_dict(a) -> dict:
    d = {
        "type": type(a).__name__,
        "kind": a.kind,
        "position": [round(a.position[0], 3), round(a.position[1], 3)],
        "display_text": a.display_text,
        "layer": a.layer,
    }
    if isinstance(a, Note):
        d["height"] = round(a.height, 3)
        d["rotation"] = round(a.rotation, 3)
    elif isinstance(a, Dimension):
        d["dim_type"] = a.dim_type
        d["measured_value"] = (
            None if a.measured_value is None else round(a.measured_value, 4)
        )
        d["text_override"] = a.text_override
        d["rendered"] = _rendered_counts(a.rendered)
    elif isinstance(a, Leader):
        d["vertices"] = len(a.vertices)
        d["rendered"] = _rendered_counts(a.rendered)
    return d


def _sort_key(entry: dict):
    return (entry["position"][0], entry["position"][1], entry["kind"], entry["display_text"])


def generate(force: bool = False, only: str = None) -> None:
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)

    candidates = []
    seen = set()
    for d in _SOURCE_DIRS:
        for f in sorted(d.glob("*.dxf")):
            if f.stem in seen or "_healed" in f.stem:
                continue
            seen.add(f.stem)
            candidates.append(f)
    dxf_files = [f for f in candidates if _has_annotations(f)]
    if only:
        dxf_files = [f for f in dxf_files if f.stem == only]

    generated = skipped = failed = 0
    for dxf_path in dxf_files:
        golden_path = GOLDEN_DIR / f"{dxf_path.stem}.json"
        if golden_path.exists() and not force:
            print(f"  SKIP (esiste): {dxf_path.name}")
            skipped += 1
            continue
        try:
            doc = forge.load_dxf(dxf_path, explode_inserts=True, flatten_z_flag=True,
                                 verbose=False)
            entries = sorted((_annotation_dict(a) for a in doc.annotations), key=_sort_key)
            golden = {
                "source_file": dxf_path.name,
                "annotation_count": len(entries),
                "by_kind": dict(Counter(e["kind"] for e in entries)),
                "annotations": entries,
            }
            golden_path.write_text(
                json.dumps(golden, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            print(f"  OK: {dxf_path.name} → {len(entries)} annotazioni {golden['by_kind']}")
            generated += 1
        except Exception as ex:
            import traceback
            print(f"  ERRORE: {dxf_path.name} — {ex}")
            traceback.print_exc()
            failed += 1

    print(f"\nGenerati: {generated}  Skippati: {skipped}  Errori: {failed}")
    print(f"Golden in: {GOLDEN_DIR}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--only", type=str, default=None)
    args = parser.parse_args()
    generate(force=args.force, only=args.only)
