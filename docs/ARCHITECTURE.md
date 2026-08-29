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
   SVG (futuro) ─────►   il modello   ├──────►  input nester (to_nester_input)
                    │                 ├──────►  SVG (futuro to_svg)
                    └─────────────────┘
```

Il `ForgeResult` è **il prodotto**. Tutti i `to_*` sono renderer del modello.
`to_dxf` **non rilegge mai il file sorgente** — disegna dal modello. Questo è il
motivo per cui un futuro `to_svg` produrrà la stessa identica immagine senza una
riga di codice nuova nel core.

Conseguenza pratica: **niente si perde**. Il riferimento dell'utente è SigmaNest,
che importa tutto — quote, centerline, spazzatura. Perché `forge` non perda
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

## I quattro strati

```
forge/
├── adapters/     TRADUZIONE formato → primitive       (conosce ezdxf)
│   ├── dxf/          load_dxf, DxfAdapter, exporter, annotation_extractor, layers
│   ├── pdf/          load_pdf — sperimentale, congelato
│   ├── svg/          (vuoto — futuro)
│   └── bridge/       Edge — la primitiva topologica di lavoro
│
├── core/         MOTORE geometrico puro               (zero ezdxf, zero formato)
│   ├── primitives/   LineSeg, ArcSeg, SplineSeg, CircleSeg + discretizzazione
│   ├── topology/     grafo dei nodi, ricerca loop, detection pieghe
│   ├── healing/      chiusura gap, normalizzazione, gerarchia
│   └── classification/  frame detection, fori filettati
│
├── model/        IL DOMINIO forge                     (dataclass pure + shapely)
│   ├── document.py   ForgeDocument, Annotation
│   ├── result.py     ForgeResult
│   ├── part.py       ForgePart, ForgeContour
│   ├── feature.py    Feature → ClosedFeature / OpenFeature
│   ├── hole.py       Hole
│   ├── engraving.py  Engraving
│   ├── bending_line.py  BendingLine
│   └── classified.py    ClassifiedEntity
│
├── pipeline/     LE FASI orchestrate                  (mette insieme core + model)
│   ├── heal.py       HealStep
│   ├── detect.py     detect()
│   ├── write.py      to_dxf(), split()
│   └── inject.py     inject()
│
├── rules/        REGOLE di dominio                     (soglie, palette, schema, validazione)
├── io/           export (JSON/XML/XDATA/nester) + utilità testi
└── inspect.py    strumento di ispezione a 3 livelli
```

**Regola di dipendenza:** `core` e `model` non importano mai `adapters`. Gli
`adapters` importano `core` e `model`. La `pipeline` importa tutto. Il core non sa
da dove viene la geometria.

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

Dopo questa funzione l'oggetto `ezdxf` sorgente **sparisce**. Tutto il resto della
pipeline lavora sul `ForgeDocument`.

### 2. `heal` → `ForgeResult` (topologia)

Il passo difficile. Lavora su `doc.edges`, zero `ezdxf`. In ordine:

1. **estrae** gli `Edge` con ruolo non strutturale (`engrave`, `marking`, decisi
   da `label_map`): non entrano nel grafo, sono geometria di marcatura, non
   contorno
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
5. **costruzione gerarchia**: quale loop contiene quale → outer / inner / holes.
   Un cerchio piccolo dentro un outer è un `Hole`; un loop più grande è un `inner`.

Se non si forma **nessun** contorno esterno chiuso, il risultato è dichiarato
**non valido** (`is_valid = False`) — come il modelspace vuoto. `to_dxf` si
rifiuterà di generare un file di sola spazzatura.

`validate_result` viene chiamata automaticamente alla fine.

### 3. `detect` (semantica)

Classifica le feature dentro le parti. **Muta il `result` in-place e lo ritorna.**
`heal_and_detect(doc)` fa il passo 2 e il passo 3 insieme; restano separati perché
un renderer o un nesting tool possono volere la sola topologia.

- **fori** → `plain` / `countersink` / `threaded`. Un foro con un arco a ~270°
  concentrico e raggio di poco maggiore (rapporto ≤ 1.6) è filettato.
- **pieghe** → una traccia da bordo a bordo dell'outer, con il punto medio dentro
  il poligono, è una `BendingLine` con il suo angolo.
- **incisioni** → le tracce con ruolo `engrave` finiscono in `part.engrave_lines`
  se contenute in una parte, altrimenti restano in trash.

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
(`rules/metadata_schema.py`). `inject` popola `part.custom` con conteggi e con
quello che un `data_injector` esterno estrae dai testi (codice, materiale,
spessore).

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
  (`source="labeled"`, `confidence=1.0`).
- **inferenza geometrica**: `forge` riconosce la feature dalla forma
  (`source="geometric"`, `confidence < 1.0`).

`Hole` è l'implementazione di riferimento (ha `hole_type` + `geometric_hint` +
`source` + `confidence`). `Engraving` lo segue. Il design resta aperto al binario
dell'inferenza anche dove non è ancora implementato — es. `detect._detect_engrave`
è un placeholder con già il parametro `engrave_tolerance` e il posto nella
pipeline.

---

## Cosa NON è (ancora) pulito

Onestà sullo stato — dettagli e decisioni prese in `MAP.md` (sezione "Decisioni
chiuse"):

- **doppio strato di forme** (D4, non ancora fatto): `bridge/shape.py`
  (`OpenShape`/`ClosedShape`, proxy durante l'healing) e `model/feature.py`
  (`OpenFeature`/`ClosedFeature`) sono vicini. I primi verranno eliminati, `heal`
  produrrà direttamente i secondi. È il refactor più invasivo che resta.
- **`inject` fa lavoro ridondante** (D8, non ancora fatto): metà di quello che
  scrive in `part.custom` è già nelle liste tipate. Diventerà una property
  derivata (`part.summary`).
- **`load_pdf`** ritorna `list[Edge]` invece di un `ForgeDocument` → non si
  aggancia a `heal()`. Congelato (D10).

Già risolto in Fase 4: traduttore entità→primitiva ora unico
(`DxfEntityDispatcher`, D7); `parse_loop` → `segments_from_loop` in
`core/topology/` (D6); `source`/`confidence` su `BendingLine` (D5).
