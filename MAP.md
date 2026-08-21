# Forge — Piano refactoring pipeline
> Ultimo aggiornamento: 2026-08-02

---

## Obiettivo

Rompere `HealStep` in stadi indipendenti con interfacce tipizzate.
Ogni stadio riceve un input, produce un output, è testabile da solo.
La pipeline (`ForgePipeline` / `ForgeSession.heal()`) è solo un orchestratore.

---

## Principi invarianti (non discuterli di nuovo)

- Nessun import ezdxf fuori da `adapters/dxf/`
- `source_ref: Optional[Any]` su tutti gli oggetti core — opaco al core
- `role: ContourRole` è il canale semantico interno — non i layer DXF
- `layer` DXF: entra come stringa dall'adapter, esce come stringa dall'adapter
- Un tipo per concetto (`ClosedShape` ≠ `OpenShape`)
- `msp` non esce mai dall'API pubblica

---

## Stadi della pipeline — interfacce target

```
Adapter.prepare()
    input:  sorgente (path o documento — dipende dall'adapter)
    output: list[Edge], list[Fix]

    Note: legge le primitive, costruisce Edge con source_ref opaco.
    Niente gap solving qui.

GapSolver.compute()
    input:  list[Edge]
    output: list[Fix]

    Note: algoritmo puro nel core. Trova endpoint liberi, calcola
    MoveEndpoint e AddSegment. Zero formato, zero side effect. Le spline dxf sono le uniche entità che restano identiche in tutto e per tutto all'originale, a parte layer e colore. il gap viene risolto con edge nuovi o prolungendo gli edge esistenti.

TopologyBuilder
    input:  list[Edge], list[Fix]
    output: Graph

BendingDetector
    input:  Graph, list[Edge]
    output: set[int]

LoopFinder
    input:  Graph, exclude_ids: set[int]
    output: list[Loop]

LoopClassifier
    input:  list[Loop]
    output: outer: list[Loop], inner: list[Loop]

ContourBuilder
    input:  outer: list[Loop], inner: list[Loop]
    output: list[ClosedShape]

HierarchyBuilder
    input:  list[ClosedShape]
    output: list[ForgePart]

DxfWriter.apply()
    input:  list[ForgePart], list[Fix], doc
    output: documento scritto
```

---

### Step 5 — `ForgePipeline` come orchestratore esplicito

**Obiettivo:** `HealStep.run()` diventa `ForgePipeline.heal()` che chiama gli stadi in sequenza.

