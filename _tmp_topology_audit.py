import io
import json
import tempfile
from collections import Counter
from contextlib import redirect_stdout
from pathlib import Path

import forge
from forge.adapters.dxf.layers import ROLE_TO_LAYER, LAYER_INNER

ROOT = Path(__file__).resolve().parent
EXAMPLES = ROOT / "tests" / "examples"

GOLDEN_DXF_DIR = EXAMPLES / "golden"
GOLDEN_JSON_DIR = GOLDEN_DXF_DIR / "json"
GOLDEN_CFG_DIR = EXAMPLES / "config"

SPLIT_PARENT_DIR = EXAMPLES / "golden_multipli"
SPLIT_GOLDEN_DIR = SPLIT_PARENT_DIR / "golden"
SPLIT_CFG_DIR = SPLIT_PARENT_DIR / "config"

DEFAULT_TOLERANCE = 0.5
GLOBAL_LABEL_MAP = {"MARK": "engrave", "Signature": "engrave"}


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_cfg(cfg_dir: Path, stem: str) -> dict:
    cfg_path = cfg_dir / f"{stem}.json"
    if cfg_path.exists():
        return _load_json(cfg_path)
    return {}


def _run_heal_on_dxf(dxf_path: Path, tolerance: float, label_map: dict):
    with redirect_stdout(io.StringIO()):
        _, msp = forge.load_dxf(
            str(dxf_path),
            upgrade=True,
            explode_inserts=True,
            flatten_z_flag=True,
        )
        result = forge.heal(msp, tolerance=tolerance, label_map=label_map)
        forge.detect(result)
        forge.inject(result)
    return result


def audit_golden_topology() -> list[dict]:
    mismatches = []
    for golden_path in sorted(GOLDEN_JSON_DIR.glob("*.json")):
        golden = _load_json(golden_path)
        dxf_path = GOLDEN_DXF_DIR / golden["source_file"]
        if not dxf_path.exists():
            continue

        cfg = _load_cfg(GOLDEN_CFG_DIR, dxf_path.stem)
        tolerance = cfg.get("tolerance", DEFAULT_TOLERANCE)
        label_map = {**GLOBAL_LABEL_MAP, **cfg.get("label_map", {})}

        result = _run_heal_on_dxf(dxf_path, tolerance, label_map)

        if result.part_count != golden["part_count"]:
            mismatches.append({
                "kind": "part_count",
                "case": golden_path.stem,
                "actual": result.part_count,
                "expected": golden["part_count"],
            })
            continue

        for idx, (part, expected) in enumerate(zip(result.parts, golden["parts"])):
            holes = sorted(part.holes, key=lambda x: x.area, reverse=True)
            inners = sorted(part.inners, key=lambda x: x.area, reverse=True)

            if len(holes) != expected["holes_count"]:
                mismatches.append({
                    "kind": "holes_count",
                    "case": golden_path.stem,
                    "part": idx,
                    "actual": len(holes),
                    "expected": expected["holes_count"],
                })

            if len(inners) != expected["inners_count"]:
                mismatches.append({
                    "kind": "inners_count",
                    "case": golden_path.stem,
                    "part": idx,
                    "actual": len(inners),
                    "expected": expected["inners_count"],
                })

    return mismatches


def _run_split_parent(parent_path: Path, tolerance: float):
    with tempfile.TemporaryDirectory(prefix=f"audit_split_{parent_path.stem}_") as tmp_dir:
        out_dir = Path(tmp_dir)
        with redirect_stdout(io.StringIO()):
            _, msp = forge.load_dxf(str(parent_path), explode_inserts=True)
            result = forge.heal(msp, tolerance=tolerance)
            if result.is_valid and result.parts:
                forge.detect(result)
                forge.write(msp, result)
                forge.split(
                    msp,
                    result,
                    output_folder=str(out_dir),
                    namer=lambda i, part: f"{part.label}_P{i + 1:03d}",
                )
        children = sorted(out_dir.glob("*.dxf"))
        return result, children


def audit_split_topology() -> list[dict]:
    mismatches = []
    cache = {}

    for golden_path in sorted(SPLIT_GOLDEN_DIR.glob("*.json")):
        golden = _load_json(golden_path)
        parent_path = SPLIT_PARENT_DIR / golden["parent_file"]
        if not parent_path.exists():
            continue

        cfg = _load_cfg(SPLIT_CFG_DIR, parent_path.stem)
        tolerance = cfg.get("tolerance", DEFAULT_TOLERANCE)
        cache_key = (str(parent_path.resolve()), float(tolerance))

        if cache_key not in cache:
            result, children = _run_split_parent(parent_path, tolerance)

            payload = []
            for part in result.parts if result.is_valid and result.parts else []:
                sorted_all_inners = sorted(part.holes + part.inners, key=lambda x: x.area, reverse=True)
                payload.append({
                    "holes_count": len(sorted_all_inners),
                    "inner_roles": [i.role for i in sorted_all_inners],
                })

            cache[cache_key] = {
                "parts": payload,
                "children_count": len(children),
            }

        cached = cache[cache_key]
        part_index = golden["part_index"]

        if part_index >= len(cached["parts"]):
            mismatches.append({
                "kind": "split_part_index_range",
                "case": golden_path.stem,
                "part_index": part_index,
                "parts": len(cached["parts"]),
            })
            continue

        if len(cached["parts"]) != cached["children_count"]:
            mismatches.append({
                "kind": "split_parts_vs_children",
                "case": golden_path.stem,
                "parts": len(cached["parts"]),
                "children": cached["children_count"],
            })

        actual = cached["parts"][part_index]

        if actual["holes_count"] != golden["holes_count"]:
            mismatches.append({
                "kind": "split_holes_count",
                "case": golden_path.stem,
                "actual": actual["holes_count"],
                "expected": golden["holes_count"],
            })

        if "inners_layers" in golden:
            actual_layers = [ROLE_TO_LAYER.get(role, LAYER_INNER) for role in actual["inner_roles"]]
            if Counter(actual_layers) != Counter(golden["inners_layers"]):
                mismatches.append({
                    "kind": "split_inners_layers",
                    "case": golden_path.stem,
                    "actual": Counter(actual_layers),
                    "expected": Counter(golden["inners_layers"]),
                })

    return mismatches


def normalize(mismatches: list[dict]) -> str:
    # stable comparison across runs
    return json.dumps(sorted(mismatches, key=lambda x: json.dumps(x, sort_keys=True)), sort_keys=True)


def main():
    run_results = []
    for run_idx in range(3):
        g = audit_golden_topology()
        s = audit_split_topology()
        run_results.append({"golden": g, "split": s})
        print(f"RUN {run_idx + 1}: golden_topology={len(g)} split_topology={len(s)}")

    stable_golden = len({normalize(r["golden"]) for r in run_results}) == 1
    stable_split = len({normalize(r["split"]) for r in run_results}) == 1

    print("FINAL stable_golden", stable_golden)
    print("FINAL stable_split", stable_split)
    print("FINAL golden_topology_mismatches", len(run_results[0]["golden"]))
    print("FINAL split_topology_mismatches", len(run_results[0]["split"]))
    print("FINAL golden_sample", run_results[0]["golden"][:8])
    print("FINAL split_sample", run_results[0]["split"][:8])


if __name__ == "__main__":
    main()
