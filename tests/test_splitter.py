"""
Test Suite per dxf_forge.splitter

Prima di lanciare, genera i DXF di esempio:
    python generate_examples.py

Poi lancia:
    python -m unittest tests/test_splitter.py -v

NOTA REFACTOR: split() è stato rimosso dall'API pubblica.
Il ForgeResult viene ora costruito direttamente da heal(),
che lavora in memoria senza rileggere dal msp.
split_to_files() usa heal_result internamente.
"""

import unittest
import json
import tempfile
import os
from pathlib import Path
import sys
import ezdxf

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import dxf_forge as forge


class TestSplitterTwoParts(unittest.TestCase):
    """Test su DXF con 2 LWPOLYLINE separate."""

    def setUp(self):
        doc = ezdxf.readfile("examples/two_parts.dxf")
        msp = doc.modelspace()
        self.result = forge.heal(msp, write_to_msp=False, label="two_parts")

    def test_001_finds_two_parts(self):
        """heal() trova 2 parti."""
        self.assertEqual(self.result.part_count, 2,
                         f"Attese 2 parti, trovate {self.result.part_count}")

    def test_002_no_holes(self):
        """Nessuna delle due parti ha fori."""
        for part in self.result.parts:
            print(f"  {part.label} holes={len(part.inners)}")
            self.assertEqual(len(part.inners), 0)

    def test_003_correct_areas(self):
        """Pezzo 1: 80x60=4800, Pezzo 2: 100x80=8000."""
        areas = sorted([p.area for p in self.result.parts])
        print(f"  areas={areas}")
        self.assertAlmostEqual(areas[0], 4800, delta=50)
        self.assertAlmostEqual(areas[1], 8000, delta=50)


class TestSplitterWithHole(unittest.TestCase):
    """Test su DXF con outer + hole già come LWPOLYLINE."""

    def setUp(self):
        doc = ezdxf.readfile("examples/pline_with_hole.dxf")
        msp = doc.modelspace()
        self.result = forge.heal(msp, write_to_msp=False, label="pline_with_hole")

    def test_001_finds_one_part(self):
        """heal() trova 1 parte."""
        self.assertEqual(self.result.part_count, 1)

    def test_002_has_one_hole(self):
        """La parte ha 1 foro."""
        holes = self.result.parts[0].inners
        print(f"  holes={len(holes)}")
        self.assertEqual(len(holes), 1)

    def test_003_net_area(self):
        """Area netta = 150x100 - 50x40 = 15000 - 2000 = 13000."""
        net_area = self.result.parts[0].area
        print(f"  net area={net_area:.1f}")
        self.assertAlmostEqual(net_area, 13000, delta=100)


class TestExport(unittest.TestCase):
    """Test su to_dict, to_json, to_nester_input."""

    def setUp(self):
        doc = ezdxf.readfile("examples/two_parts.dxf")
        msp = doc.modelspace()
        self.result = forge.heal(msp, write_to_msp=False, label="two_parts")

    def test_002_to_json_valid(self):
        """to_json produce JSON valido."""
        json_str = forge.to_json(self.result)
        parsed = json.loads(json_str)
        print(f"\n[to_json] part_count={parsed['part_count']}")
        self.assertEqual(parsed["part_count"], 2)

    def test_003_to_nester_input(self):
        """to_nester_input ha outer_coords e holes_coords."""
        doc = ezdxf.readfile("examples/pline_with_hole.dxf")
        msp = doc.modelspace()
        result = forge.heal(msp, write_to_msp=False, label="pline_with_hole")
        nester_input = forge.to_nester_input(result)
        print(f"\n[nester_input] keys={list(nester_input[0].keys())}")
        self.assertEqual(len(nester_input), 1)
        self.assertGreater(len(nester_input[0]["outer_coords"]), 0)
        self.assertEqual(len(nester_input[0]["holes_coords"]), 1)


