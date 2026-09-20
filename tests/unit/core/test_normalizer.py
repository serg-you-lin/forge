# tests/unit/core/test_normalizer.py

import math
import unittest
from forge.core.healing.normalizer import merge_collinear_overlaps, merge_cocircular_overlaps
from forge.core.topology.edge import Edge
from forge.core.primitives.segments import LineSeg, ArcSeg, CircleSeg


def _line(p1, p2, role="unknown"):
    return Edge(role=role, start=p1, end=p2, segment=LineSeg(start=p1, end=p2))


def _arc(center, radius, start_deg, end_deg, role="unknown"):
    seg = ArcSeg(center=center, radius=radius,
                 start_angle=math.radians(start_deg), end_angle=math.radians(end_deg), ccw=True)
    start = (center[0] + radius * math.cos(seg.start_angle), center[1] + radius * math.sin(seg.start_angle))
    end = (center[0] + radius * math.cos(seg.end_angle), center[1] + radius * math.sin(seg.end_angle))
    return Edge(role=role, start=(round(start[0], 3), round(start[1], 3)),
                end=(round(end[0], 3), round(end[1], 3)), segment=seg)


def _line_raw(rounded_p1, rounded_p2, raw_p1, raw_p2, role="unknown"):
    # Come l'adapter reale: Edge.start/end sono il punto ARROTONDATO
    # (identità del nodo nel grafo), il LineSeg del segmento porta la
    # coordinata a piena precisione della sorgente — le due possono differire
    # di una frazione di mm su coordinate non tonde (v. MAP.md D50 seguito).
    return Edge(role=role, start=rounded_p1, end=rounded_p2, segment=LineSeg(start=raw_p1, end=raw_p2))


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

    def test_catena_di_due_si_fonde(self):
        # Due soli tratti che si sovrappongono: l'unione di due intervalli
        # 1D e' sempre ben definita (qui: (0,15)), non c'e' modo di
        # "sbagliare" fondendo solo 2 pezzi collineari — v. il seguito del
        # commit per la storia della soglia minima che c'era qui prima.
        edges = [
            _line((0.0, 0.0), (10.0, 0.0)),
            _line((5.0, 0.0), (15.0, 0.0)),
        ]
        out = merge_collinear_overlaps(edges)
        self.assertEqual(len(out), 1)
        self.assertEqual((out[0].segment.start, out[0].segment.end), ((0.0, 0.0), (15.0, 0.0)))

    def test_un_tratto_contenuto_nell_altro_si_fonde_nel_piu_lungo(self):
        # Caso reale (golden la_104): un tratto corto (15.68-21.36) e uno
        # lungo (10.0-21.36) sulla stessa retta, il corto interamente dentro
        # il lungo — due caratteri di un'incisione allineati per coincidenza,
        # non un errore di disegno. L'unione e' comunque solo il piu' lungo:
        # fonderli non fabbrica ne' perde geometria.
        edges = [
            _line((73.297, 15.68), (73.297, 21.36)),
            _line((73.297, 21.36), (73.297, 10.0)),
        ]
        out = merge_collinear_overlaps(edges)
        self.assertEqual(len(out), 1)
        self.assertEqual({out[0].segment.start, out[0].segment.end}, {(73.297, 10.0), (73.297, 21.36)})

    def test_contatto_punta_coda_si_fonde(self):
        # Tre segmenti che si toccano esattamente in successione (nessuna
        # sovrapposizione, solo continuita') sono la stessa riga tracciata a
        # pezzi quanto una sovrapposizione vera — l'unione e' comunque ben
        # definita, (0,0)-(30,0).
        edges = [
            _line((0.0, 0.0), (10.0, 0.0)),
            _line((10.0, 0.0), (20.0, 0.0)),
            _line((20.0, 0.0), (30.0, 0.0)),
        ]
        out = merge_collinear_overlaps(edges)
        self.assertEqual(len(out), 1)
        self.assertEqual((out[0].segment.start, out[0].segment.end), ((0.0, 0.0), (30.0, 0.0)))

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

    def test_estremi_fusi_usano_il_punto_arrotondato_non_quello_grezzo(self):
        # Su coordinate non tonde edge.start/end (arrotondati, identita' del
        # nodo nel grafo) e segment.start/end (piena precisione) differiscono
        # di una frazione di mm — il fuso deve riprendere quelli arrotondati,
        # altrimenti non si aggancia più al vicino reale (bug trovato su
        # fa_che_non_mi_incazzi.dxf: un pezzo vero spariva del tutto).
        edges = [
            _line_raw((0.0, 0.0), (10.0, 0.0), (0.0000003, 0.0), (10.0000003, 0.0)),
            _line_raw((8.0, 0.0), (20.0, 0.0), (8.0000003, 0.0), (20.0000003, 0.0)),
            _line_raw((18.0, 0.0), (30.0, 0.0), (18.0000003, 0.0), (30.0000003, 0.0)),
        ]
        out = merge_collinear_overlaps(edges)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].start, (0.0, 0.0))
        self.assertEqual(out[0].end, (30.0, 0.0))
        self.assertEqual(out[0].segment.start, (0.0, 0.0))
        self.assertEqual(out[0].segment.end, (30.0, 0.0))


