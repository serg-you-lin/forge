# Framer — rilevamento automatico di cornice e cartiglio

`Framer` è un **modulo a sé**, consumatore di `forge`, che riconosce in un
disegno tecnico impaginato due cose:

- la **cornice** (frame) — il riquadro di formato ISO che borda il foglio;
- il **cartiglio** (title block) — il riquadro delle informazioni, di solito
  nell'angolo in basso a destra, suddiviso in celle e pieno di testo.
  in alcuni casi il cartiglio è in giro per il disegno e la cornice assente.

Non fa parte di `forge`: `forge` resta neutro e deterministico e non decide cosa
sia un cartiglio (memoria `forge-neutral-substrate-agent-layer-above`). Framer
usa le primitive di forge per fare il riconoscimento, assegna i ruoli
(`frame`, `title_block`) e li riporta giù a forge come input — esattamente il
pattern di `label_map` e di `detect`.

Nel disegno d'insieme, Framer è un **modulo dell'interprete** (`INTERPRETER.md`),
sorella di `views.py` e dell'unfolder. È scorporato in un documento suo perché il
problema è grosso e interessante di per sé: trattare i cartigli in automatico
vale come capacità a prescindere dall'interprete.

Doppio scopo di questo lavoro: oltre alla feature, Framer è il **primo banco di
prova reale dell'interfaccia forge ↔ consumatore** — come un modulo esterno
inietta decisioni geometriche in forge prima di `heal`. Quello che impariamo qui
serve all'unfolder e a ogni modulo futuro.


## Perché serve

Oggi forge, su un disegno con la cornice, produce **un unico cluster** con dentro
tutta la geometria del foglio come inner: la cornice è il loop più esterno e si
mangia tutto. Il cartiglio, se è un rettangolo chiuso, viene contato come cluster
a sé.

Caso reale, fixture `6200013103_P1NoLineaPiega.dxf` (`file_test_status.md`,
BUG NOTO 2): il riquadro del cartiglio (blocco `Cartiglio_sviluppo` esploso,
rettangolo 80×55 mm a ~[41,36]) viene rilevato come parte →
`cluster_count = 6` invece di 5, e i 3 MTEXT del cartiglio prendono
`cluster_ref = 5` invece di `None`. In quel file la cornice manca apposta (i
disegni della pipeline sono richiesti al cliente senza cornice per poterli
splittare) — ma è una stampella: un vero strumento che "interpreta il disegno del
cliente" deve gestire il 99% dei disegni, che la cornice ce l'hanno.

Framer toglie la stampella: rileva cornice e cartiglio **prima** di `heal`, li
marca, e `heal` li esclude dal calcolo dei cluster. L'outer vero dei pezzi
emerge; il cartiglio non è un cluster; i suoi testi hanno `cluster_ref = None`.


## Dove gira nella pipeline

Estende la pipeline dell'interprete (`INTERPRETER.md`, passo [2]):

```
file CAD
   │
   ▼
[1]  forge.load_dxf(path)            → ForgeDocument (edges puri + annotations)
   │
   ▼
[2]  Framer.detect(doc)              → trova cornice + cartiglio sulla geometria
   │                                   GREZZA (prima di heal); marca gli Edge
   │                                   con role="frame" / role="title_block"
   ▼
[3]  forge.heal(doc)                 → cluster puliti: frame e title_block fuori
   │                                   dal grafo → in trash_entities, non cluster
   ▼
[4]  forge.detect(result)            → feature dentro i cluster (forge)
   │
   ▼
[5]  Framer.read_titleblock(doc)     → legge le celle del cartiglio → metadati
   │                                   di disegno (vedi "Cosa restituisce")
   ▼
...  resto dell'interprete (views, callout, nomenclatura, enrich)
```

Il passo [2] lavora su `doc.edges` — le primitive che forge ha già parsato e
normalizzato (OCS sanificato, Z appiattita), ma prima che `heal` costruisca il
grafo. È lì che Framer ha bisogno di agganciarsi.


## Cosa rileva, e i due ruoli

### `frame` — la cornice di formato

Il riquadro esterno del foglio. Ruolo già previsto da forge:
`ContourRole.FRAME = "frame"` (`forge/model/role.py`), tenuto come **etichetta**
dopo la rimozione del vecchio `frame_detector` (MAP D24). `rules/palette` e
`adapters/dxf/layers` gli danno già un layer di destinazione.

