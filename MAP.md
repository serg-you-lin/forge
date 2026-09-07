# MAP.md — decision log di dxf-forge

Questo file è la **memoria delle decisioni**: cosa è stato deciso, e soprattutto
*perché*. Non è documentazione (quella è in `docs/`) e non è un log di sessione
(quello è il git log).

Regola: una decisione chiusa **non si re-decide da capo**. Se va rimessa in
discussione si dice esplicitamente "stiamo riaprendo la decisione N".

- **Cos'è forge, come si usa** → `README.md`, `docs/API.md`
- **Com'è fatto dentro** → `docs/ARCHITECTURE.md`
- **Storia del refactor** → git log (branch `refactor/structure`)

---

## Il contratto dell'API pubblica

```python
doc    = forge.load_dxf("file.dxf")        # unico punto che tocca ezdxf in lettura
result = forge.heal(doc)                   # topologia — zero DXF
result = forge.detect(result, "all")       # semantica/feature — zero DXF
doc_out = forge.to_dxf(result, doc)        # documento nuovo — nessun source_ref
doc_out.saveas("output.dxf")

# multi-pezzo
forge.split_to_files(doc, "output/")       # unica funzione che scrive su disco

# futuro: stesso contratto, adapter diverso
doc = forge.load_svg("file.svg")
```

**Principio portante:** `load_*` produce un `ForgeDocument` di dati puri (edge +
annotation). Dopo il load, il documento `ezdxf` sorgente sparisce. `heal` /
`detect` non vedono mai un formato. `to_dxf` costruisce un documento **nuovo** dai
segmenti del modello — non copia entità dalla sorgente, non porta `source_ref`.
Il modello è il prodotto; il DXF è solo una delle sue rappresentazioni.

Dettaglio completo di ogni funzione in `docs/API.md`.

---

## Stato

Branch: `refactor/structure`. Fasi 1–4 concluse e committate. Suite: **555 passed
/ 0 failed** (+ 62 subtests), golden verdi.

Da fare, in ordine:
1. ✅ Riscrittura degli script numerati alla radice (`00_*.py … 12_*.py`), uno
   per area di `forge.__all__`, default su `tests/examples/` (D14).
2. ✅ `to_view_model` + `to_svg` / `save_svg` (D12).
3. `detect_engrave` (D13) — quando Federico decide.
4. `forge/io/text_utils.py`: da riordinare (2026-08-31). Oggi mischia
   *estrazione* da ezdxf (`extract_forge_texts`, quella vera che alimenta
   `inject()`; `extract_texts_from_msp` resta solo per debug/stampa) e
   *pulizia del contenuto testuale* (`clean_mtext`). Idea di Federico: un
   modulo di gestione testi accessibile anche a un agente esterno, che lavori
   su stringhe pure — zero import di ezdxf dentro. Da decidere: separare in
   (a) estrazione lato adapter DXF (resta vicino a ezdxf) e (b) un modulo
   pure-text a valle (matching/pulizia/riconoscimento materiale-spessore-
   codice) senza dipendenze dal formato. Non ancora iniziato.
5. Merge di `refactor/structure` in `main`.
6. Dashboard — **repo separata** (D16). Rendering nel browser (SVG/Canvas JS)
   da `to_view_model`; backend = server Python sottile attorno a
   `heal_and_detect`. `to_svg` resta comodità di libreria (export, thumbnail).

---

## DECISIONI CHIUSE

### D1 — Nome libreria: resta `forge` (per ora)
`heal` come nome package è stato valutato e scartato (`from heal import heal`
suona male). `dxf-forge` è fuorviante — troppo legato al formato, mentre il punto
è che il modello è format-agnostic — ma il rename si rimanda. Package importabile:
`forge`.

### D2 — `heal_and_detect(doc)` come funzione della via del 90%  ✅
Funzione top-level che fa `heal → detect` e ritorna il `ForgeResult`. Va nel
README. `heal()` e `detect()` restano separate e pubbliche: un renderer o un
nesting tool possono volere la sola topologia. Nome esplicito e un po' goffo di
proposito — scelta umana, non "process". `detect()` viene saltato se `heal()` non
produce parti valide.

