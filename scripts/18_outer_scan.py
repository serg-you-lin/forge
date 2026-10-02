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
# Default sui fogli di vista anonimizzati che stanno in git. Per girare su un
# disegno vero metti qui il suo percorso (anche assoluto: `_paths` ha già fatto
# chdir alla radice, quindi i relativi partono da lì) — ma non committare mai
# il nome di un file cliente in uno script tracciato.
INPUTS = [
    r"tests/examples/golden_anchoring/anch_02.dxf",
    r"tests/examples/golden_anchoring/anch_05.dxf",
]
GROUND_TRUTH_COLOR = 134
OUTDIR = r"pipeline_output/outer_scan"
# finestre di zoom per nome file, senza estensione (xmin, xmax, ymin, ymax):
# un PNG in più per ognuna. Vuoto = solo la vista intera.
ZOOMS: dict[str, list[tuple[float, float, float, float]]] = {}
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

        windows = [(None, "")] + [(w, f"_zoom{i + 1}") for i, w in enumerate(ZOOMS.get(stem, []))]
        for window, suffix in windows:
            fig, ax = plt.subplots(figsize=(14, 10))
            if truth:
                _plot_edges(ax, truth, color="cyan", linewidth=5, alpha=0.6)
            _plot_edges(ax, doc.edges, color="0.6", linewidth=0.5)
            _plot_edges(ax, oc.edges, color="red", linewidth=1.2)
            # dove i raggi hanno toccato: è lì che si vede quale tratto di un edge è esterno
            pts = [h.point for e in oc.edges for h in oc.hits_of(e)]
            ax.plot([p[0] for p in pts], [p[1] for p in pts], "b.", markersize=2)
            if window:
                ax.set_xlim(window[0], window[1])
                ax.set_ylim(window[2], window[3])
            ax.set_aspect("equal")
            ax.set_title(f"{stem}{suffix} — rosso: candidati, blu: punti colpiti, ciano: ground truth")
            out = os.path.abspath(os.path.join(OUTDIR, f"{stem}{suffix}.png"))
            fig.savefig(out, dpi=150, bbox_inches="tight")
            plt.close(fig)
            print(f"  -> {out}")


if __name__ == "__main__":
    main()
