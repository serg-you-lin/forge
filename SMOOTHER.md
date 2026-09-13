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

**Due passate, non una** (chiuso in sessione 2026-09-13, `smoother/MAP.md` D5):
il calcolo del contenimento (`depth`/`parent`) non ha bisogno di geometria già
fittata — `heal()` discretizza comunque ogni segmento per costruire i poligoni
di contenimento (`core/healing/hierarchy.py`), quindi una sequenza di punti
grezza funziona come una spline già fittata. Fittare prima e tagliare le
linguette dopo, sulla spline, avrebbe voluto dire spezzare una curva NURBS a
metà — possibile ma tutt'altro che banale, mentre tagliare un buco in una
sequenza di punti è triviale.

```
immagine (PNG/JPG)
   │
   ▼
[1] B/N + ritocco a matita +anteprima spline (abbiamo l'svg json da forge pronto) (UI, non ancora scritta)
   │
   ▼
[2] contorni via cv2.findContours
   │
   ▼
[A] forge.load_geometry("polyline")  → forge.heal_and_detect()
   │     → depth/parent per contorno (nessun fit necessario per questo)
   ▼
[B] Smoother: linguette sui nipoti    → taglia un ponticello nei PUNTI GREZZI
   │                                     del contorno nipote, prima del fit
   │                                     (parametri di processo/CAM, non di
   │                                     forge; non ancora implementato)
   ▼
[C] forge.simplify_points()          → LineSeg / SplineSeg per contorno
   │
   ▼
forge.load_geometry("spline") → forge.heal_and_detect() → forge.to_dxf()

NON SO SE è CHIARO, IO CARICO L'IMMAGINEE HO GIà LA SPLINE OTTENUTA, RITOCCO A MATITA E LA SPLINE SI AGGIORNA VIA VIA. 
ON DICO CHE DOBBIAMO AVERE LA POSSIBILITà DI RITOCCAE ANCHE GLI ENDPOINT DELLA LWPLINE, MA SAREBBE BELLO AVERE TUTTO NELL''INTERFACIA. SE è TROPPO, LASCIAMO STARE.
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

Aperto come repo il 2026-09-13, sibling di `dxf-forge`/`framer`. Questo
documento resta lo spec d'origine (perché); le decisioni vive e il piano di
lavoro stanno in `smoother/MAP.md` e `smoother/TODO.md`, come `FRAMER.md` sta a
`framer/DESIGN.md`.

Fatto: scaffolding del repo, `smoother_5.py` migrato in
`scripts/00_image_to_dxf.py` (spigoli/refit ora via `forge.simplify_points()`,
non più codice locale) e archiviato qui in `_archive/`; `load_geometry()` ha
guadagnato il tipo `"spline"` (MAP.md D35, sotto); lo script è stato riscritto
sulle due passate della pipeline sopra.

Varco (chiuso, MAP.md D35): `forge.load_geometry()` accettava solo entità
`line`/`arc`/`circle`/`polyline`, non `spline`. **Non era però il pezzo che
bloccava le linguette** — quello (il contenimento) usa solo `"polyline"`, che
c'era già; il tipo `"spline"` serve alla passata finale [C], per scrivere in
uscita la geometria fittata. Vedi `smoother/MAP.md` D5 per l'errore di
sequenza e la correzione.
