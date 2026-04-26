from pathlib import Path
import ezdxf
import dxf_forge as forge

folder = Path("tests/examples")
total_cut = 0.0
count = 0

for f in folder.glob("*"):
    if not (f.is_file() and f.suffix.lower() == ".dxf"):
        continue
    if not f.stem.endswith("_healed"):
        continue

    doc = ezdxf.readfile(f)
    meta = forge.read_metadata_from_dxf(doc)

    if meta:
        perimeter = meta.get("total_perimeter_mm", 0.0)
        total_cut += perimeter
        count += 1
        print(f"{f.name}: {perimeter} mm")
        quantity = meta.get("quantity", 0)
        print(f"Quantità: {quantity}")

print(f"\nFile con metadati: {count}")
print(f"Lunghezza taglio totale: {total_cut:.1f} mm")