# topo — code index

**Generated file — do not edit by hand.** Regenerate with:

```
python scripts/gen_index.py
```

What this is: the lookup table of *what already exists* in the package, down to internal helpers. `docs/API.md` documents the public surface (`topo.<name>`) with full cards; this file lists every module-level function and class so nothing gets rewritten because it was not found. Signatures and docstring lines come straight from the source, so they cannot drift.

`77` modules · `405` module-level functions · `57` classes · `14190` lines of code.

Sections: [Lookup](#lookup) · [Duplicate names](#duplicate-names) · [Dependency rule](#dependency-rule) · [By module](#by-module) · [Internal dependencies](#internal-dependencies)

---

## Lookup

Every module-level name in the package, alphabetically. **Search here before writing a new helper.**

| name | kind | location | what |
|---|---|---|---|
| `Adapter` | class | `topo/core/adapter_base.py:23` |  |
| `_adaptive_polyline` | func | `topo/core/primitives/segments.py:317` | Discretizza una curva parametrica valutata da `evaluate(t) -> Point` fra |
| `_add` | func | `topo/tools/tabs.py:55` |  |
| `_add_ellipse` | func | `topo/adapters/dxf/exporter.py:161` | Materializza una EllipseSeg come ELLIPSE nativa — mai una spline: topo |
| `_add_spline` | func | `topo/adapters/dxf/exporter.py:116` | Materializza una SplineSeg come SPLINE nativa, ricostruita dalla primitiva |
| `AddSegment` | class | `topo/core/healing/gap_solver.py:84` | Istruzione: aggiungi un segmento retto tra pt_a e pt_b. |
| `anchor_annotations` | func | `topo/tools/anchor.py:34` | Assegna ``cluster_ref`` a ogni annotazione di ``result.annotations``. |
| `_angle_diff` | func | `topo/core/geometry/shape.py:158` | Differenza fra due direzioni modulo 180, in [0, 90]. |
| `angle_from_start` | func | `topo/core/primitives/segments.py:102` | Angolo, in [0, 2π), da percorrere partendo da `start_angle` nel verso |
| `_angle_of` | func | `topo/core/primitives/trim.py:93` | Angolo (o parametro dell'ellisse) di `pt` visto dal centro della curva. |
| `_angular` | func | `topo/core/primitives/trim.py:104` |  |
| `_angular_deviation` | func | `topo/core/topology/graph.py:345` |  |
| `_angular_sweep` | func | `topo/core/primitives/segments.py:83` | Angolo spazzato in radianti, sempre positivo, percorrendo da `start` a |
| `Annotation` | class | `topo/model/annotation.py:63` | Base di ogni annotazione. ``position`` è il punto d'ancoraggio XY — dove |
| `annotation_anchor` | func | `topo/adapters/dxf/annotation_extractor.py:94` | Punto d'ancoraggio XY di un'entità di annotazione. |
| `_annotation_entry` | func | `topo/io/view_model.py:106` |  |
| `_annotation_signature` | func | `topo/adapters/dxf/loader.py:63` |  |
| `apply_gap_fixes` | func | `topo/core/healing/gap_solver.py:340` | Applica i GapFix restituendo una NUOVA lista di Edge — `edges` non viene mutata. |
| `_apply_role_styles` | func | `topo/io/dxf.py:463` | Applica gli override di `role_styles` (D37) ai layer DXF: crea il layer |
| `_Arc` | class | `topo/core/healing/outer_scan.py:104` |  |
| `arc_angles` | func | `topo/core/geometry/points.py:121` | `(start_angle, end_angle, ccw)` in radianti di un arco che passa per |
| `_arc_chains` | func | `topo/core/healing/normalizer.py:394` | Catene angolari di un gruppo sullo stesso cerchio. Se l'ultima catena |
| `_arc_key` | func | `topo/core/healing/normalizer.py:367` | Chiave del cerchio (centro+raggio) a precisione fissa — v. `_line_key`. |
| `_arc_point` | func | `topo/core/healing/outer_scan.py:131` |  |
| `_arc_s` | func | `topo/core/topology/noding.py:102` |  |
| `arc_seg_to_bulge` | func | `topo/adapters/dxf/exporter.py:77` |  |
| `ArcAround` | class | `topo/core/geometry/shape.py:215` | Un arco concentrico a un cerchio e più grande di lui. |
| `arcs_around` | func | `topo/core/geometry/shape.py:228` | Gli archi di `arcs` col centro entro `tolerance` da `center` e raggio |
| `ArcSeg` | class | `topo/core/primitives/segments.py:129` |  |
| `are_collinear` | func | `topo/core/geometry/lines.py:45` | I tratti `a` e `b` stanno sulla stessa retta infinita: direzioni uguali |
| `_arrival_direction` | func | `topo/core/topology/graph.py:336` |  |
| `_assign` | func | `topo/tools/anchor.py:175` |  |
| `_at` | func | `topo/core/geometry/regions.py:85` |  |
| `axis_aligned_share` | func | `topo/core/geometry/axis.py:238` | Frazione della lunghezza dei `LineSeg` di `segments` orizzontale o |
| `axis_lines` | func | `topo/core/geometry/axis.py:87` | (orizzontali, verticali): i tratti che si scostano dall'asse al più di `eps`; gli altri non compaiono. |
| `AxisLine` | class | `topo/core/geometry/axis.py:73` | Un tratto orizzontale o verticale. |
| `_bbox_center` | func | `topo/adapters/dxf/annotation_extractor.py:467` |  |
| `_bbox_of` | func | `topo/io/view_model.py:116` |  |
| `bridge_nested_tabs` | func | `topo/tools/tabs.py:236` | Cammina `cluster.inners` (che porta `depth`/`parent` per ogni contorno, |
| `bridge_tabs` | func | `topo/tools/tabs.py:98` | Costruisce UNA linguetta fra `child_points` (contorno chiuso, il figlio |
| `bridged_runs` | func | `topo/core/geometry/lines.py:106` | File di due o più tratti sulla stessa retta in cui lo spazio fra un tratto |
| `BridgeTab` | class | `topo/tools/tabs.py:84` | Risultato di un singolo ponte. `*_cut_{a,b}` sono `(punto, indice_lato)` |
| `_bspline_basis_row` | func | `topo/core/geometry/points.py:179` | Le n+1 funzioni di base N_i,p(u) (Cox-de Boor, Piegl & Tiller A2.2). |
| `_bspline_find_span` | func | `topo/core/primitives/segments.py:258` | Indice `i` tale che `knots[i] <= t < knots[i+1]` (ricerca binaria, "The |
| `build_hierarchy` | func | `topo/core/healing/steps.py:372` | Albero di contenimento sui ClosedCurve: ogni radice è un Cluster |
| `build_metadata` | func | `topo/io/exporter.py:23` | Costruisce il dict dei metadati per un Cluster |
| `build_node_graph` | func | `topo/core/topology/graph.py:268` | Costruisce il Graph da list[Edge]. |
| `build_polygon` | func | `topo/core/primitives/polygon_builder.py:19` | Costruisce un Polygon shapely da una lista di primitive geometriche. |
| `_build_tree` | func | `topo/core/healing/hierarchy.py:78` |  |
| `_chain` | func | `topo/core/geometry/regions.py:290` | Pezzi orientati incatenati testa-coda in anelli chiusi. |
| `_chain` | func | `topo/core/healing/normalizer.py:265` | Ordina per `lo` e incatena gli span che si toccano o si sovrappongono: |
| `chord_angle_deg` | func | `topo/core/geometry/measure.py:128` | Angolo (gradi, 0-180°) della corda da `a` a `b`. Modulo 180 perché una |
| `circle` | func | `topo/core/geometry/build.py:52` | Il cerchio di raggio `radius` in `center`. |
| `_circle` | func | `topo/core/geometry/shape.py:82` |  |
| `_circle_as_arc` | func | `topo/core/topology/noding.py:132` | Un cerchio come arco di 360° da `start_angle`: stessa matematica degli archi. |
| `_circle_circle_intersections` | func | `topo/core/geometry/intersections.py:71` | Intersezioni tra due circonferenze. Restituisce 0, 1 o 2 punti. |
| `_circle_line_intersections` | func | `topo/core/geometry/intersections.py:40` | Intersezioni tra la circonferenza (cx, cy, r) e la retta infinita (p1, p2). |
| `CircleSeg` | class | `topo/core/primitives/segments.py:554` | Cerchio geometrico puro. |
| `circular_geometry` | func | `topo/core/geometry/measure.py:150` | (diameter, center) se il contorno è ~circolare, altrimenti (None, None). |
| `_clamp` | func | `topo/core/primitives/trim.py:86` | Un punto appena oltre un estremo (entro tolleranza) sta su quell'estremo. |
| `clean_mtext` | func | `topo/adapters/dxf/mtext.py:18` | Testo semplice da una stringa MTEXT grezza: rimuove i codici di |
| `close_free_gaps` | func | `topo/core/healing/steps.py:134` | Chiude i gap fra estremi liberi entro `tolerance` col gap solver |
| `close_near_full_arcs` | func | `topo/core/healing/steps.py:97` | Un ArcSeg coi due capi liberi diventa CircleSeg (stesso centro e raggio) |
| `_close_self_loop` | func | `topo/core/topology/graph.py:252` | ArcSeg il cui sviluppo (raggio*sweep) supera epsilon -> CircleSeg (loop degenere vero). Altrimenti `None` (sl… |
| `ClosedCurve` | class | `topo/model/curve.py:48` | Curva chiusa: ha un polygon e una lista di segmenti. |
| `_closest_to` | func | `topo/core/geometry/intersections.py:95` | Restituisce il punto più vicino a ref tra i candidati. |
| `_cluster` | func | `topo/core/island.py:287` |  |
| `Cluster` | class | `topo/model/cluster.py:15` |  |
| `cluster_passes_min_area` | func | `topo/io/dxf.py:157` | True se la parte supera la soglia di area minima (min_area <= 0 = nessun filtro). |
| `cluster_points` | func | `topo/core/topology/graph.py:189` | Raggruppa punti 2D entro `epsilon` e restituisce {punto -> rappresentante}. |
| `cluster_values` | func | `topo/core/geometry/axis.py:55` | I valori ordinati, tenendo per ogni gruppo il più piccolo: un valore entro |
| `_collect_inners` | func | `topo/core/healing/hierarchy.py:112` | Appiattisce l'albero di contenimento in `cluster.inners` (ogni discendente |
| `CollinearRun` | class | `topo/core/geometry/lines.py:94` | Tratti sulla stessa retta, in fila lungo di essa. |
| `color_for_layer` | func | `topo/adapters/dxf/layers.py:58` | Colore DXF canonico per un layer. |
| `_color_index` | func | `topo/model/role_rule.py:105` | Intero ACI da intero, stringa numerica ("4") o nome standard ("cyan"). |
| `compute_gap_fixes` | func | `topo/core/healing/gap_solver.py:174` | Calcola i GapFix fra gli endpoint liberi entro tolerance. I due capi |
| `concentric_groups` | func | `topo/core/geometry/shape.py:192` | Partizione dei contorni circolari di `items` per centro: ogni cerchio sta |
| `ConcentricGroup` | class | `topo/core/geometry/shape.py:175` | Contorni circolari con lo stesso centro, dal raggio minore al maggiore. |
| `_configure_odafc` | func | `topo/adapters/dxf/loader.py:107` | Punta l'addon `odafc` all'eseguibile ODA File Converter. |
| `_continues` | func | `topo/core/geometry/shape.py:275` | `seg` prosegue `prev` sulla stessa curva, nello stesso verso? |
| `_contour` | func | `topo/core/island.py:382` | Il poligono resta quello dei pezzi della rete piana; i segmenti sono |
| `Contour` | class | `topo/model/contour.py:36` |  |
| `_contour_entry` | func | `topo/io/view_model.py:48` |  |
| `contour_minus` | func | `topo/core/geometry/regions.py:307` | L'anello `contour` meno la regione chiusa `region` (tutti e due anelli di |
| `contour_shape` | func | `topo/core/geometry/shape.py:63` | Forma di un contorno chiuso (`Contour`, o qualunque oggetto con |
| `ContourPoint` | class | `topo/core/geometry/regions.py:214` | Dove cade un punto su un contorno. |
| `ContourRole` | class | `topo/model/role.py:43` | I tre ruoli che il motore topologico conosce. **Non esaustivo** — un |
| `ContourShape` | class | `topo/core/geometry/shape.py:36` | kind:   circle \| stadium \| rectangle \| polygon \| other |
| `_covered_at` | func | `topo/core/geometry/axis.py:100` |  |
| `covered_rectangles` | func | `topo/core/geometry/axis.py:144` | I rettangoli allineati agli assi con ogni lato coperto almeno per |
| `CoveredRectangle` | class | `topo/core/geometry/axis.py:109` | Un rettangolo allineato agli assi i cui quattro lati sono coperti da tratti. |
| `_crossings` | func | `topo/core/topology/noding.py:154` | Incroci reali (non sul prolungamento) fra `seg` e un cutter. |
| `_cumulative_lengths_closed` | func | `topo/tools/tabs.py:158` | `cum[i]` = distanza cumulata da `points[0]` a `points[i]` (lato i-1->i). |
| `Curve` | class | `topo/model/curve.py:38` | Radice della gerarchia. Porta solo identità semantica e traceability. |
| `cut_by` | func | `topo/core/geometry/regions.py:265` | I pezzi di `segment` fuori (`keep="outside"`) o dentro (`keep="inside"`) |
| `_cutters` | func | `topo/core/topology/noding.py:142` |  |
| `dangling_splines` | func | `topo/core/healing/steps.py:149` | SplineSeg aperte con almeno un estremo non collegato a nient'altro. |
| `dash_line` | func | `topo/core/geometry/lines.py:143` | Il segmento `start`→`end` ridotto a tratti: uno lungo `head` che parte da |
| `deduplicate` | func | `topo/adapters/dxf/sanitize.py:216` | Shortcut: estrae chiavi, trova duplicati, li elimina. |
| `delete_entities` | func | `topo/adapters/dxf/sanitize.py:210` | Elimina le entità dal msp in-place. |
| `_describe_dxf_entity` | func | `topo/inspect.py:104` |  |
| `_describe_segment` | func | `topo/inspect.py:200` |  |
| `detect_corners` | func | `topo/core/geometry/points.py:43` | Per ogni punto, True se l'angolo formato dai due lati adiacenti è sotto |
| `DetectedFeature` | class | `topo/model/detected.py:23` | Contratto minimo di un elemento attaccato a `DetectedFeatures`: la |
| `DetectedFeatures` | class | `topo/model/detected.py:34` | Contenitore aperto per nome: ogni consumatore scrive sotto il nome che |
| `_dict_to_xml` | func | `topo/io/exporter.py:230` | Converte ricorsivamente un dict in sotto-elementi XML. |
| `Dimension` | class | `topo/model/annotation.py:111` | Quota. Versione minimale: valore misurato + tipo + eventuale override del |
| `_dimension_anchor` | func | `topo/adapters/dxf/annotation_extractor.py:125` | Def-point di una DIMENSION. |
| `_dimension_annotation` | func | `topo/adapters/dxf/annotation_extractor.py:189` |  |
| `_dimension_measurement` | func | `topo/adapters/dxf/annotation_extractor.py:530` |  |
| `_dimension_override` | func | `topo/adapters/dxf/annotation_extractor.py:247` | Override esplicito del testo quota, o None se la quota mostra la misura. |
| `dimension_references` | func | `topo/tools/anchor.py:101` | Gli elementi fra cui ``dimension`` misura, come percorsi in ``result`` |
| `_dimension_semantics` | func | `topo/adapters/dxf/annotation_extractor.py:229` | (dim_type, valore misurato) di una DIMENSION. |
| `_dimension_text` | func | `topo/adapters/dxf/annotation_extractor.py:511` | Testo visualizzato della quota, quando l'immagine non è espandibile. |
| `_discretize_closed` | func | `topo/tools/tabs.py:217` | Punti grezzi chiusi di un `Contour` (senza il punto di chiusura duplicato). |
| `_distance` | func | `topo/core/geometry/intersections.py:36` |  |
| `Document` | class | `topo/model/document.py:37` | Documento di dominio prodotto da load_dxf() / load_svg() / load_pdf(). |
| `document_from_msp` | func | `topo/adapters/dxf/loader.py:343` | Costruisce un Document da un modelspace ezdxf già aperto. |
| `_dot` | func | `topo/tools/tabs.py:63` |  |
| `_drop_boundary_duplicates` | func | `topo/core/island.py:213` | Scarta un giro chiuso il cui intero bordo sta entro `band` dal bordo di |
| `drop_duplicate_points` | func | `topo/core/geometry/points.py:75` | Rimuove punti consecutivi coincidenti entro `tolerance`. |
| `_drop_redundant_meets` | func | `topo/core/island.py:257` | Scarta un fix "incontro" (due `MoveEndpoint` sullo stesso punto, la |
| `DxfAdapter` | class | `topo/adapters/dxf/adapter.py:229` | Adapter DXF che traduce entità DXF in Edge del dominio Topo. |
| `DxfAnnotationExtractor` | class | `topo/adapters/dxf/annotation_extractor.py:43` | Traduce le entità di annotazione di un msp in list[Annotation]. |
| `DxfEntityDispatcher` | class | `topo/adapters/dxf/parser.py:21` | Centralizza il routing per tipo di entità DXF. |
| `Edge` | class | `topo/core/topology/edge.py:28` | Layer intermedio tra l'entità sorgente grezza (di qualsiasi formato) e il |
| `_edge_coords` | func | `topo/core/topology/graph.py:322` |  |
| `edge_geometry` | func | `topo/core/topology/noding.py:261` | L'edge come geometria shapely: LineString discretizzata, Point se degenere. |
| `edge_styles_from_loop` | func | `topo/core/topology/loop_finder.py:187` | Stili grezzi (linetype/colore) di un loop, allineati 1:1 con |
| `edges_to_open_curves` | func | `topo/core/topology/loop_finder.py:220` | Converte gli Edge non assorbiti da un loop strutturale in OpenCurve. |
| `EdgeStyle` | class | `topo/model/style.py:38` |  |
| `_elements` | func | `topo/tools/anchor.py:147` | (percorso, geometria shapely, è chiuso) per contorni e feature di ogni cluster. |
| `EllipseSeg` | class | `topo/core/primitives/segments.py:600` | Ellisse (o arco ellittico) geometrico puro — stessa parametrizzazione del |
| `_emit` | func | `topo/adapters/dxf/loader.py:99` | Aggiunge `msg` al canale warnings; lo stampa solo se verbose. |
| `_emit_annotation` | func | `topo/io/dxf.py:268` |  |
| `_emit_note` | func | `topo/io/dxf.py:278` |  |
| `_emit_rendered` | func | `topo/io/dxf.py:304` | DIMENSION / LEADER: ri-materializza l'immagine appiattita. I testi in |
| `_endpoint_meta` | func | `topo/core/healing/gap_solver.py:253` | Dati che il solver usa per calcolare l'intersezione, per tipo di segmento. |
| `_ends` | func | `topo/core/geometry/lines.py:27` | I due capi di un tratto: `LineString` (primo e ultimo punto) o `(start, end)`. |
| `_ends` | func | `topo/core/geometry/regions.py:110` |  |
| `_ensure_layer` | func | `topo/io/dxf.py:445` | Crea il layer `name` col suo colore canonico se non esiste già. Serve per i |
| `ensure_linetype` | func | `topo/adapters/dxf/exporter.py:23` | Garantisce che il linetype `name` esista in `doc` e ne ritorna il nome; |
| `_entity_style` | func | `topo/adapters/dxf/adapter.py:75` | Cattura l'aspetto EFFETTIVO (linetype/colore) di un'entità DXF in un |
| `entity_to_polygon` | func | `topo/adapters/dxf/adapter.py:212` | Converte un'entità DXF chiusa in un `Polygon` shapely, passando per le |
| `_exact_parts` | func | `topo/core/geometry/intersections.py:146` | Retta, arco, cerchio restano se stessi; spline ed ellisse diventano |
| `_explode_inserts` | func | `topo/adapters/dxf/sanitize.py:106` | Esplode tutti gli INSERT (blocchi) nel modelspace in entità primitive. |
| `_extent` | func | `topo/core/healing/outer_scan.py:135` | (min, max) del pezzo lungo la coordinata `a` (0 = x, 1 = y). |
| `_extract_content` | func | `topo/adapters/dxf/annotation_extractor.py:149` | Testo pulito dell'annotazione, stringa vuota se non ne ha. |
| `extract_drawings_from_page` | func | `topo/adapters/pdf/extractor_adapter.py:23` | Estrae i disegni vettoriali dalla pagina PDF e normalizza l'output. |
| `extract_keyed_entities` | func | `topo/adapters/dxf/sanitize.py:201` | Produce la lista (key, entity) per tutte le entità del msp. |
| `_f` | func | `topo/adapters/dxf/annotation_extractor.py:540` |  |
| `face_segments` | func | `topo/core/topology/rim.py:29` | (segments, styles) lungo il bordo esterno di `polygon`, in senso |
| `_faced` | func | `topo/core/island.py:327` | (giri con almeno una faccia, pezzi dei loro edge fuori da ogni faccia): |
| `_faces_union_loop` | func | `topo/core/topology/outer_face.py:176` | (loop, segments, styles, polygon) sul bordo dell'unione delle facce |
| `_fallback_anchor` | func | `topo/adapters/dxf/annotation_extractor.py:133` | Cerca un qualsiasi attributo-punto usabile. |
| `_feature_entries` | func | `topo/io/view_model.py:56` | Un elemento dell'overlay (MAP.md D90) → una voce per contorno: ruolo, |
| `feature_role` | func | `topo/model/role.py:90` | Il ruolo con cui si disegna un contorno di un elemento dell'overlay (D90): |
| `_features` | func | `topo/io/view_model.py:86` | `cluster.detected` per nome → lista di voci disegnabili. |
| `find_duplicates` | func | `topo/core/healing/normalizer.py:57` | Restituisce i ref delle entità duplicate (seconda occorrenza in poi). |
| `find_joining_edges` | func | `topo/core/healing/steps.py:168` | Gli Edge fra `candidate_ids` (di solito i non-contorno) che uniscono due |
| `find_loops` | func | `topo/core/healing/steps.py:242` | La scala di heal() per chiudere i giri, esclusi `non_contour_ids`: |
| `find_non_contour_edges` | func | `topo/core/healing/steps.py:158` | id(edge) degli Edge che non chiudono un contorno (branching, e non sul |
| `_first_coord` | func | `topo/core/topology/graph.py:329` |  |
| `_first_point` | func | `topo/io/text.py:153` | Un punto che sta sul segmento, per dire in quale pezzo cade. |
| `_first_step` | func | `topo/core/topology/outer_face.py:133` | L'edge che contiene il punto più a sinistra del componente, percorso |
| `fit_circle_kasa` | func | `topo/core/geometry/points.py:89` | Fit algebrico (Kasa) ai minimi quadrati di un cerchio su `points`: minimizza |
| `fit_primitives` | func | `topo/core/primitives/fitting.py:132` | Spezza `points` sui corner marcati in `is_corner` e rifitta ogni tratto: un |
| `_fit_spline` | func | `topo/core/primitives/fitting.py:111` | Un solo SplineSeg passante per `points` (curva di fit globale, non ai |
| `_flatten_virtual` | func | `topo/adapters/dxf/annotation_extractor.py:441` | Espande `virtual_entities()` ricorsivamente sugli INSERT (frecce a blocco). |
| `flatten_z` | func | `topo/adapters/dxf/sanitize.py:29` | Porta a 0 tutte le coordinate Z != 0 per LINE, ARC, CIRCLE, |
| `_flattened_points` | func | `topo/adapters/dxf/annotation_extractor.py:479` | Punti di un ARC o CIRCLE appiattito alla sagitta `_ARC_SAGITTA`. |
| `_fmt` | func | `topo/io/svg.py:23` | Lista di [x, y] → stringa 'x0,y0 x1,y1 …' per points= di polyline/polygon. |
| `free_endpoints_from_edges` | func | `topo/core/healing/gap_solver.py:273` | Estrae gli endpoint liberi (grado < 2 nel grafo) dagli Edge. |
| `free_ends` | func | `topo/core/healing/steps.py:196` | (estremo, distanza dal nodo più vicino) per ogni estremo che nessun altro |
| `_full_arc` | func | `topo/core/geometry/regions.py:176` | Un cerchio come arco di 360°: un arco si inverte, un CircleSeg no (è |
| `_gap_endpoints` | func | `topo/core/healing/gap_solver.py:302` | GapEndpoint per gli estremi di LINE / ARC / SPLINE il cui nodo (arrotondato) |
| `gap_endpoints_at_nodes` | func | `topo/core/healing/gap_solver.py:285` | GapEndpoint per gli endpoint che cadono su uno dei `nodes` — tuple di |
| `GapEndpoint` | class | `topo/core/healing/gap_solver.py:46` | Endpoint libero nel grafo topologico. |
| `_generic` | func | `topo/core/geometry/shape.py:139` |  |
| `GeometryAdapter` | class | `topo/adapters/geometry/loader.py:49` | Traduce descrizioni geometriche pure (dict) in Edge del dominio topo. |
| `_get_solver` | func | `topo/core/healing/gap_solver.py:162` |  |
| `__getattr__` | func | `topo/model/__init__.py:46` |  |
| `_graph` | func | `topo/core/healing/steps.py:389` |  |
| `Graph` | class | `topo/core/topology/graph.py:59` | Grafo topologico interrogabile. |
| `group_collinear_lines` | func | `topo/core/geometry/lines.py:61` | Tratti raggruppati per retta: [[L1, L2], [L3], ...]. Ogni gruppo prende la |
| `_h` | func | `topo/inspect.py:42` |  |
| `heal` | func | `topo/core/heal.py:41` | Legge `doc` dall'interno: un Cluster per contorno esterno chiuso, |
| `HierarchyBuilder` | class | `topo/core/healing/hierarchy.py:149` |  |
| `inject` | func | `topo/tools/inject.py:39` | Arricchisce i Cluster con i dati estratti da un `data_injector` esterno. |
| `_inners` | func | `topo/core/island.py:295` | Un Contour inner per faccia di ogni giro chiuso; un giro senza |
| `_insert_to_degree` | func | `topo/core/primitives/trim.py:166` | Inserisce `t` nel vettore dei nodi finché compare `p` volte (agli |
| `inspect_document` | func | `topo/inspect.py:141` | Stampa un Document prodotto da topo.load_dxf(): cosa ha estratto e |
| `inspect_dxf` | func | `topo/inspect.py:62` | Apre un DXF/DWG con ezdxf e stampa cosa contiene, senza toccare topo. |
| `inspect_file` | func | `topo/inspect.py:307` | Apre un file e stampa i tre livelli in fila: |
| `inspect_result` | func | `topo/inspect.py:229` | Stampa un Result dopo heal(): il prodotto vero di topo. |
| `interior_angle_deg` | func | `topo/core/geometry/points.py:31` | Angolo interno (gradi) in curr_pt fra i lati verso prev_pt e next_pt. |
| `interpolate_bspline` | func | `topo/core/geometry/points.py:145` | B-spline di grado `degree` che passa per tutti i `points` (interpolazione |
| `intersections` | func | `topo/core/geometry/intersections.py:184` | I punti dove due primitive si incontrano: incroci e tocchi, capi compresi. |
| `_intersections` | func | `topo/core/healing/outer_scan.py:150` | Punti del pezzo con coordinata `a` == level. |
| `interval_coverage` | func | `topo/core/geometry/axis.py:47` | Frazione di [lo, hi] coperta dall'unione degli intervalli. |
| `_is_near_full_arc` | func | `topo/core/healing/steps.py:119` |  |
| `is_structural_role` | func | `topo/model/role.py:78` | True se ``role`` è OUTER o INNER per il motore (vedi ``STRUCTURAL_ROLES``). |
| `Island` | class | `topo/core/healing/islands.py:36` | Gruppo di Edge vicini, con la bbox che li contiene tutti. |
| `island` | func | `topo/core/island.py:75` | Legge `doc` per isole. Un Cluster per ogni contorno esterno che non |
| `IslandReading` | class | `topo/core/island.py:57` | Cosa island() ha deciso su un'isola, pezzo per pezzo. |
| `_item_geometry` | func | `topo/tools/anchor.py:162` |  |
| `items_inside` | func | `topo/core/geometry/axis.py:221` | I tratti con entrambi i capi dentro `bounds` allargato di `margin`, nell'ordine dato. |
| `_joined` | func | `topo/core/geometry/shape.py:294` |  |
| `_key_for` | func | `topo/adapters/dxf/sanitize.py:154` | Restituisce una chiave hashable che identifica univocamente |
| `labeled_curves` | func | `topo/core/healing/steps.py:350` | Gli Edge messi da parte da split_labeled() come curve col loro ruolo |
| `_largest_loop` | func | `topo/core/topology/outer_face.py:202` | (loop, segments, styles, polygon) del giro di area massima. |
| `Leader` | class | `topo/model/annotation.py:147` | Direttrice con testo che punta a una feature. |
| `_leader_annotation` | func | `topo/adapters/dxf/annotation_extractor.py:348` |  |
| `leader_target` | func | `topo/tools/anchor.py:73` | L'elemento indicato dalla punta (``vertices[0]``) di ``leader``, come |
| `_leader_vertices` | func | `topo/adapters/dxf/annotation_extractor.py:385` |  |
| `_leaving_angle` | func | `topo/core/topology/outer_face.py:155` | Direzione con cui `edge` lascia `node`, letta a DIRECTION_SAMPLE (o a |
| `_length` | func | `topo/core/geometry/regions.py:102` |  |
| `_length` | func | `topo/core/geometry/shape.py:154` |  |
| `length_inside` | func | `topo/core/geometry/measure.py:103` | Quanta parte di `segment` (qualunque primitiva nativa) sta dentro il |
| `_Line` | class | `topo/core/healing/outer_scan.py:97` |  |
| `_line_intersection` | func | `topo/core/geometry/intersections.py:22` | Intersezione tra retta (p1,p2) e retta (p3,p4). None se parallele. |
| `_line_key` | func | `topo/core/healing/normalizer.py:93` | Chiave della retta infinita per p1->p2: (angolo canonico, offset). |
| `_line_spans` | func | `topo/core/healing/normalizer.py:214` | Span lungo la retta comune: `t` è la proiezione sulla direzione del |
| `_lines` | func | `topo/core/island.py:364` |  |
| `LineSeg` | class | `topo/core/primitives/segments.py:44` |  |
| `load_dxf` | func | `topo/adapters/dxf/loader.py:219` | Apre un documento DXF o DWG e lo traduce in un Document. |
| `load_geometry` | func | `topo/adapters/geometry/loader.py:198` | Costruisce un Document da una lista di descrizioni geometriche pure — |
| `load_pdf` | func | `topo/adapters/pdf/loader.py:22` | Apre un documento PDF, estrae le geometrie vettoriali da tutte le pagine, |
| `load_segments` | func | `topo/adapters/geometry/loader.py:243` | Un Document da segmenti di topo (`LineSeg`, `ArcSeg`, `CircleSeg`, |
| `local_gap_fixes` | func | `topo/core/healing/gap_solver.py:229` | Solo i fix che non spostano un estremo più di `max_move`: due rette quasi |
| `longest_segment` | func | `topo/core/geometry/measure.py:115` | `(segment, length)` del segmento più lungo in `segments` — `(None, 0.0)` |
| `longest_structural_segment` | func | `topo/tools/rotate.py:89` | `(segment, length, angle_deg)` del segmento più lungo fra |
| `_loop_faces` | func | `topo/core/island.py:302` | (segmenti, stili, poligono) per ogni faccia di un giro chiuso: una se |
| `loop_geometry` | func | `topo/core/topology/loop_finder.py:206` | (segmenti, stili, poligono) di un loop; None se i segmenti non chiudono |
| `loop_to_closed_curve` | func | `topo/core/healing/hierarchy.py:21` |  |
| `LoopFinder` | class | `topo/core/topology/loop_finder.py:28` |  |
| `loops_to_curves` | func | `topo/core/healing/steps.py:297` | Un ClosedCurve per loop, col ruolo del primo edge; senza poligono valido, niente. |
| `LoopSearch` | class | `topo/core/healing/steps.py:41` | Come find_loops() ha chiuso (o non chiuso) i giri, gradino per gradino. |
| `_loose_ends_warnings` | func | `topo/core/heal.py:186` | Quello che resta aperto anche quando qualcosa si chiude (D111): gli |
| `_make_inner` | func | `topo/core/healing/hierarchy.py:91` |  |
| `_make_polygon` | func | `topo/core/primitives/polygon_builder.py:48` |  |
| `map_sanitized_item_to_edge` | func | `topo/adapters/pdf/graph_adapter.py:13` |  |
| `_measured_points` | func | `topo/adapters/dxf/annotation_extractor.py:272` | I punti sulla geometria fra cui la quota misura, dai def-point: |
| `_meet` | func | `topo/core/geometry/intersections.py:171` |  |
| `_meet_or_bridge` | func | `topo/core/healing/gap_solver.py:262` | Se le due geometrie si incontrano in `ix`, porta lì entrambi gli estremi; |
| `_merge_annotations` | func | `topo/adapters/dxf/loader.py:68` | Aggiunge a `base` le annotazioni di `extra` non già presenti (per firma). |
| `merge_cocircular_overlaps` | func | `topo/core/healing/normalizer.py:376` | `merge_collinear_overlaps` per gli ArcSeg: fonde gruppi co-circolari |
| `merge_collinear_overlaps` | func | `topo/core/healing/normalizer.py:120` | Fonde gruppi di LineSeg collineari (stessa retta infinita, `_line_key`) |
| `merge_intervals` | func | `topo/core/geometry/axis.py:36` | Unisce gli intervalli che si sovrappongono o distano al più `tolerance`, in ordine. |
| `_merge_on_carrier` | func | `topo/core/healing/normalizer.py:285` | Raggruppa per supporto (`key`) gli edge di `segment_type` con ruolo |
| `merge_runs` | func | `topo/core/geometry/shape.py:243` | Segmenti consecutivi di un giro chiuso sulla stessa circonferenza (o |
| `_merged_arc` | func | `topo/core/healing/normalizer.py:420` | Il fuso di una catena cocircolare: un arco, o un cerchio se chiude il |
| `_merged_line` | func | `topo/core/healing/normalizer.py:238` | Il fuso di una catena collineare: nodi arrotondati, segmento a piena |
| `_middle` | func | `topo/core/geometry/regions.py:114` |  |
| `_mleader_anchor` | func | `topo/adapters/dxf/annotation_extractor.py:113` | Primo vertice della direttrice di un MULTILEADER. |
| `mleader_text` | func | `topo/adapters/dxf/mtext.py:37` | Testo grezzo di un MULTILEADER (prima della pulizia), None se assente. |
| `_moved_segment` | func | `topo/core/healing/gap_solver.py:322` | Nuovo segmento con l'endpoint `role` spostato su `new_pt`. None se non gestito. |
| `MoveEndpoint` | class | `topo/core/healing/gap_solver.py:73` | Istruzione: sposta l'endpoint role di ref al punto new_pt. |
| `name_rules` | func | `topo/model/role_rule.py:96` | Scorciatoia: {nome: ruolo} → una RoleRule(name=...) per voce. |
| `_nearest_within` | func | `topo/tools/anchor.py:184` | L'indice della parte più vicina a ``probe``, se entro ``snap_distance`` (> 0). |
| `NestedBridgeResult` | class | `topo/tools/tabs.py:208` | Risultato per UNA coppia isola/genitore-diretto trovata nella gerarchia. |
| `NodedEdges` | class | `topo/core/topology/noding.py:51` | La rete piana: i pezzi, e per ognuno l'Edge da cui viene. |
| `non_contour_candidates` | func | `topo/tools/non_contour.py:40` | Edge di `doc.edges` che il criterio topologico di `heal()` escluderebbe dal |
| `NonContourEdgeDetector` | class | `topo/core/topology/non_contour_edges.py:44` |  |
| `_normalize` | func | `topo/core/island.py:241` | Stessi passi di heal, ma sulla griglia fine della rete piana: prima i |
| `normalize_ocs` | func | `topo/adapters/dxf/sanitize.py:19` | Normalizza il vettore di estrusione di tutte le entità OCS nel modelspace. |
| `normalize_role` | func | `topo/model/role.py:112` | Ripulisce una stringa-ruolo che arriva dal chiamante (``RoleRule``, |
| `Note` | class | `topo/model/annotation.py:99` | Testo libero: TEXT o MTEXT. |
| `num_segments_for_bulge` | func | `topo/core/geometry/measure.py:33` | Numero di segmenti per discretizzare un arco dato il suo bulge. |
| `_off_faces` | func | `topo/core/island.py:341` | I tratti degli edge di `loop` lontani più di `band` dal bordo di ogni |
| `_on_arc` | func | `topo/core/geometry/intersections.py:164` |  |
| `_on_arc` | func | `topo/core/healing/outer_scan.py:127` |  |
| `_on_border` | func | `topo/core/geometry/axis.py:186` |  |
| `_on_boundary` | func | `topo/tools/anchor.py:119` | L'elemento col bordo più vicino a ``point``, se entro ``distance``. |
| `_on_line` | func | `topo/core/geometry/intersections.py:155` |  |
| `_on_line` | func | `topo/core/primitives/trim.py:47` | Proiezione di `pt` sulla retta, dentro i suoi due estremi. |
| `_open` | func | `topo/core/island.py:390` |  |
| `OpenCurve` | class | `topo/model/curve.py:73` | Curva aperta: ha segmenti ma non un polygon. |
| `outer_candidate_edges` | func | `topo/core/healing/outer_scan.py:72` | Per ogni asse, una quota rappresentativa (punto medio) fra ogni coppia |
| `_outer_entity` | func | `topo/io/exporter.py:266` | L'entità su layer OuterContour che porta gli XDATA: prima una polilinea, |
| `outer_face` | func | `topo/core/topology/outer_face.py:59` | Contorno esterno della rete `edges` (già piana: split_at_crossings). I |
| `outer_face_passes` | func | `topo/core/topology/outer_face.py:88` | {id(edge): quante volte il bordo della faccia esterna di `component` |
| `_outer_face_walk` | func | `topo/core/topology/outer_face.py:103` | [(edge, dal nodo, al nodo)] lungo il bordo della faccia esterna. |
| `_outer_polygons` | func | `topo/io/dxf.py:454` | (cluster, poligono dell'outer) per ogni cluster che ne ha uno. |
| `OuterCandidates` | class | `topo/core/healing/outer_scan.py:54` | Edge candidati a bordo esterno, con i raggi che li hanno scelti. |
| `OuterFace` | class | `topo/core/topology/outer_face.py:42` | Il contorno esterno trovato, e cosa il percorso ha scartato. |
| `OuterHit` | class | `topo/core/healing/outer_scan.py:45` | Un raggio per cui l'Edge è stato l'estremo. |
| `_p` | func | `topo/inspect.py:46` | Formatta un punto (x, y) con nd decimali. |
| `_palette_dict` | func | `topo/io/view_model.py:180` | role (stringa) → colore hex, per la legenda di un renderer. |
| `_param` | func | `topo/core/geometry/regions.py:62` |  |
| `_param` | func | `topo/core/topology/noding.py:106` | (parametro, distanza del punto dal segmento). |
| `_param_range` | func | `topo/core/topology/noding.py:122` |  |
| `_parse_arc` | func | `topo/adapters/dxf/parser.py:58` |  |
| `_parse_circle` | func | `topo/adapters/dxf/parser.py:127` |  |
| `_parse_ellipse` | func | `topo/adapters/dxf/parser.py:134` | Un'ELLIPSE DXF è sempre percorsa CCW da `start_param` a `end_param` |
| `_parse_line` | func | `topo/adapters/dxf/parser.py:48` |  |
| `_parse_polyline` | func | `topo/adapters/dxf/parser.py:152` |  |
| `_parse_spline` | func | `topo/adapters/dxf/parser.py:73` |  |
| `_perp` | func | `topo/tools/tabs.py:74` | Ruota `v` di 90° (verso arbitrario, coerente fra le due chiamate). |
| `_piece` | func | `topo/core/geometry/regions.py:118` | Il tratto di `seg` fra i parametri `s0` < `s1`, stessa primitiva. |
| `_piece_length` | func | `topo/core/topology/noding.py:126` |  |
| `_pieces` | func | `topo/core/healing/outer_scan.py:113` |  |
| `_place` | func | `topo/core/geometry/build.py:21` | Ruota di `angle` gradi attorno all'origine e trasla in `center`. |
| `_place` | func | `topo/core/healing/hierarchy.py:69` |  |
| `point_line_distance` | func | `topo/core/geometry/lines.py:36` | Distanza di `point` dalla retta infinita per `a`, `b`; da `a` se i due coincidono. |
| `point_on_circle` | func | `topo/core/primitives/segments.py:97` | Punto della circonferenza (`center`, `radius`) all'angolo dato (radianti). |
| `point_on_contour` | func | `topo/core/geometry/regions.py:233` | Dove cade `point` sull'anello `segments` (testa-coda): su un vertice, su |
| `_point_to_segment_distance` | func | `topo/core/primitives/segments.py:276` | Distanza perpendicolare di `p` dal segmento `a`-`b` (0 se `a == b`). |
| `_poly_points` | func | `topo/io/view_model.py:36` | Vertici dell'anello esterno di un polygon shapely come lista di [x, y]. |
| `polygon` | func | `topo/core/geometry/build.py:27` | Il poligono per i `points` dati, chiuso: l'ultimo lato torna al primo punto. Almeno 3 punti. |
| `_polygon` | func | `topo/core/geometry/regions.py:194` |  |
| `polygonize_edges` | func | `topo/core/healing/steps.py:313` | Ultima spiaggia quando nessun grafo chiude: le facce dell'intero disegno |
| `_polygons` | func | `topo/core/island.py:376` |  |
| `polygons_to_curves` | func | `topo/core/healing/steps.py:329` | Per poligono un ClosedCurve OUTER dal bordo esterno e uno INNER per |
| `_polyline` | func | `topo/core/geometry/regions.py:47` |  |
| `polyline_line_intersections` | func | `topo/core/geometry/intersections.py:102` | Intersezioni fra la retta infinita (p1, p2) e la spezzata `points` (ogni |
| `_polyline_points` | func | `topo/adapters/dxf/annotation_extractor.py:487` |  |
| `_raw_linetype_pattern` | func | `topo/adapters/dxf/adapter.py:52` | Pattern grezzo (lunghezza totale + tratti con segno, `+` = tratto, |
| `_ray_exit_point` | func | `topo/tools/tabs.py:225` | Punto in cui il raggio da `center` verso `direction` esce dal contorno chiuso `points`. |
| `_read_dwg` | func | `topo/adapters/dxf/loader.py:148` | Legge un file DWG usando ezdxf.addons.odafc (wrapper di ODA File Converter). |
| `read_island` | func | `topo/core/island.py:164` | Un'isola: normalizza (nodi dagli estremi reali, tassellature rifittate, |
| `read_islands` | func | `topo/core/island.py:141` | I pezzi a contatto (`spatial_islands` a `max_gap`) + `read_island` per |
| `read_metadata_from_dxf` | func | `topo/io/exporter.py:307` | Legge i metadati TOPO XDATA dall'entità OuterContour. |
| `rectangle` | func | `topo/core/geometry/build.py:37` | Rettangolo `length` × `width` centrato in `center`, lato lungo a `angle` gradi. |
| `_rectangle` | func | `topo/core/geometry/shape.py:122` |  |
| `_refine_segment` | func | `topo/core/primitives/segments.py:288` | Suddivide `[t0, t1]` finché il punto medio (valutato con `evaluate(t)`) |
| `refit_tessellations` | func | `topo/core/healing/normalizer.py:492` | Una catena di almeno `min_run` LineSeg (`role == UNKNOWN`) più corti di |
| `register_role_style` | func | `topo/rules/palette.py:157` | Registra uno `RoleStyle` per `role`, valido per ogni render successivo |
| `registered_role_styles` | func | `topo/rules/palette.py:168` | Copia del registro attivo — letta dai renderer, mai mutata da loro. |
| `regular_polygon` | func | `topo/core/geometry/build.py:43` | Poligono regolare di `sides` lati inscritto nel cerchio di raggio `radius`; il primo vertice a `angle` gradi. |
| `_remove_excluded_entities` | func | `topo/io/dxf.py:430` |  |
| `_render_block` | func | `topo/adapters/dxf/annotation_extractor.py:402` | Espande l'immagine dell'entità in strokes/fills/texts puri. |
| `RenderedGeometry` | class | `topo/model/annotation.py:46` | Immagine di una quota/direttrice già appiattita in primitive pure. |
| `RenderedText` | class | `topo/model/annotation.py:37` | Un testo dentro l'immagine appiattita di una quota/direttrice. |
| `renode` | func | `topo/core/topology/noding.py:64` | Nodi di ogni Edge ricalcolati dal punto reale del segmento a |
| `repair_merged_corners` | func | `topo/core/healing/steps.py:216` | Chiude gli angoli che il grafo esatto vede aperti e il clustering degli |
| `resolve_role` | func | `topo/model/role_rule.py:88` | Ruolo della prima regola che matcha, in ordine; `unknown` se nessuna. |
| `resolve_target` | func | `topo/tools/anchor.py:126` | L'oggetto (contorno o feature) a cui punta un ``target``, o ``None``. |
| `Result` | class | `topo/model/result.py:11` | Risultato completo di una sessione topo su un file DXF. |
| `_result_bbox_center` | func | `topo/tools/rotate.py:224` | Centro del bbox unito degli outer di tutti i cluster — vedi `rotate_to_longest`. |
| `_reversed` | func | `topo/core/geometry/regions.py:190` |  |
| `_rim_runs` | func | `topo/core/topology/rim.py:87` | [((edge, verso), primo vertice, ultimo vertice)] lungo l'anello: copertura greedy |
| `_ring_segments` | func | `topo/core/healing/steps.py:395` |  |
| `_role` | func | `topo/inspect.py:53` | Nome del ruolo come stringa piatta ('outer'), non 'ContourRole.OUTER'. |
| `_role_from` | func | `topo/adapters/geometry/loader.py:41` | work_type stringa (stesso vocabolario di RoleRule.role) → ruolo. Un work_type |
| `role_str` | func | `topo/model/role.py:142` | Valore stringa di un ruolo, che sia una costante ``ContourRole`` o una |
| `role_to_color` | func | `topo/rules/palette.py:74` | Colore ACI di un ruolo. Ruolo noto → il suo colore semantico; |
| `role_to_dxf_layer` | func | `topo/adapters/dxf/layers.py:73` | Nome layer DXF per un ruolo. |
| `role_to_hex` | func | `topo/rules/palette.py:88` | Colore hex CSS di un ruolo. Un colore registrato (`register_role_style`) |
| `RoleRule` | class | `topo/model/role_rule.py:35` | Una regola: se TUTTE le condizioni date sono vere, la linea prende `role`. |
| `RoleStyle` | class | `topo/rules/palette.py:107` | Override, indipendente dal formato, dell'aspetto visivo di un ruolo in |
| `rotate_cluster` | func | `topo/tools/rotate.py:117` | Nuovo `Cluster` con `outer`/`inners` ruotati di `angle_rad` (radianti, |
| `_rotate_contour` | func | `topo/tools/rotate.py:108` |  |
| `rotate_document` | func | `topo/tools/rotate.py:187` | Nuovo `Document` con ogni `edge.segment` ruotato di `angle_rad` |
| `_rotate_point` | func | `topo/core/primitives/segments.py:71` | Ruota `pt` di `angle` radianti (CCW) attorno a `origin`. |
| `rotate_result` | func | `topo/tools/rotate.py:147` | Nuovo `Result` con ogni cluster (`rotate_cluster`), `trash_entities` |
| `rotate_to_longest` | func | `topo/tools/rotate.py:240` | Ruota `result` (già sano, da un `heal()` già fatto dal chiamante) in modo |
| `round_point` | func | `topo/core/geometry/measure.py:25` |  |
| `_round_points` | func | `topo/io/view_model.py:31` | Lista di punti (2D o 3D) → lista di [x, y] arrotondati. |
| `_sagitta_step` | func | `topo/core/primitives/segments.py:112` | Angolo massimo di una corda che dista al più `tolerance` dall'arco di |
| `sample_bezier_cubic` | func | `topo/adapters/pdf/geometry_adapter.py:37` | Campiona una curva di Bezier cubica in un set di punti lineari (poligonale). |
| `sanitize` | func | `topo/adapters/dxf/sanitize.py:88` | Esegue tutti i sanitizer in sequenza sul modelspace ricevuto. |
| `sanitize_pdf_geometries` | func | `topo/adapters/pdf/sanitize.py:13` | Prende gli item geometrici grezzi estratti dall'extractor, applica la conversione |
| `save_json` | func | `topo/io/exporter.py:117` | Salva i metadati in JSON secondo lo schema di metadata_schema.py. |
| `save_svg` | func | `topo/io/svg.py:168` | Scrive `to_svg(result, **kwargs)` su file. |
| `save_text` | func | `topo/io/text.py:266` | Scrive `to_text(result)` su `path` (per convenzione `<nome>.topo.md`). |
| `save_xml` | func | `topo/io/exporter.py:170` | Salva i metadati in XML secondo lo schema di metadata_schema.py. |
| `_scale` | func | `topo/tools/tabs.py:59` |  |
| `_scan_axis` | func | `topo/core/healing/outer_scan.py:184` |  |
| `_scan_bbox` | func | `topo/io/svg.py:175` | bbox da tutti i punti del view model — fallback quando vm['bbox'] è None. |
| `_search_warnings` | func | `topo/core/heal.py:205` | Cosa racconta heal() dei gradini della scala di find_loops(). |
| `_seg_end_point` | func | `topo/adapters/dxf/exporter.py:93` |  |
| `segment_endpoints` | func | `topo/core/primitives/segments.py:506` | (start, end) di un segmento primitivo, in coordinate XY non arrotondate. |
| `segment_is_closed` | func | `topo/core/primitives/segments.py:542` | True se gli endpoint del segmento coincidono entro ``tolerance``. |
| `_segment_key` | func | `topo/adapters/dxf/adapter.py:161` | Chiave univoca per deduplicazione. |
| `segment_length` | func | `topo/core/geometry/measure.py:86` | Lunghezza reale di una primitiva nativa singola (`LineSeg`/`ArcSeg`/ |
| `segments_from_loop` | func | `topo/core/topology/loop_finder.py:161` | Segmenti nativi di un loop, orientati nel verso di percorrenza. |
| `segments_to_pts_with_bulge` | func | `topo/adapters/dxf/exporter.py:101` |  |
| `_sense` | func | `topo/core/topology/rim.py:77` | +1 se il lato p→q va nel verso di `geom` vicino a `mid`, -1 se contro. |
| `set_schema` | func | `topo/io/exporter.py:100` | Imposta uno schema esterno come schema attivo. |
| `_setup_layers` | func | `topo/io/dxf.py:436` |  |
| `_shape` | func | `topo/io/svg.py:28` |  |
| `_short_runs` | func | `topo/core/healing/normalizer.py:544` | Catene massimali: percorsi fra nodi di grado != 2, o anelli. |
| `_side` | func | `topo/core/geometry/regions.py:201` | +1 dentro, -1 fuori, 0 sul bordo. |
| `_side_cover` | func | `topo/core/topology/rim.py:60` | Per ogni lato dell'anello, gli (edge, verso) che distano meno di `band` |
| `sides_on_border` | func | `topo/core/geometry/axis.py:231` | I lati di `bounds` ("left", "bottom", "right", "top") che stanno sul |
| `_signed_area` | func | `topo/core/geometry/regions.py:185` |  |
| `simplify_points` | func | `topo/core/primitives/fitting.py:198` | `detect_corners` + `fit_primitives` in un solo passo — comodo quando serve |
| `_size` | func | `topo/tools/anchor.py:170` | A parità di distanza vince l'elemento più piccolo: un foro sul bordo del pezzo. |
| `_solid_points` | func | `topo/adapters/dxf/annotation_extractor.py:499` | SOLID/TRACE: 4 vertici in ordine 'a farfalla' → poligono convesso. |
| `_solve_arc_arc` | func | `topo/core/healing/gap_solver.py:126` |  |
| `_solve_arc_line` | func | `topo/core/healing/gap_solver.py:112` |  |
| `_solve_line_line` | func | `topo/core/healing/gap_solver.py:100` |  |
| `_solve_spline_any` | func | `topo/core/healing/gap_solver.py:138` |  |
| `_span` | func | `topo/core/geometry/regions.py:51` |  |
| `_Span` | class | `topo/core/healing/normalizer.py:249` | Un edge come intervallo [lo, hi] sul suo supporto (posizione lungo la |
| `spanning_lines` | func | `topo/core/geometry/axis.py:199` | (ys, xs): le coordinate delle linee strettamente interne a `bounds` (bordo |
| `spatial_islands` | func | `topo/core/healing/islands.py:54` | Union-find sulle coppie di Edge a distanza <= gap_tolerance (STRtree, |
| `_spline_param` | func | `topo/core/primitives/trim.py:146` | Parametro del punto della spline più vicino a `pt`: campioni, poi |
| `SplineSeg` | class | `topo/core/primitives/segments.py:338` |  |
| `_split` | func | `topo/core/geometry/regions.py:134` | `seg` spezzato nei `points` che gli stanno sopra, nel suo verso. |
| `_split` | func | `topo/core/topology/noding.py:215` |  |
| `split` | func | `topo/io/dxf.py:162` | Materializza un Result in un Drawing per parte. |
| `split_at_crossings` | func | `topo/core/topology/noding.py:72` | Spezza ogni LineSeg/ArcSeg/CircleSeg nei punti dove incrocia un altro |
| `_split_at_junctions` | func | `topo/core/healing/normalizer.py:339` | Spezza una catena dove due span consecutivi si toccano SOLO (nessuna |
| `_split_circle` | func | `topo/core/topology/noding.py:240` |  |
| `_split_closed_polyline_at_cuts` | func | `topo/tools/tabs.py:166` | Spezza il contorno chiuso `points` sui tagli in `cuts` — ognuno |
| `_split_into_stretches` | func | `topo/core/primitives/fitting.py:48` | Spezza `points` in tratti fra due spigoli consecutivi (estremi inclusi). |
| `split_labeled` | func | `topo/core/healing/steps.py:77` | Separa gli Edge con un ruolo già deciso e non strutturale (cornice, |
| `split_non_finite` | func | `topo/core/healing/steps.py:56` | Separa gli Edge con una coordinata non finita (NaN, inf): ritorna |
| `_split_params` | func | `topo/core/topology/noding.py:179` |  |
| `split_to_files` | func | `topo/recipes.py:23` | Pipeline multi-pezzo + salvataggio su disco: heal → split → `.saveas()` per |
| `splits_polygon` | func | `topo/core/geometry/lines.py:82` | La corda `start`-`end`, prolungata di `reach` ai due capi, divide `polygon` in due o più parti. |
| `stadium` | func | `topo/core/geometry/build.py:57` | Stadio fuori tutto `length` × `width` (due semicerchi di raggio |
| `_stadium` | func | `topo/core/geometry/shape.py:96` |  |
| `structural_loops` | func | `topo/core/healing/steps.py:286` | I loop in cui ogni edge con ruolo deciso è strutturale: un solo edge non |
| `structural_segments` | func | `topo/tools/rotate.py:73` | Segmenti nativi dei contorni strutturali di ogni cluster: sempre |
| `_style_attribs` | func | `topo/adapters/dxf/exporter.py:49` | dxfattribs per una entità in output: layer + linetype della sorgente, se |
| `_sub` | func | `topo/tools/tabs.py:51` |  |
| `_sub_angular` | func | `topo/core/primitives/trim.py:61` |  |
| `_sub_part` | func | `topo/inspect.py:277` |  |
| `sub_segment` | func | `topo/core/primitives/trim.py:26` | Il tratto di `seg` da `a` a `b` (punti sulla curva, o a una tolleranza |
| `_sub_spline` | func | `topo/core/primitives/trim.py:115` |  |
| `_synthesize_dimension` | func | `topo/adapters/dxf/annotation_extractor.py:290` | Ricostruisce l'immagine di una DIMENSION lineare dai def-point, quando il |
| `_tangent` | func | `topo/core/geometry/regions.py:161` | Direzione di percorrenza di `seg` nel suo capo iniziale o finale. |
| `_text_item` | func | `topo/adapters/dxf/annotation_extractor.py:450` |  |
| `_texts_by_part` | func | `topo/tools/inject.py:74` | Testi di `result.annotations` per indice di parte. Un testo coperto da più |
| `_thinner_than` | func | `topo/core/island.py:370` | Larghezza media (2·area/perimetro: per una striscia, la sua |
| `_to_annotation` | func | `topo/adapters/dxf/annotation_extractor.py:60` |  |
| `to_dxf` | func | `topo/io/dxf.py:48` | Crea un documento DXF nuovo (R2010) e vi materializza il Result. |
| `to_json` | func | `topo/io/exporter.py:147` | Restituisce i metadati come stringa JSON secondo schema. Vedi `save_json` per `extra_metadata`. |
| `to_nester_input` | func | `topo/io/exporter.py:244` | Produce l'input per il nester: coordinate grezze + metadati base. |
| `to_svg` | func | `topo/io/svg.py:45` | `Result` → stringa SVG completa (`<svg>…</svg>`). |
| `to_text` | func | `topo/io/text.py:172` | Il `Result` come testo per un modello linguistico (`.topo.md`). |
| `to_view_model` | func | `topo/io/view_model.py:128` | `Result` → dizionario JSON-ready con la geometria di ogni feature. |
| `_track` | func | `topo/io/view_model.py:43` | Traccia aperta (lista di segmenti nativi) discretizzata a lista di [x, y]. |
| `track_length` | func | `topo/core/geometry/measure.py:67` | Lunghezza totale di una polilinea (somma delle corde). |
| `track_points` | func | `topo/core/geometry/measure.py:48` | Vertici di una traccia aperta come catena di segmenti nativi. |
| `track_shape_type` | func | `topo/core/geometry/measure.py:75` | `"line"` se la traccia è un solo segmento retto (2 vertici), altrimenti `"curve"`. |
| `transform_point` | func | `topo/adapters/pdf/geometry_adapter.py:27` | Converte un punto da punti PDF (pt) a millimetri (mm) |
| `_trash_entry` | func | `topo/io/view_model.py:96` |  |
| `_trash_probe_point` | func | `topo/io/dxf.py:333` | Punto rappresentativo di un'entità trash, per assegnarla a una parte. |
| `_trimmed` | func | `topo/core/topology/rim.py:142` | `seg` da `a` a `b`: un capo entro `band` da un estremo di `seg` è |
| `_try_fit_arc` | func | `topo/core/primitives/fitting.py:85` | Prova un fit a cerchio su `points`; lo accetta solo se lo scostamento |
| `_uniform_knots` | func | `topo/io/text.py:161` | Nodi bloccati agli estremi e passo interno costante: non serve scriverli. |
| `_unit_vector` | func | `topo/tools/tabs.py:67` |  |
| `_upgrade_to_r2010` | func | `topo/adapters/dxf/loader.py:180` | Converte un documento DXF legacy in R2010. |
| `validate` | func | `topo/rules/validator.py:29` | Valida l'input prima di heal(). |
| `validate_result` | func | `topo/rules/validator.py:128` | Valida i Cluster dentro un Result già popolato da heal(). |
| `_warn_non_roundtrip_types` | func | `topo/adapters/dxf/loader.py:86` | Avvisa sui tipi di entità che to_dxf() non riscrive (HATCH, IMAGE, …). |
| `weld_degenerate_linesegs` | func | `topo/core/healing/normalizer.py:440` | Salda (non cancella) i LineSeg `role == UNKNOWN` di lunghezza reale |
| `_width_factor` | func | `topo/adapters/dxf/annotation_extractor.py:159` | Stretch orizzontale effettivo del testo (1.0 = nessuno). |
| `_with_nodes` | func | `topo/core/topology/noding.py:209` |  |
| `_write_annotations` | func | `topo/io/dxf.py:230` | Riscrive le annotazioni testuali della sorgente nel documento di output. |
| `_write_attached_features` | func | `topo/io/dxf.py:399` | Ogni collezione di `cluster.detected` (D70, D90): topo non sa cosa siano. |
| `write_metadata_to_dxf` | func | `topo/io/exporter.py:278` | Scrive i metadati come XDATA sull'entità OuterContour. |
| `write_native_segments` | func | `topo/adapters/dxf/exporter.py:267` | Materializza segmenti aperti come geometria NATIVA, una entità DXF per |
| `write_open_segments` | func | `topo/adapters/dxf/exporter.py:325` | Materializza una lista di segmenti puri come geometria APERTA su msp. |
| `write_segments` | func | `topo/adapters/dxf/exporter.py:188` | Materializza una lista di segmenti puri su msp. |
| `_write_trash` | func | `topo/io/dxf.py:349` | Materializza `result.trash_entities`. |
| `_Writer` | class | `topo/io/text.py:43` | Numeri arrotondati e id dei contorni per una sola chiamata di `to_text`. |
| `_xy` | func | `topo/adapters/dxf/annotation_extractor.py:475` |  |

## Duplicate names

Same name defined at module level in different modules. Not automatically a bug — but each one is either two implementations of one job (merge them) or two different jobs sharing a name (rename one).

| name | defined in |
|---|---|
| `_chain` | `topo/core/geometry/regions.py:290` · `topo/core/healing/normalizer.py:265` |
| `_ends` | `topo/core/geometry/lines.py:27` · `topo/core/geometry/regions.py:110` |
| `_length` | `topo/core/geometry/regions.py:102` · `topo/core/geometry/shape.py:154` |
| `_on_arc` | `topo/core/geometry/intersections.py:164` · `topo/core/healing/outer_scan.py:127` |
| `_on_line` | `topo/core/geometry/intersections.py:155` · `topo/core/primitives/trim.py:47` |
| `_param` | `topo/core/geometry/regions.py:62` · `topo/core/topology/noding.py:106` |
| `_place` | `topo/core/geometry/build.py:21` · `topo/core/healing/hierarchy.py:69` |
| `_split` | `topo/core/geometry/regions.py:134` · `topo/core/topology/noding.py:215` |

## Dependency rule

- `core` never imports `adapters`, `tools`, `io`
- `model` never imports `adapters`, `tools`, `io`

`TYPE_CHECKING`-only imports count as violations here and must be verified by hand.

**Clean** — no violation found.

## By module

### `topo/` (root)

#### `topo/__init__.py` — 208 lines

_topo_

No module-level function or class.

### `topo/adapters/`

#### `topo/adapters/dxf/adapter.py` — 390 lines

_topo/adapters/dxf/adapter.py_

- `_raw_linetype_pattern(lt_entry) -> Optional[Tuple[float, ...]]` — L52 — Pattern grezzo (lunghezza totale + tratti con segno, `+` = tratto,
- `_entity_style(entity) -> EdgeStyle` — L75 — Cattura l'aspetto EFFETTIVO (linetype/colore) di un'entità DXF in un
- `_segment_key(segment: Segment) -> tuple` — L161 — Chiave univoca per deduplicazione.
- `entity_to_polygon(entity, tolerance: float=DEFAULT_TOLERANCE) -> Optional[Polygon]` — L212 — Converte un'entità DXF chiusa in un `Polygon` shapely, passando per le
- **class** `DxfAdapter(Adapter)` — L229 — Adapter DXF che traduce entità DXF in Edge del dominio Topo.
  - methods: `__init__`, `to_edges`, `source_context`

#### `topo/adapters/dxf/annotation_extractor.py` — 544 lines

_adapters/dxf/annotation_extractor.py_

- **class** `DxfAnnotationExtractor` — L43 — Traduce le entità di annotazione di un msp in list[Annotation].
  - methods: `__init__`, `extract`
- `_to_annotation(entity) -> Optional[Annotation]` — L60
- `annotation_anchor(entity) -> Optional[Tuple[float, float]]` — L94 — Punto d'ancoraggio XY di un'entità di annotazione.
- `_mleader_anchor(entity) -> Optional[Tuple[float, float]]` — L113 — Primo vertice della direttrice di un MULTILEADER.
- `_dimension_anchor(entity) -> Optional[Tuple[float, float]]` — L125 — Def-point di una DIMENSION.
- `_fallback_anchor(entity) -> Optional[Tuple[float, float]]` — L133 — Cerca un qualsiasi attributo-punto usabile.
- `_extract_content(entity) -> str` — L149 — Testo pulito dell'annotazione, stringa vuota se non ne ha.
- `_width_factor(entity) -> float` — L159 — Stretch orizzontale effettivo del testo (1.0 = nessuno).
- `_dimension_annotation(entity, pos, layer) -> Optional[Dimension]` — L189
- `_dimension_semantics(entity) -> Tuple[str, Optional[float]]` — L229 — (dim_type, valore misurato) di una DIMENSION.
- `_dimension_override(entity) -> Optional[str]` — L247 — Override esplicito del testo quota, o None se la quota mostra la misura.
- `_measured_points(entity, dim_type: str) -> List[Tuple[float, float]]` — L272 — I punti sulla geometria fra cui la quota misura, dai def-point:
- `_synthesize_dimension(entity)` — L290 — Ricostruisce l'immagine di una DIMENSION lineare dai def-point, quando il
- `_leader_annotation(entity, pos, layer, source_kind) -> Optional[Leader]` — L348
- `_leader_vertices(entity) -> List[Tuple[float, float]]` — L385
- `_render_block(entity) -> RenderedGeometry` — L402 — Espande l'immagine dell'entità in strokes/fills/texts puri.
- `_flatten_virtual(entity)` — L441 — Espande `virtual_entities()` ricorsivamente sugli INSERT (frecce a blocco).
- `_text_item(v) -> Optional[RenderedText]` — L450
- `_bbox_center(polylines) -> Optional[Tuple[float, float]]` — L467
- `_xy(p) -> Tuple[float, float]` — L475
- `_flattened_points(entity) -> List[Tuple[float, float]]` — L479 — Punti di un ARC o CIRCLE appiattito alla sagitta `_ARC_SAGITTA`.
- `_polyline_points(pl) -> Tuple[List[Tuple[float, float]], bool]` — L487
- `_solid_points(solid) -> List[Tuple[float, float]]` — L499 — SOLID/TRACE: 4 vertici in ordine 'a farfalla' → poligono convesso.
- `_dimension_text(entity) -> str` — L511 — Testo visualizzato della quota, quando l'immagine non è espandibile.
- `_dimension_measurement(entity) -> str` — L530
- `_f(value) -> Optional[float]` — L540

#### `topo/adapters/dxf/exporter.py` — 395 lines

_adapters/dxf/exporter.py_

- `ensure_linetype(doc, name: str, pattern: Optional[Tuple[float, ...]]=None, description: str='') -> Optional[str]` — L23 — Garantisce che il linetype `name` esista in `doc` e ne ritorna il nome;
- `_style_attribs(doc, layer: str, style: Optional[EdgeStyle]=None) -> dict` — L49 — dxfattribs per una entità in output: layer + linetype della sorgente, se
- `arc_seg_to_bulge(arc: ArcSeg) -> float` — L77
- `_seg_end_point(seg) -> Optional[tuple]` — L93
- `segments_to_pts_with_bulge(segments: list) -> list` — L101
- `_add_spline(spline: SplineSeg, msp, layer: str, style: Optional[EdgeStyle]=None) -> object` — L116 — Materializza una SplineSeg come SPLINE nativa, ricostruita dalla primitiva
- `_add_ellipse(ellipse: EllipseSeg, msp, layer: str, style: Optional[EdgeStyle]=None) -> object` — L161 — Materializza una EllipseSeg come ELLIPSE nativa — mai una spline: topo
- `write_segments(segments: List, msp, layer: str, styles: Optional[List]=None) -> Optional[object]` — L188 — Materializza una lista di segmenti puri su msp.
- `write_native_segments(segments: List, msp, layer: str, styles: Optional[List]=None) -> List[object]` — L267 — Materializza segmenti aperti come geometria NATIVA, una entità DXF per
- `write_open_segments(segments: List, msp, layer: str, styles: Optional[List]=None) -> List[object]` — L325 — Materializza una lista di segmenti puri come geometria APERTA su msp.

#### `topo/adapters/dxf/layers.py` — 92 lines

_adapters/dxf/layers.py_

- `color_for_layer(layer_name: str) -> int` — L58 — Colore DXF canonico per un layer.
- `role_to_dxf_layer(role) -> str` — L73 — Nome layer DXF per un ruolo.

#### `topo/adapters/dxf/loader.py` — 382 lines

_adapters/dxf/loader.py_

- `_annotation_signature(ann) -> tuple` — L63
- `_merge_annotations(base: list, extra: list) -> None` — L68 — Aggiunge a `base` le annotazioni di `extra` non già presenti (per firma).
- `_warn_non_roundtrip_types(msp, sink: list, verbose: bool=False) -> None` — L86 — Avvisa sui tipi di entità che to_dxf() non riscrive (HATCH, IMAGE, …).
- `_emit(sink: list, msg: str, verbose: bool=False) -> None` — L99 — Aggiunge `msg` al canale warnings; lo stampa solo se verbose.
- `_configure_odafc(sink: list=None, verbose: bool=False) -> None` — L107 — Punta l'addon `odafc` all'eseguibile ODA File Converter.
- `_read_dwg(path: str, sink: list=None, verbose: bool=False)` — L148 — Legge un file DWG usando ezdxf.addons.odafc (wrapper di ODA File Converter).
- `_upgrade_to_r2010(doc, sink: list=None, verbose: bool=False) -> object` — L180 — Converte un documento DXF legacy in R2010.
- `load_dxf(path: str, upgrade: bool=False, explode_inserts: bool=True, flatten_z_flag: bool=True, verbose: bool=False, tolerance: float=DEFAULT_NODE_TOLERANCE, role_rules: Sequence[RoleRule]=(), ignore_layers=None) -> Document` — L219 — Apre un documento DXF o DWG e lo traduce in un Document.
- `document_from_msp(msp, tolerance: float=DEFAULT_NODE_TOLERANCE, role_rules: Sequence[RoleRule]=(), ignore_layers=None, source_path: str='') -> Document` — L343 — Costruisce un Document da un modelspace ezdxf già aperto.

#### `topo/adapters/dxf/mtext.py` — 45 lines

_topo/adapters/dxf/mtext.py_

- `clean_mtext(txt) -> str` — L18 — Testo semplice da una stringa MTEXT grezza: rimuove i codici di
- `mleader_text(entity) -> Optional[str]` — L37 — Testo grezzo di un MULTILEADER (prima della pulizia), None se assente.

#### `topo/adapters/dxf/parser.py` — 193 lines

_adapters/dxf/parser.py_

- **class** `DxfEntityDispatcher` — L21 — Centralizza il routing per tipo di entità DXF.
  - methods: `__init__`, `parse`
- `_parse_line(entity, rev) -> tuple` — L48
- `_parse_arc(entity, rev) -> ArcSeg` — L58
- `_parse_spline(entity, rev) -> SplineSeg` — L73
- `_parse_circle(entity) -> CircleSeg` — L127
- `_parse_ellipse(entity, rev) -> EllipseSeg` — L134 — Un'ELLIPSE DXF è sempre percorsa CCW da `start_param` a `end_param`
- `_parse_polyline(entity, rev) -> list` — L152

#### `topo/adapters/dxf/sanitize.py` — 225 lines

_adapters/dxf/sanitize.py_

- `normalize_ocs(msp, verbose: bool=False) -> None` — L19 — Normalizza il vettore di estrusione di tutte le entità OCS nel modelspace.
- `flatten_z(msp, verbose: bool=False) -> int` — L29 — Porta a 0 tutte le coordinate Z != 0 per LINE, ARC, CIRCLE,
- `sanitize(msp, flatten_z_flag: bool=True, verbose: bool=False) -> int` — L88 — Esegue tutti i sanitizer in sequenza sul modelspace ricevuto.
- `_explode_inserts(msp, sink: list=None) -> int` — L106 — Esplode tutti gli INSERT (blocchi) nel modelspace in entità primitive.
- `_key_for(entity) -> Optional[Hashable]` — L154 — Restituisce una chiave hashable che identifica univocamente
- `extract_keyed_entities(msp) -> List[Tuple[Hashable, Any]]` — L201 — Produce la lista (key, entity) per tutte le entità del msp.
- `delete_entities(refs: List[Any], msp) -> None` — L210 — Elimina le entità dal msp in-place.
- `deduplicate(msp) -> int` — L216 — Shortcut: estrae chiavi, trova duplicati, li elimina.

#### `topo/adapters/geometry/__init__.py` — 0 lines

No module-level function or class.

#### `topo/adapters/geometry/loader.py` — 270 lines

_adapters/geometry/loader.py_

- `_role_from(entity: Dict[str, Any]) -> str` — L41 — work_type stringa (stesso vocabolario di RoleRule.role) → ruolo. Un work_type
- **class** `GeometryAdapter(Adapter)` — L49 — Traduce descrizioni geometriche pure (dict) in Edge del dominio topo.
  - methods: `__init__`, `to_edges`, `source_context`, `_round`, `_line_edge`, `_arc_edge`, `_edge`, `_circle_edge`, `_spline_edge`, `_ellipse_edge`, `_polygon_edges`
- `load_geometry(entities: List[Dict[str, Any]], tolerance: float=DEFAULT_NODE_TOLERANCE, source_path: str='') -> Document` — L198 — Costruisce un Document da una lista di descrizioni geometriche pure —
- `load_segments(segments, tolerance: float=DEFAULT_NODE_TOLERANCE, role: str='unknown', source_path: str='') -> Document` — L243 — Un Document da segmenti di topo (`LineSeg`, `ArcSeg`, `CircleSeg`,

#### `topo/adapters/pdf/__init__.py` — 0 lines

No module-level function or class.

#### `topo/adapters/pdf/extractor_adapter.py` — 86 lines

_adapters/pdf/extractor_adapter.py_

- `extract_drawings_from_page(page: Any) -> List[Dict[str, Any]]` — L23 — Estrae i disegni vettoriali dalla pagina PDF e normalizza l'output.

#### `topo/adapters/pdf/geometry_adapter.py` — 63 lines

_adapters/pdf/geometry_adapter.py_

- `transform_point(x: float, y: float, page_height: float) -> tuple[float, float]` — L27 — Converte un punto da punti PDF (pt) a millimetri (mm)
- `sample_bezier_cubic(p1: tuple, p2: tuple, p3: tuple, p4: tuple, num_segments: int=16) -> list[tuple[float, float]]` — L37 — Campiona una curva di Bezier cubica in un set di punti lineari (poligonale).

#### `topo/adapters/pdf/graph_adapter.py` — 56 lines

_adapters/pdf/graph_adapter.py_

- `map_sanitized_item_to_edge(item: tuple, decimals: int, page_idx: int) -> Edge \| None` — L13

#### `topo/adapters/pdf/loader.py` — 83 lines

_adapters/pdf/loader.py_

- `load_pdf(path: str, node_decimals: int=3, snap_tolerance: float=0.15) -> list` — L22 — Apre un documento PDF, estrae le geometrie vettoriali da tutte le pagine,

#### `topo/adapters/pdf/sanitize.py` — 103 lines

_adapters/pdf/sanitize.py_

- `sanitize_pdf_geometries(raw_items: list, page_height: float, snap_tolerance: float=0.15) -> list` — L13 — Prende gli item geometrici grezzi estratti dall'extractor, applica la conversione

### `topo/core/`

#### `topo/core/adapter_base.py` — 38 lines

_Contratto base per gli adapter di input di Topo._

- **class** `Adapter(ABC)` — L23
  - methods: `__init__`, `to_edges`, `source_context`

#### `topo/core/geometry/__init__.py` — 42 lines

_topo/core/geometry/__init__.py_

No module-level function or class.

#### `topo/core/geometry/axis.py` — 253 lines

_topo/core/geometry/axis.py_

- `merge_intervals(intervals: Iterable[Interval], tolerance: float=0.0) -> List[Interval]` — L36 — Unisce gli intervalli che si sovrappongono o distano al più `tolerance`, in ordine.
- `interval_coverage(intervals: Iterable[Interval], lo: float, hi: float) -> float` — L47 — Frazione di [lo, hi] coperta dall'unione degli intervalli.
- `cluster_values(values: Iterable[float], tolerance: float=CLUSTER_TOLERANCE) -> List[float]` — L55 — I valori ordinati, tenendo per ogni gruppo il più piccolo: un valore entro
- **class** `AxisLine` — L73 — Un tratto orizzontale o verticale.
- `axis_lines(items: Iterable, eps: float=AXIS_EPS) -> Tuple[List[AxisLine], List[AxisLine]]` — L87 — (orizzontali, verticali): i tratti che si scostano dall'asse al più di `eps`; gli altri non compaiono.
- `_covered_at(lines: Sequence[AxisLine], at: float, lo: float, hi: float, tol: float) -> float` — L100
- **class** `CoveredRectangle` — L109 — Un rettangolo allineato agli assi i cui quattro lati sono coperti da tratti.
  - methods: `bbox`, `area`, `long_side`, `short_side`, `ratio`
- `covered_rectangles(items: Sequence, min_side: float, eps: float=AXIS_EPS, cluster_tolerance: float=CLUSTER_TOLERANCE, coverage: float=SIDE_COVERAGE) -> List[CoveredRectangle]` — L144 — I rettangoli allineati agli assi con ogni lato coperto almeno per
- `_on_border(x_lo, y_lo, x_hi, y_hi, items, tol) -> list` — L186
- `spanning_lines(bounds: Bounds, items: Iterable, coverage: float=SIDE_COVERAGE, eps: float=AXIS_EPS, cluster_tolerance: float=CLUSTER_TOLERANCE) -> Tuple[List[float], List[float]]` — L199 — (ys, xs): le coordinate delle linee strettamente interne a `bounds` (bordo
- `items_inside(bounds: Bounds, items: Iterable, margin: float=0.0) -> list` — L221 — I tratti con entrambi i capi dentro `bounds` allargato di `margin`, nell'ordine dato.
- `sides_on_border(bounds: Bounds, border: Bounds, tolerance: float) -> List[str]` — L231 — I lati di `bounds` ("left", "bottom", "right", "top") che stanno sul
- `axis_aligned_share(segments: Iterable, angle_tolerance: float) -> Optional[float]` — L238 — Frazione della lunghezza dei `LineSeg` di `segments` orizzontale o

#### `topo/core/geometry/build.py` — 74 lines

_topo/core/geometry/build.py_

- `_place(points: Sequence[Point], center: Point, angle: float) -> List[Point]` — L21 — Ruota di `angle` gradi attorno all'origine e trasla in `center`.
- `polygon(points: Sequence[Point]) -> List[LineSeg]` — L27 — Il poligono per i `points` dati, chiuso: l'ultimo lato torna al primo punto. Almeno 3 punti.
- `rectangle(length: float, width: float, center: Point=(0.0, 0.0), angle: float=0.0) -> List[LineSeg]` — L37 — Rettangolo `length` × `width` centrato in `center`, lato lungo a `angle` gradi.
- `regular_polygon(sides: int, radius: float, center: Point=(0.0, 0.0), angle: float=0.0) -> List[LineSeg]` — L43 — Poligono regolare di `sides` lati inscritto nel cerchio di raggio `radius`; il primo vertice a `angle` gradi.
- `circle(radius: float, center: Point=(0.0, 0.0)) -> List[CircleSeg]` — L52 — Il cerchio di raggio `radius` in `center`.
- `stadium(length: float, width: float, center: Point=(0.0, 0.0), angle: float=0.0) -> list` — L57 — Stadio fuori tutto `length` × `width` (due semicerchi di raggio

#### `topo/core/geometry/intersections.py` — 198 lines

_topo/core/geometry/intersections.py_

- `_line_intersection(p1: Point, p2: Point, p3: Point, p4: Point) -> Optional[Point]` — L22 — Intersezione tra retta (p1,p2) e retta (p3,p4). None se parallele.
- `_distance(p1: Point, p2: Point) -> float` — L36
- `_circle_line_intersections(cx: float, cy: float, r: float, p1: Point, p2: Point) -> List[Point]` — L40 — Intersezioni tra la circonferenza (cx, cy, r) e la retta infinita (p1, p2).
- `_circle_circle_intersections(cx1: float, cy1: float, r1: float, cx2: float, cy2: float, r2: float) -> List[Point]` — L71 — Intersezioni tra due circonferenze. Restituisce 0, 1 o 2 punti.
- `_closest_to(candidates: List[Point], ref: Point) -> Optional[Point]` — L95 — Restituisce il punto più vicino a ref tra i candidati.
- `polyline_line_intersections(points: List[Point], closed: bool, p1: Point, p2: Point) -> List[Tuple[Point, int]]` — L102 — Intersezioni fra la retta infinita (p1, p2) e la spezzata `points` (ogni
- `_exact_parts(seg) -> list` — L146 — Retta, arco, cerchio restano se stessi; spline ed ellisse diventano
- `_on_line(seg: LineSeg, pt: Point) -> bool` — L155
- `_on_arc(seg, pt: Point) -> bool` — L164
- `_meet(a, b) -> List[Point]` — L171
- `intersections(a, b) -> List[Point]` — L184 — I punti dove due primitive si incontrano: incroci e tocchi, capi compresi.

#### `topo/core/geometry/lines.py` — 170 lines

_topo/core/geometry/lines.py_

- `_ends(item) -> Tuple[Point, Point]` — L27 — I due capi di un tratto: `LineString` (primo e ultimo punto) o `(start, end)`.
- `point_line_distance(point: Point, a: Point, b: Point) -> float` — L36 — Distanza di `point` dalla retta infinita per `a`, `b`; da `a` se i due coincidono.
- `are_collinear(a, b, tolerance: float=COLLINEAR_TOLERANCE, angle_tolerance: float=COLLINEAR_ANGLE_TOLERANCE) -> bool` — L45 — I tratti `a` e `b` stanno sulla stessa retta infinita: direzioni uguali
- `group_collinear_lines(lines: list, tolerance: float=COLLINEAR_TOLERANCE, angle_tolerance: float=COLLINEAR_ANGLE_TOLERANCE) -> list` — L61 — Tratti raggruppati per retta: [[L1, L2], [L3], ...]. Ogni gruppo prende la
- `splits_polygon(polygon, start: Point, end: Point, reach: float=0.0) -> bool` — L82 — La corda `start`-`end`, prolungata di `reach` ai due capi, divide `polygon` in due o più parti.
- **class** `CollinearRun` — L94 — Tratti sulla stessa retta, in fila lungo di essa.
- `bridged_runs(segments: Sequence, bridges: Sequence, tolerance: float=COLLINEAR_TOLERANCE, angle_tolerance: float=COLLINEAR_ANGLE_TOLERANCE) -> list[CollinearRun]` — L106 — File di due o più tratti sulla stessa retta in cui lo spazio fra un tratto
- `dash_line(start: Point, end: Point, head: float, tail: float, middle: float=0.0, n_middle: int=0) -> list[Tuple[Point, Point]]` — L143 — Il segmento `start`→`end` ridotto a tratti: uno lungo `head` che parte da

#### `topo/core/geometry/measure.py` — 179 lines

_topo/core/geometry/measure.py_

- `round_point(pt, decimals: int=NODE_DECIMALS) -> Tuple` — L25
- `num_segments_for_bulge(bulge: float) -> int` — L33 — Numero di segmenti per discretizzare un arco dato il suo bulge.
- `track_points(segments, tolerance: Optional[float]=None) -> List[Point]` — L48 — Vertici di una traccia aperta come catena di segmenti nativi.
- `track_length(pts) -> float` — L67 — Lunghezza totale di una polilinea (somma delle corde).
- `track_shape_type(pts) -> str` — L75 — `"line"` se la traccia è un solo segmento retto (2 vertici), altrimenti `"curve"`.
- `segment_length(segment) -> float` — L86 — Lunghezza reale di una primitiva nativa singola (`LineSeg`/`ArcSeg`/
- `length_inside(segment, bounds: Tuple[float, float, float, float]) -> float` — L103 — Quanta parte di `segment` (qualunque primitiva nativa) sta dentro il
- `longest_segment(segments) -> Tuple[Optional[object], float]` — L115 — `(segment, length)` del segmento più lungo in `segments` — `(None, 0.0)`
- `chord_angle_deg(a: Point, b: Point) -> float` — L128 — Angolo (gradi, 0-180°) della corda da `a` a `b`. Modulo 180 perché una
- `circular_geometry(polygon, segments=None)` — L150 — (diameter, center) se il contorno è ~circolare, altrimenti (None, None).

#### `topo/core/geometry/points.py` — 201 lines

_topo/core/geometry/points.py_

- `interior_angle_deg(prev_pt: Point, curr_pt: Point, next_pt: Point) -> float` — L31 — Angolo interno (gradi) in curr_pt fra i lati verso prev_pt e next_pt.
- `detect_corners(points: List[Point], angle_threshold_deg: float=DEFAULT_ANGLE_THRESHOLD_DEG, closed: bool=True) -> List[bool]` — L43 — Per ogni punto, True se l'angolo formato dai due lati adiacenti è sotto
- `drop_duplicate_points(points: List[Point], tolerance: float=DEFAULT_DUPLICATE_TOLERANCE) -> List[Point]` — L75 — Rimuove punti consecutivi coincidenti entro `tolerance`.
- `fit_circle_kasa(points: List[Point]) -> Optional[Tuple[Point, float, float]]` — L89 — Fit algebrico (Kasa) ai minimi quadrati di un cerchio su `points`: minimizza
- `arc_angles(points: List[Point], center: Point) -> Tuple[float, float, bool]` — L121 — `(start_angle, end_angle, ccw)` in radianti di un arco che passa per
- `interpolate_bspline(points: List[Point], degree: int=3) -> Tuple[List[Point], List[float]]` — L145 — B-spline di grado `degree` che passa per tutti i `points` (interpolazione
- `_bspline_basis_row(u: float, p: int, knots: List[float], n: int) -> List[float]` — L179 — Le n+1 funzioni di base N_i,p(u) (Cox-de Boor, Piegl & Tiller A2.2).

#### `topo/core/geometry/regions.py` — 352 lines

_topo/core/geometry/regions.py_

- `_polyline(seg) -> List[Point]` — L47
- `_span(seg) -> float` — L51
- `_param(seg, pt: Point) -> float` — L62
- `_at(seg, s: float) -> Point` — L85
- `_length(seg, s0: float, s1: float) -> float` — L102
- `_ends(seg) -> Tuple[Point, Point]` — L110
- `_middle(seg) -> Point` — L114
- `_piece(seg, s0: float, s1: float)` — L118 — Il tratto di `seg` fra i parametri `s0` < `s1`, stessa primitiva.
- `_split(seg, points: Sequence[Point]) -> list` — L134 — `seg` spezzato nei `points` che gli stanno sopra, nel suo verso.
- `_tangent(seg, at_end: bool) -> Tuple[float, float]` — L161 — Direzione di percorrenza di `seg` nel suo capo iniziale o finale.
- `_full_arc(seg)` — L176 — Un cerchio come arco di 360°: un arco si inverte, un CircleSeg no (è
- `_signed_area(ring: Sequence) -> float` — L185
- `_reversed(ring: Sequence) -> list` — L190
- `_polygon(ring: Sequence)` — L194
- `_side(polygon, pt: Point) -> int` — L201 — +1 dentro, -1 fuori, 0 sul bordo.
- **class** `ContourPoint` — L214 — Dove cade un punto su un contorno.
- `point_on_contour(segments: Sequence, point: Point, tolerance: float=DEFAULT_TOLERANCE, angle_tolerance: float=TANGENT_TOLERANCE) -> Optional[ContourPoint]` — L233 — Dove cade `point` sull'anello `segments` (testa-coda): su un vertice, su
- `cut_by(segment, region: Sequence, keep: str='outside') -> list` — L265 — I pezzi di `segment` fuori (`keep="outside"`) o dentro (`keep="inside"`)
- `_chain(pieces: list) -> List[list]` — L290 — Pezzi orientati incatenati testa-coda in anelli chiusi.
- `contour_minus(contour: Sequence, region: Sequence) -> List[list]` — L307 — L'anello `contour` meno la regione chiusa `region` (tutti e due anelli di

#### `topo/core/geometry/shape.py` — 298 lines

_topo/core/geometry/shape.py_

- **class** `ContourShape` — L36 — kind:   circle \| stadium \| rectangle \| polygon \| other
  - methods: `diameter`, `to_dict`
- `contour_shape(item, tolerance: float=SHAPE_TOLERANCE, angle_tolerance: float=ANGLE_TOLERANCE_DEG) -> Optional[ContourShape]` — L63 — Forma di un contorno chiuso (`Contour`, o qualunque oggetto con
- `_circle(segments, tol, _angle_tol)` — L82
- `_stadium(segments, tol, angle_tol)` — L96
- `_rectangle(segments, tol, angle_tol)` — L122
- `_generic(segments)` — L139
- `_length(line: LineSeg) -> float` — L154
- `_angle_diff(a: float, b: float) -> float` — L158 — Differenza fra due direzioni modulo 180, in [0, 90].
- **class** `ConcentricGroup` — L175 — Contorni circolari con lo stesso centro, dal raggio minore al maggiore.
  - methods: `diameters`
- `concentric_groups(items, tolerance: float=CONCENTRIC_TOLERANCE) -> list[ConcentricGroup]` — L192 — Partizione dei contorni circolari di `items` per centro: ogni cerchio sta
- **class** `ArcAround` — L215 — Un arco concentrico a un cerchio e più grande di lui.
- `arcs_around(center: Point, radius: float, arcs, tolerance: float=CONCENTRIC_TOLERANCE) -> list[ArcAround]` — L228 — Gli archi di `arcs` col centro entro `tolerance` da `center` e raggio
- `merge_runs(segments: list, styles: list)` — L243 — Segmenti consecutivi di un giro chiuso sulla stessa circonferenza (o
- `_continues(prev, prev_style, seg, style) -> bool` — L275 — `seg` prosegue `prev` sulla stessa curva, nello stesso verso?
- `_joined(prev, seg)` — L294

#### `topo/core/heal.py` — 224 lines

_core/heal.py_

- `heal(doc: Document, tolerance: Optional[float]=None, label: str='', source_file: str='', is_structural: Optional[Callable[[str], bool]]=None) -> Result` — L41 — Legge `doc` dall'interno: un Cluster per contorno esterno chiuso,
- `_loose_ends_warnings(edges: list, non_contour_ids: set, epsilon: float) -> list[str]` — L186 — Quello che resta aperto anche quando qualcosa si chiude (D111): gli
- `_search_warnings(search: LoopSearch, tolerance: float) -> list[str]` — L205 — Cosa racconta heal() dei gradini della scala di find_loops().

#### `topo/core/healing/__init__.py` — 0 lines

No module-level function or class.

#### `topo/core/healing/gap_solver.py` — 385 lines

_core/healing/gap_solver.py_

- **class** `GapEndpoint` — L46 — Endpoint libero nel grafo topologico.
- **class** `MoveEndpoint` — L73 — Istruzione: sposta l'endpoint role di ref al punto new_pt.
- **class** `AddSegment` — L84 — Istruzione: aggiungi un segmento retto tra pt_a e pt_b.
- `_solve_line_line(ep_a: GapEndpoint, ep_b: GapEndpoint) -> List[GapFix]` — L100
- `_solve_arc_line(ep_arc: GapEndpoint, ep_line: GapEndpoint) -> List[GapFix]` — L112
- `_solve_arc_arc(ep_a: GapEndpoint, ep_b: GapEndpoint) -> List[GapFix]` — L126
- `_solve_spline_any(ep_a: GapEndpoint, ep_b: GapEndpoint) -> List[GapFix]` — L138
- `_get_solver(kind_a: str, kind_b: str)` — L162
- `compute_gap_fixes(endpoints: List[GapEndpoint], tolerance: float, pairwise: bool=True) -> List[GapFix]` — L174 — Calcola i GapFix fra gli endpoint liberi entro tolerance. I due capi
- `local_gap_fixes(fixes: List[GapFix], max_move: float) -> List[GapFix]` — L229 — Solo i fix che non spostano un estremo più di `max_move`: due rette quasi
- `_endpoint_meta(segment) -> dict` — L253 — Dati che il solver usa per calcolare l'intersezione, per tipo di segmento.
- `_meet_or_bridge(ix: Optional[Point2D], ep_a: GapEndpoint, ep_b: GapEndpoint) -> List[GapFix]` — L262 — Se le due geometrie si incontrano in `ix`, porta lì entrambi gli estremi;
- `free_endpoints_from_edges(edges: List[Edge], graph) -> List[GapEndpoint]` — L273 — Estrae gli endpoint liberi (grado < 2 nel grafo) dagli Edge.
- `gap_endpoints_at_nodes(edges: List[Edge], nodes: set) -> List[GapEndpoint]` — L285 — GapEndpoint per gli endpoint che cadono su uno dei `nodes` — tuple di
- `_gap_endpoints(edges: List[Edge], keep: Callable[[Point2D], bool]) -> List[GapEndpoint]` — L302 — GapEndpoint per gli estremi di LINE / ARC / SPLINE il cui nodo (arrotondato)
- `_moved_segment(segment, role: str, new_pt: Point2D)` — L322 — Nuovo segmento con l'endpoint `role` spostato su `new_pt`. None se non gestito.
- `apply_gap_fixes(edges: List[Edge], fixes: List[GapFix]) -> List[Edge]` — L340 — Applica i GapFix restituendo una NUOVA lista di Edge — `edges` non viene mutata.

#### `topo/core/healing/hierarchy.py` — 210 lines

- `loop_to_closed_curve(loop, role: ContourRole=ContourRole.UNKNOWN, polygon=None, segments: list=None, styles: list=None) -> Optional[ClosedCurve]` — L21
- `_place(proxy: ClosedCurve, nodes: list) -> bool` — L69
- `_build_tree(proxies: list) -> list` — L78
- `_make_inner(proxy: ClosedCurve, parent_role: ContourRole=ContourRole.UNKNOWN, depth: int=1, parent: Optional[Contour]=None) -> Contour` — L91
- `_collect_inners(children: list, inners: list, classified_proxies: set, parent_role: ContourRole=ContourRole.UNKNOWN, depth: int=1, parent: Optional[Contour]=None)` — L112 — Appiattisce l'albero di contenimento in `cluster.inners` (ogni discendente
- **class** `HierarchyBuilder` — L149
  - methods: `__init__`, `build`, `_build_parts`, `_collect_trash`

#### `topo/core/healing/islands.py` — 95 lines

_core/healing/islands.py_

- **class** `Island` — L36 — Gruppo di Edge vicini, con la bbox che li contiene tutti.
  - methods: `width`, `height`
- `spatial_islands(edges: Iterable[Edge], gap_tolerance: float) -> List[Island]` — L54 — Union-find sulle coppie di Edge a distanza <= gap_tolerance (STRtree,

#### `topo/core/healing/normalizer.py` — 572 lines

_core/healing/normalizer.py_

- `find_duplicates(keyed_entities: Iterable[Tuple[Hashable, Any]]) -> List[Any]` — L57 — Restituisce i ref delle entità duplicate (seconda occorrenza in poi).
- `_line_key(p1, p2) -> Tuple[float, float]` — L93 — Chiave della retta infinita per p1->p2: (angolo canonico, offset).
- `merge_collinear_overlaps(edges: Iterable[Edge], keep_junctions: bool=False) -> List[Edge]` — L120 — Fonde gruppi di LineSeg collineari (stessa retta infinita, `_line_key`)
- `_line_spans(group: List[Edge]) -> List[_Span]` — L214 — Span lungo la retta comune: `t` è la proiezione sulla direzione del
- `_merged_line(lo: _Span, hi: _Span)` — L238 — Il fuso di una catena collineare: nodi arrotondati, segmento a piena
- **class** `_Span` — L249 — Un edge come intervallo [lo, hi] sul suo supporto (posizione lungo la
- `_chain(spans: List[_Span]) -> List[List[_Span]]` — L265 — Ordina per `lo` e incatena gli span che si toccano o si sovrappongono:
- `_merge_on_carrier(edges: Iterable[Edge], segment_type: type, key: Callable[[Any], Hashable], chains_of: Callable[[List[Edge]], List[List[_Span]]], merged: Callable[[_Span, _Span], Tuple[Point, Point, Any]], keep_junctions: bool=False) -> List[Edge]` — L285 — Raggruppa per supporto (`key`) gli edge di `segment_type` con ruolo
- `_split_at_junctions(chain: List[_Span], junction: Callable[[Point], bool]) -> List[List[_Span]]` — L339 — Spezza una catena dove due span consecutivi si toccano SOLO (nessuna
- `_arc_key(center, radius) -> Tuple[float, float, float]` — L367 — Chiave del cerchio (centro+raggio) a precisione fissa — v. `_line_key`.
- `merge_cocircular_overlaps(edges: Iterable[Edge]) -> List[Edge]` — L376 — `merge_collinear_overlaps` per gli ArcSeg: fonde gruppi co-circolari
- `_arc_chains(group: List[Edge]) -> List[List[_Span]]` — L394 — Catene angolari di un gruppo sullo stesso cerchio. Se l'ultima catena
- `_merged_arc(lo: _Span, hi: _Span)` — L420 — Il fuso di una catena cocircolare: un arco, o un cerchio se chiude il
- `weld_degenerate_linesegs(edges: Iterable[Edge]) -> List[Edge]` — L440 — Salda (non cancella) i LineSeg `role == UNKNOWN` di lunghezza reale
- `refit_tessellations(edges: Iterable[Edge], max_segment: float=0.1, min_run: int=10, arc_fit_tolerance: float=0.02, node_decimals: int=3) -> List[Edge]` — L492 — Una catena di almeno `min_run` LineSeg (`role == UNKNOWN`) più corti di
- `_short_runs(short_edges: List[Edge]) -> list` — L544 — Catene massimali: percorsi fra nodi di grado != 2, o anelli.

#### `topo/core/healing/outer_scan.py` — 217 lines

_core/healing/outer_scan.py_

- **class** `OuterHit` — L45 — Un raggio per cui l'Edge è stato l'estremo.
- **class** `OuterCandidates` — L54 — Edge candidati a bordo esterno, con i raggi che li hanno scelti.
  - methods: `ids`, `hits_of`
- `outer_candidate_edges(edges: Iterable[Edge]) -> OuterCandidates` — L72 — Per ogni asse, una quota rappresentativa (punto medio) fra ogni coppia
- **class** `_Line` — L97
- **class** `_Arc` — L104
- `_pieces(edge: Edge) -> list` — L113
- `_on_arc(arc: _Arc, pt: Point) -> bool` — L127
- `_arc_point(arc: _Arc, angle: float) -> Point` — L131
- `_extent(piece, a: int) -> Tuple[float, float]` — L135 — (min, max) del pezzo lungo la coordinata `a` (0 = x, 1 = y).
- `_intersections(piece, a: int, level: float) -> List[Point]` — L150 — Punti del pezzo con coordinata `a` == level.
- `_scan_axis(pieces: list, axis: str, hits: Dict[int, List[OuterHit]]) -> int` — L184

#### `topo/core/healing/steps.py` — 397 lines

_core/healing/steps.py_

- **class** `LoopSearch` — L41 — Come find_loops() ha chiuso (o non chiuso) i giri, gradino per gradino.
- `split_non_finite(edges: List[Edge]) -> Tuple[List[Edge], List[Edge]]` — L56 — Separa gli Edge con una coordinata non finita (NaN, inf): ritorna
- `split_labeled(edges: List[Edge], is_structural: Optional[Callable[[str], bool]]=None) -> Tuple[List[Edge], List[Edge]]` — L77 — Separa gli Edge con un ruolo già deciso e non strutturale (cornice,
- `close_near_full_arcs(edges: List[Edge], tolerance: float, max_missing_angle: float=NEAR_FULL_ARC_MISSING) -> Tuple[List[Edge], int]` — L97 — Un ArcSeg coi due capi liberi diventa CircleSeg (stesso centro e raggio)
- `_is_near_full_arc(edge: Edge, graph, tolerance: float, max_missing_angle: float) -> bool` — L119
- `close_free_gaps(edges: List[Edge], tolerance: float) -> List[Edge]` — L134 — Chiude i gap fra estremi liberi entro `tolerance` col gap solver
- `dangling_splines(edges: List[Edge]) -> List[Edge]` — L149 — SplineSeg aperte con almeno un estremo non collegato a nient'altro.
- `find_non_contour_edges(edges: List[Edge], tolerance: float) -> Set[int]` — L158 — id(edge) degli Edge che non chiudono un contorno (branching, e non sul
- `find_joining_edges(edges: List[Edge], candidate_ids: Set[int]) -> List[Edge]` — L168 — Gli Edge fra `candidate_ids` (di solito i non-contorno) che uniscono due
- `free_ends(edges: List[Edge], epsilon: float=0.0) -> List[Tuple[Tuple, float]]` — L196 — (estremo, distanza dal nodo più vicino) per ogni estremo che nessun altro
- `repair_merged_corners(edges: List[Edge], tolerance: float, exclude_ids: FrozenSet[int]=frozenset()) -> Tuple[List[Edge], int, list]` — L216 — Chiude gli angoli che il grafo esatto vede aperti e il clustering degli
- `find_loops(edges: List[Edge], non_contour_ids: Set[int], tolerance: float) -> LoopSearch` — L242 — La scala di heal() per chiudere i giri, esclusi `non_contour_ids`:
- `structural_loops(loops: List[list], is_structural: Optional[Callable[[str], bool]]=None) -> List[list]` — L286 — I loop in cui ogni edge con ruolo deciso è strutturale: un solo edge non
- `loops_to_curves(loops: List[list]) -> List[ClosedCurve]` — L297 — Un ClosedCurve per loop, col ruolo del primo edge; senza poligono valido, niente.
- `polygonize_edges(edges: List[Edge], tolerance: float) -> List[Polygon]` — L313 — Ultima spiaggia quando nessun grafo chiude: le facce dell'intero disegno
- `polygons_to_curves(polygons: List[Polygon]) -> List[ClosedCurve]` — L329 — Per poligono un ClosedCurve OUTER dal bordo esterno e uno INNER per
- `labeled_curves(edges: List[Edge]) -> list` — L350 — Gli Edge messi da parte da split_labeled() come curve col loro ruolo
- `build_hierarchy(curves: list, label: str='', source_file: str='', is_structural: Optional[Callable[[str], bool]]=None) -> Tuple[List[Cluster], list]` — L372 — Albero di contenimento sui ClosedCurve: ogni radice è un Cluster
- `_graph(edges: List[Edge], exclude_ids: FrozenSet[int], epsilon: float=0.0)` — L389
- `_ring_segments(coords) -> List[LineSeg]` — L395

#### `topo/core/island.py` — 392 lines

_core/island.py_

- **class** `IslandReading` — L57 — Cosa island() ha deciso su un'isola, pezzo per pezzo.
- `island(doc: Document, *, max_gap: float, tolerance: Optional[float]=None, is_structural: Optional[Callable[[str], bool]]=None) -> Result` — L75 — Legge `doc` per isole. Un Cluster per ogni contorno esterno che non
- `read_islands(edges: List[Edge], tolerance: float, max_gap: float) -> List[IslandReading]` — L141 — I pezzi a contatto (`spatial_islands` a `max_gap`) + `read_island` per
- `read_island(edges: List[Edge], tolerance: float, max_gap: float) -> IslandReading` — L164 — Un'isola: normalizza (nodi dagli estremi reali, tassellature rifittate,
- `_drop_boundary_duplicates(loops: list, reference: Optional[Polygon], band: float) -> list` — L213 — Scarta un giro chiuso il cui intero bordo sta entro `band` dal bordo di
- `_normalize(edges: List[Edge], tolerance: float, max_gap: float) -> List[Edge]` — L241 — Stessi passi di heal, ma sulla griglia fine della rete piana: prima i
- `_drop_redundant_meets(fixes: list, graph) -> list` — L257 — Scarta un fix "incontro" (due `MoveEndpoint` sullo stesso punto, la
- `_cluster(reading: IslandReading, source_file: str, tolerance: float) -> Cluster` — L287
- `_inners(loops, parent: Contour, tolerance: float) -> List[Contour]` — L295 — Un Contour inner per faccia di ogni giro chiuso; un giro senza
- `_loop_faces(loop, tolerance: float) -> list` — L302 — (segmenti, stili, poligono) per ogni faccia di un giro chiuso: una se
- `_faced(loops: list, tolerance: float)` — L327 — (giri con almeno una faccia, pezzi dei loro edge fuori da ogni faccia):
- `_off_faces(loop, faces) -> List[Edge]` — L341 — I tratti degli edge di `loop` lontani più di `band` dal bordo di ogni
- `_lines(geometry) -> list` — L364
- `_thinner_than(polygon: Polygon, width: float) -> bool` — L370 — Larghezza media (2·area/perimetro: per una striscia, la sua
- `_polygons(geometry) -> List[Polygon]` — L376
- `_contour(segments, styles, polygon, role, parent) -> Contour` — L382 — Il poligono resta quello dei pezzi della rete piana; i segmenti sono
- `_open(edges: List[Edge]) -> list` — L390

#### `topo/core/primitives/__init__.py` — 11 lines

No module-level function or class.

#### `topo/core/primitives/fitting.py` — 221 lines

_topo/core/primitives/fitting.py_

- `_split_into_stretches(points: List[Point], is_corner: List[bool], closed: bool) -> List[List[Point]]` — L48 — Spezza `points` in tratti fra due spigoli consecutivi (estremi inclusi).
- `_try_fit_arc(points: List[Point], arc_fit_tolerance: float, duplicate_tolerance: float) -> Optional[Union[ArcSeg, CircleSeg]]` — L85 — Prova un fit a cerchio su `points`; lo accetta solo se lo scostamento
- `_fit_spline(points: List[Point], degree: int, closed: bool=False) -> SplineSeg` — L111 — Un solo SplineSeg passante per `points` (curva di fit globale, non ai
- `fit_primitives(points: List[Point], is_corner: List[bool], closed: bool=True, min_points_for_spline: int=DEFAULT_MIN_POINTS_FOR_SPLINE, spline_degree: int=DEFAULT_SPLINE_DEGREE, duplicate_tolerance: float=DEFAULT_DUPLICATE_TOLERANCE, arc_fit_tolerance: Optional[float]=DEFAULT_ARC_FIT_TOLERANCE) -> List[Union[LineSeg, ArcSeg, CircleSeg, SplineSeg]]` — L132 — Spezza `points` sui corner marcati in `is_corner` e rifitta ogni tratto: un
- `simplify_points(points: List[Point], closed: bool=True, angle_threshold_deg: float=DEFAULT_ANGLE_THRESHOLD_DEG, min_points_for_spline: int=DEFAULT_MIN_POINTS_FOR_SPLINE, spline_degree: int=DEFAULT_SPLINE_DEGREE, duplicate_tolerance: float=DEFAULT_DUPLICATE_TOLERANCE, arc_fit_tolerance: Optional[float]=DEFAULT_ARC_FIT_TOLERANCE) -> List[Union[LineSeg, ArcSeg, CircleSeg, SplineSeg]]` — L198 — `detect_corners` + `fit_primitives` in un solo passo — comodo quando serve

#### `topo/core/primitives/polygon_builder.py` — 60 lines

_core/primitives/polygon_builder.py_

- `build_polygon(primitives: List[LineSeg \| ArcSeg \| SplineSeg \| CircleSeg \| EllipseSeg], tolerance: float=0.01) -> Optional[Polygon]` — L19 — Costruisce un Polygon shapely da una lista di primitive geometriche.
- `_make_polygon(pts: list) -> Optional[Polygon]` — L48

#### `topo/core/primitives/segments.py` — 704 lines

_topo/core/primitives/segments.py_

- **class** `LineSeg` — L44
  - methods: `discretize`, `reversed`, `rotated`
- `_rotate_point(pt: Point, angle: float, origin: Point) -> Point` — L71 — Ruota `pt` di `angle` radianti (CCW) attorno a `origin`.
- `_angular_sweep(start: float, end: float, ccw: bool) -> float` — L83 — Angolo spazzato in radianti, sempre positivo, percorrendo da `start` a
- `point_on_circle(center: Point, radius: float, angle: float) -> Point` — L97 — Punto della circonferenza (`center`, `radius`) all'angolo dato (radianti).
- `angle_from_start(center: Point, start_angle: float, ccw: bool, pt: Point) -> float` — L102 — Angolo, in [0, 2π), da percorrere partendo da `start_angle` nel verso
- `_sagitta_step(radius: float, tolerance: float) -> Optional[float]` — L112 — Angolo massimo di una corda che dista al più `tolerance` dall'arco di
- **class** `ArcSeg` — L129
  - methods: `_sweep`, `discretize`, `_point_at`, `reversed`, `rotated`, `from_chord`
- `_bspline_find_span(t: float, degree: int, knots: List[float], n: int) -> int` — L258 — Indice `i` tale che `knots[i] <= t < knots[i+1]` (ricerca binaria, "The
- `_point_to_segment_distance(p: Point, a: Point, b: Point) -> float` — L276 — Distanza perpendicolare di `p` dal segmento `a`-`b` (0 se `a == b`).
- `_refine_segment(evaluate, t0: float, t1: float, p0: Point, p1: Point, tolerance: float, out: List[Point], depth: int, max_depth: int=8, max_points: int=MAX_SEGMENTS_SPLINE * 4) -> None` — L288 — Suddivide `[t0, t1]` finché il punto medio (valutato con `evaluate(t)`)
- `_adaptive_polyline(evaluate, t_min: float, t_max: float, n_initial: int, tolerance: float) -> List[Point]` — L317 — Discretizza una curva parametrica valutata da `evaluate(t) -> Point` fra
- **class** `SplineSeg` — L338
  - methods: `reversed`, `rotated`, `_evaluate`, `discretize`
- `segment_endpoints(segment) -> Tuple[Point, Point]` — L506 — (start, end) di un segmento primitivo, in coordinate XY non arrotondate.
- `segment_is_closed(segment, tolerance: float=DEFAULT_TOLERANCE) -> bool` — L542 — True se gli endpoint del segmento coincidono entro ``tolerance``.
- **class** `CircleSeg` — L554 — Cerchio geometrico puro.
  - methods: `reversed`, `rotated`, `discretize`
- **class** `EllipseSeg` — L600 — Ellisse (o arco ellittico) geometrico puro — stessa parametrizzazione del
  - methods: `_sweep`, `_point_at`, `discretize`, `reversed`, `rotated`

#### `topo/core/primitives/trim.py` — 186 lines

_topo/core/primitives/trim.py_

- `sub_segment(seg, a: Point, b: Point, via: Point)` — L26 — Il tratto di `seg` da `a` a `b` (punti sulla curva, o a una tolleranza
- `_on_line(seg: LineSeg, pt: Point) -> Point` — L47 — Proiezione di `pt` sulla retta, dentro i suoi due estremi.
- `_sub_angular(seg, a: Point, b: Point, via: Point)` — L61
- `_clamp(offset: float, sweep: float) -> float` — L86 — Un punto appena oltre un estremo (entro tolleranza) sta su quell'estremo.
- `_angle_of(seg, pt: Point) -> float` — L93 — Angolo (o parametro dell'ellisse) di `pt` visto dal centro della curva.
- `_angular(seg, lo: float, hi: float, ccw: bool)` — L104
- `_sub_spline(seg: SplineSeg, a: Point, b: Point) -> Optional[SplineSeg]` — L115
- `_spline_param(seg: SplineSeg, pt: Point, lo: float, hi: float) -> float` — L146 — Parametro del punto della spline più vicino a `pt`: campioni, poi
- `_insert_to_degree(p: int, knots: List[float], cpw: List[Tuple[float, float, float]], t: float)` — L166 — Inserisce `t` nel vettore dei nodi finché compare `p` volte (agli

#### `topo/core/topology/edge.py` — 57 lines

_core/topology/edge.py_

- **class** `Edge` — L28 — Layer intermedio tra l'entità sorgente grezza (di qualsiasi formato) e il

#### `topo/core/topology/graph.py` — 355 lines

_graph.py_

- **class** `Graph` — L59 — Grafo topologico interrogabile.
  - methods: `canonical`, `degree`, `branching_nodes`, `merged_clusters`, `connected_components`, `open_nodes`, `pruned`, `items`, `get`
- `cluster_points(points: list, epsilon: float) -> Dict[Tuple, Tuple]` — L189 — Raggruppa punti 2D entro `epsilon` e restituisce {punto -> rappresentante}.
- `_close_self_loop(edge: Edge, epsilon: float)` — L252 — ArcSeg il cui sviluppo (raggio*sweep) supera epsilon -> CircleSeg (loop degenere vero). Altrimenti `None` (sl…
- `build_node_graph(edges: list, epsilon: float=0.0) -> Graph` — L268 — Costruisce il Graph da list[Edge].
- `_edge_coords(edge: Edge, reversed_flag: bool) -> list` — L322
- `_first_coord(edge: Edge)` — L329
- `_arrival_direction(edge: Edge, rev: bool)` — L336
- `_angular_deviation(arrival_dir, edge: Edge, rev: bool)` — L345

#### `topo/core/topology/loop_finder.py` — 253 lines

_loop_finder.py_

- **class** `LoopFinder` — L28
  - methods: `find`, `_loop_to_points`, `_deduplicate_loops`
- `segments_from_loop(loop) -> list` — L161 — Segmenti nativi di un loop, orientati nel verso di percorrenza.
- `edge_styles_from_loop(loop) -> list` — L187 — Stili grezzi (linetype/colore) di un loop, allineati 1:1 con
- `loop_geometry(loop) -> Optional[Tuple[list, list, Polygon]]` — L206 — (segmenti, stili, poligono) di un loop; None se i segmenti non chiudono
- `edges_to_open_curves(edges: list, exclude_ids: set) -> list` — L220 — Converte gli Edge non assorbiti da un loop strutturale in OpenCurve.

#### `topo/core/topology/noding.py` — 266 lines

_core/topology/noding.py_

- **class** `NodedEdges` — L51 — La rete piana: i pezzi, e per ognuno l'Edge da cui viene.
  - methods: `parent_of`
- `renode(edges: List[Edge], decimals: int=NODE_DECIMALS) -> List[Edge]` — L64 — Nodi di ogni Edge ricalcolati dal punto reale del segmento a
- `split_at_crossings(edges: List[Edge], tolerance: float, decimals: int=NODE_DECIMALS) -> NodedEdges` — L72 — Spezza ogni LineSeg/ArcSeg/CircleSeg nei punti dove incrocia un altro
- `_arc_s(seg, pt)` — L102
- `_param(seg, pt)` — L106 — (parametro, distanza del punto dal segmento).
- `_param_range(seg)` — L122
- `_piece_length(seg, p0, p1)` — L126
- `_circle_as_arc(circle, start_angle=0.0)` — L132 — Un cerchio come arco di 360° da `start_angle`: stessa matematica degli archi.
- `_cutters(edge)` — L142
- `_crossings(seg, cutter)` — L154 — Incroci reali (non sul prolungamento) fra `seg` e un cutter.
- `_split_params(edge, near, tol)` — L179
- `_with_nodes(edge, seg, decimals)` — L209
- `_split(edge, params, decimals)` — L215
- `_split_circle(edge, near, tol, decimals)` — L240
- `edge_geometry(edge: Edge)` — L261 — L'edge come geometria shapely: LineString discretizzata, Point se degenere.

#### `topo/core/topology/non_contour_edges.py` — 75 lines

_non_contour_edges.py_

- **class** `NonContourEdgeDetector` — L44
  - methods: `__init__`, `detect`

#### `topo/core/topology/outer_face.py` — 210 lines

_core/topology/outer_face.py_

- **class** `OuterFace` — L42 — Il contorno esterno trovato, e cosa il percorso ha scartato.
  - methods: `edges`
- `outer_face(edges: List[Edge], epsilon: float=0.0) -> Optional[OuterFace]` — L59 — Contorno esterno della rete `edges` (già piana: split_at_crossings). I
- `outer_face_passes(graph: Graph, component, n_edges: int) -> dict` — L88 — {id(edge): quante volte il bordo della faccia esterna di `component`
- `_outer_face_walk(graph: Graph, component, n_edges: int) -> list` — L103 — [(edge, dal nodo, al nodo)] lungo il bordo della faccia esterna.
- `_first_step(graph: Graph, component)` — L133 — L'edge che contiene il punto più a sinistra del componente, percorso
- `_leaving_angle(edge: Edge, node, graph: Graph) -> float` — L155 — Direzione con cui `edge` lascia `node`, letta a DIRECTION_SAMPLE (o a
- `_faces_union_loop(edges: List[Edge], epsilon: float)` — L176 — (loop, segments, styles, polygon) sul bordo dell'unione delle facce
- `_largest_loop(edges: List[Edge], epsilon: float)` — L202 — (loop, segments, styles, polygon) del giro di area massima.

#### `topo/core/topology/rim.py` — 154 lines

_topo/core/topology/rim.py_

- `face_segments(edges: List[Edge], polygon: Polygon, band: float)` — L29 — (segments, styles) lungo il bordo esterno di `polygon`, in senso
- `_side_cover(pts: list, geoms: list, band: float) -> List[set]` — L60 — Per ogni lato dell'anello, gli (edge, verso) che distano meno di `band`
- `_sense(geom, mid, p, q, step: float) -> int` — L77 — +1 se il lato p→q va nel verso di `geom` vicino a `mid`, -1 se contro.
- `_rim_runs(pts: list, geoms: list, cover: List[set]) -> list` — L87 — [((edge, verso), primo vertice, ultimo vertice)] lungo l'anello: copertura greedy
- `_trimmed(seg, a, b, via, band: float)` — L142 — `seg` da `a` a `b`: un capo entro `band` da un estremo di `seg` è

### `topo/` (root)

#### `topo/inspect.py` — 337 lines

_topo/inspect.py_

- `_h(title: str) -> None` — L42
- `_p(x, nd: int=2) -> str` — L46 — Formatta un punto (x, y) con nd decimali.
- `_role(r) -> str` — L53 — Nome del ruolo come stringa piatta ('outer'), non 'ContourRole.OUTER'.
- `inspect_dxf(path: str, entities: bool=True, limit: Optional[int]=40) -> None` — L62 — Apre un DXF/DWG con ezdxf e stampa cosa contiene, senza toccare topo.
- `_describe_dxf_entity(e) -> str` — L104
- `inspect_document(doc, graph: bool=True, limit: Optional[int]=60) -> None` — L141 — Stampa un Document prodotto da topo.load_dxf(): cosa ha estratto e
- `_describe_segment(seg) -> str` — L200
- `inspect_result(result, coords: bool=False) -> None` — L229 — Stampa un Result dopo heal(): il prodotto vero di topo.
- `_sub_part(i: int, cluster, coords: bool) -> None` — L277
- `inspect_file(path: str, tolerance: float=DEFAULT_NODE_TOLERANCE, role_rules: Sequence[RoleRule]=(), run_heal: bool=True, entities: bool=True, coords: bool=False) -> None` — L307 — Apre un file e stampa i tre livelli in fila:

### `topo/io/`

#### `topo/io/dxf.py` — 494 lines

_topo/io/dxf.py_

- `to_dxf(result: Result, source_doc: Optional[Document]=None, filter_cluster: Optional[Callable[[Cluster], bool]]=None, include_annotations: bool=True, include_trash: bool=True, annotation_layer: Optional[str]=LAYER_ANNOTATION, role_styles: Optional[Dict[str, RoleStyle]]=None, allow_invalid: bool=True) -> 'ezdxf.document.Drawing'` — L48 — Crea un documento DXF nuovo (R2010) e vi materializza il Result.
- `cluster_passes_min_area(cluster: Cluster, min_area: float) -> bool` — L157 — True se la parte supera la soglia di area minima (min_area <= 0 = nessun filtro).
- `split(result: Result, source_doc: Optional[Document]=None, namer: Optional[Callable]=None, include_annotations: bool=True, min_area: float=DEFAULT_MIN_CLUSTER_AREA, exclude_types: Set[str]=None, on_part: Optional[Callable]=None, annotation_layer: Optional[str]=LAYER_ANNOTATION, role_styles: Optional[Dict[str, RoleStyle]]=None) -> List['ezdxf.document.Drawing']` — L162 — Materializza un Result in un Drawing per parte.
- `_write_annotations(msp, annotations: List[Annotation], written_clusters: List[Cluster], all_clusters: List[Cluster], annotation_layer: Optional[str], restrict_to_written: bool) -> None` — L230 — Riscrive le annotazioni testuali della sorgente nel documento di output.
- `_emit_annotation(msp, ann: Annotation, annotation_layer: Optional[str]) -> None` — L268
- `_emit_note(msp, note: Note, attribs: dict) -> None` — L278
- `_emit_rendered(msp, ann, attribs: dict) -> None` — L304 — DIMENSION / LEADER: ri-materializza l'immagine appiattita. I testi in
- `_trash_probe_point(trash) -> Optional[tuple]` — L333 — Punto rappresentativo di un'entità trash, per assegnarla a una parte.
- `_write_trash(msp, result: Result, written_clusters: List[Cluster], all_clusters: List[Cluster], restrict_to_written: bool) -> None` — L349 — Materializza `result.trash_entities`.
- `_write_attached_features(msp, cluster: Cluster) -> None` — L399 — Ogni collezione di `cluster.detected` (D70, D90): topo non sa cosa siano.
- `_remove_excluded_entities(msp, excluded_upper: Set[str]) -> None` — L430
- `_setup_layers(doc) -> None` — L436
- `_ensure_layer(doc, name: str) -> None` — L445 — Crea il layer `name` col suo colore canonico se non esiste già. Serve per i
- `_outer_polygons(clusters) -> list` — L454 — (cluster, poligono dell'outer) per ogni cluster che ne ha uno.
- `_apply_role_styles(doc, role_styles: Optional[Dict[str, 'RoleStyle']]) -> None` — L463 — Applica gli override di `role_styles` (D37) ai layer DXF: crea il layer

#### `topo/io/exporter.py` — 332 lines

_exporter.py_

- `build_metadata(cluster: Cluster, schema: dict=None, extra: dict=None) -> dict` — L23 — Costruisce il dict dei metadati per un Cluster
- `set_schema(schema: dict)` — L100 — Imposta uno schema esterno come schema attivo.
- `save_json(result: Result, path: str, indent: int=2, extra_metadata: Optional[Callable[[Cluster], dict]]=None)` — L117 — Salva i metadati in JSON secondo lo schema di metadata_schema.py.
- `to_json(result: Result, indent: int=2, extra_metadata: Optional[Callable[[Cluster], dict]]=None) -> str` — L147 — Restituisce i metadati come stringa JSON secondo schema. Vedi `save_json` per `extra_metadata`.
- `save_xml(result: Result, path: str, extra_metadata: Optional[Callable[[Cluster], dict]]=None)` — L170 — Salva i metadati in XML secondo lo schema di metadata_schema.py.
- `_dict_to_xml(d: dict, parent: ET.Element)` — L230 — Converte ricorsivamente un dict in sotto-elementi XML.
- `to_nester_input(result: Result) -> list` — L244 — Produce l'input per il nester: coordinate grezze + metadati base.
- `_outer_entity(doc)` — L266 — L'entità su layer OuterContour che porta gli XDATA: prima una polilinea,
- `write_metadata_to_dxf(doc, cluster: Cluster, extra: Optional[dict]=None)` — L278 — Scrive i metadati come XDATA sull'entità OuterContour.
- `read_metadata_from_dxf(doc) -> dict` — L307 — Legge i metadati TOPO XDATA dall'entità OuterContour.

#### `topo/io/svg.py` — 195 lines

_io/svg.py_

- `_fmt(pts) -> str` — L23 — Lista di [x, y] → stringa 'x0,y0 x1,y1 …' per points= di polyline/polygon.
- `_shape(entry: dict, stroke_w: float, true_circles: bool) -> str` — L28
- `to_svg(result: Result, tolerance: float=0.05, include_trash: bool=True, include_annotations: bool=True, padding: float=0.03, background: Optional[str]='#1e1e1e', true_circles: bool=True, stroke_width: Optional[float]=None, size: Optional[str]=None, units: Optional[str]=None, allow_invalid: bool=True) -> str` — L45 — `Result` → stringa SVG completa (`<svg>…</svg>`).
- `save_svg(result: Result, path: str, **kwargs) -> None` — L168 — Scrive `to_svg(result, **kwargs)` su file.
- `_scan_bbox(vm: dict) -> Optional[list]` — L175 — bbox da tutti i punti del view model — fallback quando vm['bbox'] è None.

#### `topo/io/text.py` — 269 lines

_io/text.py_

- **class** `_Writer` — L43 — Numeri arrotondati e id dei contorni per una sola chiamata di `to_text`.
  - methods: `__init__`, `num`, `pt`, `deg`, `label`, `segment`, `spline`, `contour`, `detected_item`
- `_first_point(s) -> Optional[tuple]` — L153 — Un punto che sta sul segmento, per dire in quale pezzo cade.
- `_uniform_knots(knots, degree: int) -> bool` — L161 — Nodi bloccati agli estremi e passo interno costante: non serve scriverli.
- `to_text(result: Result, source_name: str='', decimals: int=3, spline_data: bool=False) -> str` — L172 — Il `Result` come testo per un modello linguistico (`.topo.md`).
- `save_text(result: Result, path: str \| Path, source_name: str='', decimals: int=3, spline_data: bool=False) -> None` — L266 — Scrive `to_text(result)` su `path` (per convenzione `<nome>.topo.md`).

#### `topo/io/view_model.py` — 191 lines

_io/view_model.py_

- `_round_points(seq) -> list` — L31 — Lista di punti (2D o 3D) → lista di [x, y] arrotondati.
- `_poly_points(polygon) -> list` — L36 — Vertici dell'anello esterno di un polygon shapely come lista di [x, y].
- `_track(segments, tolerance: float) -> list` — L43 — Traccia aperta (lista di segmenti nativi) discretizzata a lista di [x, y].
- `_contour_entry(contour, tolerance: float) -> dict` — L48
- `_feature_entries(item, tolerance: float) -> list` — L56 — Un elemento dell'overlay (MAP.md D90) → una voce per contorno: ruolo,
- `_features(cluster, tolerance: float) -> dict` — L86 — `cluster.detected` per nome → lista di voci disegnabili.
- `_trash_entry(trash, tolerance: float) -> dict` — L96
- `_annotation_entry(ann) -> dict` — L106
- `_bbox_of(clusters) -> Optional[list]` — L116
- `to_view_model(result: Result, tolerance: float=0.05, include_trash: bool=True, include_annotations: bool=True) -> dict` — L128 — `Result` → dizionario JSON-ready con la geometria di ogni feature.
- `_palette_dict() -> dict` — L180 — role (stringa) → colore hex, per la legenda di un renderer.

### `topo/model/`

#### `topo/model/__init__.py` — 52 lines

_topo/model/__init__.py_

- `__getattr__(name)` — L46

#### `topo/model/annotation.py` — 156 lines

_topo/model/annotation.py_

- **class** `RenderedText` — L37 — Un testo dentro l'immagine appiattita di una quota/direttrice.
- **class** `RenderedGeometry` — L46 — Immagine di una quota/direttrice già appiattita in primitive pure.
  - methods: `is_empty`
- **class** `Annotation` — L63 — Base di ogni annotazione. ``position`` è il punto d'ancoraggio XY — dove
  - methods: `kind`, `display_text`
- **class** `Note(Annotation)` — L99 — Testo libero: TEXT o MTEXT.
  - methods: `display_text`
- **class** `Dimension(Annotation)` — L111 — Quota. Versione minimale: valore misurato + tipo + eventuale override del
  - methods: `display_text`, `_shown_value`
- **class** `Leader(Annotation)` — L147 — Direttrice con testo che punta a una feature.
  - methods: `display_text`

#### `topo/model/cluster.py` — 119 lines

_model/cluster.py_

- **class** `Cluster` — L15
  - methods: `features`, `overlay_voids`, `polygon_with_holes`, `bbox`, `area`, `summary`, `to_dict`

#### `topo/model/contour.py` — 66 lines

_model/contour.py_

- **class** `Contour(ClosedCurve)` — L36
  - methods: `from_segments`, `to_dict`

#### `topo/model/curve.py` — 79 lines

_model/curve.py_

- **class** `Curve` — L38 — Radice della gerarchia. Porta solo identità semantica e traceability.
- **class** `ClosedCurve(Curve)` — L48 — Curva chiusa: ha un polygon e una lista di segmenti.
  - methods: `area`, `bbox`
- **class** `OpenCurve(Curve)` — L73 — Curva aperta: ha segmenti ma non un polygon.

#### `topo/model/detected.py` — 74 lines

_topo/model/detected.py_

- **class** `DetectedFeature(Protocol)` — L23 — Contratto minimo di un elemento attaccato a `DetectedFeatures`: la
- **class** `DetectedFeatures` — L34 — Contenitore aperto per nome: ogni consumatore scrive sotto il nome che
  - methods: `attach`, `add`, `get`, `items`, `names`

#### `topo/model/document.py` — 54 lines

_model/document.py_

- **class** `Document` — L37 — Documento di dominio prodotto da load_dxf() / load_svg() / load_pdf().
  - methods: `node_tolerance`

#### `topo/model/result.py` — 53 lines

- **class** `Result` — L11 — Risultato completo di una sessione topo su un file DXF.
  - methods: `cluster_count`, `has_issues`, `to_dict`

#### `topo/model/role.py` — 149 lines

_model/role.py_

- **class** `ContourRole(str, Enum)` — L43 — I tre ruoli che il motore topologico conosce. **Non esaustivo** — un
- `is_structural_role(role) -> bool` — L78 — True se ``role`` è OUTER o INNER per il motore (vedi ``STRUCTURAL_ROLES``).
- `feature_role(contour, item_role)` — L90 — Il ruolo con cui si disegna un contorno di un elemento dell'overlay (D90):
- `normalize_role(value) -> str` — L112 — Ripulisce una stringa-ruolo che arriva dal chiamante (``RoleRule``,
- `role_str(role) -> str` — L142 — Valore stringa di un ruolo, che sia una costante ``ContourRole`` o una

#### `topo/model/role_rule.py` — 114 lines

_model/role_rule.py_

- **class** `RoleRule` — L35 — Una regola: se TUTTE le condizioni date sono vere, la linea prende `role`.
  - methods: `matches`
- `resolve_role(rules: Sequence[RoleRule], name: str, style: EdgeStyle) -> str` — L88 — Ruolo della prima regola che matcha, in ordine; `unknown` se nessuna.
- `name_rules(mapping: Dict[str, str]) -> List[RoleRule]` — L96 — Scorciatoia: {nome: ruolo} → una RoleRule(name=...) per voce.
- `_color_index(value: Union[int, str]) -> int` — L105 — Intero ACI da intero, stringa numerica ("4") o nome standard ("cyan").

#### `topo/model/style.py` — 62 lines

_model/style.py_

- **class** `EdgeStyle` — L38
  - methods: `is_dashed`, `dash_kind`

### `topo/` (root)

#### `topo/primitives.py` — 19 lines

_topo/primitives.py_

No module-level function or class.

#### `topo/recipes.py` — 52 lines

_topo/recipes.py_

- `split_to_files(doc: Document, output_folder, label='', source_file='', tolerance=None, namer=None, include_annotations=True, min_area=DEFAULT_MIN_CLUSTER_AREA, exclude_types=None, annotation_layer=LAYER_ANNOTATION, is_structural=None) -> Result` — L23 — Pipeline multi-pezzo + salvataggio su disco: heal → split → `.saveas()` per

### `topo/rules/`

#### `topo/rules/metadata_schema.py` — 38 lines

_metadata_schema.py_

No module-level function or class.

#### `topo/rules/palette.py` — 170 lines

_rules/palette.py_

- `role_to_color(role) -> int` — L74 — Colore ACI di un ruolo. Ruolo noto → il suo colore semantico;
- `role_to_hex(role, fallback: str='#ff0000') -> str` — L88 — Colore hex CSS di un ruolo. Un colore registrato (`register_role_style`)
- **class** `RoleStyle` — L107 — Override, indipendente dal formato, dell'aspetto visivo di un ruolo in
- `register_role_style(role, style: RoleStyle) -> None` — L157 — Registra uno `RoleStyle` per `role`, valido per ogni render successivo
- `registered_role_styles() -> dict` — L168 — Copia del registro attivo — letta dai renderer, mai mutata da loro.

#### `topo/rules/validator.py` — 167 lines

_rules/validator.py_

- `validate(doc: Document) -> Result` — L29 — Valida l'input prima di heal().
- `validate_result(result: Result) -> Result` — L128 — Valida i Cluster dentro un Result già popolato da heal().

### `topo/` (root)

#### `topo/steps.py` — 52 lines

_topo/steps.py_

No module-level function or class.

### `topo/tools/`

#### `topo/tools/__init__.py` — 18 lines

_topo/tools/_

No module-level function or class.

#### `topo/tools/anchor.py` — 192 lines

_topo/tools/anchor.py_

- `anchor_annotations(result: Result, snap_distance: float=0.0, leader_distance: float=LEADER_TARGET_DISTANCE) -> Result` — L34 — Assegna ``cluster_ref`` a ogni annotazione di ``result.annotations``.
- `leader_target(result: Result, leader: Leader, distance: float=LEADER_TARGET_DISTANCE) -> Optional[str]` — L73 — L'elemento indicato dalla punta (``vertices[0]``) di ``leader``, come
- `dimension_references(result: Result, dimension: Dimension, distance: float=LEADER_TARGET_DISTANCE) -> list` — L101 — Gli elementi fra cui ``dimension`` misura, come percorsi in ``result``
- `_on_boundary(elements, point, distance: float) -> Optional[str]` — L119 — L'elemento col bordo più vicino a ``point``, se entro ``distance``.
- `resolve_target(result: Result, target: Optional[str]) -> Any` — L126 — L'oggetto (contorno o feature) a cui punta un ``target``, o ``None``.
- `_elements(result: Result) -> Iterator[Tuple[str, Any, bool]]` — L147 — (percorso, geometria shapely, è chiuso) per contorni e feature di ogni cluster.
- `_item_geometry(item)` — L162
- `_size(geom, closed: bool) -> float` — L170 — A parità di distanza vince l'elemento più piccolo: un foro sul bordo del pezzo.
- `_assign(position, refs, snap_distance: float) -> Optional[int]` — L175
- `_nearest_within(probe: Point, refs, snap_distance: float) -> Optional[int]` — L184 — L'indice della parte più vicina a ``probe``, se entro ``snap_distance`` (> 0).

#### `topo/tools/inject.py` — 97 lines

_inject.py_

- `inject(result, data_injector: Optional[Callable]=None, snap_distance: float=0.0)` — L39 — Arricchisce i Cluster con i dati estratti da un `data_injector` esterno.
- `_texts_by_part(result, snap_distance: float) -> Dict[int, List[str]]` — L74 — Testi di `result.annotations` per indice di parte. Un testo coperto da più

#### `topo/tools/non_contour.py` — 50 lines

_topo/tools/non_contour.py_

- `non_contour_candidates(doc: Document, tolerance: Optional[float]=None) -> List[Edge]` — L40 — Edge di `doc.edges` che il criterio topologico di `heal()` escluderebbe dal

#### `topo/tools/rotate.py` — 268 lines

_topo/tools/rotate.py_

- `structural_segments(result: Result, include_inners: bool=False) -> list` — L73 — Segmenti nativi dei contorni strutturali di ogni cluster: sempre
- `longest_structural_segment(result: Result, include_inners: bool=False) -> Tuple[Optional[object], float, Optional[float]]` — L89 — `(segment, length, angle_deg)` del segmento più lungo fra
- `_rotate_contour(contour: Contour, angle_rad: float, origin: Point) -> Contour` — L108
- `rotate_cluster(cluster: Cluster, angle_rad: float, origin: Point=(0.0, 0.0)) -> Cluster` — L117 — Nuovo `Cluster` con `outer`/`inners` ruotati di `angle_rad` (radianti,
- `rotate_result(result: Result, angle_rad: float, origin: Point=(0.0, 0.0)) -> Result` — L147 — Nuovo `Result` con ogni cluster (`rotate_cluster`), `trash_entities`
- `rotate_document(doc: Document, angle_rad: float, origin: Point=(0.0, 0.0)) -> Document` — L187 — Nuovo `Document` con ogni `edge.segment` ruotato di `angle_rad`
- `_result_bbox_center(result: Result) -> Point` — L224 — Centro del bbox unito degli outer di tutti i cluster — vedi `rotate_to_longest`.
- `rotate_to_longest(result: Result, include_inners: bool=False, target_angle_deg: float=0.0, origin: Optional[Point]=None) -> Tuple[Result, float]` — L240 — Ruota `result` (già sano, da un `heal()` già fatto dal chiamante) in modo

#### `topo/tools/tabs.py` — 287 lines

_topo/tools/tabs.py_

- `_sub(a: Point, b: Point) -> Point` — L51
- `_add(a: Point, b: Point) -> Point` — L55
- `_scale(v: Point, s: float) -> Point` — L59
- `_dot(a: Point, b: Point) -> float` — L63
- `_unit_vector(v: Point) -> Point` — L67
- `_perp(v: Point) -> Point` — L74 — Ruota `v` di 90° (verso arbitrario, coerente fra le due chiamate).
- **class** `BridgeTab` — L84 — Risultato di un singolo ponte. `*_cut_{a,b}` sono `(punto, indice_lato)`
- `bridge_tabs(parent_points: List[Point], child_points: List[Point], anchor_parent: Point, anchor_child: Point, tab_width: float) -> BridgeTab` — L98 — Costruisce UNA linguetta fra `child_points` (contorno chiuso, il figlio
- `_cumulative_lengths_closed(points: List[Point]) -> List[float]` — L158 — `cum[i]` = distanza cumulata da `points[0]` a `points[i]` (lato i-1->i).
- `_split_closed_polyline_at_cuts(points: List[Point], cuts: List[Tuple[int, Point, int]]) -> List[List[Point]]` — L166 — Spezza il contorno chiuso `points` sui tagli in `cuts` — ognuno
- **class** `NestedBridgeResult` — L208 — Risultato per UNA coppia isola/genitore-diretto trovata nella gerarchia.
- `_discretize_closed(contour, tolerance: float) -> List[Point]` — L217 — Punti grezzi chiusi di un `Contour` (senza il punto di chiusura duplicato).
- `_ray_exit_point(points: List[Point], center: Point, direction: Point) -> Point` — L225 — Punto in cui il raggio da `center` verso `direction` esce dal contorno chiuso `points`.
- `bridge_nested_tabs(cluster, tab_width: float, tab_count: int=4, discretize_tolerance: float=0.05) -> List[NestedBridgeResult]` — L236 — Cammina `cluster.inners` (che porta `depth`/`parent` per ogni contorno,

## Internal dependencies

Which `topo` modules each module imports — "what works with what". Modules with no internal import are omitted.

| module | imports |
|---|---|
| `topo/__init__.py` | `topo` · `topo.adapters.dxf.loader` · `topo.adapters.geometry.loader` · `topo.adapters.pdf.loader` · `topo.core` · `topo.core.heal` · `topo.core.island` · `topo.core.primitives.fitting` · `topo.inspect` · `topo.io.dxf` · `topo.io.exporter` · `topo.io.svg` · `topo.io.text` · `topo.io.view_model` · `topo.model` · `topo.model.role` · `topo.model.role_rule` · `topo.recipes` · `topo.rules.palette` · `topo.rules.validator` · `topo.tools.anchor` · `topo.tools.inject` · `topo.tools.non_contour` · `topo.tools.rotate` |
| `topo/adapters/dxf/adapter.py` | `topo.adapters.dxf.parser` · `topo.core.adapter_base` · `topo.core.geometry.measure` · `topo.core.primitives.polygon_builder` · `topo.core.primitives.segments` · `topo.core.topology.edge` · `topo.model.document` · `topo.model.role_rule` · `topo.model.style` |
| `topo/adapters/dxf/annotation_extractor.py` | `topo.adapters.dxf.mtext` · `topo.model.annotation` |
| `topo/adapters/dxf/exporter.py` | `topo.core.primitives` · `topo.model.style` |
| `topo/adapters/dxf/layers.py` | `topo.model.role` · `topo.rules.palette` |
| `topo/adapters/dxf/loader.py` | `topo.adapters.dxf.adapter` · `topo.adapters.dxf.annotation_extractor` · `topo.adapters.dxf.sanitize` · `topo.model.document` · `topo.model.role_rule` |
| `topo/adapters/dxf/parser.py` | `topo.core.primitives` · `topo.core.primitives.segments` |
| `topo/adapters/dxf/sanitize.py` | `topo.core.healing.normalizer` |
| `topo/adapters/geometry/loader.py` | `topo.core.adapter_base` · `topo.core.geometry.build` · `topo.core.geometry.measure` · `topo.core.primitives.segments` · `topo.core.topology.edge` · `topo.model.document` · `topo.model.role` |
| `topo/adapters/pdf/graph_adapter.py` | `topo.core.geometry.measure` · `topo.core.primitives.segments` · `topo.core.topology.edge` · `topo.model.role` |
| `topo/adapters/pdf/loader.py` | `topo.adapters.pdf.extractor_adapter` · `topo.adapters.pdf.graph_adapter` · `topo.adapters.pdf.sanitize` |
| `topo/adapters/pdf/sanitize.py` | `topo.adapters.pdf.geometry_adapter` · `topo.core.geometry.measure` |
| `topo/core/adapter_base.py` | `topo.core.geometry.measure` · `topo.core.topology.edge` · `topo.model.document` |
| `topo/core/geometry/__init__.py` | `topo.core.geometry.axis` · `topo.core.geometry.build` · `topo.core.geometry.intersections` · `topo.core.geometry.lines` · `topo.core.geometry.regions` · `topo.core.geometry.shape` |
| `topo/core/geometry/axis.py` | `topo.core.primitives.segments` |
| `topo/core/geometry/build.py` | `topo.core.primitives.segments` |
| `topo/core/geometry/intersections.py` | `topo.core.primitives.segments` |
| `topo/core/geometry/measure.py` | `topo.core.primitives.segments` |
| `topo/core/geometry/points.py` | `topo.core.primitives.segments` |
| `topo/core/geometry/regions.py` | `topo.core.geometry.intersections` · `topo.core.primitives.polygon_builder` · `topo.core.primitives.segments` · `topo.core.primitives.trim` |
| `topo/core/geometry/shape.py` | `topo.core.geometry.measure` · `topo.core.primitives.segments` |
| `topo/core/heal.py` | `topo.core.healing.normalizer` · `topo.core.healing.steps` · `topo.core.primitives.segments` · `topo.core.topology.loop_finder` · `topo.model.document` · `topo.model.result` · `topo.model.role` · `topo.rules.validator` |
| `topo/core/healing/gap_solver.py` | `topo.core.geometry.intersections` · `topo.core.geometry.measure` · `topo.core.primitives.segments` · `topo.core.topology.edge` · `topo.model.role` |
| `topo/core/healing/hierarchy.py` | `topo.core.geometry.measure` · `topo.core.topology.loop_finder` · `topo.model.cluster` · `topo.model.contour` · `topo.model.curve` · `topo.model.role` |
| `topo/core/healing/islands.py` | `topo.core.topology.edge` · `topo.core.topology.noding` |
| `topo/core/healing/normalizer.py` | `topo.core.primitives.fitting` · `topo.core.primitives.segments` · `topo.core.topology.edge` · `topo.core.topology.graph` · `topo.model.role` |
| `topo/core/healing/outer_scan.py` | `topo.core.primitives.segments` · `topo.core.topology.edge` |
| `topo/core/healing/steps.py` | `topo.core.geometry.measure` · `topo.core.healing.gap_solver` · `topo.core.healing.hierarchy` · `topo.core.primitives` · `topo.core.primitives.polygon_builder` · `topo.core.primitives.segments` · `topo.core.topology.edge` · `topo.core.topology.graph` · `topo.core.topology.loop_finder` · `topo.core.topology.non_contour_edges` · `topo.model.cluster` · `topo.model.curve` · `topo.model.role` |
| `topo/core/island.py` | `topo.core.geometry.shape` · `topo.core.healing.gap_solver` · `topo.core.healing.islands` · `topo.core.healing.normalizer` · `topo.core.primitives.segments` · `topo.core.primitives.trim` · `topo.core.topology.edge` · `topo.core.topology.graph` · `topo.core.topology.loop_finder` · `topo.core.topology.noding` · `topo.core.topology.non_contour_edges` · `topo.core.topology.outer_face` · `topo.core.topology.rim` · `topo.model.cluster` · `topo.model.contour` · `topo.model.curve` · `topo.model.document` · `topo.model.result` · `topo.model.role` |
| `topo/core/primitives/__init__.py` | `topo.core.primitives.polygon_builder` · `topo.core.primitives.segments` |
| `topo/core/primitives/fitting.py` | `topo.core.geometry.points` · `topo.core.primitives.segments` |
| `topo/core/primitives/polygon_builder.py` | `topo.core.primitives` |
| `topo/core/primitives/trim.py` | `topo.core.primitives.segments` |
| `topo/core/topology/edge.py` | `topo.core.primitives.segments` · `topo.model.style` |
| `topo/core/topology/graph.py` | `topo.core.geometry.measure` · `topo.core.primitives.segments` · `topo.core.topology.edge` |
| `topo/core/topology/loop_finder.py` | `topo.core.geometry.measure` · `topo.core.primitives.polygon_builder` · `topo.core.primitives.segments` · `topo.core.topology.edge` · `topo.core.topology.graph` · `topo.model.curve` |
| `topo/core/topology/noding.py` | `topo.core.geometry.intersections` · `topo.core.geometry.measure` · `topo.core.primitives.segments` · `topo.core.topology.edge` |
| `topo/core/topology/non_contour_edges.py` | `topo.core.topology.edge` · `topo.core.topology.graph` · `topo.core.topology.noding` · `topo.core.topology.outer_face` |
| `topo/core/topology/outer_face.py` | `topo.core.primitives.segments` · `topo.core.topology.edge` · `topo.core.topology.graph` · `topo.core.topology.loop_finder` · `topo.core.topology.noding` · `topo.core.topology.rim` |
| `topo/core/topology/rim.py` | `topo.core.primitives.segments` · `topo.core.primitives.trim` · `topo.core.topology.edge` · `topo.core.topology.noding` |
| `topo/inspect.py` | `topo.adapters.dxf.loader` · `topo.core.geometry.measure` · `topo.core.heal` · `topo.core.primitives.segments` · `topo.core.topology.graph` · `topo.model.document` · `topo.model.role_rule` |
| `topo/io/dxf.py` | `topo.adapters.dxf.exporter` · `topo.adapters.dxf.layers` · `topo.core.geometry.measure` · `topo.model` · `topo.model.annotation` · `topo.model.document` · `topo.model.role` · `topo.rules.palette` |
| `topo/io/exporter.py` | `topo.adapters.dxf.layers` · `topo.model` · `topo.rules.metadata_schema` |
| `topo/io/svg.py` | `topo.io.view_model` · `topo.model` |
| `topo/io/text.py` | `topo.core.geometry.shape` · `topo.core.primitives.segments` · `topo.model` · `topo.model.annotation` |
| `topo/io/view_model.py` | `topo.core.geometry.measure` · `topo.model` · `topo.model.role` · `topo.rules.palette` |
| `topo/model/__init__.py` | `topo.core.topology.edge` · `topo.model.annotation` · `topo.model.cluster` · `topo.model.contour` · `topo.model.curve` · `topo.model.detected` · `topo.model.document` · `topo.model.result` · `topo.model.role` · `topo.model.style` |
| `topo/model/cluster.py` | `topo.model.contour` |
| `topo/model/contour.py` | `topo.core.primitives.polygon_builder` · `topo.core.primitives.segments` · `topo.model.curve` |
| `topo/model/curve.py` | `topo.core.primitives.segments` · `topo.model.style` |
| `topo/model/document.py` | `topo.core.topology.edge` · `topo.model.annotation` |
| `topo/model/result.py` | `topo.model.annotation` · `topo.model.cluster` |
| `topo/model/role_rule.py` | `topo.model.role` · `topo.model.style` |
| `topo/primitives.py` | `topo.core.primitives.segments` · `topo.core.primitives.trim` |
| `topo/recipes.py` | `topo.adapters.dxf.layers` · `topo.core.heal` · `topo.io.dxf` · `topo.model.document` · `topo.model.result` |
| `topo/rules/palette.py` | `topo.model.role` |
| `topo/rules/validator.py` | `topo.core.primitives.segments` · `topo.core.topology.graph` · `topo.model` · `topo.model.document` |
| `topo/steps.py` | `topo.core.healing.islands` · `topo.core.healing.normalizer` · `topo.core.healing.steps` · `topo.core.topology.loop_finder` · `topo.core.topology.noding` · `topo.core.topology.outer_face` |
| `topo/tools/__init__.py` | `topo.tools.anchor` · `topo.tools.inject` |
| `topo/tools/anchor.py` | `topo.model.annotation` · `topo.model.result` |
| `topo/tools/inject.py` | `topo.tools.anchor` |
| `topo/tools/non_contour.py` | `topo.core.healing.steps` · `topo.core.topology.edge` · `topo.model.document` |
| `topo/tools/rotate.py` | `topo.core.geometry.measure` · `topo.core.primitives.segments` · `topo.model.cluster` · `topo.model.contour` · `topo.model.curve` · `topo.model.document` · `topo.model.result` |
| `topo/tools/tabs.py` | `topo.core.geometry.intersections` · `topo.core.geometry.measure` · `topo.core.primitives.segments` |

