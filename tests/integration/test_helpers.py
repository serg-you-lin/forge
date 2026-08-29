"""
tests/integration/test_helpers.py
----------------------------

Helper condivisi per test pipeline e semantic integrity.

Questi helper NON testano nulla.
Servono a costruire pipeline consistenti e riusabili.

Lancia:
    python -m unittest tests.integration.test_pipeline -v
"""

from pathlib import Path
import tempfile
import ezdxf

import forge


TESTS_DIR = Path(__file__).resolve().parent
DATA_DIR  = TESTS_DIR / "data"


def load(name: str) -> Path:
    """
    Restituisce il path assoluto di un DXF test.
    """
    return DATA_DIR / name


def run_pipeline(
    dxf_name,
    *,
    tolerance=0.2,
    do_detect=False,
    do_inject=False,
    do_write=False,
    reload_after_write=False,
    special_layers=None,
    interpreter=None,
):
    """
    Esegue una pipeline completa o parziale.

    Pipeline disponibile:
        heal
        detect
        inject
        write
        reload

    Returns:
        dict con:
            doc
            msp
            result

            reloaded_doc
            reloaded_msp
            reloaded_result
    """

    path = load(dxf_name)

    doc = forge.load_dxf(
        path,
        explode_inserts=True,
        tolerance=tolerance,
        label_map=special_layers or {},
    )

    result = forge.heal(
        doc,
        tolerance=tolerance,
        label=Path(dxf_name).stem,
        source_file=dxf_name,
    )

    if do_detect:
        forge.detect(
            result
        )

    if do_inject:
        forge.inject(result)

    doc_out = None
    if do_write:
        doc_out = forge.to_dxf(result, doc)

    output = {
        "doc": doc,
        "doc_out": doc_out,
        "msp": doc_out.modelspace() if doc_out is not None else None,
        "result": result,
        "reloaded_doc": None,
        "reloaded_msp": None,
        "reloaded_result": None,
    }

    if reload_after_write:

        tmp = tempfile.NamedTemporaryFile(
            suffix=".dxf",
            delete=False,
        )

        tmp.close()

        (doc_out or forge.to_dxf(result, doc)).saveas(tmp.name)

        reloaded_doc = forge.load_dxf(tmp.name, explode_inserts=True, tolerance=tolerance)

        reloaded_result = forge.heal(
            reloaded_doc,
            tolerance=tolerance,
            label=f"{Path(dxf_name).stem}_reloaded",
            source_file=tmp.name,
        )

        output["reloaded_doc"]    = reloaded_doc
        output["reloaded_msp"]    = None
        output["reloaded_result"] = reloaded_result

    return output


def count_entities_on_layer(msp, layer_name):
    """
    Conta entità su un layer.
    """
    return sum(
        1
        for e in msp
        if e.dxf.layer == layer_name
    )


def get_part(result, index=0):
    """
    Restituisce un ForgePart.
    """
    return result.parts[index]


def get_custom(result, key, default=None):
    """
    Shortcut per i conteggi/metadati di una parte.

    I conteggi feature vivono in part.summary (MAP.md D8); i dati aggiunti da
    un data_injector esterno in part.custom. Si guardano entrambi.
    """
    part = get_part(result)
    summary = part.summary
    if key in summary:
        return summary[key]
    return part.custom.get(key, default)