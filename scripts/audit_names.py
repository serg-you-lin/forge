"""
scripts/audit_names.py
----------------------
Cerca nei file tracciati i nomi che identificano un cliente: codici pezzo,
numeri d'ordine, nomi originali di disegni.

Perché esiste: i disegni dei clienti stanno in locale e non entrano in git, ma
il *nome* di un disegno può entrarci di contrabbando — citato in MAP.md, messo
nel CONFIG di uno script, o nel nome di un golden. Una volta committato resta
nella history, quindi va intercettato prima, non dopo.

Uso (da qualsiasi cartella)::

    python scripts/audit_names.py            # elenca i sospetti
    python scripts/audit_names.py --strict   # esce 1 se ne trova almeno uno

Quattro controlli:
    1. i nomi dei file tracciati
    2. il contenuto dei file tracciati di testo
    3. il contenuto dei DXF tracciati: un disegno porta dentro di sé i percorsi
       da cui è stato salvato (`AcDbXrecord`, gruppo 303) e il testo scritto sul
       foglio, dove cliente, commessa e nome originale finiscono senza che il
       nome del file dica niente
    4. i nomi composti da sole cifre (`1026.dxf`): un codice pezzo nudo, che i
       pattern con la lettera obbligatoria non vedono

`ALLOWED` è la lista delle cose che *sembrano* un codice pezzo ma non lo sono
(norme materiale, versioni DXF, sigle interne di forge): va allungata quando
l'audit segnala un falso positivo, mai per far tacere un codice vero.

In locale il controllo più forte lo fa `--from-disk`: prende i nomi dei disegni
presenti sul disco ma non tracciati — i file cliente veri, quelli che conosce
solo questa macchina — e cerca quelli. Non è riproducibile altrove, per questo
non è il default.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parent.parent
"""Radice del repo (scripts/ ne è figlia)."""

TEXT_SUFFIXES = {".md", ".py", ".toml", ".cff", ".txt", ".json", ".xml",
                 ".cfg", ".yml", ".yaml", ".ini"}

# Forme che un codice pezzo/ordine assume nei disegni veri: lettere e cifre
# mescolate, con almeno quattro cifre di fila da qualche parte. La lettera è
# obbligatoria: un token di sole cifre non si distingue da una coordinata di un
# golden, e cercarlo sommergerebbe l'audit di falsi positivi (per quelli c'è
# --digits, che guarda solo i file di prosa e di codice).
#
# Gli esempi accanto a ogni pattern sono inventati, con la stessa forma dei
# codici veri: scriverci un codice vero significherebbe mettere in git proprio
# quello che questo script serve a tenerne fuori.
PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b[A-Za-z]{1,6}\d{3,}[A-Za-z0-9_-]*\b"),        # Q0000000X, XY10000, Z105, BLANK000
    re.compile(r"\b\d{2,}[A-Za-z]{1,4}\d{2,}[A-Za-z0-9_-]*\b"),  # 00X000Y00Z, 0000XY00000-0X
    re.compile(r"\b\d{5,}[A-Za-z_][A-Za-z0-9_-]*\b"),            # 0000000000Sviluppo
    re.compile(r"\b[A-Za-z]{2,5}\d{2,4}#\d{2,4}\b"),             # XX000#000
)

BARE_DIGITS = re.compile(r"(?<![\d.#])\d{6,13}(?![\d.])")
"""Codice di sole cifre, cercato sul testo e non sui token: un token è spezzato
anche sul punto, quindi `1.0000003` diventerebbe `0000003`. Da qui i contorni —
niente cifra o punto prima e dopo (esclude i decimali), niente `#` prima
(esclude un colore `#808080`), e non oltre le 13 cifre (oltre non è un codice
ma un blob binario)."""

NAME_CODE_DIGITS = re.compile(r"^\d{3,}$")
"""Un nome di file che *comincia* con sole cifre (`1026.dxf`, `4821_...`) è un
codice pezzo: nei nomi non c'è nessuna coordinata da cui distinguerlo, quindi
qui le cifre nude si possono cercare sempre. Vale solo per il primo token del
nome — `anch_01` o `foglio__000` hanno il numero come indice, non come codice."""

TOKEN_SPLIT = re.compile(r"[^A-Za-z0-9]+")
"""Spezza su tutto quello che non è lettera o cifra. Serve perché `\\b` non
scatta dentro un underscore (`_` è un word character): in `4821_U120_20X3` non
c'è nessun confine di parola fra `4821` e `U120`, e un codice tenuto insieme
dagli underscore passerebbe inosservato."""

PROSE_SUFFIXES = {".md", ".py"}
DRAWING_SUFFIXES = {".dxf", ".dwg"}

PLAIN_HEX = re.compile(r"^[0-9a-f]+$")
BLOB_HEX = re.compile(r"^[0-9A-Fa-f]+$")
DIMENSION = re.compile(r"^\d+[xX]\d+$")
SCIENTIFIC = re.compile(r"^\d+[eE][-+]?\d*$")
"""La mantissa di un numero in notazione scientifica dentro un golden
(`34788079488412e-15`): cifre seguite da `e` ± esponente. L'esponente può
mancare perché il token viene spezzato sul segno meno."""

ABS_PATH = re.compile(r"(?<![A-Za-z0-9])(\\\\[^\\\s]|[A-Za-z]:[\\/])")
"""Percorso assoluto (UNC o con lettera di unità) dentro un disegno: nomina una
cartella di rete, una commessa, un utente. Sospetto in sé, anche senza codici.
Si cerca in tutta la riga, non solo in testa: un disegno lo scrive anche dentro
un testo (`Source file=C:\\...`). Non attaccato a una lettera, così `https://`
non conta."""

NUMBER_LINE = re.compile(r"^[-+]?\d*\.?\d+([eE][-+]?\d+)?$")
"""Riga di un DXF che è solo un numero: una coordinata, niente da leggere."""

DRAWING_NOISE: tuple[re.Pattern[str], ...] = (
    # identificatori generati dal programma che ha scritto il file
    re.compile(r"^\{?[0-9A-Fa-f]{8}(-[0-9A-Fa-f]{4}){3}-[0-9A-Fa-f]{12}\}?$"),
    # data/ora ISO, anche quella che forge stessa scrive in XDATA
    re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"),
    # nomi di classi, dizionari e stili del formato
    re.compile(r"^(ACAD|ACDB|AcDb|AcAd|ASDK|ODA|OdDb)", re.IGNORECASE),
    # una riga di blob binario scritto in esadecimale (anteprime, pacchetti
    # incorporati): dentro ci cadono spezzoni di cifre di ogni lunghezza
    re.compile(r"^[0-9A-Fa-f]{14,}$"),
)
"""Righe di un DXF che non possono contenere dati cliente: le scrive il
programma, non il disegnatore. Filtrate per riga e non per token perché un GUID
produce un token nuovo e diverso in ogni file."""


def _is_noise(token: str) -> bool:
    """Scarta quello che ha la forma di un codice ma non lo è."""
    if token.upper() in {a.upper() for a in ALLOWED}:
        return True
    if DIMENSION.match(token):           # 100x400 — una misura
        return True
    if SCIENTIFIC.match(token):          # 34788079488412e-15 — un numero
        return True
    if PLAIN_HEX.match(token) and len(token) >= 6:   # ff0000, uno sha git
        return True
    # un blob binario scritto in esadecimale (gruppo 310: anteprime, pacchetti
    # incorporati): lungo e senza struttura, nessun codice pezzo è così
    if BLOB_HEX.match(token) and len(token) >= 14:
        return True
    # un codice pezzo ha sempre almeno una lettera E almeno due cifre
    if not any(c.isalpha() for c in token):
        return True
    if sum(c.isdigit() for c in token) < 2:
        return True
    return False

ALLOWED: frozenset[str] = frozenset({
    # norme e designazioni materiale
    "EN10025", "S235JR", "S355JR", "S275JR",
    # versioni e tag DXF/DWG
    "AC1009", "AC1012", "AC1014", "AC1015", "AC1018", "AC1021", "AC1024",
    "AC1027", "AC1032", "R2000", "R2004", "R2007", "R2010", "R2013", "R2018",
    # designazioni materiale
    "AISI304", "AISI316", "AISI316L",
    # codici flake8 nei commenti `# noqa: F401`
    "F401", "F403", "E501",
    # sigle che forge usa come esempio o nei suoi stessi test
    "P1024", "U0001",
    # nomi generati dal programma dentro un disegno, guardati uno per uno:
    # impronta dell'applicazione in un AcDbXrecord (accanto ai valori "ACD" e
    # "2013") e nomi di sezione numerati progressivamente
    "85871ACD", "XSEC0001", "XSEC0002",
    # le cifre in fila dentro il nome di layer che un visualizzatore si scrive
    # da sé (`...ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-note-layer...`)
    "0123456789",
})
"""Token che somigliano a un codice pezzo ma non lo sono."""

ALLOWED_PREFIX_DIRS = ("docs/INDEX.md", "scripts/audit_names.py")
"""Esclusi dal controllo sul contenuto. `docs/INDEX.md` è generato: un sospetto
lì si corregge alla fonte. Questo script stesso contiene per forza token con la
forma di un codice — sono i suoi pattern e i suoi esempi, tenuti inventati di
proposito; nessun codice vero va scritto qui, perché qui nessuno lo vedrebbe."""


def tracked_files() -> list[str]:
    """
    I path tracciati, uno per riga. `-z` (separatore NUL) perché altrimenti git
    *quota* i nomi con caratteri non ASCII e li scrive con escape ottali
    (`"…N\\302\\2601 pz.nc.dxf"`): su Windows quei backslash vengono poi letti
    come separatori di cartella e tutto quello che sta prima dell'escape
    sparisce dal controllo. Con `-z` git non quota, e il decode è utf-8 a mano
    perché `text=True` userebbe la codepage locale.
    """
    raw = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT,
                         capture_output=True, check=True).stdout
    return [path for path in raw.decode("utf-8").split("\0") if path]


GENERATED_SHAPES: tuple[re.Pattern[str], ...] = (
    re.compile(r"\\U\+[0-9A-Fa-f]{4}"),
    re.compile(r"\{?[0-9A-Fa-f]{8}(-[0-9A-Fa-f]{4}){3}-[0-9A-Fa-f]{12}\}?"),
    re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?"),
)
"""Forme che un programma genera e che, spezzate in token, imitano un codice:
l'escape di un carattere non ASCII in un testo di quota (`\\U+00b0` → `00b07`),
un GUID (`{F0864738-…}` → `F0864738`), una data ISO (`…-09-06T13:14` → `06T13`).
Si togliono dal testo *prima* di spezzarlo, così non c'è bisogno di una voce in
`ALLOWED` per ogni GUID che esiste."""


def suspicious_tokens(text: str, bare_digits: bool = False) -> set[str]:
    """I token di `text` che hanno la forma di un codice pezzo."""
    found: set[str] = set()
    for pattern in GENERATED_SHAPES:
        text = pattern.sub(" ", text)
    for token in TOKEN_SPLIT.split(text):
        if not token:
            continue
        if any(pattern.fullmatch(token) for pattern in PATTERNS):
            if not _is_noise(token):
                found.add(token)
    if bare_digits:
        found |= {m for m in BARE_DIGITS.findall(text) if m not in ALLOWED}
    return found


def name_suspicions(rel: str) -> set[str]:
    """
    I sospetti nel path di un file tracciato: i pattern su tutto il nome, più
    le cifre nude in testa a un nome o a una cartella (`1026.dxf`, `111-23/`).
    """
    name = rel.rsplit("/", 1)[-1]
    found = suspicious_tokens(name)
    for component in rel.split("/"):
        first = next((t for t in TOKEN_SPLIT.split(component) if t), "")
        if NAME_CODE_DIGITS.fullmatch(first) and first not in ALLOWED:
            found.add(first)
    return found


def drawing_suspicions(path: Path) -> list[tuple[int, str]]:
    """
    Cosa c'è scritto dentro un disegno: percorsi assoluti e token con la forma
    di un codice. Le righe che sono solo un numero (le coordinate, la gran parte
    del file) sono saltate: lì non c'è niente da leggere.
    """
    try:
        with path.open("r", encoding="utf-8", errors="replace", newline="") as fh:
            text = fh.read()
    except OSError:
        return []
    out: list[tuple[int, str]] = []
    for n, hits, value in drawing_line_hits(text):
        if value is None:
            out.append((n, f"percorso: {next(iter(hits))}"))
        else:
            out.append((n, f"[{', '.join(sorted(hits))}] {value[:80]}"))
    return out


def drawing_line_hits(text: str) -> list[tuple[int, set[str], str | None]]:
    """
    Le righe sospette del testo di un disegno: (riga, sospetti, valore). Per un
    percorso assoluto il sospetto è il percorso stesso e il valore è `None`.
    """
    out: list[tuple[int, set[str], str | None]] = []
    for n, line in enumerate(text.split("\n"), 1):
        value = line.strip()
        if not value or NUMBER_LINE.match(value):
            continue
        if ABS_PATH.search(value):
            out.append((n, {value[:120]}, None))
            continue
        if any(pattern.search(value) for pattern in DRAWING_NOISE):
            continue
        # dentro un disegno le cifre nude si cercano sempre: una coordinata è
        # una riga che contiene SOLO il numero, ed è già stata saltata sopra,
        # quindi un codice scritto nel cartiglio non la può imitare
        hits = suspicious_tokens(value, bare_digits=True)
        if hits:
            out.append((n, hits, value))
    return out


def disk_drawing_names(tracked: Iterable[str]) -> set[str]:
    """Nomi dei disegni presenti sul disco ma non tracciati (solo locale)."""
    tracked_set = set(tracked)
    tracked_stems = {Path(f).stem for f in tracked_set}
    names: set[str] = set()
    for suffix in ("dxf", "DXF", "dwg", "DWG"):
        for path in ROOT.rglob(f"*.{suffix}"):
            rel = path.relative_to(ROOT).as_posix()
            if any(part in rel for part in (".venv", "build/", ".git/")):
                continue
            if rel in tracked_set:
                continue
            stem = re.sub(r"(_nf|_healed|_\d+)$", "", path.stem)
            for candidate in {path.stem, stem}:
                # solo se ha la forma di un codice: un nome descrittivo
                # ("arc_line_gap") non è un dato cliente
                if len(candidate) >= 5 and suspicious_tokens(candidate) \
                        and candidate not in tracked_stems:
                    names.add(candidate)
    return names


def read_words(path: Path) -> set[str]:
    """
    Parole da cercare alla lettera, una per riga (`#` commenta). Il file sta
    fuori dal repo: dentro ci sono i nomi veri che non devono entrare in git.
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    return {w.strip() for w in lines if w.strip() and not w.startswith("#")}


