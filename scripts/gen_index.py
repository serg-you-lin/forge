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

Uso (da qualsiasi cartella; `scripts/` o `tests/`, dove il progetto tiene i generatori)::

    python scripts/gen_index.py            # scrive docs/INDEX.md
    python scripts/gen_index.py --check    # esce 1 se l'indice è obsoleto o un layer è violato
    python scripts/gen_index.py --similar  # corpi simili e frammenti ripetuti

Oltre all'inventario produce due controlli automatici:
    - nomi definiti a livello di modulo in più di un modulo (candidati doppioni)
    - violazioni della regola di dipendenza del package (per forge: `core` e
      `model` non importano `adapters`/`tools`/`io`)

`--similar` non scrive l'indice: confronta i corpi invece dei nomi (variabili
locali anonimizzate) e stampa funzioni uguali o quasi uguali sotto nomi
diversi e frammenti di istruzioni ripetuti in più funzioni. Candidati da
leggere, non verdetti.

Uguale in ogni progetto (la copia di riferimento sta nella skill
`code-guardrails`): si copia in `scripts/` così com'è e trova da sé il package
da indicizzare (la cartella con `__init__.py` nella radice del repo). La regola
dei layer è del progetto e sta nel suo `pyproject.toml`; un nome vietato può
essere un layer interno o un pacchetto esterno (`forge` per snapbend):

    [tool.gen_index.layers]
    core  = ["adapters", "tools", "io"]
    model = ["adapters", "tools", "io"]

Senza sezione l'indice si genera comunque e dice che non c'è nessuna regola.
"""

from __future__ import annotations

import argparse
import ast
import copy
import sys
import tomllib
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Iterable, Iterator, Optional

ROOT = Path(__file__).resolve().parent.parent
"""Radice del repo (la cartella di questo file ne è figlia)."""

SCRIPT = Path(__file__).resolve().relative_to(ROOT).as_posix()
"""Questo file, relativo alla radice: per il comando scritto nell'indice."""

OUTPUT = ROOT / "docs" / "INDEX.md"

DOC_MAX_CHARS = 110
"""Lunghezza massima della riga di docstring riportata in tabella."""

NOT_A_PACKAGE = {"dev_tools", "scripts", "tests", "build", "docs", "_archive"}
"""Cartelle che non sono il package da indicizzare, anche se hanno __init__.py."""



def load_layer_rule(root: Path) -> dict[str, tuple[str, ...]]:
    """La regola di dipendenza del progetto, da `[tool.gen_index.layers]` del suo pyproject."""
    pyproject = root / "pyproject.toml"
    if not pyproject.exists():
        return {}
    config = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    layers = config.get("tool", {}).get("gen_index", {}).get("layers", {})
    return {layer: tuple(forbidden) for layer, forbidden in layers.items()}


LAYER_RULE = load_layer_rule(ROOT)


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
    imports: set[str] = field(default_factory=set)   # moduli interni importati
    external: set[str] = field(default_factory=set)  # pacchetti esterni, primo livello
    loc: int = 0

    @property
    def layer(self) -> str:
        """Il primo livello sotto il package (`core`, `model`, ...); "(root)" per i file in cima."""
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

    # relativo: `.` è il package che contiene il file (per un __init__.py, il
    # package stesso), ogni punto in più risale di un livello
    package = module_path.removesuffix(".py").split("/")[:-1]
    base = package[: len(package) - (node.level - 1)]
    target = ".".join(base)
    if node.module:
        target = f"{target}.{node.module}" if target else node.module
    if target:
        found.add(target)
    return found


def external_imports(node: ast.Import | ast.ImportFrom, pkg_name: str) -> set[str]:
    """I pacchetti esterni (primo livello) importati da uno statement assoluto."""
    if isinstance(node, ast.Import):
        names = [alias.name for alias in node.names]
    elif node.level == 0 and node.module:
        names = [node.module]
    else:
        return set()
    return {n.split(".")[0] for n in names if n.split(".")[0] != pkg_name}


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
            module.external |= external_imports(node, pkg_name)

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
    violations: list[tuple[str, str]] = []
    for module in modules:
        forbidden = LAYER_RULE.get(module.layer)
        if not forbidden:
            continue
        for imported in sorted(module.imports):
            tail = imported.removeprefix(f"{pkg_name}.").split(".")[0]
            if tail in forbidden:
                violations.append((module.path, imported))
        for package in sorted(module.external & set(forbidden)):
            violations.append((module.path, package))
    return violations


# --------------------------------------------------------------------------- #
# corpi simili: lo stesso lavoro sotto nomi diversi (`--similar`)
# --------------------------------------------------------------------------- #

SIMILAR_RATIO = 0.85     # soglia di somiglianza tra due corpi normalizzati
SIMILAR_MIN_NODES = 40   # sotto, due funzioni corte si somigliano per forza
WINDOW_STATEMENTS = 2    # istruzioni consecutive di un frammento ripetuto
WINDOW_MIN_NODES = 15    # nodi minimi del frammento, per scartare gli ovvi


