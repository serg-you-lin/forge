"""
tests/real/test_text_budget.py
------------------------------
Il peso di `to_text` sui disegni di viste (`anch_NN`), sorvegliato come un
golden (MAP.md D84): il valore della lettura per un agente sta nel pesare molto
meno del DXF, e ogni riga in più deve essere una scelta, non una deriva.

Si misura in caratteri, non in token: nessuna dipendenza da un tokenizer, e i
due crescono insieme. Il test fallisce se un disegno supera il suo budget;
se si aggiunge informazione apposta, il budget si rigenera dopo aver guardato
il testo nuovo, mai per far passare il test:

    python tests/real/test_text_budget.py --generate
"""
import json
import sys
import unittest
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

import forge

# max_gap non ha default (D98); island_gap non esiste più (D99)
MAX_GAP = 0.5

SOURCE_DIR = project_root / "tests" / "data" / "golden_anchoring"
BUDGET = SOURCE_DIR / "text_budget.json"
FILES = [f"anch_{i:02d}.dxf" for i in range(1, 9)]


def reading(dxf_path: Path) -> str:
    result = forge.anchor_annotations(forge.island(forge.load_dxf(str(dxf_path)), max_gap=MAX_GAP), snap_distance=5.0)
    return forge.to_text(result, dxf_path.name)


class TestTextBudget(unittest.TestCase):
    pass


def _make_test(name: str):
    def test(self):
        dxf_path = SOURCE_DIR / name
        if not dxf_path.exists() or not BUDGET.exists():
            self.skipTest(name)
        budget = json.loads(BUDGET.read_text(encoding="utf-8"))[name]
        size = len(reading(dxf_path))
        print(f"{name}: {size} caratteri (budget {budget}, DXF {dxf_path.stat().st_size} byte)")
        self.assertLessEqual(size, budget, f"{name}: to_text è cresciuto oltre il budget")
    test.__name__ = f"test_{Path(name).stem}"
    return test


for _name in FILES:
    setattr(TestTextBudget, f"test_{Path(_name).stem}", _make_test(_name))


if __name__ == "__main__":
    if "--generate" in sys.argv:
        sizes = {name: len(reading(SOURCE_DIR / name)) for name in FILES if (SOURCE_DIR / name).exists()}
        BUDGET.write_text(json.dumps(sizes, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(sizes, indent=2))
    else:
        unittest.main()
