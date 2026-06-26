# dxf-forge — TODO

Stato attuale: healing funzionante, export JSON/XDATA base, layer centralizzati.
Obiettivo: tool vendibile per normalizzazione DXF e estrazione metadati da taglio laser.

---


## PRIORITÀ ALTA — blocca il prodotto



  
---

## PRIORITÀ MEDIA — migliora la qualità

### Leaf bug

Il file lineette bastarde genera ancora bending lines li dove deovrebbe mettere le lineette sul trash e non bestemmio perhcè ho già bestemmiato a sufficienza oggi.

### Hashing

creare una fingerprint geometrica per validare na forge part.

### Hashing

creare una fingerprint geometrica per validare na forge part.

### Layers

al momento uso name layer e color layer, non va bene, deve essere layer e il layer deve avere il colore al suo interno.
Bisognerebbe anche implementare i test perhcè ne esco matto così.

### API

- [ ] **`forge.process()` — punto di ingresso unico**
  - `result = forge.process(input_dxf, output_dxf, upgrade=True, tolerance=0.05, write_xdata=True)`
  - Nasconde doc/msp/upgrade/write_metadata all'utente
  - Il batch script diventa 5 righe

- [ ] **`upgrade_to_r2010` — integrato automaticamente**
  - Attualmente va chiamato manualmente nel batch
  - `forge.process()` lo chiama sempre se `doc.dxfversion < 'AC1015'`. bisognerebbe consentire all'utente opzionalmente di upgrdare tutti i files, mentre per quanto mi riguarda se si vuole avere il forge i files che non gestiscono gli XDATA devono obbligatoriamente essere upgradati.

### Aggiunta in script
forse recover.readfile() e doc.audit(), capire se ha senso farlo per non perdere cose importanti

### Analisi

- [ ] **`DxfAnalyzer` — output CSV**
  - Esportare `summary_stats()` anche in CSV per analisi batch
  - Utile per misurare qualità dei fornitori

---

## PRIORITÀ BASSA — futuro

Refactor Virtual — OCS come responsabilità dell'adapter
Attualmente VirtualShape riceve entità ezdxf e ricostruisce geometria (bulge, archi, angoli) internamente. Questo significa che il layer Virtual conosce implicitamente concetti DXF come OCS, extrusion, start/end angle.
La proposta è spostare tutta la conversione DXF→geometria nell'adapter, in modo che Virtual riceva solo primitive già in WCS:
LineSeg(start, end)
ArcSeg(start, end, center, radius)
SplineSeg(points)
Virtual diventerebbe un layer "dumb" — riceve geometria pura, non sa nulla di DXF. Tutto il casino OCS, bulge, angoli, extrusion viene gestito una volta sola nell'adapter e non trapela mai oltre.
Il vantaggio è che Hierarchy, Graph e Splitter ragionerebbero sempre in coordinate WCS pulite, senza dipendere da come il formato DXF ha codificato la geometria. Debug molto più semplice, zero edge case nascosti.
È un refactor grosso che tocca tutta la pipeline — da fare a freddo, non in emergenza.

può essere qualcosa di simile a questo?
parse_geometry()
build_topology()
heal()
detect_features()
writeback()
split()
inject()

Agente

1) COSA SIGNIFICA “AGENT READY” DAVVERO

Non è registry, non è OOP, non è eleganza.

È questo:

il sistema può cambiare comportamento senza riscrivere il flusso

2) DOVE IL TUO PROGETTO DIVENTA AGENT-READY
🔥 Punto 1 — entity → behavior resolution

Questo:

entity_length(entity)
entity_to_polygon(entity)
get_representative_point(entity)

👉 è già un mini “action router”

Se lo guardi bene:

DXF ENTITY → decisione → comportamento

Questo è EXACTLY il pattern di un agent tool system.

🔥 Punto 2 — graph building
build_node_graph(msp)
find_closed_loops(graph)
classify_loops(loops)

Qui succede una cosa importante:

👉 stai separando percezione → ragionamento → decisione

graph = perception
loops = reasoning
classify = decision layer

Questo è già pipeline agentica.

🔥 Punto 3 — _free_endpoints

Questa è la parte più “agent-like” di tutte:

if len(graph.get(s_r, [])) < 2:

👉 stai già facendo:

anomaly detection + decisione locale

cioè:

"questo nodo è sospetto → fallo uscire nel free set"

Questo è comportamento da agent (trigger-based reasoning)

🔥 Punto 4 — _deduplicate_entities

Questo è il punto opposto:

👉 state mutation + memory cleanup

Gli agenti veri hanno SEMPRE:

memory cleanup
normalization
deduplication

