dxf-forge/
│
├── forge/
│   │
│   ├── adapters/                  # Traduzione formato → primitivi
│   │   ├── dxf/
│   │   ├── pdf/                   # in costruzione
│   │   └── svg/                   # futuro
│   │
│   ├── core/                      # Motore geometrico puro
│   │   ├── primitives/            # LineSeg, ArcSeg, SplineSeg
│   │   ├── topology/              # topologia, loop detection, graph
│   │   ├── hierarchy/             # containment, holes
│   │   ├── healing/               # gap closing, dedup, normalize
│   │   └── frame/                 # frame detection
│   │
│   ├── model/                     # Forge domain model
│   │   ├── part.py                # ForgePart
│   │   ├── hole.py                # Hole
│   │   ├── edge.py                # Edge
│   │   ├── result.py              # ForgeResult
│   │   ├── shape.py         # OpenShape, ClosedShape
│   │   └── classified.py              
│   │
│   ├── pipeline/                  # Le fasi orchestrate
│   │   ├── heal.py
│   │   ├── detect.py
│   │   ├── write.py
│   │   └── split.py
│   │   └── inject.py
│   │
│   ├── rules/                  # Regole di Forge
│   │   ├── metadata_schema.py
│   │   ├── palette.py
│   │   ├── thresholds.py
│   │   └── validator.py
│   │   └── inject.py
│   │
│   └── tools/                     # Tools sul modello (futuri)
│       ├── validator.py
│       ├── hasher.py              # fingerprint geometrica
│       ├── analyzer.py            # DxfAnalyzer, CSV export
│       └── offset.py      
│
|  drawing_parser/          #     Plugin esterno - usa forge internamente    
|      ├── view_classifier.py    ← ragiona su ForgeModel
|      ├── view_reconstructor.py ← ricompone interruzioni, parti piegate, ecc...
|      └── thickness_extractor.py
│
└── tests/





📂 forge\adapters\dxf\

├── loader.py                    (invariato)
│     load_dxf, _read_dwg, _upgrade_to_r2010

├── sanitize.py                  (+ dedup_adapter)
│     sanitize, normalize_ocs, flatten_z, _explode_inserts
│     deduplicate, _key_for, extract_keyed_entities, delete_entities

├── geometry_adapter.py          (solo geometria pura)
│     entity_to_polygon, pline_to_polygon
│     arc_endpoints, arc_to_bulge, arc_to_linestrings
│     spline_to_points
│     _polygon_pline, _polygon_circle, _polygon_flattened
│     _arc_endpoint
│     + registri interni (_register_polygon, ecc.)

├── graph_adapter.py             (invariato + frame)
│     edges_from_msp
│     _entity_endpoints, _normalized_endpoints, _entity_to_linestring, _spline_endpoints
│     _line_to_raw, _lwpoly_to_raw, _entity_to_raw, extract_frame_handles

├── virtual_adapter.py           (invariato)
│     DxfWriteContext
│     _loop_to_contour, parse_loop
│     _parse_line, _parse_arc, _parse_arc_discretized, _parse_spline
│     _build_pts_with_bulge, _extract_origin
│     _write_virtual_shape

├── proxy_adapter.py             (nuovo)
│     entity_to_proxy, contour_to_proxy

├── copy_adapter.py              (invariato)
│     copy_entity, _copy_*, _register_copy

├── gap_adapter.py               (invariato)
│     extract_free_endpoints, apply_gap_fixes, _apply_move, _apply_add_segment, _meta_for

└── hole_detector.py             (estratto da geometry_adapter)
│     is_threaded_arc, is_threaded_hole, is_countersink_outer
      get_representative_point, entity_midpoint, entity_length
      _repr_pt_*, _line_length, _arc_length, ecc.