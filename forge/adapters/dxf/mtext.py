"""
forge/adapters/dxf/mtext.py
---------------------------
Decodifica del testo formattato DXF: MTEXT inline codes e testo dei MULTILEADER.

`clean_mtext` è una funzione stringa → stringa (i codici di formattazione MTEXT
sono un formato di testo, non entità DXF) ed è riesportata da ``forge`` come
utilità generica. `mleader_text` invece legge un'entità ezdxf.
"""

from __future__ import annotations

from typing import Optional

from ezdxf.tools.text import plain_mtext


def clean_mtext(txt) -> str:
    """
    Testo semplice da una stringa MTEXT grezza: rimuove i codici di
    formattazione (font, colore, allineamento, …) e normalizza gli spazi.
    Accetta anche un'entità con attributo ``.text`` per comodità.
    Ritorna "" per stringhe vuote o segnaposto ("<>").
    """
    if not txt:
        return ""
    if not isinstance(txt, str):
        try:
            txt = txt.text
        except Exception:
            txt = str(txt)

    result = plain_mtext(txt).strip()
    return "" if result in ("<>", "") else result


def mleader_text(entity) -> Optional[str]:
    """Testo grezzo di un MULTILEADER (prima della pulizia), None se assente."""
    try:
        mtext = entity.context.mtext
        if mtext and hasattr(mtext, "default_content"):
            return mtext.default_content
    except Exception:
        pass
    return None
