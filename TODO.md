# dxf-forge — TODO


Stato attuale: healing funzionante, export JSON/XDATA base, layer centralizzati.
Forge è un motore per comprendere geometria CAD 2D.

---


## PRIORITÀ ALTA — blocca il prodotto



  
---

## PRIORITÀ MEDIA — migliora la qualità

### Leaf bug

Il file lineette bastarde genera ancora bending lines li dove deovrebbe mettere le lineette sul trash e non bestemmio perhcè ho già bestemmiato a sufficienza oggi.


### Apertura files

I files splittati non vengono aperti in Autocad, vengono aperti in sigmanest senza problemi e anche in edrawing. Se si aprono in autocad è meglio, perhcè così a lavoro posso guardarli e se i colleghi vogliono guardarli non rompono il cazzo che non si aprono.

### Hashing

creare una fingerprint geometrica per validare na forge part.

### Cornice
Capire dove deve lavorare perhcè potrebbe essere parte del plugin per i draft

### Refactoring hierarchy
DXF adapter → produce List[ShapeProxy] già pronti
core._collect_proxies → riceve List[ShapeProxy], non sa niente di ezdxf
    _build_topology(self, proxies)


### Refactoring Adapters
# core/adapter_base.py  ← agnostico, zero import DXF
from abc import ABC, abstractmethod

class ForgeAdapter(ABC):
    
    @abstractmethod
    def to_edges(self) -> List[Edge]:
        """Produce gli archi per il grafo topologico."""
        ...
    
    @abstractmethod
    def to_proxies(self) -> List[ShapeProxy]:
        """Produce le forme chiuse pre-esistenti (cerchi, polyline chiuse)."""
        ...
    
    @abstractmethod
    def source_layer(self, ref: Any) -> str:
        """Estrae il layer dall'oggetto originale."""
        ...
E DxfAdapter diventa:
python# adapters/dxf/adapter.py
class DxfAdapter(ForgeAdapter):
    def __init__(self, msp, node_decimals, exclude_ids=None, ignore_layers=None):
        self.msp = msp
        ...
    
    def to_edges(self) -> List[Edge]:
        # tutto ciò che oggi fa edges_from_msp()
        ...
    
    def to_proxies(self) -> List[ShapeProxy]:
        # converte circles, plines chiuse, splines chiuse
        # tutto ciò che oggi _build_hierarchy() fa nella prima sezione
        ...
E HealStep diventa:
pythonclass HealStep:
    def __init__(self, adapter: ForgeAdapter, tolerance, label="", ...):
        self.adapter   = adapter
        self.edges     = adapter.to_edges()      # List[Edge] — zero formato
        self.proxies   = adapter.to_proxies()    # List[ShapeProxy] — zero formato
        self.tolerance = tolerance
        # mai più self.msp, mai più self.all_lines, mai più ezdxf


Il pattern if entity.dxftype() == "ARC" sparso in 150 posti è fragile e non scala.
Però questa è una terza cosa grossa — separata da ShapeProxy e da ForgeAdapter. E si collega direttamente al discorso di prima: se l'obiettivo è essere format-agnostici, allora il dispatcher per tipo entità è esattamente il problema che ForgeAdapter risolve a livello architetturale. Quando hai DxfAdapter come classe, il dispatcher per tipo diventa un metodo interno all'adapter — e fuori non esiste più.
2. ForgeAdapter / DxfAdapter        ← elimina il dispatcher sparso
3. entity_length, entity_to_proxy   ← diventano metodi di DxfAdapter