### D3 — `detect()` / `inject()` ritornano il result  ✅
Non ritornano più `None`: ritornano il `ForgeResult` (lo stesso oggetto, mutato)
così la catena è esplicita: `result = forge.detect(result)`. Nessun test
dipendeva dal `None`.

### D4 — `OpenShape` / `ClosedShape` (bridge) eliminati  ✅
`heal` produce direttamente `OpenFeature` / `ClosedFeature`; `bridge/shape.py`
cancellato. `pts` / `length` / `shape_type` ora derivati dai segmenti nativi via
`core/geometry.py` (`track_points` / `track_length` / `track_shape_type`).
`OpenFeature` / `ClosedFeature` (`model/feature.py`) **tenuti**: la distinzione
"ha polygon / non ce l'ha" è onesta e dà `area` / `bbox` gratis. È stato il
cambiamento più invasivo della Fase 4 — fatto sub-step per sub-step con la suite
golden come rete.

### D5 — `source` / `confidence` sulle feature rilevate  ✅
`Hole`, `Engraving`, `BendingLine`, `ClassifiedEntity` restano tutte e quattro:
sono quattro intenti di fabbricazione con consumatori diversi. Ognuna porta
`source: str` e `confidence: float`, popolati in `detect.py`: lane geometrica →
`source="geometric"`, lane `label_map` → `source="labeled"` / `confidence=1.0`.
**Niente gerarchia con ereditarietà multipla** — è una convenzione, non una torre
di classi. `ClassifiedEntity` resta fuori dalla gerarchia `Feature` per scelta
(via di fuga dict-based). Invariante: dopo `detect()`, ogni feature ha `source` +
`confidence` sensati.

Struttura finale del modello:
```
Feature (role)
├── ClosedFeature (polygon, segments) → ForgeContour, Hole
└── OpenFeature   (segments)          → Engraving, BendingLine
ClassifiedEntity  → catch-all dict-based, fuori gerarchia per scelta
```

### D6 — `parse_loop` → `segments_from_loop`  ✅
Rinominata e spostata da `adapters/dxf/parser.py` a
`core/topology/loop_finder.py` (logica di dominio pura, non parsing DXF).
`_reverse_segment` rimosso: `LineSeg` / `ArcSeg` / `CircleSeg` hanno `.reversed()`
come `SplineSeg`.

### D7 — Un solo dispatcher entità→primitiva  ✅
`parser.py::DxfEntityDispatcher` e `adapter.py::entity_to_primitive` erano due
copie quasi identiche. Ora una sola (`DxfEntityDispatcher`), usata da produzione
**e** test. **Bug latente scoperto e corretto:** `ArcSeg.from_chord` sbagliava
gli archi maggiori (`|bulge| > 1`, sweep > 180°) — usava `sqrt(r² - half_chord²)`
(sempre positivo → sempre arco minore) invece di `r·cos(sweep/2)` (con segno).
Era mascherato perché la produzione usava il `_bulge_to_arc` corretto di
`adapter.py`. 5 golden roundtrip lo hanno preso appena unificato il dispatcher.

### D8 — `inject()` sgonfiato  ✅
I conteggi feature (fori per tipo, pieghe, incisioni, marking) sono ora
`ForgePart.summary`, property derivata dal modello — non più copiati in
`part.custom` da `inject()`. `inject()` resta solo per il `data_injector` esterno
(materiale / spessore / codice dai testi); senza `data_injector` non fa nulla.
Equivalenza provata prima di toccare i fixture (`part.summary ==
inject().part.custom` su tutte le 63 parti golden, 0 mismatch), poi rename
chirurgico `"custom"` → `"summary"` nei fixture.

### D9 — L'inspector diventa strumento a 3 livelli  ✅
`dxf_inspect.py` (morto, import rotti) → `forge/inspect.py`, esportato. Stampa
tre livelli: (1) entità DXF grezze — "cosa c'è nel file"; (2) primitive / edge /
grafo dopo `load_dxf` — "cosa ha capito l'adapter"; (3) il modello dopo
`heal` / `detect` — "cosa ha prodotto forge". Serve per lavorare su file reali
(es. quando si implementerà `detect_engrave`).

