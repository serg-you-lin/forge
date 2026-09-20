# tests/unit/core/test_normalizer.py

import unittest
from forge.core.healing.normalizer import merge_collinear_overlaps
from forge.core.topology.edge import Edge
from forge.core.primitives.segments import LineSeg


def _line(p1, p2, role="unknown", closed_path=False):
    return Edge(role=role, start=p1, end=p2, segment=LineSeg(start=p1, end=p2), closed_path=closed_path)


class TestMergeCollinearOverlaps(unittest.TestCase):

    def test_catena_di_tre_si_fonde(self):
        # A-B si sovrappongono, B-C si sovrappongono, A-C no direttamente —
        # deve fondersi comunque in un solo segmento (0,0)-(30,0).
        edges = [
            _line((0.0, 0.0), (10.0, 0.0)),
            _line((8.0, 0.0), (20.0, 0.0)),
            _line((18.0, 0.0), (30.0, 0.0)),
        ]
        out = merge_collinear_overlaps(edges)
        self.assertEqual(len(out), 1)
        self.assertEqual((out[0].segment.start, out[0].segment.end), ((0.0, 0.0), (30.0, 0.0)))

    def test_catena_di_due_non_si_fonde(self):
        # Due soli tratti sovrapposti sono una coincidenza plausibile
        # (lettere/marcature) — non abbastanza per fidarsi (v. golden
        # PROFILE_PART, dove una coppia così erano due caratteri diversi).
        edges = [
            _line((0.0, 0.0), (10.0, 0.0)),
            _line((5.0, 0.0), (15.0, 0.0)),
        ]
        out = merge_collinear_overlaps(edges)
        self.assertEqual(len(out), 2)

    def test_contatto_punta_coda_non_e_sovrapposizione(self):
        # Tre segmenti che si toccano esattamente in successione (nessuna
        # sovrapposizione di lunghezza positiva) sono la geometria normale
        # di lati consecutivi — non vanno fusi (v. golden
        # fa_che_non_mi_incazzi, dove un intaglio reale spariva così).
        edges = [
            _line((0.0, 0.0), (10.0, 0.0)),
            _line((10.0, 0.0), (20.0, 0.0)),
            _line((20.0, 0.0), (30.0, 0.0)),
        ]
        out = merge_collinear_overlaps(edges)
        self.assertEqual(len(out), 3)

    def test_rette_parallele_non_si_fondono(self):
        # Stessa direzione, offset diverso: NON è la stessa retta.
        edges = [
            _line((0.0, 0.0), (10.0, 0.0)),
            _line((3.0, 0.0), (13.0, 0.0)),
            _line((6.0, 0.0), (16.0, 0.0)),
            _line((0.0, 5.0), (10.0, 5.0)),
            _line((3.0, 5.0), (13.0, 5.0)),
            _line((6.0, 5.0), (16.0, 5.0)),
        ]
        out = merge_collinear_overlaps(edges)
        self.assertEqual(len(out), 2)

    def test_ruolo_gia_assegnato_non_e_candidato(self):
        # Un ruolo diverso da UNKNOWN (assegnato da label_map) non entra mai
        # nel graph-building: fonderlo non aiuta e può alterare geometria di
        # dominio intenzionale (v. golden la_104: tratti di un'incisione che
        # si sovrappongono per disegno, non per errore).
        edges = [
            _line((0.0, 0.0), (10.0, 0.0), role="engrave"),
            _line((5.0, 0.0), (15.0, 0.0), role="engrave"),
            _line((8.0, 0.0), (20.0, 0.0), role="engrave"),
        ]
        out = merge_collinear_overlaps(edges)
        self.assertEqual(len(out), 3)

    def test_closed_path_non_e_candidato(self):
        edges = [
            _line((0.0, 0.0), (10.0, 0.0), closed_path=True),
            _line((5.0, 0.0), (15.0, 0.0), closed_path=True),
            _line((8.0, 0.0), (20.0, 0.0), closed_path=True),
        ]
        out = merge_collinear_overlaps(edges)
        self.assertEqual(len(out), 3)

    def test_ordine_preservato_per_tutto_il_resto(self):
        # Un pre-pass di pulizia non deve riordinare edge che non tocca —
        # anche a zero fusioni (v. golden PROFILE_PART: il solo riordino,
        # senza nessuna fusione, cambiava il risultato del loop-finder).
        others = [_line((i * 100.0, 0.0), (i * 100.0 + 1.0, 0.0)) for i in range(5)]
        chain = [
            _line((0.0, 50.0), (10.0, 50.0)),
            _line((8.0, 50.0), (20.0, 50.0)),
            _line((18.0, 50.0), (30.0, 50.0)),
        ]
        edges = [others[0], others[1], chain[0], others[2], chain[1], others[3], chain[2], others[4]]
        out = merge_collinear_overlaps(edges)

        self.assertEqual(len(out), 6)  # 5 "others" + 1 fuso
        # Il fuso occupa la posizione del primo membro della catena in ordine
        # di input (indice 2 in `edges`), il resto non si è mosso.
        self.assertIs(out[0], others[0])
        self.assertIs(out[1], others[1])
        self.assertEqual((out[2].segment.start, out[2].segment.end), ((0.0, 50.0), (30.0, 50.0)))
        self.assertIs(out[3], others[2])
        self.assertIs(out[4], others[3])
        self.assertIs(out[5], others[4])

    def test_lista_vuota(self):
        self.assertEqual(merge_collinear_overlaps([]), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
