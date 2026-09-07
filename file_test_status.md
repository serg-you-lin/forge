arc_open.dxf --> RISOLTO (F3): a tolleranza default nessun outer chiude -> is_valid=False + errore, to_dxf/split sollevano, nessun file. A tolerance >= 0.3 il gap arco/arco si chiude (1 cluster). Archi auto-intersecanti / prolungamenti che non si toccano: fuori scope, oggi assorbiti da F3 (nessun loop -> invalido).

archi_si_no.dxf  --> in teoria dovrebbe riconoscere gli archi come profilo outer e mettere il percorso 'lungo'  che ora è outer in trash. Ok, è complicato ed è da raginarci, può essere una cosa opzionale? lasciamolo li per ora,m accettiamolo così. Occho perchp sefacciamo come dico io abbiamo le regressioni con le bending line, perchè il grafo gira prima.
F6.dxf  --> caso edge, va gestito con le tolleranze. con il validator e i cech si nodi ambigui che abbiamo aggiunto di recente mi aspettavo qualche warning, come faccio ad ottenerlo con quello che ho ora? comunque caso buono se si vuole creare un'interfaccia.


multifeature.dxf  --> un file con tutti i tipi di feature, generato apposta per poter testare i vari comportamenti.  le entità sono modificate, difatt il e linee tratteggiate non sono più tratteggiate. imho la tipologia di linea deve essere gestita, e mantenuta nel dxf output. Teniamo conto hce il role dovrà poter esesre individuato acnhe da tipo linea e colore, quindi direi che è roba che serve e a quel punto prendiamo due piccioni con una fava. 
    [A-bis v2] quote e frecce di sezione RECUPERATE: le 16 DIMENSION le cancellava l'auditor di ezdxf (nessun blocco geometria) -> ora estratte prima di audit() + ricostruite dai def-point; i 4 LEADER non avevano repr point -> posizione dal bbox. Restano fuori scope: engrave (Cluster D, poi risolto).
    [Cluster E] RISOLTO: le 64 LINE assiali CENTER (trash) ora escono tratteggiate, non più continue -- linetype captato dall'adapter e ripristinato in output su tutta la geometria. Colore invariato ovunque, trash compreso (decisione: solo lo stile va preservato, non il colore -- il trash resta rosso Trash).

rect_special_conutersink.dxf --> il countersink viene rilevato e il foro è sul layer corretto,  non è presente nel dxf esportato. capire se si può opzionalmente fare in modo che i benedetti esterni del foro possano opzionalmente essere messi su un layer a parte, di modo che se uno vuole trattarli in CAM in modo diverso può farlo ma è opzionale e non bloccante

rect_with_threadad_holes_geometric.dxf --> fori rilevati correttamente e posti sul layer giusto, archi in trash. Capire se con la rilevazione semantica non sia bello piazzare l'arco esterno per unificarlo a livello di disegno, un reverse-geometric feature. Non bloccante e forse non necessario, solo un'ipotesi.


two_rects_with_bend.dxf   --> uno dei due rect ha una bl interna i cui ep non combaciano con l'outer per 10mm. ho prevato a fare il detect aumentando la bending tol a 11, ma non viene comunque individuata come bending, quella entità. entità in trash.


6200013103_P1NoLineaPiega.dxf  --> file cliente reale (Solid Edge), 6 pezzi, ognuno sul proprio layer 6200013103_1..5 + info per pezzo nei 16 MULTILEADER (CODICE / SPESSORE / PEZZI N°) e 3 MTEXT cartiglio. Aggiunto come fixture perché espone il bug leader-solo-testo (MULTILEADER senza anchor né vertici né geometria venivano scartati in extract -- RISOLTO in b5b2503, ripiego sulla posizione del testo appiattito; golden annotazioni a guardia).
    BUG NOTO 1 (bending): il pezzo _1 (layer 6200013103_1, MULTILEADER "CODICE: 6200013103_1", cluster area ~127826, bbox ~[30,45,560,825]) genera 1 sola bending line dove Federico se ne aspetta di più. Causa sconosciuta -- da indagare. Il nome del file ("NoLineaPiega") già segnala l'anomalia.
    BUG NOTO 2 (cartiglio come parte): il riquadro del cartiglio (blocco Cartiglio_sviluppo esploso, rettangolo 80x55 mm a ~[41,36]) viene rilevato come parte -> cluster_count = 6 invece di 5. Di conseguenza i 3 MTEXT del cartiglio ("Materiale...", "Codice Articolo...") prendono cluster_ref = 5 in interpret_annotations invece di None. Serve una regola per scartare cartigli / riquadri dalla detection parti (o ignorare il layer Default), non ancora fatta.
    I golden (json/, golden_multipli/, annotations/) catturano l'output attuale: per questa fixture i conteggi bending_lines, cluster_count e i cluster_ref dei testi cartiglio NON sono ground truth finché i due bug non sono chiariti.


