arc_open.dxf --> Entità materializzate, ma gap non colmato. Bisogna improvare il gapper tra archi?  se il loro allungamento non produce punti di contatto? cosa fanno oggi gli archi di un eventualo outer che si intersecano? devono dare invalido imho, e non generare il file come quando non c'è un outer.

archi_si_no.dxf  --> in teoria dovrebbe riconoscere gli archi come profilo outer e mettere il percorso 'lungo'  che ora è outer in trash. Ok, è complicato ed è da raginarci, può essere una cosa opzionale? lasciamolo li per ora,m accettiamolo così. Occho perchp sefacciamo come dico io abbiamo le regressioni con le bending line, perchè il grafo gira prima.
F6.dxf  --> caso edge, va gestito con le tolleranze. con il validator e i cech si nodi ambigui che abbiamo aggiunto di recente mi aspettavo qualche warning, come faccio ad ottenerlo con quello che ho ora? comunque caso buono se si vuole creare un'interfaccia.

Fu.dxf --> Le linee di engraving non si vedono, si vedono solo i punti. vengono esportati solo i punti al posto degli edge? inoltre, verificare se la lunghezza degli elementi engrave siano conteggiati per i metadati
la_104.dxf  --> vedere fu.dxf

multifeature.dxf  --> un file con tutti i tipi di feature, generato apposta per poter testare i vari comportamenti.  le entità sono modificate, difatt il e linee tratteggiate non sono più tratteggiate. imho la tipologia di linea deve essere gestita, e mantenuta nel dxf output. Teniamo conto hce il role dovrà poter esesre individuato acnhe da tipo linea e colore, quindi direi che è roba che serve e a quel punto prendiamo due piccioni con una fava. E c'è anceh qui il problema degli engrave
    [A-bis v2] quote e frecce di sezione RECUPERATE: le 16 DIMENSION le cancellava l'auditor di ezdxf (nessun blocco geometria) -> ora estratte prima di audit() + ricostruite dai def-point; i 4 LEADER non avevano repr point -> posizione dal bbox. Restano fuori scope: linetype tratteggiati (Cluster E), engrave (Cluster D).

rect_special_conutersink.dxf --> il countersink viene rilevato e il foro è sul layer corretto,  non è presente nel dxf esportato. capire se si può opzionalmente fare in modo che i benedetti esterni del foro possano opzionalmente essere messi su un layer a parte, di modo che se uno vuole trattarli in CAM in modo diverso può farlo ma è opzionale e non bloccante
rect_with_secial_layers.dxf --> ci sono 3 linee, 2 su bend e 1 su mark. ho runnato con special_layers = 
    "MARK"      : "engrave" eccetera, le linee di bend NON vanno in bend, vano in trash, è una regressione recente, quella di mark non c'è, non è presente e non capsico il motivo. bisognerebeb indagare un giorno, perhèc potrebbe essere messa tra le candidate bend a mio parere dato che va da parte a parte....
rect_with_threadad_holes_geometric.dxf --> fori rilevati correttamente e posti sul layer giusto, archi in trash. Capire se con la rilevazione semantica non sia bello piazzare l'arco esterno per unificarlo a livello di disegno, un reverse-geometric feature. Non bloccante e forse non necessario, solo un'ipotesi.


two_rects_with_bend.dxf   --> uno dei due rect ha una bl interna i cui ep non combaciano con l'outer per 10mm. ho prevato a fare il detect aumentando la bending tol a 11, ma non viene comunque individuata come bending, quella entità. entità in trash.



file rotti mi sa dopo implementato epsilon nei nodes per il graph
6200012964_lineette_bastarde.dxf -->  Bending lines non detectate, vanno in trash. non capisco come i test possano essere verdi, ma i test che abbimamo hanno senso?
6200012967_AMBIGUO.dxf --> idem come sopra.