"""
forge/tools/anonymize.py
------------------------
Ripulire un disegno cliente per farne un fixture pubblicabile.

Serve a forge e a ogni suo consumatore: i test si fanno per forza con disegni
veri, quindi il passaggio che li rende pubblicabili è uno strumento, non
un'abitudine. Due modalità, e la prima non è automatizzabile:

- `scan_dxf()` — elenca **tutto quello che è scritto** dentro il disegno:
  testi, nomi di layer, di blocco, di stile, percorsi di salvataggio, variabili
  d'intestazione, XDATA, commenti. Da leggere con l'occhio. Un *codice* ha una
  forma e un pattern lo trova; un *nome* no: il nome di uno studio usato come
  nome di uno stile di quota non lo becca nessuna espressione regolare, lo
  vede una persona.
- `clean_dxf()` — applica una mappa `originale → sostituto` a quelle stringhe e
  basta a quelle. Numeri e struttura non vengono toccati.

Il fixture deve restare il file che è: nessun round-trip attraverso il modello
di forge (`load_dxf` → `heal` → `to_dxf` restituisce la *lettura* di forge, non
il file, e spline strane, entità fuori contorno e `Trash` — cioè ciò che rende
quel disegno un caso di prova — non tornerebbero uguali). Per questo si lavora
sulle coppie (codice, valore) del DXF ASCII: vedi `adapters/dxf/tags.py`.

La verifica la fa forge stessa: `clean_dxf(verify=True)` chiama `heal()` prima e
dopo e confronta numero di cluster, aree, perimetri, bbox e `trash`. Se un
numero cambia, la pulitura ha toccato la geometria e la funzione solleva invece
di scrivere.

Due cose imparate sul campo (MAP.md D76):
- una stringa si **sostituisce, non si cancella**: togliere il testo del
  cartiglio cambia quello che vedono `annotations` e `inject()`;
- un nome di layer va sostituito in *tutti* i posti dove compare (record di
  tabella, blocchi, gruppo `8` di ogni entità) — qui è automatico, perché la
  mappa si applica per valore e non per posizione.

Non è dato cliente la **marcatura**: il testo che ripete il numero del pezzo lo
scrive il CAD per ogni pezzo tagliato, è il nome del normalino e può stare in
git. `scan` la mostra come tutto il resto, ma non c'è ragione di sostituirla.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

from forge.adapters.dxf.tags import DxfTag, TaggedFile, read_tags

# ---------------------------------------------------------------------------
# Dove, in un DXF, può finire una stringa scritta da una persona
# ---------------------------------------------------------------------------

TEXT_CODES = {"1", "3", "304"}
"""Valore di TEXT/MTEXT/ATTRIB e le sue continuazioni."""

NAME_CODES = {"2"}
"""Nome di un record di tabella (layer, stile di quota, stile di testo...),
nome di un blocco, tag di un attributo."""

STYLE_CODES = {"6", "7"}
"""Nome di linetype (`6`) e di stile di testo (`7`) riferiti da un'entità."""

LAYER_CODES = {"8"}
"""Layer di un'entità."""

ARBITRARY_CODES = {str(code) for code in range(300, 310)} | {"1000", "1001"}
"""Testo arbitrario in un XRECORD (300-309) e stringhe XDATA (1000, 1001)."""

HEADER_NAME_CODE = "9"
"""Nome di una variabile d'intestazione: il valore sta nella coppia dopo."""

COMMENT_CODE = "999"
"""Commento, scritto da chi ha generato il file."""

SCANNED_CODES = (TEXT_CODES | NAME_CODES | STYLE_CODES | LAYER_CODES
                 | ARBITRARY_CODES | {HEADER_NAME_CODE, COMMENT_CODE})

ABSOLUTE_PATH = re.compile(r"^(\\\\[^\\]|[A-Za-z]:[\\/])")
"""Percorso assoluto, UNC o con lettera di unità: nomina una cartella di rete,
una commessa, un utente. Da trattare come sospetto in sé."""

# ---------------------------------------------------------------------------
# Quello che il formato scrive da sé, e che nessuno deve leggere a mano
# ---------------------------------------------------------------------------

