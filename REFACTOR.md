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



