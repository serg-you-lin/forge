# Smoother — da immagine a DXF pulito

`Smoother` è un **repo a sé**, sorella di `framer` e `bendly`, consumatore di
`forge` via `pip install -e ../dxf-forge` — non un modulo dentro forge (memoria
`forge-neutral-substrate-agent-layer-above`, `dont-bolt-adapters-onto-forge-for-external-projects`).

Nasce dal prototipo `smoother_5.py` (in questo repo, da spostare/archiviare
quando il nuovo repo esiste): porta un disegno organico da immagine
(un cancello, un logo, un contorno disegnato a mano) a un DXF pulito con
line/spline vere, non discretizzate.

## Perché non è dentro forge

Dipende da OpenCV (cv2), fa I/O immagine e — in prospettiva — UI di ritocco: né
l'una né l'altra cosa hanno posto in forge, che resta neutro, deterministico,
zero dipendenze da computer vision (stessa ragione per cui `framer` è fuori).
Quello che forge dà a Smoother è già pronto:

- `forge.simplify_points()` (MAP.md D33) — ricostruzione linea/spline da una
  sequenza di punti densa, con soglie parametriche
- `forge.load_geometry()` (MAP.md D32) — porta i contorni ricostruiti a
  `ForgeDocument`, pronto per `heal()`/`heal_and_detect()`
- `ForgeContour.depth`/`.parent` (MAP.md D34) — l'albero di contenimento, per
  sapere quali contorni sono "nipoti" (annidati a profondità ≥2) e di chi,
  necessario per le linguette

## La pipeline

```
immagine (PNG/JPG)
   │
   ▼
[1] B/N + ritocco a matita (UI, non ancora scritta)
   │
   ▼
[2] contorni via cv2.findContours
   │
   ▼
[3] forge.simplify_points()          → LineSeg / SplineSeg per contorno
   │
   ▼
[4] forge.load_geometry()            → ForgeDocument
   │
   ▼
[5] forge.heal()                     → ForgeCluster (outer/inners con depth/parent)
   │
   ▼
[6] Smoother: linguette sui nipoti    → usa depth/parent, decide dove e quanto
   │                                     larghe (parametri di processo/CAM,
   │                                     non di forge)
   ▼
[7] normalizzazione + DXF via forge.to_dxf()
```

Punto chiuso in sessione (2026-09-12): aggiungere un contenitore esterno dopo
il fatto (es. la lamiera attorno a un ingranaggio già tracciato) non richiede
nessuna operazione di "reparent" — `heal()` ricalcola il contenimento da zero
per geometria a ogni chiamata. Basta includere il nuovo contorno nello stesso
batch di `load_geometry()`: outer/figlio/nipote si aggiustano da soli.
Conseguenza per Smoother: non taggare `role="outer"`/`"inner"` sui contorni
tracciati finché non sai se la forma è definitiva — lascia `role` non
impostato e leggi `depth`/`parent` in uscita da `heal()` per sapere chi è
cosa. Disciplina di chi chiama, non responsabilità di forge.

## Estrazione/editing indipendente della polyline

Uso previsto anche standalone, fuori dalla pipeline immagine→DXF completa:
caricare un contorno (da immagine o da un DXF esistente), estrarne solo la
polyline, editarla liberamente, poi normalizzare e trasformare in spline. Le
tappe [3]-[5]-[7] sopra sono le stesse; cambia solo cosa entra al passo [2]
(un DXF via `forge.load_dxf()` invece di un'immagine).

## Fase futura — sito multi-tool (esplorativo, non iniziato)

Idea di Federico: un sito dove esporre Smoother e gli altri tool (non solo
questo) uno per pagina. Non ancora iniziato, nessun codice — solo la
direzione, per non chiudere strade con le scelte di Smoother:

- **Backend**: servizio Python sottile (FastAPI) che avvolge
  forge/Smoother/bendly — niente reimplementazione della geometria in JS.
  Formato di scambio: `forge.to_view_model()`/`to_json()`/`to_svg()`, già
  esistenti (`forge/io/view_model.py`, `forge/io/svg.py`).
- **Frontend**: TypeScript (non JS puro) — una base condivisa fra tool
  (editor a canvas/matita, editing di polyline, rendering SVG) conviene
  tipizzata da subito. Canvas/SVG nativi bastano, nessun framework pesante
  finché non serve davvero.
- Ogni tool è una pagina che parla con lo stesso backend; il browser
  modifica/visualizza, la verità geometrica resta lato Python.

## Stato

Non ancora aperto come repo. Prossimi passi quando si parte:
1. `git init` del repo `smoother`, sibling di `dxf-forge`/`framer`/`bendly`
2. `pip install -e ../dxf-forge` come dipendenza
3. Migrare `smoother_5.py` come primo script di prova, sostituendo
   `classifica_punti`/`scrivi_contorno` con `forge.simplify_points()`
