"""Datenmodell des Lebenslaufs: Aufbau, Standardwerte, Beispiel, Laden und Speichern.

Ein Lebenslauf ist ein einfaches dict, das 1:1 als JSON-Datei gespeichert wird:

    {
      "version": 1,
      "kopf":   {"ueberschrift_zeigen", "ueberschrift", "name", "beruf",
                 "foto", "foto_zeigen", "foto_form"},
      "design": {"vorlage", "farbe", "schrift", "schriftgroesse", "spaltenbreite",
                 "unterschrift_zeigen", "ort", "datum"},
      "abschnitte": [{"id", "typ", "titel", "zeigen", ...je nach Typ...}, ...]
    }

Abschnitt-Typen:
    persoenlich  "felder":    [{"id", "label", "wert", "zeigen"}]
    text         "text":      Freitext, Absätze durch Leerzeilen getrennt
    eintraege    "eintraege": [{"id", "von", "bis", "titel", "organisation", "ort",
                                "beschreibung", "zeigen"}]
    kenntnisse   "skala", "anzeige", "eintraege": [{"id", "name", "stufe", "info", "zeigen"}]
    liste        "anzeige", "eintraege": [str]
"""
from __future__ import annotations

import copy
import datetime as _dt
import json
import os
import re
import tempfile
import uuid

from . import design

VERSION = 1

TYPEN = {
    "persoenlich": "Persönliche Daten (Feld + Wert)",
    "text": "Freitext",
    "eintraege": "Stationen mit Zeitraum",
    "kenntnisse": "Kenntnisse mit Stufe",
    "liste": "Einfache Liste",
}

# Stufen 1–5; 0 bedeutet „keine Stufe anzeigen“ (dann nur der Info-Text).
SKALEN = {
    "kenntnisse": ["", "Grundkenntnisse", "Erweiterte Kenntnisse", "Gute Kenntnisse",
                   "Sehr gute Kenntnisse", "Expertenwissen"],
    "sprachen": ["", "Grundkenntnisse (A1/A2)", "Gute Kenntnisse (B1)", "Sehr gute Kenntnisse (B2)",
                 "Verhandlungssicher (C1/C2)", "Muttersprache"],
}
SKALEN_NAMEN = {"kenntnisse": "Kenntnisse", "sprachen": "Sprachen (GER)"}

KENNTNIS_ANZEIGEN = {
    "punkte_text": "Punkte und Text",
    "punkte": "Nur Punkte",
    "text": "Nur Text",
}
LISTEN_ANZEIGEN = {
    "komma": "Fließtext mit Kommas",
    "aufzaehlung": "Aufzählung",
}

FOTO_FORMEN = {"rechteckig": "Rechteckig (3,5 × 4,5 cm)", "rund": "Rund"}

# Persönliche Standardfelder: (Bezeichnung, standardmäßig angezeigt)
STANDARD_FELDER = [
    ("Anschrift", True),
    ("Telefon", True),
    ("E-Mail", True),
    ("Geburtsdatum", True),
    ("Geburtsort", True),
    ("Staatsangehörigkeit", True),
    ("Familienstand", False),
    ("Führerschein", True),
    ("Website", True),
    ("LinkedIn", True),
    ("GitHub", True),
]

# Katalog für „Abschnitt hinzufügen“: (Typ, Titel, Zusatzwerte)
ABSCHNITT_VORLAGEN = [
    ("persoenlich", "Persönliche Daten", {}),
    ("text", "Kurzprofil", {}),
    ("eintraege", "Berufserfahrung", {}),
    ("eintraege", "Ausbildung", {}),
    ("eintraege", "Studium", {}),
    ("eintraege", "Schulbildung", {}),
    ("eintraege", "Praktika", {}),
    ("eintraege", "Weiterbildungen & Zertifikate", {}),
    ("eintraege", "Projekte", {}),
    ("eintraege", "Ehrenamt & Engagement", {}),
    ("eintraege", "Wehrdienst / Freiwilligendienst", {}),
    ("eintraege", "Auslandserfahrung", {}),
    ("kenntnisse", "Fachkenntnisse", {"skala": "kenntnisse"}),
    ("kenntnisse", "EDV-Kenntnisse", {"skala": "kenntnisse"}),
    ("kenntnisse", "Sprachen", {"skala": "sprachen"}),
    ("liste", "Stärken", {"anzeige": "komma"}),
    ("liste", "Interessen & Hobbys", {"anzeige": "komma"}),
    ("eintraege", "Referenzen", {}),
    ("text", "Sonstiges", {}),
]

