# forge

**Deterministic 2D-geometry engine for technical drawings and CAD geometry.**

`forge` turns a messy 2D drawing into a clean, lossless model — healed closed
contours, their containment hierarchy, the drawing's annotations, and an open
overlay where detected features are attached — then renders it to DXF (one
document, or one per part), JSON/XML, SVG, a view model for a UI, or (experimental) a compact text reading for
a language model. The model is the product; a CAD format is
only a door in or out of it. Today that door is DXF (DWG via ODA), handled by a
single adapter — everything downstream works on the format-neutral model.

The distinctive part is the **healing**: reconnecting broken geometry — `LINE`/`ARC`
soup from a CAM export, a client's DXF, a legacy R12 file — into closed contours.
No other tool does that for you.

It is **not a DXF library** and **not a sheet-metal tool**. Sheet and plate
manufacturing is where forge grew up and still its first consumer, not its
boundary: the engine knows no material, process or product. Reading geometry as
"a hole to drill" or "a bend" is the consumer's interpretation (`snapbend` for
sheet metal, `snapdraw` for drawing notation) — forge has no reading of that
kind built in, so a consumer in any domain gets the same geometry and puts its
own vocabulary on top through one open overlay (`cluster.detected`).

> Status: **alpha**. Used in production, but the API still moves. See `MAP.md` for the current design decisions.

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
result = forge.heal(doc)                             # topology: closed contours, outer/inner
#   holes, bends, engraving are a process reading on top: snapbend.flat.detect_flat

if not result.is_valid:                             # no closed outer contour
    print(result.errors)                             # still renderable, see "Known limits"

doc_out = forge.to_dxf(result, doc)                  # -> ezdxf Drawing
doc_out.saveas("part_healed.dxf")

forge.save_json(result, "part.json")                 # metadata
circles = [c for cl in result.clusters for c in cl.inners
           if forge.geometry.contour_shape(c).kind == "circle"]
print(f"{result.cluster_count} cluster(s), {len(circles)} inner circles")
```

## Multi-part file

```python
import forge

doc    = forge.load_dxf("batch.dxf")
result = forge.split_to_files(doc, "output/", label="batch")
# writes output/batch_P1.dxf, output/batch_P2.dxf, ... one per piece
# (pass namer=lambda i, cluster: "..." to control the file names)
forge.save_json(result, "batch.json")
```

## A drawing of views (several views, isometric)

```python
import forge

doc    = forge.load_dxf("sheet.dxf")        # frame / title block marked by role, or removed
result = forge.island(doc, island_gap=10.0)
for cluster in result.clusters:              # one view (or part) per island
    print(cluster.outer.polygon.area, len(cluster.inners))
```

`heal()` reads a drawing of separate flat outlines from the inside (which loops close, which is
inside which). `island()` reads a drawing of views from the outside: islands
by proximity, then the outer contour of each as the outer face of its planar
network. Same `ForgeResult` out — see `docs/API.md` (`island`).

Both are recipes over public steps. `heal()`'s steps (`split_labeled`,
`close_free_gaps`, `find_loops`, `build_hierarchy`, ...) are exported one by one,
so a consumer can compose its own order — see `docs/API.md` (the steps of `heal()`).

## Drawing with forge

```python
import forge

fg = forge.geometry
doc = forge.load_segments(fg.rectangle(200, 100) + fg.rectangle(100, 50))
result = forge.heal(doc)                # one part: outer 200×100, one inner 100×50
forge.to_dxf(result, doc).saveas("two_rectangles.dxf")
```

Builders return forge segments: `polygon(points)`, `rectangle`, `regular_polygon`,
`circle`, `stadium` (with true arcs). Any other straight-sided shape is a `polygon`.

## Shapes: what a contour is, not what it is for

forge names geometry, never its use. A circle is a circle; whether it is a
drilled hole, a seat or a logo dot is a consumer's reading (snapbend for the
part, snapdraw for the drawing notation — D68, D91).

```python
for cluster in result.clusters:
    for inner in cluster.inners:
        shape = forge.geometry.contour_shape(inner)     # circle / stadium / rectangle / polygon / other
        print(shape.kind, shape.center, shape.length, shape.width)

    # circles sharing a center, smallest first (singletons included)
    for group in forge.geometry.concentric_groups(cluster.inners, tolerance=0.1):
        if len(group.items) > 1:
            print("concentric:", group.center, group.diameters)