_GUID = re.compile(r"^\{?[0-9A-Fa-f]{8}(-[0-9A-Fa-f]{4}){3}-[0-9A-Fa-f]{12}\}?$")
_ISO_STAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")
_HEX_BLOB = re.compile(r"^[0-9A-Fa-f]{14,}$")
_NUMBERISH = re.compile(r"^[-+]?[\d.,]+(mm|MM|°)?$")
_INTERNAL_PREFIX = re.compile(
    r"^(ACAD|ACDB|AcDb|AcAd|AcCm|AcDs|ADSK|AEC_|ASDK|AST|Ast|ODA|OdDb|ANSI_|"
    r"Arrowhead|Balloon|AM_|ACIS|Am[a-z]|GENAX)", re.IGNORECASE)
_INTERNAL_EXACT = frozenset({
    "ByLayer", "ByBlock", "Standard", "STANDARD", "Normal", "Continuous",
    "CONTINUOUS", "Annotative", "Defpoints", "DEFPOINTS", "Model", "MODEL",
    "Basic", "Global", "Export", "Media", "Glass", "Group",
    "2dWireframe", "3dWireframe", "3D Hidden", "Conceptual", "Realistic",
    "Shaded", "Shades of Gray", "Sketchy", "Wireframe", "X-Ray",
    "HEADER", "CLASSES", "TABLES", "BLOCKS", "ENTITIES", "OBJECTS", "LTYPE",
    "STYLE", "APPID", "QUOTE", "BLOCK_RECORD", "PLOTSETTINGS",
})
_LINETYPE_PATTERN = re.compile(r"^[A-Za-z0-9 ().x]*[_.]{2,}")
"""La descrizione di un linetype (`Border __ __ . __ __ .`): è un disegnino."""
_RESERVED_NAME = re.compile(r"^[*_]")
"""Nome riservato del formato (`*Model_Space`, `_OBLIQUE`): lo scrive il CAD."""
_VERSION_TAG = re.compile(r"^AC\d{4}$")
"""Sigla di versione del formato (`AC1015`)."""
_SHORT_KEY = re.compile(r"^[A-Za-z]\d{1,2}$")
"""Chiave breve di un dizionario (`A1`, `B7`): non ci sta un nome dentro."""


def is_format_internal(value: str) -> bool:
    """
    `True` se la stringa l'ha scritta il programma, non il disegnatore.

    Serve solo a tenere leggibile il referto di `scan`: un DXF è pieno di nomi
    di classe, GUID, timestamp e blob esadecimali, e un elenco che li mostra
    tutti non lo legge nessuno. Non è un criterio di sicurezza — `scan` tiene
    comunque ogni stringa, e `report(all_strings=True)` le mostra.
    """
    if not value or value in _INTERNAL_EXACT:
        return True
    if _NUMBERISH.match(value) or _GUID.match(value):
        return True
    if _ISO_STAMP.search(value) or _HEX_BLOB.match(value):
        return True
    if _INTERNAL_PREFIX.match(value) or _LINETYPE_PATTERN.match(value):
        return True
    if _RESERVED_NAME.match(value) or _VERSION_TAG.match(value):
        return True
    if _SHORT_KEY.match(value):
        return True
    if not any(char.isalpha() for char in value):
        return True
    return False


# ---------------------------------------------------------------------------
# Il referto
# ---------------------------------------------------------------------------

_INTERNAL_OWNERS = frozenset({
    "AcDbDictionary", "AcDbCellStyleMap", "AcDbVisualStyle", "AcDbMlineStyle",
    "CLASS", "AcDbPlaceHolder", "AcDbXrecord", "AcDbSortentsTable",
    "AcDbLayout", "AcDbScale",
})
"""Strutture in cui le stringhe sono il vocabolario del formato (chiavi di
dizionario, nomi di classe, mappe di stile di cella): si collassano nel
referto. Un percorso assoluto resta visibile anche se sta qui — un
`AcDbXrecord` è proprio dove il CAD scrive da dove ha salvato."""


