"""Ein einfaches Dokumentmodell (Absätze, Tabellen, Bilder) und das Layout „Klassisch“.

Das Layout wird nur einmal beschrieben; export_docx.py und export_odt.py übersetzen
dasselbe Modell in Word- bzw. LibreOffice-Format. So sehen beide Dateien gleich aus.
"""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field

from . import bild as _bild
from . import daten, design

SEITE_BREITE = 210.0   # mm, DIN A4
SEITE_HOEHE = 297.0


@dataclass
class Lauf:
    """Ein Stück Text mit einheitlicher Formatierung (in Word: „Run“)."""
    text: str = ""
    fett: bool = False
    kursiv: bool = False
    farbe: str | None = None      # "1F4E79"
    groesse: float | None = None  # pt
    sperrung: float = 0.0         # Zeichenabstand in pt
    link: str | None = None       # mailto:, tel: oder https://
    bild: _bild.Bild | None = None


@dataclass
class Absatz:
    laeufe: list = field(default_factory=list)
    ausrichtung: str = "links"        # links | rechts | mitte
    vor: float = 0.0                  # Abstand davor in pt
    nach: float = 0.0                 # Abstand danach in pt
    aufzaehlung: bool = False
    linie_unten: str | None = None    # Farbe einer Linie unter dem Absatz
    linie_staerke: float = 0.75       # pt
    mit_naechstem: bool = False       # nicht vom nächsten Absatz trennen
    ueberschrift: bool = False        # Abschnittsüberschrift (Gliederungsebene 1)


@dataclass
class Zelle:
    inhalt: list = field(default_factory=list)   # Absatz | Tabelle
    vertikal: str = "oben"                        # oben | mitte | unten


@dataclass
class Tabelle:
    spalten: list            # Breiten in mm
    zeilen: list             # [[Zelle, ...], ...]
    zeilen_zusammenhalten: bool = True   # eine Zeile nicht über zwei Seiten teilen


@dataclass
class Dokument:
    bloecke: list
    schrift: str
    groesse: float
    titel: str
    autor: str
    akzent: str
    rand: tuple = (18.0, 20.0, 16.0, 20.0)   # oben, rechts, unten, links (mm)
    textfarbe: str = design.TEXT
    sprache: str = "de-DE"

    @property
    def nutzbreite(self) -> float:
        return SEITE_BREITE - self.rand[1] - self.rand[3]


# ---------------------------------------------------------------- Layout „Klassisch“

def klassisch(cv: dict, heute: _dt.date | None = None) -> Dokument:
    kopf, des = cv["kopf"], cv["design"]
    akzent = design.lesbare_akzentfarbe(des["farbe"])
    basis = float(des["schriftgroesse"])
    name = kopf["name"].strip()

    dok = Dokument([], des["schrift"], basis, f"Lebenslauf {name}".strip(), name, akzent)
    breite = dok.nutzbreite
    links = float(des["spaltenbreite"])
    rechts = breite - links
    b = dok.bloecke

    if kopf["ueberschrift_zeigen"] and kopf["ueberschrift"].strip():
        b.append(Absatz([Lauf(kopf["ueberschrift"].strip().upper(), fett=True, farbe=akzent,
                              groesse=basis - 1, sperrung=2.5)], nach=6))

    # Kopf: Name und Beruf, rechts daneben das Foto
    kopf_absaetze = []
    if name:
        kopf_absaetze.append(Absatz([Lauf(name, fett=True, farbe=akzent, groesse=basis + 13)], nach=2))
    if kopf["beruf"].strip():
        kopf_absaetze.append(Absatz([Lauf(kopf["beruf"].strip(), farbe=design.GRAU, groesse=basis + 2)]))

    foto = kopf["foto"] if kopf["foto_zeigen"] else None
    if foto:
        f_breite, f_hoehe = design.FOTO_MASSE[kopf["foto_form"]]
        foto_bild = _bild.fuer_dokument(foto, kopf["foto_form"], f_breite, f_hoehe)
        b.append(Tabelle([breite - f_breite - 2, f_breite + 2], [[
            Zelle(kopf_absaetze or [Absatz()], vertikal="mitte"),
            Zelle([Absatz([Lauf(bild=foto_bild)], ausrichtung="rechts")]),
        ]]))
    else:
        b.extend(kopf_absaetze)
    # Trennlinie unter dem Kopf
    b.append(Absatz([Lauf("", groesse=2)], nach=4, linie_unten=akzent, linie_staerke=1.5))

    for abschnitt in daten.sichtbare_abschnitte(cv):
        b.append(Absatz([Lauf(abschnitt["titel"].strip(), fett=True, farbe=akzent, groesse=basis + 2.5)],
                        vor=14, nach=6, linie_unten=design.mischen(akzent, "FFFFFF", 0.55),
                        linie_staerke=0.5, mit_naechstem=True, ueberschrift=True))
        b.extend(_abschnitt(abschnitt, links, rechts, akzent, basis))

    if des["unterschrift_zeigen"]:
        ort_datum = ", ".join(t for t in (des["ort"].strip(), daten.datum_text(cv, heute)) if t)
        b.append(Absatz([Lauf(ort_datum)], vor=30, mit_naechstem=True))
        b.append(Absatz([Lauf("_" * 34, farbe=design.GRAU)], vor=24, mit_naechstem=True))
        if name:
            b.append(Absatz([Lauf(name, farbe=design.GRAU, groesse=basis - 1)], vor=2))
    return dok


