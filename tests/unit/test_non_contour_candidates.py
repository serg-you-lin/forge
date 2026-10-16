# tests/unit/test_non_contour_candidates.py

import unittest

import forge
from forge.model.document import ForgeDocument
from forge.core.topology.edge import Edge
from forge.core.primitives.segments import LineSeg


def _make_edge(p1, p2):
    # Ruolo irrilevante per il criterio (solo topologia: branching + faccia esterna) —
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

    def test_lato_concavo_fra_due_pieghe_non_e_candidato(self):
        # una U: le due pieghe vanno da (0,10)/(30,10) ai vertici del fondo
        # della tacca, (10,10)/(20,10); il fondo (10,10)-(20,10) sta dentro il
        # convex hull ma confina con l'esterno: è contorno (D111)
        u = [_make_edge(a, b) for a, b in [
            ((0.0, 0.0), (30.0, 0.0)), ((30.0, 0.0), (30.0, 20.0)), ((30.0, 20.0), (20.0, 20.0)),
            ((20.0, 20.0), (20.0, 10.0)), ((20.0, 10.0), (10.0, 10.0)), ((10.0, 10.0), (10.0, 20.0)),
            ((10.0, 20.0), (0.0, 20.0)), ((0.0, 20.0), (0.0, 0.0))]]
        bends = [_make_edge((0.0, 0.0), (10.0, 10.0)), _make_edge((30.0, 0.0), (20.0, 10.0))]
        doc = ForgeDocument(edges=u + bends)

        self.assertEqual({id(e) for e in forge.non_contour_candidates(doc)}, {id(e) for e in bends})

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
