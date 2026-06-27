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

import dxf_forge as forge

# from dxf_forge.rules.interpreter import GeometricInterpreter


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

    # if interpreter is None:
    #     interpreter = GeometricInterpreter()

    path = load(dxf_name)

    doc = ezdxf.readfile(path)
    msp = doc.modelspace()

    result = forge.heal(
        msp,
        tolerance=tolerance,
        explode_inserts=True,
        label=Path(dxf_name).stem,
        source_file=dxf_name,
        special_layers=special_layers or {},
    )

    if do_detect:
        forge.detect(
            result,
            msp,
        )

    if do_inject:
        forge.inject(msp, result)

    if do_write:
        forge.write(msp, result)

    output = {
        "doc": doc,
        "msp": msp,
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

        doc.saveas(tmp.name)

        reloaded_doc = ezdxf.readfile(tmp.name)
        reloaded_msp = reloaded_doc.modelspace()

        reloaded_result = forge.heal(
            reloaded_msp,
            tolerance=tolerance,
            explode_inserts=True,
            label=f"{Path(dxf_name).stem}_reloaded",
            source_file=tmp.name,
        )

        output["reloaded_doc"]    = reloaded_doc
        output["reloaded_msp"]    = reloaded_msp
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
    Shortcut per part.custom.
    """
    part = get_part(result)
    return part.custom.get(key, default)