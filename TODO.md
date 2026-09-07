# forge — TODO


Stato attuale: healing funzionante, export JSON/XDATA base, layer centralizzati.
Forge è un motore per comprendere geometria CAD 2D.

---


## PRIORITÀ ALTA — blocca il prodotto

### ✅ Refactor `ForgePart` → `ForgeCluster` (branch `refactor/clusters`, 0.6.3)

`heal()` produce **cluster** (gruppi di geometria separati spazialmente), non
"parti". La part-ness — se un cluster è un pezzo vero, una vista, o il cartiglio
— è interpretazione del consumatore (vedi `INTERPRETER.md`). Fatto: rename
meccanico `ForgePart`/`result.parts`/`part_count`/`part_ref`/`part_label` +
variabili, file `model/part.py` → `model/cluster.py`, chiavi JSON/XML/view-model,
docs. Nessuna logica cambiata; golden rigenerati sulle sole chiavi; 610 verdi.

### ✅ Split di `forge/pipeline/` (branch `refactor/module-layout`, 0.6.4)

Fatto (MAP.md D22): `heal` → `core/heal.py`; `detect`/`interpret`/`inject` →
`tools/`; `to_dxf`/`split` → `io/dxf.py`; `heal_and_detect`/`split_to_files` →
`recipes.py`; `pipeline/` e `workflow/` cancellate; `ARCHITECTURE.md` + skill
`python-project-setup` aggiornate. `forge.__all__` invariato, 610 verdi.

### ✅ Frame detector rimosso (branch `refactor/kill-frame-deadcode`)

Fatto (MAP.md D24): `core/classification/frame_detector.py` e
`adapters/dxf/frame_adapter_dxf.py` erano codice morto e con import rotto —
cancellati. Il rilevamento cornice/cartiglio è roba dell'interprete (gira prima
di `heal`); l'algoritmo resta documentato in `INTERPRETER.md`. Ruolo
`ContourRole.FRAME` tenuto (solo etichetta). → poi rimosso in D31: `frame` è
uno slug di consumatore, non un ruolo di forge.

### ✅ `core/classification/` sciolta (branch `refactor/hole-detector-to-tools`, 0.6.6)

Fatto (MAP.md D25): `hole_detector.py` → `forge/tools/`, `possibili_altri.md`
cancellato, `forge/adapters/bridge/` (vuota) rimossa. `core/` resta solo motore
geometrico. Nuovi classificatori (bend, engrave, slot, corner…): un modulo
opt-in per volta sotto `tools/`, `detect` diventa package se cresce — non una
cartella `classification/`.

### ✅ `model/` riordinato (branch `refactor/model-tidy`, 0.6.7)

Fatto (MAP.md D26): `ForgeContour` → `model/contour.py`, `BaseInterpreter`
cancellato (ABC morta), `ClassifiedEntity` resta in `model/` (la tiene
`ForgeResult`).

### ✅ Ruoli come vocabolario aperto (branch `refactor/open-roles`, 0.6.7)

Fatto (MAP.md D27): `ContourRole` è la raccolta dei ruoli noti, non più universo
chiuso. `model/role.normalize_role()` è l'unico punto d'ingresso (slug sicuro,
neutralizza injection); `layer_to_role` / `_style_role` / `_role_from` ci passano
invece di schiacciare a `UNKNOWN`; `role_str()` al posto di `.role.value`; type
hint `role: str`; `VALID_WORK_TYPES` morto rimosso. Un consumatore assegna
`role="title_block"` e forge lo conserva (Trash, non strutturale). 619 verdi.

### ✅ Predicato strutturale unico + aggancio pre-heal (branch `refactor/consolidate-structural-role`, 0.6.9)

Fatto (MAP.md D30): `is_structural_role()` + `STRUCTURAL_ROLES` in
`model/role.py`, unico punto di verità — prima il concetto era ridefinito in 4
posti che non concordavano. `heal._split_labeled` estrae ogni ruolo deciso e
non strutturale (non più solo engrave/marking): un consumatore marca
`edge.role` su `doc.edges` prima di `heal` e forge lo tiene fuori dal grafo.
Bug fisso: `detect()` non trasforma più un ruolo che non conosce in un
`ClassifiedEntity` scollegato (geometria persa in output) — lo lascia in Trash.
`forge.normalize_role` / `forge.is_structural_role` pubbliche. Aggancio B di
`FRAMER.md`. 625 verdi.

