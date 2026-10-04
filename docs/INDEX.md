# forge — code index

**Generated file — do not edit by hand.** Regenerate with:

```
python scripts/gen_index.py
```

What this is: the lookup table of *what already exists* in the package, down to internal helpers. `docs/API.md` documents the public surface (`forge.<name>`) with full cards; this file lists every module-level function and class so nothing gets rewritten because it was not found. Signatures and docstring lines come straight from the source, so they cannot drift.

`71` modules · `341` module-level functions · `56` classes · `12789` lines of code.

Sections: [Lookup](#lookup) · [Duplicate names](#duplicate-names) · [Dependency rule](#dependency-rule) · [By module](#by-module) · [Internal dependencies](#internal-dependencies)

---

## Lookup

Every module-level name in the package, alphabetically. **Search here before writing a new helper.**

| name | kind | location | what |
|---|---|---|---|
| `_adaptive_polyline` | func | `forge/core/primitives/segments.py:317` | Discretizza una curva parametrica valutata da `evaluate(t) -> Point` fra |
| `_add` | func | `forge/tools/tabs.py:55` |  |
| `_add_ellipse` | func | `forge/adapters/dxf/exporter.py:161` | Materializza una EllipseSeg come ELLIPSE nativa — mai una spline: forge |
| `_add_spline` | func | `forge/adapters/dxf/exporter.py:116` | Materializza una SplineSeg come SPLINE nativa, ricostruita dalla primitiva |
| `AddSegment` | class | `forge/core/healing/gap_solver.py:84` | Istruzione: aggiungi un segmento retto tra pt_a e pt_b. |
| `anchor_annotations` | func | `forge/tools/anchor.py:34` | Assegna ``cluster_ref`` a ogni annotazione di ``result.annotations``. |
| `_angle_diff` | func | `forge/core/geometry/shape.py:158` | Differenza fra due direzioni modulo 180, in [0, 90]. |
| `angle_from_start` | func | `forge/core/primitives/segments.py:102` | Angolo, in [0, 2π), da percorrere partendo da `start_angle` nel verso |
| `_angular_deviation` | func | `forge/core/topology/graph.py:347` |  |
| `_angular_sweep` | func | `forge/core/primitives/segments.py:83` | Angolo spazzato in radianti, sempre positivo, percorrendo da `start` a |
| `Annotation` | class | `forge/model/annotation.py:63` | Base di ogni annotazione. ``position`` è il punto d'ancoraggio XY — dove |
| `annotation_anchor` | func | `forge/adapters/dxf/annotation_extractor.py:94` | Punto d'ancoraggio XY di un'entità di annotazione. |
| `_annotation_entry` | func | `forge/io/view_model.py:106` |  |
| `_annotation_signature` | func | `forge/adapters/dxf/loader.py:63` |  |
| `apply_gap_fixes` | func | `forge/core/healing/gap_solver.py:326` | Applica i GapFix restituendo una NUOVA lista di Edge — `edges` non viene mutata. |
| `_apply_role_styles` | func | `forge/io/dxf.py:463` | Applica gli override di `role_styles` (D37) ai layer DXF: crea il layer |
| `_Arc` | class | `forge/core/healing/outer_scan.py:104` |  |
| `arc_angles` | func | `forge/core/geometry/points.py:121` | `(start_angle, end_angle, ccw)` in radianti di un arco che passa per |
| `_arc_chains` | func | `forge/core/healing/normalizer.py:357` | Catene angolari di un gruppo sullo stesso cerchio. Se l'ultima catena |
| `_arc_key` | func | `forge/core/healing/normalizer.py:330` | Chiave del cerchio (centro+raggio) a precisione fissa — v. `_line_key`. |
| `_arc_point` | func | `forge/core/healing/outer_scan.py:131` |  |
| `_arc_s` | func | `forge/core/topology/noding.py:90` |  |
| `arc_seg_to_bulge` | func | `forge/adapters/dxf/exporter.py:77` |  |
| `ArcAround` | class | `forge/core/geometry/shape.py:215` | Un arco concentrico a un cerchio e più grande di lui. |
| `arcs_around` | func | `forge/core/geometry/shape.py:228` | Gli archi di `arcs` col centro entro `tolerance` da `center` e raggio |
| `ArcSeg` | class | `forge/core/primitives/segments.py:129` |  |
| `are_collinear` | func | `forge/core/geometry/lines.py:45` | I tratti `a` e `b` stanno sulla stessa retta infinita: direzioni uguali |
| `_arrival_direction` | func | `forge/core/topology/graph.py:338` |  |
| `_assign` | func | `forge/tools/anchor.py:175` |  |
| `axis_aligned_share` | func | `forge/core/geometry/axis.py:231` | Frazione della lunghezza dei `LineSeg` di `segments` orizzontale o |
| `axis_lines` | func | `forge/core/geometry/axis.py:87` | (orizzontali, verticali): i tratti che si scostano dall'asse al più di `eps`; gli altri non compaiono. |
| `AxisLine` | class | `forge/core/geometry/axis.py:73` | Un tratto orizzontale o verticale. |
| `_bbox_center` | func | `forge/adapters/dxf/annotation_extractor.py:467` |  |
| `_bbox_of` | func | `forge/io/view_model.py:116` |  |
| `bridge_nested_tabs` | func | `forge/tools/tabs.py:236` | Cammina `cluster.inners` (che porta `depth`/`parent` per ogni contorno, |
| `bridge_tabs` | func | `forge/tools/tabs.py:98` | Costruisce UNA linguetta fra `child_points` (contorno chiuso, il figlio |
| `bridged_runs` | func | `forge/core/geometry/lines.py:106` | File di due o più tratti sulla stessa retta in cui lo spazio fra un tratto |
| `BridgeTab` | class | `forge/tools/tabs.py:84` | Risultato di un singolo ponte. `*_cut_{a,b}` sono `(punto, indice_lato)` |
| `_bspline_basis_row` | func | `forge/core/geometry/points.py:179` | Le n+1 funzioni di base N_i,p(u) (Cox-de Boor, Piegl & Tiller A2.2). |
| `_bspline_find_span` | func | `forge/core/primitives/segments.py:258` | Indice `i` tale che `knots[i] <= t < knots[i+1]` (ricerca binaria, "The |
| `build_hierarchy` | func | `forge/core/healing/steps.py:250` | Albero di contenimento sui ClosedFeature: ogni radice è un ForgeCluster |
| `build_metadata` | func | `forge/io/exporter.py:23` | Costruisce il dict dei metadati per un ForgeCluster |
| `build_node_graph` | func | `forge/core/topology/graph.py:270` | Costruisce il Graph da list[Edge]. |
| `build_polygon` | func | `forge/core/primitives/polygon_builder.py:19` | Costruisce un Polygon shapely da una lista di primitive geometriche. |
| `_build_tree` | func | `forge/core/healing/hierarchy.py:78` |  |
| `_chain` | func | `forge/core/healing/normalizer.py:259` | Ordina per `lo` e incatena gli span che si toccano o si sovrappongono: |
| `chord_angle_deg` | func | `forge/core/geometry/measure.py:121` | Angolo (gradi, 0-180°) della corda da `a` a `b`. Modulo 180 perché una |
| `_circle` | func | `forge/core/geometry/shape.py:82` |  |
| `_circle_as_arc` | func | `forge/core/topology/noding.py:120` | Un cerchio come arco di 360° da `start_angle`: stessa matematica degli archi. |
| `_circle_circle_intersections` | func | `forge/core/geometry/intersections.py:67` | Intersezioni tra due circonferenze. Restituisce 0, 1 o 2 punti. |
| `_circle_line_intersections` | func | `forge/core/geometry/intersections.py:36` | Intersezioni tra la circonferenza (cx, cy, r) e la retta infinita (p1, p2). |
| `CircleSeg` | class | `forge/core/primitives/segments.py:554` | Cerchio geometrico puro. |
| `circular_geometry` | func | `forge/core/geometry/measure.py:143` | (diameter, center) se il contorno è ~circolare, altrimenti (None, None). |
| `clean_mtext` | func | `forge/adapters/dxf/mtext.py:18` | Testo semplice da una stringa MTEXT grezza: rimuove i codici di |
| `close_free_gaps` | func | `forge/core/healing/steps.py:69` | Chiude i gap fra estremi liberi entro `tolerance` col gap solver |
| `_close_self_loop` | func | `forge/core/topology/graph.py:254` | ArcSeg il cui sviluppo (raggio*sweep) supera epsilon -> CircleSeg (loop degenere vero). Altrimenti `None` (sl… |
| `ClosedFeature` | class | `forge/model/feature.py:47` | Feature con geometria chiusa: ha un polygon e una lista di segmenti. |
| `_closest_to` | func | `forge/core/geometry/intersections.py:91` | Restituisce il punto più vicino a ref tra i candidati. |
| `_cluster` | func | `forge/core/island.py:209` |  |
| `cluster_passes_min_area` | func | `forge/io/dxf.py:157` | True se la parte supera la soglia di area minima (min_area <= 0 = nessun filtro). |
| `cluster_points` | func | `forge/core/topology/graph.py:191` | Raggruppa punti 2D entro `epsilon` e restituisce {punto -> rappresentante}. |
| `cluster_values` | func | `forge/core/geometry/axis.py:55` | I valori ordinati, tenendo per ogni gruppo il più piccolo: un valore entro |
| `_collect_inners` | func | `forge/core/healing/hierarchy.py:112` | Appiattisce l'albero di contenimento in `cluster.inners` (ogni discendente |
| `CollinearRun` | class | `forge/core/geometry/lines.py:94` | Tratti sulla stessa retta, in fila lungo di essa. |
| `color_for_layer` | func | `forge/adapters/dxf/layers.py:58` | Colore DXF canonico per un layer. |
| `_color_index` | func | `forge/model/role_rule.py:105` | Intero ACI da intero, stringa numerica ("4") o nome standard ("cyan"). |
| `compute_gap_fixes` | func | `forge/core/healing/gap_solver.py:174` | Calcola i GapFix per tutti gli endpoint liberi entro tolerance. |
| `concentric_groups` | func | `forge/core/geometry/shape.py:192` | Partizione dei contorni circolari di `items` per centro: ogni cerchio sta |
| `ConcentricGroup` | class | `forge/core/geometry/shape.py:175` | Contorni circolari con lo stesso centro, dal raggio minore al maggiore. |
| `_configure_odafc` | func | `forge/adapters/dxf/loader.py:107` | Punta l'addon `odafc` all'eseguibile ODA File Converter. |
| `_continues` | func | `forge/core/geometry/shape.py:275` | `seg` prosegue `prev` sulla stessa curva, nello stesso verso? |
| `_contour` | func | `forge/core/island.py:227` | Il poligono resta quello dei pezzi della rete piana; i segmenti sono |
| `_contour_entry` | func | `forge/io/view_model.py:48` |  |
| `contour_shape` | func | `forge/core/geometry/shape.py:63` | Forma di un contorno chiuso (`ForgeContour`, o qualunque oggetto con |
| `ContourRole` | class | `forge/model/role.py:43` | I tre ruoli che il motore topologico conosce. **Non esaustivo** — un |
| `ContourShape` | class | `forge/core/geometry/shape.py:36` | kind:   circle \| stadium \| rectangle \| polygon \| other |
| `_covered_at` | func | `forge/core/geometry/axis.py:100` |  |
| `covered_rectangles` | func | `forge/core/geometry/axis.py:144` | I rettangoli allineati agli assi con ogni lato coperto almeno per |
| `CoveredRectangle` | class | `forge/core/geometry/axis.py:109` | Un rettangolo allineato agli assi i cui quattro lati sono coperti da tratti. |
| `_crossings` | func | `forge/core/topology/noding.py:142` | Incroci reali (non sul prolungamento) fra `seg` e un cutter. |
| `_cumulative_lengths_closed` | func | `forge/tools/tabs.py:158` | `cum[i]` = distanza cumulata da `points[0]` a `points[i]` (lato i-1->i). |
| `_cutters` | func | `forge/core/topology/noding.py:130` |  |
| `dangling_splines` | func | `forge/core/healing/steps.py:84` | SplineSeg aperte con almeno un estremo non collegato a nient'altro. |
| `deduplicate` | func | `forge/adapters/dxf/sanitize.py:216` | Shortcut: estrae chiavi, trova duplicati, li elimina. |
| `delete_entities` | func | `forge/adapters/dxf/sanitize.py:210` | Elimina le entità dal msp in-place. |
| `_describe_dxf_entity` | func | `forge/inspect.py:104` |  |
| `_describe_segment` | func | `forge/inspect.py:200` |  |
| `detect_corners` | func | `forge/core/geometry/points.py:43` | Per ogni punto, True se l'angolo formato dai due lati adiacenti è sotto |
| `DetectedFeature` | class | `forge/model/detected.py:23` | Contratto minimo di un elemento attaccato a `DetectedFeatures`: la |
| `DetectedFeatures` | class | `forge/model/detected.py:34` | Contenitore aperto per nome: ogni consumatore scrive sotto il nome che |
| `_dict_to_xml` | func | `forge/io/exporter.py:230` | Converte ricorsivamente un dict in sotto-elementi XML. |
| `Dimension` | class | `forge/model/annotation.py:111` | Quota. Versione minimale: valore misurato + tipo + eventuale override del |
| `_dimension_anchor` | func | `forge/adapters/dxf/annotation_extractor.py:125` | Def-point di una DIMENSION. |
| `_dimension_annotation` | func | `forge/adapters/dxf/annotation_extractor.py:189` |  |
| `_dimension_measurement` | func | `forge/adapters/dxf/annotation_extractor.py:530` |  |
| `_dimension_override` | func | `forge/adapters/dxf/annotation_extractor.py:247` | Override esplicito del testo quota, o None se la quota mostra la misura. |
| `dimension_references` | func | `forge/tools/anchor.py:101` | Gli elementi fra cui ``dimension`` misura, come percorsi in ``result`` |
| `_dimension_semantics` | func | `forge/adapters/dxf/annotation_extractor.py:229` | (dim_type, valore misurato) di una DIMENSION. |
| `_dimension_text` | func | `forge/adapters/dxf/annotation_extractor.py:511` | Testo visualizzato della quota, quando l'immagine non è espandibile. |
| `_discretize_closed` | func | `forge/tools/tabs.py:217` | Punti grezzi chiusi di un `ForgeContour` (senza il punto di chiusura duplicato). |
| `_distance` | func | `forge/core/geometry/intersections.py:32` |  |
| `document_from_msp` | func | `forge/adapters/dxf/loader.py:343` | Costruisce un ForgeDocument da un modelspace ezdxf già aperto. |
| `_dot` | func | `forge/tools/tabs.py:63` |  |
| `drop_duplicate_points` | func | `forge/core/geometry/points.py:75` | Rimuove punti consecutivi coincidenti entro `tolerance`. |
| `DxfAdapter` | class | `forge/adapters/dxf/adapter.py:229` | Adapter DXF che traduce entità DXF in Edge del dominio Forge. |
| `DxfAnnotationExtractor` | class | `forge/adapters/dxf/annotation_extractor.py:43` | Traduce le entità di annotazione di un msp in list[Annotation]. |
| `DxfEntityDispatcher` | class | `forge/adapters/dxf/parser.py:21` | Centralizza il routing per tipo di entità DXF. |
| `Edge` | class | `forge/core/topology/edge.py:28` | Layer intermedio tra l'entità sorgente grezza (di qualsiasi formato) e il |
| `_edge_coords` | func | `forge/core/topology/graph.py:324` |  |
| `edge_geometry` | func | `forge/core/topology/noding.py:246` | L'edge come geometria shapely: LineString discretizzata, Point se degenere. |
| `edge_styles_from_loop` | func | `forge/core/topology/loop_finder.py:187` | Stili grezzi (linetype/colore) di un loop, allineati 1:1 con |
| `edges_to_open_features` | func | `forge/core/topology/loop_finder.py:220` | Converte gli Edge non assorbiti da un loop strutturale in OpenFeature. |
| `EdgeStyle` | class | `forge/model/style.py:38` |  |
| `_elements` | func | `forge/tools/anchor.py:147` | (percorso, geometria shapely, è chiuso) per contorni e feature di ogni cluster. |
| `EllipseSeg` | class | `forge/core/primitives/segments.py:600` | Ellisse (o arco ellittico) geometrico puro — stessa parametrizzazione del |
| `_emit` | func | `forge/adapters/dxf/loader.py:99` | Aggiunge `msg` al canale warnings; lo stampa solo se verbose. |
| `_emit_annotation` | func | `forge/io/dxf.py:268` |  |
| `_emit_note` | func | `forge/io/dxf.py:278` |  |
| `_emit_rendered` | func | `forge/io/dxf.py:304` | DIMENSION / LEADER: ri-materializza l'immagine appiattita. I testi in |
| `_endpoint_meta` | func | `forge/core/healing/gap_solver.py:239` | Dati che il solver usa per calcolare l'intersezione, per tipo di segmento. |
| `_ends` | func | `forge/core/geometry/lines.py:27` | I due capi di un tratto: `LineString` (primo e ultimo punto) o `(start, end)`. |
| `_ensure_layer` | func | `forge/io/dxf.py:445` | Crea il layer `name` col suo colore canonico se non esiste già. Serve per i |
| `ensure_linetype` | func | `forge/adapters/dxf/exporter.py:23` | Garantisce che il linetype `name` esista in `doc` e ne ritorna il nome; |
| `_entity_style` | func | `forge/adapters/dxf/adapter.py:75` | Cattura l'aspetto EFFETTIVO (linetype/colore) di un'entità DXF in un |
| `entity_to_polygon` | func | `forge/adapters/dxf/adapter.py:212` | Converte un'entità DXF chiusa in un `Polygon` shapely, passando per le |
| `_explode_inserts` | func | `forge/adapters/dxf/sanitize.py:106` | Esplode tutti gli INSERT (blocchi) nel modelspace in entità primitive. |
| `_extent` | func | `forge/core/healing/outer_scan.py:135` | (min, max) del pezzo lungo la coordinata `a` (0 = x, 1 = y). |
| `_extract_content` | func | `forge/adapters/dxf/annotation_extractor.py:149` | Testo pulito dell'annotazione, stringa vuota se non ne ha. |
| `extract_drawings_from_page` | func | `forge/adapters/pdf/extractor_adapter.py:23` | Estrae i disegni vettoriali dalla pagina PDF e normalizza l'output. |
| `extract_keyed_entities` | func | `forge/adapters/dxf/sanitize.py:201` | Produce la lista (key, entity) per tutte le entità del msp. |
| `_f` | func | `forge/adapters/dxf/annotation_extractor.py:540` |  |
| `_fallback_anchor` | func | `forge/adapters/dxf/annotation_extractor.py:133` | Cerca un qualsiasi attributo-punto usabile. |
| `Feature` | class | `forge/model/feature.py:37` | Radice della gerarchia. Porta solo identità semantica e traceability. |
| `_feature_entries` | func | `forge/io/view_model.py:56` | Un elemento dell'overlay (MAP.md D90) → una voce per contorno: ruolo, |
| `feature_role` | func | `forge/model/role.py:90` | Il ruolo con cui si disegna un contorno di un elemento dell'overlay (D90): |
| `_features` | func | `forge/io/view_model.py:86` | `cluster.detected` per nome → lista di voci disegnabili. |
| `find_duplicates` | func | `forge/core/healing/normalizer.py:57` | Restituisce i ref delle entità duplicate (seconda occorrenza in poi). |
| `find_loops` | func | `forge/core/healing/steps.py:128` | La scala di heal() per chiudere i giri, esclusi `non_contour_ids`: |
| `find_non_contour_edges` | func | `forge/core/healing/steps.py:93` | id(edge) degli Edge che non chiudono un contorno (branching + centroide |
| `_first_coord` | func | `forge/core/topology/graph.py:331` |  |
| `_first_point` | func | `forge/io/text.py:153` | Un punto che sta sul segmento, per dire in quale pezzo cade. |
| `_first_step` | func | `forge/core/topology/outer_face.py:112` | L'edge che contiene il punto più a sinistra del componente, percorso |
| `fit_circle_kasa` | func | `forge/core/geometry/points.py:89` | Fit algebrico (Kasa) ai minimi quadrati di un cerchio su `points`: minimizza |
| `fit_primitives` | func | `forge/core/primitives/fitting.py:132` | Spezza `points` sui corner marcati in `is_corner` e rifitta ogni tratto: un |
| `_fit_spline` | func | `forge/core/primitives/fitting.py:111` | Un solo SplineSeg passante per `points` (curva di fit globale, non ai |
| `_flatten_virtual` | func | `forge/adapters/dxf/annotation_extractor.py:441` | Espande `virtual_entities()` ricorsivamente sugli INSERT (frecce a blocco). |
| `flatten_z` | func | `forge/adapters/dxf/sanitize.py:29` | Porta a 0 tutte le coordinate Z != 0 per LINE, ARC, CIRCLE, |
| `_flattened_points` | func | `forge/adapters/dxf/annotation_extractor.py:479` | Punti di un ARC o CIRCLE appiattito alla sagitta `_ARC_SAGITTA`. |
| `_fmt` | func | `forge/io/svg.py:23` | Lista di [x, y] → stringa 'x0,y0 x1,y1 …' per points= di polyline/polygon. |
| `ForgeAdapter` | class | `forge/core/adapter_base.py:23` |  |
| `ForgeCluster` | class | `forge/model/cluster.py:15` |  |
| `ForgeContour` | class | `forge/model/contour.py:29` |  |
| `ForgeDocument` | class | `forge/model/document.py:37` | Documento di dominio prodotto da load_dxf() / load_svg() / load_pdf(). |
| `ForgeResult` | class | `forge/model/result.py:11` | Risultato completo di una sessione forge su un file DXF. |
| `free_endpoints_from_edges` | func | `forge/core/healing/gap_solver.py:259` | Estrae gli endpoint liberi (grado < 2 nel grafo) dagli Edge. |
| `_gap_endpoints` | func | `forge/core/healing/gap_solver.py:288` | GapEndpoint per gli estremi di LINE / ARC / SPLINE il cui nodo (arrotondato) |
| `gap_endpoints_at_nodes` | func | `forge/core/healing/gap_solver.py:271` | GapEndpoint per gli endpoint che cadono su uno dei `nodes` — tuple di |
| `GapEndpoint` | class | `forge/core/healing/gap_solver.py:46` | Endpoint libero nel grafo topologico. |
| `_generic` | func | `forge/core/geometry/shape.py:139` |  |
| `GeometryAdapter` | class | `forge/adapters/geometry/loader.py:47` | Traduce descrizioni geometriche pure (dict) in Edge del dominio forge. |
| `_get_solver` | func | `forge/core/healing/gap_solver.py:162` |  |
| `__getattr__` | func | `forge/model/__init__.py:33` |  |
| `_graph` | func | `forge/core/healing/steps.py:267` |  |
| `Graph` | class | `forge/core/topology/graph.py:59` | Grafo topologico interrogabile. |
| `group_collinear_lines` | func | `forge/core/geometry/lines.py:61` | Tratti raggruppati per retta: [[L1, L2], [L3], ...]. Ogni gruppo prende la |
| `_h` | func | `forge/inspect.py:42` |  |
| `heal` | func | `forge/core/heal.py:38` | Legge `doc` dall'interno: un ForgeCluster per contorno esterno chiuso, |
| `HierarchyBuilder` | class | `forge/core/healing/hierarchy.py:149` |  |
| `inject` | func | `forge/tools/inject.py:39` | Arricchisce i ForgeCluster con i dati estratti da un `data_injector` esterno. |
| `_inners` | func | `forge/core/island.py:217` | Un ForgeContour inner per giro chiuso; un giro senza poligono valido no. |
| `inspect_document` | func | `forge/inspect.py:141` | Stampa un ForgeDocument prodotto da forge.load_dxf(): cosa ha estratto e |
| `inspect_dxf` | func | `forge/inspect.py:62` | Apre un DXF/DWG con ezdxf e stampa cosa contiene, senza toccare forge. |
| `inspect_file` | func | `forge/inspect.py:307` | Apre un file e stampa i tre livelli in fila: |
| `inspect_result` | func | `forge/inspect.py:229` | Stampa un ForgeResult dopo heal(): il prodotto vero di forge. |
| `interior_angle_deg` | func | `forge/core/geometry/points.py:31` | Angolo interno (gradi) in curr_pt fra i lati verso prev_pt e next_pt. |
| `interpolate_bspline` | func | `forge/core/geometry/points.py:145` | B-spline di grado `degree` che passa per tutti i `points` (interpolazione |
| `_intersections` | func | `forge/core/healing/outer_scan.py:150` | Punti del pezzo con coordinata `a` == level. |
| `interval_coverage` | func | `forge/core/geometry/axis.py:47` | Frazione di [lo, hi] coperta dall'unione degli intervalli. |
| `is_structural_role` | func | `forge/model/role.py:78` | True se ``role`` è OUTER o INNER per il motore (vedi ``STRUCTURAL_ROLES``). |
| `Island` | class | `forge/core/healing/islands.py:36` | Gruppo di Edge vicini, con la bbox che li contiene tutti. |
| `island` | func | `forge/core/island.py:69` | Legge `doc` per isole. Un ForgeCluster per isola: `outer` il contorno |
| `IslandReading` | class | `forge/core/island.py:52` | Cosa island() ha deciso su un'isola, pezzo per pezzo. |
| `_item_geometry` | func | `forge/tools/anchor.py:162` |  |
| `items_inside` | func | `forge/core/geometry/axis.py:221` | I tratti con entrambi i capi dentro `bounds` allargato di `margin`, nell'ordine dato. |
| `_joined` | func | `forge/core/geometry/shape.py:294` |  |
| `_key_for` | func | `forge/adapters/dxf/sanitize.py:154` | Restituisce una chiave hashable che identifica univocamente |
| `labeled_features` | func | `forge/core/healing/steps.py:228` | Gli Edge messi da parte da split_labeled() come feature col loro ruolo |
| `_largest_loop` | func | `forge/core/topology/outer_face.py:155` | (loop, segments, styles, polygon) del giro di area massima. |
| `Leader` | class | `forge/model/annotation.py:147` | Direttrice con testo che punta a una feature. |
| `_leader_annotation` | func | `forge/adapters/dxf/annotation_extractor.py:348` |  |
| `leader_target` | func | `forge/tools/anchor.py:73` | L'elemento indicato dalla punta (``vertices[0]``) di ``leader``, come |
| `_leader_vertices` | func | `forge/adapters/dxf/annotation_extractor.py:385` |  |
| `_leaving_angle` | func | `forge/core/topology/outer_face.py:134` | Direzione con cui `edge` lascia `node`, letta a DIRECTION_SAMPLE (o a |
| `_length` | func | `forge/core/geometry/shape.py:154` |  |
| `_Line` | class | `forge/core/healing/outer_scan.py:97` |  |
| `_line_intersection` | func | `forge/core/geometry/intersections.py:18` | Intersezione tra retta (p1,p2) e retta (p3,p4). None se parallele. |
| `_line_key` | func | `forge/core/healing/normalizer.py:93` | Chiave della retta infinita per p1->p2: (angolo canonico, offset). |
| `_line_spans` | func | `forge/core/healing/normalizer.py:208` | Span lungo la retta comune: `t` è la proiezione sulla direzione del |
| `LineSeg` | class | `forge/core/primitives/segments.py:44` |  |
| `load_dxf` | func | `forge/adapters/dxf/loader.py:219` | Apre un documento DXF o DWG e lo traduce in un ForgeDocument. |
| `load_geometry` | func | `forge/adapters/geometry/loader.py:209` | Costruisce un ForgeDocument da una lista di descrizioni geometriche pure — |
| `load_pdf` | func | `forge/adapters/pdf/loader.py:22` | Apre un documento PDF, estrae le geometrie vettoriali da tutte le pagine, |
| `local_gap_fixes` | func | `forge/core/healing/gap_solver.py:215` | Solo i fix che non spostano un estremo più di `max_move`: due rette quasi |
| `longest_segment` | func | `forge/core/geometry/measure.py:108` | `(segment, length)` del segmento più lungo in `segments` — `(None, 0.0)` |
| `longest_structural_segment` | func | `forge/tools/rotate.py:89` | `(segment, length, angle_deg)` del segmento più lungo fra |
| `loop_geometry` | func | `forge/core/topology/loop_finder.py:206` | (segmenti, stili, poligono) di un loop; None se i segmenti non chiudono |
| `loop_to_closed_feature` | func | `forge/core/healing/hierarchy.py:21` |  |
| `LoopFinder` | class | `forge/core/topology/loop_finder.py:28` |  |
| `loops_to_features` | func | `forge/core/healing/steps.py:175` | Un ClosedFeature per loop, col ruolo del primo edge; senza poligono valido, niente. |
| `LoopSearch` | class | `forge/core/healing/steps.py:37` | Come find_loops() ha chiuso (o non chiuso) i giri, gradino per gradino. |
| `_make_inner` | func | `forge/core/healing/hierarchy.py:91` |  |
| `_make_polygon` | func | `forge/core/primitives/polygon_builder.py:48` |  |
| `map_sanitized_item_to_edge` | func | `forge/adapters/pdf/graph_adapter.py:13` |  |
| `_measured_points` | func | `forge/adapters/dxf/annotation_extractor.py:272` | I punti sulla geometria fra cui la quota misura, dai def-point: |
| `_meet_or_bridge` | func | `forge/core/healing/gap_solver.py:248` | Se le due geometrie si incontrano in `ix`, porta lì entrambi gli estremi; |
| `_merge_annotations` | func | `forge/adapters/dxf/loader.py:68` | Aggiunge a `base` le annotazioni di `extra` non già presenti (per firma). |
| `merge_cocircular_overlaps` | func | `forge/core/healing/normalizer.py:339` | `merge_collinear_overlaps` per gli ArcSeg: fonde gruppi co-circolari |
| `merge_collinear_overlaps` | func | `forge/core/healing/normalizer.py:120` | Fonde gruppi di LineSeg collineari (stessa retta infinita, `_line_key`) |
| `merge_intervals` | func | `forge/core/geometry/axis.py:36` | Unisce gli intervalli che si sovrappongono o distano al più `tolerance`, in ordine. |
| `_merge_on_carrier` | func | `forge/core/healing/normalizer.py:279` | Raggruppa per supporto (`key`) gli edge di `segment_type` con ruolo |
| `merge_runs` | func | `forge/core/geometry/shape.py:243` | Segmenti consecutivi di un giro chiuso sulla stessa circonferenza (o |
| `_merged_arc` | func | `forge/core/healing/normalizer.py:383` | Il fuso di una catena cocircolare: un arco, o un cerchio se chiude il |
| `_merged_line` | func | `forge/core/healing/normalizer.py:232` | Il fuso di una catena collineare: nodi arrotondati, segmento a piena |
| `_mleader_anchor` | func | `forge/adapters/dxf/annotation_extractor.py:113` | Primo vertice della direttrice di un MULTILEADER. |
| `mleader_text` | func | `forge/adapters/dxf/mtext.py:37` | Testo grezzo di un MULTILEADER (prima della pulizia), None se assente. |
| `_moved_segment` | func | `forge/core/healing/gap_solver.py:308` | Nuovo segmento con l'endpoint `role` spostato su `new_pt`. None se non gestito. |
| `MoveEndpoint` | class | `forge/core/healing/gap_solver.py:73` | Istruzione: sposta l'endpoint role di ref al punto new_pt. |
| `name_rules` | func | `forge/model/role_rule.py:96` | Scorciatoia: {nome: ruolo} → una RoleRule(name=...) per voce. |
| `_nearest_within` | func | `forge/tools/anchor.py:184` | L'indice della parte più vicina a ``probe``, se entro ``snap_distance`` (> 0). |
| `NestedBridgeResult` | class | `forge/tools/tabs.py:208` | Risultato per UNA coppia isola/genitore-diretto trovata nella gerarchia. |
| `node_decimals_for` | func | `forge/core/geometry/measure.py:24` | Numero di decimali a cui arrotondare gli endpoint per la topologia. |
| `NodedEdges` | class | `forge/core/topology/noding.py:39` | La rete piana: i pezzi, e per ognuno l'Edge da cui viene. |
| `non_contour_candidates` | func | `forge/tools/non_contour.py:40` | Edge di `doc.edges` che l'euristica topologica di `heal()` escluderebbe dal |
| `NonContourEdgeDetector` | class | `forge/core/topology/non_contour_edges.py:41` |  |
| `_normalize` | func | `forge/core/island.py:195` | Stessi passi di heal, ma sulla griglia fine della rete piana: prima i |
| `normalize_ocs` | func | `forge/adapters/dxf/sanitize.py:19` | Normalizza il vettore di estrusione di tutte le entità OCS nel modelspace. |
| `normalize_role` | func | `forge/model/role.py:112` | Ripulisce una stringa-ruolo che arriva dal chiamante (``RoleRule``, |
| `Note` | class | `forge/model/annotation.py:99` | Testo libero: TEXT o MTEXT. |
| `num_segments_for_bulge` | func | `forge/core/geometry/measure.py:38` | Numero di segmenti per discretizzare un arco dato il suo bulge. |
| `_on_arc` | func | `forge/core/healing/outer_scan.py:127` |  |
| `_on_border` | func | `forge/core/geometry/axis.py:186` |  |
| `_on_boundary` | func | `forge/tools/anchor.py:119` | L'elemento col bordo più vicino a ``point``, se entro ``distance``. |
| `_open` | func | `forge/core/island.py:235` |  |
| `OpenFeature` | class | `forge/model/feature.py:72` | Feature con geometria aperta: ha segmenti ma non un polygon. |
| `outer_candidate_edges` | func | `forge/core/healing/outer_scan.py:72` | Per ogni asse, una quota rappresentativa (punto medio) fra ogni coppia |
| `_outer_entity` | func | `forge/io/exporter.py:266` | L'entità su layer OuterContour che porta gli XDATA: prima una polilinea, |
| `outer_face` | func | `forge/core/topology/outer_face.py:52` | Contorno esterno della rete `edges` (già piana: split_at_crossings). I |
| `_outer_face_walk` | func | `forge/core/topology/outer_face.py:82` | [(edge, dal nodo, al nodo)] lungo il bordo della faccia esterna. |
| `_outer_polygons` | func | `forge/io/dxf.py:454` | (cluster, poligono dell'outer) per ogni cluster che ne ha uno. |
| `OuterCandidates` | class | `forge/core/healing/outer_scan.py:54` | Edge candidati a bordo esterno, con i raggi che li hanno scelti. |
| `OuterFace` | class | `forge/core/topology/outer_face.py:35` | Il contorno esterno trovato, e cosa il percorso ha scartato. |
| `OuterHit` | class | `forge/core/healing/outer_scan.py:45` | Un raggio per cui l'Edge è stato l'estremo. |
| `_p` | func | `forge/inspect.py:46` | Formatta un punto (x, y) con nd decimali. |
| `_palette_dict` | func | `forge/io/view_model.py:180` | role (stringa) → colore hex, per la legenda di un renderer. |
| `_param` | func | `forge/core/topology/noding.py:94` | (parametro, distanza del punto dal segmento). |
| `_param_range` | func | `forge/core/topology/noding.py:110` |  |
| `_parse_arc` | func | `forge/adapters/dxf/parser.py:58` |  |
| `_parse_circle` | func | `forge/adapters/dxf/parser.py:127` |  |
| `_parse_ellipse` | func | `forge/adapters/dxf/parser.py:134` | Un'ELLIPSE DXF è sempre percorsa CCW da `start_param` a `end_param` |
| `_parse_line` | func | `forge/adapters/dxf/parser.py:48` |  |
| `_parse_polyline` | func | `forge/adapters/dxf/parser.py:152` |  |
| `_parse_spline` | func | `forge/adapters/dxf/parser.py:73` |  |
| `_perp` | func | `forge/tools/tabs.py:74` | Ruota `v` di 90° (verso arbitrario, coerente fra le due chiamate). |
| `_piece_length` | func | `forge/core/topology/noding.py:114` |  |
| `_pieces` | func | `forge/core/healing/outer_scan.py:113` |  |
| `_place` | func | `forge/core/healing/hierarchy.py:69` |  |
| `point_line_distance` | func | `forge/core/geometry/lines.py:36` | Distanza di `point` dalla retta infinita per `a`, `b`; da `a` se i due coincidono. |
| `point_on_circle` | func | `forge/core/primitives/segments.py:97` | Punto della circonferenza (`center`, `radius`) all'angolo dato (radianti). |
| `_point_to_segment_distance` | func | `forge/core/primitives/segments.py:276` | Distanza perpendicolare di `p` dal segmento `a`-`b` (0 se `a == b`). |
| `_poly_points` | func | `forge/io/view_model.py:36` | Vertici dell'anello esterno di un polygon shapely come lista di [x, y]. |
| `polygonize_edges` | func | `forge/core/healing/steps.py:191` | Ultima spiaggia quando nessun grafo chiude: le facce dell'intero disegno |
| `polygons_to_features` | func | `forge/core/healing/steps.py:207` | Per poligono un ClosedFeature OUTER dal bordo esterno e uno INNER per |
| `polyline_line_intersections` | func | `forge/core/geometry/intersections.py:98` | Intersezioni fra la retta infinita (p1, p2) e la spezzata `points` (ogni |
| `_polyline_points` | func | `forge/adapters/dxf/annotation_extractor.py:487` |  |
| `_raw_linetype_pattern` | func | `forge/adapters/dxf/adapter.py:52` | Pattern grezzo (lunghezza totale + tratti con segno, `+` = tratto, |
| `_ray_exit_point` | func | `forge/tools/tabs.py:225` | Punto in cui il raggio da `center` verso `direction` esce dal contorno chiuso `points`. |
| `_read_dwg` | func | `forge/adapters/dxf/loader.py:148` | Legge un file DWG usando ezdxf.addons.odafc (wrapper di ODA File Converter). |
| `read_island` | func | `forge/core/island.py:153` | Un'isola: normalizza (nodi dagli estremi reali, tassellature rifittate, |
| `read_islands` | func | `forge/core/island.py:131` | `spatial_islands` + `read_island` per ognuna, e l'annidamento: un'isola |
| `read_metadata_from_dxf` | func | `forge/io/exporter.py:307` | Legge i metadati FORGE XDATA dall'entità OuterContour. |
| `_rectangle` | func | `forge/core/geometry/shape.py:122` |  |
| `_refine_segment` | func | `forge/core/primitives/segments.py:288` | Suddivide `[t0, t1]` finché il punto medio (valutato con `evaluate(t)`) |
| `refit_tessellations` | func | `forge/core/healing/normalizer.py:455` | Una catena di almeno `min_run` LineSeg (`role == UNKNOWN`) più corti di |
| `register_role_style` | func | `forge/rules/palette.py:157` | Registra uno `RoleStyle` per `role`, valido per ogni render successivo |
| `registered_role_styles` | func | `forge/rules/palette.py:168` | Copia del registro attivo — letta dai renderer, mai mutata da loro. |
| `_remove_excluded_entities` | func | `forge/io/dxf.py:430` |  |
| `_render_block` | func | `forge/adapters/dxf/annotation_extractor.py:402` | Espande l'immagine dell'entità in strokes/fills/texts puri. |
| `RenderedGeometry` | class | `forge/model/annotation.py:46` | Immagine di una quota/direttrice già appiattita in primitive pure. |
| `RenderedText` | class | `forge/model/annotation.py:37` | Un testo dentro l'immagine appiattita di una quota/direttrice. |
| `renode` | func | `forge/core/topology/noding.py:52` | Nodi di ogni Edge ricalcolati dal punto reale del segmento a |
| `repair_merged_corners` | func | `forge/core/healing/steps.py:102` | Chiude gli angoli che il grafo esatto vede aperti e il clustering degli |
| `resolve_role` | func | `forge/model/role_rule.py:88` | Ruolo della prima regola che matcha, in ordine; `unknown` se nessuna. |
| `resolve_target` | func | `forge/tools/anchor.py:126` | L'oggetto (contorno o feature) a cui punta un ``target``, o ``None``. |
| `_result_bbox_center` | func | `forge/tools/rotate.py:231` | Centro del bbox unito degli outer di tutti i cluster — vedi `rotate_to_longest`. |
| `_ring_segments` | func | `forge/core/healing/steps.py:273` |  |
| `_role` | func | `forge/inspect.py:53` | Nome del ruolo come stringa piatta ('outer'), non 'ContourRole.OUTER'. |
| `_role_from` | func | `forge/adapters/geometry/loader.py:39` | work_type stringa (stesso vocabolario di RoleRule.role) → ruolo. Un work_type |
| `role_str` | func | `forge/model/role.py:142` | Valore stringa di un ruolo, che sia una costante ``ContourRole`` o una |
| `role_to_color` | func | `forge/rules/palette.py:74` | Colore ACI di un ruolo. Ruolo noto → il suo colore semantico; |
| `role_to_dxf_layer` | func | `forge/adapters/dxf/layers.py:73` | Nome layer DXF per un ruolo. |
| `role_to_hex` | func | `forge/rules/palette.py:88` | Colore hex CSS di un ruolo. Un colore registrato (`register_role_style`) |
| `RoleRule` | class | `forge/model/role_rule.py:35` | Una regola: se TUTTE le condizioni date sono vere, la linea prende `role`. |
| `RoleStyle` | class | `forge/rules/palette.py:107` | Override, indipendente dal formato, dell'aspetto visivo di un ruolo in |
| `rotate_cluster` | func | `forge/tools/rotate.py:117` | Nuovo `ForgeCluster` con `outer`/`inners` ruotati di `angle_rad` (radianti, |
| `_rotate_contour` | func | `forge/tools/rotate.py:108` |  |
| `rotate_document` | func | `forge/tools/rotate.py:187` | Nuovo `ForgeDocument` con ogni `edge.segment` ruotato di `angle_rad` |
| `_rotate_point` | func | `forge/core/primitives/segments.py:71` | Ruota `pt` di `angle` radianti (CCW) attorno a `origin`. |
| `rotate_result` | func | `forge/tools/rotate.py:147` | Nuovo `ForgeResult` con ogni cluster (`rotate_cluster`), `trash_entities` |
| `rotate_to_longest` | func | `forge/tools/rotate.py:247` | Ruota `result` (già sano, da un `heal()` già fatto dal chiamante) in modo |
| `round_point` | func | `forge/core/geometry/measure.py:20` |  |
| `_round_points` | func | `forge/io/view_model.py:31` | Lista di punti (2D o 3D) → lista di [x, y] arrotondati. |
| `_sagitta_step` | func | `forge/core/primitives/segments.py:112` | Angolo massimo di una corda che dista al più `tolerance` dall'arco di |
| `sample_bezier_cubic` | func | `forge/adapters/pdf/geometry_adapter.py:37` | Campiona una curva di Bezier cubica in un set di punti lineari (poligonale). |
| `sanitize` | func | `forge/adapters/dxf/sanitize.py:88` | Esegue tutti i sanitizer in sequenza sul modelspace ricevuto. |
| `sanitize_pdf_geometries` | func | `forge/adapters/pdf/sanitize.py:13` | Prende gli item geometrici grezzi estratti dall'extractor, applica la conversione |
| `save_json` | func | `forge/io/exporter.py:117` | Salva i metadati in JSON secondo lo schema di metadata_schema.py. |
| `save_svg` | func | `forge/io/svg.py:168` | Scrive `to_svg(result, **kwargs)` su file. |
| `save_text` | func | `forge/io/text.py:266` | Scrive `to_text(result)` su `path` (per convenzione `<nome>.forge.md`). |
| `save_xml` | func | `forge/io/exporter.py:170` | Salva i metadati in XML secondo lo schema di metadata_schema.py. |
| `_scale` | func | `forge/tools/tabs.py:59` |  |
| `_scan_axis` | func | `forge/core/healing/outer_scan.py:184` |  |
| `_scan_bbox` | func | `forge/io/svg.py:175` | bbox da tutti i punti del view model — fallback quando vm['bbox'] è None. |
| `_search_warnings` | func | `forge/core/heal.py:167` | Cosa racconta heal() dei gradini della scala di find_loops(). |
| `_seg_end_point` | func | `forge/adapters/dxf/exporter.py:93` |  |
| `segment_endpoints` | func | `forge/core/primitives/segments.py:506` | (start, end) di un segmento primitivo, in coordinate XY non arrotondate. |
| `segment_is_closed` | func | `forge/core/primitives/segments.py:542` | True se gli endpoint del segmento coincidono entro ``tolerance``. |
| `_segment_key` | func | `forge/adapters/dxf/adapter.py:161` | Chiave univoca per deduplicazione. |
| `segment_length` | func | `forge/core/geometry/measure.py:91` | Lunghezza reale di una primitiva nativa singola (`LineSeg`/`ArcSeg`/ |
| `segments_from_loop` | func | `forge/core/topology/loop_finder.py:161` | Segmenti nativi di un loop, orientati nel verso di percorrenza. |
| `segments_to_pts_with_bulge` | func | `forge/adapters/dxf/exporter.py:101` |  |
| `set_schema` | func | `forge/io/exporter.py:100` | Imposta uno schema esterno come schema attivo. |
| `_setup_layers` | func | `forge/io/dxf.py:436` |  |
| `_shape` | func | `forge/io/svg.py:28` |  |
| `_short_runs` | func | `forge/core/healing/normalizer.py:507` | Catene massimali: percorsi fra nodi di grado != 2, o anelli. |
| `simplify_points` | func | `forge/core/primitives/fitting.py:198` | `detect_corners` + `fit_primitives` in un solo passo — comodo quando serve |
| `_size` | func | `forge/tools/anchor.py:170` | A parità di distanza vince l'elemento più piccolo: un foro sul bordo del pezzo. |
| `_solid_points` | func | `forge/adapters/dxf/annotation_extractor.py:499` | SOLID/TRACE: 4 vertici in ordine 'a farfalla' → poligono convesso. |
| `_solve_arc_arc` | func | `forge/core/healing/gap_solver.py:126` |  |
| `_solve_arc_line` | func | `forge/core/healing/gap_solver.py:112` |  |
| `_solve_line_line` | func | `forge/core/healing/gap_solver.py:100` |  |
| `_solve_spline_any` | func | `forge/core/healing/gap_solver.py:138` |  |
| `_Span` | class | `forge/core/healing/normalizer.py:243` | Un edge come intervallo [lo, hi] sul suo supporto (posizione lungo la |
| `spanning_lines` | func | `forge/core/geometry/axis.py:199` | (ys, xs): le coordinate delle linee strettamente interne a `bounds` (bordo |
| `spatial_islands` | func | `forge/core/healing/islands.py:54` | Union-find sulle coppie di Edge a distanza <= gap_tolerance (STRtree, |
| `SplineSeg` | class | `forge/core/primitives/segments.py:338` |  |
| `_split` | func | `forge/core/topology/noding.py:200` |  |
| `split` | func | `forge/io/dxf.py:162` | Materializza un ForgeResult in un Drawing per parte. |
| `split_at_crossings` | func | `forge/core/topology/noding.py:60` | Spezza ogni LineSeg/ArcSeg/CircleSeg nei punti dove incrocia un altro |
| `_split_circle` | func | `forge/core/topology/noding.py:225` |  |
| `_split_closed_polyline_at_cuts` | func | `forge/tools/tabs.py:166` | Spezza il contorno chiuso `points` sui tagli in `cuts` — ognuno |
| `_split_into_stretches` | func | `forge/core/primitives/fitting.py:48` | Spezza `points` in tratti fra due spigoli consecutivi (estremi inclusi). |
| `split_labeled` | func | `forge/core/healing/steps.py:52` | Separa gli Edge con un ruolo già deciso e non strutturale (cornice, |
| `_split_params` | func | `forge/core/topology/noding.py:167` |  |
| `split_to_files` | func | `forge/recipes.py:23` | Pipeline multi-pezzo + salvataggio su disco: heal → split → `.saveas()` per |
| `splits_polygon` | func | `forge/core/geometry/lines.py:82` | La corda `start`-`end`, prolungata di `reach` ai due capi, divide `polygon` in due o più parti. |
| `_stadium` | func | `forge/core/geometry/shape.py:96` |  |
| `structural_loops` | func | `forge/core/healing/steps.py:164` | I loop in cui ogni edge con ruolo deciso è strutturale: un solo edge non |
| `structural_segments` | func | `forge/tools/rotate.py:73` | Segmenti nativi dei contorni strutturali di ogni cluster: sempre |
| `_style_attribs` | func | `forge/adapters/dxf/exporter.py:49` | dxfattribs per una entità in output: layer + linetype della sorgente, se |
| `_sub` | func | `forge/tools/tabs.py:51` |  |
| `_sub_part` | func | `forge/inspect.py:277` |  |
| `_synthesize_dimension` | func | `forge/adapters/dxf/annotation_extractor.py:290` | Ricostruisce l'immagine di una DIMENSION lineare dai def-point, quando il |
| `_text_item` | func | `forge/adapters/dxf/annotation_extractor.py:450` |  |
| `_texts_by_part` | func | `forge/tools/inject.py:74` | Testi di `result.annotations` per indice di parte. Un testo coperto da più |
| `_to_annotation` | func | `forge/adapters/dxf/annotation_extractor.py:60` |  |
| `to_dxf` | func | `forge/io/dxf.py:48` | Crea un documento DXF nuovo (R2010) e vi materializza il ForgeResult. |
| `to_json` | func | `forge/io/exporter.py:147` | Restituisce i metadati come stringa JSON secondo schema. Vedi `save_json` per `extra_metadata`. |
| `to_nester_input` | func | `forge/io/exporter.py:244` | Produce l'input per il nester: coordinate grezze + metadati base. |
| `to_svg` | func | `forge/io/svg.py:45` | `ForgeResult` → stringa SVG completa (`<svg>…</svg>`). |
| `to_text` | func | `forge/io/text.py:172` | Il `ForgeResult` come testo per un modello linguistico (`.forge.md`). |
| `to_view_model` | func | `forge/io/view_model.py:128` | `ForgeResult` → dizionario JSON-ready con la geometria di ogni feature. |
| `_track` | func | `forge/io/view_model.py:43` | Traccia aperta (lista di segmenti nativi) discretizzata a lista di [x, y]. |
| `track_length` | func | `forge/core/geometry/measure.py:72` | Lunghezza totale di una polilinea (somma delle corde). |
| `track_points` | func | `forge/core/geometry/measure.py:53` | Vertici di una traccia aperta come catena di segmenti nativi. |
| `track_shape_type` | func | `forge/core/geometry/measure.py:80` | `"line"` se la traccia è un solo segmento retto (2 vertici), altrimenti `"curve"`. |
| `transform_point` | func | `forge/adapters/pdf/geometry_adapter.py:27` | Converte un punto da punti PDF (pt) a millimetri (mm) |
| `_trash_entry` | func | `forge/io/view_model.py:96` |  |
| `_trash_probe_point` | func | `forge/io/dxf.py:333` | Punto rappresentativo di un'entità trash, per assegnarla a una parte. |
| `_try_fit_arc` | func | `forge/core/primitives/fitting.py:85` | Prova un fit a cerchio su `points`; lo accetta solo se lo scostamento |
| `_uniform_knots` | func | `forge/io/text.py:161` | Nodi bloccati agli estremi e passo interno costante: non serve scriverli. |
| `_unit_vector` | func | `forge/tools/tabs.py:67` |  |
| `_upgrade_to_r2010` | func | `forge/adapters/dxf/loader.py:180` | Converte un documento DXF legacy in R2010. |
| `validate` | func | `forge/rules/validator.py:29` | Valida l'input prima di heal(). |
| `validate_result` | func | `forge/rules/validator.py:128` | Valida i ForgeCluster dentro un ForgeResult già popolato da heal(). |
| `_warn_non_roundtrip_types` | func | `forge/adapters/dxf/loader.py:86` | Avvisa sui tipi di entità che to_dxf() non riscrive (HATCH, IMAGE, …). |
| `weld_degenerate_linesegs` | func | `forge/core/healing/normalizer.py:403` | Salda (non cancella) i LineSeg `role == UNKNOWN` di lunghezza reale |
| `_width_factor` | func | `forge/adapters/dxf/annotation_extractor.py:159` | Stretch orizzontale effettivo del testo (1.0 = nessuno). |
| `_with_nodes` | func | `forge/core/topology/noding.py:194` |  |
| `_write_annotations` | func | `forge/io/dxf.py:230` | Riscrive le annotazioni testuali della sorgente nel documento di output. |
| `_write_attached_features` | func | `forge/io/dxf.py:399` | Ogni collezione di `cluster.detected` (D70, D90): forge non sa cosa siano. |
| `write_metadata_to_dxf` | func | `forge/io/exporter.py:278` | Scrive i metadati come XDATA sull'entità OuterContour. |
| `write_native_segments` | func | `forge/adapters/dxf/exporter.py:267` | Materializza segmenti aperti come geometria NATIVA, una entità DXF per |
| `write_open_segments` | func | `forge/adapters/dxf/exporter.py:325` | Materializza una lista di segmenti puri come geometria APERTA su msp. |
| `write_segments` | func | `forge/adapters/dxf/exporter.py:188` | Materializza una lista di segmenti puri su msp. |
| `_write_trash` | func | `forge/io/dxf.py:349` | Materializza `result.trash_entities`. |
| `_Writer` | class | `forge/io/text.py:43` | Numeri arrotondati e id dei contorni per una sola chiamata di `to_text`. |
| `_xy` | func | `forge/adapters/dxf/annotation_extractor.py:475` |  |

## Duplicate names

No module-level name is defined in more than one module.

## Dependency rule

- `core` never imports `adapters`, `tools`, `io`
- `model` never imports `adapters`, `tools`, `io`

`TYPE_CHECKING`-only imports count as violations here and must be verified by hand.

**Clean** — no violation found.

## By module

### `forge/` (root)

#### `forge/__init__.py` — 241 lines

_forge_

No module-level function or class.

### `forge/adapters/`

#### `forge/adapters/dxf/adapter.py` — 390 lines

_forge/adapters/dxf/adapter.py_

- `_raw_linetype_pattern(lt_entry) -> Optional[Tuple[float, ...]]` — L52 — Pattern grezzo (lunghezza totale + tratti con segno, `+` = tratto,
- `_entity_style(entity) -> EdgeStyle` — L75 — Cattura l'aspetto EFFETTIVO (linetype/colore) di un'entità DXF in un
- `_segment_key(segment: Segment) -> tuple` — L161 — Chiave univoca per deduplicazione.
- `entity_to_polygon(entity, tolerance: float=DEFAULT_TOLERANCE) -> Optional[Polygon]` — L212 — Converte un'entità DXF chiusa in un `Polygon` shapely, passando per le
- **class** `DxfAdapter(ForgeAdapter)` — L229 — Adapter DXF che traduce entità DXF in Edge del dominio Forge.
  - methods: `__init__`, `to_edges`, `source_context`

#### `forge/adapters/dxf/annotation_extractor.py` — 544 lines

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

#### `forge/adapters/dxf/exporter.py` — 395 lines

_adapters/dxf/exporter.py_

- `ensure_linetype(doc, name: str, pattern: Optional[Tuple[float, ...]]=None, description: str='') -> Optional[str]` — L23 — Garantisce che il linetype `name` esista in `doc` e ne ritorna il nome;
- `_style_attribs(doc, layer: str, style: Optional[EdgeStyle]=None) -> dict` — L49 — dxfattribs per una entità in output: layer + linetype della sorgente, se
- `arc_seg_to_bulge(arc: ArcSeg) -> float` — L77
- `_seg_end_point(seg) -> Optional[tuple]` — L93
- `segments_to_pts_with_bulge(segments: list) -> list` — L101
- `_add_spline(spline: SplineSeg, msp, layer: str, style: Optional[EdgeStyle]=None) -> object` — L116 — Materializza una SplineSeg come SPLINE nativa, ricostruita dalla primitiva
- `_add_ellipse(ellipse: EllipseSeg, msp, layer: str, style: Optional[EdgeStyle]=None) -> object` — L161 — Materializza una EllipseSeg come ELLIPSE nativa — mai una spline: forge
- `write_segments(segments: List, msp, layer: str, styles: Optional[List]=None) -> Optional[object]` — L188 — Materializza una lista di segmenti puri su msp.
- `write_native_segments(segments: List, msp, layer: str, styles: Optional[List]=None) -> List[object]` — L267 — Materializza segmenti aperti come geometria NATIVA, una entità DXF per
- `write_open_segments(segments: List, msp, layer: str, styles: Optional[List]=None) -> List[object]` — L325 — Materializza una lista di segmenti puri come geometria APERTA su msp.

#### `forge/adapters/dxf/layers.py` — 92 lines

_adapters/dxf/layers.py_

- `color_for_layer(layer_name: str) -> int` — L58 — Colore DXF canonico per un layer.
- `role_to_dxf_layer(role) -> str` — L73 — Nome layer DXF per un ruolo.

#### `forge/adapters/dxf/loader.py` — 382 lines

_adapters/dxf/loader.py_

- `_annotation_signature(ann) -> tuple` — L63
- `_merge_annotations(base: list, extra: list) -> None` — L68 — Aggiunge a `base` le annotazioni di `extra` non già presenti (per firma).
- `_warn_non_roundtrip_types(msp, sink: list, verbose: bool=False) -> None` — L86 — Avvisa sui tipi di entità che to_dxf() non riscrive (HATCH, IMAGE, …).
- `_emit(sink: list, msg: str, verbose: bool=False) -> None` — L99 — Aggiunge `msg` al canale warnings; lo stampa solo se verbose.
- `_configure_odafc(sink: list=None, verbose: bool=False) -> None` — L107 — Punta l'addon `odafc` all'eseguibile ODA File Converter.
- `_read_dwg(path: str, sink: list=None, verbose: bool=False)` — L148 — Legge un file DWG usando ezdxf.addons.odafc (wrapper di ODA File Converter).
- `_upgrade_to_r2010(doc, sink: list=None, verbose: bool=False) -> object` — L180 — Converte un documento DXF legacy in R2010.
- `load_dxf(path: str, upgrade: bool=False, explode_inserts: bool=True, flatten_z_flag: bool=True, verbose: bool=False, tolerance: float=DEFAULT_NODE_TOLERANCE, role_rules: Sequence[RoleRule]=(), ignore_layers=None) -> ForgeDocument` — L219 — Apre un documento DXF o DWG e lo traduce in un ForgeDocument.
- `document_from_msp(msp, tolerance: float=DEFAULT_NODE_TOLERANCE, role_rules: Sequence[RoleRule]=(), ignore_layers=None, source_path: str='') -> ForgeDocument` — L343 — Costruisce un ForgeDocument da un modelspace ezdxf già aperto.

#### `forge/adapters/dxf/mtext.py` — 45 lines

_forge/adapters/dxf/mtext.py_

- `clean_mtext(txt) -> str` — L18 — Testo semplice da una stringa MTEXT grezza: rimuove i codici di
- `mleader_text(entity) -> Optional[str]` — L37 — Testo grezzo di un MULTILEADER (prima della pulizia), None se assente.

#### `forge/adapters/dxf/parser.py` — 193 lines

_adapters/dxf/parser.py_

- **class** `DxfEntityDispatcher` — L21 — Centralizza il routing per tipo di entità DXF.
  - methods: `__init__`, `parse`
- `_parse_line(entity, rev) -> tuple` — L48
- `_parse_arc(entity, rev) -> ArcSeg` — L58
- `_parse_spline(entity, rev) -> SplineSeg` — L73
- `_parse_circle(entity) -> CircleSeg` — L127
- `_parse_ellipse(entity, rev) -> EllipseSeg` — L134 — Un'ELLIPSE DXF è sempre percorsa CCW da `start_param` a `end_param`
- `_parse_polyline(entity, rev) -> list` — L152

#### `forge/adapters/dxf/sanitize.py` — 225 lines

_adapters/dxf/sanitize.py_

- `normalize_ocs(msp, verbose: bool=False) -> None` — L19 — Normalizza il vettore di estrusione di tutte le entità OCS nel modelspace.
- `flatten_z(msp, verbose: bool=False) -> int` — L29 — Porta a 0 tutte le coordinate Z != 0 per LINE, ARC, CIRCLE,
- `sanitize(msp, flatten_z_flag: bool=True, verbose: bool=False) -> int` — L88 — Esegue tutti i sanitizer in sequenza sul modelspace ricevuto.
- `_explode_inserts(msp, sink: list=None) -> int` — L106 — Esplode tutti gli INSERT (blocchi) nel modelspace in entità primitive.
- `_key_for(entity) -> Optional[Hashable]` — L154 — Restituisce una chiave hashable che identifica univocamente
- `extract_keyed_entities(msp) -> List[Tuple[Hashable, Any]]` — L201 — Produce la lista (key, entity) per tutte le entità del msp.
- `delete_entities(refs: List[Any], msp) -> None` — L210 — Elimina le entità dal msp in-place.
- `deduplicate(msp) -> int` — L216 — Shortcut: estrae chiavi, trova duplicati, li elimina.

#### `forge/adapters/geometry/__init__.py` — 0 lines

No module-level function or class.

#### `forge/adapters/geometry/loader.py` — 251 lines

_adapters/geometry/loader.py_

- `_role_from(entity: Dict[str, Any]) -> str` — L39 — work_type stringa (stesso vocabolario di RoleRule.role) → ruolo. Un work_type
- **class** `GeometryAdapter(ForgeAdapter)` — L47 — Traduce descrizioni geometriche pure (dict) in Edge del dominio forge.
  - methods: `__init__`, `to_edges`, `source_context`, `_round`, `_line_edge`, `_arc_edge`, `_edge`, `_circle_edge`, `_spline_edge`, `_ellipse_edge`, `_polyline_edges`
- `load_geometry(entities: List[Dict[str, Any]], tolerance: float=DEFAULT_NODE_TOLERANCE, source_path: str='') -> ForgeDocument` — L209 — Costruisce un ForgeDocument da una lista di descrizioni geometriche pure —

#### `forge/adapters/pdf/__init__.py` — 0 lines

No module-level function or class.

#### `forge/adapters/pdf/extractor_adapter.py` — 86 lines

_adapters/pdf/extractor_adapter.py_

- `extract_drawings_from_page(page: Any) -> List[Dict[str, Any]]` — L23 — Estrae i disegni vettoriali dalla pagina PDF e normalizza l'output.

#### `forge/adapters/pdf/geometry_adapter.py` — 63 lines

_adapters/pdf/geometry_adapter.py_

- `transform_point(x: float, y: float, page_height: float) -> tuple[float, float]` — L27 — Converte un punto da punti PDF (pt) a millimetri (mm)
- `sample_bezier_cubic(p1: tuple, p2: tuple, p3: tuple, p4: tuple, num_segments: int=16) -> list[tuple[float, float]]` — L37 — Campiona una curva di Bezier cubica in un set di punti lineari (poligonale).

#### `forge/adapters/pdf/graph_adapter.py` — 56 lines

_adapters/pdf/graph_adapter.py_

- `map_sanitized_item_to_edge(item: tuple, decimals: int, page_idx: int) -> Edge \| None` — L13

#### `forge/adapters/pdf/loader.py` — 83 lines

_adapters/pdf/loader.py_

- `load_pdf(path: str, node_decimals: int=3, snap_tolerance: float=0.15) -> list` — L22 — Apre un documento PDF, estrae le geometrie vettoriali da tutte le pagine,

#### `forge/adapters/pdf/sanitize.py` — 103 lines

_adapters/pdf/sanitize.py_

- `sanitize_pdf_geometries(raw_items: list, page_height: float, snap_tolerance: float=0.15) -> list` — L13 — Prende gli item geometrici grezzi estratti dall'extractor, applica la conversione

### `forge/core/`

#### `forge/core/adapter_base.py` — 37 lines

_Contratto base per gli adapter di input di Forge._

- **class** `ForgeAdapter(ABC)` — L23
  - methods: `__init__`, `to_edges`, `source_context`

#### `forge/core/geometry/__init__.py` — 34 lines

_forge/core/geometry/__init__.py_

No module-level function or class.

#### `forge/core/geometry/axis.py` — 246 lines

_forge/core/geometry/axis.py_

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
- `axis_aligned_share(segments: Iterable, angle_tolerance: float) -> Optional[float]` — L231 — Frazione della lunghezza dei `LineSeg` di `segments` orizzontale o

#### `forge/core/geometry/intersections.py` — 130 lines

_forge/core/geometry/intersections.py_

- `_line_intersection(p1: Point, p2: Point, p3: Point, p4: Point) -> Optional[Point]` — L18 — Intersezione tra retta (p1,p2) e retta (p3,p4). None se parallele.
- `_distance(p1: Point, p2: Point) -> float` — L32
- `_circle_line_intersections(cx: float, cy: float, r: float, p1: Point, p2: Point) -> List[Point]` — L36 — Intersezioni tra la circonferenza (cx, cy, r) e la retta infinita (p1, p2).
- `_circle_circle_intersections(cx1: float, cy1: float, r1: float, cx2: float, cy2: float, r2: float) -> List[Point]` — L67 — Intersezioni tra due circonferenze. Restituisce 0, 1 o 2 punti.
- `_closest_to(candidates: List[Point], ref: Point) -> Optional[Point]` — L91 — Restituisce il punto più vicino a ref tra i candidati.
- `polyline_line_intersections(points: List[Point], closed: bool, p1: Point, p2: Point) -> List[Tuple[Point, int]]` — L98 — Intersezioni fra la retta infinita (p1, p2) e la spezzata `points` (ogni

#### `forge/core/geometry/lines.py` — 140 lines

_forge/core/geometry/lines.py_

- `_ends(item) -> Tuple[Point, Point]` — L27 — I due capi di un tratto: `LineString` (primo e ultimo punto) o `(start, end)`.
- `point_line_distance(point: Point, a: Point, b: Point) -> float` — L36 — Distanza di `point` dalla retta infinita per `a`, `b`; da `a` se i due coincidono.
- `are_collinear(a, b, tolerance: float=COLLINEAR_TOLERANCE, angle_tolerance: float=COLLINEAR_ANGLE_TOLERANCE) -> bool` — L45 — I tratti `a` e `b` stanno sulla stessa retta infinita: direzioni uguali
- `group_collinear_lines(lines: list, tolerance: float=COLLINEAR_TOLERANCE, angle_tolerance: float=COLLINEAR_ANGLE_TOLERANCE) -> list` — L61 — Tratti raggruppati per retta: [[L1, L2], [L3], ...]. Ogni gruppo prende la
- `splits_polygon(polygon, start: Point, end: Point, reach: float=0.0) -> bool` — L82 — La corda `start`-`end`, prolungata di `reach` ai due capi, divide `polygon` in due o più parti.
- **class** `CollinearRun` — L94 — Tratti sulla stessa retta, in fila lungo di essa.
- `bridged_runs(segments: Sequence, bridges: Sequence, tolerance: float=COLLINEAR_TOLERANCE, angle_tolerance: float=COLLINEAR_ANGLE_TOLERANCE) -> list[CollinearRun]` — L106 — File di due o più tratti sulla stessa retta in cui lo spazio fra un tratto

#### `forge/core/geometry/measure.py` — 172 lines

_forge/core/geometry/measure.py_

- `round_point(pt, decimals: int=1) -> Tuple` — L20
- `node_decimals_for(tolerance: float) -> int` — L24 — Numero di decimali a cui arrotondare gli endpoint per la topologia.
- `num_segments_for_bulge(bulge: float) -> int` — L38 — Numero di segmenti per discretizzare un arco dato il suo bulge.
- `track_points(segments, tolerance: Optional[float]=None) -> List[Point]` — L53 — Vertici di una traccia aperta come catena di segmenti nativi.
- `track_length(pts) -> float` — L72 — Lunghezza totale di una polilinea (somma delle corde).
- `track_shape_type(pts) -> str` — L80 — `"line"` se la traccia è un solo segmento retto (2 vertici), altrimenti `"curve"`.
- `segment_length(segment) -> float` — L91 — Lunghezza reale di una primitiva nativa singola (`LineSeg`/`ArcSeg`/
- `longest_segment(segments) -> Tuple[Optional[object], float]` — L108 — `(segment, length)` del segmento più lungo in `segments` — `(None, 0.0)`
- `chord_angle_deg(a: Point, b: Point) -> float` — L121 — Angolo (gradi, 0-180°) della corda da `a` a `b`. Modulo 180 perché una
- `circular_geometry(polygon, segments=None)` — L143 — (diameter, center) se il contorno è ~circolare, altrimenti (None, None).

#### `forge/core/geometry/points.py` — 201 lines

_forge/core/geometry/points.py_

- `interior_angle_deg(prev_pt: Point, curr_pt: Point, next_pt: Point) -> float` — L31 — Angolo interno (gradi) in curr_pt fra i lati verso prev_pt e next_pt.
- `detect_corners(points: List[Point], angle_threshold_deg: float=DEFAULT_ANGLE_THRESHOLD_DEG, closed: bool=True) -> List[bool]` — L43 — Per ogni punto, True se l'angolo formato dai due lati adiacenti è sotto
- `drop_duplicate_points(points: List[Point], tolerance: float=DEFAULT_DUPLICATE_TOLERANCE) -> List[Point]` — L75 — Rimuove punti consecutivi coincidenti entro `tolerance`.
- `fit_circle_kasa(points: List[Point]) -> Optional[Tuple[Point, float, float]]` — L89 — Fit algebrico (Kasa) ai minimi quadrati di un cerchio su `points`: minimizza
- `arc_angles(points: List[Point], center: Point) -> Tuple[float, float, bool]` — L121 — `(start_angle, end_angle, ccw)` in radianti di un arco che passa per
- `interpolate_bspline(points: List[Point], degree: int=3) -> Tuple[List[Point], List[float]]` — L145 — B-spline di grado `degree` che passa per tutti i `points` (interpolazione
- `_bspline_basis_row(u: float, p: int, knots: List[float], n: int) -> List[float]` — L179 — Le n+1 funzioni di base N_i,p(u) (Cox-de Boor, Piegl & Tiller A2.2).

#### `forge/core/geometry/shape.py` — 298 lines

_forge/core/geometry/shape.py_

- **class** `ContourShape` — L36 — kind:   circle \| stadium \| rectangle \| polygon \| other
  - methods: `diameter`, `to_dict`
- `contour_shape(item, tolerance: float=SHAPE_TOLERANCE, angle_tolerance: float=ANGLE_TOLERANCE_DEG) -> Optional[ContourShape]` — L63 — Forma di un contorno chiuso (`ForgeContour`, o qualunque oggetto con
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

#### `forge/core/heal.py` — 186 lines

_core/heal.py_

- `heal(doc: ForgeDocument, tolerance: Optional[float]=None, label: str='', source_file: str='', is_structural: Optional[Callable[[str], bool]]=None) -> ForgeResult` — L38 — Legge `doc` dall'interno: un ForgeCluster per contorno esterno chiuso,
- `_search_warnings(search: LoopSearch, tolerance: float) -> list[str]` — L167 — Cosa racconta heal() dei gradini della scala di find_loops().

#### `forge/core/healing/__init__.py` — 0 lines

No module-level function or class.

#### `forge/core/healing/gap_solver.py` — 371 lines

_core/healing/gap_solver.py_

- **class** `GapEndpoint` — L46 — Endpoint libero nel grafo topologico.
- **class** `MoveEndpoint` — L73 — Istruzione: sposta l'endpoint role di ref al punto new_pt.
- **class** `AddSegment` — L84 — Istruzione: aggiungi un segmento retto tra pt_a e pt_b.
- `_solve_line_line(ep_a: GapEndpoint, ep_b: GapEndpoint) -> List[GapFix]` — L100
- `_solve_arc_line(ep_arc: GapEndpoint, ep_line: GapEndpoint) -> List[GapFix]` — L112
- `_solve_arc_arc(ep_a: GapEndpoint, ep_b: GapEndpoint) -> List[GapFix]` — L126
- `_solve_spline_any(ep_a: GapEndpoint, ep_b: GapEndpoint) -> List[GapFix]` — L138
- `_get_solver(kind_a: str, kind_b: str)` — L162
- `compute_gap_fixes(endpoints: List[GapEndpoint], tolerance: float) -> List[GapFix]` — L174 — Calcola i GapFix per tutti gli endpoint liberi entro tolerance.
- `local_gap_fixes(fixes: List[GapFix], max_move: float) -> List[GapFix]` — L215 — Solo i fix che non spostano un estremo più di `max_move`: due rette quasi
- `_endpoint_meta(segment) -> dict` — L239 — Dati che il solver usa per calcolare l'intersezione, per tipo di segmento.
- `_meet_or_bridge(ix: Optional[Point2D], ep_a: GapEndpoint, ep_b: GapEndpoint) -> List[GapFix]` — L248 — Se le due geometrie si incontrano in `ix`, porta lì entrambi gli estremi;
- `free_endpoints_from_edges(edges: List[Edge], graph) -> List[GapEndpoint]` — L259 — Estrae gli endpoint liberi (grado < 2 nel grafo) dagli Edge.
- `gap_endpoints_at_nodes(edges: List[Edge], nodes: set) -> List[GapEndpoint]` — L271 — GapEndpoint per gli endpoint che cadono su uno dei `nodes` — tuple di
- `_gap_endpoints(edges: List[Edge], keep: Callable[[Point2D], bool]) -> List[GapEndpoint]` — L288 — GapEndpoint per gli estremi di LINE / ARC / SPLINE il cui nodo (arrotondato)
- `_moved_segment(segment, role: str, new_pt: Point2D)` — L308 — Nuovo segmento con l'endpoint `role` spostato su `new_pt`. None se non gestito.
- `apply_gap_fixes(edges: List[Edge], fixes: List[GapFix], node_decimals: int=1) -> List[Edge]` — L326 — Applica i GapFix restituendo una NUOVA lista di Edge — `edges` non viene mutata.

#### `forge/core/healing/hierarchy.py` — 210 lines

- `loop_to_closed_feature(loop, role: ContourRole=ContourRole.UNKNOWN, polygon=None, segments: list=None, styles: list=None) -> Optional[ClosedFeature]` — L21
- `_place(proxy: ClosedFeature, nodes: list) -> bool` — L69
- `_build_tree(proxies: list) -> list` — L78
- `_make_inner(proxy: ClosedFeature, parent_role: ContourRole=ContourRole.UNKNOWN, depth: int=1, parent: Optional[ForgeContour]=None) -> ForgeContour` — L91
- `_collect_inners(children: list, inners: list, classified_proxies: set, parent_role: ContourRole=ContourRole.UNKNOWN, depth: int=1, parent: Optional[ForgeContour]=None)` — L112 — Appiattisce l'albero di contenimento in `cluster.inners` (ogni discendente
- **class** `HierarchyBuilder` — L149
  - methods: `__init__`, `build`, `_build_parts`, `_collect_trash`

#### `forge/core/healing/islands.py` — 95 lines

_core/healing/islands.py_

- **class** `Island` — L36 — Gruppo di Edge vicini, con la bbox che li contiene tutti.
  - methods: `width`, `height`
- `spatial_islands(edges: Iterable[Edge], gap_tolerance: float) -> List[Island]` — L54 — Union-find sulle coppie di Edge a distanza <= gap_tolerance (STRtree,

#### `forge/core/healing/normalizer.py` — 535 lines

_core/healing/normalizer.py_

- `find_duplicates(keyed_entities: Iterable[Tuple[Hashable, Any]]) -> List[Any]` — L57 — Restituisce i ref delle entità duplicate (seconda occorrenza in poi).
- `_line_key(p1, p2) -> Tuple[float, float]` — L93 — Chiave della retta infinita per p1->p2: (angolo canonico, offset).
- `merge_collinear_overlaps(edges: Iterable[Edge]) -> List[Edge]` — L120 — Fonde gruppi di LineSeg collineari (stessa retta infinita, `_line_key`)
- `_line_spans(group: List[Edge]) -> List[_Span]` — L208 — Span lungo la retta comune: `t` è la proiezione sulla direzione del
- `_merged_line(lo: _Span, hi: _Span)` — L232 — Il fuso di una catena collineare: nodi arrotondati, segmento a piena
- **class** `_Span` — L243 — Un edge come intervallo [lo, hi] sul suo supporto (posizione lungo la
- `_chain(spans: List[_Span]) -> List[List[_Span]]` — L259 — Ordina per `lo` e incatena gli span che si toccano o si sovrappongono:
- `_merge_on_carrier(edges: Iterable[Edge], segment_type: type, key: Callable[[Any], Hashable], chains_of: Callable[[List[Edge]], List[List[_Span]]], merged: Callable[[_Span, _Span], Tuple[Point, Point, Any]]) -> List[Edge]` — L279 — Raggruppa per supporto (`key`) gli edge di `segment_type` con ruolo
- `_arc_key(center, radius) -> Tuple[float, float, float]` — L330 — Chiave del cerchio (centro+raggio) a precisione fissa — v. `_line_key`.
- `merge_cocircular_overlaps(edges: Iterable[Edge]) -> List[Edge]` — L339 — `merge_collinear_overlaps` per gli ArcSeg: fonde gruppi co-circolari
- `_arc_chains(group: List[Edge]) -> List[List[_Span]]` — L357 — Catene angolari di un gruppo sullo stesso cerchio. Se l'ultima catena
- `_merged_arc(lo: _Span, hi: _Span)` — L383 — Il fuso di una catena cocircolare: un arco, o un cerchio se chiude il
- `weld_degenerate_linesegs(edges: Iterable[Edge]) -> List[Edge]` — L403 — Salda (non cancella) i LineSeg `role == UNKNOWN` di lunghezza reale
- `refit_tessellations(edges: Iterable[Edge], max_segment: float=0.1, min_run: int=10, arc_fit_tolerance: float=0.02, node_decimals: int=3) -> List[Edge]` — L455 — Una catena di almeno `min_run` LineSeg (`role == UNKNOWN`) più corti di
- `_short_runs(short_edges: List[Edge]) -> list` — L507 — Catene massimali: percorsi fra nodi di grado != 2, o anelli.

#### `forge/core/healing/outer_scan.py` — 217 lines

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

#### `forge/core/healing/steps.py` — 275 lines

_core/healing/steps.py_

- **class** `LoopSearch` — L37 — Come find_loops() ha chiuso (o non chiuso) i giri, gradino per gradino.
- `split_labeled(edges: List[Edge], is_structural: Optional[Callable[[str], bool]]=None) -> Tuple[List[Edge], List[Edge]]` — L52 — Separa gli Edge con un ruolo già deciso e non strutturale (cornice,
- `close_free_gaps(edges: List[Edge], tolerance: float) -> List[Edge]` — L69 — Chiude i gap fra estremi liberi entro `tolerance` col gap solver
- `dangling_splines(edges: List[Edge]) -> List[Edge]` — L84 — SplineSeg aperte con almeno un estremo non collegato a nient'altro.
- `find_non_contour_edges(edges: List[Edge], tolerance: float) -> Set[int]` — L93 — id(edge) degli Edge che non chiudono un contorno (branching + centroide
- `repair_merged_corners(edges: List[Edge], tolerance: float, exclude_ids: FrozenSet[int]=frozenset()) -> Tuple[List[Edge], int, list]` — L102 — Chiude gli angoli che il grafo esatto vede aperti e il clustering degli
- `find_loops(edges: List[Edge], non_contour_ids: Set[int], tolerance: float) -> LoopSearch` — L128 — La scala di heal() per chiudere i giri, esclusi `non_contour_ids`:
- `structural_loops(loops: List[list], is_structural: Optional[Callable[[str], bool]]=None) -> List[list]` — L164 — I loop in cui ogni edge con ruolo deciso è strutturale: un solo edge non
- `loops_to_features(loops: List[list]) -> List[ClosedFeature]` — L175 — Un ClosedFeature per loop, col ruolo del primo edge; senza poligono valido, niente.
- `polygonize_edges(edges: List[Edge], tolerance: float) -> List[Polygon]` — L191 — Ultima spiaggia quando nessun grafo chiude: le facce dell'intero disegno
- `polygons_to_features(polygons: List[Polygon]) -> List[ClosedFeature]` — L207 — Per poligono un ClosedFeature OUTER dal bordo esterno e uno INNER per
- `labeled_features(edges: List[Edge]) -> list` — L228 — Gli Edge messi da parte da split_labeled() come feature col loro ruolo
- `build_hierarchy(features: list, label: str='', source_file: str='', is_structural: Optional[Callable[[str], bool]]=None) -> Tuple[List[ForgeCluster], list]` — L250 — Albero di contenimento sui ClosedFeature: ogni radice è un ForgeCluster
- `_graph(edges: List[Edge], exclude_ids: FrozenSet[int], epsilon: float=0.0)` — L267
- `_ring_segments(coords) -> List[LineSeg]` — L273

#### `forge/core/island.py` — 237 lines

_core/island.py_

- **class** `IslandReading` — L52 — Cosa island() ha deciso su un'isola, pezzo per pezzo.
- `island(doc: ForgeDocument, tolerance: Optional[float]=None, island_gap: float=10.0, max_gap: float=0.5, is_structural: Optional[Callable[[str], bool]]=None) -> ForgeResult` — L69 — Legge `doc` per isole. Un ForgeCluster per isola: `outer` il contorno
- `read_islands(edges: List[Edge], tolerance: float, island_gap: float=10.0, max_gap: float=0.5) -> List[IslandReading]` — L131 — `spatial_islands` + `read_island` per ognuna, e l'annidamento: un'isola
- `read_island(edges: List[Edge], tolerance: float, max_gap: float=0.5) -> IslandReading` — L153 — Un'isola: normalizza (nodi dagli estremi reali, tassellature rifittate,
- `_normalize(edges: List[Edge], tolerance: float, max_gap: float) -> List[Edge]` — L195 — Stessi passi di heal, ma sulla griglia fine della rete piana: prima i
- `_cluster(reading: IslandReading, source_file: str) -> ForgeCluster` — L209
- `_inners(loops, parent: ForgeContour) -> List[ForgeContour]` — L217 — Un ForgeContour inner per giro chiuso; un giro senza poligono valido no.
- `_contour(segments, styles, polygon, role, parent) -> ForgeContour` — L227 — Il poligono resta quello dei pezzi della rete piana; i segmenti sono
- `_open(edges: List[Edge]) -> list` — L235

#### `forge/core/primitives/__init__.py` — 11 lines

No module-level function or class.

#### `forge/core/primitives/fitting.py` — 221 lines

_forge/core/primitives/fitting.py_

- `_split_into_stretches(points: List[Point], is_corner: List[bool], closed: bool) -> List[List[Point]]` — L48 — Spezza `points` in tratti fra due spigoli consecutivi (estremi inclusi).
- `_try_fit_arc(points: List[Point], arc_fit_tolerance: float, duplicate_tolerance: float) -> Optional[Union[ArcSeg, CircleSeg]]` — L85 — Prova un fit a cerchio su `points`; lo accetta solo se lo scostamento
- `_fit_spline(points: List[Point], degree: int, closed: bool=False) -> SplineSeg` — L111 — Un solo SplineSeg passante per `points` (curva di fit globale, non ai
- `fit_primitives(points: List[Point], is_corner: List[bool], closed: bool=True, min_points_for_spline: int=DEFAULT_MIN_POINTS_FOR_SPLINE, spline_degree: int=DEFAULT_SPLINE_DEGREE, duplicate_tolerance: float=DEFAULT_DUPLICATE_TOLERANCE, arc_fit_tolerance: Optional[float]=DEFAULT_ARC_FIT_TOLERANCE) -> List[Union[LineSeg, ArcSeg, CircleSeg, SplineSeg]]` — L132 — Spezza `points` sui corner marcati in `is_corner` e rifitta ogni tratto: un
- `simplify_points(points: List[Point], closed: bool=True, angle_threshold_deg: float=DEFAULT_ANGLE_THRESHOLD_DEG, min_points_for_spline: int=DEFAULT_MIN_POINTS_FOR_SPLINE, spline_degree: int=DEFAULT_SPLINE_DEGREE, duplicate_tolerance: float=DEFAULT_DUPLICATE_TOLERANCE, arc_fit_tolerance: Optional[float]=DEFAULT_ARC_FIT_TOLERANCE) -> List[Union[LineSeg, ArcSeg, CircleSeg, SplineSeg]]` — L198 — `detect_corners` + `fit_primitives` in un solo passo — comodo quando serve

#### `forge/core/primitives/polygon_builder.py` — 60 lines

_core/primitives/polygon_builder.py_

- `build_polygon(primitives: List[LineSeg \| ArcSeg \| SplineSeg \| CircleSeg \| EllipseSeg], tolerance: float=0.01) -> Optional[Polygon]` — L19 — Costruisce un Polygon shapely da una lista di primitive geometriche.
- `_make_polygon(pts: list) -> Optional[Polygon]` — L48

#### `forge/core/primitives/segments.py` — 704 lines

_forge/core/primitives/segments.py_

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

#### `forge/core/topology/edge.py` — 57 lines

_core/topology/edge.py_

- **class** `Edge` — L28 — Layer intermedio tra l'entità sorgente grezza (di qualsiasi formato) e il

#### `forge/core/topology/graph.py` — 357 lines

_graph.py_

- **class** `Graph` — L59 — Grafo topologico interrogabile.
  - methods: `canonical`, `degree`, `branching_nodes`, `merged_clusters`, `connected_components`, `open_nodes`, `pruned`, `items`, `get`
- `cluster_points(points: list, epsilon: float) -> Dict[Tuple, Tuple]` — L191 — Raggruppa punti 2D entro `epsilon` e restituisce {punto -> rappresentante}.
- `_close_self_loop(edge: Edge, epsilon: float)` — L254 — ArcSeg il cui sviluppo (raggio*sweep) supera epsilon -> CircleSeg (loop degenere vero). Altrimenti `None` (sl…
- `build_node_graph(edges: list, epsilon: float=0.0) -> Graph` — L270 — Costruisce il Graph da list[Edge].
- `_edge_coords(edge: Edge, reversed_flag: bool) -> list` — L324
- `_first_coord(edge: Edge)` — L331
- `_arrival_direction(edge: Edge, rev: bool)` — L338
- `_angular_deviation(arrival_dir, edge: Edge, rev: bool)` — L347

#### `forge/core/topology/loop_finder.py` — 253 lines

_loop_finder.py_

- **class** `LoopFinder` — L28
  - methods: `find`, `_loop_to_points`, `_deduplicate_loops`
- `segments_from_loop(loop) -> list` — L161 — Segmenti nativi di un loop, orientati nel verso di percorrenza.
- `edge_styles_from_loop(loop) -> list` — L187 — Stili grezzi (linetype/colore) di un loop, allineati 1:1 con
- `loop_geometry(loop) -> Optional[Tuple[list, list, Polygon]]` — L206 — (segmenti, stili, poligono) di un loop; None se i segmenti non chiudono
- `edges_to_open_features(edges: list, exclude_ids: set) -> list` — L220 — Converte gli Edge non assorbiti da un loop strutturale in OpenFeature.

#### `forge/core/topology/noding.py` — 251 lines

_core/topology/noding.py_

- **class** `NodedEdges` — L39 — La rete piana: i pezzi, e per ognuno l'Edge da cui viene.
  - methods: `parent_of`
- `renode(edges: List[Edge], decimals: int=NODE_DECIMALS) -> List[Edge]` — L52 — Nodi di ogni Edge ricalcolati dal punto reale del segmento a
- `split_at_crossings(edges: List[Edge], tolerance: float, decimals: int=NODE_DECIMALS) -> NodedEdges` — L60 — Spezza ogni LineSeg/ArcSeg/CircleSeg nei punti dove incrocia un altro
- `_arc_s(seg, pt)` — L90
- `_param(seg, pt)` — L94 — (parametro, distanza del punto dal segmento).
- `_param_range(seg)` — L110
- `_piece_length(seg, p0, p1)` — L114
- `_circle_as_arc(circle, start_angle=0.0)` — L120 — Un cerchio come arco di 360° da `start_angle`: stessa matematica degli archi.
- `_cutters(edge)` — L130
- `_crossings(seg, cutter)` — L142 — Incroci reali (non sul prolungamento) fra `seg` e un cutter.
- `_split_params(edge, near, tol)` — L167
- `_with_nodes(edge, seg, decimals)` — L194
- `_split(edge, params, decimals)` — L200
- `_split_circle(edge, near, tol, decimals)` — L225
- `edge_geometry(edge: Edge)` — L246 — L'edge come geometria shapely: LineString discretizzata, Point se degenere.

#### `forge/core/topology/non_contour_edges.py` — 80 lines

_non_contour_edges.py_

- **class** `NonContourEdgeDetector` — L41
  - methods: `__init__`, `detect`

#### `forge/core/topology/outer_face.py` — 163 lines

_core/topology/outer_face.py_

- **class** `OuterFace` — L35 — Il contorno esterno trovato, e cosa il percorso ha scartato.
  - methods: `edges`
- `outer_face(edges: List[Edge], epsilon: float=0.0) -> Optional[OuterFace]` — L52 — Contorno esterno della rete `edges` (già piana: split_at_crossings). I
- `_outer_face_walk(graph: Graph, component, n_edges: int) -> list` — L82 — [(edge, dal nodo, al nodo)] lungo il bordo della faccia esterna.
- `_first_step(graph: Graph, component)` — L112 — L'edge che contiene il punto più a sinistra del componente, percorso
- `_leaving_angle(edge: Edge, node, graph: Graph) -> float` — L134 — Direzione con cui `edge` lascia `node`, letta a DIRECTION_SAMPLE (o a
- `_largest_loop(edges: List[Edge], epsilon: float)` — L155 — (loop, segments, styles, polygon) del giro di area massima.

### `forge/` (root)

#### `forge/inspect.py` — 337 lines

_forge/inspect.py_

- `_h(title: str) -> None` — L42
- `_p(x, nd: int=2) -> str` — L46 — Formatta un punto (x, y) con nd decimali.
- `_role(r) -> str` — L53 — Nome del ruolo come stringa piatta ('outer'), non 'ContourRole.OUTER'.
- `inspect_dxf(path: str, entities: bool=True, limit: Optional[int]=40) -> None` — L62 — Apre un DXF/DWG con ezdxf e stampa cosa contiene, senza toccare forge.
- `_describe_dxf_entity(e) -> str` — L104
- `inspect_document(doc, graph: bool=True, limit: Optional[int]=60) -> None` — L141 — Stampa un ForgeDocument prodotto da forge.load_dxf(): cosa ha estratto e
- `_describe_segment(seg) -> str` — L200
- `inspect_result(result, coords: bool=False) -> None` — L229 — Stampa un ForgeResult dopo heal(): il prodotto vero di forge.
- `_sub_part(i: int, cluster, coords: bool) -> None` — L277
- `inspect_file(path: str, tolerance: float=DEFAULT_NODE_TOLERANCE, role_rules: Sequence[RoleRule]=(), run_heal: bool=True, entities: bool=True, coords: bool=False) -> None` — L307 — Apre un file e stampa i tre livelli in fila:

### `forge/io/`

#### `forge/io/dxf.py` — 494 lines

_forge/io/dxf.py_

- `to_dxf(result: ForgeResult, source_doc: Optional[ForgeDocument]=None, filter_cluster: Optional[Callable[[ForgeCluster], bool]]=None, include_annotations: bool=True, include_trash: bool=True, annotation_layer: Optional[str]=LAYER_ANNOTATION, role_styles: Optional[Dict[str, RoleStyle]]=None, allow_invalid: bool=True) -> 'ezdxf.document.Drawing'` — L48 — Crea un documento DXF nuovo (R2010) e vi materializza il ForgeResult.
- `cluster_passes_min_area(cluster: ForgeCluster, min_area: float) -> bool` — L157 — True se la parte supera la soglia di area minima (min_area <= 0 = nessun filtro).
- `split(result: ForgeResult, source_doc: Optional[ForgeDocument]=None, namer: Optional[Callable]=None, include_annotations: bool=True, min_area: float=DEFAULT_MIN_CLUSTER_AREA, exclude_types: Set[str]=None, on_part: Optional[Callable]=None, annotation_layer: Optional[str]=LAYER_ANNOTATION, role_styles: Optional[Dict[str, RoleStyle]]=None) -> List['ezdxf.document.Drawing']` — L162 — Materializza un ForgeResult in un Drawing per parte.
- `_write_annotations(msp, annotations: List[Annotation], written_clusters: List[ForgeCluster], all_clusters: List[ForgeCluster], annotation_layer: Optional[str], restrict_to_written: bool) -> None` — L230 — Riscrive le annotazioni testuali della sorgente nel documento di output.
- `_emit_annotation(msp, ann: Annotation, annotation_layer: Optional[str]) -> None` — L268
- `_emit_note(msp, note: Note, attribs: dict) -> None` — L278
- `_emit_rendered(msp, ann, attribs: dict) -> None` — L304 — DIMENSION / LEADER: ri-materializza l'immagine appiattita. I testi in
- `_trash_probe_point(trash) -> Optional[tuple]` — L333 — Punto rappresentativo di un'entità trash, per assegnarla a una parte.
- `_write_trash(msp, result: ForgeResult, written_clusters: List[ForgeCluster], all_clusters: List[ForgeCluster], restrict_to_written: bool) -> None` — L349 — Materializza `result.trash_entities`.
- `_write_attached_features(msp, cluster: ForgeCluster) -> None` — L399 — Ogni collezione di `cluster.detected` (D70, D90): forge non sa cosa siano.
- `_remove_excluded_entities(msp, excluded_upper: Set[str]) -> None` — L430
- `_setup_layers(doc) -> None` — L436
- `_ensure_layer(doc, name: str) -> None` — L445 — Crea il layer `name` col suo colore canonico se non esiste già. Serve per i
- `_outer_polygons(clusters) -> list` — L454 — (cluster, poligono dell'outer) per ogni cluster che ne ha uno.
- `_apply_role_styles(doc, role_styles: Optional[Dict[str, 'RoleStyle']]) -> None` — L463 — Applica gli override di `role_styles` (D37) ai layer DXF: crea il layer

#### `forge/io/exporter.py` — 332 lines

_exporter.py_

- `build_metadata(cluster: ForgeCluster, schema: dict=None, extra: dict=None) -> dict` — L23 — Costruisce il dict dei metadati per un ForgeCluster
- `set_schema(schema: dict)` — L100 — Imposta uno schema esterno come schema attivo.
- `save_json(result: ForgeResult, path: str, indent: int=2, extra_metadata: Optional[Callable[[ForgeCluster], dict]]=None)` — L117 — Salva i metadati in JSON secondo lo schema di metadata_schema.py.
- `to_json(result: ForgeResult, indent: int=2, extra_metadata: Optional[Callable[[ForgeCluster], dict]]=None) -> str` — L147 — Restituisce i metadati come stringa JSON secondo schema. Vedi `save_json` per `extra_metadata`.
- `save_xml(result: ForgeResult, path: str, extra_metadata: Optional[Callable[[ForgeCluster], dict]]=None)` — L170 — Salva i metadati in XML secondo lo schema di metadata_schema.py.
- `_dict_to_xml(d: dict, parent: ET.Element)` — L230 — Converte ricorsivamente un dict in sotto-elementi XML.
- `to_nester_input(result: ForgeResult) -> list` — L244 — Produce l'input per il nester: coordinate grezze + metadati base.
- `_outer_entity(doc)` — L266 — L'entità su layer OuterContour che porta gli XDATA: prima una polilinea,
- `write_metadata_to_dxf(doc, cluster: ForgeCluster, extra: Optional[dict]=None)` — L278 — Scrive i metadati come XDATA sull'entità OuterContour.
- `read_metadata_from_dxf(doc) -> dict` — L307 — Legge i metadati FORGE XDATA dall'entità OuterContour.

#### `forge/io/svg.py` — 195 lines

_io/svg.py_

- `_fmt(pts) -> str` — L23 — Lista di [x, y] → stringa 'x0,y0 x1,y1 …' per points= di polyline/polygon.
- `_shape(entry: dict, stroke_w: float, true_circles: bool) -> str` — L28
- `to_svg(result: ForgeResult, tolerance: float=0.05, include_trash: bool=True, include_annotations: bool=True, padding: float=0.03, background: Optional[str]='#1e1e1e', true_circles: bool=True, stroke_width: Optional[float]=None, size: Optional[str]=None, units: Optional[str]=None, allow_invalid: bool=True) -> str` — L45 — `ForgeResult` → stringa SVG completa (`<svg>…</svg>`).
- `save_svg(result: ForgeResult, path: str, **kwargs) -> None` — L168 — Scrive `to_svg(result, **kwargs)` su file.
- `_scan_bbox(vm: dict) -> Optional[list]` — L175 — bbox da tutti i punti del view model — fallback quando vm['bbox'] è None.

#### `forge/io/text.py` — 269 lines

_io/text.py_

- **class** `_Writer` — L43 — Numeri arrotondati e id dei contorni per una sola chiamata di `to_text`.
  - methods: `__init__`, `num`, `pt`, `deg`, `label`, `segment`, `spline`, `contour`, `detected_item`
- `_first_point(s) -> Optional[tuple]` — L153 — Un punto che sta sul segmento, per dire in quale pezzo cade.
- `_uniform_knots(knots, degree: int) -> bool` — L161 — Nodi bloccati agli estremi e passo interno costante: non serve scriverli.
- `to_text(result: ForgeResult, source_name: str='', decimals: int=3, spline_data: bool=False) -> str` — L172 — Il `ForgeResult` come testo per un modello linguistico (`.forge.md`).
- `save_text(result: ForgeResult, path: str \| Path, source_name: str='', decimals: int=3, spline_data: bool=False) -> None` — L266 — Scrive `to_text(result)` su `path` (per convenzione `<nome>.forge.md`).

#### `forge/io/view_model.py` — 191 lines

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
- `to_view_model(result: ForgeResult, tolerance: float=0.05, include_trash: bool=True, include_annotations: bool=True) -> dict` — L128 — `ForgeResult` → dizionario JSON-ready con la geometria di ogni feature.
- `_palette_dict() -> dict` — L180 — role (stringa) → colore hex, per la legenda di un renderer.

### `forge/model/`

#### `forge/model/__init__.py` — 37 lines

- `__getattr__(name)` — L33

#### `forge/model/annotation.py` — 156 lines

_forge/model/annotation.py_

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

#### `forge/model/cluster.py` — 119 lines

_model/cluster.py_

- **class** `ForgeCluster` — L15
  - methods: `features`, `overlay_voids`, `polygon_with_holes`, `bbox`, `area`, `summary`, `to_dict`

#### `forge/model/contour.py` — 38 lines

_model/contour.py_

- **class** `ForgeContour(ClosedFeature)` — L29
  - methods: `to_dict`

#### `forge/model/detected.py` — 74 lines

_forge/model/detected.py_

- **class** `DetectedFeature(Protocol)` — L23 — Contratto minimo di un elemento attaccato a `DetectedFeatures`: la
- **class** `DetectedFeatures` — L34 — Contenitore aperto per nome: ogni consumatore scrive sotto il nome che
  - methods: `attach`, `add`, `get`, `items`, `names`

#### `forge/model/document.py` — 54 lines

_model/document.py_

- **class** `ForgeDocument` — L37 — Documento di dominio prodotto da load_dxf() / load_svg() / load_pdf().
  - methods: `node_tolerance`

#### `forge/model/feature.py` — 77 lines

_model/feature.py_

- **class** `Feature` — L37 — Radice della gerarchia. Porta solo identità semantica e traceability.
- **class** `ClosedFeature(Feature)` — L47 — Feature con geometria chiusa: ha un polygon e una lista di segmenti.
  - methods: `area`, `bbox`
- **class** `OpenFeature(Feature)` — L72 — Feature con geometria aperta: ha segmenti ma non un polygon.

#### `forge/model/result.py` — 53 lines

- **class** `ForgeResult` — L11 — Risultato completo di una sessione forge su un file DXF.
  - methods: `cluster_count`, `has_issues`, `to_dict`

#### `forge/model/role.py` — 149 lines

_model/role.py_

- **class** `ContourRole(str, Enum)` — L43 — I tre ruoli che il motore topologico conosce. **Non esaustivo** — un
- `is_structural_role(role) -> bool` — L78 — True se ``role`` è OUTER o INNER per il motore (vedi ``STRUCTURAL_ROLES``).
- `feature_role(contour, item_role)` — L90 — Il ruolo con cui si disegna un contorno di un elemento dell'overlay (D90):
- `normalize_role(value) -> str` — L112 — Ripulisce una stringa-ruolo che arriva dal chiamante (``RoleRule``,
- `role_str(role) -> str` — L142 — Valore stringa di un ruolo, che sia una costante ``ContourRole`` o una

#### `forge/model/role_rule.py` — 114 lines

_model/role_rule.py_

- **class** `RoleRule` — L35 — Una regola: se TUTTE le condizioni date sono vere, la linea prende `role`.
  - methods: `matches`
- `resolve_role(rules: Sequence[RoleRule], name: str, style: EdgeStyle) -> str` — L88 — Ruolo della prima regola che matcha, in ordine; `unknown` se nessuna.
- `name_rules(mapping: Dict[str, str]) -> List[RoleRule]` — L96 — Scorciatoia: {nome: ruolo} → una RoleRule(name=...) per voce.
- `_color_index(value: Union[int, str]) -> int` — L105 — Intero ACI da intero, stringa numerica ("4") o nome standard ("cyan").

#### `forge/model/style.py` — 62 lines

_model/style.py_

- **class** `EdgeStyle` — L38
  - methods: `is_dashed`, `dash_kind`

### `forge/` (root)

#### `forge/recipes.py` — 52 lines

_forge/recipes.py_

- `split_to_files(doc: ForgeDocument, output_folder, label='', source_file='', tolerance=None, namer=None, include_annotations=True, min_area=DEFAULT_MIN_CLUSTER_AREA, exclude_types=None, annotation_layer=LAYER_ANNOTATION, is_structural=None) -> ForgeResult` — L23 — Pipeline multi-pezzo + salvataggio su disco: heal → split → `.saveas()` per

### `forge/rules/`

#### `forge/rules/metadata_schema.py` — 38 lines

_metadata_schema.py_

No module-level function or class.

#### `forge/rules/palette.py` — 170 lines

_rules/palette.py_

- `role_to_color(role) -> int` — L74 — Colore ACI di un ruolo. Ruolo noto → il suo colore semantico;
- `role_to_hex(role, fallback: str='#ff0000') -> str` — L88 — Colore hex CSS di un ruolo. Un colore registrato (`register_role_style`)
- **class** `RoleStyle` — L107 — Override, indipendente dal formato, dell'aspetto visivo di un ruolo in
- `register_role_style(role, style: RoleStyle) -> None` — L157 — Registra uno `RoleStyle` per `role`, valido per ogni render successivo
- `registered_role_styles() -> dict` — L168 — Copia del registro attivo — letta dai renderer, mai mutata da loro.

#### `forge/rules/validator.py` — 167 lines

_rules/validator.py_

- `validate(doc: ForgeDocument) -> ForgeResult` — L29 — Valida l'input prima di heal().
- `validate_result(result: ForgeResult) -> ForgeResult` — L128 — Valida i ForgeCluster dentro un ForgeResult già popolato da heal().

### `forge/tools/`

#### `forge/tools/__init__.py` — 18 lines

_forge/tools/_

No module-level function or class.

#### `forge/tools/anchor.py` — 192 lines

_forge/tools/anchor.py_

- `anchor_annotations(result: ForgeResult, snap_distance: float=0.0, leader_distance: float=LEADER_TARGET_DISTANCE) -> ForgeResult` — L34 — Assegna ``cluster_ref`` a ogni annotazione di ``result.annotations``.
- `leader_target(result: ForgeResult, leader: Leader, distance: float=LEADER_TARGET_DISTANCE) -> Optional[str]` — L73 — L'elemento indicato dalla punta (``vertices[0]``) di ``leader``, come
- `dimension_references(result: ForgeResult, dimension: Dimension, distance: float=LEADER_TARGET_DISTANCE) -> list` — L101 — Gli elementi fra cui ``dimension`` misura, come percorsi in ``result``
- `_on_boundary(elements, point, distance: float) -> Optional[str]` — L119 — L'elemento col bordo più vicino a ``point``, se entro ``distance``.
- `resolve_target(result: ForgeResult, target: Optional[str]) -> Any` — L126 — L'oggetto (contorno o feature) a cui punta un ``target``, o ``None``.
- `_elements(result: ForgeResult) -> Iterator[Tuple[str, Any, bool]]` — L147 — (percorso, geometria shapely, è chiuso) per contorni e feature di ogni cluster.
- `_item_geometry(item)` — L162
- `_size(geom, closed: bool) -> float` — L170 — A parità di distanza vince l'elemento più piccolo: un foro sul bordo del pezzo.
- `_assign(position, refs, snap_distance: float) -> Optional[int]` — L175
- `_nearest_within(probe: Point, refs, snap_distance: float) -> Optional[int]` — L184 — L'indice della parte più vicina a ``probe``, se entro ``snap_distance`` (> 0).

#### `forge/tools/inject.py` — 97 lines

_inject.py_

- `inject(result, data_injector: Optional[Callable]=None, snap_distance: float=0.0)` — L39 — Arricchisce i ForgeCluster con i dati estratti da un `data_injector` esterno.
- `_texts_by_part(result, snap_distance: float) -> Dict[int, List[str]]` — L74 — Testi di `result.annotations` per indice di parte. Un testo coperto da più

#### `forge/tools/non_contour.py` — 52 lines

_forge/tools/non_contour.py_

- `non_contour_candidates(doc: ForgeDocument, tolerance: Optional[float]=None) -> List[Edge]` — L40 — Edge di `doc.edges` che l'euristica topologica di `heal()` escluderebbe dal

#### `forge/tools/rotate.py` — 275 lines

_forge/tools/rotate.py_

- `structural_segments(result: ForgeResult, include_inners: bool=False) -> list` — L73 — Segmenti nativi dei contorni strutturali di ogni cluster: sempre
- `longest_structural_segment(result: ForgeResult, include_inners: bool=False) -> Tuple[Optional[object], float, Optional[float]]` — L89 — `(segment, length, angle_deg)` del segmento più lungo fra
- `_rotate_contour(contour: ForgeContour, angle_rad: float, origin: Point) -> ForgeContour` — L108
- `rotate_cluster(cluster: ForgeCluster, angle_rad: float, origin: Point=(0.0, 0.0)) -> ForgeCluster` — L117 — Nuovo `ForgeCluster` con `outer`/`inners` ruotati di `angle_rad` (radianti,
- `rotate_result(result: ForgeResult, angle_rad: float, origin: Point=(0.0, 0.0)) -> ForgeResult` — L147 — Nuovo `ForgeResult` con ogni cluster (`rotate_cluster`), `trash_entities`
- `rotate_document(doc: ForgeDocument, angle_rad: float, origin: Point=(0.0, 0.0), tolerance: float=DEFAULT_NODE_TOLERANCE) -> ForgeDocument` — L187 — Nuovo `ForgeDocument` con ogni `edge.segment` ruotato di `angle_rad`
- `_result_bbox_center(result: ForgeResult) -> Point` — L231 — Centro del bbox unito degli outer di tutti i cluster — vedi `rotate_to_longest`.
- `rotate_to_longest(result: ForgeResult, include_inners: bool=False, target_angle_deg: float=0.0, origin: Optional[Point]=None) -> Tuple[ForgeResult, float]` — L247 — Ruota `result` (già sano, da un `heal()` già fatto dal chiamante) in modo

#### `forge/tools/tabs.py` — 287 lines

_forge/tools/tabs.py_

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
- `_discretize_closed(contour, tolerance: float) -> List[Point]` — L217 — Punti grezzi chiusi di un `ForgeContour` (senza il punto di chiusura duplicato).
- `_ray_exit_point(points: List[Point], center: Point, direction: Point) -> Point` — L225 — Punto in cui il raggio da `center` verso `direction` esce dal contorno chiuso `points`.
- `bridge_nested_tabs(cluster, tab_width: float, tab_count: int=4, discretize_tolerance: float=0.05) -> List[NestedBridgeResult]` — L236 — Cammina `cluster.inners` (che porta `depth`/`parent` per ogni contorno,

## Internal dependencies

Which `forge` modules each module imports — "what works with what". Modules with no internal import are omitted.

| module | imports |
|---|---|
| `forge/__init__.py` | `forge.adapters.dxf.loader` · `forge.adapters.geometry.loader` · `forge.adapters.pdf.loader` · `forge.core` · `forge.core.heal` · `forge.core.healing.islands` · `forge.core.healing.normalizer` · `forge.core.healing.steps` · `forge.core.island` · `forge.core.primitives.fitting` · `forge.core.topology.loop_finder` · `forge.core.topology.noding` · `forge.core.topology.outer_face` · `forge.inspect` · `forge.io.dxf` · `forge.io.exporter` · `forge.io.svg` · `forge.io.text` · `forge.io.view_model` · `forge.model` · `forge.model.role` · `forge.model.role_rule` · `forge.recipes` · `forge.rules.palette` · `forge.rules.validator` · `forge.tools.anchor` · `forge.tools.inject` · `forge.tools.non_contour` · `forge.tools.rotate` |
| `forge/adapters/dxf/adapter.py` | `forge.adapters.dxf.parser` · `forge.core.adapter_base` · `forge.core.geometry.measure` · `forge.core.primitives.polygon_builder` · `forge.core.primitives.segments` · `forge.core.topology.edge` · `forge.model.document` · `forge.model.role_rule` · `forge.model.style` |
| `forge/adapters/dxf/annotation_extractor.py` | `forge.adapters.dxf.mtext` · `forge.model.annotation` |
| `forge/adapters/dxf/exporter.py` | `forge.core.primitives` · `forge.model.style` |
| `forge/adapters/dxf/layers.py` | `forge.model.role` · `forge.rules.palette` |
| `forge/adapters/dxf/loader.py` | `forge.adapters.dxf.adapter` · `forge.adapters.dxf.annotation_extractor` · `forge.adapters.dxf.sanitize` · `forge.model.document` · `forge.model.role_rule` |
| `forge/adapters/dxf/parser.py` | `forge.core.primitives` · `forge.core.primitives.segments` |
| `forge/adapters/dxf/sanitize.py` | `forge.core.healing.normalizer` |
| `forge/adapters/geometry/loader.py` | `forge.core.adapter_base` · `forge.core.geometry.measure` · `forge.core.primitives.segments` · `forge.core.topology.edge` · `forge.model.document` · `forge.model.role` |
| `forge/adapters/pdf/graph_adapter.py` | `forge.core.geometry.measure` · `forge.core.primitives.segments` · `forge.core.topology.edge` · `forge.model.role` |
| `forge/adapters/pdf/loader.py` | `forge.adapters.pdf.extractor_adapter` · `forge.adapters.pdf.graph_adapter` · `forge.adapters.pdf.sanitize` |
| `forge/adapters/pdf/sanitize.py` | `forge.adapters.pdf.geometry_adapter` · `forge.core.geometry.measure` |
| `forge/core/adapter_base.py` | `forge.core.geometry.measure` · `forge.core.topology.edge` · `forge.model.document` |
| `forge/core/geometry/__init__.py` | `forge.core.geometry.axis` · `forge.core.geometry.lines` · `forge.core.geometry.shape` |
| `forge/core/geometry/axis.py` | `forge.core.primitives.segments` |
| `forge/core/geometry/measure.py` | `forge.core.primitives.segments` |
| `forge/core/geometry/points.py` | `forge.core.primitives.segments` |
| `forge/core/geometry/shape.py` | `forge.core.geometry.measure` · `forge.core.primitives.segments` |
| `forge/core/heal.py` | `forge.core.healing.normalizer` · `forge.core.healing.steps` · `forge.core.primitives.segments` · `forge.core.topology.loop_finder` · `forge.model.document` · `forge.model.result` · `forge.model.role` · `forge.rules.validator` |
| `forge/core/healing/gap_solver.py` | `forge.core.geometry.intersections` · `forge.core.geometry.measure` · `forge.core.primitives.segments` · `forge.core.topology.edge` · `forge.model.role` |
| `forge/core/healing/hierarchy.py` | `forge.core.geometry.measure` · `forge.core.topology.loop_finder` · `forge.model.cluster` · `forge.model.contour` · `forge.model.feature` · `forge.model.role` |
| `forge/core/healing/islands.py` | `forge.core.topology.edge` · `forge.core.topology.noding` |
| `forge/core/healing/normalizer.py` | `forge.core.primitives.fitting` · `forge.core.primitives.segments` · `forge.core.topology.edge` · `forge.core.topology.graph` · `forge.model.role` |
| `forge/core/healing/outer_scan.py` | `forge.core.primitives.segments` · `forge.core.topology.edge` |
| `forge/core/healing/steps.py` | `forge.core.geometry.measure` · `forge.core.healing.gap_solver` · `forge.core.healing.hierarchy` · `forge.core.primitives` · `forge.core.primitives.polygon_builder` · `forge.core.primitives.segments` · `forge.core.topology.edge` · `forge.core.topology.graph` · `forge.core.topology.loop_finder` · `forge.core.topology.non_contour_edges` · `forge.model.cluster` · `forge.model.feature` · `forge.model.role` |
| `forge/core/island.py` | `forge.core.geometry.shape` · `forge.core.healing.gap_solver` · `forge.core.healing.islands` · `forge.core.healing.normalizer` · `forge.core.primitives.segments` · `forge.core.topology.edge` · `forge.core.topology.graph` · `forge.core.topology.loop_finder` · `forge.core.topology.noding` · `forge.core.topology.non_contour_edges` · `forge.core.topology.outer_face` · `forge.model.cluster` · `forge.model.contour` · `forge.model.document` · `forge.model.feature` · `forge.model.result` · `forge.model.role` |
| `forge/core/primitives/__init__.py` | `forge.core.primitives.polygon_builder` · `forge.core.primitives.segments` |
| `forge/core/primitives/fitting.py` | `forge.core.geometry.points` · `forge.core.primitives.segments` |
| `forge/core/primitives/polygon_builder.py` | `forge.core.primitives` |
| `forge/core/topology/edge.py` | `forge.core.primitives.segments` · `forge.model.style` |
| `forge/core/topology/graph.py` | `forge.core.geometry.measure` · `forge.core.primitives.segments` · `forge.core.topology.edge` |
| `forge/core/topology/loop_finder.py` | `forge.core.geometry.measure` · `forge.core.primitives.polygon_builder` · `forge.core.primitives.segments` · `forge.core.topology.edge` · `forge.core.topology.graph` · `forge.model.feature` |
| `forge/core/topology/noding.py` | `forge.core.geometry.intersections` · `forge.core.primitives.segments` · `forge.core.topology.edge` |
| `forge/core/topology/non_contour_edges.py` | `forge.core.topology.edge` · `forge.core.topology.graph` |
| `forge/core/topology/outer_face.py` | `forge.core.primitives.segments` · `forge.core.topology.edge` · `forge.core.topology.graph` · `forge.core.topology.loop_finder` |
| `forge/inspect.py` | `forge.adapters.dxf.loader` · `forge.core.geometry.measure` · `forge.core.heal` · `forge.core.primitives.segments` · `forge.core.topology.graph` · `forge.model.document` · `forge.model.role_rule` |
| `forge/io/dxf.py` | `forge.adapters.dxf.exporter` · `forge.adapters.dxf.layers` · `forge.core.geometry.measure` · `forge.model` · `forge.model.annotation` · `forge.model.document` · `forge.model.role` · `forge.rules.palette` |
| `forge/io/exporter.py` | `forge.adapters.dxf.layers` · `forge.model` · `forge.rules.metadata_schema` |
| `forge/io/svg.py` | `forge.io.view_model` · `forge.model` |
| `forge/io/text.py` | `forge.core.geometry.shape` · `forge.core.primitives.segments` · `forge.model` · `forge.model.annotation` |
| `forge/io/view_model.py` | `forge.core.geometry.measure` · `forge.model` · `forge.model.role` · `forge.rules.palette` |
| `forge/model/__init__.py` | `forge.core.topology.edge` · `forge.model.annotation` · `forge.model.cluster` · `forge.model.contour` · `forge.model.detected` · `forge.model.document` · `forge.model.feature` · `forge.model.result` · `forge.model.style` |
| `forge/model/cluster.py` | `forge.model.contour` |
| `forge/model/contour.py` | `forge.model.feature` |
| `forge/model/document.py` | `forge.core.topology.edge` · `forge.model.annotation` |
| `forge/model/feature.py` | `forge.core.primitives.segments` · `forge.model.style` |
| `forge/model/result.py` | `forge.model.annotation` · `forge.model.cluster` |
| `forge/model/role_rule.py` | `forge.model.role` · `forge.model.style` |
| `forge/recipes.py` | `forge.adapters.dxf.layers` · `forge.core.heal` · `forge.io.dxf` · `forge.model.document` · `forge.model.result` |
| `forge/rules/palette.py` | `forge.model.role` |
| `forge/rules/validator.py` | `forge.core.primitives.segments` · `forge.core.topology.graph` · `forge.model` · `forge.model.document` |
| `forge/tools/__init__.py` | `forge.tools.anchor` · `forge.tools.inject` |
| `forge/tools/anchor.py` | `forge.model.annotation` · `forge.model.result` |
| `forge/tools/inject.py` | `forge.tools.anchor` |
| `forge/tools/non_contour.py` | `forge.core.healing.steps` · `forge.core.topology.edge` · `forge.model.document` |
| `forge/tools/rotate.py` | `forge.core.geometry.measure` · `forge.core.primitives.segments` · `forge.model.cluster` · `forge.model.contour` · `forge.model.document` · `forge.model.feature` · `forge.model.result` |
| `forge/tools/tabs.py` | `forge.core.geometry.intersections` · `forge.core.geometry.measure` · `forge.core.primitives.segments` |