@dataclass
class Body:
    """Una funzione o un metodo, col corpo normalizzato."""

    name: str                      # `f` o `Classe.f`
    location: str
    shape: str                     # dump del corpo normalizzato
    tokens: list[str]
    size: int                      # nodi ast del corpo


class _Anonymize(ast.NodeTransformer):
    """Rinomina parametri e variabili locali in `v0, v1, ...` nell'ordine in cui
    compaiono: due corpi che differiscono solo per quei nomi diventano uguali.
    Nomi globali, attributi e costanti restano: portano il significato."""

    def __init__(self, local: set[str]) -> None:
        self.local = local
        self.names: dict[str, str] = {}

    def _rename(self, name: str) -> str:
        return self.names.setdefault(name, f"v{len(self.names)}")

    def visit_Name(self, node: ast.Name) -> ast.AST:
        if node.id in self.local:
            return ast.copy_location(ast.Name(id=self._rename(node.id), ctx=node.ctx), node)
        return node

    def visit_arg(self, node: ast.arg) -> ast.AST:
        node.arg = self._rename(node.arg)
        node.annotation = None
        return node


def _local_names(nodes: list[ast.AST]) -> set[str]:
    """Nomi assegnati o ricevuti come parametro dentro `nodes`."""
    local: set[str] = set()
    for root in nodes:
        for node in ast.walk(root):
            if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
                local.add(node.id)
            elif isinstance(node, ast.arg):
                local.add(node.arg)
    return local


def _strip_docstring(body: list[ast.stmt]) -> list[ast.stmt]:
    first = body[0] if body else None
    if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) \
            and isinstance(first.value.value, str):
        return body[1:]
    return body


def _normalize(nodes: list[ast.AST], extra_local: Iterable[str] = ()) -> list[ast.AST]:
    """Copia di `nodes` con i nomi locali anonimizzati."""
    nodes = [copy.deepcopy(n) for n in nodes]
    renamer = _Anonymize(_local_names(nodes) | set(extra_local))
    return [renamer.visit(n) for n in nodes]


def _tokens(nodes: list[ast.AST]) -> list[str]:
    out: list[str] = []
    for root in nodes:
        for node in ast.walk(root):
            out.append(type(node).__name__)
            for attr in ("id", "attr", "arg"):
                if hasattr(node, attr):
                    out.append(str(getattr(node, attr)))
    return out


def _size(nodes: list[ast.AST]) -> int:
    return sum(1 for root in nodes for _ in ast.walk(root))


def _iter_functions(tree: ast.Module) -> Iterator[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]]:
    """Funzioni di modulo e metodi di classe (non le funzioni annidate)."""
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node.name, node
        elif isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    yield f"{node.name}.{item.name}", item


def read_bodies(path: Path) -> list[Body]:
    """Le funzioni e i metodi di un file, coi corpi normalizzati."""
    rel = path.relative_to(ROOT).as_posix()
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    bodies = []
    for name, fn in _iter_functions(tree):
        body = _strip_docstring(fn.body)
        if not body:
            continue
        params = [a.arg for a in ast.walk(fn.args) if isinstance(a, ast.arg)]
        norm = _normalize(body, params)
        bodies.append(Body(
            name=name, location=f"{rel}:{fn.lineno}",
            shape="|".join(ast.dump(n) for n in norm), tokens=_tokens(norm), size=_size(body),
        ))
    return bodies


def find_same_bodies(bodies: list[Body]) -> list[list[Body]]:
    """Gruppi di funzioni con corpo identico a meno dei nomi locali."""
    groups: dict[str, list[Body]] = {}
    for b in bodies:
        if b.size >= SIMILAR_MIN_NODES // 2:
            groups.setdefault(b.shape, []).append(b)
    return [g for g in groups.values() if len(g) > 1]


def find_similar_bodies(bodies: list[Body]) -> list[tuple[float, Body, Body]]:
    """Coppie di corpi quasi uguali (non identici), dalla più simile."""
    big = [b for b in bodies if b.size >= SIMILAR_MIN_NODES]
    pairs = []
    for i, a in enumerate(big):
        for b in big[i + 1:]:
            la, lb = len(a.tokens), len(b.tokens)
            if a.shape == b.shape or min(la, lb) / max(la, lb) < SIMILAR_RATIO:
                continue
            m = SequenceMatcher(None, a.tokens, b.tokens, autojunk=False)
            if m.quick_ratio() < SIMILAR_RATIO:
                continue
            r = m.ratio()
            if r >= SIMILAR_RATIO:
                pairs.append((r, a, b))
    return sorted(pairs, key=lambda t: -t[0])


