"""
17_rotate_to_longest_outer.py — allinea il lato OUTER più lungo all'orizzontale
================================================================================

API forge usate (sperimentali, forge.tools.rotate — non ancora nell'API
pubblica top-level):
    longest_outer_segment   ForgeResult -> (segment, length, angle_deg) del
                             lato OUTER più lungo — filtrato a cluster.outer,
                             ignora qualunque altra geometria del disegno
                             (bending line, incisioni, ...)
    rotate_to_longest_outer ForgeDocument -> (ForgeDocument ruotato, angle_deg
                             applicato) — due passate: heal() per scoprire
                             l'angolo, poi ruota la geometria grezza

Fixture: `try_for_rotation.dxf` (tests/generate_rotation_fixture.py) — un
rettangolo alto e stretto (100x400, outer verticale) con una linea interna
diagonale come una bending line ma non parallela a un lato: dimostra che il
filtro prende il lato OUTER più lungo, non una traccia interna qualunque.

    python scripts/17_rotate_to_longest_outer.py
"""

import _paths  # noqa: F401  — chdir alla radice del repo

import os
import forge
from forge.tools.rotate import rotate_to_longest_outer, longest_outer_segment

# --- CONFIG ------------------------------------------------------------
INPUT = r"tests/examples/try_for_rotation.dxf"
TOLERANCE = 0.5
OUTDIR = "pipeline_output"
# -------------------------------------------------------------------------

doc = forge.load_dxf(INPUT, tolerance=TOLERANCE)

result_before = forge.heal(doc, tolerance=TOLERANCE)
_, length, angle_deg = longest_outer_segment(result_before)
print(f"outer più lungo PRIMA : {length:.1f}mm a {angle_deg:.1f}°")

rotated_doc, applied_deg = rotate_to_longest_outer(doc, tolerance=TOLERANCE)
print(f"rotazione applicata   : {applied_deg:.1f}°")

result_after = forge.heal(rotated_doc, tolerance=TOLERANCE)
_, length2, angle_deg2 = longest_outer_segment(result_after)
print(f"outer più lungo DOPO  : {length2:.1f}mm a {angle_deg2:.1f}°  (atteso ~0°)")

os.makedirs(OUTDIR, exist_ok=True)
out = forge.to_dxf(result_after, source_doc=rotated_doc, include_trash=True)
path = os.path.join(OUTDIR, "try_for_rotation_rotated.dxf")
out.saveas(path)
print(f"scritto               -> {path}")
