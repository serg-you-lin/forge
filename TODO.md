# forge — TODO


Stato attuale: healing funzionante, export JSON/XDATA base, layer centralizzati.
Forge è un motore per comprendere geometria CAD 2D.

---


## PRIORITÀ ALTA — blocca il prodotto

### [PROSSIMA SESSIONE — prima cosa] Refactor `ForgePart` → `ForgeCluster`

`heal()` produce **cluster** (gruppi di geometria separati spazialmente), non
"parti". La part-ness — se un cluster è un pezzo vero, una vista, o il cartiglio
— è interpretazione del consumatore (vedi `INTERPRETER.md`). Il modello va reso
onesto.

- rename meccanico: `ForgePart` → `ForgeCluster`, `result.parts` → `result.clusters`,
  `part_count` → `cluster_count`, variabili `part` → `cluster`
- nessuna logica cambia; `detect` / `split` / `split_to_files` restano in forge e
  consumano cluster
- golden: cambiano solo le **chiavi** dei JSON (`"parts"` → `"clusters"` ecc.), i
  valori (aree, WKT, conteggi) sono identici — un rename puro non tocca la
  geometria. 610 test + golden devono restare verdi.
- `to_dict()` cambia chiave: unico breaking, ma nessuno consuma ancora il JSON
- branch `refactor/clusters`, merge a verde, bump a 0.6.3
- poi riscrivere `INTERPRETER.md` col vocabolario nuovo

heal / detect dentro forge

Sì, ci stanno. Sono l'API semplice per quando le cose vanno già bene. Ma non sono un vincolo: un consumatore può prendere solo la topologia da heal e fare il resto a modo suo (l'unfolder, un nester, tu). È lì il valore — non "una pipeline fissa" ma "oggetti puliti su cui costruire".

Il nome

Il concetto: libreria deterministica che ripulisce la matematica pesante e le rotture, e ti dà oggetti CAD pronti. La cosa che ti dà una base di riferimento fidata.

I miei candidati, in ordine:

1. datum — nel disegno meccanico è il riferimento da cui si misura tutto. "il datum layer per la geometria CAD in Python." Termine vero, corto, serio. È esattamente quello che vuoi che sia.
2. billet — lo spezzone di materiale grezzo, standardizzato e pronto per essere lavorato. forge raffina il file incasinato in un billet su cui l'agente lavora. Tattile, manifatturiero, probabilmente libero su PyPI.
3. plumb — a piombo, squadrato, giusto. "geometria messa a piombo." Evoca la correttezza.


Deciso a fine sessione del 2026-09-06 (`main` a 0.6.2). Clean break, come da
stance sui refactor.

  
---

## PRIORITÀ MEDIA — migliora la qualità


### Apertura files

I files splittati non vengono aperti in Autocad, vengono aperti in sigmanest senza problemi e anche in edrawing. Se si aprono in autocad è meglio, perhcè così a lavoro posso guardarli e se i colleghi vogliono guardarli non rompono il cazzo che non si aprono.

### Hashing

creare una fingerprint geometrica per validare na forge part.

### Cornice
Capire dove deve lavorare perhcè potrebbe essere parte del plugin per i draft






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



# I tools possibili sul motore geometrico:
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


### Cos'è in poche parole:

Questa libreria è tipo un “riparatore di disegni tecnici”: legge un file DXF, controlla se le linee e le forme sono rotte o confuse, le sistema, trova le parti e gli spazi vuoti, e poi salva un disegno più pulito e ordinato.

In pratica
Ora: utile per CAD/CAM e automazione industriale.
Domani: può diventare un sistema di “interpretazione visiva di disegni” se aggiungi:
classificazione robusta,
feature detection,
model di topologia,
regole di business,
eventualmente ML/vision.



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


# UNFOLDING

Il ragionamento è solido e l'architettura è pulita. "Unfold" funziona bene — corto, preciso, non dipende da DXF, scala a qualsiasi forma sviluppabile.

