"""
generate_rotation_fixture.py
-----------------------------
Genera `try_for_rotation.dxf`: rettangolo alto e stretto (100 x 400, outer
verticale) con una linea interna inclinata — come fosse una bending line, ma
in diagonale invece che parallela a un lato — per testare
`forge.tools.rotate` (allineare il lato OUTER più lungo, ignorando questa
diagonale che è più corta e comunque non outer).

    python tests/generate_rotation_fixture.py
"""

import ezdxf
from pathlib import Path

EXAMPLES_DIR = Path(__file__).resolve().parent / "examples"
EXAMPLES_DIR.mkdir(parents=True, exist_ok=True)

W, H = 100.0, 400.0  # largo 100, alto 400 — i lati più lunghi sono i verticali

doc = ezdxf.new(dxfversion="R2010")
msp = doc.modelspace()

# Outer: rettangolo chiuso, lati verticali (lunghezza H=400) più lunghi dei
# lati orizzontali (larghezza W=100) — l'outer più lungo atteso è verticale,
# angolo 90°.
msp.add_lwpolyline(
    [(0, 0), (W, 0), (W, H), (0, H)],
    close=True,
)

# Linea interna diagonale, come una bending line ma non parallela a un lato:
# dal lato sinistro (vicino, non esattamente sopra) al lato destro, ad
# altezze diverse — stessa convenzione di bending_lines_1.dxf/
# two_rects_with_bend.dxf: endpoint entro 1mm dal bordo outer (criterio di
# `detect._detect_bending`), non esattamente coincidenti per non toccare la
# topologia dell'outer.
msp.add_line((0.3, 50.0), (W - 0.3, H - 50.0))

path = EXAMPLES_DIR / "try_for_rotation.dxf"
doc.saveas(str(path))
print(f"Generato: {path}")
