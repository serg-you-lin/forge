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
ChatGPT/Gemini/Deepseek, raccolti a titolo di confronto, + discussione diretta) è **come**
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

> **Nota (Federico, 2026-09-17):** questo mi sembra il fine-tuning con un
> cliente — probabilmente overfitta, e credo sia la cosa giusta da fare. Se in
> futuro avrò 3 aziende che mi chiedono di lavorare su un paio di clienti a
> testa, dovrei tarare l'addestramento su ogni cliente specifico, e intanto
> fare una cosa non troppo legale: un altro addestramento per migliorare
> l'agente in sé, senza dirlo agli interessati. Non so se funziona così, ma
> credo abbia senso.
>
> **Risposta:** sulla prima parte hai ragione — è già il design di
> `profiles/`, overfittare deliberatamente su un cliente è corretto, è il
> punto. Una correzione di lessico che vale la pena tenere, visto quanto ci
> siamo giocati la parola stasera: questo non è "determinismo" nel senso di
> questo documento (stesso input → stesso output). È **specializzazione**,
> una proprietà diversa — un profilo tarato su un cliente resta comunque
> deterministico nell'esecuzione, cambia solo quanto è stretto.
>
> Sulla seconda parte, la buona notizia è nella nota sotto ("cos'è un
> agente"): in questa architettura non c'è quasi mai un vero riaddestramento
> di pesi — "addestrare" qui significa quasi sempre affinare un `ShopProfile`
> (pattern, tabelle, config), non toccare un modello. Sotto questa luce il
> rischio è più piccolo di quanto temevi: riusare la tua logica generale (i
> pattern che scrivi tu) fra clienti è normale riuso di codice, non uso
> improprio dei loro dati — il problema vero si porrebbe solo se un giorno
> allenassi un modello condiviso sulle geometrie/testi letterali di più
> clienti senza dirglielo, cosa che oggi non è nemmeno nel piano. Se mai ci
> arrivi, resta valida la risposta di prima: dichiaralo, anche in una riga di
> contratto, invece di farlo di nascosto.

All'interno di ciascuno, tre operazioni distinte convivono (schema utile,
venuto dal confronto con ChatGPT):

- **Determinismo** — "se do X, applicando questa operazione ottengo sempre
  Y". Proprietà dell'*esecuzione*, non una categoria di funzioni. `heal`,
  `detect`, `bridge_tabs`, `detect_frame` sono tutti deterministici dati i
  loro parametri, pur vivendo in domini diversi.
