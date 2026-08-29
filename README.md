# forge

**2D geometry preprocessor for sheet/plate manufacturing.**

`forge` takes a messy 2D drawing — scattered `LINE`/`ARC` soup exported by a CAM
machine, a client's DXF, a legacy R12 file — and turns it into a clean, structured
model: closed part profiles, inner cutouts, holes (plain / countersink / threaded),
bend lines, engraving traces. That model can then be rendered back to DXF (one file
per part), exported as JSON/XML metadata, or fed to nesting.

The distinctive part is the **healing**: reconnecting broken geometry into closed
contours. No other DXF library does that for you.

> Status: **alpha**. Used in production for laser/plasma cutting prep, but the API
> still moves. See `MAP.md` for the current design decisions.

---

## Install

```bash
pip install -e .            # from a clone
pip install -e ".[pdf]"     # + experimental PDF input
```

Dependencies: `ezdxf`, `shapely`, `numpy` (Python ≥ 3.10).

---

## Quick start — one file

```python
import forge

doc    = forge.load_dxf("part.dxf", tolerance=0.5)   # -> ForgeDocument
result = forge.heal_and_detect(doc)                  # topology + holes/bends/engraving
#   == forge.heal(doc) then forge.detect(result, "all"); call them separately if
#      you only need the topology. Bare forge.detect(result) does not classify
#      holes — pass features ("holes" / "bending" / "engrave" / "all").

if not result.is_valid:
    raise SystemExit(result.errors)

doc_out = forge.to_dxf(result, doc)                  # -> ezdxf Drawing
doc_out.saveas("part_healed.dxf")

forge.save_json(result, "part.json")                 # metadata
print(f"{result.part_count} part(s), "
      f"{sum(len(p.holes) for p in result.parts)} holes")
```

## Multi-part file

```python
import forge

doc    = forge.load_dxf("batch.dxf")
result = forge.split_to_files(doc, "output/", label="batch")
# writes output/batch_P1.dxf, output/batch_P2.dxf, ... one per piece
# (pass namer=lambda i, part: "..." to control the file names)
forge.save_json(result, "batch.json")
```

## Bend / engrave layers you already know

If the source file marks bend lines or engraving on named layers, tell `load_dxf`
so it assigns the role up front instead of guessing:

```python
doc = forge.load_dxf("part.dxf", label_map={"Piega": "bending", "MARK": "engrave"})
```

---

## The pipeline

```
load_dxf(path)  ──►  ForgeDocument   (edges + annotations + source_meta)
                          │            the only step that touches ezdxf for reading
                          ▼
     heal(doc)  ──►  ForgeResult      topology: gaps closed, loops found,
                          │            outer / inner containment tree (no holes yet)
                          ▼
  detect(result, "all")               semantics: hole type, bend lines, engraving
                          │            (mutates result in place, returns it)
                          │            heal + detect together: heal_and_detect(doc)
                          ▼
   to_dxf(result, doc)  ──►  ezdxf Drawing        render — one document
   split(result, doc)   ──►  list[Drawing]        render — one per part
   save_json / save_xml / to_nester_input         export the model
   inject(result, ...)                            optional CAM enrichment from texts
```

The model is the product. `to_dxf` never re-reads the source file — every renderer
draws from the model, so a future `to_svg` produces the same picture.

---

## Output DXF layers

| Layer          | Meaning                                    |
|----------------|--------------------------------------------|
| `OuterContour` | outer profile of the part                  |
| `InnerContour` | internal opening (slot, pocket)            |
| `Hole`         | plain circular hole                        |
| `Countersink`  | countersunk hole                           |
| `ThreadHole`   | threaded / tapped hole                     |
| `Bending`      | bend line                                  |
| `Engrave`      | engraving / marking trace                  |
| `Marking`      | other marking geometry                     |
| `Annotation`   | source texts and dimensions (not a cut layer) |
| `Trash`        | everything `forge` could not classify — kept, never dropped |

Nothing from the source is silently lost: unclassified geometry goes to `Trash`,
texts and dimensions to `Annotation`. Entity types `forge` does not model (`HATCH`,
`IMAGE`, `TABLE`, …) are reported as a warning by `load_dxf`, not dropped in silence.

---

## Inspecting a real file

Three levels, matching the pipeline:

```python
import forge

forge.inspect_dxf("part.dxf")        # 1 — raw DXF entities: what's in the file
forge.inspect_document(doc)          # 2 — edges, primitives, node graph: what the adapter understood
forge.inspect_result(result)         # 3 — the model: parts, typed holes, bends, engraving, trash

forge.inspect_file("part.dxf", label_map={"Piega": "bending"})   # all three, in order
```

Everything prints to stdout. Use it when something on a real file doesn't come out
right and you need to see where in the chain it breaks.

---

## Supported input geometry

- **As structural contours:** `LWPOLYLINE`, `POLYLINE`, `CIRCLE`, closed `SPLINE`
- **To reconstruct into contours:** `LINE`, `ARC`, open `SPLINE` connected to other entities
- **As annotations:** `TEXT`, `MTEXT`, `DIMENSION`, `LEADER`, `MULTILEADER`
- **Blocks:** `INSERT` is exploded on load by default
- **Legacy:** R12/R13/R14 files are upgraded to R2010
- **DWG:** neither `forge` nor `ezdxf` reads DWG natively — it goes through
  [ODA File Converter](https://www.opendesign.com/guestfiles/oda_file_converter)
  (free). Install it and point `forge` at the executable via the `ODA_PATH`
  environment variable (full path to the `.exe`), or put `ODAFileConverter` on
  your `PATH`. See `docs/API.md` → *load_dxf → DWG* for per-OS setup.

---

## Known limits

- **Splines** are re-emitted natively on cut layers but **discretized** in the
  planned SVG output.
- **`load_pdf`** exists but is experimental — it returns raw edges, not a
  `ForgeDocument`, so it does not plug into `heal()` yet. Not in the public API.
- **Geometric engraving inference** (`detect` finding engraving without a
  `label_map`) is a planned no-op placeholder.
- **`arc/arc` gaps beyond tolerance** are not auto-closed — raise `tolerance`.
- If no closed outer contour can be formed, `result.is_valid` is `False` and
  `to_dxf` / `split` raise `ValueError` rather than emit a file of only trash.

---

## Full API reference

See [`docs/API.md`](docs/API.md). Architecture and rationale: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).
