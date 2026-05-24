# dxf-forge — TODO

Stato attuale: healing funzionante, export JSON/XDATA base, layer centralizzati.
Obiettivo: tool vendibile per normalizzazione DXF e estrazione metadati da taglio laser.

---


## PRIORITÀ ALTA — blocca il prodotto


sessione dedicata ai test

healer/
  __init__.py      ← espone solo heal() — API pubblica
  _geometry.py     ← build_node_graph, find_loops, close_gaps, ecc.
  _hierarchy.py    ← gerarchia padre-figlio, costruzione ForgeResult
  _writer.py       ← _apply_to_msp
  _utils.py        ← _deduplicate, _special_layer_names, ecc.

  
---

## PRIORITÀ MEDIA — migliora la qualità

### Hashing
bending lines nell'interpreter
creare una fingerprint geometrica per validare na forge part.


### API

- [ ] **`forge.process()` — punto di ingresso unico**
  - `result = forge.process(input_dxf, output_dxf, upgrade=True, tolerance=0.05, write_xdata=True)`
  - Nasconde doc/msp/upgrade/write_metadata all'utente
  - Il batch script diventa 5 righe

- [ ] **`upgrade_to_r2010` — integrato automaticamente**
  - Attualmente va chiamato manualmente nel batch
  - `forge.process()` lo chiama sempre se `doc.dxfversion < 'AC1015'`. bisognerebbe consentire all'utente opzionalmente di upgrdare tutti i files, mentre per quanto mi riguarda se si vuole avere il forge i files che non gestiscono gli XDATA devono obbligatoriamente essere upgradati.

### Analisi

- [ ] **`DxfAnalyzer` — output CSV**
  - Esportare `summary_stats()` anche in CSV per analisi batch
  - Utile per misurare qualità dei fornitori

---

## PRIORITÀ BASSA — futuro

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