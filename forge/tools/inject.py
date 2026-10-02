"""
inject.py
-----------
Arricchimento CAM opzionale di un ForgeResult già prodotto da heal() (+ detect_flat()).

Da MAP.md D8: il conteggio delle feature (fori per tipo, pieghe, incisioni) NON
si fa più qui — è `cluster.summary`, una property derivata dal modello. `inject()`
resta solo per il suo lavoro unico: passare a un `data_injector` esterno i testi
che ricadono dentro l'outer di ogni parte (codice pezzo, materiale, spessore) e
mettere il dict risultante in `cluster.custom`.

I testi vengono da `result.annotations` (il modello tipato prodotto da
load_dxf): niente più `msp` o liste sciolte. Filtro per contenimento nell'outer
della parte — l'equivalente di quello che faceva `anchor_annotations()`, ma
applicato al volo qui perché `inject()` deve funzionare anche se quella fase non
è stata chiamata.

Contratto:
    - Opera su un ForgeResult già prodotto da heal() (+ detect_flat()).
    - Lavora sul modello: non tocca ezdxf.
    - Il data_injector è opzionale — senza, inject() non fa nulla.
    - Muta result.clusters[i].custom in-place e ritorna il result.

Flusso tipico:

    doc    = forge.load_dxf("pezzo.dxf", role_rules=forge.name_rules({"Bend": "bending"}))
    result = forge.heal_and_detect(doc)
    forge.inject(result, data_injector=leggi_cartiglio)
    forge.save_json(result, ...)   # i conteggi vengono da cluster.summary
"""

from typing import Callable, Dict, List, Optional

from shapely.geometry import Point

from .anchor import _nearest_within


def inject(result, data_injector: Optional[Callable] = None,
           snap_distance: float = 0.0):
    """
    Arricchisce i ForgeCluster con i dati estratti da un `data_injector` esterno.

    Muta `result.clusters[i].custom` in-place e ritorna il `result`.

    Args:
        result:        ForgeResult prodotto da heal() (+ detect_flat()).
        data_injector: `callable(ForgeCluster, list[str]) -> dict`. Riceve i testi
                       contenuti nell'outer della parte, restituisce i campi da
                       mettere in `cluster.custom` (materiale, spessore, codice, ...).
        snap_distance: > 0 → un testo fuori da ogni parte va alla parte più vicina
                       se dista al massimo tanto dal suo contorno (stessa regola di
                       `anchor_annotations`). Default 0.0: solo contenimento.
    """
    if not result.clusters or data_injector is None:
        return result

    testi = _texts_by_part(result, snap_distance)
    for i, cluster in enumerate(result.clusters):
        if i not in testi:
            continue
        try:
            injected = data_injector(cluster, testi[i])
            if injected:
                cluster.custom.update(injected)
        except Exception as ex:
            result.warnings.append(
                f"data_injector fallito su {cluster.label}: {ex}"
            )

    return result


def _texts_by_part(result, snap_distance: float) -> Dict[int, List[str]]:
    """
    Testi di `result.annotations` per indice di parte. Un testo coperto da più
    outer va a ciascuno; uno fuori da tutti va alla parte più vicina entro
    `snap_distance`, altrimenti a nessuna.
    """
    refs = [
        (i, c.outer.polygon)
        for i, c in enumerate(result.clusters)
        if c.outer is not None and c.outer.polygon is not None
        and not c.outer.polygon.is_empty
    ]
    testi: Dict[int, List[str]] = {i: [] for i, _ in refs}
    for ann in result.annotations:
        if not ann.display_text:
            continue
        probe = Point(ann.position)
        parts = [i for i, poly in refs if poly.covers(probe)]
        if not parts:
            nearest = _nearest_within(probe, refs, snap_distance)
            parts = [] if nearest is None else [nearest]
        for i in parts:
            testi[i].append(ann.display_text)
    return testi