HEUTE_WOERTER = {"heute", "jetzt", "aktuell", "laufend", "derzeit", "present", "now", "today"}


# ---------------------------------------------------------------- Bausteine

def neue_id() -> str:
    return uuid.uuid4().hex[:10]


def neues_feld(label: str = "Neues Feld", wert: str = "", zeigen: bool = True) -> dict:
    return {"id": neue_id(), "label": label, "wert": wert, "zeigen": zeigen}


def neuer_eintrag(von="", bis="", titel="", organisation="", ort="", beschreibung="", zeigen=True) -> dict:
    return {"id": neue_id(), "von": von, "bis": bis, "titel": titel, "organisation": organisation,
            "ort": ort, "beschreibung": beschreibung, "zeigen": zeigen}


def neue_kenntnis(name: str = "", stufe: int = 3, info: str = "", zeigen: bool = True) -> dict:
    return {"id": neue_id(), "name": name, "stufe": stufe, "info": info, "zeigen": zeigen}


def neuer_abschnitt(typ: str, titel: str | None = None, **zusatz) -> dict:
    if typ not in TYPEN:
        raise ValueError(f"Unbekannter Abschnitt-Typ: {typ}")
    abschnitt = {"id": neue_id(), "typ": typ, "titel": titel or TYPEN[typ], "zeigen": True}
    if typ == "persoenlich":
        abschnitt["felder"] = [neues_feld(label, "", zeigen) for label, zeigen in STANDARD_FELDER]
    elif typ == "text":
        abschnitt["text"] = ""
    elif typ == "eintraege":
        abschnitt["eintraege"] = []
    elif typ == "kenntnisse":
        abschnitt["skala"] = "kenntnisse"
        abschnitt["anzeige"] = "punkte_text"
        abschnitt["eintraege"] = []
    elif typ == "liste":
        abschnitt["anzeige"] = "komma"
        abschnitt["eintraege"] = []
    abschnitt.update(zusatz)
    return abschnitt


def standard_kopf() -> dict:
    return {
        "ueberschrift_zeigen": True,
        "ueberschrift": "Lebenslauf",
        "name": "",
        "beruf": "",
        "foto": None,           # {"daten": base64, "mime": "image/jpeg"}
        "foto_zeigen": True,
        "foto_form": "rechteckig",
    }


def standard_design() -> dict:
    return {
        "vorlage": "klassisch",
        "farbe": design.FARBEN[0][1],
        "schrift": "Georgia",
        "schriftgroesse": 10.5,
        "spaltenbreite": 42,     # mm, Breite der linken Spalte (Zeitraum / Bezeichnung)
        "unterschrift_zeigen": True,
        "ort": "",
        "datum": "",             # leer = Datum des Exports
    }


def leerer_lebenslauf() -> dict:
    return {
        "version": VERSION,
        "kopf": standard_kopf(),
        "design": standard_design(),
        "abschnitte": [
            neuer_abschnitt("persoenlich", "Persönliche Daten"),
            neuer_abschnitt("text", "Kurzprofil"),
            neuer_abschnitt("eintraege", "Berufserfahrung"),
            neuer_abschnitt("eintraege", "Ausbildung"),
            neuer_abschnitt("eintraege", "Schulbildung"),
            neuer_abschnitt("kenntnisse", "Fachkenntnisse"),
            neuer_abschnitt("kenntnisse", "Sprachen", skala="sprachen", anzeige="text"),
            neuer_abschnitt("liste", "Interessen & Hobbys"),
        ],
    }


