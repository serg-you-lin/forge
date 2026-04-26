# dxf-forge

DXF geometry preprocessor for manufacturing pipelines.

Prepares raw DXF files — from CAD software, clients, or CAM machines — into clean,
structured data ready for downstream tools like nesting, quoting, or fabrication workflows.

---

## What it does

- **Heals** broken geometry: reconnects scattered `LINE` and `ARC` entities into closed `LWPOLYLINE` contours
- **Splits** multi-part DXF files into individual part files, one per piece
- **Classifies** contours: outer profiles, inner cutouts, holes
- **Exports** structured metadata: area, perimeter, bounding box, hole count — as Python objects, JSON, or XML
- **Validates** geometry before processing: detects open contours, ambiguous nodes, missing structure

---

## Philosophy

`dxf-forge` never opens or saves files by itself.  
It works on `msp` (modelspace) objects already loaded by the caller.  
The caller decides when to open, when to save, when to close.

```python
import ezdxf
import dxf_forge as forge

doc = ezdxf.readfile("part.dxf")
msp = doc.modelspace()

result = forge.heal(msp, tolerance=0.5, write_to_msp=True)
print(f"Parts found: {result.part_count}")

doc.saveas("part_healed.dxf")
```

---

## Core API

### `heal(msp)`
Repairs geometry and classifies contours.  
Handles `LINE`/`ARC` soup, existing `LWPOLYLINE`, `CIRCLE`, closed `SPLINE`, `ELLIPSE`.  
Returns a `ForgeResult` with one `ForgePart` per closed outer contour found.

### `split_to_files(msp, output_folder)`
Splits a multi-part file into N child DXF files, one per part.  
Copies inner contours and extra entities (marks, text, annotations) into the correct child file.

```python
result = forge.split_to_files(
    msp,
    output_folder="output/",
    label="part_code",
    source_file="multi.dxf",
)
```

### `is_multi(result)`
Returns `True` if the file contains more than one part.

```python
result = forge.heal(msp, write_to_msp=True)
if forge.is_multi(result):
    forge.split_to_files(msp, output_folder="output/", heal_result=result)
else:
    forge.write_metadata_to_dxf(doc, result.parts[0])
    doc.saveas("output/part.dxf")
```

### Metadata
Geometric metadata is written as XDATA into the DXF and can be exported to JSON or XML.

```python
forge.write_metadata_to_dxf(doc, part)
forge.save_json(result, "metadata.json")
forge.save_xml(result, "metadata.xml")
```

---

## Structural layers

| Layer | Meaning |
|---|---|
| `OuterContour` | Outer profile of the part |
| `InnerContour` | Internal opening (slot, pocket) |
| `Hole` | Circular hole (diameter < 32.1 mm) |
| `Trash` | Unclassified entities |

---

## Supported geometry

As structural contours: `LWPOLYLINE`, `CIRCLE`, closed `SPLINE`, `ELLIPSE`  
As raw geometry to reconstruct: `LINE`, `ARC`, open `SPLINE` connected to other entities

---

## Dependencies

```
ezdxf
shapely
numpy
```

---

## Structure

```
dxf_forge/
  healer.py      — geometry repair, core of the library
  splitter.py    — multi-part file splitting
  geometry.py    — pure geometric functions
  graph.py       — topological graph for closed loop detection
  virtual.py     — in-memory loop representation
  classifier.py  — extra entity classification by layer/color
  exporter.py    — JSON / XML / XDATA serialization
  validator.py   — pre-healing validation
  models.py      — ForgeResult, ForgePart, ForgeContour
  layers.py      — single source of truth for layer names and colors
```

---

## Notes

Experimental project. Built to handle real-world DXF files from CAM machines in a laser/plasma cutting context.  
Not a general-purpose DXF library — it solves a specific problem in a specific domain.