"""
test_role.py
------------
Test unitari per forge.model.role: il vocabolario ruoli aperto (MAP.md D27).

Copre:
  - normalize_role : ruolo noto → costante, ignoto → slug conservato,
                     input sporco → slug sicuro (niente payload di injection)
  - role_str       : valore stringa che il ruolo sia enum o str
  - layer_to_role  : un work_type sconosciuto nel label_map non viene
                     schiacciato a UNKNOWN
  - integrazione   : un ruolo custom sopravvive a load_geometry → heal
"""

import unittest

import forge
from forge.model.role import (
    ContourRole, normalize_role, role_str, layer_to_role,
    is_structural_role, STRUCTURAL_ROLES,
)


class TestNormalizeRole(unittest.TestCase):

    def test_ruolo_noto_diventa_costante(self):
        # Solo outer/inner sono vocabolario del motore ora (roles out of
        # core) — normalize_role() li promuove a ContourRole.
        self.assertIs(normalize_role("outer"), ContourRole.OUTER)
        self.assertIs(normalize_role("  INNER "), ContourRole.INNER)

    def test_ruolo_manifatturiero_e_uno_slug_qualunque_qui(self):
        # "hole"/"bending" non sono più costanti di model.role: sono
        # vocabolario di tools.manufacturing_role, a fianco di detect().
        # Qui passano come uno slug qualunque, non come un ContourRole.
        self.assertEqual(normalize_role("hole"), "hole")
        self.assertNotIsInstance(normalize_role("hole"), ContourRole)

    def test_ruolo_ignoto_conservato_come_slug(self):
        self.assertEqual(normalize_role("title_block"), "title_block")
        self.assertEqual(normalize_role("Nesting Region"), "nesting_region")

    def test_input_sporco_neutralizzato(self):
        # caratteri fuori da [a-z0-9_-] collassati: niente injection nei sink
        self.assertEqual(normalize_role("</cluster><x>"), "cluster_x")
        self.assertEqual(normalize_role("a\nb\tc"), "a_b_c")

    def test_troncatura_a_64(self):
        self.assertEqual(len(normalize_role("x" * 200)), 64)

    def test_vuoto_o_non_stringa_diventa_unknown(self):
        self.assertEqual(normalize_role(""), "unknown")
        self.assertEqual(normalize_role("   "), "unknown")
        self.assertEqual(normalize_role(None), "unknown")
        self.assertEqual(normalize_role(123), "unknown")


class TestRoleStr(unittest.TestCase):

    def test_da_enum_e_da_stringa(self):
        self.assertEqual(role_str(ContourRole.OUTER), "outer")
        self.assertEqual(role_str("title_block"), "title_block")


class TestLayerToRole(unittest.TestCase):

    def test_work_type_ignoto_non_schiacciato(self):
        self.assertEqual(layer_to_role("Cartiglio", {"cartiglio": "title_block"}),
                         "title_block")

    def test_layer_non_mappato_e_unknown(self):
        self.assertEqual(layer_to_role("Boh", {"altro": "outer"}), "unknown")


class TestIsStructuralRole(unittest.TestCase):
    """
    Predicato minimo del motore (MAP.md D30, ristretto da "roles out of
    core"): solo outer/inner. Il predicato ESTESO (+ hole/countersink/
    threaded_hole) è `tools.manufacturing_role.is_structural`, testato in
    TestManufacturingIsStructural sotto — non qui, non è vocabolario di
    model.role.
    """

    def test_ruoli_di_contorno(self):
        for r in (ContourRole.OUTER, ContourRole.INNER):
            self.assertTrue(is_structural_role(r))

    def test_marcatura_e_arredo_non_sono_strutturali(self):
        for r in ("engrave", "marking", "bending", "hole", ContourRole.UNKNOWN):
            self.assertFalse(is_structural_role(r))

    def test_slug_di_un_consumatore_non_e_strutturale(self):
        # `frame` non è più una costante di forge (D31): è uno slug come gli altri
        self.assertFalse(is_structural_role("frame"))
        self.assertFalse(is_structural_role("title_block"))
        self.assertFalse(is_structural_role("section"))

    def test_accetta_lo_slug_stringa_equivalente(self):
        # ContourRole eredita da str: "outer" == ContourRole.OUTER
        self.assertTrue(is_structural_role("outer"))
        self.assertIn(ContourRole.INNER, STRUCTURAL_ROLES)


