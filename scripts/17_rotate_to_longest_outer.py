"""
17_rotate_to_longest_outer.py — allinea il segmento OUTER più lungo all'orizzontale
====================================================================================

API topo usate (sperimentali — importabili come topo.rotate_to_longest,
non ancora in __all__/docs, vedi MAP.md D46):
    topo.rotate_to_longest      Result -> (Result ruotato,
                                  angle_deg applicato) — UN SOLO heal() in
                                  tutto (quello fatto qui sotto): una
                                  rotazione rigida non cambia la topologia,
                                  quindi ruota direttamente il Result già
                                  sano, non richiama heal() una seconda volta
    longest_structural_segment   Result -> (segment, length, angle_deg)
                                  del segmento più lungo fra gli outer di
                                  ogni cluster (include_inners=True per
                                  includere anche i loop interni) — helper di
                                  introspezione, resta su topo.tools.rotate

Fixture: `try_for_rotation.dxf` (tests/generate_rotation_fixture.py) — un
rettangolo alto e stretto (100x400, outer verticale) con una linea interna
diagonale come una bending line ma non parallela a un lato: dimostra che il
filtro prende il lato OUTER più lungo, non una traccia interna qualunque.

    python scripts/17_rotate_to_longest_outer.py
"""

import _paths  # noqa: F401  — chdir alla radice del repo

import os
import topo
from topo.tools.rotate import longest_structural_segment

# --- CONFIG ------------------------------------------------------------
INPUT = r"tests/data/try_for_rotation.dxf"
TOLERANCE = 0.5
OUTDIR = "pipeline_output"
# -------------------------------------------------------------------------

doc = topo.load_dxf(INPUT, tolerance=TOLERANCE)
result = topo.heal(doc, tolerance=TOLERANCE)  # unico heal() di tutto lo script

_, length, angle_deg = longest_structural_segment(result)  # include_inners=False
print(f"outer più lungo PRIMA : {length:.1f}mm a {angle_deg:.1f}°")

rotated_result, applied_deg = topo.rotate_to_longest(result)
print(f"rotazione applicata   : {applied_deg:.1f}°")

_, length2, angle_deg2 = longest_structural_segment(rotated_result)
print(f"outer più lungo DOPO  : {length2:.1f}mm a {angle_deg2:.1f}°  (atteso ~0°)")

os.makedirs(OUTDIR, exist_ok=True)
out = topo.to_dxf(rotated_result, source_doc=doc, include_trash=True)
path = os.path.join(OUTDIR, "try_for_rotation_rotated.dxf")
out.saveas(path)
print(f"scritto               -> {path}")
