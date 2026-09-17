# forge come substrato + Pippo come primo consumatore

`forge` è una libreria **deterministica** che ripulisce la matematica pesante e
le rotture di coglioni di un file CAD, e restituisce **oggetti già pronti** su
cui altri lavorano: un agente, un'altra libreria, un nester, bendly (lo
sviluppo lamiere), un disegno interpretato.

**Pippo** è il nome del traguardo: un agente capace di leggere un disegno
tecnico come lo leggerebbe una persona di reparto — materiale, spessore,
quantità, cosa va tagliato, cosa piegato, cosa marcato — senza che tu debba
"pensarci sopra" ogni volta. Resta il nome che tiene la direzione. Quello che
è cambiato in questa revisione (sessione del 2026-09-16, confronto con
ChatGPT/Gemini/Deepseek in `PARERI_VARI.md` + discussione diretta) è **come**
ci si arriva: non un unico prodotto monolitico costruito dall'alto, ma una
cassetta di strumenti indipendenti e già utili da soli, che un agente compone
guardando lo specifico disegno che ha davanti. Il rischio del "tutto o
niente" — costruire mesi di pipeline che vale solo se arriva in fondo intera —
si abbassa parecchio se ogni pezzo ha valore anche da solo.


## Il confine: tre domini, non due livelli di certezza

Non è "forge deterministico, il resto no". Dentro ciascuno dei tre pezzi
sotto puoi avere passi deterministici e passi che restano euristici — quello
che li separa è **di cosa parlano**, non quanto sono certi:

- **forge** — cosa *è* il pezzo fabbricato: geometria, topologia, feature di
  lavorazione (fori, pieghe, incisioni). Dominio: manifattura.
- **framer** — come il pezzo *è documentato* sul foglio: cornice, cartiglio,
  callout, raggruppamento viste. Dominio: convenzioni di disegno tecnico.
  Framer è generico e riusabile fra clienti — nessun dato privato.
- **l'interprete** — cosa quella documentazione *significa per questo
  cliente*: nomenclatura di reparto, profili per-cliente, riempimento buchi
  da ERP. Dominio: conoscenza privata, mai nel repo pubblico.
 QUESTO è IL FINE TUNING MI SEMBRA, CU UN CLIENTE. SI OVERFITTA PROBABILMENTE ED è QUELLLA LA COAS GIUSTA DA FARE.
 PROBABILMENTE SE IN FUTURTO AVRà 3 AZIENDE, OGNUNA DELLE QUALI MI CHIEDE DI ADDESTRAE SU UN PAIO DI CLIENTI A TESTA, DOVREI TARARE
 L'ADDESTRAMENTO SU OGNI SPECIFICO CLIENTE, ED INTANTO FARE UNA COSA NON LEGALISSIMA OVVERO AVEE UN'ALTRO ADDESTRAMENTO PER MIGLIORARE L'AGENTE IN SE.
 NON LO SO SE FUNZIOAN COSì, MA CREOD CHE ABBIA SENSO. UN ADESTRAMENTO PIù DETERMINISTICO SU QUEL CLIENTE, E UNO UN PO PIù ìSPORCO

All'interno di ciascuno, tre operazioni distinte convivono (schema utile,
venuto dal confronto con ChatGPT):

- **Determinismo** — "se do X, applicando questa operazione ottengo sempre
  Y". Proprietà dell'*esecuzione*, non una categoria di funzioni. `heal`,
  `detect`, `bridge_tabs`, `detect_frame` sono tutti deterministici dati i
  loro parametri, pur vivendo in domini diversi.
- **Interpretazione** — "cosa rappresenta X?". Giudizio, sempre con
  `source` + `confidence`, mai una supposizione spacciata per fatto.
- **Correzione** — "dato quello che ho capito, come modifico X?". Un passo
  ulteriore rispetto all'interpretazione — decide un'azione, che poi torna
  giù come trasformazione deterministica eseguita da forge.

Esempio concreto (dal caso "la quota non torna con la scala della vista"):
*misurare* la geometria vera e *applicare* una correzione data sono forge;
*decidere* che la vista è incoerente e *proporre* la correzione sono
interpretazione + correzione, fuori da forge. Utile qui anche il vocabolario
CAD vero — **Drawing Scale** (fattore generale della vista), **View Scale**
(viste di dettaglio/sezione, sopra la drawing scale), **DIMSCALE** (solo gli
elementi grafici della quota, non le misure reali) — sono tre cose diverse,
da non confondere quando questo pezzo si costruirà davvero.


## forge = substrato

### Cosa produce (deterministico)

