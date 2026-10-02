"""
tests/unit/test_anonymize.py
----------------------------
`forge.tools.anonymize`: guardare e ripulire quello che è scritto dentro un
disegno, senza toccare la geometria.

Il fixture è `Linee_piegatura.dxf` (tracciato, piccolo): porta il layer
`MARCATURA` in 9 posti — una volta nel record di tabella e otto volte nel
gruppo 8 delle entità — che è esattamente il caso in cui una sostituzione per
posizione romperebbe il file e una per valore no.
"""

import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from forge.adapters.dxf.tags import is_ascii_dxf, read_tags
from forge.tools.anonymize import (
    apply_mapping,
    clean_dxf,
    geometry_fingerprint,
    is_format_internal,
    scan_dxf,
)

FIXTURE = project_root / "tests" / "examples" / "Linee_piegatura.dxf"


class TestScan(unittest.TestCase):
    """Il referto: cosa c'è scritto, e in che veste."""

    @classmethod
    def setUpClass(cls):
        if not FIXTURE.exists():
            raise unittest.SkipTest(f"fixture mancante: {FIXTURE}")
        cls.report = scan_dxf(FIXTURE)

    def test_trova_il_layer_col_suo_contesto(self):
        # il nome del layer e il posto in cui sta: è il contesto che fa capire
        # cos'è una parola (un layer, non uno stile di quota)
        marcatura = [s for s in self.report.strings if s.value == "MARCATURA"]
        self.assertEqual(len(marcatura), 1, "una voce per stringa, non per occorrenza")
        found = marcatura[0]
        self.assertIn("name/AcDbLayerTableRecord", found.contexts)
        self.assertIn("layer/AcDbEntity", found.contexts)
        self.assertEqual(len(found.lines), 9)

    def test_le_variabili_di_intestazione_portano_il_loro_nome(self):
        # `$DIMSTYLE` → ISO-25: il valore è attribuito alla variabile, non
        # all'entità che capita prima
        header = {s.value: s for s in self.report.of_kind("header")}
        self.assertTrue(header, "nessuna variabile d'intestazione letta")
        self.assertTrue(any("$" in context
                            for s in header.values() for context in s.contexts))

    def test_il_referto_e_piu_corto_di_tutto(self):
        # senza il collasso del vocabolario del formato non lo legge nessuno
        self.assertLess(len(self.report.to_read()), len(self.report.strings))
        self.assertIn("MARCATURA", self.report.report())

    def test_cosa_e_del_formato_e_cosa_no(self):
        self.assertTrue(is_format_internal("AcDbEntity"))
        self.assertTrue(is_format_internal("ByLayer"))
        self.assertTrue(is_format_internal("*Model_Space"))
        self.assertTrue(is_format_internal("{F0864738-46B2-0047-8E7C-DD2C0D14328C}"))
        self.assertTrue(is_format_internal("1.4.3 @ 2026-09-06T13:14:46.693489+00:00"))
        # un nome scritto da una persona non è mai "del formato"
        self.assertFalse(is_format_internal("Rossi"))
        self.assertFalse(is_format_internal("MARCATURA"))


class TestClean(unittest.TestCase):
    """La pulitura: sostituisce le stringhe, non la geometria."""

    def setUp(self):
        if not FIXTURE.exists():
            self.skipTest(f"fixture mancante: {FIXTURE}")
        self.tmp = Path(tempfile.mkdtemp(prefix="anonymize_"))
        self.copy = self.tmp / FIXTURE.name
        shutil.copy2(FIXTURE, self.copy)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_rinomina_il_layer_in_ogni_posto(self):
        out = self.tmp / "pulito.dxf"
        report = clean_dxf(self.copy, {"MARCATURA": "SEGNI"}, out)
        self.assertTrue(report.verified, "forge deve confermare la geometria")
        self.assertEqual(report.total, 9, "tutte le occorrenze, non solo la tabella")
        # e nel file non resta traccia del nome vecchio
        testo = out.read_text(encoding="utf-8", errors="replace")
        self.assertNotIn("MARCATURA", testo)
        self.assertIn("SEGNI", testo)

    def test_la_geometria_resta_identica(self):
        out = self.tmp / "pulito.dxf"
        prima = geometry_fingerprint(self.copy)
        clean_dxf(self.copy, {"MARCATURA": "SEGNI"}, out)
        self.assertEqual(geometry_fingerprint(out), prima)

    def test_non_tocca_i_numeri(self):
        # una chiave che somiglia a una coordinata non deve trovare niente:
        # i gruppi numerici non sono fra quelli che la pulitura guarda
        out = self.tmp / "pulito.dxf"
        report = clean_dxf(self.copy, {"0.0": "9.9"}, out)
        self.assertEqual(report.total, 0)
        self.assertIn("0.0", report.unused)
        self.assertEqual(out.read_bytes(), self.copy.read_bytes())

    def test_scrivere_senza_modifiche_non_cambia_un_byte(self):
        # la promessa del modulo: il fixture resta il file che è
        out = self.tmp / "copia.dxf"
        read_tags(self.copy).save(out)
        self.assertEqual(out.read_bytes(), self.copy.read_bytes())

    def test_rifiuta_se_la_geometria_cambia(self):
        # se la pulitura spostasse un numero, il file non deve essere scritto
        out = self.tmp / "pulito.dxf"
        with mock.patch("forge.tools.anonymize.geometry_fingerprint",
                        side_effect=[("prima",), ("dopo",)]):
            with self.assertRaises(ValueError):
                clean_dxf(self.copy, {"MARCATURA": "SEGNI"}, out)
        self.assertFalse(out.exists(), "il file sbagliato va rimosso")

    def test_un_dxf_binario_non_si_legge(self):
        finto = self.tmp / "binario.dxf"
        finto.write_bytes(b"AutoCAD Binary DXF\r\n\x1a\x00" + b"\x00" * 16)
        self.assertFalse(is_ascii_dxf(finto))
        with self.assertRaises(ValueError):
            read_tags(finto)


class TestApplyMapping(unittest.TestCase):
    """I golden che citano quei testi vanno riallineati nello stesso passaggio."""

    def test_riallinea_un_golden(self):
        tmp = Path(tempfile.mkdtemp(prefix="anonymize_golden_"))
        try:
            golden = tmp / "golden.json"
            golden.write_text('{"display_text": "MARCATURA", "area": 100.0}',
                              encoding="utf-8")
            changed = apply_mapping([golden], {"MARCATURA": "SEGNI"})
            self.assertEqual(list(changed.values()), [1])
            self.assertIn("SEGNI", golden.read_text(encoding="utf-8"))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
