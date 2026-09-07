"""
scripts/_paths.py — un solo modo di gestire i percorsi negli script
==================================================================

Prima riga di ogni script della serie::

    import _paths  # noqa: F401

Da quel momento la cartella di lavoro è la radice del repo, SEMPRE — non conta
da dove lanci lo script (riga di comando, pulsante Run di VS Code, un terminale
aperto in un'altra cartella). Quindi nel blocco CONFIG scrivi il percorso
grezzo e basta:

    INPUT  = r"tests/examples/Multifeature.dxf"   # relativo -> parte dal repo
    INPUT  = r"C:\\job\\disegno_cliente.dxf"       # assoluto -> usato com'è
    OUTDIR = r"pipeline_output"                    # scritto in <repo>/pipeline_output

Nessun altro pattern da ricordare, niente `EXAMPLES / "..."`.

Underscore iniziale: non fa parte del package `forge`, vive solo qui accanto
agli script.
"""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
"""Radice del repo (scripts/ ne è figlia)."""

os.chdir(ROOT)