### `title_block` — il cartiglio

Ruolo **aperto**, non tra le costanti di forge: un consumatore lo assegna e forge
lo conserva (MAP D27 — "Un consumatore assegna `role='title_block'` e forge lo
conserva (Trash, non strutturale)"). `normalize_role` lo lascia passare come slug
sicuro.

Entrambi i ruoli non sono in `STRUCTURAL_ROLES`
(`{OUTER, INNER, HOLE}`, `forge/rules/thresholds.py`): geometria non di taglio,
va in `trash_entities` con lo stile preservato e il colore del layer forge di
destinazione.


## Algoritmo

Ripreso dal `core/classification/frame_detector.py` rimosso in MAP D24 (è in
git history, commit `ccbb34f^`), da riscrivere sulle primitive di forge invece
che su `RawSegment` propri.

### Cornice

1. Tra gli `edge`, trova i **rettangoli chiusi**: un `closed_path` a 4 lati, o 4
   `LineSeg` axis-aligned i cui endpoint si chiudono.
2. Filtra quelli con **ratio ≈ √2** (formati ISO), tolleranza ±5%
   (`RATIO_TOLERANCE`).
3. Per ogni candidato calcola il **contenimento**: frazione della geometria
   restante i cui punti stanno dentro la sua bbox (con un piccolo margine).
4. Tieni i candidati con contenimento ≥ **80%** (`CONTAINMENT_THRESHOLD`); tra
   questi prendi il **più grande** — quella è la cornice.
5. **Conservativo**: se nessun candidato supera la soglia, Framer **non filtra
   niente** e segnala `frame: uncertain` nei flag. Meglio un cluster sporco che
   buttare via geometria di un pezzo.

### Cartiglio

Il cartiglio **non è per forza dentro una cornice**: a volte la cornice manca e
il riquadro è piazzato in giro per il disegno. Quindi il rilevamento del
cartiglio è indipendente da quello della cornice — se la cornice c'è, la sua
posizione è un segnale in più, non un prerequisito.

Segnali (da combinare, nessuno da solo è sufficiente):

- rettangolo chiuso **suddiviso da linee interne** in una griglia di celle —
  è il segnale più forte e non dipende dalla cornice;
- **racchiude un gruppo denso di annotazioni** — Framer incrocia
  `doc.annotations` (i `Note` / MTEXT già estratti da forge) e cerca il
  rettangolo che ne contiene di più;
- dimensioni tipiche da cartiglio (poche decine / ~200 mm di lato), piccolo
  rispetto all'estensione totale del disegno;
- se la cornice è stata trovata: sta **dentro** la sua bbox, di solito in un
  **angolo** (in basso a destra) — segnale aggiuntivo, non necessario;
- opzionale: **nome di blocco noto** se l'adapter lo espone
  (`Cartiglio_sviluppo`, `TITLE`, …) — segnale forte ma non richiesto.

Anche qui conservativo: nel dubbio non marca, e mette `title_block: uncertain`
nei flag.


## L'interfaccia forge ↔ consumatore (il punto sperimentale)

Framer deve dire a `heal` "questi edge non sono contorno di pezzo". Oggi
`heal._extract_labeled_edges` (`forge/core/heal.py:146`) toglie dal grafo **solo**
`ContourRole.ENGRAVE` e `ContourRole.MARKING`. Un edge `role="frame"` oggi
entrerebbe comunque nel grafo e nella ricerca loop.

Tre modi di agganciarsi, dal meno al più invasivo su forge — **da decidere, è la
scelta di design che questo modulo serve a chiarire**:

| # | come | tocca forge? | note |
|---|---|---|---|
| A | Framer **rimuove** gli edge di frame/cartiglio da `doc.edges` prima di `heal`, li tiene da parte e li fa riemettere a valle | **no** | rispetta `dont-bolt-adapters-onto-forge-for-external-projects` e "forge resta neutro, l'interprete si adatta" (`INTERPRETER.md`). Costo: chi riemette la geometria di cornice nell'output? |
| B | Framer setta `edge.role = "frame"` / `"title_block"` su `doc.edges`; forge estende il set non-strutturale di `_extract_labeled_edges` a `FRAME` + ruoli custom non strutturali | sì, minimo | la geometria resta nel modello (`trash_entities`), l'output la riemette già con stile e layer suo. Coerente con D27. |
| C | forge espone un hook `role_resolver(edge) -> str \| None` a `load_dxf` / `heal` che il consumatore passa | sì, API nuova | generalizza oltre Framer (l'unfolder ne vuole uno simile per `role="section"`). Più lavoro, decisione più pesante. |

Prima lettura: **B** — è il minimo cambiamento, la geometria non si perde, ed è
già il comportamento previsto da D27 per `title_block` (manca solo estenderlo a
`FRAME` nel filtro di `heal`). **A** resta la via se vogliamo zero modifiche a
forge in questa fase. **C** si valuta quando anche l'unfolder chiede la stessa
cosa — se due consumatori la vogliono, l'hook è giustificato.

Invariante da rispettare comunque (`INTERPRETER.md`, "Cosa NON ci va"):
Framer non ragiona *dentro* forge. Framer chiama `forge.load_dxf`, fa il suo
lavoro geometrico, e restituisce a forge dei ruoli. Se serve un cambiamento in
forge è solo per **accettare** i ruoli, mai per **decidere** cosa sia un
cartiglio.


## Il verso "aggiungi" (più avanti)

Oltre a *rilevare* una cornice esistente, Framer può *generarne* una standard e
metterla attorno a un disegno che non ce l'ha — è la nota in `TODO.md`
("Cornice: potrebbe essere parte del plugin per i draft"). Stesso modulo, verso
opposto: dato un `ForgeResult` e un formato ISO, produce gli edge di cornice +
un cartiglio vuoto da compilare. Fuori dal primo giro di lavoro, ma il modulo è
il posto giusto.


## Cosa restituisce

`framer.detect(doc)` → un oggetto (nome da decidere, es. `FrameLayout`) con:

- `frame` — bbox e edge della cornice, o `None`
- `title_block` — bbox, edge, e le **celle** (rettangoli interni con il testo che
  contengono), o `None`
- `format` — formato ISO riconosciuto (`A3`, `A4`, …) dedotto dalle dimensioni
- `confidence` per frame e per cartiglio
- `flags` — `frame: uncertain`, `title_block: uncertain`, `multiple_frames`, …

`framer.read_titleblock(layout)` → dict dei campi del cartiglio
(`{material, drawing_number, revision, scale, ...}`), ognuno con `source` e
`confidence`, `None` + voce in `unresolved` dove non legge. Questo alimenta lo
step `titleblock.py` dell'interprete (`INTERPRETER.md` passo [8]) — o lo è.


## Cosa NON ci va

- decisioni dentro forge — forge non sa cosa sia un cartiglio, e resta così;
- nomenclatura di reparto o logica di un singolo cliente (sta nei `profiles/`
  dell'interprete, mai qui e mai su GitHub);
- guessing non etichettato: ogni campo letto dal cartiglio porta `source` +
  `confidence`, e "non lo so" è `None` + `unresolved`, mai una supposizione;
- discretizzazione: se Framer rimuove/riemette geometria di cornice, la riemette
  con le primitive native, come ogni renderer di forge.


## Stato e prossimi passi

- [ ] recuperare `frame_detector.py` da `ccbb34f^` e riscriverlo sulle primitive
      di forge (`Edge` / `LineSeg` / `closed_path`), niente `RawSegment`, niente
      `print("DEBUG")`
- [ ] decidere l'interfaccia con `heal` (A / B / C sopra) — **prima cosa da
      chiudere**, è il motivo per cui questo modulo esiste ora
- [ ] rilevamento cartiglio (i segnali combinati, incrocio con `doc.annotations`)
- [ ] `read_titleblock` — lettura delle celle
- [ ] repo separato o cartella nel repo dell'interprete? (l'interprete non esiste
      ancora — vedi `INTERPRETER.md`)
- [ ] fixture: `6200013103` con la cornice (chiedere al cliente una versione
      completa), più un paio di A3/A4 standard

### Domande aperte

- Framer è un modulo dell'interprete o un progetto a sé che l'interprete importa?
  (`INTERPRETER.md` ha la stessa domanda aperta per l'agente.)
- La lettura dei campi del cartiglio è di Framer o dello step `titleblock.py`
  dell'interprete? Framer di sicuro **delimita** il cartiglio e le sue celle;
  leggere i valori potrebbe stare di là.
