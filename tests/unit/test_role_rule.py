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
# catene: segni diversi alternati (tratto lungo + tratto corto / punto)
TRATTO_PUNTO = EdgeStyle(linetype="Qualunque", linetype_pattern=(1.0, 0.5, -0.25, 0.0, -0.25))
DUE_TRATTI   = EdgeStyle(linetype="Qualunque", linetype_pattern=(2.0, 1.25, -0.25, 0.25, -0.25))


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


class TestDashKind(unittest.TestCase):
    # D64: la forma del tratto si legge dai segni del pattern, non dal nome

    def test_continua(self):
        self.assertEqual(CONTINUA.dash_kind, "continuous")
        self.assertEqual(EdgeStyle(linetype_pattern=(1.0, 1.0, 0.0)).dash_kind, "continuous")

    def test_tratteggio_uniforme(self):
        self.assertEqual(TRATTEGGIATA.dash_kind, "uniform")
        self.assertEqual(PUNTINATA.dash_kind, "uniform")      # solo punti
        # stesso tratto ripetuto più volte nel pattern: resta uniforme
        self.assertEqual(EdgeStyle(linetype_pattern=(1.5, 0.5, -0.25, 0.5, -0.25)).dash_kind,
                         "uniform")

    def test_catena(self):
        self.assertEqual(TRATTO_PUNTO.dash_kind, "chain")
        self.assertEqual(DUE_TRATTI.dash_kind, "chain")
        # tratto lungo + due corti
        self.assertEqual(EdgeStyle(linetype_pattern=(0.8, 0.45, -0.05, 0.1, -0.05, 0.1, -0.05))
                         .dash_kind, "chain")

    def test_tolleranza_relativa_alla_scala(self):
        # stessi rapporti a scale diverse → stessa forma
        for k in (0.01, 1.0, 100.0):
            pattern = tuple(x * k for x in (2.0, 1.25, -0.25, 0.25, -0.25))
            self.assertEqual(EdgeStyle(linetype_pattern=pattern).dash_kind, "chain", msg=k)
        # tratti diversi per un arrotondamento non fanno una catena
        self.assertEqual(EdgeStyle(linetype_pattern=(1.5, 0.5, -0.25, 0.501, -0.25)).dash_kind,
                         "uniform")

    def test_lunghezza_totale_zero(self):
        # pattern senza lunghezza totale dichiarata: si usa la somma dei segni
        self.assertEqual(EdgeStyle(linetype_pattern=(0.0, 1.25, -0.25, 0.25, -0.25)).dash_kind,
                         "chain")


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
        # il caso del snapdraw: tratteggiata E nome "construction"
        rule = forge.RoleRule("construction", name_contains="construction", dashed=True)
        self.assertTrue(rule.matches("construction", TRATTEGGIATA))
        self.assertFalse(rule.matches("construction", CONTINUA))
        self.assertFalse(rule.matches("0", TRATTEGGIATA))

    def test_solo_continue(self):
        rule = forge.RoleRule("outer", dashed=False)
        self.assertTrue(rule.matches("", CONTINUA))
        self.assertFalse(rule.matches("", TRATTEGGIATA))

    def test_forma_del_tratto(self):
        # la regola ISO 128 del snapdraw: catena → costruzione, il tratteggio no
        rule = forge.RoleRule("construction", dash="chain")
        self.assertTrue(rule.matches("", TRATTO_PUNTO))
        self.assertTrue(rule.matches("", DUE_TRATTI))
        self.assertFalse(rule.matches("", TRATTEGGIATA))
        self.assertFalse(rule.matches("", CONTINUA))
        self.assertTrue(forge.RoleRule("x", dash="UNIFORM").matches("", PUNTINATA))

    def test_dashed_include_le_catene(self):
        # dashed resta "ha almeno un vuoto": vale per le due famiglie
        self.assertTrue(forge.RoleRule("x", dashed=True).matches("", TRATTO_PUNTO))

    def test_dash_sconosciuto_solleva(self):
        with self.assertRaises(ValueError):
            forge.RoleRule("construction", dash="dashdot")

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

    def test_piega_a_catena_presa_prima_dal_nome(self):
        # una piega disegnata a catena resta bending se la regola per nome viene prima
        rules = [
            forge.RoleRule("bending", name="piega"),
            forge.RoleRule("construction", dash="chain"),
        ]
        self.assertEqual(resolve_role(rules, "Piega", TRATTO_PUNTO), "bending")
        self.assertEqual(resolve_role(rules, "Assi", TRATTO_PUNTO), "construction")

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
