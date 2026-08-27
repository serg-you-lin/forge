Piano completo — refactoring dxf-forge
Contratto finale dell'API pubblica
python
doc = forge.load_dxf("file.dxf")      # unico punto che tocca ezdxf
result = forge.heal(doc)               # core puro — zero DXF
result = forge.detect(result)          # classificazione — zero DXF
doc_out = forge.write(result)          # documento nuovo — zero source_ref
doc_out.saveas("output.dxf")

# split è write per ogni part
paths = forge.split(result, output_folder)

# futuro
doc = forge.load_svg("file.svg")       # stesso contratto, adapter diverso
Cosa è doc — il ForgeDocument

load_dxf() non restituisce un msp ezdxf. Restituisce un oggetto dominio:

python
@dataclass
class ForgeDocument:
    edges:       List[Edge]        # geometria parsata — input per heal()
    annotations: List[Annotation]  # testi, quote, leader — input per write()
    source_meta: dict              # $INSUNITS, $MEASUREMENT, ecc.
    source_path: str

edges e annotations sono dati puri — zero ezdxf dentro. L'adapter li produce e poi il riferimento al msp originale sparisce.

I passi in ordine

Passo 1 — ForgeDocument

Crea model/document.py con il dataclass sopra. Annotation è un dataclass semplice:

python
@dataclass
class Annotation:
    kind:     str                    # "TEXT" | "MTEXT" | "DIMENSION" | ...
    position: Tuple[float, float]    # punto rappresentativo
    data:     dict                   # tutto il necessario per riscriverla

Niente source_ref — data contiene il testo, la posizione, tutto quello che serve per ricreare l'entità nel documento di output.

Passo 2 — forge.load_dxf()

python
def load_dxf(path: str) -> ForgeDocument:
    doc = ezdxf.readfile(path)
    msp = doc.modelspace()
    edges       = DxfAdapter(msp).to_edges()
    annotations = DxfAnnotationExtractor(msp).extract()
    meta = {
        "$INSUNITS":   doc.header.get("$INSUNITS", 4),
        "$MEASUREMENT": doc.header.get("$MEASUREMENT", 1),
    }
    return ForgeDocument(edges=edges, annotations=annotations,
                         source_meta=meta, source_path=path)

Dopo questa funzione, ezdxf non viene mai più toccato fino a write().

Passo 3 — forge.heal() riceve ForgeDocument

python
def heal(doc: ForgeDocument) -> ForgeResult:
    # lavora su doc.edges — zero DXF
    ...

ForgeResult non cambia struttura — ma non porta più source_ref né _entities_in_loops_ids.

Passo 4 — elimina source_ref dal modello

Ora che heal() non vede più ezdxf, source_ref non ha motivo di esistere. Si elimina da:

Edge
ClosedShape, OpenShape
Feature e tutta la gerarchia
Hole, BendingLine, ForgeContour
ClassifiedEntity

Passo 5 — forge.write() riceve ForgeResult

python
def write(result: ForgeResult, source_doc: ForgeDocument = None) -> ezdxf.document:
    doc_out = ezdxf.new(dxfversion="R2010")
    if source_doc:
        doc_out.header["$INSUNITS"]    = source_doc.source_meta["$INSUNITS"]
        doc_out.header["$MEASUREMENT"] = source_doc.source_meta["$MEASUREMENT"]
    msp_out = doc_out.modelspace()
    _setup_layers(doc_out)

    for part in result.parts:
        write_segments(part.outer.segments, msp_out, LAYER_OUTER)
        for inner in part.inners:
            write_segments(inner.segments, msp_out, LAYER_INNER)
        for hole in part.holes:
            layer = _work_layer_for_hole(hole) or LAYER_HOLE
            write_segments(hole.segments, msp_out, layer)
        _write_bending_lines(msp_out, part)
        for eng in part.engrave_lines:
            write_segments(eng.segments, msp_out, LAYER_ENGRAVE)

    if source_doc and source_doc.annotations:
        _write_annotations(msp_out, result, source_doc.annotations)

    return doc_out

Passo 6 — forge.split() diventa banale

python
def split(result: ForgeResult, source_doc: ForgeDocument,
          output_folder: str, ...) -> list:
    for i, part in enumerate(result.parts):
        result_part = ForgeResult(parts=[part], ...)
        doc_out = write(result_part, source_doc)
        doc_out.saveas(path)

Passo 7 — aggiorna i test

I test di write smettono di controllare il msp originale — controllano il doc_out restituito. Questo è il passo che blocca tutto se non viene fatto prima di scrivere il codice.

Ordine di esecuzione
1. ForgeDocument          — model/document.py
2. DxfAnnotationExtractor — adapters/dxf/annotation_extractor.py
3. forge.load_dxf()       — forge/__init__.py o pipeline/load.py
4. forge.heal() aggiornato — pipeline/heal.py
5. elimina source_ref     — modello e bridge
6. forge.write() riscritto — pipeline/write.py
7. forge.split() riscritto — pipeline/write.py
8. aggiorna i test        — tutti i test di write e split
Cosa NON cambia
DxfAdapter.to_edges() — già produce Edge puri
hierarchy.py — già lavoro su ClosedShape puri
detect() — non tocca DXF
exporter.py — già lavora su segmenti puri
Il modello domain interno — fino al passo 5
Il futuro load_svg
python
def load_svg(path: str) -> ForgeDocument:
    edges       = SvgAdapter(path).to_edges()
    annotations = []   # SVG non ha annotazioni DXF
    meta        = {}
    return ForgeDocument(edges=edges, annotations=annotations,
                         source_meta=meta, source_path=path)

