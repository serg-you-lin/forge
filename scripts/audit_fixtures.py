"""
scripts/audit_fixtures.py
-------------------------
Dice quali disegni la suite usa senza averli in git: i file che su questa
macchina ci sono e su un clone pulito no.

Perché esiste: un golden senza il suo DXF padre non fallisce, fa `skipTest`.
La suite resta verde e sembra tutto a posto, ma chi scarica il progetto sta
girando meno test di quanti ne vede passare — e nessuno glielo dice.

Due strade per arrivare a un disegno, entrambe guardate qui:

1. **I padri dei golden.** Ogni golden porta dentro il nome del disegno da cui
   è stato prodotto (`source_file`, `parent_file`), risolto come fa il test che
   lo usa: `golden/` per `test_golden`, `golden_multipli/` per
   `test_golden_split`, e per le annotazioni la ricerca in `examples/` prima di
   `examples/golden/`.
2. **I fixture nominati a codice**, cioè le stringhe `"qualcosa.dxf"` dentro i
   test: lì il disegno non è scritto in nessun golden, lo nomina il test.

Uso (da qualsiasi cartella)::

    python scripts/audit_fixtures.py            # il referto, con dimensione e audit
    python scripts/audit_fixtures.py --strict   # esce 1 se manca almeno un file
    python scripts/audit_fixtures.py --list     # solo i percorsi, da dare a git

Mettere in git un disegno è una decisione di Federico, non di questo script:
per questo `--list` si ferma a stampare la lista.

    python scripts/audit_fixtures.py --list > fixtures.txt
    git add -f --pathspec-from-file=fixtures.txt

`--pathspec-from-file` e non `$(cat ...)`: un fixture ha uno spazio nel nome, e
la sostituzione di shell lo spezzerebbe in due percorsi che non esistono.

Ogni file della lista passa dai controlli di `audit_names.py` (nome e contenuto
del disegno) prima di essere proposto: la colonna lo dice.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import audit_names

ROOT = Path(__file__).resolve().parent.parent
"""Radice del repo (scripts/ ne è figlia)."""

DATA = ROOT / "tests" / "data"
"""La radice tracciata che la suite legge. Un disegno qui dentro e' in git per
il fatto di stare qui (`.gitignore` tiene `tests/data/**`), non per un
`git add -f` che qualcuno si e' ricordato di dare."""

GOLDEN = DATA / "golden"
MULTIPLI = DATA / "golden_multipli"

DXF_LITERAL = re.compile(r'["\']([^"\'*{]+\.(?:dxf|DXF))["\']')
"""Una stringa che nomina un disegno dentro un test. Esclude i modelli con
`*` o `{}`: quelli sono pattern di glob o f-string, non nomi di file."""


def tracked_lower() -> set[str]:
    """I path tracciati, minuscoli: su Windows `x.DXF` e `x.dxf` sono lo stesso
    file, e confrontarli caso-sensibile direbbe che manca un file che c'è."""
    raw = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT,
                         capture_output=True, check=True).stdout
    return {path.lower() for path in raw.decode("utf-8").split("\0") if path}


def _golden_parents() -> set[Path]:
    """I disegni padre nominati dentro i golden, risolti come fa ogni test."""
    found: set[Path] = set()

    def add(path: Path | None) -> None:
        if path is not None and path.exists():
            found.add(path)

    for golden in sorted((GOLDEN / "json").glob("*.json")):
        data = json.loads(golden.read_text(encoding="utf-8"))
        add(GOLDEN / data["source_file"])

    for golden in sorted((GOLDEN / "annotations").glob("*.json")):
        name = json.loads(golden.read_text(encoding="utf-8"))["source_file"]
        add(next((base / name for base in (DATA, GOLDEN)
                  if (base / name).exists()), None))

    for golden in sorted((MULTIPLI / "golden").glob("*.json")):
        data = json.loads(golden.read_text(encoding="utf-8"))
        add(MULTIPLI / data["parent_file"])

    return found


def _named_in_tests() -> set[Path]:
    """I disegni che un test nomina a codice, cercati dove il test li cerca."""
    found: set[Path] = set()
    for module in sorted((ROOT / "tests").rglob("*.py")):
        if "__pycache__" in module.as_posix():
            continue
        text = module.read_text(encoding="utf-8", errors="replace")
        for name in DXF_LITERAL.findall(text):
            base = name.rsplit("/", 1)[-1]
            for candidate in (DATA / base, GOLDEN / base):
                if candidate.exists():
                    found.add(candidate)
                    break
    return found


def missing_fixtures() -> list[str]:
    """I disegni che servono alla suite e non sono tracciati."""
    tracked = tracked_lower()
    needed = _golden_parents() | _named_in_tests()
    out = {p.relative_to(ROOT).as_posix() for p in needed}
    return sorted(rel for rel in out if rel.lower() not in tracked)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Disegni che la suite usa e che non sono in git.")
    parser.add_argument("--strict", action="store_true",
                        help="esce 1 se manca almeno un disegno")
    parser.add_argument("--list", action="store_true", dest="only_list",
                        help="stampa solo i percorsi, uno per riga")
    args = parser.parse_args(argv)

    missing = missing_fixtures()

    if args.only_list:
        for rel in missing:
            print(rel)
        return 1 if (missing and args.strict) else 0

    if not missing:
        print("tutti i disegni che la suite usa sono in git.")
        return 0

    print(f"disegni usati dalla suite e non tracciati: {len(missing)}\n")
    total_kb = 0.0
    da_ripulire = 0
    for rel in missing:
        path = ROOT / rel
        kb = path.stat().st_size / 1024
        total_kb += kb
        sospetti = audit_names.name_suspicions(rel) or \
            audit_names.drawing_suspicions(path)
        if sospetti:
            da_ripulire += 1
        verdetto = "DA RIPULIRE" if sospetti else "pulito"
        print(f"   {verdetto:12} {kb:7.0f} KB  {rel}")

    print(f"\ntotale {total_kb / 1024:.2f} MB; da ripulire prima di git: {da_ripulire}")
    print("Metterli in git è una decisione tua:\n"
          "   python scripts/audit_fixtures.py --list > fixtures.txt\n"
          "   git add -f --pathspec-from-file=fixtures.txt")
    return 1 if args.strict else 0


if __name__ == "__main__":
    sys.exit(main())