class TestManufacturingIsStructural(unittest.TestCase):
    """
    Predicato ESTESO — outer/inner (motore) + hole/countersink/threaded_hole
    (manifatturiero) — quello che `heal_and_detect()` inietta in
    `heal(is_structural=...)`. Vive a fianco di detect(), non nel motore.
    """

    def test_ruoli_manifatturieri_strutturali(self):
        from forge.tools.manufacturing_role import is_structural
        for r in ("outer", "inner", "hole", "countersink", "threaded_hole"):
            self.assertTrue(is_structural(r))

    def test_marcatura_e_arredo_restano_non_strutturali(self):
        from forge.tools.manufacturing_role import is_structural
        for r in ("bending", "engrave", "marking", "frame", "unknown"):
            self.assertFalse(is_structural(r))


class TestCustomRoleSurvivesHeal(unittest.TestCase):

    def test_ruolo_custom_conservato_non_schiacciato_a_unknown(self):
        # un quadrato "outer" con dentro un quadratino marcato con un ruolo
        # che forge non conosce: heal lo tiene come geometria non strutturale
        # (trash), ma il ruolo resta quello del chiamante, non "unknown"
        doc = forge.load_geometry([
            {"type": "polyline", "closed": True, "role": "outer",
             "points": [(0, 0), (100, 0), (100, 100), (0, 100)]},
            {"type": "polyline", "closed": True, "role": "title_block",
             "points": [(10, 10), (40, 10), (40, 30), (10, 30)]},
        ])
        result = forge.heal(doc)

        all_roles = {result.clusters[0].outer.role}
        all_roles.update(i.role for i in result.clusters[0].inners)
        all_roles.update(role_str(getattr(t, "role", "")) for t in result.trash_entities)

        self.assertIn("title_block", all_roles)
        self.assertEqual(result.clusters[0].outer.role, ContourRole.OUTER)


class TestConsumerRolesSurviveDetect(unittest.TestCase):
    """
    D30: un ruolo che forge non classifica (cornice, cartiglio, slug di un
    consumatore) sopravvive TUTTA la pipeline — load → heal → detect — con
    geometria e ruolo intatti. Prima detect() ne faceva un ClassifiedEntity
    scollegato che l'exporter non riscriveva → geometria persa.
    """

    def _framed_doc(self):
        # cornice grande + due pezzi dentro, tutti geometricamente distinti
        return forge.load_geometry([
            {"type": "polyline", "closed": True, "role": "frame",
             "points": [(0, 0), (400, 0), (400, 300), (0, 300)]},
            {"type": "polyline", "closed": True, "role": "outer",
             "points": [(20, 20), (120, 20), (120, 120), (20, 120)]},
            {"type": "polyline", "closed": True, "role": "outer",
             "points": [(200, 20), (300, 20), (300, 120), (200, 120)]},
        ])

    def test_la_cornice_non_e_un_cluster_ne_mangia_i_pezzi(self):
        result = forge.heal(self._framed_doc())
        self.assertEqual(len(result.clusters), 2)
        for c in result.clusters:
            self.assertEqual(c.outer.role, ContourRole.OUTER)
            self.assertLess(c.outer.polygon.area, 20000)  # non è la cornice

    def test_detect_non_sposta_il_ruolo_custom_fuori_dalla_trash(self):
        result = forge.heal(self._framed_doc())
        trash_prima = len(result.trash_entities)
        frame_prima = sum(1 for t in result.trash_entities
                          if role_str(getattr(t, "role", "")) == "frame")
        self.assertGreater(frame_prima, 0)

        forge.detect(result, features="all")

        frame_dopo = sum(1 for t in result.trash_entities
                         if role_str(getattr(t, "role", "")) == "frame")
        self.assertEqual(frame_dopo, frame_prima)
        self.assertEqual(len(result.trash_entities), trash_prima)
        # niente ClassifiedEntity scollegato, niente warning "non contenuta"
        self.assertEqual(result.classified_entities, [])
        self.assertFalse([w for w in result.warnings if "non contenuta" in w])

    def test_to_dxf_scrive_il_ruolo_di_consumatore_su_un_layer_suo(self):
        # D31: la cornice non finisce su "Trash" insieme alla spazzatura vera,
        # ma su un layer "frame" col suo colore. forge non sa cosa sia — porta
        # fedele lo slug che il consumatore ha assegnato.
        doc = self._framed_doc()
        result = forge.heal(doc)
        out = forge.to_dxf(result, doc)

        layers = {e.dxf.layer for e in out.modelspace()}
        self.assertIn("frame", layers)

        frame_ents = [e for e in out.modelspace() if e.dxf.layer == "frame"]
        self.assertTrue(frame_ents)
        self.assertIn("frame", out.layers)


if __name__ == "__main__":
    unittest.main()
