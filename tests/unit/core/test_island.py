# tests/unit/core/test_island.py

import math
import unittest
import forge
from forge.model.document import ForgeDocument
from forge.model.role import ContourRole
from forge.core.topology.edge import Edge
from forge.core.primitives.segments import LineSeg, CircleSeg
from forge.core.healing.normalizer import refit_tessellations
from forge.core.healing.gap_solver import local_gap_fixes, MoveEndpoint, AddSegment
from forge.core.primitives.segments import ArcSeg


def _line(p1, p2):
    return Edge(role="unknown", start=p1, end=p2, segment=LineSeg(start=p1, end=p2))


def _poly(*pts):
    return [_line(pts[i], pts[(i + 1) % len(pts)]) for i in range(len(pts))]


def _circle(center, radius):
    pt = (center[0] + radius, center[1])
    return Edge(role="unknown", start=pt, end=pt, segment=CircleSeg(center=center, radius=radius))


def _doc(edges):
    return ForgeDocument(edges=edges, annotations=[], source_meta={"tolerance": 0.05}, source_path="")


class TestIsland(unittest.TestCase):

    def test_due_viste_separate_due_cluster(self):
        edges = _poly((0, 0), (10, 0), (10, 10), (0, 10)) + _poly((50, 0), (60, 0), (60, 5), (50, 5))
        result = forge.island(_doc(edges))
        self.assertEqual(len(result.clusters), 2)
        self.assertEqual([round(c.outer.polygon.area) for c in result.clusters], [100, 50])

    def test_isola_dentro_un_altra_non_e_un_cluster(self):
        # cornice 100x100 e una vista dentro: l'unico contorno esterno è la cornice
        edges = _poly((0, 0), (100, 0), (100, 100), (0, 100)) + _poly((40, 40), (60, 40), (60, 60), (40, 60))
        result = forge.island(_doc(edges))
        self.assertEqual(len(result.clusters), 1)
        self.assertAlmostEqual(result.clusters[0].outer.polygon.area, 10000.0)
        self.assertEqual(len(result.clusters[0].inners), 1)

    def test_gruppo_di_fori_staccati_dentro_una_vista_tutti_interni(self):
        # D71: tre fori vicini fra loro (< island_gap) ma lontani dal bordo (> island_gap):
        # sono un'isola a sé fatta di cerchi disgiunti; dentro la vista diventano tutti interni
        edges = _poly((0, 0), (200, 0), (200, 100), (0, 100)) + [
            _circle((90, 50), 3), _circle((100, 50), 5.5), _circle((110, 50), 3)]
        result = forge.island(_doc(edges))
        self.assertEqual(len(result.clusters), 1)
        self.assertEqual(sorted(round(i.polygon.area) for i in result.clusters[0].inners),
                         sorted(round(math.pi * r * r) for r in (3, 5.5, 3)))
        self.assertEqual(result.trash_entities, [])

    def test_foro_resta_giro_interno(self):
        edges = _poly((0, 0), (20, 0), (20, 20), (0, 20)) + [_circle((10, 10), 3)]
        cluster = forge.island(_doc(edges)).clusters[0]
        self.assertEqual(cluster.outer.role, ContourRole.OUTER)
        self.assertEqual(len(cluster.inners), 1)
        self.assertAlmostEqual(cluster.inners[0].polygon.area, math.pi * 9, delta=0.5)

    def test_foro_tagliato_dagli_assi_torna_cerchio(self):
        # gli assi spezzano il cerchio in 4 archi nella rete piana: il giro
        # interno li ricompone, e detect lo vede come foro
        edges = _poly((0, 0), (20, 0), (20, 20), (0, 20)) + [_circle((10, 10), 3)]
        edges += [_line((5, 10), (15, 10)), _line((10, 5), (10, 15))]
        result = forge.island(_doc(edges))
        inner = result.clusters[0].inners[0]
        self.assertEqual([type(s).__name__ for s in inner.segments], ["CircleSeg"])
        self.assertEqual(len(forge.detect_flat(result, "holes").clusters[0].features("holes")), 1)

    def test_lato_tagliato_da_un_asse_torna_un_segmento(self):
        # un asse che esce dal contorno lo spezza: il contorno esterno resta di 4 lati
        edges = _poly((0, 0), (20, 0), (20, 20), (0, 20)) + [_line((10, -5), (10, 25))]
        outer = forge.island(_doc(edges)).clusters[0].outer
        self.assertEqual(len(outer.segments), 4)

    def test_cornice_marcata_resta_fuori(self):
        # D30: snapdraw marca la cornice → island() non la legge, resta in trash col suo ruolo
        frame = _poly((0, 0), (100, 0), (100, 100), (0, 100))
        for e in frame:
            e.role = "frame"
        view = _poly((40, 40), (60, 40), (60, 60), (40, 60))
        result = forge.island(_doc(frame + view))
        self.assertEqual(len(result.clusters), 1)
        self.assertAlmostEqual(result.clusters[0].outer.polygon.area, 400.0)
        self.assertEqual(sum(1 for t in result.trash_entities if t.role == "frame"), 4)

    def test_niente_di_chiuso_invalido(self):
        result = forge.island(_doc([_line((0, 0), (5, 0))]))
        self.assertFalse(result.is_valid)

    def test_richiede_un_documento(self):
        with self.assertRaises(TypeError):
            forge.island([_line((0, 0), (1, 0))])


class TestRefitTessellations(unittest.TestCase):

    def _tessellated_arc(self, n=40):
        pts = [(10 * math.cos(math.pi * i / (2 * n)), 10 * math.sin(math.pi * i / (2 * n))) for i in range(n + 1)]
        return [_line(pts[i], pts[i + 1]) for i in range(n)]

    def test_catena_corta_diventa_un_arco(self):
        # 40 segmenti da ~0.39mm: sotto max_segment=0.5 → un arco r=10
        out = refit_tessellations(self._tessellated_arc(), max_segment=0.5)
        self.assertEqual(len(out), 1)
        self.assertIsInstance(out[0].segment, ArcSeg)
        self.assertAlmostEqual(out[0].segment.radius, 10.0, places=3)

    def test_estremi_tengono_i_nodi(self):
        chain = self._tessellated_arc()
        out = refit_tessellations(chain, max_segment=0.5)
        self.assertEqual(out[0].start, chain[0].start)
        self.assertEqual(out[0].end, chain[-1].end)

    def test_catena_troppo_corta_non_si_tocca(self):
        chain = self._tessellated_arc(n=5)
        self.assertEqual(refit_tessellations(chain, max_segment=5.0), chain)


class TestLocalGapFixes(unittest.TestCase):

    def test_spostamento_lontano_scartato(self):
        e = _line((0, 0), (10, 0))
        near = MoveEndpoint(ref=e, role="end", new_pt=(10.3, 0.0))
        far = MoveEndpoint(ref=e, role="end", new_pt=(500.0, 0.0))
        add = AddSegment(pt_a=(0, 0), pt_b=(0, 0.3))
        self.assertEqual(local_gap_fixes([near, far, add], max_move=0.5), [near, add])


if __name__ == "__main__":
    unittest.main(verbosity=2)
