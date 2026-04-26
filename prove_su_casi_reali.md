V    poligono chiuso semplice ----    rect_lines
V    poligono con spigoli raggiati   ----   rettangolo_raggiato
V    poligono con poligono interno  ----   rect_with_hole
V    poligono con foro   ----  rettangolo_foro_centrale
V    flangia tonda forata  ---- flangia_con_fori
V    flangia quadrata con fori   ----  flangia_quadra
V    fori di diverse dimensioni ----  fori_spuri
V    poligono con arco convesso   ---   arco_convesso
V    linee di piegatura da centro lato  ----- Linee_piegatura
V    linee di piegatura dagli angoli  --- linee_di_piegatura_interne
V    poligono già polilinea con marcatura interna   ---  polilinea_con_marcatura
V    dxf ceh mi aveva fatto dannare l'anima con fori e marcatura   -----  la_104   -----> 
V    file dxf vecchio   -----   older_dxf_type
V    spline interna    -------    quadro_fori_spline
V    parte di poligono spline    -----     poly_spline_parts
V    poligono arco + linee + fori centrali   ------   archi_bastardi
V    linea + arco > 180°   ----- flangia_scantonata
V    profilo con tanti cambiamenti di direzione rettangolare + fori interni  -------   intricato
V    test su vari layer per vedere se funzionano i filtri su layer    ------    rect_with_special_layers
V    test con linee spazzatura per testare il trash collect    -----   rect_with_trash
spline + linea che chiude   -----   spline_line
spline + linea che chiude e aperture interne   -----   spline_line_fori
spline intera   ------  spline_completa
spline intera con aperture interne    -----   spline_fori
spline + linee con gap tra spline e linea   -----   spline_line_gap
profilo non del tutto chiuso    -----   rect_gap
profilo con laot leggermente più lungo del necessario   -----        rect_overlap
profilo con gap a linee parallele molto ravvicinate    -----     gap_parallelo
profolo in diagonale con archi ad inizio e  fine e aperture interne   -------   maniglia
poligoni ambigui (non deve funzionare, deve dare un warning)   ------   F6
rettangolo con lato non chiuso (non deve funzionare)    ------ rect_3_sides
trapezio con base maggiore non chiusa (non deve funzionare)    ------     trapezio_3_sides