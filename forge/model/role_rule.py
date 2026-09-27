"""
model/role_rule.py
-------------------
Regole con cui il chiamante assegna un ruolo alle linee in ingresso.

forge fornisce solo il meccanismo: il contenuto delle regole (quali nomi,
quali stili, quale ruolo) lo scrive chi chiama. L'adapter le valuta al load
su segnali neutri — il nome del gruppo sorgente e l'aspetto (`EdgeStyle`) —
e consegna al core solo il ruolo risultante (MAP.md D63).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Union

from .role import ContourRole, normalize_role
from .style import EdgeStyle

# Nomi colore ACI standard (1-9 + "pink" di rules/palette.py) → indice.
_ACI_NAME_TO_INT = {
    "red": 1, "yellow": 2, "green": 3, "cyan": 4, "blue": 5,
    "magenta": 6, "white": 7, "black": 7,
    "gray": 8, "grey": 8, "darkgray": 8, "darkgrey": 8,
    "lightgray": 9, "lightgrey": 9,
    "pink": 11,
}


# ---------------------------------------------------------------------------
# API pubblica
# ---------------------------------------------------------------------------

@dataclass
class RoleRule:
    """
    Una regola: se TUTTE le condizioni date sono vere, la linea prende `role`.
    Le condizioni lasciate a None non contano; almeno una è obbligatoria.

    Campi:
        role          : ruolo assegnato (passa per normalize_role)
        name          : nome del gruppo sorgente, uguale (maiuscole ignorate)
        name_contains : sottostringa del nome del gruppo (maiuscole ignorate)
        dashed        : True = solo tratteggiate, False = solo continue
        color         : colore ACI, intero o nome standard ("cyan")
    """
    role:          str
    name:          Optional[str]              = None
    name_contains: Optional[str]              = None
    dashed:        Optional[bool]             = None
    color:         Optional[Union[int, str]]  = None

    def __post_init__(self):
        if (self.name is None and self.name_contains is None
                and self.dashed is None and self.color is None):
            raise ValueError(f"RoleRule({self.role!r}) senza condizioni: matcherebbe tutto")
        self.role = normalize_role(self.role)
        if self.name is not None:
            self.name = self.name.lower()
        if self.name_contains is not None:
            self.name_contains = self.name_contains.lower()
        if self.color is not None:
            self.color = _color_index(self.color)

    def matches(self, name: str, style: EdgeStyle) -> bool:
        """True se la linea (nome del gruppo sorgente + aspetto) soddisfa la regola."""
        name = (name or "").lower()
        if self.name is not None and name != self.name:
            return False
        if self.name_contains is not None and self.name_contains not in name:
            return False
        if self.dashed is not None and style.is_dashed != self.dashed:
            return False
        if self.color is not None and style.color != self.color:
            return False
        return True


def resolve_role(rules: Sequence[RoleRule], name: str, style: EdgeStyle) -> str:
    """Ruolo della prima regola che matcha, in ordine; `unknown` se nessuna."""
    for rule in rules:
        if rule.matches(name, style):
            return rule.role
    return ContourRole.UNKNOWN.value


def name_rules(mapping: Dict[str, str]) -> List[RoleRule]:
    """Scorciatoia: {nome: ruolo} → una RoleRule(name=...) per voce."""
    return [RoleRule(role=role, name=name) for name, role in mapping.items()]


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _color_index(value: Union[int, str]) -> int:
    """Intero ACI da intero, stringa numerica ("4") o nome standard ("cyan")."""
    if isinstance(value, int):
        return value
    key = str(value).strip().lower()
    if key.lstrip("-").isdigit():
        return int(key)
    if key in _ACI_NAME_TO_INT:
        return _ACI_NAME_TO_INT[key]
    raise ValueError(f"colore non riconosciuto: {value!r}")
