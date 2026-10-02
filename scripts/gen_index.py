"""
scripts/gen_index.py
----------------------
Genera `docs/INDEX.md`: l'inventario completo di cosa esiste già nel package.

Perché esiste: `docs/API.md` documenta la superficie pubblica (i nomi
`forge.<name>`), ma la maggior parte delle funzioni del package è interna, e
una funzione che nessuno sa di avere viene riscritta. Questo indice è la
tabella di lookup — "esiste già qualcosa che calcola una distanza punto-retta?"
— e va rigenerato, non scritto a mano, perché un elenco scritto a mano mente al
primo commit successivo.

Legge i sorgenti con `ast`: non importa `forge`, quindi nessun side effect e
nessuna dipendenza oltre la standard library.

Uso (da qualsiasi cartella)::

    python scripts/gen_index.py            # scrive docs/INDEX.md
    python scripts/gen_index.py --check    # esce 1 se l'indice è obsoleto

Oltre all'inventario produce due controlli automatici:
    - nomi definiti a livello di modulo in più di un modulo (candidati doppioni)
    - violazioni della regola di dipendenza del package (per forge: `core` e
      `model` non importano `adapters`/`tools`/`io`)

Riusabile negli altri progetti della famiglia (snapbend, snapdraw, ...): il file
si copia in `scripts/` così com'è, trova da sé il package da indicizzare (la
cartella con `__init__.py` nella radice del repo). Per avere anche il controllo
dei layer basta aggiungere una voce a `LAYER_RULES`; senza voce l'indice si
genera comunque e quella sezione dice che non c'è nessuna regola configurata.
"""

from __future__ import annotations

import argparse
import ast
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Iterator, Optional

ROOT = Path(__file__).resolve().parent.parent
"""Radice del repo (scripts/ ne è figlia)."""

OUTPUT = ROOT / "docs" / "INDEX.md"

DOC_MAX_CHARS = 110
"""Lunghezza massima della riga di docstring riportata in tabella."""

NOT_A_PACKAGE = {"dev_tools", "scripts", "tests", "build", "docs", "_archive"}
"""Cartelle che non sono il package da indicizzare, anche se hanno __init__.py."""

# Regola di dipendenza per package: dentro un package, chi sta a sinistra non può
# importare nessuno dei layer a destra. Per forge è quella di ARCHITECTURE.md /
# MAP.md D44. Un package senza voce qui salta il controllo.
LAYER_RULES: dict[str, dict[str, tuple[str, ...]]] = {
    "forge": {
        "core": ("adapters", "tools", "io"),
        "model": ("adapters", "tools", "io"),
    },
}


def find_package(root: Path) -> Path:
    """La cartella del package da indicizzare: quella con `__init__.py`.

    Più di una candidata (o nessuna) è un errore esplicito: meglio chiedere
    `--package` che indicizzare la cartella sbagliata in silenzio.
    """
    candidates = [
        child for child in sorted(root.iterdir())
        if child.is_dir()
        and child.name not in NOT_A_PACKAGE
        and not child.name.startswith((".", "_"))
        and (child / "__init__.py").exists()
    ]
    if len(candidates) == 1:
        return candidates[0]
    names = ", ".join(c.name for c in candidates) or "nessuna"
    raise SystemExit(
        f"impossibile scegliere il package in {root} (candidate: {names}) — "
        f"passa --package NOME"
    )


# --------------------------------------------------------------------------- #
# modello dei dati estratti
# --------------------------------------------------------------------------- #

@dataclass
class Symbol:
    """Una funzione o una classe a livello di modulo."""

    name: str
    kind: str                      # "func" | "class"
    signature: str
    doc: str
    line: int
    module: str                    # percorso posix relativo alla radice
    methods: list[str] = field(default_factory=list)

    @property
    def location(self) -> str:
        """`file:riga`, cliccabile in un terminale."""
        return f"{self.module}:{self.line}"