class TestMergeCocircularOverlaps(unittest.TestCase):

    def test_catena_di_frammenti_si_fonde(self):
        # golden piega_cazzuta: un arco tracciato a 4 spezzoni consecutivi
        # che si toccano esattamente -> un solo ArcSeg da 0 a 200 gradi.
        edges = [
            _arc((0.0, 0.0), 10.0, 0.0, 50.0),
            _arc((0.0, 0.0), 10.0, 50.0, 120.0),
            _arc((0.0, 0.0), 10.0, 120.0, 160.0),
            _arc((0.0, 0.0), 10.0, 160.0, 200.0),
        ]
        out = merge_cocircular_overlaps(edges)
        self.assertEqual(len(out), 1)
        seg = out[0].segment
        self.assertAlmostEqual(math.degrees(seg.start_angle), 0.0)
        self.assertAlmostEqual(math.degrees(seg.end_angle), 200.0)
        self.assertNotEqual(out[0].start, out[0].end)

    def test_sliver_degenere_assorbito(self):
        # golden piega_cazzuta: uno spezzone di 0.008 gradi (rumore) in mezzo
        # alla catena sparisce nel fuso invece di restare un nodo spurio.
        edges = [
            _arc((0.0, 0.0), 10.0, 0.0, 50.0),
            _arc((0.0, 0.0), 10.0, 50.0, 50.008),
            _arc((0.0, 0.0), 10.0, 50.008, 120.0),
        ]
        out = merge_cocircular_overlaps(edges)
        self.assertEqual(len(out), 1)

    def test_due_semicerchi_chiudono_il_cerchio(self):
        # golden cerchi_ciambella: un foro disegnato come 2 semicirchi ->
        # un giro intero e' un cerchio (CircleSeg), non un ArcSeg a 360 gradi
        # -- niente traccia di quale frammento fosse il primo.
        edges = [
            _arc((0.0, 0.0), 10.0, 0.0, 180.0),
            _arc((0.0, 0.0), 10.0, 180.0, 360.0),
        ]
        out = merge_cocircular_overlaps(edges)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].start, out[0].end)
        self.assertIsInstance(out[0].segment, CircleSeg)
        self.assertEqual(out[0].segment.radius, 10.0)

    def test_gap_vero_non_si_chiude_per_errore(self):
        # arc_arc_gap: un gap reale (qui volutamente grande, 10 gradi) su un
        # lato non deve sparire solo perché l'altro lato tocca esattamente.
        edges = [
            _arc((0.0, 0.0), 10.0, 0.0, 170.0),
            _arc((0.0, 0.0), 10.0, 180.0, 360.0),
        ]
        out = merge_cocircular_overlaps(edges)
        self.assertEqual(len(out), 1)
        seg = out[0].segment
        self.assertAlmostEqual(math.degrees(seg._sweep()), 350.0)
        self.assertNotEqual(out[0].start, out[0].end)

    def test_ruolo_gia_assegnato_non_e_candidato(self):
        edges = [
            _arc((0.0, 0.0), 10.0, 0.0, 50.0, role="engrave"),
            _arc((0.0, 0.0), 10.0, 50.0, 120.0, role="engrave"),
        ]
        out = merge_cocircular_overlaps(edges)
        self.assertEqual(len(out), 2)

    def test_cerchi_diversi_non_si_fondono(self):
        edges = [
            _arc((0.0, 0.0), 10.0, 0.0, 50.0),
            _arc((0.0, 0.0), 20.0, 0.0, 50.0),
        ]
        out = merge_cocircular_overlaps(edges)
        self.assertEqual(len(out), 2)

    def test_ordine_preservato(self):
        others = [_line((i * 100.0, 0.0), (i * 100.0 + 1.0, 0.0)) for i in range(3)]
        chain = [
            _arc((0.0, 0.0), 10.0, 0.0, 50.0),
            _arc((0.0, 0.0), 10.0, 50.0, 120.0),
        ]
        edges = [others[0], chain[0], others[1], chain[1], others[2]]
        out = merge_cocircular_overlaps(edges)

        self.assertEqual(len(out), 4)  # 3 "others" + 1 fuso
        self.assertIs(out[0], others[0])
        seg = out[1].segment
        self.assertAlmostEqual(math.degrees(seg.end_angle), 120.0)
        self.assertIs(out[2], others[1])
        self.assertIs(out[3], others[2])

    def test_lista_vuota(self):
        self.assertEqual(merge_cocircular_overlaps([]), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
