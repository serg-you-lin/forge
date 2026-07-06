dxf-forge/
│
├── forge/
│   │
│   ├── adapters/                  # Traduzione formato → primitivi
│   │   ├── dxf/
│   │   │   ├── virtual_adapter.py
│   │   │   ├── copy_adapter.py
│   │   │   └── loader.py
│   │   ├── pdf/                   # futuro
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
│   │   └── hints.py               # GeometryHints
│   │
│   ├── pipeline/                  # Le fasi orchestrate
│   │   ├── heal.py
│   │   ├── detect.py
│   │   ├── write.py
│   │   └── split.py
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