@dataclass
class Module:
    """Un file del package, con i suoi simboli e le sue dipendenze interne."""

    path: str                      # percorso posix relativo alla radice
    doc: str
    symbols: list[Symbol] = field(default_factory=list)
    imports: set[str] = field(default_factory=set)   # moduli forge importati
    loc: int = 0

    @property
    def layer(self) -> str:
        """Il primo livello sotto `forge/` (`core`, `model`, `tools`...)."""
        parts = self.path.split("/")
        return parts[1] if len(parts) > 2 else "(root)"


# --------------------------------------------------------------------------- #
# estrazione
# --------------------------------------------------------------------------- #

def first_doc_line(node: ast.AST) -> str:
    """Prima riga non vuota del docstring, troncata. Stringa vuota se assente."""
    raw = ast.get_docstring(node, clean=True)
    if not raw:
        return ""
    for line in raw.splitlines():
        text = line.strip()
        if not text:
            continue
        # una riga di sottolineatura (---- o ====) non è contenuto
        if set(text) <= {"-", "=", "~"}:
            continue
        if len(text) > DOC_MAX_CHARS:
            text = text[: DOC_MAX_CHARS - 1].rstrip() + "…"
        return text.replace("|", "\\|")
    return ""


def render_signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    """La riga `def ...` senza corpo né decoratori, via `ast.unparse`."""
    stub = ast.FunctionDef(
        name=node.name,
        args=node.args,
        body=[ast.Expr(value=ast.Constant(value=Ellipsis))],
        decorator_list=[],
        returns=node.returns,
        type_comment=None,
        type_params=[],
    )
    ast.fix_missing_locations(stub)
    head = ast.unparse(stub).splitlines()[0]
    return head.removeprefix("def ").removesuffix(":").replace("|", "\\|")


def class_methods(node: ast.ClassDef) -> list[str]:
    """Metodi pubblici della classe, più `__init__` se definito a mano."""
    out: list[str] = []
    for item in node.body:
        if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if item.name.startswith("__") and item.name != "__init__":
            continue
        out.append(item.name)
    return out


def resolve_import(node: ast.Import | ast.ImportFrom, module_path: str,
                   pkg_name: str) -> set[str]:
    """I moduli interni al package importati da uno statement, come nomi puntati."""
    found: set[str] = set()
    if isinstance(node, ast.Import):
        for alias in node.names:
            if alias.name.split(".")[0] == pkg_name:
                found.add(alias.name)
        return found

    # ImportFrom: può essere assoluto (`from <pkg>.core...`) o relativo
    if node.level == 0:
        if node.module and node.module.split(".")[0] == pkg_name:
            found.add(node.module)
        return found

    # relativo: risale di `level` dal package del modulo corrente
    parts = module_path.removesuffix(".py").split("/")
    if parts[-1] == "__init__":
        parts = parts[:-1]
    base = parts[: len(parts) - (node.level - 1)] if node.level > 1 else parts[:-1]
    target = ".".join(base)
    if node.module:
        target = f"{target}.{node.module}" if target else node.module
    if target:
        found.add(target)
    return found


def read_module(path: Path, pkg_name: str) -> Module:
    """Estrae simboli e dipendenze di un file, senza importarlo."""
    source = path.read_text(encoding="utf-8")
    rel = path.relative_to(ROOT).as_posix()
    tree = ast.parse(source, filename=str(path))

    module = Module(path=rel, doc=first_doc_line(tree), loc=len(source.splitlines()))

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            module.symbols.append(Symbol(
                name=node.name,
                kind="func",
                signature=render_signature(node),
                doc=first_doc_line(node),
                line=node.lineno,
                module=rel,
            ))
        elif isinstance(node, ast.ClassDef):
            bases = ", ".join(ast.unparse(b) for b in node.bases)
            module.symbols.append(Symbol(
                name=node.name,
                kind="class",
                signature=f"{node.name}({bases})" if bases else node.name,
                doc=first_doc_line(node),
                line=node.lineno,
                module=rel,
                methods=class_methods(node),
            ))

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            module.imports |= resolve_import(node, rel, pkg_name)

    return module