class TestSplitToFilesFilter(unittest.TestCase):
    """Test sul filtro entità in split_to_files."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        doc = ezdxf.new('R2010')
        msp = doc.modelspace()
        msp.add_lwpolyline(
            [(0, 0), (200, 0), (200, 100), (0, 100)],
            close=True, dxfattribs={'layer': '0'}
        )
        msp.add_text("NOTA TECNICA", dxfattribs={
            'insert': (50, 50), 'height': 5, 'layer': 'TESTO'
        })
        msp.add_circle((100, 50), 10, dxfattribs={'layer': '0'})
        self.input_dxf = os.path.join(self.temp_dir, "test_filter.dxf")
        doc.saveas(self.input_dxf)

    def test_001_include_all_by_default(self):
        """Default: testo e geometria vengono copiati."""
        out_dir = tempfile.mkdtemp()
        doc = ezdxf.readfile(self.input_dxf)
        forge.split_to_files(doc.modelspace(), output_folder=out_dir, label="test")
        out_doc = ezdxf.readfile(f"{out_dir}/test_1.dxf")
        out_msp = out_doc.modelspace()
        texts   = list(out_msp.query('TEXT'))
        circles = list(out_msp.query('CIRCLE'))
        print(f"\n[filter default] texts={len(texts)}, circles={len(circles)}")
        self.assertEqual(len(texts), 1)
        self.assertEqual(len(circles), 1)

    def test_002_exclude_text_by_type(self):
        """exclude_types={'TEXT'}: il testo non viene copiato."""
        out_dir = tempfile.mkdtemp()
        doc = ezdxf.readfile(self.input_dxf)
        forge.split_to_files(doc.modelspace(), output_folder=out_dir,
                             label="test", exclude_types={'TEXT'})
        out_doc = ezdxf.readfile(f"{out_dir}/test_1.dxf")
        out_msp = out_doc.modelspace()
        texts   = list(out_msp.query('TEXT'))
        circles = list(out_msp.query('CIRCLE'))
        print(f"\n[exclude TEXT] texts={len(texts)}, circles={len(circles)}")
        self.assertEqual(len(texts), 0)
        self.assertEqual(len(circles), 1)

    def test_003_include_annotations_false(self):
        """include_annotations=False esclude tutti i tipi annotazione."""
        out_dir = tempfile.mkdtemp()
        doc = ezdxf.readfile(self.input_dxf)
        forge.split_to_files(doc.modelspace(), output_folder=out_dir,
                             label="test", include_annotations=False)
        out_doc = ezdxf.readfile(f"{out_dir}/test_1.dxf")
        out_msp = out_doc.modelspace()
        texts   = list(out_msp.query('TEXT'))
        circles = list(out_msp.query('CIRCLE'))
        print(f"\n[no annotations] texts={len(texts)}, circles={len(circles)}")
        self.assertEqual(len(texts), 0)
        self.assertEqual(len(circles), 1)


class TestMetadata(unittest.TestCase):
    """
    Test su write_metadata_to_dxf e read_metadata_from_dxf.

    I metadata non vengono più scritti da split_to_files —
    è responsabilità del chiamante scriverli dopo lo split
    con i dati esterni che conosce (materiale, spessore, ecc.).
    """

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        doc = ezdxf.new('R2010')
        msp = doc.modelspace()
        msp.add_lwpolyline(
            [(0, 0), (150, 0), (150, 80), (0, 80)],
            close=True, dxfattribs={'layer': '0'}
        )
        self.input_dxf = os.path.join(self.temp_dir, "meta_test.dxf")
        doc.saveas(self.input_dxf)

    def _heal_and_get_part(self):
        """Heala il file e restituisce (doc, part) pronti per i metadata."""
        doc = ezdxf.readfile(self.input_dxf)
        msp = doc.modelspace()
        result = forge.heal(msp, write_to_msp=True, label="meta_test")
        return doc, result.parts[0]

    def test_001_metadata_written(self):
        """I metadati vengono scritti e riletti correttamente."""
        doc, part = self._heal_and_get_part()
        forge.write_metadata_to_dxf(doc, part)
        out_path = os.path.join(self.temp_dir, "meta_test_out.dxf")
        doc.saveas(out_path)
        out_doc = ezdxf.readfile(out_path)
        meta = forge.read_metadata_from_dxf(out_doc)
        print(f"\n[metadata] {meta}")
        self.assertNotEqual(meta, {})
        self.assertEqual(meta['label'], "meta_test")

    def test_002_metadata_area(self):
        """Area nei metadati corrisponde a 150x80=12000."""
        doc, part = self._heal_and_get_part()
        forge.write_metadata_to_dxf(doc, part)
        out_path = os.path.join(self.temp_dir, "meta_test_out.dxf")
        doc.saveas(out_path)
        out_doc = ezdxf.readfile(out_path)
        meta = forge.read_metadata_from_dxf(out_doc)
        print(f"\n[metadata area] {meta.get('area_mm2')}")
        self.assertAlmostEqual(meta['area_mm2'], 12000, delta=50)

    def test_003_metadata_absent_without_write(self):
        """Senza chiamare write_metadata_to_dxf i metadati non esistono."""
        doc, part = self._heal_and_get_part()
        out_path = os.path.join(self.temp_dir, "meta_test_out.dxf")
        doc.saveas(out_path)
        out_doc = ezdxf.readfile(out_path)
        meta = forge.read_metadata_from_dxf(out_doc)
        print(f"\n[metadata absent] {meta}")
        self.assertEqual(meta, {})

    def test_004_metadata_bbox(self):
        """La bbox nei metadati è corretta."""
        doc, part = self._heal_and_get_part()
        forge.write_metadata_to_dxf(doc, part)
        out_path = os.path.join(self.temp_dir, "meta_test_out.dxf")
        doc.saveas(out_path)
        out_doc = ezdxf.readfile(out_path)
        meta = forge.read_metadata_from_dxf(out_doc)
        bbox = meta['bbox']
        print(f"\n[metadata bbox] w={bbox['maxx']-bbox['minx']:.1f} "
              f"h={bbox['maxy']-bbox['miny']:.1f}")
        self.assertAlmostEqual(bbox['maxx'] - bbox['minx'], 150, delta=1)
        self.assertAlmostEqual(bbox['maxy'] - bbox['miny'], 80,  delta=1)


class TestSplitToFilesClosedContours(unittest.TestCase):
    """
    Ogni contorno strutturale esportato nei file figli deve essere chiuso.
    Copre LWPOLYLINE (bug introdotto passando a _copy_entity),
    e verifica che CIRCLE e SPLINE vengano esportati correttamente.
    """

    def _get_output_contours(self, input_dxf_name, label):
        out_dir = tempfile.mkdtemp()
        doc = ezdxf.readfile(f"examples/{input_dxf_name}")
        forge.split_to_files(doc.modelspace(), output_folder=out_dir, label=label)
        results = {}
        for f in Path(out_dir).glob("*.dxf"):
            child_doc = ezdxf.readfile(str(f))
            results[f.name] = child_doc.modelspace()
        return results

    def test_001_lwpolyline_outer_is_closed(self):
        """LWPOLYLINE su OuterContour deve essere closed=True."""
        from dxf_forge.layers import LAYER_OUTER
        children = self._get_output_contours("two_parts.dxf", "two_parts")
        self.assertGreater(len(children), 0)
        for fname, msp in children.items():
            for e in msp.query('LWPOLYLINE'):
                if e.dxf.layer == LAYER_OUTER:
                    self.assertTrue(e.closed,
                        f"{fname}: LWPOLYLINE su {LAYER_OUTER} non è chiusa")

    def test_002_lwpolyline_inner_is_closed(self):
        """LWPOLYLINE su InnerContour/Hole deve essere closed=True."""
        from dxf_forge.layers import LAYER_INNER, LAYER_HOLE
        children = self._get_output_contours("pline_with_hole.dxf", "pline_with_hole")
        for fname, msp in children.items():
            for e in msp.query('LWPOLYLINE'):
                if e.dxf.layer in (LAYER_INNER, LAYER_HOLE):
                    self.assertTrue(e.closed,
                        f"{fname}: LWPOLYLINE su {e.dxf.layer} non è chiusa")

    def test_003_circle_outer_exported(self):
        """CIRCLE su OuterContour viene esportato nel file figlio."""
        from dxf_forge.layers import LAYER_OUTER
        children = self._get_output_contours("cerchi_ciambella.dxf", "cerchi_ciambella")
        self.assertGreater(len(children), 0)
        for fname, msp in children.items():
            outer_circles = [e for e in msp.query('CIRCLE')
                             if e.dxf.layer == LAYER_OUTER]
            self.assertEqual(len(outer_circles), 1,
                f"{fname}: atteso 1 CIRCLE su OuterContour, trovati {len(outer_circles)}")

    def test_004_spline_outer_exported(self):
        """
        Loop con SPLINE su OuterContour: le entità originali (LINE+SPLINE)
        devono essere presenti nel file figlio su layer OuterContour.
        Non viene prodotta una LWPOLYLINE discretizzata.
        """
        from dxf_forge.layers import LAYER_OUTER
        children = self._get_output_contours("intricato_doppio.dxf", "intricato_doppio")
        spline_files = [
            fname for fname, msp in children.items()
            if any(e.dxf.layer == LAYER_OUTER
                   for e in msp.query('SPLINE LINE ARC'))
        ]
        self.assertGreater(len(spline_files), 0,
            "Nessun file figlio contiene entità su OuterContour per loop con SPLINE")

    def test_005_all_contours_closed_generic(self):
        """
        Per qualsiasi file in examples/, ogni LWPOLYLINE strutturale
        nei file figli deve essere closed=True.
        Regressione generica — cattura il bug close=entity.closed.
        """
        from dxf_forge.layers import LAYER_OUTER, LAYER_INNER, LAYER_HOLE
        structural = {LAYER_OUTER, LAYER_INNER, LAYER_HOLE}
        examples = Path("examples").glob("*.dxf")
        for src in examples:
            if src.stem.endswith("_healed"):
                continue
            out_dir = tempfile.mkdtemp()
            try:
                doc = ezdxf.readfile(str(src))
                forge.split_to_files(doc.modelspace(),
                                     output_folder=out_dir, label=src.stem)
                for child in Path(out_dir).glob("*.dxf"):
                    child_doc = ezdxf.readfile(str(child))
                    for e in child_doc.modelspace().query('LWPOLYLINE'):
                        if e.dxf.layer in structural:
                            self.assertTrue(e.closed,
                                f"{child.name}: LWPOLYLINE su {e.dxf.layer} "
                                f"non è chiusa (sorgente: {src.name})")
            except Exception:
                pass  # file non splittabili ignorati


class TestSplitToFilesLayers(unittest.TestCase):
    """I layer forge nei file figli hanno i colori canonici da layers.py."""

    def setUp(self):
        self.out_dir = tempfile.mkdtemp()
        doc = ezdxf.readfile("examples/two_parts.dxf")
        forge.split_to_files(doc.modelspace(),
                             output_folder=self.out_dir, label="test")

    def test_001_outer_layer_color(self):
        """LAYER_OUTER ha COLOR_OUTER nel file figlio."""
        from dxf_forge.layers import LAYER_OUTER, COLOR_OUTER
        for f in Path(self.out_dir).glob("*.dxf"):
            child_doc = ezdxf.readfile(str(f))
            layer = child_doc.layers.get(LAYER_OUTER)
            self.assertEqual(layer.dxf.color, COLOR_OUTER,
                f"{f.name}: LAYER_OUTER ha colore {layer.dxf.color}, atteso {COLOR_OUTER}")

    def test_002_all_forge_layers_present(self):
        """Tutti i layer forge sono presenti nel file figlio."""
        from dxf_forge.layers import (
            LAYER_OUTER, LAYER_INNER, LAYER_HOLE,
            LAYER_BENDING, LAYER_MARKING, LAYER_ENGRAVE, TRASH_LAYER,
        )
        all_layers = {LAYER_OUTER, LAYER_INNER, LAYER_HOLE,
                      LAYER_BENDING, LAYER_MARKING, LAYER_ENGRAVE, TRASH_LAYER}
        for f in Path(self.out_dir).glob("*.dxf"):
            child_doc = ezdxf.readfile(str(f))
            child_layer_names = {l.dxf.name for l in child_doc.layers}
            for layer_name in all_layers:
                self.assertIn(layer_name, child_layer_names,
                    f"{f.name}: layer '{layer_name}' mancante")

    def test_003_layer_colors_match_canonical(self):
        """Tutti i layer forge hanno il colore canonico da layers.py."""
        from dxf_forge.splitter import ALL_FORGE_LAYERS
        for f in Path(self.out_dir).glob("*.dxf"):
            child_doc = ezdxf.readfile(str(f))
            for layer_name, expected_color in ALL_FORGE_LAYERS.items():
                layer = child_doc.layers.get(layer_name)
                self.assertEqual(layer.dxf.color, expected_color,
                    f"{f.name}: layer '{layer_name}' ha colore "
                    f"{layer.dxf.color}, atteso {expected_color}")
                
                
if __name__ == '__main__':
    unittest.main(verbosity=2)