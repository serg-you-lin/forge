"""
Test Suite per casi edge su DXF reali.

Comportamento atteso per ogni DXF in examples/edge_cases/:
- Se l'healer trova loop → verifica che i nodi USATI nei loop
  siano presenti nei vertici della LWPOLYLINE risultante
- Se l'healer NON trova loop → verifica che emetta un warning
  (file da ritoccare manualmente — comportamento corretto)

Aggiungi DXF problematici in examples/edge_cases/ day by day.

Lancia:
    python -m unittest tests/test_edge_cases.py -v
"""

import unittest
from pathlib import Path
import sys
import ezdxf
import numpy as np
from collections import defaultdict

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import dxf_forge as forge

COORD_TOLERANCE = 0.01
EDGE_CASES_DIR  = project_root / "tests" / "examples" / "edge_cases"


def _arc_endpoints(entity):
    cx, cy = entity.dxf.center.x, entity.dxf.center.y
    r = entity.dxf.radius
    s = (cx + r * np.cos(np.radians(entity.dxf.start_angle)),
         cy + r * np.sin(np.radians(entity.dxf.start_angle)))
    e = (cx + r * np.cos(np.radians(entity.dxf.end_angle)),
         cy + r * np.sin(np.radians(entity.dxf.end_angle)))
    return s, e


def _round_point(pt, decimals=1):
    return (round(pt[0], decimals), round(pt[1], decimals))


def _find_loop_nodes(msp) -> list:
    """
    Ricostruisce il grafo e trova i nodi che appartengono a loop chiusi.
    Restituisce solo i punti delle entità effettivamente usate nei loop.
    Ignora LINE/ARC che non fanno parte di nessun contorno chiuso
    (es. marcature, quote, linee di costruzione).
    """
    graph = defaultdict(list)
    for entity in msp.query('LINE ARC'):
        if entity.dxftype() == 'LINE':
            s = _round_point((entity.dxf.start.x, entity.dxf.start.y))
            e = _round_point((entity.dxf.end.x,   entity.dxf.end.y))
        else:
            s_pt, e_pt = _arc_endpoints(entity)
            s = _round_point(s_pt)
            e = _round_point(e_pt)
        graph[s].append((entity, e))
        graph[e].append((entity, s))

    visited_edges = set()
    loop_entities = set()

    for start_node in graph:
        for (entity, next_node) in graph[start_node]:
            if id(entity) in visited_edges:
                continue

            chain = [(entity,)]
            visited_edges.add(id(entity))
            current_node = next_node

            while current_node != start_node:
                candidates = [(e, n) for (e, n) in graph[current_node]
                              if id(e) not in visited_edges]
                if not candidates:
                    break
                next_entity, current_node = candidates[0]
                visited_edges.add(id(next_entity))
                chain.append((next_entity,))

            if current_node == start_node:
                for (e,) in chain:
                    loop_entities.add(id(e))

    # Estrai i punti solo delle entità nei loop
    points = []
    for entity in msp.query('LINE ARC'):
        if id(entity) not in loop_entities:
            continue
        if entity.dxftype() == 'LINE':
            points.append((entity.dxf.start.x, entity.dxf.start.y))
            points.append((entity.dxf.end.x,   entity.dxf.end.y))
        else:
            s, e = _arc_endpoints(entity)
            points.append(s)
            points.append(e)

    return points, len(loop_entities) > 0


def _extract_pline_vertices(msp) -> list:
    points = []
    for entity in msp.query('LWPOLYLINE'):
        for pt in entity.get_points():
            points.append((pt[0], pt[1]))
    return points


def _point_in_list(pt, point_list, tolerance) -> bool:
    for other in point_list:
        dx = pt[0] - other[0]
        dy = pt[1] - other[1]
        if (dx*dx + dy*dy) ** 0.5 <= tolerance:
            return True
    return False


def _load_edge_cases() -> list:
    if not EDGE_CASES_DIR.exists():
        return []
    return sorted(EDGE_CASES_DIR.glob("*.dxf")) + \
           sorted(EDGE_CASES_DIR.glob("*.DXF"))


class TestEdgeCases(unittest.TestCase):
    pass


def _make_test(dxf_path: Path):
    def test_method(self):
        name = dxf_path.stem
        print(f"\n--- Edge case: {name} ---")

        doc  = ezdxf.readfile(str(dxf_path))
        msp  = doc.modelspace()

        loop_nodes, has_loops = _find_loop_nodes(msp)
        print(f"  Nodi in loop chiusi: {len(loop_nodes)}, loop trovati: {has_loops}")

        if not list(msp.query('LINE ARC')):
            # File solo LWPOLYLINE
            print("  File già pulito — testo assegnazione layer.")
            result = forge.heal(msp, write_to_msp=True)
            self.assertGreater(result.part_count, 0,
                               f"{name}: nessun pezzo trovato su file già pulito")
            layers = {p.dxf.layer for p in msp.query('LWPOLYLINE')}
            print(f"  Layer: {layers}")
            self.assertIn(forge.LAYER_OUTER, layers)
            return

        result = forge.heal(msp, write_to_msp=True)
        print(f"  Parts: {result.part_count}, Valid: {result.is_valid}")
        if result.warnings:
            for w in result.warnings:
                print(f"  WARN: {w}")
        if result.errors:
            for e in result.errors:
                print(f"  ERROR: {e}")

        self.assertIsNotNone(result)

        if not has_loops:
            # Nessun loop trovato — comportamento corretto è emettere warning
            print(f"  Nessun loop — file da ritoccare manualmente. "
                  f"Verifico che ci sia un warning.")
            self.assertTrue(result.has_issues,
                            f"{name}: atteso warning per file senza loop chiusi")
            print(f"  OK: warning emesso correttamente.")
            return

        # Loop trovati — verifica che i nodi siano nei vertici healed
        self.assertGreater(result.part_count, 0,
                           f"{name}: loop trovati ma nessun pezzo prodotto")

        healed_vertices = _extract_pline_vertices(msp)
        print(f"  Vertici LWPOLYLINE dopo heal: {len(healed_vertices)}")

        missing = [pt for pt in loop_nodes
                   if not _point_in_list(pt, healed_vertices, COORD_TOLERANCE)]

        if missing:
            print(f"  NODI MANCANTI: {len(missing)}")
            for pt in missing[:5]:
                print(f"    {pt}")

        self.assertEqual(len(missing), 0,
                         f"{name}: {len(missing)} nodi originali non trovati "
                         f"(tolleranza={COORD_TOLERANCE}mm)")
        print(f"  OK: tutti i nodi dei loop presenti nei vertici healed.")

    test_method.__name__ = f"test_{dxf_path.stem}"
    test_method.__doc__  = f"Edge case: {dxf_path.name}"
    return test_method


for _dxf_path in _load_edge_cases():
    setattr(TestEdgeCases, f"test_{_dxf_path.stem}", _make_test(_dxf_path))


class TestEdgeCasesDirExists(unittest.TestCase):

    def test_001_dir_exists(self):
        """La cartella examples/edge_cases/ esiste."""
        self.assertTrue(EDGE_CASES_DIR.exists(),
                        f"Cartella non trovata: {EDGE_CASES_DIR}")

    def test_002_contains_dxf(self):
        """La cartella contiene almeno 1 DXF."""
        files = _load_edge_cases()
        print(f"\n  DXF trovati: {len(files)}")
        for f in files:
            print(f"    - {f.name}")
        self.assertGreater(len(files), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)