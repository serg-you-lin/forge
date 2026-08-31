
#!/usr/bin/env python3
"""
Genera un DXF contenente:
  1) sviluppo piano del tronco di cono (settore anulare);
  2) sviluppo piano del cilindro (rettangolo);
  3) quote principali e testo riepilogativo.

I diametri inseriti sono ESTERNI.
Gli sviluppi sono calcolati sulla fibra media:

    D_medio = D_esterno - spessore

Installazione:
    pip install ezdxf

Configurazione:
    Modificare esclusivamente la sezione
    "PARAMETRI DI INPUT" qui sotto.

Il DXF viene salvato nel percorso specificato
da OUTPUT_DXF.
"""

from __future__ import annotations

import math
from pathlib import Path

import ezdxf
from ezdxf import units


# =============================================================================
# PARAMETRI DI INPUT
# =============================================================================
#
# Modifica questi valori direttamente nello script.
# Tutte le quote sono espresse in millimetri.
#

DIAMETRO_SUPERIORE = 200
DIAMETRO_INFERIORE = 150

ALTEZZA_CONO = 100
ALTEZZA_CILINDRO = 3895.0

SPESSORE = 2

# Percorso completo o relativo del file DXF da creare.
#
# Esempi Windows:
#
# OUTPUT_DXF = r"C:\Users\Nome\Desktop\sviluppo.dxf"
# OUTPUT_DXF = r"C:\Users\Nome\Documents\DXF\sviluppo.dxf"
#
# Oppure percorso relativo:
#
# OUTPUT_DXF = "output/sviluppo.dxf"
#
OUTPUT_DXF = r"output/sviluppo_cono_cilindro.dxf"


# =============================================================================
# COSTANTI
# =============================================================================

TOL = 1e-9


# =============================================================================
# GEOMETRIA
# =============================================================================

def punto_polare(
    raggio: float,
    angolo_gradi: float,
    origine: tuple[float, float] = (0.0, 0.0),
) -> tuple[float, float]:
    """Restituisce un punto a coordinate polari."""

    angolo = math.radians(angolo_gradi)

    return (
        origine[0] + raggio * math.cos(angolo),
        origine[1] + raggio * math.sin(angolo),
    )


def calcola_cono(
    diametro_superiore: float,
    diametro_inferiore: float,
    altezza: float,
    spessore: float,
) -> dict[str, float]:
    """
    Calcola i parametri dello sviluppo del tronco di cono
    sulla fibra media.
    """

    diametro_superiore_medio = diametro_superiore - spessore
    diametro_inferiore_medio = diametro_inferiore - spessore

    if diametro_superiore_medio <= 0:
        raise ValueError(
            "Lo spessore deve essere minore del diametro superiore."
        )

    if diametro_inferiore_medio <= 0:
        raise ValueError(
            "Lo spessore deve essere minore del diametro inferiore."
        )

    if abs(diametro_superiore_medio - diametro_inferiore_medio) < TOL:
        raise ValueError(
            "I diametri del cono sono uguali. "
            "Per un cilindro usare lo sviluppo cilindrico."
        )

    diametro_grande = max(
        diametro_superiore_medio,
        diametro_inferiore_medio,
    )

    diametro_piccolo = min(
        diametro_superiore_medio,
        diametro_inferiore_medio,
    )

    raggio_grande = diametro_grande / 2.0
    raggio_piccolo = diametro_piccolo / 2.0

    delta_r = raggio_grande - raggio_piccolo

    # Generatrice reale del tronco di cono.
    generatrice = math.hypot(altezza, delta_r)

    # Raggi dello sviluppo piano.
    raggio_esterno = generatrice * raggio_grande / delta_r
    raggio_interno = generatrice * raggio_piccolo / delta_r

    # Angolo del settore.
    angolo = 360.0 * raggio_grande / raggio_esterno

    return {
        "diametro_superiore_medio": diametro_superiore_medio,
        "diametro_inferiore_medio": diametro_inferiore_medio,
        "diametro_grande_medio": diametro_grande,
        "diametro_piccolo_medio": diametro_piccolo,
        "generatrice": generatrice,
        "raggio_esterno": raggio_esterno,
        "raggio_interno": raggio_interno,
        "angolo": angolo,
        "arco_esterno": math.pi * diametro_grande,
        "arco_interno": math.pi * diametro_piccolo,
    }