- **cluster** — gruppi di geometria separati spazialmente (un outer, i suoi
  inner, i suoi segmenti aperti). Nel codice: `ForgeCluster` / `result.clusters`.
  Resta **puramente topologico** — outer/inner per contenimento, niente
  logica di "vicinato" o di raggruppamento semantico. Se in futuro serve
  raggruppare cluster per vista o riconoscere una convenzione grafica (una
  linea di rottura a zig-zag che indica "vista interrotta"), quel lavoro non
  entra qui anche se fosse implementato in modo deterministico: cambierebbe
  cosa significa la geometria nel disegno, non la ricostruirebbe — stessa
  ragione per cui `frame_detector` è uscito da forge (D24). Va in framer.
- feature dentro un cluster: fori (per tipo), pieghe, incisioni — via `detect`
- annotazioni tipate: `Note` / `Dimension` / `Leader`, con `cluster_ref`
  (quale cluster contiene l'annotazione) via `anchor_annotations` (D43,
  prima `interpret_annotations` — rinominata perché "interpret" era già
  usata per tre cose diverse: questa funzione, questo intero progetto, il
  concetto generico discusso in D39-D42)
- bbox, posizione relativa dei cluster

### Cosa NON decide

Un cluster **può essere** un pezzo lavorabile — ma anche una vista dello stesso
pezzo, una sezione, un particolare, o il cartiglio. **forge non decide quale.**
La "part-ness" è interpretazione, ed è del consumatore.

### Gap noto, ancora aperto

`Dimension.references` / `.target` — quale segmento/foro quota una data
quota — sono predisposti nel modello ma **mai calcolati**. È la stessa
famiglia geometrica di `cluster_ref` (dato un punto/una direttrice e la
geometria vicina, trova cosa sta quotando) — meccanica pura, deterministica
data la posizione, quindi resta candidata a `anchor.py`, non a framer. È il
pezzo mancante prima che qualunque cross-check "la quota scritta concorda con
la geometria misurata" sia possibile.

### I tool deterministici che consumano cluster (restano in forge)

| tool | cosa fa |
|---|---|
| `heal` | file → cluster (topologia pulita) |
| `detect` | classifica la geometria dentro i cluster (fori/pieghe/incisioni → `role`) |
| `split` / `split_to_files` | divide i cluster, li nomina, li scrive uno per file |
| `anchor_annotations` | `Annotation.cluster_ref` — quale cluster contiene l'annotazione (solo geometria) |
| `inspect` | ispezione a 3 livelli |
| `to_dxf` / `to_svg` / `save_json` | export fedele dal modello |

Un consumatore può fermarsi a `heal` e fare tutto il resto a modo suo. Questo
non è solo teoria: `heal()`/`detect()` sono separati e pubblici apposta
(MAP.md D2) — forge stesso è già una cassetta degli attrezzi, non una
pipeline forzata. Un disegno vero non dice in anticipo se va splittato, se ha
più viste, se ha una cornice: un agente lo scopre passo passo e sceglie lui
quali strumenti chiamare, non esegue una sequenza scritta a tavolino per "il
disegno tipico".


## framer — il lettore di documentazione (ambito allargato)

Prima framer copriva solo cornice + cartiglio. In questa revisione assorbe
anche quello che nella vecchia versione di questo documento erano moduli
separati dell'interprete (`callouts.py`, `titleblock.py`, `views.py`): sono
tutti la stessa famiglia di lavoro — riconoscere convenzioni di
documentazione tecnica sulla geometria e sul testo che forge ha già estratto,
con `source` + `confidence`, senza dati privati di nessun cliente.

- **cornice** (`frame`) — il riquadro ISO che borda il foglio. **Fatto**,
  portato da forge D24, verificato su un disegno reale (framer D3/D5).
- **cartiglio** (`title_block`) — il riquadro delle informazioni, celle +
  testo. **Stub**, non ancora implementato (`detect_titleblock`,
  `read_titleblock`).