Stesso contratto — heal(), detect(), write() non cambiano una riga.

---

# STATO DEL REFACTOR — aggiornato 2026-08-27

Branch: `refactor/structure`. Modifiche **non committate** (i commit li fa Federico).

## Fatto e verificato

- **Passo 1** — `forge/model/document.py`: `ForgeDocument` (edges, annotations, source_meta, source_path) + `Annotation` (kind, position, data). Esportati da `forge/model/__init__.py` e `forge/__init__.py`.
- **Passo 2** — `forge/adapters/dxf/annotation_extractor.py`: `DxfAnnotationExtractor(msp).extract() -> List[Annotation]`.
- **Passo 3** — `forge/adapters/dxf/loader.py`: `load_dxf(...) -> ForgeDocument` (non più `(doc, msp)`). Aggiunto `document_from_msp(msp, ...)` per test / geometria generata a mano.
- **Passo 4** — `forge/pipeline/heal.py`: `HealStep(doc: ForgeDocument, ...)`, lavora su `doc.edges`, zero ezdxf. `forge.heal(doc)` valida il tipo e prende `tolerance` da `doc.source_meta`.
- **Passo 6** — `forge/pipeline/write.py`: `write(result, source_doc=None) -> doc_out` (documento ezdxf nuovo, mai il msp sorgente). `$INSUNITS`/`$MEASUREMENT` da `source_meta`. `_write_annotations()` filtra per part scritte.
- **Passo 7** — `write.py`: `split(result, source_doc=None, output_folder=..., ...)` — un `write()` per part. `forge/pipeline/__init__.py`: `heal()`, `split_to_files()` sul nuovo contratto.
- **Gap healing puro** — `forge/core/healing/gap_solver.py`: `free_endpoints_from_edges(edges, graph)` e `apply_gap_fixes(edges, fixes, node_decimals) -> List[Edge]` sostituiscono i metodi DXF-based dell'adapter. `compute_gap_fixes` invariato. Rimossi da `adapter.py`: `extract_free_endpoints`, `apply_gap_fixes`, `to_circular_arcs`, `load_entity_lists`, `_gap_meta_for`, `_GAP_KIND_MAP`.
- **Regressione bending risolta** — `Edge.closed_path: bool` (nuovo campo). `to_edges()` lo mette a True per i segmenti esplosi da LWPOLYLINE/POLYLINE chiuse; `BendingDetector` scarta questi edge dai candidati piega (era la guardia `_is_closed_polyline_ref(source_ref)` persa col Passo 4).
- Helper: `forge/core/geometry.py::node_decimals_for(tol)`, `forge/core/primitives/segments.py::segment_endpoints(seg)`.

Verifica: `tests/real/test_golden.py` **48/48**, `tests/real/test_golden_split.py` **51/51**.
Suite completa: **217 passed / 208 failed / 16 errors** (i fail sono quasi tutti Passo 8, sotto).

## Passo 5 — source_ref: quasi fatto

Rimosso da: `Edge`, `ClosedShape`/`OpenShape`, `Feature` e gerarchia, `Hole`, `BendingLine`,
`ForgeContour`, `ClassifiedEntity`, `loop_finder.edges_to_open_shapes`.

**Ancora da togliere** (`grep -rn source_ref forge/`):
- `forge/adapters/pdf/graph_adapter.py` — 3 costruzioni `Edge(source_ref=...)` → rompe l'import dell'adapter PDF
- `forge/io/text_utils.py:35` — `ForgeText(source_ref=e)`
- `forge/model/text.py:20` — campo `source_ref: Optional[Any]`
- commenti stantii: `loop_finder.py:162`, `feature.py:17`

## Passo 8 — migrazione test: DA FARE (sessione dedicata)

Traduzione meccanica vecchia API → nuova:
- `heal(msp, ...)` / `heal(msp, label_map=...)` → `heal(forge.document_from_msp(msp, label_map=...), ...)` oppure via `load_dxf`
- `doc, msp = load_dxf(...)` → `doc = load_dxf(...)`
- `write(msp, result)` → `doc_out = write(result, doc)`
- `split(msp, result, folder)` → `split(result, doc, folder)`
- test che ispezionano `msp` dopo il write → ispezionare `doc_out.modelspace()`

File da migrare: `tests/unit/test_healer.py`, `tests/integration/test_gap.py`,
`tests/integration/test_splitter.py`, `tests/integration/test_injector.py`,
`tests/integration/test_special_layers.py`, `tests/integration/test_pipeline.py`,
`tests/real/test_layers.py`, `tests/unit/test_detect.py`, `tests/real/test_edge_cases.py`.

Da **riscrivere** (non migrare): `tests/integration/test_writeback.py` — testa "scrivi nel msp
sorgente / entità su layer Trash", comportamento che non esiste più.

Già rossi **prima** del refactor (vecchia API modello, non causati da noi):
`tests/unit/test_models.py`, `tests/unit/adapters/test_parsing_and_exporting.py`,
`tests/unit/core/test_hierarchy_builder.py`.

Script root da aggiornare al nuovo contratto: `01_run_healer_interpreter.py` … `20_*.py`,
`tests/generate_golden.py`, `tests/generate_golden_split.py`.

## Fatto: già migrati

`tests/integration/test_helpers.py`, `tests/real/test_golden.py`, `tests/real/test_golden_split.py`.