@dataclass(frozen=True)
class WrittenString:
    """
    Una stringa scritta dentro il disegno, con tutti i posti in cui compare.

    L'unità è la **stringa**, non la singola occorrenza: è la stringa che una
    persona giudica, e lo stesso nome di layer compare una volta nel record di
    tabella e cento volte nel gruppo `8` delle entità.

    `contexts` è quello che fa capire *cos'è* una parola — `Rossi & C.` +
    `name/AcDbDimStyleTableRecord` è il nome di uno stile di quota, e quindi
    il nome di chi ha disegnato; `Rossi & C.` da solo non dice niente.
    """

    value: str
    kinds: tuple[str, ...]
    """`text`, `name`, `layer`, `style`, `header`, `xdata`, `comment`, `path`."""
    contexts: tuple[str, ...]
    lines: tuple[int, ...]
    codes: tuple[str, ...]

    @property
    def is_path(self) -> bool:
        return bool(ABSOLUTE_PATH.match(self.value))

    @property
    def internal(self) -> bool:
        """Scritta dal programma: per forma, o per il posto in cui sta."""
        if is_format_internal(self.value):
            return True
        return all(context.split("/", 1)[-1] in _INTERNAL_OWNERS
                   for context in self.contexts)

    def __str__(self) -> str:
        where = ", ".join(str(line) for line in self.lines[:2])
        if len(self.lines) > 2:
            where += f" (+{len(self.lines) - 2})"
        return (f"{self.value!r}  [{', '.join(self.contexts)}]  "
                f"righe {where}")


@dataclass
class ScanReport:
    """Tutto quello che è scritto in un disegno, da leggere con l'occhio."""

    path: Path
    strings: tuple[WrittenString, ...] = field(default_factory=tuple)

    def of_kind(self, *kinds: str) -> tuple[WrittenString, ...]:
        wanted = set(kinds)
        return tuple(s for s in self.strings if wanted & set(s.kinds))

    def paths(self) -> tuple[WrittenString, ...]:
        """I percorsi assoluti: sospetti in sé, senza bisogno di giudizio."""
        return tuple(s for s in self.strings if s.is_path)

    def to_read(self) -> tuple[WrittenString, ...]:
        """Quello che una persona deve guardare: tolta la roba del formato."""
        return tuple(s for s in self.strings
                     if not s.internal or s.is_path)

    def report(self, all_strings: bool = False) -> str:
        """Il referto come testo."""
        shown = self.strings if all_strings else self.to_read()
        collapsed = len(self.strings) - len(shown)
        lines = [f"{self.path.name}: {len(self.strings)} stringhe scritte dentro"]
        if collapsed:
            lines.append(f"   ({collapsed} scritte dal programma, non mostrate: "
                         f"GUID, timestamp, nomi di classe, blob)")
        percorsi = self.paths()
        if percorsi:
            lines.append("")
            lines.append("   PERCORSI (sospetti in sé):")
            lines.extend(f"      {s}" for s in percorsi)
        rest = [s for s in shown if not s.is_path]
        if rest:
            lines.append("")
            lines.append("   DA LEGGERE:")
            lines.extend(f"      {s}" for s in sorted(rest, key=lambda s: s.value.lower()))
        if not percorsi and not rest:
            lines.append("   niente da leggere: solo stringhe del formato.")
        return "\n".join(lines)


_KIND_BY_CODE: dict[str, str] = {
    **{code: "text" for code in TEXT_CODES},
    **{code: "name" for code in NAME_CODES},
    **{code: "style" for code in STYLE_CODES},
    **{code: "layer" for code in LAYER_CODES},
    **{code: "xdata" for code in ARBITRARY_CODES},
    COMMENT_CODE: "comment",
}


def scan_dxf(path: Path | str) -> ScanReport:
    """
    Elenca ogni stringa scritta dentro il disegno, con dove e in che veste.

    `owner` arriva dal contesto: l'ultimo `0` (tipo di entità o di record) e
    l'ultimo `100` (marcatore di sottoclasse) visti prima della coppia. È
    quello che distingue un nome di layer da un nome di stile di quota.
    """
    tagged = read_tags(path)
    return _scan_tagged(tagged)


