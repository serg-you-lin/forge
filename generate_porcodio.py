"""
run_generate_single.py
----------------------
Genera il golden per un singolo DXF e salva il DXF healed per verifica CAD.
"""

import json
import sys
from pathlib import Path
import ezdxf

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import dxf_forge as forge

EXAMPLES_DIR = project_root / "tests" / "examples"
GOLDEN_DIR   = project_root / "tests" / "examples" / "golden"

# ← CAMBIA QUI
INPUT_DXF = r"tests/examples/BE3STEMMIE/la_104.DXF"

GLOBAL_SPECIAL_LAYERS = {
    "MARK":      "engrave",
    "Signature": "engrave",
}

DEFAULT_TOLERANCE = 0.2


def _load_config(dxf_path: Path) -> dict:
    config_path = EXAMPLES_DIR / "config" / f"{dxf_path.stem}.json"
    if config_path.exists():
        return json.loads(config_path.read_text(encoding="utf-8"))
    return {}


def main():
    dxf_path = Path(INPUT_DXF).resolve()
    if not dxf_path.exists():
        print(f"File non trovato: {dxf_path}")
        return

    config         = _load_config(dxf_path)
    tolerance      = config.get("tolerance", DEFAULT_TOLERANCE)
    special_layers = {**GLOBAL_SPECIAL_LAYERS, **config.get("special_layers", {})}

    print(f"File    : {dxf_path.name}")
    print(f"Tol     : {tolerance}")
    print(f"Layers  : {special_layers}")

    doc = ezdxf.readfile(dxf_path)
    if doc.dxfversion < "AC1015":
        doc = forge.upgrade_to_r2010(doc)
    msp = doc.modelspace()

    result = forge.heal(msp, tolerance=tolerance)

    forge.detect(result, msp, special_layers=special_layers)

    forge.write(msp, result)
    forge.inject(msp, result)

    # --- report ---
    print(f"\nParti   : {result.part_count}")
    for i, part in enumerate(result.parts):
        print(f"\n  Parte {i+1}:")
        print(f"    Area outer       : {part.outer.area:.2f}")
        print(f"    Holes            : {len(part.holes)}")
        print(f"    Inners           : {len(part.inners)}")
        if part.custom:
            for k, v in part.custom.items():
                print(f"    {k}: {v}")

    # --- salva DXF healed per verifica CAD ---
    output_dxf = dxf_path.parent / f"{dxf_path.stem}_healed.dxf"
    doc.saveas(output_dxf)
    print(f"\nDXF salvato : {output_dxf}")

    # --- salva golden ---
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    golden_path = GOLDEN_DIR / f"{dxf_path.stem}.json"

    golden = {
        "source_file": dxf_path.name,
        "part_count":  result.part_count,
        "parts":       [],
    }

    for part in result.parts:
        all_inners = sorted(part.holes + part.inners, key=lambda x: x.area, reverse=True)
        golden["parts"].append({
            "area_mm2":           round(part.area, 4),
            "holes_count":        len(all_inners),
            "outer_perimeter_mm": round(part.outer.polygon.exterior.length, 4),
            "inner_perimeter_mm": round(sum(i.polygon.exterior.length for i in all_inners), 4),
            "total_perimeter_mm": round(
                part.outer.polygon.exterior.length +
                sum(i.polygon.exterior.length for i in all_inners), 4
            ),
            "outer_wkt":     part.outer.polygon.wkt,
            "inners_wkt":    [i.polygon.wkt for i in all_inners],
            "outer_layer":   part.outer.layer,
            "inners_layers": [i.layer for i in all_inners],
            "custom":        dict(part.custom),
        })

    golden_path.write_text(
        json.dumps(golden, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Golden salvato : {golden_path}")


if __name__ == "__main__":
    main()