def _git(*args: str) -> bytes:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                          check=True).stdout


def _word_hits(text: str, words: set[str]) -> set[str]:
    low = text.lower()
    return {w for w in words if w.lower() in low}


def history_suspicions(words: set[str]) -> dict[str, dict[str, list[str]]]:
    """
    I sospetti in tutta la history, su ogni ref: nei path mai esistiti, in ogni
    versione di ogni file, nei messaggi di commit. Raggruppati per sospetto,
    con i posti in cui compare: è l'elenco che serve a un rewrite, che pulisce
    una stringa ovunque e non un file alla volta.
    """
    found: dict[str, dict[str, list[str]]] = {
        "path": {}, "contenuto": {}, "messaggio": {}}

    def note(kind: str, hits: Iterable[str], where: str) -> None:
        for hit in hits:
            found[kind].setdefault(hit, []).append(where)

    # path: ogni nome che un commit abbia mai toccato
    raw = _git("log", "--all", "--format=", "--name-only", "-z")
    for rel in sorted({p for p in raw.decode("utf-8").split("\0") if p.strip()}):
        rel = rel.strip()
        note("path", name_suspicions(rel) | _word_hits(rel, words), rel)

    # contenuto: ogni blob una volta sola, letto con `cat-file --batch`
    listing = _git("rev-list", "--all", "--objects").decode("utf-8")
    blobs: dict[str, str] = {}
    for line in listing.splitlines():
        sha, _, rel = line.partition(" ")
        if rel and Path(rel).suffix.lower() in (DRAWING_SUFFIXES | TEXT_SUFFIXES):
            blobs.setdefault(sha, rel)
    proc = subprocess.Popen(["git", "cat-file", "--batch"], cwd=ROOT,
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    assert proc.stdin and proc.stdout
    for sha, rel in blobs.items():
        proc.stdin.write(f"{sha}\n".encode())
        proc.stdin.flush()
        header = proc.stdout.readline().split()
        if len(header) < 3 or header[1] != b"blob":
            continue
        data = proc.stdout.read(int(header[2]))
        proc.stdout.read(1)
        text = data.decode("utf-8", errors="replace")
        where = f"{rel}@{sha[:8]}"
        note("contenuto", _word_hits(text, words), where)
        suffix = Path(rel).suffix
        if suffix.lower() in DRAWING_SUFFIXES:
            for _, hits, _ in drawing_line_hits(text):
                note("contenuto", hits, where)
        elif rel not in ALLOWED_PREFIX_DIRS:
            bare = suffix in PROSE_SUFFIXES
            for line in text.splitlines():
                note("contenuto", suspicious_tokens(line, bare_digits=bare), where)
    proc.stdin.close()
    proc.wait()

    # messaggi di commit
    log = _git("log", "--all", "--format=%h%x00%B%x01").decode("utf-8")
    for entry in log.split("\x01"):
        sha, _, body = entry.strip().partition("\0")
        if sha:
            note("messaggio", suspicious_tokens(body, bare_digits=True)
                 | _word_hits(body, words), sha)
    return found


def print_history(found: dict[str, dict[str, list[str]]]) -> int:
    """Stampa un sospetto per riga, con quante volte e il primo posto."""
    total = 0
    for kind, hits in found.items():
        print(f"\n— nei {kind.upper()} della history ({len(hits)} distinti)")
        for hit in sorted(hits, key=str.lower):
            places = sorted(set(hits[hit]))
            print(f"    {hit}   ×{len(places)}   es. {places[0]}")
        total += len(hits)
    return total


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Cerca nomi di clienti nei file tracciati.")
    parser.add_argument("--strict", action="store_true",
                        help="esce 1 se trova almeno un sospetto")
    parser.add_argument("--from-disk", action="store_true",
                        help="cerca anche i nomi dei disegni non tracciati "
                             "presenti su questa macchina")
    parser.add_argument("--digits", action="store_true",
                        help="segnala anche i codici di sole cifre, ma solo in "
                             "prosa e codice (.md/.py): nei golden sarebbero "
                             "coordinate")
    parser.add_argument("--history", action="store_true",
                        help="cerca in tutta la history (ogni commit, path e "
                             "messaggio) invece che nei file di adesso")
    parser.add_argument("--words", type=Path,
                        help="file locale, fuori dal repo: parole da cercare "
                             "alla lettera, una per riga (i nomi veri che i "
                             "pattern non riconoscono)")
    args = parser.parse_args(argv)

    tracked = tracked_files()
    extra_names = disk_drawing_names(tracked) if args.from_disk else set()
    if args.words:
        extra_names |= read_words(args.words)

    if args.history:
        total = print_history(history_suspicions(extra_names))
        if not total:
            print("\nnessun sospetto nella history.")
            return 0
        print(f"\n{total} sospetti distinti nella history.")
        return 1 if args.strict else 0

    in_names: list[str] = []
    in_content: list[str] = []
    in_drawings: list[str] = []

    for rel in tracked:
        name = rel.rsplit("/", 1)[-1]
        hits = name_suspicions(rel) | {
            extra for extra in extra_names if extra in name}
        if hits:
            in_names.append(f"{rel}   [{', '.join(sorted(hits))}]")

        if Path(rel).suffix.lower() in DRAWING_SUFFIXES:
            for n, detail in drawing_suspicions(ROOT / rel):
                in_drawings.append(f"{rel}:{n}   {detail}")
            continue

        if rel in ALLOWED_PREFIX_DIRS or Path(rel).suffix not in TEXT_SUFFIXES:
            continue
        try:
            lines = (ROOT / rel).read_text(encoding="utf-8",
                                           errors="replace").splitlines()
        except OSError:
            continue
        # in prosa e codice un numero di 6+ cifre non è mai una coordinata, e
        # un codice pezzo di sole cifre non ha nessuna lettera da cui farsi
        # riconoscere: lì si cerca sempre. Nei golden (.json/.xml) le cifre
        # nude sono misure, e si cercano solo se le chiedi con --digits.
        bare = args.digits or Path(rel).suffix in PROSE_SUFFIXES
        for n, line in enumerate(lines, 1):
            hits = suspicious_tokens(line, bare_digits=bare) | {
                name for name in extra_names if name in line}
            if hits:
                in_content.append(f"{rel}:{n}   [{', '.join(sorted(hits))}]")

    print(f"file tracciati: {len(tracked)}")
    if args.from_disk:
        print(f"nomi di disegni non tracciati su questa macchina: {len(extra_names)}")

    print(f"\n— nel NOME di un file tracciato ({len(in_names)})")
    for row in in_names:
        print("   ", row)
    print(f"\n— nel CONTENUTO di un file tracciato ({len(in_content)})")
    for row in in_content:
        print("   ", row)
    print(f"\n— DENTRO un disegno tracciato ({len(in_drawings)})")
    for row in in_drawings:
        print("   ", row)

    total = len(in_names) + len(in_content) + len(in_drawings)
    if not total:
        print("\nnessun sospetto.")
        return 0
    print(f"\n{total} sospetti. Falso positivo? aggiungilo ad ALLOWED. "
          f"Codice vero? va rinominato o descritto a parole.")
    return 1 if args.strict else 0


if __name__ == "__main__":
    sys.exit(main())
