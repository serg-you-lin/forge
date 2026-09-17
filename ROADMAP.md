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
pieghe). Non chiede — non subito — di ricongiungere viste spezzate o leggere
la scala. Quella roba serve alla produzione, non al preventivo. NON è VERO, SE IO DEOV SPERE QUANTE LAMIERE COMPERARE, DEVO SAPERE IN CHE SCALA è IL DISEGNO, A PARTIREE DALLA PREVENTIVAZIONE. CAZZO.



## Chi fa cosa — quattro pezzi, non settanta moduli

| pezzo | di cosa si occupa | dove vive |
|---|---|---|
| **forge** | il pezzo fabbricato: geometria, topologia, feature (fori/pieghe/incisioni), conteggi (`cluster.summary`) | `dxf-forge`, maturo |
| **framer** | come il disegno è documentato: cornice, cartiglio, callout, raggruppamento viste | `framer`, pre-alpha, un pezzo su cinque fatto |
| **l'interprete** | nomenclatura privata del cliente, profili, riempimento buchi da ERP | non esiste ancora un repo — e forse non gli serve nemmeno, vedi `INTERPRETER.md` | NON HO CAPITO COSA INTENDI
| **bendly** | sviluppo lamiere — direzione opposta (da specifica a DXF), oracolo di verifica in futuro | `unfold_generator`, alpha, già in uso |

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

1. **(forge, piccolo)** `snap_distance` anche su `inject()` — stessa logica
   già scritta per `anchor_annotations`, la stessa piccola tolleranza.
2. **(tuo, privato)** scrivi il `data_injector` per il primo cliente che ti
   interessa — regex/pattern per material/thickness/qty/code. Non va nel
   repo pubblico (`forge-reports-drawing-never-guesses-no-shop-nomenclature`).
3. **A questo punto hai già un primo Pippo-per-preventivi**, su forge da
   solo: `heal_and_detect` → `inject(data_injector=...)` →
   `cluster.summary` per la complessità. Nessun modulo nuovo, nessun repo
   nuovo.
4. **(forge)** `Dimension.references` / `Leader.target` — solo quando ti
   serve davvero incrociare una quota con la feature che quota, non prima.
5. **(framer)** cartiglio — quando ti serve leggere i metadati generali del
   disegno oltre al singolo pezzo (numero disegno, revisione), non prima.
6. **(framer, ultimo, il più incerto)** raggruppamento viste / linee di
   rottura — solo quando il caso reale lo chiede, e solo dopo aver guardato
   disegni veri (stessa lezione di framer D5: non scriverlo a tavolino).

I passi 4-6 servono alla produzione più che al preventivo — restano nella
roadmap, ma dopo, non prima.