def _scan_tagged(tagged: TaggedFile) -> ScanReport:
    found: dict[str, list[tuple[str, str, DxfTag]]] = {}
    entity = ""
    subclass = ""
    header_var = ""

    for tag in tagged.tags:
        if tag.code == "0":
            entity, subclass = tag.value, ""
            continue
        if tag.code == "100":
            subclass = tag.value
            continue
        if tag.code == HEADER_NAME_CODE:
            header_var = tag.value
            continue
        if tag.code not in SCANNED_CODES:
            continue

        if header_var:
            kind, owner = "header", header_var
            header_var = ""
        else:
            kind = _KIND_BY_CODE.get(tag.code, "text")
            owner = subclass or entity or "?"
        if ABSOLUTE_PATH.match(tag.value):
            kind = "path"
        found.setdefault(tag.value, []).append((kind, owner, tag))

    strings = tuple(
        WrittenString(
            value=value,
            kinds=tuple(sorted({kind for kind, _, _ in occurrences})),
            contexts=tuple(sorted({f"{kind}/{owner}"
                                   for kind, owner, _ in occurrences})),
            lines=tuple(tag.line for _, _, tag in occurrences),
            codes=tuple(sorted({tag.code for _, _, tag in occurrences})),
        )
        for value, occurrences in found.items()
    )
    return ScanReport(path=tagged.path, strings=strings)


# ---------------------------------------------------------------------------
# La pulitura
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Replacement:
    """Una sostituzione applicata, col numero di coppie che ha toccato."""

    original: str
    replacement: str
    occurrences: int


@dataclass
class CleanReport:
    """Cosa è stato sostituito, e se forge ha confermato la geometria."""

    source: Path
    output: Path
    replacements: tuple[Replacement, ...]
    verified: bool
    unused: tuple[str, ...] = field(default_factory=tuple)
    """Voci della mappa che il disegno non conteneva: di solito un errore di
    battitura in chi ha scritto la mappa, quindi si dicono."""

    @property
    def total(self) -> int:
        return sum(r.occurrences for r in self.replacements)

    def summary(self) -> str:
        lines = [f"{self.source.name} → {self.output.name}: "
                 f"{self.total} valori sostituiti"]
        for r in sorted(self.replacements, key=lambda r: -r.occurrences):
            lines.append(f"   {r.original!r} → {r.replacement!r}  "
                         f"({r.occurrences} coppie)")
        for missing in self.unused:
            lines.append(f"   ! {missing!r} non compare nel disegno")
        lines.append("   geometria verificata con heal(): "
                     + ("identica" if self.verified else "NON verificata"))
        return "\n".join(lines)


def geometry_fingerprint(path: Path | str) -> tuple:
    """
    Un'impronta della geometria letta da forge, per dire se una pulitura ha
    cambiato il disegno. Prende il conto degli edge a monte di `heal()` e, a
    valle, validità, numero di cluster, di trash, aree e bounding box.

    L'import di forge è qui dentro e non in testa al modulo: `forge/tools/` è
    sopra il package, e importarlo al caricamento sarebbe un ciclo.
    """
    import forge

    doc = forge.load_dxf(path)
    result = forge.heal(doc)
    return (
        len(doc.edges),
        result.is_valid,
        len(result.clusters),
        len(result.trash_entities),
        tuple(round(cluster.area, 6) for cluster in result.clusters),
        tuple(tuple(round(value, 6) for value in cluster.bbox)
              for cluster in result.clusters),
    )