def beispiel() -> dict:
    """Ein ausgefüllter Beispiel-Lebenslauf (frei erfunden)."""
    cv = leerer_lebenslauf()
    cv["kopf"].update(name="Max Mustermann", beruf="Elektroniker für Automatisierungstechnik")
    cv["design"]["ort"] = "Musterstadt"
    persoenlich, profil, beruf, ausbildung, schule, kenntnisse, sprachen, hobbys = cv["abschnitte"]

    werte = {
        "Anschrift": "Musterstraße 12, 12345 Musterstadt",
        "Telefon": "+49 170 1234567",
        "E-Mail": "max.mustermann@example.com",
        "Geburtsdatum": "14.03.2001",
        "Geburtsort": "Musterstadt",
        "Staatsangehörigkeit": "deutsch",
        "Familienstand": "ledig",
        "Führerschein": "Klasse B",
        "GitHub": "github.com/max-mustermann",
    }
    for feld in persoenlich["felder"]:
        feld["wert"] = werte.get(feld["label"], "")

    profil["text"] = (
        "Elektroniker für Automatisierungstechnik mit vier Jahren Berufserfahrung in der "
        "Inbetriebnahme von SPS-gesteuerten Anlagen. Derzeit in der Weiterbildung zum staatlich "
        "geprüften Techniker. Ich arbeite strukturiert, denke mit und lerne gern im Team."
    )
    beruf["eintraege"] = [
        neuer_eintrag("08/2022", "heute", "Elektroniker für Automatisierungstechnik",
                      "Muster Automation GmbH", "Musterstadt",
                      "- Programmierung und Inbetriebnahme von Siemens S7-1500 (TIA Portal)\n"
                      "- Fehlersuche an PROFINET- und IO-Link-Komponenten\n"
                      "- Betreuung von zwei Auszubildenden"),
        neuer_eintrag("09/2021", "07/2022", "Servicetechniker (befristet)",
                      "Beispiel Anlagenbau AG", "Beispielstadt",
                      "- Wartung und Störungsbeseitigung beim Kunden vor Ort"),
    ]
    ausbildung["eintraege"] = [
        neuer_eintrag("08/2025", "heute", "Staatlich geprüfter Techniker – Automatisierungstechnik",
                      "Fachschule für Technik", "Musterstadt",
                      "Berufsbegleitend, voraussichtlicher Abschluss 07/2029"),
        neuer_eintrag("09/2018", "06/2021", "Ausbildung Elektroniker für Automatisierungstechnik",
                      "Muster Automation GmbH", "Musterstadt",
                      "Abschluss vor der IHK, Note: gut (2,0)"),
    ]
    schule["eintraege"] = [
        neuer_eintrag("2012", "2018", "Mittlere Reife", "Realschule plus am Park", "Musterstadt"),
    ]
    kenntnisse["eintraege"] = [
        neue_kenntnis("SPS-Programmierung (TIA Portal)", 4),
        neue_kenntnis("Elektroplanung (EPLAN)", 3),
        neue_kenntnis("Pneumatik / Elektropneumatik", 4),
        neue_kenntnis("Python", 2),
        neue_kenntnis("Microsoft Office", 4),
    ]
    sprachen["eintraege"] = [
        neue_kenntnis("Deutsch", 5),
        neue_kenntnis("Englisch", 3),
        neue_kenntnis("Spanisch", 1),
    ]
    hobbys["eintraege"] = ["Fußball im Verein", "Elektronik-Basteln", "Radfahren"]
    return cv


# ---------------------------------------------------------------- Laden & Speichern

def _text(wert, standard: str = "") -> str:
    return wert if isinstance(wert, str) else standard


def _bool(wert, standard: bool) -> bool:
    return wert if isinstance(wert, bool) else standard


def _zahl(wert, standard, minimum, maximum):
    if isinstance(wert, bool) or not isinstance(wert, (int, float)):
        return standard
    return min(max(wert, minimum), maximum)


def _liste(wert) -> list:
    return wert if isinstance(wert, list) else []


