# ROADMAP — la strada verso Pippo, in breve

Non è un doppione di `INTERPRETER.md` (quello resta il "come e perché" di
ogni pezzo). Questo è il foglio corto: chi fa cosa, cosa c'è già, cosa manca
davvero, in che ordine. Se ti perdi tra i dettagli, riparti da qui.


## Il traguardo, con le tue parole

**Pippo**: un agente addestrato/tarato su uno **stock di disegni di un
cliente specifico** (non "un agente generico per qualsiasi disegno del
pianeta" — un agente che impara le convenzioni di UN cliente alla volta,
esattamente il `ShopProfile` già previsto). Il caso d'uso principale, almeno
per ora: **preventivazione**, non (solo) produzione. Questo conta: cambia
cosa costruire prima.

Preventivare bene chiede soprattutto: materiale, spessore, quantità, codice
pezzo, e una stima di complessità (numero fori, lunghezza taglio, numero
pieghe). Non chiede — non subito — di ricongiungere viste spezzate. Sulla
scala, vedi la nota sotto: qui la frase originale era imprecisa.

> **Nota (Federico): "leggere la scala" non è roba da produzione — se devo
> sapere quante lamiere comprare, devo sapere in che scala è il disegno, a
> partire dalla preventivazione.**
> **Risposta: hai ragione, la frase era sbagliata — corretta sopra.** Ma vale
> la pena separare due cose che ho impastato:
>
> 1. **Le coordinate che forge misura sono già a scala reale.** Un file DXF
>    ben fatto è disegnato in model space 1:1 — la "scala" (Drawing
>    Scale/View Scale/DIMSCALE, vedi `INTERPRETER.md`) è un fattore di
>    stampa/annotazione, non una trasformazione della geometria. Quindi il
>    bbox di un cluster che `heal` produce è già la dimensione vera del
>    pezzo — non c'è un passo "leggi la scala e converti" da fare in più.
>    Questo pezzo della frase originale (non serve un modulo apposta per
>    "interpretare la scala") resta vero.
> 2. **Ma "è già a scala reale" è un'assunzione, non una garanzia — e
>    proprio per il preventivo non te la puoi permettere.** Un file scalato
>    male all'origine, o disegnato volutamente non in scala, ti fa comprare
>    la lamiera sbagliata senza che nulla lo segnali. Il modo economico per
>    proteggersi è quello che il documento chiama già "gap noto" —
>    `Dimension.references`/verifica quota-vs-geometria-misurata — e questo
>    **non è roba da produzione, è roba da preventivo esattamente come dici
>    tu.** Quindi il passo 4 sotto ("solo quando ti serve davvero
>    incrociare una quota", trattato come produzione) va corretto: quando
>    c'è almeno una quota scritta sul disegno, un controllo minimo — la
>    geometria misurata concorda con quella quota, sì/no — va fatto **prima**
>    di fidarti del bbox per comprare materiale, non dopo. Vedi step 0 più
>    sotto.



## Chi fa cosa — quattro pezzi, non settanta moduli

| pezzo | di cosa si occupa | dove vive |
|---|---|---|
| **forge** | il pezzo fabbricato: geometria, topologia, feature (fori/pieghe/incisioni), conteggi (`cluster.summary`) | `dxf-forge`, maturo |
| **framer** | come il disegno è documentato: cornice, cartiglio, callout, raggruppamento viste | `framer`, pre-alpha, un pezzo su cinque fatto |
| **l'interprete** | nomenclatura privata del cliente, profili, riempimento buchi da ERP | non esiste ancora un repo — e forse non gli serve nemmeno, vedi `INTERPRETER.md` |
| **bendly** | sviluppo lamiere — direzione opposta (da specifica a DXF), oracolo di verifica in futuro | `unfold_generator`, alpha, già in uso |

> **Nota (Federico): "forse non gli serve nemmeno [un repo]" — non ho capito
> cosa intendi.**
> **Risposta:** non "l'interprete non ti serve" (quello ti serve di sicuro:
> nomenclatura, profili, ERP restano privati per forza). Intendevo: forse non
> ti serve un **repo/progetto vero e proprio con un orchestratore** —
> `pipeline.py` che chiama forge poi framer poi traduzione in sequenza
> fissa. Perché una volta tolto tutto quello che è finito in framer, quello
> che resta dell'interprete è poca roba: un paio di file Python privati
> (`nomenclature.py`, `profiles/`) con dentro le tue tabelle e i tuoi
> pattern. È abbastanza sottile che potrebbe bastarti chiamare quelle
> funzioni direttamente da dove oggi chiami forge, senza costruire un
> pacchetto a parte che le orchestra. Il dettaglio è nella "Domanda aperta"
> di `INTERPRETER.md`, sezione "L'interprete": non è deciso, resta
> intenzionalmente aperto finché non vedi quanto pesa in pratica la parte di
> traduzione privata.

Tutto il resto (Determinismo/Interpretazione/Correzione, il confine
manifattura/documentazione/privato) è spiegazione del *perché* questa tabella
è fatta così — sta in `INTERPRETER.md`, non serve ripeterlo qui.


## Scoperta di stasera: il preventivo è più vicino di quanto sembrasse

Rileggendo `forge/tools/inject.py` per rispondere a "cosa fa il parser
regex": **non devi aspettare che framer costruisca `callouts.py`.**
`forge.inject(result, data_injector=una_tua_funzione)` esiste già, maturo,
testato — raccoglie i testi dentro l'outer di ogni pezzo e li passa a una
funzione che scrivi tu (privata, mai nel repo), che ritorna
`{material, thickness, quantity, code}`. Il "parser regex per i callout" di
cui parlavamo non è un modulo da costruire — è la funzione `data_injector`
che scrivi oggi, per il cliente che ti interessa oggi, e la passi a una API
che già c'è.

**Gap piccolo trovato mentre verificavo questo**: `inject()` ricontrolla il
contenimento per conto suo (`_texts_inside`) e non ha lo `snap_distance` che
invece ha `anchor_annotations` — quindi il problema del testo "leggermente
fuori dall'outer" di prima, se usi `inject()` per i preventivi, ti si
ripresenta lì. Piccola aggiunta, non un nuovo modulo — la metto in coda
sotto, non l'ho toccata senza dirtelo.


## Ordine consigliato (per il preventivo, non per Pippo intero)

0. **(forge)** `Dimension.references`/`Leader.target` — non per incrociare
   feature e quota in produzione, ma per il controllo minimo "preventivo":
   quando c'è almeno una quota scritta, la geometria misurata concorda?
   Spostato qui dal vecchio punto 4 dopo la nota sulla scala sopra — è
   preventivo, non produzione.
1. **(forge, piccolo)** `snap_distance` anche su `inject()` — stessa logica
   già scritta per `anchor_annotations`, la stessa piccola tolleranza.
2. **(tuo, privato)** scrivi il `data_injector` per il primo cliente che ti
   interessa — regex/pattern per material/thickness/qty/code. Non va nel
   repo pubblico (`forge-reports-drawing-never-guesses-no-shop-nomenclature`).
3. **A questo punto hai già un primo Pippo-per-preventivi**, su forge da
   solo: `heal_and_detect` → controllo quota (step 0, se presente) →
   `inject(data_injector=...)` → `cluster.summary` per la complessità.
   Nessun modulo nuovo, nessun repo nuovo.
4. **(framer)** cartiglio — quando ti serve leggere i metadati generali del
   disegno oltre al singolo pezzo (numero disegno, revisione), non prima.
5. **(framer, ultimo, il più incerto)** raggruppamento viste / linee di
   rottura — solo quando il caso reale lo chiede, e solo dopo aver guardato
   disegni veri (stessa lezione di framer D5: non scriverlo a tavolino).

I passi 4-5 servono alla produzione più che al preventivo — restano nella
roadmap, ma dopo, non prima.
