"""
test_role_rule.py
-----------------
Test unitari per forge.model.role_rule: le regole con cui il chiamante
assegna un ruolo al load (MAP.md D63), valutate su segnali neutri — nome del
gruppo sorgente e EdgeStyle — senza nessun formato di mezzo.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import forge
from forge.model.role_rule import resolve_role
from forge.model.style import EdgeStyle

CONTINUA    = EdgeStyle()
TRATTEGGIATA = EdgeStyle(linetype="DASHED", linetype_pattern=(0.75, 0.5, -0.25))
PUNTINATA   = EdgeStyle(linetype="DOT", linetype_pattern=(4.0, 0.0, -4.0))
CIANO       = EdgeStyle(color=4)


class TestIsDashed(unittest.TestCase):

    def test_pattern_con_vuoti_e_tratteggiato(self):
        self.assertTrue(TRATTEGGIATA.is_dashed)
        self.assertTrue(PUNTINATA.is_dashed)

    def test_senza_pattern_o_senza_vuoti_e_continua(self):
        self.assertFalse(CONTINUA.is_dashed)
        self.assertFalse(EdgeStyle(linetype_pattern=(1.0, 1.0, 0.0)).is_dashed)

    def test_conta_il_pattern_non_il_nome(self):
        # D63: "tratteggiata" è un fatto del pattern; il nome non dice nulla
        self.assertFalse(EdgeStyle(linetype="DASHED").is_dashed)
        self.assertTrue(EdgeStyle(linetype="Qualunque",
                                  linetype_pattern=(2.0, 1.0, -1.0)).is_dashed)


class TestRoleRule(unittest.TestCase):

    def test_nome_ignora_le_maiuscole(self):
        rule = forge.RoleRule("bending", name="Piega")
        self.assertTrue(rule.matches("PIEGA", CONTINUA))
        self.assertFalse(rule.matches("Pieghe", CONTINUA))

    def test_nome_contiene(self):
        rule = forge.RoleRule("construction", name_contains="constr")
        self.assertTrue(rule.matches("Construction_lines", CONTINUA))
        self.assertFalse(rule.matches("Taglio", CONTINUA))

    def test_condizioni_tutte_vere_insieme(self):
        # il caso del framer: tratteggiata E nome "construction"
        rule = forge.RoleRule("construction", name_contains="construction", dashed=True)
        self.assertTrue(rule.matches("construction", TRATTEGGIATA))
        self.assertFalse(rule.matches("construction", CONTINUA))
        self.assertFalse(rule.matches("0", TRATTEGGIATA))

    def test_solo_continue(self):
        rule = forge.RoleRule("outer", dashed=False)
        self.assertTrue(rule.matches("", CONTINUA))
        self.assertFalse(rule.matches("", TRATTEGGIATA))

    def test_colore_per_nome_intero_o_stringa(self):
        for key in ("cyan", 4, "4"):
            self.assertTrue(forge.RoleRule("engrave", color=key).matches("", CIANO), msg=repr(key))
        self.assertFalse(forge.RoleRule("engrave", color="red").matches("", CIANO))

    def test_colore_sconosciuto_solleva(self):
        with self.assertRaises(ValueError):
            forge.RoleRule("engrave", color="viola")

    def test_regola_senza_condizioni_solleva(self):
        with self.assertRaises(ValueError):
            forge.RoleRule("bending")

    def test_ruolo_ripulito(self):
        self.assertEqual(forge.RoleRule("Title Block", name="x").role, "title_block")


class TestResolveRole(unittest.TestCase):

    def test_vince_la_prima_in_ordine(self):
        rules = [
            forge.RoleRule("bending", name="piega"),
            forge.RoleRule("engrave", color="cyan"),
        ]
        self.assertEqual(resolve_role(rules, "Piega", CIANO), "bending")
        self.assertEqual(resolve_role(rules[::-1], "Piega", CIANO), "engrave")

    def test_nessuna_regola_e_unknown(self):
        self.assertEqual(resolve_role([], "Piega", CONTINUA), "unknown")
        self.assertEqual(resolve_role(forge.name_rules({"altro": "outer"}), "Boh", CONTINUA),
                         "unknown")

    def test_name_rules(self):
        rules = forge.name_rules({"Cartiglio": "title_block", "MARK": "engrave"})
        self.assertEqual(resolve_role(rules, "cartiglio", CONTINUA), "title_block")
        self.assertEqual(resolve_role(rules, "MARK", CONTINUA), "engrave")


if __name__ == "__main__":
    unittest.main()
