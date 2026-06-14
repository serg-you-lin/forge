

"""
workflow/splitter.py
--------------------
Divide un DXF con più pezzi in file separati.

Contratto:
    - split_to_files() è un wrapper di convenienza sulla pipeline completa.
      Internamente chiama heal() → detect() → split() in sequenza.
    - Il file sorgente non viene MAI modificato: legge dal msp originale
      e scrive sempre su nuovi documenti ezdxf.
    - Chi vuole controllo granulare usa direttamente la pipeline:
        result = forge.heal(msp, ...)
        forge.detect(result, msp, special_layers={...})
        forge.split(msp, result, output_folder)

    Il namer è una funzione (int, ForgePart) -> str decisa dal chiamante.

Workflow utente:

    # Caso A — pipeline completa in una chiamata
    result = forge.split_to_files(msp, output_folder,
                                  special_layers={"BEND": "bending"})

    # Caso B — pipeline manuale con controllo tra gli step
    result = forge.heal(msp, label="pezzo")
    forge.detect(result, msp, special_layers={"BEND": "bending"})
    # qui può intervenire un agente
    forge.split(msp, result, output_folder)

    # Caso C — namer con dati esterni
    def mio_namer(i, part):
        return lookup_codice(part.label, i)
    forge.split_to_files(msp, output_folder, namer=mio_namer)
"""

from __future__ import annotations

from typing import Callable, Optional
from unittest import result

from ..core.models import ForgeResult, BaseInterpreter
from .healer import heal
from .detection import detect
from .writeback import split, DEFAULT_MIN_PART_AREA, write


# ---------------------------------------------------------------------------
# API pubblica
# ---------------------------------------------------------------------------

def split_to_files(
    msp,
    output_folder:   str,
    label:           str                      = "",
    source_file:     str                      = "",
    tolerance:       float                    = 0.05,
    explode_inserts: bool                     = False,
    special_layers:  dict                     = None,
    interpreter:     Optional[BaseInterpreter] = None,
    namer:           Optional[Callable]        = None,
    keep_trash:      bool                     = False,
    include_annotations: bool                 = True,
    min_area:        float                    = DEFAULT_MIN_PART_AREA,
) -> ForgeResult:
    """
    Pipeline completa: heal → detect → split.

    Wrapper di convenienza — tutta la logica fisica vive in
    heal(), detect() e writeback.split().

    Args:
        msp:             modelspace ezdxf già aperto dal chiamante
        output_folder:   cartella dove salvare i file figli
        label:           nome base per i file
        source_file:     percorso del file originale (tracciabilità)
        tolerance:       tolleranza healing in mm
        explode_inserts: se True esplode gli INSERT prima dell'healing
        special_layers:  dict {nome_layer: work_type}
                         es. {"BEND": "bending", "MARK": "engrave"}
        interpreter:     implementazione di BaseInterpreter — opzionale
        namer:           funzione (int, ForgePart) -> str per il nome file
                         default: "{label}_{i}"
        keep_trash:      se True copia anche le entità Trash nei figli
        min_area:        area minima mm² per considerare un outer come pezzo reale

    Returns:
        ForgeResult con tutti i ForgePart trovati.
    """
    result = heal(
        msp,
        tolerance=tolerance,
        explode_inserts=explode_inserts,
        label=label,
        source_file=source_file,
        special_layers=special_layers,
    )

    for w in result.warnings:
        print(f"  [heal] {w}")
    for e in result.errors:
        print(f"  [heal ERROR] {e}")

    if not result.is_valid or not result.parts:
        return result

    detect(
        result,
        msp,
    )

    # write(msp, result)

    split(
        msp,
        result,
        output_folder=output_folder,
        namer=namer,
        keep_trash=keep_trash,
        include_annotations=include_annotations,
        min_area=min_area,
    )

    return result