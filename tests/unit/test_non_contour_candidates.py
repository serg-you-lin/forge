# tests/unit/test_non_contour_candidates.py

import unittest

import forge
from forge.model.document import ForgeDocument
from forge.core.topology.edge import Edge
from forge.core.primitives.segments import LineSeg


def _make_edge(p1, p2):
    # Ruolo irrilevante per il criterio (solo geometria: branching + hull) —
    # stesso pattern di tests/unit/core/test_non_contour_edges.py.
    return Edge(role="unknown", start=p1, end=p2, segment=LineSeg(start=p1, end=p2))


class TestNonContourCandidates(unittest.TestCase):

    def test_diagonale_interna_e_candidata(self):
        # rettangolo con diagonale interna — stesso schema di
        # test_non_contour_edges.test_linea_interna_confermata, ma passando
        # per l'API pubblica su un ForgeDocument.
        rect = [
            _make_edge((0.0, 0.0), (1.0, 0.0)),
            _make_edge((1.0, 0.0), (1.0, 2.0)),
            _make_edge((1.0, 2.0), (0.0, 2.0)),
            _make_edge((0.0, 2.0), (0.0, 0.0)),
        ]
        diagonal = _make_edge((0.0, 0.0), (1.0, 2.0))
        doc = ForgeDocument(edges=rect + [diagonal], source_meta={"tolerance": 0.01})

        candidates = forge.non_contour_candidates(doc)

        self.assertEqual([id(e) for e in candidates], [id(diagonal)])

    def test_contorno_semplice_nessun_candidato(self):
        # triangolo — nessun nodo branching, niente da segnalare
        tri = [
            _make_edge((0.0, 0.0), (1.0, 0.0)),
            _make_edge((1.0, 0.0), (0.5, 1.0)),
            _make_edge((0.5, 1.0), (0.0, 0.0)),
        ]
        doc = ForgeDocument(edges=tri, source_meta={"tolerance": 0.01})

        self.assertEqual(forge.non_contour_candidates(doc), [])

    def test_tolerance_esplicita_sovrascrive_source_meta(self):
        rect = [
            _make_edge((0.0, 0.0), (1.0, 0.0)),
            _make_edge((1.0, 0.0), (1.0, 2.0)),
            _make_edge((1.0, 2.0), (0.0, 2.0)),
            _make_edge((0.0, 2.0), (0.0, 0.0)),
        ]
        diagonal = _make_edge((0.0, 0.0), (1.0, 2.0))
        # source_meta assente del tutto: deve cadere sul default (0.05), non
        # esplodere.
        doc = ForgeDocument(edges=rect + [diagonal])

        candidates = forge.non_contour_candidates(doc, tolerance=0.01)

        self.assertEqual([id(e) for e in candidates], [id(diagonal)])

    def test_edge_restituiti_sono_mutabili_in_place(self):
        # Il punto della funzione: il chiamante deve poter settare .role sugli
        # oggetti restituiti e vederlo riflesso su doc.edges, per passarli a
        # heal() già etichettati (SNAPDRAW.md).
        rect = [
            _make_edge((0.0, 0.0), (1.0, 0.0)),
            _make_edge((1.0, 0.0), (1.0, 2.0)),
            _make_edge((1.0, 2.0), (0.0, 2.0)),
            _make_edge((0.0, 2.0), (0.0, 0.0)),
        ]
        diagonal = _make_edge((0.0, 0.0), (1.0, 2.0))
        doc = ForgeDocument(edges=rect + [diagonal], source_meta={"tolerance": 0.01})

        for edge in forge.non_contour_candidates(doc):
            edge.role = forge.normalize_role("flange_up")

        self.assertEqual(diagonal.role, "flange_up")


if __name__ == "__main__":
    unittest.main(verbosity=2)
