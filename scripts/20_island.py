"""
20_island.py — lettura per isole su tutti i disegni di una cartella
==================================================================

API forge usate:
    forge.island(doc, island_gap=, max_gap=)
                                -> ForgeResult, un ForgeCluster per isola
                                   (outer = contorno esterno, inners = giri
                                   chiusi dentro; isole annidate → interno
                                   di quella che le contiene)
    forge.read_islands(edges, tolerance, island_gap, max_gap)
                                -> [IslandReading]: per ogni isola cosa è
                                   stato deciso, pezzo per pezzo

Per ogni file un DXF con un layer per decisione, per vedere cosa ha fatto
ogni passo (i ruoli qui sotto sono solo del DXF di controllo: island() non
assegna ruoli, mette tutto il resto in trash come `unknown`):
    OuterContour     contorno esterno di ogni isola non annidata
    InnerContour     giri chiusi dentro (e contorni delle isole annidate)
    sporgenza        percorsi andata e ritorno dal contorno (assi, segni)
    fuori_contorno   pezzi dell'isola rimasti fuori dal contorno
    non_contorno     candidati non-contorno (criterio di heal, D49)
    Trash            il resto, non classificato

    python scripts/20_island.py
"""

import _paths  # noqa: F401  — chdir alla radice del repo

import glob
import os
import time
import traceback

import forge
from forge.model.feature import OpenFeature

# --- CONFIG ----------------------------------------------------------------
INPUT_DIR = r"tests/examples/islands"          # tutti i .dxf/.dwg qui dentro
EXCLUDE = ["_healed"]                           # file il cui nome contiene questi pezzi
TOLERANCE = 0.05
ISLAND_GAP = 10.0                               # mm — distanza massima fra due edge della stessa isola
MAX_GAP = 0.5                                   # mm — gap chiusi fra estremi liberi
OUTDIR = r"pipeline_output/island"
# ---------------------------------------------------------------------------


def _inputs():
    paths = []
    for pattern in ("*.dxf", "*.DXF", "*.dwg", "*.DWG"):
        paths += glob.glob(os.path.join(INPUT_DIR, pattern))
    paths = sorted(dict.fromkeys(os.path.normcase(p) for p in paths))
    return [p for p in paths if not any(x.lower() in os.path.basename(p).lower() for x in EXCLUDE)]


def _diagnostic(result, readings):
    """Il trash di island() è tutto `unknown`: per il DXF di controllo lo si
    ridistribuisce sui layer della decisione presa, letta da IslandReading."""
    trash = []
    for r in readings:
        for role, edges in (("sporgenza", r.spurs), ("fuori_contorno", r.outside),
                            ("non_contorno", r.non_contour), ("unknown", r.unclassified)):
            trash += [OpenFeature(role=role, segments=[e.segment], styles=[e.style]) for e in edges]
        if r.outer is None:
            trash += [OpenFeature(role="unknown", segments=[e.segment], styles=[e.style]) for e in r.edges]
    result.trash_entities = trash
    return result


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    for path in _inputs():
        stem = os.path.splitext(os.path.basename(path))[0]
        t0 = time.time()
        try:
            doc = forge.load_dxf(path, tolerance=TOLERANCE)
            result = forge.island(doc, tolerance=TOLERANCE, island_gap=ISLAND_GAP, max_gap=MAX_GAP)
            readings = forge.read_islands(doc.edges, TOLERANCE, island_gap=ISLAND_GAP, max_gap=MAX_GAP)
        except Exception as exc:
            print(f"{stem}: ERRORE {type(exc).__name__}: {exc}")
            traceback.print_exc(limit=3)
            continue
        n_out = len(result.clusters) if result.is_valid else 0
        print(f"{stem}: {len(doc.edges)} edge, {len(readings)} isole, "
              f"{n_out} contorni esterni, {time.time() - t0:.1f}s")
        for c in result.clusters:
            print(f"  outer {c.outer.polygon.area:.0f} mm², {len(c.inners)} inner")
        suffix = ""
        if not result.is_valid:
            # to_dxf rifiuta un risultato invalido: qui lo si vuole vedere lo stesso
            result.is_valid, result.errors = True, []
            suffix = "_INVALIDO"
        out = os.path.abspath(os.path.join(OUTDIR, f"{stem}{suffix}.dxf"))
        try:
            forge.to_dxf(_diagnostic(result, readings), doc, include_trash=True).saveas(out)
            print(f"  -> {out}")
        except PermissionError:
            print(f"  !! {out} è aperto in un altro programma: non sovrascritto")


if __name__ == "__main__":
    main()