def normalisieren(daten) -> dict:
    """Prüft eingelesene Daten und ergänzt fehlende Werte, damit ältere oder von Hand
    bearbeitete Dateien sicher funktionieren."""
    if not isinstance(daten, dict) or not isinstance(daten.get("abschnitte"), list):
        raise ValueError("Die Datei enthält keinen Lebenslauf.")

    kopf = standard_kopf()
    alt = daten.get("kopf") if isinstance(daten.get("kopf"), dict) else {}
    for schluessel in ("ueberschrift", "name", "beruf"):
        kopf[schluessel] = _text(alt.get(schluessel), kopf[schluessel])
    for schluessel in ("ueberschrift_zeigen", "foto_zeigen"):
        kopf[schluessel] = _bool(alt.get(schluessel), kopf[schluessel])
    if alt.get("foto_form") in FOTO_FORMEN:
        kopf["foto_form"] = alt["foto_form"]
    foto = alt.get("foto")
    if (isinstance(foto, dict) and isinstance(foto.get("daten"), str) and foto.get("mime") in ("image/png", "image/jpeg")
            and re.fullmatch(r"[A-Za-z0-9+/=\s]+", foto["daten"])):
        kopf["foto"] = {"daten": "".join(foto["daten"].split()), "mime": foto["mime"]}

    des = standard_design()
    alt = daten.get("design") if isinstance(daten.get("design"), dict) else {}
    if alt.get("vorlage") in design.VORLAGEN:
        des["vorlage"] = alt["vorlage"]
    des["farbe"] = design.farbe_pruefen(alt.get("farbe"), des["farbe"])
    if alt.get("schrift") in design.SCHRIFTEN:
        des["schrift"] = alt["schrift"]
    des["schriftgroesse"] = _zahl(alt.get("schriftgroesse"), des["schriftgroesse"], 8, 14)
    des["spaltenbreite"] = _zahl(alt.get("spaltenbreite"), des["spaltenbreite"], 25, 70)
    des["unterschrift_zeigen"] = _bool(alt.get("unterschrift_zeigen"), des["unterschrift_zeigen"])
    des["ort"] = _text(alt.get("ort"))
    des["datum"] = _text(alt.get("datum"))

    abschnitte = []
    for alt in daten["abschnitte"]:
        if not isinstance(alt, dict) or alt.get("typ") not in TYPEN:
            continue
        typ = alt["typ"]
        neu = neuer_abschnitt(typ, _text(alt.get("titel"), TYPEN[typ]))
        neu["id"] = _text(alt.get("id")) or neu["id"]
        neu["zeigen"] = _bool(alt.get("zeigen"), True)
        if typ == "persoenlich":
            neu["felder"] = [
                {"id": _text(f.get("id")) or neue_id(), "label": _text(f.get("label")),
                 "wert": _text(f.get("wert")), "zeigen": _bool(f.get("zeigen"), True)}
                for f in _liste(alt.get("felder")) if isinstance(f, dict)
            ]
        elif typ == "text":
            neu["text"] = _text(alt.get("text"))
        elif typ == "eintraege":
            neu["eintraege"] = []
            for e in _liste(alt.get("eintraege")):
                if isinstance(e, dict):
                    eintrag = neuer_eintrag(**{k: _text(e.get(k)) for k in
                                               ("von", "bis", "titel", "organisation", "ort", "beschreibung")})
                    eintrag["id"] = _text(e.get("id")) or eintrag["id"]
                    eintrag["zeigen"] = _bool(e.get("zeigen"), True)
                    neu["eintraege"].append(eintrag)
        elif typ == "kenntnisse":
            neu["skala"] = alt.get("skala") if alt.get("skala") in SKALEN else "kenntnisse"
            neu["anzeige"] = alt.get("anzeige") if alt.get("anzeige") in KENNTNIS_ANZEIGEN else "punkte_text"
            neu["eintraege"] = []
            for k in _liste(alt.get("eintraege")):
                if isinstance(k, dict):
                    kenntnis = neue_kenntnis(_text(k.get("name")), int(_zahl(k.get("stufe"), 3, 0, 5)),
                                             _text(k.get("info")), _bool(k.get("zeigen"), True))
                    kenntnis["id"] = _text(k.get("id")) or kenntnis["id"]
                    neu["eintraege"].append(kenntnis)
        elif typ == "liste":
            neu["anzeige"] = alt.get("anzeige") if alt.get("anzeige") in LISTEN_ANZEIGEN else "komma"
            neu["eintraege"] = [t for t in _liste(alt.get("eintraege")) if isinstance(t, str)]
        abschnitte.append(neu)

    _ids_eindeutig(abschnitte)
    return {"version": VERSION, "kopf": kopf, "design": des, "abschnitte": abschnitte}


def _ids_eindeutig(abschnitte: list) -> None:
    """Doppelte IDs (z. B. durch Kopieren in der JSON-Datei) bekommen neue Werte –
    die Oberfläche braucht eindeutige IDs."""
    vergeben = {"kopf", "design"}
    for objekt in abschnitte + [e for a in abschnitte for e in a.get("felder", []) + a.get("eintraege", [])
                                if isinstance(e, dict)]:
        if objekt["id"] in vergeben or not re.fullmatch(r"[\w-]{1,40}", objekt["id"]):
            objekt["id"] = neue_id()
        vergeben.add(objekt["id"])


def laden(pfad: str) -> dict:
    with open(pfad, encoding="utf-8") as datei:
        return normalisieren(json.load(datei))


def speichern(cv: dict, pfad: str) -> None:
    """Speichert atomar: erst in eine temporäre Datei, dann umbenennen –
    so bleibt die alte Datei heil, falls etwas schiefgeht."""
    ordner = os.path.dirname(os.path.abspath(pfad))
    os.makedirs(ordner, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=".lebenslauf-", suffix=".json", dir=ordner)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as datei:
            json.dump(cv, datei, ensure_ascii=False, indent=2)
        os.replace(temp, pfad)
    except BaseException:
        if os.path.exists(temp):
            os.remove(temp)
        raise


def kopie(cv: dict) -> dict:
    return copy.deepcopy(cv)


# ---------------------------------------------------------------- Hilfen für die Exporte