def iter_sources(package: Path) -> Iterator[Path]:
    """I file .py del package, in ordine di percorso."""
    for path in sorted(package.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        yield path


# --------------------------------------------------------------------------- #
# controlli
# --------------------------------------------------------------------------- #

def find_duplicate_names(modules: Iterable[Module]) -> dict[str, list[Symbol]]:
    """Nomi definiti a livello di modulo in più di un modulo.

    Solo simboli top-level: lo stesso nome di metodo su dataclass diverse
    (`to_dict`, `discretize`) è normale e non è un doppione.
    """
    by_name: dict[str, list[Symbol]] = {}
    for module in modules:
        for symbol in module.symbols:
            by_name.setdefault(symbol.name, []).append(symbol)
    return {
        name: syms
        for name, syms in sorted(by_name.items())
        if len({s.module for s in syms}) > 1
    }


def find_layer_violations(modules: Iterable[Module],
                          pkg_name: str) -> list[tuple[str, str]]:
    """Import che violano la regola di dipendenza, come (modulo, import)."""
    rule = LAYER_RULES.get(pkg_name, {})
    violations: list[tuple[str, str]] = []
    for module in modules:
        forbidden = rule.get(module.layer)
        if not forbidden:
            continue
        for imported in sorted(module.imports):
            tail = imported.removeprefix(f"{pkg_name}.").split(".")[0]
            if tail in forbidden:
                violations.append((module.path, imported))
    return violations


# --------------------------------------------------------------------------- #
# rendering
# --------------------------------------------------------------------------- #

def render(modules: list[Module], pkg_name: str) -> str:
    """Il testo completo di docs/INDEX.md."""
    all_symbols = [s for m in modules for s in m.symbols]
    funcs = [s for s in all_symbols if s.kind == "func"]
    classes = [s for s in all_symbols if s.kind == "class"]
    duplicates = find_duplicate_names(modules)
    violations = find_layer_violations(modules, pkg_name)
    layer_rule = LAYER_RULES.get(pkg_name, {})
    total_loc = sum(m.loc for m in modules)

    out: list[str] = []
    w = out.append

    w(f"# {pkg_name} — code index")
    w("")
    w("**Generated file — do not edit by hand.** Regenerate with:")
    w("")
    w("```")
    w("python scripts/gen_index.py")
    w("```")
    w("")
    w("What this is: the lookup table of *what already exists* in the package, "
      "down to internal helpers. `docs/API.md` documents the public surface "
      f"(`{pkg_name}.<name>`) with full cards; this file lists every module-level "
      "function and class so nothing gets rewritten because it was not found. "
      "Signatures and docstring lines come straight from the source, so they "
      "cannot drift.")
    w("")
    w(f"`{len(modules)}` modules · `{len(funcs)}` module-level functions · "
      f"`{len(classes)}` classes · `{total_loc}` lines of code.")
    w("")
    w("Sections: [Lookup](#lookup) · [Duplicate names](#duplicate-names) · "
      "[Dependency rule](#dependency-rule) · [By module](#by-module) · "
      "[Internal dependencies](#internal-dependencies)")
    w("")
    w("---")
    w("")

    # --- lookup alfabetico ---------------------------------------------------
    w("## Lookup")
    w("")
    w("Every module-level name in the package, alphabetically. "
      "**Search here before writing a new helper.**")
    w("")
    w("| name | kind | location | what |")
    w("|---|---|---|---|")
    for symbol in sorted(all_symbols, key=lambda s: (s.name.lstrip("_").lower(), s.module)):
        kind = "class" if symbol.kind == "class" else "func"
        w(f"| `{symbol.name}` | {kind} | `{symbol.location}` | {symbol.doc} |")
    w("")

    # --- doppioni -----------------------------------------------------------
    w("## Duplicate names")
    w("")
    if not duplicates:
        w("No module-level name is defined in more than one module.")
    else:
        w("Same name defined at module level in different modules. Not "
          "automatically a bug — but each one is either two implementations of "
          "one job (merge them) or two different jobs sharing a name (rename "
          "one).")
        w("")
        w("| name | defined in |")
        w("|---|---|")
        for name, syms in duplicates.items():
            places = " · ".join(f"`{s.location}`" for s in syms)
            w(f"| `{name}` | {places} |")
    w("")

    # --- regola di dipendenza ----------------------------------------------
    w("## Dependency rule")
    w("")
    if not layer_rule:
        w(f"No dependency rule configured for `{pkg_name}` — add one to "
          "`LAYER_RULES` in `scripts/gen_index.py` to have it checked here.")
    else:
        for layer, forbidden in layer_rule.items():
            forbidden_list = ", ".join(f"`{f}`" for f in forbidden)
            w(f"- `{layer}` never imports {forbidden_list}")
        w("")
        w("`TYPE_CHECKING`-only imports count as violations here and must be "
          "verified by hand.")
        w("")
        if not violations:
            w("**Clean** — no violation found.")
        else:
            w("| module | forbidden import |")
            w("|---|---|")
            for module_path, imported in violations:
                w(f"| `{module_path}` | `{imported}` |")
    w("")

    # --- per modulo ---------------------------------------------------------
    w("## By module")
    w("")
    current_layer = None
    for module in modules:
        if module.layer != current_layer:
            current_layer = module.layer
            w(f"### `{pkg_name}/{current_layer}/`" if current_layer != "(root)"
              else f"### `{pkg_name}/` (root)")
            w("")
        w(f"#### `{module.path}` — {module.loc} lines")
        w("")
        if module.doc:
            w(f"_{module.doc}_")
            w("")
        if not module.symbols:
            w("No module-level function or class.")
            w("")
            continue
        for symbol in module.symbols:
            if symbol.kind == "func":
                w(f"- `{symbol.signature}` — L{symbol.line}"
                  + (f" — {symbol.doc}" if symbol.doc else ""))
            else:
                w(f"- **class** `{symbol.signature}` — L{symbol.line}"
                  + (f" — {symbol.doc}" if symbol.doc else ""))
                if symbol.methods:
                    w(f"  - methods: {', '.join(f'`{m}`' for m in symbol.methods)}")
        w("")

    # --- dipendenze interne -------------------------------------------------
    w("## Internal dependencies")
    w("")
    w(f"Which `{pkg_name}` modules each module imports — \"what works with "
      "what\". Modules with no internal import are omitted.")
    w("")
    w("| module | imports |")
    w("|---|---|")
    for module in modules:
        if not module.imports:
            continue
        imported = " · ".join(f"`{name}`" for name in sorted(module.imports))
        w(f"| `{module.path}` | {imported} |")
    w("")

    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------- #
# entry point
# --------------------------------------------------------------------------- #

def build(package: Path) -> str:
    """Legge il package e ritorna il testo dell'indice."""
    pkg_name = package.name
    modules = [read_module(path, pkg_name) for path in iter_sources(package)]
    return render(modules, pkg_name)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Genera docs/INDEX.md: l'inventario dei nomi del package.")
    parser.add_argument("--check", action="store_true",
                        help="non scrive: esce 1 se docs/INDEX.md è obsoleto")
    parser.add_argument("--package", default=None,
                        help="nome della cartella del package (default: trovata da sé)")
    args = parser.parse_args(argv)

    package = (ROOT / args.package) if args.package else find_package(ROOT)
    if not (package / "__init__.py").exists():
        raise SystemExit(f"{package} non è un package (nessun __init__.py)")

    text = build(package)

    if args.check:
        if not OUTPUT.exists():
            print(f"{OUTPUT.relative_to(ROOT).as_posix()} missing — run gen_index.py")
            return 1
        if OUTPUT.read_text(encoding="utf-8") != text:
            print(f"{OUTPUT.relative_to(ROOT).as_posix()} is stale — run gen_index.py")
            return 1
        print(f"{OUTPUT.relative_to(ROOT).as_posix()} up to date")
        return 0

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(text, encoding="utf-8")
    print(f"written {OUTPUT.relative_to(ROOT).as_posix()} ({len(text.splitlines())} lines)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