### ✅ `frame` fuori da forge; ruoli di consumatore su un layer loro (branch `refactor/consumer-roles-out-of-forge`, 0.6.10)

Fatto (MAP.md D31): su un disegno reale con la cornice, la geometria di cornice
usciva tutta sul layer `Trash` — `io/dxf._write_trash` scriveva ogni entità su
`TRASH_LAYER` ignorando il ruolo. `ContourRole.FRAME` rimosso (`frame` è uno
slug di consumatore come `title_block`); `_write_trash` instrada per ruolo: slug
di consumatore → layer col nome dello slug (grigio), `unknown` → `Trash`.
626 verdi, nessun golden toccato.

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


# "BENDING CANDIDATES" IN HEALSTEP — nome che perde vocabolario, e la domanda vera

## ✅ Rename fatto (branch `refactor/rename-non-contour-edges`, 0.6.8, MAP D28)

`BendingDetector` → `NonContourEdgeDetector`, `bending_detector.py` →
`non_contour_edges.py`, `candidate_bending_ids` → `non_contour_edge_ids`,
`_reintegrate_bending()` (era un `pass`) cancellato. Nessun cambiamento di
comportamento. Resta aperta la parte sotto (slot unfolder sul cluster).

Sollevato da Federico: in `HealStep` c'era
`_find_bending_candidates()` / `BendingDetector` — sembrava roba di `detect`, e in
`heal` "facciamo cose che boh".

Cosa fa davvero (verificato in `core/topology/bending_detector.py`): NON
classifica niente come piega. Trova gli edge che hanno **entrambi** gli endpoint
su nodi di branching (degree > 2) e il centroide interno al convex hull, e li
**esclude dal grafo dei contorni** così che `_find_loops` possa chiudere outer e
inner. Una linea che attraversa il pezzo da parte a parte, senza questa
esclusione, rompe la ricerca dei loop. `candidate_bending_ids` è stato interno
di `HealStep`: **non finisce mai sul risultato**. Il `ForgeCluster` che `heal`
ritorna ha sempre `bending_lines=[]` finché non chiami `detect`.

Quindi topologicamente è lavoro di `heal` (produrre cluster puliti); solo il
**nome** prende in prestito la semantica di `detect`. La semantica vera
("questa linea è una piega") è già in `detect._detect_bending`, che legge
`trash_entities` e promuove a `BendingLine` — opt-in, com'è giusto.

Fix minimo: rinominare (`BendingDetector` → filtro edge non-contorno,
`candidate_bending_ids` → `non_contour_edge_ids`), non spostare.

## La domanda architetturale sotto (dove entra l'agente?)

Già decisa, memoria `forge-neutral-substrate-agent-layer-above` + `INTERPRETER.md`
+ MAP D24: **non un punto solo**. L'interprete *orchestra* forge — prima di
`heal` (marca cornice/cartiglio sulla geometria grezza), fra gli step (passa
decisioni giù come `label_map`), dopo (legge cluster+feature e ci mette la
semantica). forge resta deterministico; l'agente lo chiama, non ci entra.

## Tensione residua ("se il cluster è una vista, le feature non c'entrano")

Il cluster di `heal` è già neutro: `outer` + `inners`, geometria
provenance-free. Ma la dataclass `ForgeCluster` ha comunque i campi
`bending_lines` / `holes` / `engrave_lines` **cablati nella struttura** — i
cassetti da "pezzo di lamiera" nel modello neutro (tensione di
`forge-clusters-not-parts` non chiusa fino in fondo).

Opzione da valutare: le feature tipizzate in un overlay che `detect`
ritorna/attacca (`cluster.detected` o un `DetectedFeatures` a parte), non come
campi fissi. Così `heal → ForgeCluster` = puro contenimento geometrico,
`detect → feature` = strato semantico opt-in. Refactor non piccolo: prima
provare che il campo fisso dà davvero fastidio
(`prove-regression-before-architectural-work`).