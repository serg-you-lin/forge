"""
forge/adapters/dxf/tags.py
--------------------------
Lettura di un DXF ASCII come sequenza di coppie (codice, valore), una riga
ciascuna, conservando il file riga per riga così come sta sul disco.

Non è un secondo loader: `loader.py` legge la *geometria* e la traduce in
primitive forge. Questo modulo serve a chi deve guardare o riscrivere il file
alla lettera — oggi `tools/anonymize.py`, che sostituisce stringhe che
identificano un cliente senza toccare nient'altro.

Perché non passare da `ezdxf` per questo: un fixture di test deve restare il
file che è, byte per byte, tranne le stringhe sostituite. Qualunque round-trip
attraverso un modello (il nostro o quello di una libreria) riscrive il file
secondo le regole di chi lo riscrive, e un disegno che serve a provare il
*parsing* perderebbe esattamente ciò che lo rende un caso di prova.

Un DXF binario non si legge qui: `is_ascii_dxf()` lo dice e il chiamante
decide. Le righe mantengono il loro fine-riga originale, quindi riscrivere un
file che non si è modificato lo lascia identico al byte.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional, Sequence

BINARY_SENTINEL = b"AutoCAD Binary DXF"
"""Un DXF binario comincia con questa firma (seguita da CR LF SUB NUL)."""


@dataclass(frozen=True)
class DxfTag:
    """
    Una coppia del file. `line` è l'indice (1-based) della riga del *valore*,
    quella che un editor mostra: il codice sta sulla riga precedente.
    """

    code: str
    value: str
    line: int

    @property
    def code_line(self) -> int:
        """La riga del codice di gruppo."""
        return self.line - 1


@dataclass
class TaggedFile:
    """
    Il file aperto in coppie, con le righe originali a fianco.

    `lines` è la verità: `tags` ci punta per indice. Si modifica solo tramite
    `replace_value`, che tiene il fine-riga della riga che sostituisce.
    """

    path: Path
    lines: list[str]
    tags: tuple[DxfTag, ...]
    newline: str

    def replace_value(self, tag: DxfTag, value: str) -> None:
        """Riscrive il valore di una coppia, lasciando intatto il fine-riga."""
        index = tag.line - 1
        original = self.lines[index]
        suffix = "\r" if original.endswith("\r") else ""
        self.lines[index] = value + suffix

    def text(self) -> str:
        """Il file come stringa, pronto da riscrivere."""
        return self.newline.join(self.lines)

    def save(self, path: Optional[Path] = None) -> Path:
        """Scrive il file (o una copia) senza traduzioni di fine-riga."""
        target = Path(path) if path is not None else self.path
        with target.open("w", encoding="utf-8", newline="") as handle:
            handle.write(self.text())
        return target

    def tags_with_code(self, *codes: str) -> Iterator[DxfTag]:
        """Le coppie con uno dei codici di gruppo dati."""
        wanted = set(codes)
        for tag in self.tags:
            if tag.code in wanted:
                yield tag


def is_ascii_dxf(path: Path | str) -> bool:
    """`False` per un DXF binario (o per un file che non si può leggere)."""
    try:
        with Path(path).open("rb") as handle:
            return not handle.read(len(BINARY_SENTINEL)).startswith(BINARY_SENTINEL)
    except OSError:
        return False


def read_tags(path: Path | str, encoding: str = "utf-8") -> TaggedFile:
    """
    Apre un DXF ASCII in coppie (codice, valore).

    Le righe si dividono su `\\n` e il `\\r` eventuale resta attaccato alla
    riga: è il modo di non riscrivere i fine-riga di un file che non si sta
    modificando. Il codice di gruppo è la riga dispari, il valore la pari;
    una riga di codice senza valore in coda al file viene ignorata.
    """
    source = Path(path)
    if not is_ascii_dxf(source):
        raise ValueError(f"{source.name}: DXF binario, questo modulo legge solo ASCII")
    with source.open("r", encoding=encoding, errors="replace", newline="") as handle:
        raw = handle.read()
    lines = raw.split("\n")

    tags: list[DxfTag] = []
    index = 0
    while index + 1 < len(lines):
        code = lines[index].strip()
        if not code:
            index += 1
            continue
        value_line = lines[index + 1]
        value = value_line[:-1] if value_line.endswith("\r") else value_line
        tags.append(DxfTag(code=code, value=value.strip(), line=index + 2))
        index += 2

    return TaggedFile(path=source, lines=lines, tags=tuple(tags), newline="\n")


def group_values(tagged: TaggedFile, codes: Sequence[str]) -> dict[str, list[DxfTag]]:
    """Le coppie cercate, raccolte per codice di gruppo."""
    out: dict[str, list[DxfTag]] = {code: [] for code in codes}
    for tag in tagged.tags:
        if tag.code in out:
            out[tag.code].append(tag)
    return out