# =============================================================================
# DXF - UTILITY
# =============================================================================

def aggiungi_quota_lineare(
    msp,
    p1,
    p2,
    base,
    angolo,
    testo=None,
):
    """Aggiunge una quota lineare al DXF."""

    quota = msp.add_linear_dim(
        base=base,
        p1=p1,
        p2=p2,
        angle=angolo,
        dimstyle="EZDXF",
        override={
            "dimtxt": 18,
            "dimasz": 12,
            "dimexo": 5,
            "dimexe": 5,
        },
    )

    if testo:
        quota.set_text(testo)

    quota.render()


def aggiungi_testo(
    msp,
    testo,
    posizione,
    altezza=22,
    layer="TESTI",
):
    """Aggiunge testo al modelspace."""

    entita = msp.add_text(
        testo,
        dxfattribs={
            "height": altezza,
            "layer": layer,
        },
    )

    entita.set_placement(posizione)

    return entita


# =============================================================================
# DXF - SVILUPPO CONO
# =============================================================================

def disegna_settore_cono(
    msp,
    dati,
    origine=(0.0, 0.0),
):
    """Disegna lo sviluppo piano del tronco di cono."""

    raggio_interno = dati["raggio_interno"]
    raggio_esterno = dati["raggio_esterno"]
    angolo = dati["angolo"]

    # Settore simmetrico rispetto all'asse X.
    angolo_inizio = -angolo / 2.0
    angolo_fine = angolo / 2.0

    punto_interno_1 = punto_polare(
        raggio_interno,
        angolo_inizio,
        origine,
    )

    punto_esterno_1 = punto_polare(
        raggio_esterno,
        angolo_inizio,
        origine,
    )

    punto_interno_2 = punto_polare(
        raggio_interno,
        angolo_fine,
        origine,
    )

    punto_esterno_2 = punto_polare(
        raggio_esterno,
        angolo_fine,
        origine,
    )

    # Arco esterno.
    msp.add_arc(
        center=origine,
        radius=raggio_esterno,
        start_angle=angolo_inizio,
        end_angle=angolo_fine,
        dxfattribs={
            "layer": "TAGLIO",
        },
    )

    # Arco interno.
    msp.add_arc(
        center=origine,
        radius=raggio_interno,
        start_angle=angolo_inizio,
        end_angle=angolo_fine,
        dxfattribs={
            "layer": "TAGLIO",
        },
    )

    # Lati radiali del settore.
    msp.add_line(
        punto_interno_1,
        punto_esterno_1,
        dxfattribs={
            "layer": "TAGLIO",
        },
    )

    msp.add_line(
        punto_interno_2,
        punto_esterno_2,
        dxfattribs={
            "layer": "TAGLIO",
        },
    )

    # Linee radiali di costruzione.
    msp.add_line(
        origine,
        punto_esterno_1,
        dxfattribs={
            "layer": "COSTRUZIONE",
        },
    )

    msp.add_line(
        origine,
        punto_esterno_2,
        dxfattribs={
            "layer": "COSTRUZIONE",
        },
    )

    # Centro.
    msp.add_point(
        origine,
        dxfattribs={
            "layer": "COSTRUZIONE",
        },
    )

    aggiungi_testo(
        msp,
        "SVILUPPO TRONCO DI CONO - FIBRA MEDIA",
        (
            origine[0] + raggio_interno,
            origine[1]
            + raggio_esterno * math.sin(math.radians(angolo_fine))
            + 70,
        ),
        28,
    )