- **Interpretazione** (Federico ha proposto *"Giudizio?"* — la tengo com'era:
  "giudizio" è più vicino al passo successivo, *Correzione*, che decide
  un'azione; "interpretazione" resta la parola giusta per "cosa rappresenta
  X", un passo prima di decidere cosa farci) — sempre con `source` +
  `confidence`, mai una supposizione spacciata per fatto.
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
| `to_dxf` / `to_svg` / `save_json` | export fedele dal modello — il risultato consegnato, sia per preventivo che per produzione |

Un consumatore può fermarsi a `heal` e fare tutto il resto a modo suo. Questo
non è solo teoria: `heal()`/`detect()` sono separati e pubblici apposta
(MAP.md D2) — forge stesso è già una cassetta degli attrezzi, non una
pipeline forzata. Un disegno vero non dice in anticipo se va splittato, se ha
più viste, se ha una cornice: un agente lo scopre passo passo e sceglie lui
quali strumenti chiamare, non esegue una sequenza scritta a tavolino per "il
disegno tipico".

> **Nota (Federico): `detect` è "determinismo più overfittato"??**
> **Risposta:** no, e vale la pena separarli bene. Overfitting è una proprietà
> di qualcosa che *impara* da dati e cattura il rumore invece del segnale
> generale. La soglia di `detect` (32.1mm per i fori, MAP.md D15) non impara
> niente — è un default generico dichiarato, che il chiamante può sovrascrivere
> per macchina/utensile. Resta un parametro scelto consapevolmente, non un
> valore appreso su un cliente specifico. Categoria diversa da `profiles/`.
>
> **Nota: `split`/`split_to_files` è un task molto specifico, oggi utile
> soprattutto per il flusso di un certo tipo di cliente/disegno (un file con
> più pezzi annidati) — un agente potrebbe riconoscere "questo è quel tipo di
> disegno, non sprecare energia su altre interpretazioni, splitta e basta".**
> **Risposta:** giusto, ed è un buon esempio concreto della "cassetta degli
> attrezzi non pipeline fissa" di cui parla il paragrafo sopra e sotto — non è
> un'idea a parte, è esattamente quel comportamento.
>
> **Nota: non vedo come `inspect` possa servire a un agente, spiegami come.**
> **Risposta: hai ragione più che torto.** Il suo stesso docstring lo dice:
> "pensato per il debug... senza leggere il codice" — stampa report testuali
> con `print`, pensato perché un umano lo legga a schermo mentre indaga un
> file che si comporta in modo strano. Un agente che sa eseguire codice
> potrebbe comunque lanciarlo e leggerne l'output come fa un umano, per
> autodiagnosi quando un risultato sembra sbagliato ("perché questo file non
> è guarito bene?") — ma resta un ripiego di debug, non un passo della
> pipeline normale di lettura di un disegno.


## framer — il lettore di documentazione (ambito allargato)

> **Nota (Federico): probabilmente da rinominare pesantemente, i nomi mi
> stanno facendo venire l'ansia.**
> **Risposta:** segnato — stesso filone della discussione sul brand di
> stasera, non lo risolvo qui per non forzarti a deciderlo in mezzo al resto.
> Framer che allarga il mandato oltre cornice/cartiglio è un motivo in più
> per rivederne il nome quando ci torni sopra, non un'urgenza di per sé.
>
> **Nota: capisce anche che tipo di cliente è??**
> **Risposta:** oggi no, ed è un pezzo mancante reale, non ancora in questo
> documento — grazie per averlo fatto notare. È diverso da tutto il resto di
> framer: non "leggere cosa c'è scritto" ma "riconoscere DI CHI è questo
> disegno" (dal layout del cartiglio, dai pattern dei callout, magari da un
> nome di blocco ricorrente) e scegliere il `ShopProfile` giusto invece di
> farselo dire dal chiamante. Non può stare in framer (framer non tocca dati
> privati di cliente) — è un passo dell'interprete, che confronta contro i
> `profiles/` che già possiede. L'ho aggiunto alla tabella dei moduli
> dell'interprete più sotto (`profile_matching`).

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

> **Nota (Federico): è fattibile davvero?**
> **Risposta:** fattibile sì, nello stesso senso in cui lo è stato il
> rilevamento di cornice — pattern geometrici con soglie esplicite, non
> serve machine learning. Ma è onestamente **il pezzo più a rischio di
> tutta questa roadmap**, perché è l'unico senza un prototipo funzionante
> già verificato (la cornice ce l'ha, D3/D5). La casistica reale delle
> viste spezzate/linee di rottura è più varia di un cartiglio (che è quasi
> sempre un rettangolo a griglia). Non lo eviterei per questo — lo
> tratterei con più cautela: prima i disegni veri, poi il codice, pronto a
> scoprire che il primo tentativo va rifatto, come è successo a framer D5.

Nessuno di questi tocca forge oltre a leggerne l'output e a riassegnare ruoli
via `edge.role` prima di `heal` (l'interfaccia già chiusa in forge D30,
verificata da framer D2/D6 — il punto sperimentale vero di questo lavoro, e
resta il contributo più prezioso finora: riusabile paro paro da bendly se un
giorno gli servirà).

Stato reale: framer è pre-alpha, non ha ancora un repo GitHub remoto, non ha
fixture reali in `tests/examples/`. Un solo pezzo dei cinque sopra è fatto.


## L'interprete — ridotto a quello che è davvero privato

> **Nota (Federico): "giudice"?**
> **Risposta:** ci ho pensato — solo in parte. Tradurre nomenclatura e
> incrociare con l'ERP non è "giudicare", è lookup/mappatura. Segnalare
> `flags`/`unresolved` quando qualcosa non torna è più vicino a un giudizio.
> Tengo "l'interprete": copre meglio l'insieme, "giudice" ne descrive solo un
> pezzo.
>
> **Nota: è qui che entra in gioco l'addestramento? Si può addestrare un
> agente? Come cazzo si fa? Cos'è un agente?**
> **Risposta, con calma perché sono domande vere:** "agente" qui — Pippo, o
> me stesso in questa conversazione — non è una rete neurale che addestri tu
> da zero. È un modello linguistico già addestrato da altri (Claude, o
> equivalenti) a cui dai **strumenti da chiamare** (forge, framer, le
> funzioni dell'interprete) e **contesto strutturato da leggere** (il
> `ShopProfile`, l'output di forge/framer con `source`/`confidence`). Il
> "ragionare" lo fa il modello generale, che il ragionamento sa già farlo in
> generale — tu non lo insegni da capo.
>
> "Addestrare" in questa architettura, quasi sempre, **non** significa
> riallenare pesi di rete. Significa affinare il `ShopProfile`: aggiungere un
> pattern regex che prima mancava, correggere una tabella di nomenclatura,
> aggiustare una soglia. È lavoro tuo, esplicito, su file di config — non
> gradient descent. Solo in una fase molto più avanzata potrebbe avere senso
> allenare un modellino piccolo e specifico (es. "riconosci automaticamente
> di che cliente è questo disegno") — un progetto a parte, minuscolo rispetto
> a "addestrare l'agente", e comunque non necessario per far funzionare
> Pippo oggi. Vedi anche la nota più giù su `Addestramento` e quella ancora
> dopo (l'analogia del disegnatore) — insieme rispondono a questa per
> intero, ce l'hai fatta a spiegartelo da solo mentre scrivevi.

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
| `profile_matching.py` | riconosce **di chi** è il disegno (layout cartiglio, pattern callout) e sceglie il `ShopProfile` giusto, invece di farselo dire dal chiamante. Idea di Federico, non ancora nel resto del documento prima di questa revisione |
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

> **Nota (Federico): non lo so se ho capito...**
> **Risposta, in concreto:** per ogni disegno che passa nella pipeline tieni
> 4 file — cosa ha estratto forge, cosa ha letto framer, cosa ha indovinato
> l'interprete, e cosa era **davvero giusto** (tu che correggi l'output).
> Confrontando "l'interprete ha detto X" con "in realtà era Y" su tanti
> disegni dello stesso cliente, vedi DOVE sbaglia sistematicamente — es.
> "perde sempre questa notazione del materiale" — e aggiusti il pattern nel
> suo `ShopProfile`. Tutto qui: è un ciclo correggi-e-aggiusta-la-config, non
> matematica nascosta. Hai capito bene.

### Domanda aperta

L'agente sta **sopra** l'interprete (lo usa come tool), o **è** l'agente a
chiamare forge/framer/nomenclatura direttamente, senza un "interprete" come
prodotto a sé? Non decisa — dipende da quanto la parte di traduzione privata
finisce per pesare in pratica.

> **Nota (Federico):** ho cercato di spiegarlo qui sopra in alcuni punti. Io
> lo vedo come un agente che già per i cazzi suoi sa il fatto suo, e continua
> ad imparare, e in alcuni casi si "overfitta" su un cliente. Come uno che ha
> fatto un corso di disegno su PC ed entra in azienda: sa usare il software
> in generale, e intanto impara sui disegni dei vari clienti, man mano li
> capisce sempre di più, e intanto impara nuove cose e a utilizzare il
> software meglio. E magari dà feedback agli sviluppatori per
> migliorare/velocizzare il software.
>
> **Risposta: l'analogia è buona, tienila — con una precisazione che conta.**
> Il disegnatore neoassunto che "sa già il mestiere in generale" = il modello
> generale (Claude o equivalente): il ragionamento di base non lo insegni tu,
> è già lì. Quello che il disegnatore impara *sul lavoro, cliente per
> cliente* = il `ShopProfile` che affini tu, esattamente come nella nota
> sopra. Il "dare feedback agli sviluppatori per migliorare il software" =
> letteralmente questa conversazione di stasera: tu che scopri un caso reale
> (le linguette, i disegni spezzati) e io/te che aggiustiamo forge/framer di
> conseguenza. Tutti e tre i pezzi della tua analogia hanno già un posto
> preciso in questo documento.
>
> La precisazione: a differenza del disegnatore, la "bravura generale" del
> tuo agente (il modello sotto) non è qualcosa che TU alleni o possiedi —
> quella è di chi ha costruito il modello. Quello che costruisci e possiedi
> tu è tutto il resto: la cassetta degli attrezzi (forge/framer) e la
> libreria di profili per cliente. Non è un limite — è in realtà una buona
> notizia per uno che lavora da solo: non devi costruire il cervello, solo
> l'officina e il know-how che ci gira intorno, che è già abbastanza.


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

> **Nota (Federico): sono più che d'accordo — si scarica la cassetta degli
> attrezzi e la si consegna al cliente. Cosa si passa al cliente? L'agente
> overfittato? Come si fa a non passare l'overfitting di un cliente a un
> altro? Ci sono sub-agenti, con un agentone che intanto impara da tutti?**
> **Risposta:** più semplice di quanto sembri, proprio perché "overfittare"
> qui vuol dire "un file di config dedicato", non "un modello dedicato" (vedi
> le due note sopra). Quello che consegni al cliente è: forge + framer (lo
> stesso codice per tutti, generico) **più** il `profiles/<questo-cliente>`
> — un file suo, separato per costruzione dai file degli altri clienti. Non
> passi "l'agente overfittato": il modello resta uno solo e generale (Claude
> o equivalente), è il profilo di config a essere specifico. "Non passare
> l'overfitting di un cliente a un altro" è già risolto dalla separazione dei
> file, non serve inventare sub-agenti per questo.
>
> L'"agentone che impara da tutti in background" è un'idea diversa e
> separata — quella sì che tocca la domanda etica della prima nota di
> stasera (usare dati di più clienti per migliorare qualcosa di condiviso).
> È facoltativa, è successiva, e non ti serve per consegnare il primo
> cliente: puoi costruire e vendere "cassetta + profilo" senza mai
> affrontarla, e deciderla con calma se e quando diventa un'idea concreta,
> non un'implicazione automatica di come funziona oggi.
- guessing non etichettato con `source` + `confidence`
- logica di un singolo cliente fuori dai `profiles/`
- modifiche a forge per far comodo a framer o all'interprete: forge resta
  neutro, sono loro ad adattarsi