Un'unica cosa che aggiungerei alla riflessione prima di partire con la struttura:

il confine Forge/Unfold va definito bene subito, perché è il punto che più rischia di diventare ambiguo man mano che cresci. La domanda chiave è:

Unfold sa parlare di entità geometriche "native" (cerchi, archi, linee, facce 3D), o riceve già un modello semantico ("questa è una faccia conica con questi parametri")?

Due opzioni architetturali:

A) Unfold riceve parametri puri

python
Cone(top_diameter=1600, bottom_diameter=1016, height=1000)

Forge fa tutto il riconoscimento/estrazione, Unfold è un motore matematico puro. Testabilissimo, zero dipendenze.

B) Unfold riceve geometria e la interpreta

python
unfold.from_forge(drawing)  # Unfold capisce da solo cosa c'è

Più magico, ma il riconoscimento delle forme diventa un problema non banale e si sovrappone a quello che già fa Forge.

La mia lettura è che A è il cuore di Unfold, e il from_forge() che hai disegnato è un adapter — uno strato sottile che siede tra i due e traduce. Non appartiene né a Forge né a Unfold, o appartiene a entrambi come modulo opzionale.

Quindi l'architettura diventa:

FORGE (parsing, healing, topology)
    │
    ▼
forge.unfold_adapter  ← estrae parametri dalla geometria
    │
    ▼
UNFOLD (matematica pura: Cone, Cylinder, Elbow, Transition...)
    │
    ▼
FlatGeometry  ← oggetto neutro, non è DXF
    │
    ▼
FORGE (nesting, tagging, export → DXF)

FlatGeometry è il contratto tra i due sistemi. Se lo definisci bene adesso, i due progetti restano davvero indipendenti.

Vale la pena decidere questo prima di scrivere una riga — cambiarlo dopo è costoso. Cosa ne pensi?

Potresti avere API del genere:

from unfold import Cone, Cylinder

cone = Cone(
    top_diameter=1600,
    bottom_diameter=1016,
    height=1000,
    thickness=5,
)

flat = cone.develop()

flat.to_dxf("cone.dxf")

e poi:

from unfold import Cylinder

flat = Cylinder(
    diameter=1016,
    height=3895,
    thickness=5,
).develop()

Ma il vero salto sarebbe poter passare geometria proveniente da Forge:

import forge
import unfold

drawing = forge.load_dxf("disegno.dxf")
drawing = drawing.heal()

part = unfold.from_forge(drawing)

flat = part.develop()

forge.save_dxf(flat, "sviluppo.dxf")

A quel punto non stai più facendo uno script che calcola un settore anulare.

---

# NIPOTI STACCATI (microjoints / linguette di ritenuta)

Da ragionare con calma, non ora. Idea di Federico: nel taglio lamiera, i contorni
annidati in profondità (un'isola dentro un foro dentro un pezzo — i "nipoti" nella
gerarchia di contenimento, non i "figli" diretti) non restano attaccati al pezzo dopo
il taglio laser: cadono via se non c'è un ponticello di materiale che li tiene. Oggi
Federico li collega a mano disegnando delle "linguette" (microjoints) sul contorno.
Domanda: è roba di forge, o no?

Prima lettura di Federico: no — "forge deve solo classificare e lavorare sui suoi
valori". Il piazzamento delle linguette è una decisione di processo (CAM), stessa
famiglia del nesting — che è già esplicitamente fuori scope per forge.