# =============================================================================
# DXF - SVILUPPO CILINDRO
# =============================================================================

def disegna_cilindro(
    msp,
    diametro_esterno,
    altezza,
    spessore,
    origine,
):
    """Disegna lo sviluppo piano del cilindro."""

    diametro_medio = diametro_esterno - spessore

    if diametro_medio <= 0:
        raise ValueError(
            "Lo spessore deve essere minore del diametro del cilindro."
        )

    sviluppo = math.pi * diametro_medio

    x0, y0 = origine

    punti = [
        (x0, y0),
        (x0 + sviluppo, y0),
        (x0 + sviluppo, y0 + altezza),
        (x0, y0 + altezza),
    ]

    # Rettangolo dello sviluppo.
    msp.add_lwpolyline(
        punti,
        close=True,
        dxfattribs={
            "layer": "TAGLIO",
        },
    )

    # Quota larghezza.
    aggiungi_quota_lineare(
        msp,
        punti[0],
        punti[1],
        (
            x0 + sviluppo / 2.0,
            y0 - 80,
        ),
        0,
        f"{sviluppo:.2f}",
    )

    # Quota altezza.
    aggiungi_quota_lineare(
        msp,
        punti[0],
        punti[3],
        (
            x0 - 80,
            y0 + altezza / 2.0,
        ),
        90,
        f"{altezza:.2f}",
    )

    aggiungi_testo(
        msp,
        "SVILUPPO CILINDRO - FIBRA MEDIA",
        (
            x0,
            y0 + altezza + 70,
        ),
        28,
    )

    aggiungi_testo(
        msp,
        (
            f"De={diametro_esterno:.2f}  "
            f"Dm={diametro_medio:.2f}  "
            f"s={spessore:.2f}"
        ),
        (
            x0,
            y0 + altezza + 30,
        ),
        20,
    )

    return sviluppo


# =============================================================================
# CREAZIONE DXF
# =============================================================================