# arcs concentric to a circle and larger: sweep in degrees, radius ratio
for found in forge.geometry.arcs_around((10, 20), 2.5, result.all_arcs, tolerance=0.1):
    print(found.sweep, found.radius_ratio)
```

No thresholds of meaning inside: "~270° and a bit larger" is how a drawing
shows a thread, and that rule lives in the consumer.

## Bend / engrave lines you already know how to recognize

If you know how the source marks bend lines or engraving — by name, by dash,
by colour, or a combination — tell `load_dxf` with rules, so it assigns the
role up front instead of guessing. Rules are checked in order, the first
match wins:

```python
doc = forge.load_dxf("part.dxf", role_rules=[
    *forge.name_rules({"Piega": "bending", "MARK": "engrave"}),
    forge.RoleRule("construction", name_contains="constr", dashed=True),
    forge.RoleRule("bending", dashed=True),
])
```

---

## The pipeline

```
load_dxf(path)  ──►  ForgeDocument   (edges + annotations + source_meta)
                          │            the only step that touches ezdxf for reading
                          ▼
     heal(doc)  ──►  ForgeResult      topology: gaps closed, loops found,
                          │            outer / inner containment tree
                          ▼
  (a consumer's reading)               e.g. snapbend: hole type, bend lines, engraving,
                          │            attached to cluster.detected
                          ▼
   to_dxf(result, doc)  ──►  ezdxf Drawing        render — one document
   split(result, doc)   ──►  list[Drawing]        render — one per part
   to_svg(result)       ──►  SVG string           render — for a UI / report
   to_view_model(result)  ─►  dict (full geometry) for an external renderer
   to_text(result)      ──►  Markdown              experimental: a reading for a language model (D84)
   save_json / save_xml                           export the model (metadata)
   inject(result, ...)                            optional enrichment from texts
```

The model is the product. `to_dxf` never re-reads the source file — every renderer
(DXF, SVG, the view model) draws from the same model, so they all show the same picture.

---

## Output DXF layers

| Layer          | Meaning                                    |
|----------------|--------------------------------------------|
| `OuterContour` | outer profile of the part                  |
| `InnerContour` | closed contour inside the outer             |
| `Annotation`   | source texts and dimensions (not a cut layer) |
| *role name*    | geometry with a consumer's role (`frame`, `hole`, `bending`, …): its own layer, named and coloured by `register_role_style` if the consumer registered one |
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
forge.inspect_result(result)         # 3 — the model: clusters, outer/inner, whatever a consumer attached, trash

forge.inspect_file("part.dxf", role_rules=forge.name_rules({"Piega": "bending"}))   # all three, in order
```

Everything prints to stdout. Use it when something on a real file doesn't come out
right and you need to see where in the chain it breaks.

---

## Supported input geometry

- **As structural contours:** `LWPOLYLINE`, `POLYLINE`, `CIRCLE`, closed `SPLINE`, closed `ELLIPSE`
- **To reconstruct into contours:** `LINE`, `ARC`, open `SPLINE`/`ELLIPSE` connected to other entities
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

- **Splines and ellipses** are re-emitted natively on cut layers (`to_dxf`) but
  **discretized** in `to_svg` / `to_view_model` (polylines: use `to_dxf` when
  the exact curve matters).
- **`load_pdf`** exists but is experimental — it returns raw edges, not a
  `ForgeDocument`, so it does not plug into `heal()` yet. Not in the public API.
- **`arc/arc` gaps beyond tolerance** are not auto-closed — raise `tolerance`.
- If no closed outer contour can be formed, `result.is_valid` is `False`.
  `to_dxf` / `to_svg` still render what is there (everything on `Trash`), so
  you can see what forge understood; a caller feeding a machine passes
  `allow_invalid=False` and gets `ValueError` instead. `split` always raises:
  one file per part means nothing without parts.

---

## Documentation

- **[`docs/API.md`](docs/API.md)** — every public function: signature, what it
  takes, returns, mutates, when it raises. With copyable examples (in Italian).
- **[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)** — how it is built and why:
  the layers, the flow, "the model is the product".
- **`MAP.md`** — the design decisions, in chronological order.
- **[`docs/LLM.md`](docs/LLM.md)** — a dense, token-minimal reference for an AI
  agent writing code against forge: same ground as `API.md`.
- **`SCRIPTS.md`** — the numbered scripts in `scripts/`, one per stage of the pipeline.

---

## License

All rights reserved — see [`LICENSE`](LICENSE). Copyright (c) 2026 Federico
Sidraschi. This is not open source; if you'd like to try or use it, get in
touch: smia4punto6@gmail.com.