def sichtbare_felder(abschnitt: dict) -> list:
    return [f for f in abschnitt.get("felder", []) if f["zeigen"] and f["wert"].strip()]


def sichtbare_eintraege(abschnitt: dict) -> list:
    return [e for e in abschnitt.get("eintraege", []) if e["zeigen"]
            and any(e[k].strip() for k in ("von", "bis", "titel", "organisation", "ort", "beschreibung"))]


def sichtbare_kenntnisse(abschnitt: dict) -> list:
    return [k for k in abschnitt.get("eintraege", []) if k["zeigen"] and k["name"].strip()]


def listen_punkte(abschnitt: dict) -> list:
    return [t.strip() for t in abschnitt.get("eintraege", []) if t.strip()]


def text_absaetze(text: str) -> list:
    """Teilt Freitext an Leerzeilen in Absätze; einfache Zeilenumbrüche bleiben erhalten."""
    absaetze = re.split(r"\n\s*\n", text.strip())
    return [a.strip() for a in absaetze if a.strip()]


def hat_inhalt(abschnitt: dict) -> bool:
    typ = abschnitt["typ"]
    if typ == "persoenlich":
        return bool(sichtbare_felder(abschnitt))
    if typ == "text":
        return bool(abschnitt["text"].strip())
    if typ == "eintraege":
        return bool(sichtbare_eintraege(abschnitt))
    if typ == "kenntnisse":
        return bool(sichtbare_kenntnisse(abschnitt))
    if typ == "liste":
        return bool(listen_punkte(abschnitt))
    return False


def sichtbare_abschnitte(cv: dict) -> list:
    return [a for a in cv["abschnitte"] if a["zeigen"] and hat_inhalt(a)]


def zeitraum(von: str, bis: str) -> str:
    von, bis = von.strip(), bis.strip()
    if von and bis:
        return f"{von} – {bis}"
    return von or bis


def beschreibung_zeilen(text: str) -> list:
    """Zerlegt eine Beschreibung in Zeilen: [(ist_aufzaehlungspunkt, text), ...].
    Zeilen, die mit -, •, * oder – beginnen, werden zu Aufzählungspunkten."""
    zeilen = []
    for zeile in text.splitlines():
        zeile = zeile.strip()
        if not zeile:
            continue
        treffer = re.match(r"^[-•*–]\s*(.*)$", zeile)
        if treffer:
            zeilen.append((True, treffer.group(1).strip()))
        else:
            zeilen.append((False, zeile))
    return zeilen


def stufen_text(skala: str, stufe: int) -> str:
    stufen = SKALEN.get(skala, SKALEN["kenntnisse"])
    return stufen[stufe] if 0 <= stufe < len(stufen) else ""


def kenntnis_text(abschnitt: dict, kenntnis: dict) -> str:
    """Der Text neben einer Kenntnis: eigener Info-Text, sonst der Name der Stufe."""
    return kenntnis["info"].strip() or stufen_text(abschnitt["skala"], kenntnis["stufe"])


_TELEFON = re.compile(r"^\+?[\d\s()/.-]{6,}$")
_DOMAIN = re.compile(r"^(www\.)?([\w-]+\.)+[a-zA-Z]{2,}(/\S*)?$", re.UNICODE)


def link_ziel(label: str, wert: str):
    """Erkennt E-Mail-Adressen, Telefonnummern und Webadressen.
    Gibt (art, ziel) zurück, art ist "mail", "tel", "web" oder None."""
    wert = wert.strip()
    if re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", wert):
        return "mail", "mailto:" + wert
    beschriftung = label.lower()
    if _TELEFON.match(wert) and (re.search(r"telefon|mobil|handy|tel\b|fax", beschriftung) or wert.startswith("+")):
        return "tel", "tel:" + re.sub(r"[^\d+]", "", wert)
    if re.match(r"^https?://\S+$", wert, re.IGNORECASE):
        return "web", wert
    if " " not in wert and _DOMAIN.match(wert):
        return "web", "https://" + wert
    return None, None


def datum_text(cv: dict, heute: _dt.date | None = None) -> str:
    eigenes = cv["design"]["datum"].strip()
    if eigenes:
        return eigenes
    return (heute or _dt.date.today()).strftime("%d.%m.%Y")


def dateiname(cv: dict, endung: str) -> str:
    name = cv["kopf"]["name"].strip()
    teil = re.sub(r"[^\w-]+", "_", name, flags=re.UNICODE).strip("_")
    return f"Lebenslauf_{teil}.{endung}" if teil else f"Lebenslauf.{endung}"
