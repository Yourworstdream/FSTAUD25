# 📄 Lebenslauf-Generator

Ein Desktop-Programm (Python), mit dem du deinen Lebenslauf zusammenstellst und als **Word (.docx)**, **LibreOffice (.odt)** oder **interaktive Webseite (.html)** exportierst.

**Beispiel ansehen:** [Interaktiver Beispiel-Lebenslauf](https://yourworstdream.github.io/FSTAUD25/lebenslauf/beispiel/Lebenslauf_Max_Mustermann.html)

## Was es kann

- **Felder frei auswählen:** Jeder Abschnitt, jedes persönliche Feld (Geburtsdatum, Familienstand, Führerschein …), jeder Eintrag und jede Kenntnis hat einen eigenen Haken – nur was angehakt ist, landet im Lebenslauf. Leere Felder werden automatisch weggelassen.
- **Eigene Struktur:** Abschnitte per Maus ziehen, umbenennen, duplizieren, löschen. Weitere Abschnitte aus einer Liste hinzufügen (Praktika, Projekte, Zertifikate, Ehrenamt …) oder ganz eigene anlegen. Eigene Felder bei den persönlichen Daten.
- **Design „Klassisch“** – der typisch deutsche tabellarische Lebenslauf, anpassbar: Akzentfarbe, Schriftart, Schriftgröße, Breite der Datumsspalte, Foto rechteckig (3,5 × 4,5 cm) oder rund, Überschrift „Lebenslauf“, Ort/Datum/Unterschrift.
- **Live-Vorschau im Browser**, die sich bei jeder Änderung von selbst aktualisiert.
- **Automatisches Sichern** – beim nächsten Start ist alles wieder da.

### Die interaktive Webseite

Eine einzige HTML-Datei ohne Internet-Abhängigkeiten, z. B. zum Verschicken oder zum Veröffentlichen auf GitHub Pages:

- Abschnitte blenden beim Scrollen sanft ein, Kenntnis-Punkte füllen sich animiert
- Abschnitte per Klick ein- und ausklappen
- Hell/Dunkel-Umschalter
- E-Mail und Telefon per Klick kopieren
- Dauer jeder Station wird berechnet („3 Jahre 2 Monate“)
- Inhaltsnavigation am Rand (breiter Bildschirm), Lesefortschritt, „Nach oben“-Knopf
- Passt sich an Handys an
- **Drucken / PDF:** saubere A4-Druckansicht – so bekommst du auch ein PDF („Als PDF speichern“)

## Starten

Du brauchst **Python 3.8 oder neuer** ([python.org](https://www.python.org/downloads/) – unter Windows bei der Installation „Add Python to PATH“ anhaken).

```bash
cd lebenslauf
python lebenslauf.py
```

Unter Windows geht auch ein Doppelklick auf `lebenslauf.py`. Unter Linux fehlt manchmal tkinter: `sudo apt install python3-tk`.

**Optional:** `pip install pillow` – dann wird das Foto automatisch verkleinert, richtig gedreht und auch in der ODT-Datei rund zugeschnitten. Ohne Pillow funktioniert alles andere genauso.

## Bedienung

| Bereich | Was du dort machst |
|---|---|
| **Liste links** | ☑/☐ anklicken = Abschnitt zeigen/verstecken · ziehen = Reihenfolge · `＋ Abschnitt`, ↑ ↓ ⧉ ✕ |
| **Kopf & Foto** | Name, Berufsbezeichnung, Foto und Fotoform |
| **Design & Layout** | Farbe, Schrift, Größe, Spaltenbreite, Ort/Datum/Unterschrift |
| **Persönliche Daten** | Feld + Inhalt, jedes Feld mit Haken, eigene Felder hinzufügen |
| **Stationen** (Beruf, Ausbildung …) | Zeitraum, Titel, Firma/Schule, Ort, Beschreibung – Zeilen mit `-` werden Aufzählungspunkte |
| **Kenntnisse / Sprachen** | Stufe 1–5 als Punkte und/oder Text, Sprachen mit GER-Stufen (A1 … C2) |
| **Liste** (Hobbys, Stärken) | eine Zeile pro Eintrag, als Fließtext oder Aufzählung |

Tastenkürzel: `Strg+S` speichern, `Strg+O` öffnen, `Strg+N` neu, `F5` Live-Vorschau, `F1` Hilfe.

**Speichern** legt eine Projektdatei (`.json`) an, die du später wieder öffnen oder auf einen anderen PC mitnehmen kannst – das Foto ist darin enthalten.

## Export ohne Oberfläche

```bash
python lebenslauf.py --export mein_lebenslauf.json --format docx odt html --ziel ausgabe/
python lebenslauf.py --beispiel --ziel ausgabe/     # Beispiel-Lebenslauf exportieren
```

## Aufbau

```
lebenslauf/
├── lebenslauf.py            Startdatei (Oberfläche oder Kommandozeile)
├── lebenslauf_app/
│   ├── daten.py             Datenmodell, Beispiel, Laden/Speichern
│   ├── design.py            Farben, Schriften, Vorlagen
│   ├── bild.py              Foto einlesen und zuschneiden
│   ├── dokument.py          Layout „Klassisch“ als gemeinsames Dokumentmodell
│   ├── export_docx.py       Word-Export (ohne Zusatzbibliotheken)
│   ├── export_odt.py        LibreOffice-Export (ohne Zusatzbibliotheken)
│   ├── export_html.py       interaktive Webseite
│   ├── vorschau.py          Live-Vorschau (Webserver nur auf 127.0.0.1)
│   └── gui.py               Oberfläche (tkinter)
├── beispiel/                exportierte Beispiel-Webseite
└── tests/                   python -m unittest discover -s tests
```

Ein weiteres Design lässt sich ergänzen, indem man in `design.py` eine Vorlage einträgt und in `dokument.py` / `export_html.py` das Layout dazu schreibt.

## Datenschutz

Alles bleibt auf deinem Rechner. Die Live-Vorschau ist nur von deinem eigenen PC aus erreichbar, der automatisch gesicherte Stand liegt in `~/.lebenslauf-generator/`. **Lade deinen echten Lebenslauf nicht in dieses öffentliche Repository hoch.**
