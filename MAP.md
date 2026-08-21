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

## Tipi core da tipizzare

### `Graph` (oggi è `dict`)
```python
# forge/core/topology/graph.py

@dataclass
class GraphNode:
    point: Tuple[float, float]
    connections: list[tuple[Edge, Tuple[float, float]]]

Graph = dict[Tuple[float, float], list[tuple[Edge, Tuple[float, float]]]]
# oppure, se vogliamo interrogabile:
@dataclass
class Graph:
    nodes: dict[Tuple[float, float], list[tuple[Edge, Tuple[float, float]]]]

    def neighbors(self, node) -> list: ...
    def degree(self, node) -> int: ...
    def branching_nodes(self) -> list: ...
    def pruned(self) -> 'Graph': ...        # prune_dead_ends
```

### `Loop`
```python
# forge/core/topology/loops.py
Loop = list[tuple[Edge, bool]]   # (edge, reversed)
# già usato così — solo dargli un alias esplicito
```

---


## Step successivi (da fare in ordine)

### Step 1 — `Graph` tipizzato

**Obiettivo:** `build_node_graph()` restituisce `Graph` dataclass invece di `dict`.

**File da toccare:**
- `forge/core/topology/graph.py` — aggiungere dataclass `Graph`, aggiornare `build_node_graph()`
- `forge/core/topology/loops.py` — aggiornare `find_closed_loops()`, `_prune_dead_ends()`, `check_loop_ambiguity()`
- `forge/pipeline/heal.py` — `_build_graph()` restituisce `Graph`
- `forge/adapters/dxf/gap_adapter.py` — `extract_free_endpoints()` riceve `Graph`

**Test da scrivere prima di toccare codice:**
```python
def test_graph_degree():
    # 3 edge a triangolo → ogni nodo ha degree 2
def test_graph_branching_nodes():
    # nodo con 3 connessioni → appare in branching_nodes()
def test_graph_pruned_removes_dead_ends():
    # catena aperta → nodi degree-1 rimossi
```

---

### Step 2 — `BendingDetector` come classe indipendente

**Obiettivo:** estrarre `_find_bending_candidates()` da `HealStep`.

**Interfaccia target:**
```python
class BendingDetector:
    def detect(self, graph: Graph, edges: list[Edge]) -> set[int]:
        ...
```

**File da toccare:**
- nuovo `forge/core/healing/bending_detector.py`
- `forge/pipeline/heal.py` — `_find_bending_candidates()` diventa `BendingDetector().detect()`

**Test da scrivere prima:**
```python
def test_bending_detector_trova_linea_interna():
    # grafo con linea che connette due nodi branching interni
    # → id della linea in output
def test_bending_detector_ignora_linea_sul_bordo():
    # linea sul convex hull → non è bending
```

---

### Step 3 — `LoopFinder` come classe indipendente

**Obiettivo:** `find_closed_loops()` + `_deduplicate_loops()` diventano `LoopFinder`.

**Interfaccia target:**
```python
class LoopFinder:
    def find(self, graph: Graph, exclude_ids: set[int] = None) -> list[Loop]:
        ...
```

**File da toccare:**
- `forge/core/topology/loops.py` — wrappare in classe
- `forge/pipeline/heal.py` — `_find_loops()` usa `LoopFinder`

**Test da scrivere prima:**
```python
def test_loop_finder_triangolo():
    # 3 edge triangolo → 1 loop
def test_loop_finder_esclude_bending():
    # triangolo + linea bending → esclude la linea, trova 1 loop
def test_loop_finder_deduplica():
    # stesso loop trovato da due nodi di partenza → 1 solo risultato
```

---

### Step 4 — `HierarchyBuilder` come classe indipendente

**Obiettivo:** `_build_hierarchy()` e `_build_trash()` diventano `HierarchyBuilder`.

**Interfaccia target:**
```python
class HierarchyBuilder:
    def build(self, proxies: list[ClosedShape]) -> tuple[list[ForgePart], list[ClosedShape]]:
        # restituisce (parts, trash)
        ...
```

**File da toccare:**
- `forge/core/healing/hierarchy.py` — wrappare in classe, eliminare monkey-patch su HealStep
- `forge/pipeline/heal.py` — `_build_hierarchy()` + `_build_trash()` usano `HierarchyBuilder`

**Test da scrivere prima:**
```python
def test_hierarchy_outer_con_hole():
    # proxy outer + proxy piccolo interno → 1 part con 1 hole
def test_hierarchy_countersink():
    # proxy outer + proxy medio + proxy piccolo annidato → outer + countersink
def test_hierarchy_trash():
    # proxy con role UNKNOWN non in loop → finisce in trash
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