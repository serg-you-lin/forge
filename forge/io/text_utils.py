"""
text_utils.py
---------
Funzioni per estrarre e pulire i testi da un msp, gestendo TEXT, MTEXT, MULTILEADER e DIMENSION.
Usata da heal() per estrarre i testi da un msp padre (un pezzo) e da split_to_files() per estrarre i testi da un new_msp figlio (già filtrato).
Non gestisce INSERT — assumere che siano già stati esplosi. 
"""


from ezdxf.tools.text import plain_mtext
from shapely.geometry import Point
from ..model.text import ForgeText
from ..adapters.dxf.geometry_adapter import get_representative_point

ANNOTATION_TYPES = {'TEXT', 'MTEXT', 'DIMENSION', 'LEADER', 'MULTILEADER'}

def extract_forge_texts(msp) -> list[ForgeText]:
    """
    Estrae i testi dal msp come ForgeText — contenuto + posizione shapely.
    Prodotto dall'adapter DXF, consumato da inject().
    """
    result = []
    for e in msp:
        if e.dxftype() not in ANNOTATION_TYPES:
            continue
        pt = get_representative_point(e)
        if pt is None:
            continue
        content = _extract_content(e)
        if not content:
            continue
        result.append(ForgeText(
            content=content,
            position=pt if isinstance(pt, Point) else Point(pt),
        ))
    return result


def _extract_content(e) -> str:
    """Estrae e pulisce il testo da una entità DXF."""
    t = e.dxftype()
    if t == 'TEXT':
        return e.dxf.get('text', '').strip()
    elif t == 'MTEXT':
        return clean_mtext(e.text)
    elif t == 'MULTILEADER':
        raw = handle_mleader(e)
        return clean_mtext(raw) if raw else ''
    elif t == 'DIMENSION':
        txt = e.dxf.get('text', '')
        return txt if txt and txt != '<>' else ''
    return ''

def extract_texts(msp, doc):
    texts = []

    def handle_entity(e):
        t = e.dxftype()

        # TEXT
        if t == "TEXT":
            txt = e.dxf.text.strip()
            if txt:
                texts.append(txt)

        # MTEXT
        elif t == "MTEXT":
            txt = e.text.strip()
            if txt:
                texts.append(clean_mtext(txt))

        # MULTILEADER
        elif t == "MULTILEADER":
            txt = handle_mleader(e)

            if txt:
                texts.append(clean_mtext(txt))

        elif t == "ATTRIB":
            txt = e.dxf.text.strip()
            if txt:
                texts.append(txt)
                
        elif t == "INSERT":
            for attrib in e.attribs:
                txt = attrib.dxf.text.strip()
                if txt:
                    texts.append(txt)
                    
        # DIMENSION (solo override)
        elif t == "DIMENSION":
            txt = e.dxf.text
            if txt and txt != "<>":
                texts.append(txt)

    for e in msp:
        handle_entity(e)

    return texts

def extract_texts_from_msp(msp) -> list[str]:
    """
    Estrae tutti i testi grezzi da un msp senza bisogno di doc.
    Usata da heal() (msp padre, un pezzo) e split_to_files() (new_msp figlio, già filtrato).
    Non gestisce INSERT — assumere che siano già stati esplosi.
    """
    texts = []
    for e in msp:
        t = e.dxftype()
        if t == 'TEXT':
            txt = e.dxf.get('text', '').strip()
            if txt:
                texts.append(txt)
        elif t == 'MTEXT':
            txt = clean_mtext(e.text)
            if txt:
                texts.append(txt)
        elif t == 'MULTILEADER':
            raw = handle_mleader(e)
            txt = clean_mtext(raw) if raw else None
            if txt:
                texts.append(txt)
        elif t == 'DIMENSION':
            txt = e.dxf.get('text', '')
            if txt and txt != '<>':
                texts.append(txt)
    return texts


def clean_mtext(txt: str) -> str:
    if not txt:
        return ""
    if not isinstance(txt, str):
        try:
            txt = txt.text
        except Exception:
            txt = str(txt)
    
    result = plain_mtext(txt)   # ezdxf rimuove tutti i codici standard
    result = result.strip()
    
    if result in ("<>", ""):
        return ""
    
    return result

def handle_mleader(e):
    try:
        mtext = e.context.mtext
        if mtext and hasattr(mtext, "default_content"):
            return mtext.default_content
    except:
        pass

    return None