### D10 — `load_pdf` congelato  ✅
Ritorna `list[Edge]`, non un `ForgeDocument` → `forge.heal()` lo rifiuta. Tolto
da `__all__`, marcato sperimentale. Il codice **non si tocca**. Resta importabile
come `forge.load_pdf`. PDF si riprende più avanti (o mai).

### D11 — Versione: unico punto = `pyproject.toml`  ✅
`forge.__version__` la legge con `importlib.metadata.version("forge")`, fallback
`0.0.0+dev`. Non si aggiorna più niente a mano tranne il `pyproject`.

### D12 — SVG: solo in uscita, spline discretizzate  ✅
`to_svg(result)` è un renderer del modello; archi/cerchi/spline appiattiti a
polilinea (accettabile per visualizzare, non per il taglio). **Niente
`SvgAdapter` in ingresso** finché non arriva un file SVG reale.

Implementato in due pezzi (`forge/io/`):
- **`to_view_model(result)`** — `ForgeResult` → dict JSON con la geometria di
  *ogni* feature + ruolo + colore hex. È il vero contratto per un renderer
  esterno (dashboard JS).
- **`to_svg` / `save_svg`** — SVG "batterie incluse" costruito sopra il view
  model. Un colore per ruolo (palette semantica condivisa col DXF), Y ribaltata,
  una parte = un `<g data-part>`, fori come `<circle>` veri.
- `forge/rules/palette.py` esteso: `ROLE_TO_COLOR` completo + `ACI_TO_HEX` +
  `role_to_hex()` (nessuna dipendenza da ezdxf o dal formato).

### D13 — `detect_engrave`: rimandato
`_detect_engrave` resta placeholder no-op. Il seam nella pipeline `detect()` c'è
già (parametro `engrave_tolerance`, chiamata in `detect()`). Quando implementato:
guarda `part.inners` con role UNKNOWN e `result.trash_entities`, promuove a
`Engraving(source="geometric")` i pattern riconoscibili (es. due polilinee
~parallele a distanza < tolerance → incisione, non foro). Federico lo
implementerà dopo aver fatto ordine.

### D14 — Script numerati alla radice: restano, ma si riscrivono
Federico li usa come palestra per capire l'API. Decisione aggiornata (2026-08-29):
non solo si tengono, si **riscrivono e rinumerano** — idealmente uno script per
ogni funzione di `forge.__all__`, con un `INPUT` di default che punti a
`tests/examples/` così girano senza configurazione. `.gitignore` copre già i loro
output (`*_healed.dxf`, `*.png`, `pipeline_output/`, `_split_debug/`).
`13_ARC_splitter` è **fuori da questo lavoro**: è codice di produzione su file
cliente, va portato alla nuova API in una sessione dedicata e collaudato da
Federico con il suo overlay-check in SigmaNest.

### D15 — `detect()` parametrico + classificazione hole spostata lì  ✅
Principio: `HOLE_DIAMETER_THRESHOLD` (32.1 mm) è un **parametro di processo** —
la capacità di foratura della macchina/utensile — non una costante di dominio. I
parametri di processo appartengono alla chiamata di classificazione, non alla
topologia.

Forma finale:
- `heal` produce **solo** l'albero di contenimento:
  `ForgePart(outer, inners=[ForgeContour...])`, zero `Hole`.
- `detect()` è parametrico:
  - `detect(result)` nudo → default taglio laser: solo lane `label_map`
    (autoritativa) + pulizia topologia, zero `Hole`;
  - `detect(result, "holes" | "bending" | "engrave" | "all")` → lane geometriche
    opt-in;
  - `max_drill_diameter` (default 32.1) è argomento di `detect()`: Ø < soglia →
    `Hole`, Ø ≥ soglia → resta `ForgeContour` inner.
- `heal_and_detect(..., features="all")` è la via del 90%.
- `ClosedFeature.diameter` / `center` rimossi: la geometria circolare la ricava
  `core/geometry.circular_geometry`.

Prova di equivalenza su tutti i golden (`features="all"`): diff **solo** su 7
file, dove cerchi Ø ≥ 32.1 migrano da `Hole(role="inner")` a
`ForgeContour(role=INNER)` — che è il comportamento voluto. Golden rigenerati uno
per uno, diff verificato a mano.

