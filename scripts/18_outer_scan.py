"""
18_outer_scan.py — candidati a bordo esterno per ray casting, verifica visiva
============================================================================

API forge usate (sperimentali — non ancora in __all__/docs):
    forge.core.healing.outer_scan.outer_candidate_edges
        edges -> OuterCandidates (.edges, .ids, .hits_of(edge), .n_rays)

Per ogni file: tutti gli edge in grigio, i candidati in rosso. Se il file ha
un ground truth dipinto a mano (edge con colore GROUND_TRUTH_COLOR), va sotto
in ciano spesso e in console escono presi / mancati / in più.

    python scripts/18_outer_scan.py
"""

import _paths  # noqa: F401  — chdir alla radice del repo

import os
import forge
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from forge.core.healing.outer_scan import outer_candidate_edges

# --- CONFIG ----------------------------------------------------------------
INPUTS = [
    r"tests/examples/islands/3d_painted.dxf",
    r"tests/examples/islands/SHEETCODE_1.dxf",
    r"tests/examples/islands/SHEETCODE_2.dxf",
    r"tests/examples/islands/SHEETCODE_3.dxf",
    r"tests/examples/islands/SHEETCODE.dxf",
]
GROUND_TRUTH_COLOR = 134
OUTDIR = r"pipeline_output/outer_scan"
# ---------------------------------------------------------------------------


def _plot_edges(ax, edges, **kw):
    for e in edges:
        pts = e.segment.discretize(0.05)
        ax.plot([p[0] for p in pts], [p[1] for p in pts], **kw)


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    for path in INPUTS:
        doc = forge.load_dxf(path)
        oc = outer_candidate_edges(doc.edges)
        stem = os.path.splitext(os.path.basename(path))[0]

        line = f"{stem}: {len(doc.edges)} edge -> {len(oc.edges)} candidati ({oc.n_rays} raggi)"
        truth = [e for e in doc.edges if e.style.color == GROUND_TRUTH_COLOR]
        if truth:
            truth_ids = {id(e) for e in truth}
            line += (f" | ground truth {len(truth)}: presi {len(truth_ids & oc.ids)},"
                     f" mancati {len(truth_ids - oc.ids)}, in più {len(oc.ids - truth_ids)}")
        print(line)

        fig, ax = plt.subplots(figsize=(14, 10))
        if truth:
            _plot_edges(ax, truth, color="cyan", linewidth=5, alpha=0.6)
        _plot_edges(ax, doc.edges, color="0.7", linewidth=0.4)
        _plot_edges(ax, oc.edges, color="red", linewidth=1.2)
        ax.set_aspect("equal")
        ax.set_title(f"{stem} — rosso: candidati, ciano: ground truth")
        out = os.path.join(OUTDIR, f"{stem}.png")
        fig.savefig(out, dpi=150, bbox_inches="tight")
        plt.close(fig)
        print(f"  -> {out}")


if __name__ == "__main__":
    main()