**Struttura target:**
```python
class ForgePipeline:
    def heal(self, adapter: ForgeAdapter, tolerance, ...) -> ForgeResult:
        edges   = adapter.to_edges()
        fixes   = GapSolver(tolerance).compute(edges)
        graph   = TopologyBuilder().build(edges, fixes)
        bending = BendingDetector().detect(graph, edges)
        loops   = LoopFinder().find(graph, exclude_ids=bending)
        outer, inner = LoopClassifier().classify(loops)
        proxies = ContourBuilder().build(outer + inner)
        proxies += adapter.to_closed()
        parts, trash = HierarchyBuilder().build(proxies)
        return ForgeResult(parts=parts, trash=trash, fixes=fixes, ...)
        

**File da toccare:**
- nuovo `forge/pipeline/forge_pipeline.py`
- `forge/pipeline/heal.py` — `HealStep` diventa wrapper di compatibilità o viene eliminato

---

## Regressioni note / bug aperti

| Issue | File | Note |
|-------|------|-------|
| `test_quattro_entita_su_trash` fallisce | `core/healing/hierarchy.py` | 6 entità su Trash invece di 4; regressione di `_build_trash` che ora filtra su `role != UNKNOWN` invece di `origin` |
| `to_proxies()` gira prima di `sanitize()` | `pipeline/heal.py` | Si risolve a Step 7/11 quando sanitize esce da HealStep |
| Monkey-patch `HealStep` da `loops.py` e `hierarchy.py` | `pipeline/heal.py` | Eliminato a Step 11 |

---

## API pubblica target (non cambiare)

```python
session = forge.load_dxf("part.dxf", explode_inserts=True)
result  = session.heal(tolerance=0.02, label_map=label_map)
session.detect(result)
session.save_dxf("part_healed.dxf")
```

---

## Come usare questo documento in sessione

1. Incollalo all'inizio della sessione
2. Dimmi quale step vuoi fare
3. Partiamo dalle interfacce / test, poi spostiamo il codice


---

## Refactoring - candidati da ridurre

Obiettivo: togliere i doppioni di concetto, non aggiungere nuovi wrapper.

### Decisione presa

- `ClosedShape` resta il nome canonico.
- `ForgeContour` si elimina.

### Keep

| Nome | Perche tenerlo |
|------|----------------|
| `Hole` | Ha semantica di dominio reale e viene usato in detect, write e model. |
| `ClassifiedEntity` | E' il payload di detection verso inject/write. |
| `ForgeResult` | E' il contenitore di sessione della pipeline. |
| `ForgePart` | Rappresenta l'unita finale del dominio. |

### Merge o semplifica

| Nome | Problema | Direzione consigliata |
|------|----------|-----------------------|
| `ClosedShape` | Si sovrappone a `ForgeContour` come proxy di contorno chiuso. | Unificare su un solo concetto di contorno chiuso, con un eventuale adapter/proxy temporaneo. |
| `OpenShape` | E' un proxy di traccia aperta gia ricostruibile da `Edge`. | Tenerlo solo se serve come boundary di pipeline; altrimenti sostituirlo con una vista derivata da `Edge`. |
| `LineSeg` / `ArcSeg` / `SplineSeg` / `DiscretizedArcSeg` | Sono DTO quasi equivalenti, con logica distribuita in adapter e builder. | Unificare in primitive piu generiche o in un singolo registry di handler. |
| `CircularArcSeg` | Serve, ma e un caso speciale molto vicino a `ArcSeg`. | Valutare se assorbirlo in `ArcSeg` o tenerlo solo dove l'hole detector lo richiede davvero. |

### Candidati a rimozione solo dopo consolidamento

| Nome | Perche ora sembra superfluo | Cosa deve succedere prima |
|------|-----------------------------|---------------------------|
| `ForgeContour` | Duplica il ruolo di `ClosedShape` e sembra un secondo contenitore di contorni. | Decidere un solo modello canonico per contorni chiusi. |
| `DiscretizedArcSeg` | Rappresenta una forma gia approssimata che potrebbe stare direttamente in una lista di punti. | Introdurre un tipo piu esplicito per le tracce campionate, oppure eliminarne l'uso nel virtual adapter. |
| `to_open()` in `ForgeAdapter` | Il core ha gia `edges_to_open_shapes()`. | Spostare del tutto la responsabilita di costruzione open nel core. |

### Ordine pratico

1. Unificare `ClosedShape` e `ForgeContour`.
2. Togliere `to_open()` come sorgente primaria.
3. Ridurre le primitive a un set minimo e portare il resto nei handler.
4. Solo dopo, ripulire i wrapper rimasti in `model/`.




## Adapter DXF 

Io farei un registry di handler
Ad esempio.

class ArcHandler:
    dxftype = "ARC"

    def endpoints(self, entity):
        ...

    def geometry(self, entity):
        ...

    def polygon(self, entity):
        ...

    def length(self, entity):
        ...

    def representative_point(self, entity):
        ...

    def move_endpoint(self, entity, role, pt):
        ...

Poi

class LineHandler:
    dxftype = "LINE"
    ...

e

class SplineHandler:
    dxftype = "SPLINE"
    ...

Alla fine hai

HANDLERS = {
    "LINE": LineHandler(),
    "ARC": ArcHandler(),
    "SPLINE": SplineHandler(),
    ...
}

e ovunque diventa

handler = HANDLERS.get(entity.dxftype())

if handler is None:
    return

geom = handler.geometry(entity)
oppure
handler.endpoints(entity)
L'adapter diventa stupido
Invece di
if dtype == "LINE":
    ...
elif dtype == "ARC":
    ...
elif dtype == "SPLINE":
    ...
diventa
for entity in self.msp:

    handler = handlers.get(entity.dxftype())
    if handler is None:
        continue

    edge = handler.to_edge(entity)

    if edge:
        edges.append(edge)

L'adapter non sa più cosa sia un ARC.
Sa solo:
"c'è un handler che mi costruisce un Edge."

Ancora meglio
Secondo me geometry_adapter.py sta già cercando di diventare questa cosa.

Hai già:

_LENGTH_HANDLERS
_POLYGON_HANDLERS
_REPR_PT_HANDLERS

Sono tre registry.

Io li unificherei.

Invece di avere

_LENGTH_HANDLERS
_POLYGON_HANDLERS
_REPR_PT_HANDLERS

avrei

ENTITY_HANDLERS = {
    "LINE": LineEntityHandler(),
    "ARC": ArcEntityHandler(),
    ...
}

dove ogni handler implementa tutto quello che sa fare.

Per esempio ARC
class ArcEntityHandler(EntityHandler):

    def endpoints(self, entity):
        ...

    def geometry(self, entity):
        ...

    def polygon(self, entity):
        ...

    def representative_point(self, entity):
        ...

    def length(self, entity):
        ...

    def gap_metadata(self, entity):
        ...

    def move_endpoint(self, entity, role, pt):
        ...

Fine.

Se domani aggiungi

ELLIPSE

non tocchi 15 file.

Scrivi

class EllipseHandler(...)

e basta.

Il vantaggio enorme

Oggi la conoscenza di un ARC è sparsa in:

adapter.py
geometry_adapter.py
gap solver
entity_length
entity_midpoint
polygon conversion
representative point

Domani se cambi il modo di rappresentare gli archi devi ricordarti di aggiornare tutto.

Con gli handler, tutto quello che riguarda un ARC vive in un solo posto. L'adapter diventa un semplice orchestratore e aggiungere un nuovo tipo di entità significa estendere il sistema, non modificare codice esistente. Questo è molto più vicino al principio Open/Closed e, secondo me, si adatta bene alla direzione modulare che stai cercando di dare a Forge.