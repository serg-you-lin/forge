"""
inject.py
-----------
Arricchimento CAM opzionale di un ForgeResult già prodotto da heal() (+ detect()).

Da MAP.md D8: il conteggio delle feature (fori per tipo, pieghe, incisioni) NON
si fa più qui — è `part.summary`, una property derivata dal modello. `inject()`
resta solo per il suo lavoro unico: passare a un `data_injector` esterno i testi
che ricadono dentro l'outer di ogni parte (codice pezzo, materiale, spessore) e
mettere il dict risultante in `part.custom`.

I testi vengono da `result.annotations` (il modello tipato prodotto da
load_dxf): niente più `msp` o liste sciolte. Filtro per contenimento nell'outer
della parte — l'equivalente di quello che faceva `interpret_annotations()`, ma
applicato al volo qui perché `inject()` deve funzionare anche se quella fase non
è stata chiamata.

Contratto:
    - Opera su un ForgeResult già prodotto da heal() (+ detect()).
    - Lavora sul modello: non tocca ezdxf.
    - Il data_injector è opzionale — senza, inject() non fa nulla.
    - Muta result.parts[i].custom in-place e ritorna il result.

Flusso tipico:

    doc    = forge.load_dxf("pezzo.dxf", label_map={"Bend": "bending"})
    result = forge.heal_and_detect(doc)
    forge.inject(result, data_injector=leggi_cartiglio)
    forge.save_json(result, ...)   # i conteggi vengono da part.summary
"""

from typing import Callable, List, Optional

from shapely.geometry import Point


def inject(result, data_injector: Optional[Callable] = None):
    """
    Arricchisce i ForgePart con i dati estratti da un `data_injector` esterno.

    Muta `result.parts[i].custom` in-place e ritorna il `result`.

    Args:
        result:        ForgeResult prodotto da heal() (+ detect()).
        data_injector: `callable(ForgePart, list[str]) -> dict`. Riceve i testi
                       contenuti nell'outer della parte, restituisce i campi da
                       mettere in `part.custom` (materiale, spessore, codice, ...).
    """
    if not result.parts or data_injector is None:
        return result

    for part in result.parts:
        outer_poly = part.outer.polygon
        if outer_poly is None or outer_poly.is_empty:
            continue

        testi = _texts_inside(result.annotations, outer_poly)
        try:
            injected = data_injector(part, testi)
            if injected:
                part.custom.update(injected)
        except Exception as ex:
            result.warnings.append(
                f"data_injector fallito su {part.label}: {ex}"
            )

    return result


def _texts_inside(annotations, outer_poly) -> List[str]:
    """Testi delle annotazioni che ricadono dentro `outer_poly`, come list[str]."""
    return [
        ann.display_text
        for ann in annotations
        if ann.display_text and outer_poly.covers(Point(ann.position))
    ]
