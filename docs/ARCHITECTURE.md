# forge — architettura

Questo documento spiega *come è fatto dentro* e *perché*. Per l'uso pratico
dell'API vedi [`API.md`](API.md).

---

## L'idea in una frase

`forge` non è una libreria DXF. È un **motore di ricostruzione topologica** con
un adapter DXF davanti. Prende geometria 2D rumorosa e produce un modello di
fabbricazione consistente: contorni chiusi, gerarchia, feature.

Il DXF è solo il primo formato di ingresso implementato. Il core non sa cosa sia
un DXF, né cosa sia un arco o una spline in quanto entità di CAD — lavora su
primitive geometriche pure.

---

## Il principio: il prodotto è il modello

```
                    ┌─────────────────┐
   DXF / DWG  ──────►                 ├──────►  DXF (to_dxf, split)
   PDF (sperim.) ───►   ForgeResult   ├──────►  JSON / XML (save_json, save_xml)
   SVG (futuro) ─────►   il modello   ├──────►  view model JSON (to_view_model)
                    │                 ├──────►  SVG (to_svg, save_svg)
                    └─────────────────┘
```

Il `ForgeResult` è **il prodotto**. Tutti i `to_*` sono renderer del modello.
`to_dxf` **non rilegge mai il file sorgente** — disegna dal modello. Questo è il
motivo per cui `to_svg` produce la stessa identica immagine senza una riga di
codice nuova nel core.

Conseguenza pratica: **niente si perde**. Si importa tutto — quote, centerline, spazzatura. 
Perché `forge` non perda
niente, il modello è abbastanza ricco da tenere anche ciò che non ha classificato:

- geometria di taglio classificata → parti / fori / feature
- geometria non classificata → `result.trash_entities` (segmenti puri,
  formato-indipendenti — ogni loader li alimenta, ogni renderer sceglie se
  disegnarli)
- testi e quote → `result.annotations` (oggetti di dominio, con sia il valore
  semantico sia la forma renderizzata come primitive)

I tipi di entità che `forge` non modella (`HATCH`, `IMAGE`, `TABLE`, `3DFACE`,
`XLINE`…) restano fuori, ma `load_dxf` emette un warning che li elenca — nessuna
perdita silenziosa.

---

## La struttura

```
forge/
├── adapters/     TRADUZIONE formato → primitive       (conosce ezdxf)
│   ├── dxf/          load_dxf, DxfAdapter, exporter, annotation_extractor, layers
│   ├── pdf/          load_pdf — sperimentale, congelato
│   └── geometry/     load_geometry — sperimentale (geometria pura, non un file)
│
├── core/         MOTORE geometrico puro               (zero ezdxf, zero formato)
│   ├── primitives/   LineSeg, ArcSeg, SplineSeg, CircleSeg, EllipseSeg + discretizzazione
│   ├── topology/     edge.py, grafo dei nodi, ricerca loop, detection pieghe
│   ├── healing/      chiusura gap, normalizzazione, gerarchia
│   └── heal.py       HealStep + heal() — l'atto del motore: file → modello
│
├── model/        IL DOMINIO forge                     (dataclass pure + shapely)
│   ├── document.py   ForgeDocument
│   ├── result.py     ForgeResult
│   ├── cluster.py    ForgeCluster — il contenitore, `detected` è l'overlay
│   │                 di detect() (vocabolario aperto per nome — D44)
│   ├── feature.py    Feature → ClosedFeature / OpenFeature
│   ├── contour.py
│   └── annotation.py Annotation → Note / Dimension / Leader
│
├── tools/        STADI opzionali su un ForgeResult    (il caller sceglie quali e in che ordine)
│   ├── detect.py         detect() / describe_features() — classifica le
│   │                     feature nei cluster (`cluster.detected`)
│   ├── hole_detector.py  euristiche filettato / svasatura usate da detect()
│   ├── anchor.py         anchor_annotations()   — àncora le annotazioni ai cluster
│   ├── inject.py         inject()                — testi del cluster → data_injector esterno
│   ├── thresholds.py     soglie di detect() (HOLE_DIAMETER_THRESHOLD...)
│   └── model/            Hole / BendingLine / Engraving / ClassifiedEntity /
│                         DetectedFeatures — output di detect(), non
│                         geometria di heal() (D44): non in `model/` apposta
│
├── io/           RENDERER del modello + serializzazione
│   ├── dxf.py        to_dxf(), split()       (ex pipeline/write.py)
│   ├── svg.py        to_svg(), save_svg()
│   ├── view_model.py to_view_model()
│   └── exporter.py   save_json / save_xml / XDATA
│
├── rules/        REGOLE di dominio                     (palette, schema, validazione)
├── recipes.py    heal_and_detect(), split_to_files()  — la via del 90%
└── inspect.py    strumento di ispezione a 3 livelli
```

