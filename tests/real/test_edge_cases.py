
"""
Test Suite per casi edge su DXF reali.
"""

import unittest
from pathlib import Path
import sys
import ezdxf
from collections import defaultdict
from forge.adapters.dxf.geometry_adapter import arc_endpoints as _arc_endpoints
from forge.core.geometry import round_point as _round_point

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

import forge

COORD_TOLERANCE = 0.01
EDGE_CASES_DIR = project_root / "tests" / "examples" / "edge_cases"



def _find_loop_nodes(msp):
    graph = defaultdict(list)

    for entity in msp.query("LINE ARC"):
        if entity.dxftype() == "LINE":
            s = _round_point((entity.dxf.start.x, entity.dxf.start.y))
            e = _round_point((entity.dxf.end.x, entity.dxf.end.y))
        else:
            s_pt, e_pt = _arc_endpoints(entity)
            s = _round_point(s_pt)
            e = _round_point(e_pt)

        graph[s].append((entity, e))
        graph[e].append((entity, s))

    visited = set()
    loop_entities = set()

    for start_node in graph:
        for (entity, next_node) in graph[start_node]:
            if id(entity) in visited:
                continue

            chain = [(entity,)]
            visited.add(id(entity))
            current = next_node

            while current != start_node:
                candidates = [
                    (e, n)
                    for (e, n) in graph[current]
                    if id(e) not in visited
                ]
                if not candidates:
                    break

                next_entity, current = candidates[0]
                visited.add(id(next_entity))
                chain.append((next_entity,))

            if current == start_node:
                for (e,) in chain:
                    loop_entities.add(id(e))

    points = []
    for entity in msp.query("LINE ARC"):
        if id(entity) not in loop_entities:
            continue

        if entity.dxftype() == "LINE":
            points.append((entity.dxf.start.x, entity.dxf.start.y))
            points.append((entity.dxf.end.x, entity.dxf.end.y))
        else:
            s, e = _arc_endpoints(entity)
            points.append(s)
            points.append(e)

    return points, len(loop_entities) > 0


def _extract_pline_vertices(msp):
    points = []
    for entity in msp.query("LWPOLYLINE"):
        for pt in entity.get_points():
            points.append((pt[0], pt[1]))
    return points


def _point_in_list(pt, point_list, tolerance):
    for other in point_list:
        dx = pt[0] - other[0]
        dy = pt[1] - other[1]
        if (dx * dx + dy * dy) ** 0.5 <= tolerance:
            return True
    return False


def _load_edge_cases():
    if not EDGE_CASES_DIR.exists():
        return []
    return sorted(EDGE_CASES_DIR.glob("*.dxf")) + sorted(
        EDGE_CASES_DIR.glob("*.DXF")
    )


class TestEdgeCases(unittest.TestCase):
    pass


def _make_test(dxf_path):
    def test_method(self):
        name = dxf_path.stem

        doc = ezdxf.readfile(str(dxf_path))
        msp = doc.modelspace()

        loop_nodes, has_loops = _find_loop_nodes(msp)

        result = forge.heal(msp)
        forge.detect(result)
        forge.write(msp, result)
        forge.inject(result)

        self.assertIsNotNone(result)

        if not has_loops:
            self.assertTrue(result.has_issues)
            return

        self.assertGreater(result.part_count, 0)

        healed_vertices = _extract_pline_vertices(msp)

        missing = [
            pt
            for pt in loop_nodes
            if not _point_in_list(pt, healed_vertices, COORD_TOLERANCE)
        ]

        self.assertEqual(len(missing), 0)

    test_method.__name__ = f"test_{dxf_path.stem}"
    test_method.__doc__ = f"Edge case: {dxf_path.name}"
    return test_method


for _dxf_path in _load_edge_cases():
    setattr(TestEdgeCases, f"test_{_dxf_path.stem}", _make_test(_dxf_path))


class TestEdgeCasesDirExists(unittest.TestCase):

    def test_001_dir_exists(self):
        self.assertTrue(EDGE_CASES_DIR.exists())

    def test_002_contains_dxf(self):
        files = _load_edge_cases()
        self.assertGreater(len(files), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)