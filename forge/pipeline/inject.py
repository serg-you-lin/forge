"""
inject.py
-----------
Arricchimento CAM opzionale di un ForgeResult già prodotto da heal() + detect().

Da MAP.md D8: il conteggio delle feature (fori per tipo, pieghe, incisioni) NON
si fa più qui — è `part.summary`, una property derivata dal modello. `inject()`
resta solo per il suo lavoro unico: passare i testi che ricadono dentro l'outer
di ogni parte a un `data_injector` esterno (codice pezzo, materiale, spessore),
e mettere il dict risultante in `part.custom`.

Contratto:
    - Opera su un ForgeResult già prodotto da heal() (+ detect()).
    - Lavora sul modello: non tocca ezdxf.
    - Il data_injector è opzionale — senza, inject() non fa nulla.
    - Muta result.parts[i].custom in-place e ritorna il result.

Flusso tipico:

    doc    = forge.load_dxf("pezzo.dxf", label_map={"Bend": "bending"})
    result = forge.heal_and_detect(doc)
    forge.inject(result, data_injector=leggi_cartiglio,
                 texts=forge.extract_texts_from_msp(msp))
    forge.save_json(result, ...)   # i conteggi vengono da part.summary
"""

from typing import Callable, Optional

from ..model.text import ForgeText


def inject(
    result,
    data_injector: Optional[Callable] = None,
    texts: Optional[list[ForgeText]] = None,
    tolerance: float = 0.1,
):
    """
    Arricchisce i ForgePart con i dati estratti da un `data_injector` esterno.

    Muta `result.parts[i].custom` in-place e ritorna il `result`.

    Args:
        result:        ForgeResult prodotto da heal() (+ detect()).
        data_injector: `callable(ForgePart, list[str]) -> dict`. Riceve i testi
                       contenuti nell'outer della parte, restituisce i campi da
                       mettere in `part.custom` (materiale, spessore, codice, ...).
        texts:         lista di ForgeText (da `extract_texts_from_msp` +
                       costruzione ForgeText, o da un estrattore proprio).
        tolerance:     accettato per compatibilità di firma; non più usato.
    """
    if not result.parts or data_injector is None:
        return result

    for part in result.parts:
        outer_poly = part.outer.polygon
        if outer_poly is None or outer_poly.is_empty:
            continue

        testi = _filter_texts_for_part(texts or [], outer_poly)
        try:
            injected = data_injector(part, testi)
            if injected:
                part.custom.update(injected)
        except Exception as ex:
            result.warnings.append(
                f"data_injector fallito su {part.label}: {ex}"
            )

    return result


def _filter_texts_for_part(texts: list[ForgeText], outer_poly) -> list[str]:
    """
    Filtra i ForgeText che ricadono dentro l'outer_poly del part.
    Restituisce list[str] per compatibilità con data_injector esistenti.
    """
    return [
        t.content for t in texts
        if outer_poly.covers(t.position)
    ]