`pipeline/` non esiste più (MAP.md D22): metteva insieme tre cose diverse —
`heal` (l'atto del motore, ora in `core/`), gli stadi opzionali (`tools/`) e i
renderer (`to_dxf`/`split`, ora in `io/` accanto a `to_svg`/`to_json`).

**Regola di dipendenza:** `core` e `model` non importano mai `adapters` **né
`tools`** (D44 — stesso principio, `tools` è un pacchetto pari-grado di
`adapters`/`io`, mai sotto `model`). `adapters`, `tools` e `io` importano
`core` / `model` / `rules`. Quando `model/` deve comunque annotare un tipo che
vive in `tools/` (es. `ForgeCluster.detected`), lo fa solo sotto
`TYPE_CHECKING` — zero import a runtime, `from __future__ import annotations`
rende l'annotazione una stringa pigra. `recipes` mette in fila `core.heal` +
`tools` + `io`. Il core non sa da dove viene la geometria.

---

## Il flusso, passo per passo

### 1. `load_dxf` → `ForgeDocument`

Unico punto che legge `ezdxf`. In ordine:

1. se `.dwg` → conversione via ODA File Converter
2. `readfile`
3. `audit` (le annotazioni vengono estratte **prima**: l'auditor di ezdxf
   cancella le quote che referenziano un blocco geometria mancante)
4. upgrade a R2010 se il file è legacy (R12/R13/R14)
5. explode degli `INSERT` (default `True` — un blocco non esploso fa sparire la
   sua geometria)
6. sanitize: normalizzazione OCS, appiattimento Z ≠ 0, deduplica
7. traduzione: ogni entità → uno o più `Edge`; ogni testo/quota → un `Annotation`

Dopo questa funzione l'oggetto `ezdxf` sorgente **sparisce**. Tutto il resto
lavora sul `ForgeDocument`.

### 2. `heal` → `ForgeResult` (topologia)

Il passo difficile. Lavora su `doc.edges`, zero `ezdxf`. In ordine:

1. **estrae** gli `Edge` con ruolo deciso e non strutturale (`engrave`,
   `marking`, `bending` da `label_map`, o uno slug di un consumatore come
   `frame` / `title_block`): non entrano nel grafo — sono marcatura o arredo
   del disegno, non contorno. Il predicato è `model/role.is_structural_role`
   (D30); è il punto d'aggancio per un consumatore che marca la geometria prima
   di `heal` (framer)
2. **preprocess**: costruisce il grafo dei nodi, trova gli endpoint liberi entro
   `tolerance`, chiude i gap prolungando i segmenti alla loro intersezione reale
3. **detection pieghe candidate**: gli `Edge` con entrambi gli endpoint su nodi di
   branching (grado > 2) sono candidati piega — escono dal grafo per non rompere
   la ricerca dei loop
4. **ricerca loop**, con una scala di strategie sempre meno esatte:
   - grafo esatto (uguaglianza delle tuple arrotondate)
   - se fallisce: clustering degli endpoint entro `tolerance` per trovare gli
     angoli "quasi chiusi", poi chiusura vera all'intersezione
   - se fallisce: loop sul grafo clusterizzato tollerante (con warning: la
     discrepanza sopravvive nell'output)
   - ultima spiaggia: `shapely.polygonize` sui segmenti discretizzati
5. **costruzione gerarchia**: quale loop contiene quale → albero di contenimento
   `outer` / `inner`. `heal` si ferma qui: **non** decide hole vs inner (D15) —
   ogni loop contenuto è un `ForgeContour` in `cluster.inners`.

Se non si forma **nessun** contorno esterno chiuso, il risultato è dichiarato
**non valido** (`is_valid = False`) — come il modelspace vuoto. `to_dxf` si
rifiuterà di generare un file di sola spazzatura.

`validate_result` viene chiamata automaticamente alla fine.

### 3. `detect` (semantica)

Classifica le feature dentro le parti. **Muta il `result` in-place e lo ritorna.**
`heal_and_detect(doc)` fa il passo 2 e il passo 3 insieme (con `features="all"`);
restano separati perché un renderer o un nesting tool possono volere la sola
topologia.

`detect(result)` nudo fa solo la lane `label_map` + pulizia topologia. Le lane
geometriche sono opt-in: `detect(result, "holes" | "bending" | "engrave" | "all")`.

- **fori** (`features="holes"`) → un contorno interno circolare con Ø `<
  max_drill_diameter` (parametro di processo, default 32.1 mm) viene promosso a
  `Hole`; sopra soglia resta `ForgeContour`. Tipo: `plain` / `countersink`
  (cerchio piccolo concentrico dentro cerchio grande) / `threaded` (arco a ~270°
  concentrico, raggio di poco maggiore, rapporto ≤ 1.6).
- **pieghe** → una traccia da bordo a bordo dell'outer, con il punto medio dentro
  il poligono, è una `BendingLine` con il suo angolo.
- **incisioni** → le tracce con ruolo `engrave` finiscono in
  `cluster.features("engrave_lines")` se contenute in una parte, altrimenti
  restano in trash.

Ogni feature trovata si scrive su `cluster.detected` (D44), non su campi
fissi del cluster — `cluster.features(name)` legge una collezione per nome,
`[]` se `detected` è `None` o quel nome non è stato scritto. Vedi "Due
concetti che tornano ovunque" più sotto.

### 4. render — `to_dxf` / `split`

Costruiscono un documento `ezdxf` **nuovo** (mai il sorgente) e ci scrivono i
segmenti puri del modello, ognuno sul suo layer forge (vedi tabella in
[`API.md`](API.md#output-dxf-layers) e nel README). Regole di fedeltà:

- **le spline** si riemettono come `SPLINE` native, ricostruite da control points
  / knots / weights / degree / tangenti — **mai discretizzate a polilinea**
- **le incisioni** si emettono come N entità native (`LINE`/`ARC`/`SPLINE`/
  `CIRCLE`), **mai come `LWPOLYLINE`** — un'incisione è N segmenti separati
- **il trash** si materializza sempre sul layer `Trash`
- **le annotazioni** si riscrivono tutte; in `split` ognuna va nel file della
  parte che la contiene (o della più vicina)

### 5. export / inject

`save_json` / `save_xml` scrivono i metadati per parte secondo lo schema
(`rules/metadata_schema.py`), fondendo tre livelli (D44): `cluster.summary`
(conteggio grezzo, generico, sempre disponibile — `{nome}_count` per ogni
collezione attaccata a `cluster.detected`), `tools.detect.describe_features()`
(il dettaglio ricco che solo forge sa dare sui suoi tipi noti — fori per tipo,
pieghe raggruppate, lunghezza incisioni), ed `extra`/`extra_metadata` — un
dizionario o una callback esplicita del chiamante (stesso idioma di
`data_injector`) per una detection propria che forge non può conoscere.
`inject` serve solo a passare i testi dentro l'outer a un `data_injector`
esterno che restituisce codice / materiale / spessore, e a metterli in
`cluster.custom`.

---

## Due concetti che tornano ovunque

### La tolleranza

`tolerance` (default 0.05, i golden usano 0.5) è la distanza sotto la quale due
punti sono "lo stesso nodo". Serve in due modi:

1. **arrotondamento**: ogni endpoint viene quantizzato su una griglia di lato
   `tolerance` prima di entrare nel grafo
2. **chiusura gap**: due endpoint liberi entro `tolerance` vengono congiunti
   prolungando i segmenti

Un gap 4× la tolleranza **non** viene chiuso — è una scelta, non un bug: se il
file ha buchi grossi, o sono voluti o l'unità di misura è sbagliata. Workaround:
alza `tolerance`.

### Il doppio binario delle feature (label_map / inferenza)

Ogni feature manifatturiera è raggiungibile per **due strade**:

- **`label_map`**: l'utente dice "il layer `Piega` sono pieghe". Il ruolo è
  assegnato al load, è **autoritativo**, a valle non si rimette in discussione
  (`source="labeled"`, `confidence=1.0`). Il vocabolario dei ruoli è aperto: un
  work_type che forge non conosce (`frame`, `title_block`, …) non è un errore —
  passa per `normalize_role`, viene conservato e trattato come non strutturale:
  `heal` lo tiene fuori dal grafo, `detect` non lo tocca, l'output lo scrive su
  un layer DXF col nome dello slug (non `Trash` — non è spazzatura), geometria
  intatta (D27, D30, D31). Stessa autorità, stesso load, per
  `linetype_map`/`color_map` (`{"DASHED": "bending"}`, `{"cyan": "engrave"}`,
  Cluster E): quando il disegno porta l'intenzione nello stile della linea
  invece che nel layer, sono la stessa lane con un altro segnale in ingresso —
  si applicano solo dove `label_map` non ha già deciso dal layer. Il linetype
  e il colore confrontati sono quelli **effettivi**: un'entità `ByLayer`
  eredita lo stile dal layer che la contiene, e `DxfAdapter` lo risolve prima
  del confronto — altrimenti ogni entità che eredita lo stile dal layer (il
  caso comune) sfuggirebbe silenziosamente a entrambe le lane.
- **inferenza geometrica**: `forge` riconosce la feature dalla forma
  (`source="geometric"`, `confidence < 1.0`).

`Hole` è l'implementazione di riferimento (ha `hole_type` + `geometric_hint` +
`source` + `confidence`). `Engraving` lo segue. Il design resta aperto al binario
dell'inferenza anche dove non è ancora implementato — es. `detect._detect_engrave`
è un placeholder con già il parametro `engrave_tolerance` e il posto in
`detect()`.

---

## Cosa NON è (ancora) pulito

Onestà sullo stato — dettagli e motivazioni sono in `MAP.md` (sezione
"Closed decisions"), non ripetuti qui:

- **`load_pdf`** ritorna `list[Edge]` invece di un `ForgeDocument` → non si
  aggancia a `heal()`. Congelato (MAP.md D10).
- **`detect._detect_engrave`** è ancora un placeholder no-op (MAP.md D13).
- la tassonomia hole/countersink/threaded/engrave/marking vive in
  `model/role.py` ma è concettualmente di `detect`, non di `model` —
  questione aperta accanto a MAP.md D37, non ancora risolta.

Tutta la storia dei refactor già chiusi (bridge/shape eliminato, dispatcher
entità→primitiva unificato, `Edge` spostato da `adapters/` a
`core/topology/`, ecc.) è nel log decisioni — vedi `MAP.md`.