def crea_dxf(
    diametro_superiore,
    diametro_inferiore,
    altezza_cono,
    altezza_cilindro,
    spessore,
    output,
):
    """Crea e salva il DXF."""

    # -------------------------------------------------------------------------
    # Validazione input
    # -------------------------------------------------------------------------

    valori = {
        "Diametro superiore": diametro_superiore,
        "Diametro inferiore": diametro_inferiore,
        "Altezza cono": altezza_cono,
        "Altezza cilindro": altezza_cilindro,
        "Spessore": spessore,
    }

    for nome, valore in valori.items():
        if valore <= 0:
            raise ValueError(
                f"{nome} deve essere maggiore di zero."
            )

    if spessore >= min(
        diametro_superiore,
        diametro_inferiore,
    ):
        raise ValueError(
            "Spessore non compatibile con i diametri inseriti."
        )

    # -------------------------------------------------------------------------
    # Calcolo cono
    # -------------------------------------------------------------------------

    dati = calcola_cono(
        diametro_superiore,
        diametro_inferiore,
        altezza_cono,
        spessore,
    )

    # -------------------------------------------------------------------------
    # Creazione documento DXF
    # -------------------------------------------------------------------------

    doc = ezdxf.new(
        "R2010",
        setup=True,
    )

    doc.units = units.MM
    doc.header["$INSUNITS"] = units.MM

    # Layer.
    doc.layers.add(
        "TAGLIO",
        color=1,
        linetype="CONTINUOUS",
    )

    doc.layers.add(
        "COSTRUZIONE",
        color=8,
        linetype="DASHED",
    )

    doc.layers.add(
        "QUOTE",
        color=3,
        linetype="CONTINUOUS",
    )

    doc.layers.add(
        "TESTI",
        color=7,
        linetype="CONTINUOUS",
    )

    msp = doc.modelspace()

    # -------------------------------------------------------------------------
    # Sviluppo cono
    # -------------------------------------------------------------------------

    origine_cono = (0.0, 0.0)

    disegna_settore_cono(
        msp,
        dati,
        origine_cono,
    )

    ingombro_y_cono = (
        dati["raggio_esterno"]
        * math.sin(
            math.radians(
                dati["angolo"] / 2.0
            )
        )
    )

    # -------------------------------------------------------------------------
    # Sviluppo cilindro
    # -------------------------------------------------------------------------

    origine_cilindro = (
        0.0,
        ingombro_y_cono + 350.0,
    )

    sviluppo_cilindro = disegna_cilindro(
        msp,
        diametro_inferiore,
        altezza_cilindro,
        spessore,
        origine_cilindro,
    )

    # -------------------------------------------------------------------------
    # Tabella dati
    # -------------------------------------------------------------------------

    x_tabella = dati["raggio_esterno"] + 300.0
    y_tabella = ingombro_y_cono

    righe = [
        "DATI DI CALCOLO - DIAMETRI ESTERNI",
        f"Diametro superiore esterno = {diametro_superiore:.2f} mm",
        f"Diametro inferiore esterno = {diametro_inferiore:.2f} mm",
        f"Altezza cono = {altezza_cono:.2f} mm",
        f"Altezza cilindro = {altezza_cilindro:.2f} mm",
        f"Spessore = {spessore:.2f} mm",
        f"Generatrice media = {dati['generatrice']:.2f} mm",
        f"Raggio settore esterno = {dati['raggio_esterno']:.2f} mm",
        f"Raggio settore interno = {dati['raggio_interno']:.2f} mm",
        f"Angolo settore = {dati['angolo']:.6f} gradi",
        f"Sviluppo cilindro = {sviluppo_cilindro:.2f} mm",
        "Nessun sovrametallo incluso.",
    ]

    for indice, riga in enumerate(righe):
        aggiungi_testo(
            msp,
            riga,
            (
                x_tabella,
                y_tabella - indice * 35.0,
            ),
            22 if indice == 0 else 18,
        )

    # -------------------------------------------------------------------------
    # Salvataggio
    # -------------------------------------------------------------------------

    output = Path(output)

    if output.suffix.lower() != ".dxf":
        output = output.with_suffix(".dxf")

    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    doc.saveas(output)

    return (
        output,
        dati,
        sviluppo_cilindro,
    )


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Entry point."""

    output, dati, sviluppo_cilindro = crea_dxf(
        diametro_superiore=DIAMETRO_SUPERIORE,
        diametro_inferiore=DIAMETRO_INFERIORE,
        altezza_cono=ALTEZZA_CONO,
        altezza_cilindro=ALTEZZA_CILINDRO,
        spessore=SPESSORE,
        output=OUTPUT_DXF,
    )

    print()
    print("=" * 60)
    print("DXF CREATO CORRETTAMENTE")
    print("=" * 60)
    print(f"File: {output.resolve()}")
    print()
    print(f"Diametro superiore:      {DIAMETRO_SUPERIORE:.3f} mm")
    print(f"Diametro inferiore:      {DIAMETRO_INFERIORE:.3f} mm")
    print(f"Altezza cono:             {ALTEZZA_CONO:.3f} mm")
    print(f"Altezza cilindro:         {ALTEZZA_CILINDRO:.3f} mm")
    print(f"Spessore:                 {SPESSORE:.3f} mm")
    print()
    print(f"Generatrice media:        {dati['generatrice']:.3f} mm")
    print(f"Raggio settore esterno:   {dati['raggio_esterno']:.3f} mm")
    print(f"Raggio settore interno:   {dati['raggio_interno']:.3f} mm")
    print(f"Angolo settore:           {dati['angolo']:.6f}°")
    print(f"Sviluppo cilindro:        {sviluppo_cilindro:.3f} mm")
    print()
    print("Nota: non sono inclusi sovrametalli di saldatura o rifilatura.")
    print("=" * 60)


if __name__ == "__main__":
    main()