def clean_dxf(
    path: Path | str,
    mapping: dict[str, str],
    output: Optional[Path | str] = None,
    *,
    whole_value: bool = False,
    verify: bool = True,
) -> CleanReport:
    """
    Sostituisce `mapping` nelle sole stringhe scritte dentro il disegno.

    Toccati solo i gruppi di `SCANNED_CODES`: nessun numero, nessun handle,
    nessun codice di gruppo. Una sostituzione vale per *valore*, quindi un nome
    di layer cambia insieme in tutti i posti dove compare — record di tabella,
    blocchi, gruppo `8` di ogni entità — che è l'unico modo di non rompere il
    file.

    `whole_value=True` sostituisce solo i valori uguali per intero a una
    chiave; il default sostituisce anche dentro (serve per il cartiglio:
    `CODICE: <codice>_1`).

    Con `verify=True` (default) la geometria letta da forge prima e dopo deve
    coincidere: se cambia, il file scritto viene rimosso e la funzione solleva
    `ValueError`. È forge a dire se la pulitura è stata innocua.
    """
    source = Path(path)
    target = Path(output) if output is not None else source
    before = geometry_fingerprint(source) if verify else None

    tagged = read_tags(source)
    counts: dict[str, int] = {original: 0 for original in mapping}
    for tag in tagged.tags:
        if tag.code not in SCANNED_CODES or not tag.value:
            continue
        value = tag.value
        for original, replacement in mapping.items():
            if whole_value:
                if value == original:
                    value = replacement
            elif original in value:
                value = value.replace(original, replacement)
            else:
                continue
            counts[original] += 1
        if value != tag.value:
            tagged.replace_value(tag, value)

    tagged.save(target)

    report = CleanReport(
        source=source,
        output=target,
        replacements=tuple(Replacement(original, mapping[original], count)
                           for original, count in counts.items() if count),
        verified=False,
        unused=tuple(original for original, count in counts.items() if not count),
    )

    if verify:
        after = geometry_fingerprint(target)
        if after != before:
            if target != source:
                target.unlink(missing_ok=True)
            raise ValueError(
                f"{source.name}: la pulitura ha cambiato la geometria "
                f"(prima {before}, dopo {after}) — file non scritto")
        report.verified = True
    return report


def apply_mapping(paths: Iterable[Path | str], mapping: dict[str, str]) -> dict[str, int]:
    """
    Applica la stessa mappa a file di testo che citano quelle stringhe — i
    golden, tipicamente (`"display_text": …`, `label`, `source_file`).

    Serve perché un fixture ripulito senza i suoi golden rompe i test: il testo
    dentro il disegno e il valore atteso nel golden sono la stessa stringa in
    due posti. Ritorna quante righe ha cambiato per file.
    """
    changed: dict[str, int] = {}
    for item in paths:
        target = Path(item)
        with target.open("r", encoding="utf-8", errors="replace", newline="") as handle:
            original = handle.read()
        text = original
        for before, after in mapping.items():
            text = text.replace(before, after)
        if text == original:
            continue
        with target.open("w", encoding="utf-8", newline="") as handle:
            handle.write(text)
        changed[str(target)] = sum(
            1 for a, b in zip(original.split("\n"), text.split("\n")) if a != b)
    return changed


def _main(argv: Optional[Iterable[str]] = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="python -m forge.tools.anonymize",
        description="Guarda (e, in futuro, ripulisce) quello che è scritto "
                    "dentro un disegno.")
    sub = parser.add_subparsers(dest="command", required=True)
    scan = sub.add_parser("scan", help="elenca tutto quello che è scritto dentro")
    scan.add_argument("drawings", nargs="+", help="uno o più DXF")
    scan.add_argument("--all", action="store_true", dest="all_strings",
                      help="mostra anche le stringhe scritte dal programma")

    clean = sub.add_parser("clean", help="sostituisce le stringhe di una mappa")
    clean.add_argument("drawing", help="il DXF da ripulire")
    clean.add_argument("--map", required=True, dest="mapping",
                       help="JSON {\"originale\": \"sostituto\"} — resta locale, "
                            "e' l'unico file che lega il fixture all'originale")
    clean.add_argument("--out", default=None,
                       help="dove scrivere (default: sovrascrive il disegno)")
    clean.add_argument("--also", nargs="*", default=(),
                       help="file di testo a cui applicare la stessa mappa "
                            "(i golden che citano quei testi)")
    clean.add_argument("--whole-value", action="store_true",
                       help="sostituisce solo i valori uguali per intero")
    clean.add_argument("--no-verify", action="store_true",
                       help="non confrontare la geometria con heal() (sconsigliato)")

    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.command == "scan":
        for name in args.drawings:
            print(scan_dxf(name).report(all_strings=args.all_strings))
            print()
        return 0

    import json

    mapping = json.loads(Path(args.mapping).read_text(encoding="utf-8"))
    report = clean_dxf(args.drawing, mapping, args.out,
                       whole_value=args.whole_value,
                       verify=not args.no_verify)
    print(report.summary())
    if args.also:
        for name, lines in apply_mapping(args.also, mapping).items():
            print(f"   {name}: {lines} righe riallineate")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