Cosa ho trovato guardando `core/healing/hierarchy.py`: l'albero di contenimento a
profondità arbitraria (padre → figli → nipoti → ...) viene già costruito
internamente da `_build_tree()`/`_place()` durante `heal()` — ma poi
`_collect_inners()` lo appiattisce deliberatamente ("appiattisce l'albero di
contenimento... a qualsiasi profondità") in un'unica lista piatta `part.inners`,
perdendo l'informazione di profondità e di chi-contiene-chi. Quindi oggi forge non
espone nemmeno il dato grezzo che un tool di linguette avrebbe bisogno di leggere
(quali contorni sono nipoti, e di chi).

Ipotesi di confine (da confermare, non decisa): sapere "questo contorno è annidato a
profondità N dentro questo genitore" è classificazione/topologia — legittimamente
compito di forge, coerente con "forge classifica". Decidere DOVE tagliare un
ponticello, quanto largo, in base a spessore/materiale — quello è CAM.

CORREZIONE di Federico: le linguette NON sono un modulo a parte — Smoother lavora
su file PNG dall'inizio alla fine (immagine → contorni → geometria pulita → DXF), è
pensato per gestire disegni organici più velocemente in tutta la pipeline. Le
linguette entrano come uno step in PIÙ, un passo prima dello smoothing finale, nella
STESSA pipeline/tool. Quindi: 3 moduli, non 4 — forge (classifica, incluso il
conteggio/profondità di annidamento, riusabile), Unfold (genera sviluppi da
parametri), Smoother (immagine → contorni → linguette → geometria pulita → DXF,
tutto in un tool). Il pezzo che forge deve dare a Smoother per le linguette è
esattamente il dato di nesting che oggi butta via in `_collect_inners()` — va reso
riusabile (non ricalcolato da Smoother in proprio).

Prossimo passo deciso: costruire `load_geometry()` per primo — serve sia a Unfold
sia a Smoother (entrambi devono poter consegnare a forge geometria già calcolata/
ricostruita, non un file).

## classifica_punti — cos'è, e se ha senso spostarlo nel core forge

Vedi `smoother_5.py::classifica_punti()` + `scrivi_contorno()`. Cosa fa davvero:
prende una sequenza di punti ORDINATA e chiusa (in smoother_5 viene da
`cv2.findContours`, ma la funzione stessa non sa nulla di immagini) e per ogni punto
calcola l'angolo interno formato dai due lati adiacenti (vettore verso il punto
precedente, vettore verso il successivo). Se l'angolo è sotto una soglia (spigolo
vivo) marca il punto come "corner". `scrivi_contorno()` poi spezza la sequenza sui
corner: i tratti fra due corner con pochi punti diventano una LINE, quelli con molti
punti (una curva vera, campionata densamente) diventano una SPLINE rifittata sui
punti. In sostanza: **ricostruzione di primitive pulite (linea/arco/spline) da una
nuvola di punti densa/rumorosa**, con rilevamento degli spigoli per non "smussare"
via un angolo vero.

Questo NON è specifico della computer vision — è una vera e propria voce del core
motore geometrico, e infatti è già in lista come `simplify()` nella sezione "tools
possibili sul motore geometrico" più sopra in questo file ("riduzione punti, merge
di segmenti collineari"). Casi in cui servirebbe anche fuori da Smoother:
- **DXF con curve già discretizzate**: alcuni software esportano una spline come
  LWPOLYLINE con centinaia di segmentini invece che come SPLINE/ARC vera — oggi
  forge la porta in output così com'è, densa e brutta. Con questo tool potrebbe
  ricostruirla pulita.
- **PDF**: i path PDF sono spesso bezier appiattite in polilinee dense in export —
  stesso problema, stesso beneficio per l'adapter PDF.
- **`load_geometry()` stesso**: se chi chiama consegna punti densi invece di
  parametri d'arco puliti, questo tool li ripulisce prima che entrino nel modello.

Quindi sì, ha senso che sia forge ad averlo — non come "smoothing PNG" (quello resta
di Smoother, dipende da opencv), ma come ricostruzione geometrica generale da punti
ordinati, zero dipendenza da immagini. Nome: da decidere, in inglese (es.
`simplify_points` / `fit_primitives` / `detect_corners` + refit) — coerente con
tutto il resto dei nomi pubblici di forge, già tutti in inglese.