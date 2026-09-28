"""
forge/tools/non_contour.py
---------------------------
Espone a un consumatore lo stesso criterio topologico che `heal()` usa
internamente per decidere "questo edge non chiude un contorno" —
`NonContourEdgeDetector` (branching + centroide fuori dal convex hull della
sua componente connessa, MAP.md D49).

`heal()` non assegna mai un significato a questi edge: li esclude dal grafo e
basta, restano in `trash_entities` col ruolo che avevano (`unknown` se nessuno
l'ha già deciso). È `detect_flat()` — un consumatore a valle come un altro — a
interpretarli (`_detect_bending`, "candidato dritto con gli estremi sul
contorno esterno → piega, confidence 0.9").

Un consumatore diverso da `detect_flat()` (framer, l'interprete) può volere la
stessa lista di candidati SENZA quell'interpretazione, per applicarne una
propria (un bordo di feature in rilievo vista in pianta non è una piega) e
assegnare `edge.role` prima di chiamare `heal()` (vedi FRAMER.md, MAP.md D30).
`non_contour_candidates()` è il punto d'aggancio: stesso criterio, zero
duplicazione, nessuna fonte di verità seconda che possa divergere da quella
di `heal()`.

Nota: lavora su `doc.edges` così come sono, PRIMA che `heal()` fonda segmenti
sovrapposti/cocircolari e chiuda i gap minuscoli (i suoi primi passi interni,
D50/D52). Su un disegno con duplicati o gap sotto tolleranza il risultato può
differire di poco da quello che `heal()` escluderebbe a conti fatti — non è un
problema: questa funzione serve a decidere `edge.role` PRIMA di heal(), la
parola finale su cosa resta nel grafo la dice comunque heal() stesso.
"""

from __future__ import annotations

from typing import List, Optional

from ..model.document import ForgeDocument
from ..core.topology.edge import Edge
from ..core.healing.steps import find_non_contour_edges


def non_contour_candidates(doc: ForgeDocument, tolerance: Optional[float] = None) -> List[Edge]:
    """
    Edge di `doc.edges` che l'euristica topologica di `heal()` escluderebbe dal
    grafo dei contorni — candidati a "qualcos'altro", senza dire cosa.

    tolerance: se None ripresa da doc.source_meta['tolerance'] (stesso
               fallback di heal()).
    """
    edges = list(doc.edges)
    tol = tolerance if tolerance is not None else doc.source_meta.get("tolerance", 0.05)

    excluded_ids = find_non_contour_edges(edges, tol)
    return [e for e in edges if id(e) in excluded_ids]
