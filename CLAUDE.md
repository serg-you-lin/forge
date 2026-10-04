# forge — working agreement

Deterministic 2D-geometry engine for technical drawings and CAD geometry.
Input adapters (DXF today; PDF frozen/experimental; raw primitives) → a lossless
domain model (healed closed contours, containment hierarchy, annotations, an open
overlay for detected features) → renderers (DXF / JSON / XML / SVG / view-model).

It is **not** a DXF library, and **not** a sheet-metal tool. Sheet/plate
manufacturing is where forge came from and still its first consumer, not its
boundary: the engine knows no process, no material and no product. Anything that
reads geometry as "a hole to drill", "a bend", "a dimension that means a thread"
is the consumer's interpretation (`snapbend` for sheet metal, `snapdraw` for
drawing notation), not forge's.

Python 3.11 · version in `pyproject.toml` (single source of truth) · `import forge`.
Talk to Federico in Italian; everything written in the repo is English (except
docstrings/comments, see Conventions).

## Read before you write

| situation | read |
|---|---|
| calling the library, need a signature or the pipeline | `docs/LLM.md` — dense reference written for an LLM, **load this one first** |
| need the full card for a public name | `docs/API.md` |
| **about to add a function, helper or class** | `docs/INDEX.md` — every module-level name in the package with `file:line`. Check the name *and* the job exist nowhere before writing |
| **writing geometry** (a measure, a fact between contours, lines, rectangles) | it goes in `forge/core/geometry/` and its public facts in `forge.geometry` (`__init__.py` is the map) — never as a private helper in a reading or in a consumer (D93-D95) |
| why is it built this way | `docs/ARCHITECTURE.md` |
| why was X decided | `MAP.md` — decision log `D1…Dn`. Grep for the topic. **A closed decision is not re-decided**; to reopen it, say "reopening D##" out loud |
| what's missing / planned | `TODO.md`, `ROADMAP.md` |
| running something end to end | `scripts/NN_*.py` (first line `import _paths`), listed in `SCRIPTS.md` |
| tests, fixtures, goldens | `tests/`, plus the `python-testing-style` skill |

`docs/INDEX.md` is **generated**. Never edit it by hand:

```
python scripts/gen_index.py            # regenerate after adding/moving code
python scripts/gen_index.py --check    # exit 1 if stale or the dependency rule is broken
```

`tests/unit/test_index.py` runs the check in the suite. The rule is in
`pyproject.toml` (`[tool.gen_index.layers]`); the script is the same file as
snapbend's `tests/gen_index.py` — change it in one, copy to the other.

## Non-negotiables

1. **Reason in forge's own primitives.** `Edge`, `LineSeg`/`ArcSeg`/`SplineSeg`/
   `CircleSeg`/`EllipseSeg`, `role`/`ContourRole`, `closed_path`. A source-format
   detail — which DXF layer something sits on, `LINE` vs `LWPOLYLINE`, how the CAD
   author grouped entities — is a fact about how *one file* was authored, never
   domain truth. Test before writing any rule: would it still make sense if the
   same geometry arrived from a PDF or SVG adapter with no layers at all? If not,
   translate it into a real domain concept or drop it.
2. **Build test fixtures with forge's own API** (`forge.load_dxf`, `Edge`,
   `LineSeg`, …), never with `ezdxf` directly. forge exists so that is unnecessary.
3. **Dependency rule:** `core` and `model` never import `adapters`, `tools` or `io`
   (MAP.md D44). `model` may annotate a `tools` type only under `TYPE_CHECKING`.
4. **forge knows no process.** The `hole`/`bending`/`engrave` vocabulary and
   `detect_flat()` live in snapbend (`snapbend.flat`, D88). forge reads
   structure (what closes, what lies inside what, what is connected); meaning
   (hole, bend, view, dimension) is a consumer's, written to `cluster.detected`
   and rendered by role (D90).
5. **snapbend's `detect_flat()` assumes a flat part seen from its face** (cutting
   file / development). Never run it on `island()` output: it invents bends in isometrics
   and holes in logo letters. `heal()` and `island()` are two *readings*, never two
   steps — never chain them on one document.
6. **Always check `result.is_valid`** before handing output to a machine.
   `to_dxf`/`to_svg` render an invalid result anyway (`allow_invalid=True`, so
   you can see it); a caller that delivers to a machine passes
   `allow_invalid=False`. `split` always raises on invalid (D83).
7. **Nothing is silently dropped**: unclassified geometry goes to `trash_entities`,
   unmodeled source types to `doc.warnings`.
8. **Justify every choice from forge's own geometry and domain model.** "That is
   what other CAD software does" / "it's the convention" is not an argument here —
   forge exists precisely so it does not have to inherit anyone else's conventions.
   State the geometric or mathematical reason directly.
9. **Never regenerate a golden to make a test pass** without first proving the code
   is right.
10. **No client data in git.** Drawings under `tests/examples/` are anonymized by
    Federico before they enter the repo. Never commit or push an original client
    drawing, a client name, an original file name or part code, or any line that
    maps an anonymized fixture back to its origin — not in code, docs, MAP.md or
    commit messages. A full audit of what may live in git is due before 1.0.0.

## How to work

- **A concrete failing file is a symptom, not the target.** The deliverable is the
  general mechanism behind it, fixed. Never tune a change so that one example comes
  out right.
- **Geometric results are judged by eye.** When an experiment produces geometry
  Federico has to assess, give him DXF files he can open — not only numbers, not a
  matplotlib PNG.
- **A decision made is a decision written.** Append it to `MAP.md` with the next
  `D##`, with the *why*. Docstrings stay short; the reasoning and history go in
  `MAP.md`, not in the function.
- **A large file is filtered, not read**: to find something inside a big file
  (a drawing, a log, a golden) run a filter (`grep`, `anonymize scan`, a small
  parser) and read its output only.
- Refactors are clean breaks: no compatibility aliases kept "just in case".

## Conventions

Identifiers, function and class names in English; docstrings and comments in
Italian. Every module docstring opens with the file's path. Type hints everywhere.
Dataclasses for the domain; results are queryable typed objects, not loose dicts.
Format reading is isolated in `adapters/`, everything downstream is pure. No
shebang lines. `README.md` in English with `README_IT.md` as its Italian twin.
