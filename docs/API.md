# forge — riferimento API

Tutto quello che serve è in `import forge`. I moduli interni non si importano
direttamente. Questo documento copre ogni nome esportato in `forge.__all__`.

Convenzioni di questo documento:

- **firma** — parametri e default reali
- **prende / ritorna** — i tipi
- **muta** — se modifica qualcosa in-place (importante: diverse funzioni della
  pipeline lavorano per effetto collaterale)
- **solleva** — le eccezioni che il chiamante deve prevedere

I tipi di dominio (`ForgeDocument`, `ForgeResult`, `ForgePart`, …) sono descritti
in fondo.

---

## Indice

1. [Apertura file](#1-apertura-file) — `load_dxf`, `document_from_msp`
2. [Validazione](#2-validazione) — `validate`, `validate_result`
3. [Pipeline](#3-pipeline) — `heal`, `detect`, `heal_and_detect`, `to_dxf`, `split`, `split_to_files`, `inject`
4. [Export](#4-export) — `save_json`, `to_json`, `save_xml`, `to_nester_input`
5. [Metadati XDATA](#5-metadati-xdata) — `write_metadata_to_dxf`, `read_metadata_from_dxf`, `set_schema`
6. [Ispezione / debug](#6-ispezione--debug) — `inspect_dxf`, `inspect_document`, `inspect_result`, `inspect_file`
7. [Utilità](#7-utilità) — `extract_forge_texts`, `extract_texts_from_msp`
8. [Tipi di dominio](#8-tipi-di-dominio)
9. [Il flusso completo, in ordine](#9-il-flusso-completo-in-ordine)

---

## 1. Apertura file

### `load_dxf`

```python
forge.load_dxf(
    path,
    upgrade=False,
    explode_inserts=True,
    flatten_z_flag=True,
    verbose=False,
    tolerance=0.05,
    label_map=None,
    ignore_layers=None,
) -> ForgeDocument
```

Unico punto in cui `ezdxf` viene usato per **leggere**. Apre un `.dxf` o `.dwg`,
lo audita, lo porta a R2010 se legacy, esplode gli `INSERT`, sanifica (OCS, Z≠0),
traduce le entità in `Edge` puri e le annotazioni in `Annotation`. Dopo questa
funzione il documento `ezdxf` sorgente sparisce.

| parametro | significato |
|---|---|
| `path` | percorso `.dxf` o `.dwg`. Per il `.dwg` vedi la sezione **DWG** qui sotto. |
| `upgrade` | forza l'upgrade a R2010 anche se non necessario. |
| `explode_inserts` | `True` (default): esplode i blocchi in primitive. **Metti `False` solo se vuoi ignorare i blocchi di proposito** — un `INSERT` non esploso viene scartato e la sua geometria sparisce. |
| `flatten_z_flag` | riporta sul piano le entità con Z ≠ 0. |
| `tolerance` | tolleranza di arrotondamento dei nodi topologici. Viene salvata in `source_meta` e riletta da `heal()` se non gliela ripassi. |
| `label_map` | `{nome_layer: work_type}` — assegna il **ruolo** agli `Edge` già in fase di traduzione. Chiavi case-insensitive. `work_type` validi: `outer`, `hole`, `bending`, `frame`, `inner`, `countersink`, `threaded_hole`, `engrave`, `marking`. |
| `ignore_layers` | lista di layer da escludere dalla geometria. |

**Ritorna** un `ForgeDocument`. La diagnostica sul file grezzo (audit, INSERT non
esplosi, Z≠0, duplicati rimossi, tipi non ri-materializzabili in output) finisce
in `doc.warnings`; `forge.validate(doc)` la rilancia.

**Solleva** `FileNotFoundError`, `EnvironmentError` (DWG senza `ODA_PATH`),
`RuntimeError` (conversione DWG fallita), o le eccezioni di lettura di `ezdxf`.

```python
doc = forge.load_dxf("pezzo.dxf", tolerance=0.5,
                     label_map={"Piega": "bending", "MARK": "engrave"})
for w in doc.warnings:
    print("loader:", w)
```

#### DWG

**`forge` non legge il DWG da solo, e nemmeno `ezdxf`.** Il DWG è un formato
chiuso: il "supporto DWG" di `ezdxf` è l'addon `odafc`, che è un wrapper attorno
a **ODA File Converter** — converte il `.dwg` in un `.dxf` temporaneo e `ezdxf`
rilegge quello. `forge` usa esattamente questo (`adapters/dxf/loader.py`).

Per aprire un `.dwg` serve quindi:

1. **ODA File Converter** installato — download gratuito:
   <https://www.opendesign.com/guestfiles/oda_file_converter>
2. `forge` deve trovare l'eseguibile. Due modi:
   - variabile d'ambiente **`ODA_PATH`** = *full path dell'eseguibile*
     (non la cartella — se ODA è in `ODAFileConverter 27.1.0\`, il path deve
     includere `\ODAFileConverter.exe`);
   - oppure `ODAFileConverter` raggiungibile dal `PATH` di sistema.

Impostare `ODA_PATH`:

| SO | comando |
|---|---|
| Windows, permanente | `setx ODA_PATH "C:\Program Files\ODA\ODAFileConverter 27.1.0\ODAFileConverter.exe"` — poi **riapri il terminale** |
| Windows, solo sessione (PowerShell) | `$env:ODA_PATH = "C:\...\ODAFileConverter.exe"` |
| Windows, GUI | Impostazioni → *Modifica le variabili di ambiente relative al sistema* → *Variabili d'ambiente…* → *Nuova* |
| Linux / macOS, permanente | `export ODA_PATH="/opt/ODAFileConverter/ODAFileConverter"` in `~/.bashrc` o `~/.zshrc`, poi riapri la shell |
| Linux / macOS, solo sessione | `export ODA_PATH="/opt/ODAFileConverter/ODAFileConverter"` |

Guide di riferimento per le variabili d'ambiente:
[Windows](https://learn.microsoft.com/windows/win32/procthread/environment-variables) ·
[Linux/macOS (`export`)](https://www.gnu.org/software/bash/manual/bash.html#Environment).

Se manca tutto, `load_dxf` su un `.dwg` solleva `EnvironmentError` con il link e
questa stessa guida nel messaggio.

---

### `document_from_msp`

```python
forge.document_from_msp(
    msp,
    tolerance=0.05,
    label_map=None,
    ignore_layers=None,
    source_path="",
) -> ForgeDocument
```

Costruisce un `ForgeDocument` da un `modelspace` `ezdxf` **già aperto**. Utile per
i test o per geometria generata a mano. **Non** fa audit / upgrade / sanitize: si
assume che il `msp` sia già pronto.

```python
import ezdxf
doc_ez = ezdxf.new("R2010"); msp = doc_ez.modelspace()
msp.add_line((0, 0), (100, 0)); msp.add_line((100, 0), (100, 50))
# ...
document = forge.document_from_msp(msp, tolerance=0.5)
```

---

## 2. Validazione

### `validate`

```python
forge.validate(doc: ForgeDocument) -> ForgeResult
```

Valida l'**input** prima di `heal()`. Non modifica niente. Ritorna un
`ForgeResult` con solo `warnings` / `errors` / `is_valid` (`parts` vuoto).

- **`is_valid = False`** — il file non è lavorabile: nessuna geometria, coordinate
  NaN/inf, tutti i segmenti degeneri.
- **warning** — lavorabile ma da tenere d'occhio: `LINE`/`ARC` ancora fuori da un
  contorno chiuso, endpoint che non si toccano nemmeno alla tolleranza dichiarata,
  segmenti di lunghezza nulla. Include anche le `doc.warnings` del loader.

**Solleva** `TypeError` se non gli passi un `ForgeDocument`.

```python
check = forge.validate(doc)
if not check.is_valid:
    raise SystemExit(check.errors)
for w in check.warnings:
    print("warn:", w)
```

### `validate_result`

```python
forge.validate_result(result: ForgeResult) -> ForgeResult
```

Valida l'**output** dopo `heal()`. **Muta** il `result` passato: aggiunge
`warnings` / `errors` e può mettere `is_valid = False`. Controlla, per ogni part:
poligono outer valido e non vuoto, area > 0, fori contenuti nell'outer.

Viene **già chiamata automaticamente da `heal()`** — la usi a mano solo se
costruisci un `ForgeResult` per altre vie.

---

## 3. Pipeline

### `heal`

```python
forge.heal(doc: ForgeDocument, tolerance=None, label="", source_file="") -> ForgeResult
```

Il passo difficile: ricostruzione della topologia. Lavora su `doc.edges`, zero
`ezdxf`. Chiude i gap, individua le linee di piega candidate, trova i loop chiusi,
costruisce l'albero di contenimento outer / inner.

`heal()` **non classifica i fori** (D15): consegna solo `ForgePart(outer,
inners=[ForgeContour...])`. La promozione a `Hole` è di `detect(features="holes")`.

| parametro | significato |
|---|---|
| `tolerance` | se `None`, ripresa da `doc.source_meta["tolerance"]` (quella passata a `load_dxf`). |
| `label` | etichetta del pezzo, finisce in `part.label` e nei metadati. |
| `source_file` | nome file sorgente, finisce nei metadati. |

`label_map` **non è un parametro di `heal`** — va passato a `load_dxf()`, che
assegna i ruoli agli `Edge`.

**Ritorna** un `ForgeResult`. Se non si forma nessun contorno esterno chiuso,
`result.is_valid` è `False` e `result.errors` è popolato (la `trash_entities`
resta piena per la diagnostica).

**Solleva** `TypeError` se non gli passi un `ForgeDocument`.

```python
result = forge.heal(doc, tolerance=0.5, label="P-1024")
```

---

### `detect`

```python
forge.detect(
    result: ForgeResult,
    features=None,                      # None/() | "all" | {"holes","bending","engrave"}
    *,
    max_drill_diameter=32.1,            # HOLE_DIAMETER_THRESHOLD
    bending_tolerance=1.0,
    engrave_tolerance=1.0,
    deduplicate_boundary_open=True,
    boundary_tolerance=0.05,
) -> ForgeResult
```

Il passo semantico: classifica le feature dentro le parti già trovate da `heal()`.

`detect(result)` **nudo** fa solo il minimo: la lane `label_map` (autoritativa) e
la pulizia della topologia. I contorni circolari restano `inners`, nessun `Hole` —
è il default per il taglio laser.

Le lane geometriche sono **opt-in** via `features`:

| chiamata | cosa fa in più |
|---|---|
| `detect(result, "holes")` | promuove a `Hole` i contorni circolari con Ø `< max_drill_diameter` (`plain` / `countersink` / `threaded`); i Ø maggiori restano contorni interni |
| `detect(result, "bending")` | linee di piega geometriche (segmenti da bordo a bordo) |
| `detect(result, "engrave")` | inferenza incisioni (oggi no-op, D13) |
| `detect(result, "all")` | tutte e tre |

**Muta** `result` in-place (parti, `trash_entities`, `classified_entities`) **e lo
ritorna** — la catena resta esplicita: `result = forge.detect(result, "all")`.

| parametro | significato |
|---|---|
| `features` | quali lane geometriche eseguire. `None`/`()` = nessuna. `"all"` o l'iterabile `{"holes","bending","engrave"}`. |
| `max_drill_diameter` | parametro di processo: sotto questo Ø un contorno circolare è un foro da punta, sopra resta contorno interno. Default `32.1` mm. |
| `bending_tolerance` | lunghezza minima di una traccia perché sia considerata piega. |
| `engrave_tolerance` | riservato all'inferenza geometrica delle incisioni (oggi no-op). |
| `deduplicate_boundary_open` | rimuove dalla trash i segmenti aperti che coincidono col bordo outer. |

```python
result = forge.heal(doc)
result = forge.detect(result, "all", max_drill_diameter=25.0)
```

---

### `heal_and_detect`

```python
forge.heal_and_detect(
    doc: ForgeDocument,
    tolerance=None, label="", source_file="",
    features="all",
    max_drill_diameter=32.1,
    bending_tolerance=1.0, engrave_tolerance=1.0,
    deduplicate_boundary_open=True, boundary_tolerance=0.05,
) -> ForgeResult
```

`heal()` + `detect()` in un colpo solo — la via del 90% dei chiamanti. A
differenza di `detect()` nudo, qui `features="all"` è il default: fori, pieghe e
incisioni vengono classificati. `detect()` viene saltato se `heal()` non produce
parti valide (il `result` torna comunque, con `is_valid=False` e gli errori
popolati). I primi parametri sono quelli di `heal()`, gli altri quelli di
`detect()`.

`heal()` e `detect()` separati restano disponibili: un renderer o un nesting tool
possono volere la sola topologia, senza classificazione feature.

```python
doc    = forge.load_dxf("pezzo.dxf", label_map={"Piega": "bending"})
result = forge.heal_and_detect(doc, label="P-1024")
if not result.is_valid:
    raise SystemExit(result.errors)
```

---

### `to_dxf`

```python
forge.to_dxf(
    result: ForgeResult,
    source_doc: ForgeDocument = None,
    filter_part=None,
    include_annotations=True,
    include_trash=True,
    annotation_layer="Annotation",
) -> ezdxf.document.Drawing
```

Materializza il modello in un **documento DXF nuovo** (R2010). Non rilegge mai
entità dalla sorgente: `source_doc` serve solo a riportare gli header
(`$INSUNITS`, `$MEASUREMENT`). Testi e quote arrivano da `result.annotations`.

| parametro | significato |
|---|---|
| `filter_part` | `callable(ForgePart) -> bool` — scrive solo le parti che passano. |
| `include_trash` | `True` (default): la geometria non classificata va sul layer `Trash`. Un operatore CAM deve poter vedere ogni entità del disegno di partenza. |
| `annotation_layer` | `"Annotation"` → layer forge dedicato; `"Trash"` o altro nome → quel layer; `None` → layer originale della sorgente. Nessuna annotazione viene mai scartata. |

**Ritorna** un `Drawing` `ezdxf`. Sta a te fare `doc_out.saveas(...)`.

**Solleva `ValueError`** se `result.is_valid` è `False` — non genera un file di
sola spazzatura. **Controlla `result.is_valid` prima di chiamarlo.**

```python
if result.is_valid:
    forge.to_dxf(result, doc).saveas("out.dxf")
```

---

### `split`

```python
forge.split(
    result: ForgeResult,
    source_doc: ForgeDocument = None,
    namer=None,
    include_annotations=True,
    min_area=50.0,
    exclude_types=None,
    on_part=None,
    annotation_layer="Annotation",
) -> list[ezdxf.document.Drawing]
```

Come `to_dxf` ma produce **un `Drawing` per parte**. Funzione **pura**: non tocca
il disco. Le parti sotto `min_area` (mm²) vengono scartate (con warning nel
`result`).

| parametro | significato |
|---|---|
| `namer` | `callable(i, part) -> str` — assegna `part.label`, così il nome file resta `f"{part.label}.dxf"` a valle. |
| `exclude_types` | set di `dxftype` da rimuovere dal documento di ogni parte (es. `{"TEXT"}`). |
| `on_part` | `callable(part, doc_out)` — hook per parte, prima che il `Drawing` entri nella lista. |

**Ritorna** la lista dei `Drawing` nell'ordine delle parti tenute.
**Solleva `ValueError`** se `result.is_valid` è `False`.

```python
docs = forge.split(result, doc, min_area=100.0)
for d, part in zip(docs, [p for p in result.parts if p.outer.polygon.area >= 100]):
    d.saveas(f"{part.label}.dxf")
```

---

### `split_to_files`

```python
forge.split_to_files(
    doc: ForgeDocument,
    output_folder,
    label="",
    source_file="",
    tolerance=None,
    namer=None,
    include_annotations=True,
    min_area=50.0,
    exclude_types=None,
    annotation_layer="Annotation",
) -> ForgeResult
```

Pipeline completa multi-pezzo + salvataggio su disco: `heal → detect → split →
.saveas()` per parte. **È l'unica funzione della pipeline che scrive su disco.**
Il nome file è `f"{part.label}.dxf"`, dove `part.label` è quello che assegna
`namer(i, part)`; senza `namer` diventa `f"{label}_P{i+1}"` (es. `batch_P1.dxf`).

**Ritorna** il `ForgeResult` (per poterci fare `save_json` dopo). Se il risultato
non è valido, ritorna il result senza scrivere niente.

```python
result = forge.split_to_files(doc, "output/", label="batch")
forge.save_json(result, "batch.json")
```

---

### `inject`

```python
forge.inject(
    result: ForgeResult,
    data_injector=None,
    texts=None,
    tolerance=0.1,   # accettato per compat, non più usato
) -> ForgeResult
```

Arricchimento CAM **opzionale**. **Muta** `result.parts[i].custom` in-place e
ritorna il `result`. Fa **una cosa**: se passi `data_injector` —
`callable(part, list[str]) -> dict` — gli passa i testi che ricadono dentro
l'outer di ogni parte e mette il dict restituito in `part.custom` (codice pezzo,
materiale, spessore, …). Senza `data_injector`, `inject()` non fa nulla.

`texts` va passato come **`list[ForgeText]`** (`content` + `position`) — il
filtraggio per parte è geometrico, servono le posizioni. Si ottiene con
`forge.extract_forge_texts(msp)`, **non** con `extract_texts_from_msp` (che
ritorna stringhe nude). Il `data_injector` riceve comunque `list[str]`.

I **conteggi delle feature** (fori per tipo, pieghe, lunghezza incisioni) NON si
fanno più qui: sono `part.summary`, una property derivata dal modello (MAP.md
D8). `save_json` / `save_xml` li leggono da lì.

```python
import ezdxf
msp = ezdxf.readfile("pezzo.dxf").modelspace()

def leggi_cartiglio(part, testi):
    return {"material": next((t for t in testi if t.startswith("S")), "S275JR")}

forge.inject(result, data_injector=leggi_cartiglio,
             texts=forge.extract_forge_texts(msp))
```

---

## 4. Export

Tutti leggono lo schema da `forge/rules/metadata_schema.py` — **una sola fonte**
per i nomi dei campi. Cambia quel file (o usa `set_schema`) per adattarti al tuo
CAM.

### `save_json` / `to_json`

```python
forge.save_json(result: ForgeResult, path, indent=2) -> None   # scrive su file
forge.to_json(result: ForgeResult, indent=2) -> str             # ritorna la stringa
```

Metadati per parte secondo schema — **niente coordinate**. Struttura:

```json
{
  "source_file": "batch.dxf",
  "is_valid": true,
  "part_count": 3,
  "warnings": [], "errors": [],
  "parts": [
    {
      "label": "P-1", "source_file": "batch.dxf",
      "quantity": 1, "material": "S275JR", "thickness_mm": 0.0,
      "bending_lines": 2, "countersink_count": 0, "threaded_holes_count": 4,
      "total_engrave_length_mm": 0.0,
      "area_mm2": 12345.67, "holes_count": 6, "inner_contours_count": 1,
      "outer_perimeter_mm": 480.0, "inner_perimeter_mm": 60.0,
      "total_perimeter_mm": 540.0,
      "bbox": {"minx": 0, "miny": 0, "maxx": 200, "maxy": 100}
    }
  ]
}
```

### `save_xml`

```python
forge.save_xml(result: ForgeResult, path) -> None
```

Stessi campi di `save_json`, in XML (`<forge><parts><part>…`).

### `to_nester_input`

```python
forge.to_nester_input(result: ForgeResult) -> list[dict]
```

**Non** usa lo schema: il nester vuole le **coordinate**, non i nomi. Per parte:
`label`, `source_file`, `area`, `bbox`, `outer_coords`, `holes_coords`.

---

## 5. Metadati XDATA

### `write_metadata_to_dxf` / `read_metadata_from_dxf`

```python
forge.write_metadata_to_dxf(doc, part: ForgePart) -> None
forge.read_metadata_from_dxf(doc) -> dict
```

Scrive / rilegge i metadati (stessi campi di `save_json`) come XDATA `FORGE`
sull'entità del layer `OuterContour`. `doc` è un `Drawing` `ezdxf` (tipicamente
quello restituito da `to_dxf`). `read_` ritorna `{}` se non trova niente.

```python
doc_out = forge.to_dxf(result, doc)
forge.write_metadata_to_dxf(doc_out, result.parts[0])
doc_out.saveas("out.dxf")
# più tardi:
meta = forge.read_metadata_from_dxf(ezdxf.readfile("out.dxf"))
```

### `set_schema`

```python
forge.set_schema(schema: dict) -> None
```

Sostituisce lo schema metadati attivo a runtime. Da usare quando `forge` è
installato con pip e non puoi editare `metadata_schema.py`. Struttura:
`{chiave_interna: (nome_output, default, sorgente)}` con `sorgente` ∈
`{"part", "custom", "calculated"}`.

---

## 6. Ispezione / debug

Tre livelli, in ordine di pipeline. Tutti stampano su stdout.

```python
forge.inspect_dxf(path, entities=True, limit=40) -> None
```
**Livello 1** — entità DXF grezze: versione, header, conteggio per tipo e per
layer, dettaglio di ogni entità. Non tocca `forge`.

```python
forge.inspect_document(doc, graph=True, limit=60) -> None
```
**Livello 2** — un `ForgeDocument` (o un path): `source_meta`, warning del loader,
gli `Edge` (ruolo, primitiva, endpoint, `closed_path`), le annotazioni, e il
grafo dei nodi (nodi totali, loop degeneri, nodi di branching, estremi liberi).
"Cosa ha capito l'adapter."

```python
forge.inspect_result(result, coords=False) -> None
```
**Livello 3** — un `ForgeResult`: validità, warning/errori, e per ogni parte
outer/inner/holes (tipati)/bending/engrave/custom, più `trash_entities`,
`classified_entities`, annotazioni. "Cosa ha prodotto forge."

```python
forge.inspect_file(path, tolerance=0.05, label_map=None,
                   run_heal=True, run_detect=True, entities=True, coords=False) -> None
```
Orchestratore: apre il file e stampa i tre livelli in fila. `run_heal=False` /
`run_detect=False` per fermarti a un livello precedente.

```python
forge.inspect_file("pezzo.dxf", label_map={"Piega": "bending"})
```

---

## 7. Utilità

### `extract_forge_texts`

```python
forge.extract_forge_texts(msp) -> list[ForgeText]
```

Estrae i testi da un `modelspace` `ezdxf` come `ForgeText` (`content` +
`position`). **È questo** l'argomento `texts` di `inject()` — il filtraggio per
parte è geometrico e servono le posizioni. Non gestisce `INSERT` — vanno esplosi
prima (`load_dxf` lo fa; qui riapri il file solo per i testi).

### `extract_texts_from_msp`

```python
forge.extract_texts_from_msp(msp) -> list[str]
```

Come sopra ma ritorna solo le stringhe, senza posizione. Per chi vuole i testi e
basta — **non** passabile a `inject()`.

---

## 8. Tipi di dominio

### `ForgeDocument`

Prodotto da `load_dxf` / `document_from_msp`. È il contratto tra l'adapter e il
core: dopo di lui, `ezdxf` non si tocca più.

| campo | tipo | contenuto |
|---|---|---|
| `edges` | `list[Edge]` | geometria tradotta in primitive pure — input di `heal()` |
| `annotations` | `list[Annotation]` | testi e quote della sorgente |
| `source_meta` | `dict` | `$INSUNITS`, `$MEASUREMENT`, `tolerance`, `label_map`, `ignore_layers` |
| `source_path` | `str` | percorso del file |
| `warnings` | `list[str]` | diagnostica del loader sul file grezzo |

### `Annotation`

`kind` (`"TEXT"` | `"MTEXT"` | `"DIMENSION"` | `"LEADER"` | `"MULTILEADER"`),
`position` `(x, y)`, `data` `dict` (contenuto testuale + forma renderizzata come
primitive pure per le quote).

### `ForgeText`

Prodotto da `extract_forge_texts(msp)`, consumato da `inject()`. `content` (`str`,
già ripulito) + `position` (shapely `Point`, per il containment check per parte).

### `ForgeResult`

Prodotto da `heal()`, arricchito da `detect()` / `inject()`.

| campo | tipo | contenuto |
|---|---|---|
| `parts` | `list[ForgePart]` | un elemento per contorno esterno chiuso |
| `is_valid` | `bool` | **controllalo prima di `to_dxf` / `split`** |
| `warnings` / `errors` | `list[str]` | diagnostica |
| `trash_entities` | `list` | geometria non classificata (proxy con `segments`, formato-indipendenti) |
| `annotations` | `list[Annotation]` | copiate da `heal()` dal `ForgeDocument` |
| `classified_entities` | `list[ClassifiedEntity]` | feature senza classe dedicata (marking, work_type custom) |
| `all_arcs` | `list[ArcSeg]` | tutti gli archi — usato dal detector fori filettati |
| `label_map` | `dict` | configurazione di sessione, non serializzata |
| `part_count` | property | `len(parts)` |

Metodo `to_dict()` → dizionario JSON-ready (usato internamente dagli export).

### `ForgePart`

| campo | tipo | contenuto |
|---|---|---|
| `outer` | `ForgeContour` | profilo esterno (ha `polygon`, `segments`, `role`, `area`, `bbox`) |
| `inners` | `list[ForgeContour]` | aperture interne non classificate come foro |
| `holes` | `list[Hole]` | fori — `diameter`, `center`, `hole_type`, `source`, `confidence` |
| `bending_lines` | `list[BendingLine]` | pieghe — `geometry`, `length`, `angle_deg` |
| `engrave_lines` | `list[Engraving]` | incisioni — `segments`, `length`, `closed`, `source`, `confidence` |
| `label` | `str` | etichetta, base del nome file |
| `custom` | `dict` | dati aggiunti da un `data_injector` esterno (materiale, spessore, codice) |
| `summary` | property | conteggi feature derivati dal modello: `plain_holes_count`, `countersink_count`, `threaded_holes_count`, `bending_lines` (gruppi collineari), `total_engrave_length`, `total_marking_length` |
| `area` | property | outer − fori − inner |
| `bbox` | property | `(minx, miny, maxx, maxy)` |

### `ForgeContour`

`role` (`ContourRole`), `polygon` (shapely), `segments` (primitive native),
proprietà `area` e `bbox`.

### `ContourRole` (enum, valori stringa)

`unknown`, `outer`, `hole`, `countersink`, `threaded_hole`, `bending`, `frame`,
`inner`, `engrave`, `marking`.

---

## 9. Il flusso completo, in ordine

```python
import forge, ezdxf

# 1. apri — unico punto che legge ezdxf
doc = forge.load_dxf("pezzo.dxf", tolerance=0.5,
                     label_map={"Piega": "bending"})

# 2. valida l'input (opzionale ma consigliato)
check = forge.validate(doc)
if not check.is_valid:
    raise SystemExit(check.errors)

# 3. + 4. topologia + semantica in un colpo
result = forge.heal_and_detect(doc, label="P-1024")
# separati, se ti serve la sola topologia:
#   result = forge.heal(doc, label="P-1024")
#   result = forge.detect(result, "all")   # detect(result) nudo non classifica i fori

# 5. controlla SEMPRE prima di renderizzare
if not result.is_valid:
    raise SystemExit(result.errors)

# 6. arricchimento CAM (opzionale — solo se hai un data_injector per i testi)
result = forge.inject(result, data_injector=leggi_cartiglio, texts=...)

# 7a. render — un documento con tutte le parti
forge.to_dxf(result, doc).saveas("pezzo_healed.dxf")

# 7b. oppure render — un file per parte
result2 = forge.split_to_files(doc, "output/", label="P-1024")

# 8. metadati
forge.save_json(result, "pezzo.json")
```

Se qualcosa non torna su un file reale: `forge.inspect_file("pezzo.dxf")`.
