arc_open.dxf --> RISOLTO (F3): a tolleranza default nessun outer chiude -> is_valid=False + errore, to_dxf/split sollevano, nessun file. A tolerance >= 0.3 il gap arco/arco si chiude (1 part). Archi auto-intersecanti / prolungamenti che non si toccano: fuori scope, oggi assorbiti da F3 (nessun loop -> invalido).

archi_si_no.dxf  --> in teoria dovrebbe riconoscere gli archi come profilo outer e mettere il percorso 'lungo'  che ora è outer in trash. Ok, è complicato ed è da raginarci, può essere una cosa opzionale? lasciamolo li per ora,m accettiamolo così. Occho perchp sefacciamo come dico io abbiamo le regressioni con le bending line, perchè il grafo gira prima.
F6.dxf  --> caso edge, va gestito con le tolleranze. con il validator e i cech si nodi ambigui che abbiamo aggiunto di recente mi aspettavo qualche warning, come faccio ad ottenerlo con quello che ho ora? comunque caso buono se si vuole creare un'interfaccia.


multifeature.dxf  --> un file con tutti i tipi di feature, generato apposta per poter testare i vari comportamenti.  le entità sono modificate, difatt il e linee tratteggiate non sono più tratteggiate. imho la tipologia di linea deve essere gestita, e mantenuta nel dxf output. Teniamo conto hce il role dovrà poter esesre individuato acnhe da tipo linea e colore, quindi direi che è roba che serve e a quel punto prendiamo due piccioni con una fava. 
    [A-bis v2] quote e frecce di sezione RECUPERATE: le 16 DIMENSION le cancellava l'auditor di ezdxf (nessun blocco geometria) -> ora estratte prima di audit() + ricostruite dai def-point; i 4 LEADER non avevano repr point -> posizione dal bbox. Restano fuori scope: linetype tratteggiati (Cluster E), engrave (Cluster D).

rect_special_conutersink.dxf --> il countersink viene rilevato e il foro è sul layer corretto,  non è presente nel dxf esportato. capire se si può opzionalmente fare in modo che i benedetti esterni del foro possano opzionalmente essere messi su un layer a parte, di modo che se uno vuole trattarli in CAM in modo diverso può farlo ma è opzionale e non bloccante

rect_with_threadad_holes_geometric.dxf --> fori rilevati correttamente e posti sul layer giusto, archi in trash. Capire se con la rilevazione semantica non sia bello piazzare l'arco esterno per unificarlo a livello di disegno, un reverse-geometric feature. Non bloccante e forse non necessario, solo un'ipotesi.


two_rects_with_bend.dxf   --> uno dei due rect ha una bl interna i cui ep non combaciano con l'outer per 10mm. ho prevato a fare il detect aumentando la bending tol a 11, ma non viene comunque individuata come bending, quella entità. entità in trash.