Questa è la tua “memory layer”

3) IL VERO SALTO (QUI STA LA RISPOSTA IMPORTANTE)

Il progetto diventa agent-ready quando:

👉 non è più il codice a decidere cosa fare
👉 ma il codice decide che tool chiamare

Tu sei già a metà strada.

4) COSA TI MANCA PER DIVENTARE DAVVERO AGENT SYSTEM
1. TOOL BOUNDARY CHIARA

Ora hai funzioni sparse.

Ti serve questo concetto:

TOOLS:
- geometry tools
- graph tools
- mutation tools
- io tools
2. DISPATCH LAYER (MANCANTE)

Non hai ancora questo:

Agent / Orchestrator → sceglie tool

Adesso è tutto:

import + call diretto
3. STATE EXTERNALIZATION

Ora lo stato è:

msp
graph
loops

👉 un agent-ready system vuole:

STATE object unico o context container

7) QUANDO SCATTA IL “TRUE AGENT MODE”

Succede quando aggiungi UNA sola cosa:

👉 decision layer

tipo:

tool = decide(entity)
tool(entity, context)

non:

if dxftype == ...

non:

call function manually

---


Astrazione ad esempio....

Serve il passo successivo:

❗ dispatch centralizzato

Esempio concettuale:

Invece di:

if dxftype == "LINE":
elif dxftype == "ARC":
elif dxftype == "SPLINE":

devi arrivare a:

handler = REGISTRY[dxftype]
handler(entity)

2. graph.py → SOLO helper registry (NO core)

Se proprio:

endpoint resolver per entity type
spline/arc adapters

Ma non trasformarlo in dispatcher engine.

3. healer / pipeline → QUI nasce il “kernel”

Il vero salto agent-ready NON è geometry.

È questo layer:

pipeline che decide cosa fare delle entità

Tipo:

entity → classify → transform → route → output

Questo è il tuo futuro “kernel”, non geometry.





models.py          → aggiungi Edge                      ✓ da fare
core/graph.py      → build_node_graph, find_closed_loops,
                     classify_loops, loop_to_points,
                     check_loop_ambiguity               ✓ da fare
core/virtual.py    → from_loop, from_spline_loop        ✓ da fare
healer/pipeline.py → _find_loops, entities_in_loops     ✓ da fare
healer/_helpers.py → _free_endpoints                    ✓ da verificare
healer/_utils.py   → _deduplicate_loops                 ✓ da verificare

core/geometry.py   → nessuna modifica                   ✗
core/gap.py        → nessuna modifica                   ✗





## LINEA GUIDA SVILUPPO — 


La verità architetturale (importante)

Il sistema NON è:

geometry engine generico

È:

topology reconstruction engine (with DXF adapter layer)

cioè:

🎯 Input:

qualsiasi geometria “rumorosa”

🎯 Output:

grafo consistente + loop chiusi + strutture interpretabili

🧠 Il vero modello NON è DXF

Il vero modello è:

👉 “spatial uncertainty graph”

cioè:

nodi = punti/feature
archi = relazioni geometriche
pesi = tolleranze / errori / ambiguità

## POSSIBILE REFACTORING IN TAL SENSO


🔵 1. CORE (NO DXF, NO WORKFLOW, SOLO LOGICA PURA)
📁 core/geometry.py → RESTA quasi tutto

✔️ RESTA:

line/arc/circle math
distance, intersection
arc_endpoint
circle_line_intersections
circle_circle_intersections
closest_to
entity_length → ⚠️ ma diventa shape_length, non entity
_line_length, _arc_length, _circle_length
_polyline_length
_spline_length
round_point
num_segments_for_bulge
_point_to_line_distance
are_collinear
group_collinear_lines
spline flattening logic (MA SENZA DXF objects)
polygon conversion logic (MA su Shape, non entity)
representative point logic (MA su Shape)

❌ ESCE:

tutto ciò che usa entity.dxf
_copy_*
writeback logic
qualunque cosa che conosce DXF

👉 RISULTATO:

geometry lavora su primitive: Point, Segment, Arc, Polyline


🟡 2. DOMAIN MODEL (NUOVO - fondamentale)

Questo è quello che oggi ti manca e ti crea confusione.

📁 model/
Point
Segment
Arc
Circle
Spline
Polyline
Node
Edge
Graph
Shape

👉 questo elimina completamente:

entity
msp dependency
DXF mental model dentro il core
🟠 3. DXF ADAPTER (TUTTO QUELLO CHE TOGLI DAL CORE)
📁 adapters/dxf/

QUI va tutto ciò che oggi è “sporco ma necessario”:

da geometry.py:

❌ _copy_*
❌ entity_to_polygon
❌ pline_to_polygon
❌ circle_to_lwpolyline
❌ get_representative_point(entity)
❌ is_threaded_arc
❌ is_threaded_hole

da workflow/healer:

❌ _edges_from_msp
❌ _load
❌ _deduplicate_entities
❌ _explode_inserts

👉 OUTPUT adapter:

DXF → GraphState
GraphState → DXF
🔴 4. WORKFLOW (IL TUO HEALER ATTUALE)
📁 workflow/healer/pipeline.py

✔️ RESTA:

HealerPipeline.run
orchestrazione

❌ ESCE:

logica geometrica
logica graph
logica gap
logica loop

👉 diventa SOLO:

load → preprocess → detect → classify → output
🟣 5. AGENT (OPZIONALE DOPO)

NON lo metto dentro ora perché hai ragione a dubitare.

Ma diventa:

osserva GraphState
decide parametri pipeline
ripete run
non tocca core



## STRATEGIA REFACTORING 

🧭 1. Decisione giusta (ordine corretto)

✔️ Step 3 — spostamento logica dal pipeline
❌ NON: riscrivere pipeline prima

Quindi sì:

prima isoliamo il cazzo di adapter, senza rompere nulla sopra

🧱 2. Punto chiave che hai centrato (fondamentale)

Tu hai detto:

“le entità originali devono sempre essere recuperabili”

Questo cambia tutto.

Perché implica:

❗ vincolo architetturale reale

ogni astrazione NON può essere lossless rispetto a DXF entity

Quindi il modello NON è:

DXF → geometry → graph

ma:

DXF → (Graph + Back-reference to Entity)
🔥 3. Correzione importante al modello mentale

Il modello “pulito” puro:

geometry senza DXF

NON è completo nel tuo caso industriale.

Quello corretto è:

🟢 CORE = topology + references
Node
Edge {
    geometry: pure shape
    source_entity_id: optional reference
}

👉 quindi il core NON è “ignorante del DXF”
è:

indipendente dal formato, ma non dalla tracciabilità

🧠 4. Questo risolve il tuo dubbio principale

Tu dicevi:

“se tolgo DXF dal core perdo qualcosa”

✔️ vero SOLO se lo togli completamente

Ma la soluzione reale è:

DXF non entra come logica, entra come IDENTITÀ TRACCIATA

🟠 5. QUINDI: cosa diventa l’ADAPTER (vera definizione)

📁 adapters/dxf/

Qui succede tutto il lavoro sporco:

🔹 1. parsing
def to_primitives(entity) -> Primitive:
🔹 2. preservazione identità
@dataclass
class Primitive:
    geom: Geometry
    entity_id: int
    layer: str
🔹 3. graph seed
def build_graph(primitives) -> Graph:
🔹 4. dedup / explode / normalize

✔️ QUI restano:

_deduplicate_entities
_explode_inserts
_normalized_endpoints
🔹 5. writeback reverse mapping
def graph_to_dxf(graph) -> msp
⚙️ 6. cosa cambia nel tuo HealerPipeline ORA

Senza toccare il resto:

PRIMA:
self._load()
self._edges_from_msp()
DOPO:
graph = dxf_adapter.to_graph(msp, tolerance)
🔥 7. e questo è il punto cruciale

👉 il pipeline NON cambia ancora

cambia solo questo:

“chi prepara i dati”

🧠 8. perché questo è il punto giusto

Perché:

✔️ non rompi i golden test
✔️ continui a lavorare su DXF reali
✔️ non perdi precisione
✔️ non introduci astrazioni premature

⚠️ 9. sul tuo dubbio “secondo sistema di tipi”

Hai ragione a essere sospettoso.

Quindi la regola giusta è:

❌ NON creare un nuovo CAD model parallelo
✔️ creare solo:

lightweight geometry + graph + references

🧭 10. quindi roadmap corretta (versione reale, non teorica)
STEP 1 (adesso)

👉 estrazione adapter DXF

niente pipeline changes
niente graph refactor
solo conversion layer
STEP 2

👉 GraphState introdotto

edge/node
ma ancora con entity reference
STEP 3

👉 spostamento logica dal pipeline

STEP 4

👉 solo allora geometry/core pulito


✔ Pipeline corretta:
1. DXF → RAW ENTITIES (MSP)
2. SPLITTER → PRIMITIVE CANONICHE
3. HEALER → TOPOLOGY (graph)
4. WRITER → DXF finale


👉 “automatic feature reconstruction engine per CAD/CAM preprocessing”

questo:

è industriale
è integrabile
è vendibile come modulo
è utile anche senza UI
è usabile in pipeline CAM reali