def find_repeated_fragments(paths: list[Path]) -> list[tuple[str, list[str]]]:
    """Sequenze di WINDOW_STATEMENTS istruzioni consecutive che compaiono, a meno
    dei nomi locali, in più di una funzione: candidati a una microfunzione.
    Ritorna (testo del frammento, posizioni `file:riga`)."""
    seen: dict[str, list[tuple[str, str, str]]] = {}
    for path in paths:
        rel = path.relative_to(ROOT).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for name, fn in _iter_functions(tree):
            for block in ast.walk(fn):
                for field_name in ("body", "orelse", "finalbody"):
                    stmts = getattr(block, field_name, None)
                    if not isinstance(stmts, list) or not stmts or not isinstance(stmts[0], ast.stmt):
                        continue
                    stmts = _strip_docstring(stmts)
                    for i in range(len(stmts) - WINDOW_STATEMENTS + 1):
                        win = stmts[i:i + WINDOW_STATEMENTS]
                        if _size(win) < WINDOW_MIN_NODES:
                            continue
                        key = "|".join(ast.dump(n) for n in _normalize(win))
                        seen.setdefault(key, []).append((
                            f"{rel}:{win[0].lineno}", f"{rel}::{name}",
                            "\n".join(ast.unparse(n) for n in win)))
    found = sorted(
        (occ[0][2], sorted(o[0] for o in occ))
        for occ in seen.values() if len({o[1] for o in occ}) > 1
    )
    found.sort(key=lambda t: t[1])
    # un frammento più lungo della finestra dà finestre sovrapposte: le fondo
    merged: list[tuple[str, list[str]]] = []
    for text, locs in found:
        if merged and _shifted(merged[-1][1], locs):
            continue
        merged.append((text, locs))
    return sorted(merged, key=lambda t: -len(t[1]))


def _shifted(a: list[str], b: list[str]) -> bool:
    """Le posizioni `b` sono le `a` spostate in avanti di poche righe."""
    if len(a) != len(b):
        return False
    for x, y in zip(a, b):
        fx, lx = x.rsplit(":", 1)
        fy, ly = y.rsplit(":", 1)
        if fx != fy or not 0 < int(ly) - int(lx) <= 8:
            return False
    return True


def report_similar(package: Path) -> str:
    """Il testo del rapporto `--similar`."""
    paths = list(iter_sources(package))
    bodies = [b for p in paths for b in read_bodies(p)]
    lines = [f"# corpi analizzati: {len(bodies)}", "", "## stesso corpo (a meno dei nomi locali)"]
    for g in find_same_bodies(bodies):
        lines.append("- " + " · ".join(f"{b.name} ({b.location})" for b in g))
    lines += ["", f"## corpi quasi uguali (>= {SIMILAR_RATIO:.0%})"]
    for r, a, b in find_similar_bodies(bodies):
        lines.append(f"- {r:.0%}  {a.name} ({a.location})  ~  {b.name} ({b.location})")
    lines += ["", f"## frammenti ripetuti ({WINDOW_STATEMENTS}+ istruzioni)"]
    for text, locs in find_repeated_fragments(paths):
        lines.append(f"- {len(locs)}x  " + " · ".join(locs))
        lines += ["      " + t for t in text.splitlines()[:8]]
    return "\n".join(lines) + "\n"


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
    layer_rule = LAYER_RULE
    total_loc = sum(m.loc for m in modules)

    out: list[str] = []
    w = out.append

    w(f"# {pkg_name} — code index")
    w("")
    w("**Generated file — do not edit by hand.** Regenerate with:")
    w("")
    w("```")
    w(f"python {SCRIPT}")
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
        w(f"No dependency rule configured for `{pkg_name}` — add "
          "`[tool.gen_index.layers]` to `pyproject.toml` to have it checked here.")
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
    parser.add_argument("--similar", action="store_true",
                        help="non scrive: stampa corpi uguali o simili sotto nomi diversi "
                             "e frammenti ripetuti")
    parser.add_argument("--package", default=None,
                        help="nome della cartella del package (default: trovata da sé)")
    args = parser.parse_args(argv)

    package = (ROOT / args.package) if args.package else find_package(ROOT)
    if not (package / "__init__.py").exists():
        raise SystemExit(f"{package} non è un package (nessun __init__.py)")

    if args.similar:
        sys.stdout.reconfigure(encoding="utf-8")
        print(report_similar(package), end="")
        return 0

    text = build(package)

    if args.check:
        modules = [read_module(path, package.name) for path in iter_sources(package)]
        violations = find_layer_violations(modules, package.name)
        for module_path, imported in violations:
            print(f"dependency rule: {module_path} imports {imported}")
        if not OUTPUT.exists():
            print(f"{OUTPUT.relative_to(ROOT).as_posix()} missing — run gen_index.py")
            return 1
        if OUTPUT.read_text(encoding="utf-8") != text:
            print(f"{OUTPUT.relative_to(ROOT).as_posix()} is stale — run gen_index.py")
            return 1
        print(f"{OUTPUT.relative_to(ROOT).as_posix()} up to date")
        return 1 if violations else 0

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(text, encoding="utf-8")
    print(f"written {OUTPUT.relative_to(ROOT).as_posix()} ({len(text.splitlines())} lines)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