def _zeile(text_links: list, inhalt_rechts: list) -> list:
    return [Zelle(text_links), Zelle(inhalt_rechts)]


def _abschnitt(abschnitt: dict, links: float, rechts: float, akzent: str, basis: float) -> list:
    typ = abschnitt["typ"]
    if typ == "persoenlich":
        zeilen = []
        for feld in daten.sichtbare_felder(abschnitt):
            art, ziel = daten.link_ziel(feld["label"], feld["wert"])
            wert = Lauf(feld["wert"].strip(), link=ziel if art else None, farbe=akzent if art else None)
            zeilen.append(_zeile([Absatz([Lauf(feld["label"].strip(), farbe=design.GRAU)], nach=3)],
                                 [Absatz([wert], nach=3)]))
        return [Tabelle([links, rechts], zeilen)]

    if typ == "text":
        return [Absatz([Lauf(a)], nach=5) for a in daten.text_absaetze(abschnitt["text"])]

    if typ == "eintraege":
        zeilen = []
        for e in daten.sichtbare_eintraege(abschnitt):
            rechts_inhalt = []
            if e["titel"].strip():
                rechts_inhalt.append(Absatz([Lauf(e["titel"].strip(), fett=True)], nach=1))
            unterzeile = ", ".join(t.strip() for t in (e["organisation"], e["ort"]) if t.strip())
            if unterzeile:
                rechts_inhalt.append(Absatz([Lauf(unterzeile, kursiv=True, farbe=design.GRAU)], nach=1))
            for punkt, text in daten.beschreibung_zeilen(e["beschreibung"]):
                rechts_inhalt.append(Absatz([Lauf(text)], aufzaehlung=punkt, nach=1))
            if rechts_inhalt:
                rechts_inhalt[-1].nach = 8
            else:
                rechts_inhalt.append(Absatz(nach=8))
            datum = daten.zeitraum(e["von"], e["bis"])
            zeilen.append(_zeile([Absatz([Lauf(datum, farbe=design.GRAU)])], rechts_inhalt))
        return [Tabelle([links, rechts], zeilen)]

    if typ == "kenntnisse":
        zeilen = []
        anzeige = abschnitt["anzeige"]
        for k in daten.sichtbare_kenntnisse(abschnitt):
            laeufe = []
            if anzeige in ("punkte", "punkte_text") and k["stufe"] > 0:
                laeufe.append(Lauf("●" * k["stufe"], farbe=akzent, sperrung=1))
                laeufe.append(Lauf("●" * (5 - k["stufe"]), farbe=design.HELLGRAU, sperrung=1))
            text = daten.kenntnis_text(abschnitt, k)
            if text and (anzeige == "text" or anzeige == "punkte_text" or k["stufe"] == 0):
                laeufe.append(Lauf(("   " if laeufe else "") + text, farbe=design.GRAU if laeufe else None))
            zeilen.append(_zeile([Absatz([Lauf(k["name"].strip())], nach=3)], [Absatz(laeufe, nach=3)]))
        return [Tabelle([links, rechts], zeilen)]

    if typ == "liste":
        punkte = daten.listen_punkte(abschnitt)
        if abschnitt["anzeige"] == "aufzaehlung":
            return [Absatz([Lauf(p)], aufzaehlung=True, nach=1) for p in punkte]
        return [Absatz([Lauf(", ".join(punkte))], nach=4)]
    return []
