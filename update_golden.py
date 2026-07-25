import json
from pathlib import Path

golden_dir = Path(r"C:\Users\FEDERICO\Documents\Python_Scripts\Projects\GitHub\dxf-forge\tests\examples\golden\json")  # aggiusta il path

for f in golden_dir.glob("*.json"):
    text = f.read_text(encoding="utf-8")
    text = text.replace('"layer":', '"origin":')
    text = text.replace('"special_layers"', '"labeled"')
    f.write_text(text, encoding="utf-8")

print("done")