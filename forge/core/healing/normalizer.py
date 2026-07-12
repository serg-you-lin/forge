"""
core/healing/normalizer.py
---------------------------
Normalizzazione geometrica format-agnostic.

Zero dipendenze da ezdxf, PDF, SVG o qualsiasi formato.
Lavora su chiavi opache prodotte dall'adapter e restituisce
i riferimenti da eliminare.

Concetto: due entità sono duplicate se producono la stessa chiave geometrica.
L'adapter decide come calcolare la chiave dal formato nativo.

Funzioni pubbliche:
    find_duplicates — dato un iterabile di (key, ref), restituisce i ref duplicati
"""

from __future__ import annotations
from typing import Any, Hashable, Iterable, List, Tuple


def find_duplicates(
    keyed_entities: Iterable[Tuple[Hashable, Any]],
) -> List[Any]:
    """
    Restituisce i ref delle entità duplicate (seconda occorrenza in poi).

    Parametri:
        keyed_entities : iterabile di (key, ref) — l'adapter produce le chiavi,
                         ref è opaco (l'adapter sa come eliminarlo)

    Restituisce:
        Lista di ref da eliminare. L'ordine riflette l'ordine di input.
    """
    seen:      set       = set()
    to_delete: List[Any] = []

    for key, ref in keyed_entities:
        if key is None:
            continue
        if key in seen:
            to_delete.append(ref)
        else:
            seen.add(key)

    return to_delete