Effetto collaterale: il vecchio bug `Hole(role="inner")` prodotto da `hierarchy`
sparisce da solo (nessun `Hole` da `hierarchy`).

Riferimento: memoria `hole-classification-belongs-in-detect`.

### D16 — Dashboard: repo separata, non branch
Una eventuale dashboard / interfaccia è un'**app** con dipendenze proprie (web
server o toolkit GUI), ciclo di release diverso, e non deve inquinare la repo
della libreria. Va in una repo a sé che fa `pip install forge` (o `-e` in
sviluppo), come già `snapmark`. I prototipi in `dev_tools/` (`dashboard.py`,
`dashboard_2.py`, `split_verify*.py`, `dxf_kernel*.py`) sono il punto di
partenza, si portano lì. Un branch andrebbe bene solo per un prototipo
usa-e-getta dentro questa stessa storia.

### D17 — La posizione XY del mondo è preservata (invariante, non decisione)
Registrato qui perché è una garanzia su cui si appoggia il flusso di produzione
(split → import in SigmaNest → overlay dell'originale per il registration check).
La pipeline **non trasla mai** la geometria: `load_dxf` sanifica l'OCS
(`normalize_ocs`: gira il vettore di estrusione senza alterare la geometria in
WCS) e appiattisce la Z; `heal` tocca solo gli endpoint per chiudere i gap;
`to_dxf` / `split` scrivono `center` / `pts` dei segmenti verbatim. Ogni parte
splittata atterra alla stessa coordinata XY assoluta della sorgente. **Unica
perdita voluta:** la Z viene appiattita a 0 (corretto per lamiera/laser).
`test_golden_split` blocca questo invariante — confronta l'`outer_wkt` con
coordinate assolute, un ricentraggio lo farebbe fallire.

### D18 — `to_nester_input`: fuori da `__all__`, sperimentale
dxf-forge **non fa nesting** (disporre i pezzi in tavola per minimizzare lo
sfrido) e non lo farà, salvo commessa pagata da un cliente. `to_nester_input`
era stato scritto all'inizio per un nester mai realizzato. Trattamento identico a
`load_pdf` (D10): il codice resta, importabile come `forge.to_nester_input`, ma
fuori da `__all__` e non documentato nel contratto. La serializzazione della
geometria per renderer/tool è `to_view_model` (D12).
Riferimento: memoria `nesting-out-of-scope`.

### D19 — `adapters/bridge/` eliminato, `Edge` spostato in `core/topology/edge.py`  ✅
Segnalato da Federico: `bridge/` era rimasta con un solo file (`edge.py`) dopo
l'eliminazione di `shape.py` (D4) — smell di cartella. Più a fondo: `Edge`
viveva sotto `adapters/` ma `core/topology/graph.py`, `loop_finder.py`,
`bending_detector.py`, `core/healing/gap_solver.py` e `core/adapter_base.py`
lo importavano tutti da lì — **`core` dipendeva da `adapters`**, il contrario
esatto della regola di dipendenza (`docs/ARCHITECTURE.md`). `Edge` non è una
primitiva (quelle sono math puro in `core/primitives/segments.py`): è un
wrapper topologico con ruolo/stile/provenienza attorno a una primitiva —
appartiene a `core/topology/`, dove vivono i suoi consumatori veri. Spostato
lì; adapter DXF/PDF ora lo importano da `core`, come da regola. Nessuna
modifica di comportamento — solo import aggiornati. Suite: 579 passed.

### D20 — Annotazioni: modello tipato + fase `interpret` separata  ✅
Segnalato da Federico: le annotazioni erano un casino. Due modelli paralleli non
tipati per la stessa cosa — `Annotation(kind, position, data=dict)` in
`model/document.py`, prodotto da `annotation_extractor.py` e consumato da
`write()`, e `ForgeText(content, position: shapely.Point)` in `model/text.py`,
prodotto da `io/text_utils.extract_forge_texts` e consumato da `inject()` — che
leggevano la stessa entità DXF due volte. In più `io/text_utils.py` (codice DXF
puro, ma sotto `io/`) e `annotation_extractor.py` si importavano a vicenda.

Decisione, in linea con `annotations-are-first-class-interpreted-content`:

- **Un solo modello tipato** in `model/annotation.py`: `Annotation` base +
  `Note` / `Dimension` / `Leader`, più `RenderedGeometry` / `RenderedText` per
  l'immagine appiattita di quote e direttrici. Niente `data` dict, niente
  `shapely` nei campi (posizione = tupla). `Annotation(data=dict)` e `ForgeText`
  eliminati.
- **Adapter = solo formato.** `annotation_extractor` legge DXF → oggetti tipati;
  `write` fa l'inverso, fedele. Gli helper stringa MTEXT stanno in
  `adapters/dxf/mtext.py` (`clean_mtext` riesportata da `forge`).
- **Interpretazione in una fase a sé**, `forge.interpret_annotations(result)`,
  **non** dentro `detect()` (che fa già troppo — vedi
  `keep-detect-focused-prefer-separate-stages`). Oggi popola solo
  `Annotation.part_ref` (indice della parte contenitrice); `references` /
  `target` verso le feature sono predisposti ma non ancora calcolati.
- `inject()` non prende più `texts=` né un `msp`: filtra `result.annotations`
  per contenimento. `io/text_utils.py`, `extract_texts_from_msp` e
  `extract_forge_texts` rimossi (nessun chiamante reale, clean break).

Regressione trovata e risolta lungo la strada (`b5b2503`): i MULTILEADER
solo-testo senza anchor/vertici/geometria (Solid Edge) venivano scartati.
Fixture `6200013103_P1NoLineaPiega` aggiunta a `golden/` e `golden_multipli/`;
nuovo golden `golden/annotations/` con `generate_golden_annotations.py`. Due bug
noti pre-esistenti su quella fixture documentati in `file_test_status.md` (BL
sotto-rilevate sul pezzo _1; cartiglio rilevato come parte). Suite: 610 passed.

### D21 — `ForgePart` → `ForgeCluster`  ✅

`heal()` produce **cluster**: gruppi di geometria separati spazialmente. Un
cluster *può* essere un pezzo lavorabile, ma anche una vista, una sezione, un
particolare o il cartiglio — la "part-ness" è interpretazione del consumatore,
non una cosa che forge decide (vedi `INTERPRETER.md` e la memoria
`forge-clusters-not-parts`). Il nome `ForgePart` prometteva una semantica che
forge non fornisce.

Rename meccanico, zero logica cambiata: `ForgePart` → `ForgeCluster`,
`result.parts` → `result.clusters`, `part_count` → `cluster_count`,
`Annotation.part_ref` → `cluster_ref`, `*.part_label` → `cluster_label`,
`filter_part`/`on_part`/`namer(i, part)` → `cluster`, `DEFAULT_MIN_PART_AREA`
→ `DEFAULT_MIN_CLUSTER_AREA`, file `model/part.py` → `model/cluster.py`. Chiavi
di output rinominate (`to_dict`, `save_json`, `save_xml` `<clusters><cluster>`,
`to_view_model`, `data-cluster` in SVG, schema `source="cluster"`). Golden
rigenerati sulle **sole chiavi** — diff verificato: nessun valore geometrico
toccato. Suite: 610 passed.

Breaking: le chiavi JSON/XML cambiano nome. Nessun consumatore reale le legge
ancora. Branch `refactor/clusters`, merge ff, `main` a 0.6.3.

### D22 — `pipeline/` sciolto: `heal`→core, `tools/`, renderer in `io/`  ✅

Segnalato da Federico: `pipeline/` non era "una cosa", mescolava tre tipi
diversi di modulo, e il nome implicava una sequenza fissa che la libreria non
impone ("non una pipeline fissa ma oggetti puliti su cui costruire").

- **`heal.py` (`HealStep` + `heal()`) → `forge/core/heal.py`.** È l'atto del
  motore: `ForgeDocument` → `ForgeResult`, orchestra tutto `core/topology` +
  `core/healing`. Non è opzionale — ogni altro passo lavora sul suo output.
  `core/` già dipendeva da `rules/` (`hole_detector` → `rules.thresholds`;
  `rules/validator` → `core.topology`), quindi `heal` che usa
  `rules.validator` non è una violazione nuova. Tolte 3 righe di import morti
  (`LAYER_OUTER`/`LAYER_INNER`/`COLOR_OUTER`/`COLOR_INNER` + `LoopFinder`
  module-level, già re-importato in `_find_loops`).
- **`detect.py` / `interpret.py` / `inject.py` → `forge/tools/`.** Stadi
  opzionali e componibili su un `ForgeResult`: ognuno lo arricchisce in-place e
  lo ritorna, il caller sceglie quali e in che ordine. È il pattern che un
  interprete di disegno (progetto separato) generalizza — vedi `INTERPRETER.md`.
- **`write.py` (`to_dxf` / `split`) → `forge/io/dxf.py`.** Sono renderer del
  modello, esattamente come `to_svg` / `to_json` / `to_view_model` — che erano
  già in `io/`. `ARCHITECTURE.md` li descriveva come renderer mentre il codice
  li teneva altrove.
- **`heal_and_detect` / `split_to_files` → `forge/recipes.py`.** Le scorciatoie
  della "via del 90%": nessuna logica nuova, solo l'ordine comodo.
- Cancellate `forge/pipeline/` e `forge/workflow/` (quest'ultima vuota da
  sempre).

Nessun cambiamento di comportamento — solo file spostati e import aggiornati.
`forge.__all__` invariato. Suite: 610 passed. Branch `refactor/module-layout`,
`main` a 0.6.4.

Il frame (`core/classification/frame_detector.py`,
`adapters/dxf/frame_adapter_dxf.py`) è concettualmente roba dell'interprete ma
resta in forge finché quel repo non esiste.

---

## QUESTIONI CHIUSE (storico)

- **Q1 — classificazione hole: topologia o detection?** → risolta da D15
  (detection, `detect()` parametrico). L'ipotesi scartata era tenerla in
  `heal` / `hierarchy`: avrebbe impegnato `heal` sulla semantica hole/inner,
  rendendolo non più saltabile, contro
  `laser-cutting-default-cam-enrichment-optional`.
- **Q2 — valore di `HOLE_DIAMETER_THRESHOLD`** → risolta da D15. `32.1` mm è ora
  il **default** di `detect(max_drill_diameter=...)`, non una costante di
  dominio. Federico: lascia `32.1` per ora ("ragiono sui fori che magari hanno
  tolleranza e devono essere ripassati"). La costante resta in
  `rules/thresholds.py` come sorgente del default; il chiamante la può override
  per macchina/utensile.



* Appunti Federico
** API
inspect_file: se non gli passo il dxf, ma un altro fiel in entrata?? ce ne freghaimo ora, dal momento che non abbiamo altri input?
in ispect_dxf, sarebbe meglio avere l'opzione di non printare entità, ome avevamo prima. voglio dire, se hno boisogno solo dela spline o della polilinea, mi devo beccare anche tutto il resto?
load_dxf: se non faccio poi detection all, la tracciatura dei layer non serve a niente, vero?

Ha senso fare come facciamo noi? l'heal e la detection seeparati? si fa? senza stare li a diventare matti...
heal: non mi è chairo cosa sia il part label, è il nome che viene assegnato poi al file di usicta? va solo nei metadati?
split: exclude types può escludere qualunque cosa? o solo text o annotations? prende una lista? vuole to_dxf dopo, o è già compreso nell'api?
split_to_files: ha exclude types cpme split? se non avessi bisogno dei metadati, potrei fare direttamente   split_to_files senza fare result = ....?
inject: tolerance=0.1,   # accettato per compat, non più usato che significa? se è inutile, togliamolo, si può? meglio lasciarlo secondo te? non sporca e confonde?


** MODULI
text_utils.py: fa ancora qualcosa? era quell oche usavo per i testi prima del refactoring, sarebbe cda caire se facevo qualcosa di particolare che possa migliorare quello ce faciamo ora, unificare o non so. Comunque un gestore di testo che possa essere accessibile all'esterno, per un agente coem te o uno specifico per i dxf, ci starebbe, testi in stringa però, un modulo li non deve avere dxf dentro.