- **callout** — pattern `etichetta: valore` sparsi nel disegno (non nel
  cartiglio): stessa natura di lettura testo-vicino-a-un-pattern del
  cartiglio, stesso posto. **Non ancora iniziato.** (Vedi sopra "cosa fa il
  parser regex" per il dettaglio.)
- **raggruppamento viste** — quali cluster sono viste dello stesso pezzo
  (pianta / sezione / sviluppo), riconoscimento di convenzioni come le linee
  di rottura (vista interrotta). **Non ancora iniziato**, e resta il pezzo
  meno definito: a differenza di cornice/cartiglio/callout (pattern con
  soglie relativamente chiare), qui la casistica reale è più varia. Prima
  di scriverci codice vale la pena guardare un po' di disegni veri e
  vedere quanti pattern ricorrono davvero.

Nessuno di questi tocca forge oltre a leggerne l'output e a riassegnare ruoli
via `edge.role` prima di `heal` (l'interfaccia già chiusa in forge D30,
verificata da framer D2/D6 — il punto sperimentale vero di questo lavoro, e
resta il contributo più prezioso finora: riusabile paro paro da bendly se un
giorno gli servirà).

Stato reale: framer è pre-alpha, non ha ancora un repo GitHub remoto, non ha
fixture reali in `tests/examples/`. Un solo pezzo dei cinque sopra è fatto.


## L'interprete — ridotto a quello che è davvero privato

Tolto tutto quello che si è spostato in framer, quello che resta
dell'"interprete" è molto più piccolo di quanto sembrasse: non più un
orchestratore a 11 passi, ma poco più che **traduzione con dati privati +
incrocio con fonti esterne + assemblaggio finale**. Ha senso restare un
progetto a sé (mai nomenclatura di reparto nel repo pubblico — vedi
`forge-reports-drawing-never-guesses-no-shop-nomenclature`), ma potrebbe
anche finire per essere sottile abbastanza da non aver bisogno di un vero
`pipeline.py`: l'agente stesso potrebbe chiamare forge → framer → queste
funzioni di traduzione, senza un orchestratore dedicato in mezzo. Domanda
aperta, non decisa qui.

| modulo | cosa fa |
|---|---|
| `nomenclature.py` | traduzione nomi di reparto (FE-DECAPATO → …). Tabelle vere in config privato, mai nel repo |
| `enrich.py` | hook di gap-filling (ERP, foglio di lavoro). Callback |
| `profiles/` | profili per-reparto/per-cliente: pattern callout (passati a framer), convenzioni cornice, materiale di default. Dove si materializza l'apprendimento per-cliente |
| `model.py` | `Drawing` (metadati + pezzi), `InterpretedPart` (il cluster di forge + framer, più material/thickness/quantity/code/instructions, ognuno con `source`/`confidence`) |

### Cosa restituisce — la forma comoda per l'agente

- `drawing.parts[i]` = cluster di forge **più** framer **più**
  `.material`/`.thickness`/`.quantity`/`.code`/`.instructions`, ognuno con
  `.source` e `.confidence`
- `drawing.metadata` — numero disegno, revisione, scala, materiale generale
- `drawing.unresolved` — cosa non è riuscito a determinare
- `drawing.flags` — incongruenze (quota vs geometria, due materiali candidati)
- `drawing.forge_result` — il risultato grezzo di forge sotto

### Onestà

Può essere probabilistico ma deve **etichettare** l'incertezza. Dove non sa:
`None` + una voce in `unresolved`. Mai una supposizione come fatto.

### Addestramento

Corpus per disegno: `(forge_result.json, framer_output.json,
interprete_output.json, verità_umana.json)`. Il `ShopProfile` si affina dai
diff. Mai in forge o in framer — non si impara su un output che già indovina.

### Domanda aperta

L'agente sta **sopra** l'interprete (lo usa come tool), o **è** l'agente a
chiamare forge/framer/nomenclatura direttamente, senza un "interprete" come
prodotto a sé? Non decisa — dipende da quanto la parte di traduzione privata
finisce per pesare in pratica.


## bendly (l'unfolder) — sibling, non una tappa della pipeline

Bendly (repo `unfold_generator`) **esiste già**, alpha, fasi 1-3 fatte —
non è un progetto futuro. Nato come esperimento indipendente ("mi serviva
una cosa, volevo vedere dove si arrivava"), non pianificato dall'alto come
parte di questo lavoro. Condivide con forge solo un contratto neutro
(`FlatGeometry.entities` ~ `forge.load_geometry()`), e va nella direzione
**opposta** a Pippo: da specifiche di piega a DXF, non da DXF a
interpretazione. Un giorno potrebbe servire a Pippo come oracolo — verificare
uno sviluppo dichiarato sul disegno contro il calcolo vero di bendly — ma è
un'integrazione futura, non ipotizzata nel dettaglio da nessuna parte.


## Cassetta degli attrezzi, non pipeline fissa

La vecchia versione di questo documento disegnava 11 passi in sequenza fissa.
Non lo fa più: un disegno reale non garantisce di aver bisogno di tutti i
passi, nello stesso ordine, ogni volta. Quello che c'è, oggi e in prospettiva,
è una lista di capacità che un agente compone guardando il disegno specifico:

```
forge:   load_* · heal · detect · split · anchor_annotations · inspect · to_dxf/to_svg
framer:  detect_frame (fatto) · detect_titleblock/read_titleblock (stub)
         · callout parsing (da fare) · raggruppamento viste (da fare)
interprete: nomenclatura · enrich · profili · Drawing (tutto da fare, ambito ridotto)
bendly:  sviluppo lamiere (esiste, direzione opposta — oracolo di verifica, forse)
```

Ognuno di questi ha valore preso da solo. Non serve che arrivino tutti prima
che qualcosa sia utile.


## Cosa NON ci va

- la nomenclatura di reparto nel repo / su github
- guessing non etichettato con `source` + `confidence`
- logica di un singolo cliente fuori dai `profiles/`
- modifiche a forge per far comodo a framer o all'interprete: forge resta
  neutro, sono loro ad adattarsi