Step 1 — core/adapter_base.py
Classe astratta ForgeAdapter con to_edges(), to_proxies(), source_layer(ref). Zero import DXF. È solo il contratto — non rompe niente.
Step 2 — adapters/dxf/adapter.py
DxfAdapter(ForgeAdapter) con msp in init. to_edges() = tutto ciò che fa oggi edges_from_msp(). to_proxies() = circles, plines chiuse, splines chiuse. Il dispatcher if entity.dxftype() sparso nel codice confluisce qui e sparisce dal resto.
Step 3 — HealStep refactor
Riceve adapter: ForgeAdapter invece di msp. Init fa self.edges = adapter.to_edges() e self.proxies = adapter.to_proxies(). Spariscono self.msp, self.all_lines, self.all_circles, ecc.
Step 4 — _collect_proxies / _build_topology
Il core riceve List[ShapeProxy] già pronti dall'adapter. _build_topology(self, proxies) — zero ezdxf dentro.
Step 5 — BendingLine core puro
Campi: geometry, length, angle_deg, part_label, source_ref. _make_bending_line si sposta in adapters/dxf/bending_adapter.py come bending_line_from_dxf().
Step 6 — ClassifiedEntity core puro
Il campo entity diventa source_ref. detect.py smette di leggere entity.dxf.* direttamente.
Step 7 — load() generico
load_dxf() diventa load(path) con dispatch per formato. DxfAdapter istanziato dentro il loader DXF.
Step 7b — source_layer rinominato source_context


### Analisi

- [ ] **`DxfAnalyzer` — output CSV**
  - Esportare `summary_stats()` anche in CSV per analisi batch
  - Utile per misurare qualità dei fornitori

---

## PRIORITÀ BASSA — futuro

### Feature di tracciatura.
Simil_arcardini_segni_tracciati_stretto_healed --> questo file ha una serie di dentelli che partono da una linea orizzontele, che sono considerati parte del grafo giustamnete. vorrei aggiungere un parametro che sotto una certa distanza queste linee siano considerate solo dei segni di marcatura, completando il grafo solo con la linea orizzontale. Anche se ho degli inner che hanno distanza inferiore alla tolleranza di cui sopra, devono essere detectati come segni di incisione e posti sul layer 'Engrave'. probabilmente questa cosa va implementata nel modulo detect e può essere individuato il tutto solo passando detect() come facciamo con le bl che hanno la loro tolleranza.


### Implementazione nuovo formato:
Al momento in input posso avere solo dxf, ma mi sono messo in condizione di poter prendere anche svg o pdf. Da capire se implementare ad esempio almeno i pdf.



### Comprensione futura:
può essere qualcosa di simile a questo?

parse_geometry()     ← explode INSERT, detect & exclude frame
build_topology()     ← costruisce il grafo
heal()               ← healing geometrico puro
detect_features()    ← detect(), holes, bending lines
writeback()          ← scrive il DXF
split()
inject()


  INPUT

 DWG
 DXF
 PDF
 STEP (domani)
 SVG  (domani)

      │
      ▼

  Adapter Layer
(load, sanitize, convert)

      │
      ▼

 GEOMETRY ENGINE

 graph
 loops
 polygon
 healing
 hierarchy
 frame detection

      │
      ▼

 Forge Model

 ForgePart
 Hole
 Edge
 Metadata
 GeometryHints

      │
      ▼

      API

 result.parts
 result.holes
 result.edges

      │
      ▼

    Plugins


Domani potrebbe semplicemente fare

parts = forge.load(file).heal().detect().parts

e basta.

Lui non sa cosa sia un arco.

Non sa cos'è un grafo.

Non sa cos'è una spline.

Non gli interessa.

Lo splitter è un plugin

Non è Forge.

È

forge.split(...)





I tools possibili sul motore geometrico:
Interrogazione (query)

measure() — distanze, aree, perimetri, bounding box
classify() — aperto/chiuso, convesso/concavo, presenza fori
compare() — similarity tra due parti (base per l'hashing/fingerprint che hai in lista)
validate() — check topologico: ci sono gap? self-intersections? geometrie degeneri?

Trasformazione

heal() — già ce l'hai
simplify() — riduzione punti, merge di segmenti collineari
offset() — kerf compensation, inset/outset contours
normalize() — porta tutto in coordinate canoniche (utile per comparison e hashing)

Analisi

nest_hint() — bounding box ottimale, orientamento suggerito per nesting
grain_direction() — suggerisce orientamento rispetto alla fibra del materiale
engrave_detect() — quello che hai in lista come "feature di tracciatura"

Decomposizione

split() — già ce l'hai
skeleton() — asse mediano (utile per bend detection avanzato)
region_decompose() — divide parti complesse in regioni semantiche





## PRIORITÀ INSENSATA — probabilmente mai o comunque non in questo contesto

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