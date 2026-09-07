"""
_paths.py — ancore di percorso per gli script numerati
=====================================================

Gli script della serie (``00_*.py`` … ``14_*.py``) importano da qui invece di
scrivere percorsi relativi alla cartella di lavoro. Cosí ``python 03_detect.py``
e il pulsante Run di VS Code si comportano identici da qualsiasi CWD, e per
puntare a un file esterno al progetto basta un path assoluto nel blocco CONFIG
senza dover cambiare la root.

Perché funziona: Python mette in ``sys.path[0]`` la cartella dello script, non
il CWD — quindi ``from _paths import ...`` risolve sempre finché ``_paths.py``
sta accanto agli script (la radice del repo).

Underscore iniziale: non fa parte del package ``forge``, vive solo accanto agli
script (come ``_archive/``).
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent
"""Radice del repo (la cartella che contiene questo file)."""

EXAMPLES = ROOT / "tests" / "examples"
"""Fixture DXF di input per gli script."""

OUTPUT = ROOT / "pipeline_output"
"""Cartella di output degli script (git-ignored)."""
