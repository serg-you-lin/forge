"""
run_healer_batch.py
-------------------

Heal all DXF files in a folder using the current Forge API.

Skips files whose name ends with "_healed.dxf".
"""

from pathlib import Path

import forge


# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------

input_dir = Path(
    r"C:\Users\FEDERICO\Documents\Python_Scripts\Projects\GitHub\dxf-forge\tests\examples"
).resolve()

tolerance = 0.2

special_layers = {
    "MARK": "engrave",
    "Signature": "engrave",
    "Filettati": "threaded_hole",
    "Svasati": "countersink",
    "Piega": "bending",
}


# ---------------------------------------------------------------------------
# BATCH
# ---------------------------------------------------------------------------

dxf_files = sorted(
    path
    for path in input_dir.glob("*.dxf")
    if path.is_file() and not path.stem.endswith("_healed")
)

if not dxf_files:
    print("No DXF files found.")
    raise SystemExit(0)


failed = []

for input_dxf in dxf_files:
    base_name = input_dxf.stem

    output_dxf = input_dxf.parent / f"{base_name}_healed.dxf"
    output_json = input_dxf.parent / f"{base_name}_healed.json"

    try:
        doc = forge.load_dxf(
            str(input_dxf),
            explode_inserts=True,
            flatten_z_flag=True,
            label_map=special_layers,
            verbose=False,
        )

        result = forge.heal(
            doc,
            tolerance=tolerance,
            label=base_name,
            source_file=input_dxf.name,
        )

        forge.detect(
            result,
            bending_tolerance=0.2,
        )

        doc_out = forge.to_dxf(result, doc)

        forge.inject(result)

        forge.save_json(result, str(output_json))

        if not result.is_valid:
            failed.append((input_dxf.name, "invalid result"))
            continue

        doc_out.saveas(str(output_dxf))

        print(f"OK  {input_dxf.name} -> {output_dxf.name}")

    except Exception as exc:
        failed.append((input_dxf.name, str(exc)))


# ---------------------------------------------------------------------------
# SUMMARY
# ---------------------------------------------------------------------------

print(f"\nProcessed: {len(dxf_files)}")
print(f"Failed:    {len(failed)}")

if failed:
    print("\nFailures:")
    for filename, error in failed:
        print(f"  {filename}: {error}")