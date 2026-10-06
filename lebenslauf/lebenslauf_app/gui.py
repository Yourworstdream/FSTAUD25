"""Die Programmoberfläche (tkinter – ist bei Python unter Windows und macOS schon dabei).

Aufbau: links die Liste der Abschnitte (Haken = anzeigen, ziehen = Reihenfolge ändern),
rechts der Bearbeitungsbereich für den ausgewählten Eintrag. Jede Änderung wird sofort
automatisch gesichert und – falls geöffnet – in der Live-Vorschau im Browser angezeigt.
"""
from __future__ import annotations

import io
import json
import math
import os
import subprocess
import sys
import tkinter as tk
import tkinter.font as tkfont
import webbrowser
from pathlib import Path
from tkinter import colorchooser, filedialog, messagebox, ttk

from . import __version__, bild, daten, design, export_html, exporte
from .vorschau import LiveVorschau

APP_NAME = "Lebenslauf-Generator"
ORDNER = Path.home() / ".lebenslauf-generator"
AUTOSAVE = ORDNER / "autosave.json"
FEST = ("kopf", "design")          # feste Einträge oben in der Liste
AN, AUS = "☑", "☐"

HILFE = """So funktioniert's

1. Links einen Bereich auswählen und rechts ausfüllen.
2. Haken in der Liste: Abschnitt erscheint im Lebenslauf (☑) oder nicht (☐).
   Auch einzelne Felder und Einträge haben eigene Haken.
3. Reihenfolge: Abschnitte mit der Maus ziehen oder ↑ / ↓ benutzen.
4. „＋ Abschnitt“ fügt weitere Abschnitte hinzu – auch eigene.
5. „Live-Vorschau“ öffnet den Lebenslauf im Browser; er aktualisiert sich
   bei jeder Änderung von selbst.
6. Export: Word (.docx), LibreOffice (.odt) oder interaktive Webseite (.html).
   Ein PDF bekommst du über die Webseite: „Drucken / PDF“ → „Als PDF speichern“.

Alles wird automatisch gesichert. Mit „Speichern“ legst du zusätzlich eine
Projektdatei (.json) an, die du später wieder öffnen oder weitergeben kannst.

Beschreibungen: eine Zeile pro Punkt. Zeilen, die mit „-“ beginnen,
werden zu Aufzählungspunkten.
Zeiträume: z. B. „09/2023“ bis „heute“ – dann berechnet die Webseite die Dauer."""


def datei_oeffnen(pfad: str) -> None:
    """Öffnet eine Datei mit dem passenden Programm des Betriebssystems."""
    if pfad.lower().endswith(".html"):
        webbrowser.open(Path(pfad).resolve().as_uri())
    elif sys.platform.startswith("win"):
        os.startfile(pfad)  # noqa: S606 – Datei hat der Nutzer selbst gewählt
    elif sys.platform == "darwin":
        subprocess.Popen(["open", pfad])
    else:
        subprocess.Popen(["xdg-open", pfad])


class ScrollRahmen(ttk.Frame):
    """Ein Rahmen mit senkrechter Bildlaufleiste; der Inhalt kommt in `.innen`."""

    def __init__(self, eltern, **kw):
        super().__init__(eltern, **kw)
        hintergrund = ttk.Style(self).lookup("TFrame", "background") or None
        self.canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0, background=hintergrund)
        leiste = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=leiste.set)
        self.innen = ttk.Frame(self.canvas, padding=(18, 14, 18, 24))
        self._fenster = self.canvas.create_window(0, 0, window=self.innen, anchor="nw")
        self.canvas.grid(row=0, column=0, sticky="nsew")
        leiste.grid(row=0, column=1, sticky="ns")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.innen.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self._fenster, width=e.width))
        self.canvas.bind("<Enter>", self._rad_an)
        self.canvas.bind("<Leave>", self._rad_aus)

    def _rad_an(self, _e=None):
        self.bind_all("<MouseWheel>", self._rad)
        self.bind_all("<Button-4>", self._rad)
        self.bind_all("<Button-5>", self._rad)

    def _rad_aus(self, _e=None):
        self.unbind_all("<MouseWheel>")
        self.unbind_all("<Button-4>")
        self.unbind_all("<Button-5>")

    def _rad(self, event):
        # Textfelder und Listen scrollen selbst
        if isinstance(event.widget, (tk.Text, ttk.Treeview, tk.Listbox)):
            return
        if self.innen.winfo_reqheight() <= self.canvas.winfo_height():
            return
        if getattr(event, "num", None) == 4:
            schritt = -1
        elif getattr(event, "num", None) == 5:
            schritt = 1
        else:
            schritt = -1 if event.delta > 0 else 1
        self.canvas.yview_scroll(schritt * 2, "units")

    def nach_oben(self):
        self.canvas.yview_moveto(0)


class App:
    def __init__(self, root: tk.Tk, pfad: str | None = None):
        self.root = root
        self.vorschau = LiveVorschau()
        self.datei: str | None = None
        self.ungespeichert = False         # Änderungen seit dem letzten Speichern als Datei
        self.export_ordner = str(Path.home())
        self._timer = {}
        self._foto_ref = None
        self._ziehen = None
        self.auswahl = None

        self.cv, hinweis = self._startdaten(pfad)
        self._stile()
        self._menue()
        self._oberflaeche()
        self.baum_fuellen()
        self.auswaehlen("kopf")
        self.titel_aktualisieren()
        self.status(hinweis)
        root.protocol("WM_DELETE_WINDOW", self.beenden)

    # ------------------------------------------------------------------ Start & Aussehen

    def _startdaten(self, pfad):
        if pfad:
            try:
                cv = daten.laden(pfad)
                self.datei = os.path.abspath(pfad)
                return cv, f"Geöffnet: {pfad}"
            except (OSError, ValueError, json.JSONDecodeError) as fehler:
                messagebox.showerror(APP_NAME, f"Die Datei konnte nicht geöffnet werden:\n{fehler}")
        try:
            with open(AUTOSAVE, encoding="utf-8") as f:
                gesichert = json.load(f)
            cv = daten.normalisieren(gesichert["lebenslauf"])
            self.datei = gesichert.get("datei") if isinstance(gesichert.get("datei"), str) else None
            self.ungespeichert = bool(gesichert.get("ungespeichert"))
            if isinstance(gesichert.get("export_ordner"), str):
                self.export_ordner = gesichert["export_ordner"]
            return cv, "Letzter Stand wiederhergestellt."
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            return daten.beispiel(), "Willkommen! Ein Beispiel ist geladen – „Datei → Neu“ startet leer."

    def _stile(self):
        stil = ttk.Style(self.root)
        if stil.theme_use() not in ("vista", "aqua", "winnative"):
            stil.theme_use("clam")
        familie = tkfont.nametofont("TkDefaultFont").actual("family")
        basis = (familie,)
        self.schrift_titel = (familie, 15, "bold")
        self.schrift_klein = (familie, 9)
        self.root.option_add("*Text.font", "TkTextFont")
        stil.configure("Titel.TLabel", font=self.schrift_titel)
        stil.configure("Klein.TLabel", font=self.schrift_klein, foreground="#5f6368")
        stil.configure("Haupt.TButton", font=(basis[0], 10, "bold"))
        stil.configure("Treeview", rowheight=28)
        stil.configure("Abschnitte.Treeview", font=(basis[0], 10))

    def _menue(self):
        m = tk.Menu(self.root)
        datei = tk.Menu(m, tearoff=False)
        datei.add_command(label="Neu (leer)", accelerator="Strg+N", command=self.neu)
        datei.add_command(label="Beispiel laden", command=self.beispiel_laden)
        datei.add_command(label="Öffnen …", accelerator="Strg+O", command=self.oeffnen)
        datei.add_separator()
        datei.add_command(label="Speichern", accelerator="Strg+S", command=self.speichern)
        datei.add_command(label="Speichern unter …", command=lambda: self.speichern(neu=True))
        datei.add_separator()
        datei.add_command(label="Beenden", command=self.beenden)
        m.add_cascade(label="Datei", menu=datei)

        export = tk.Menu(m, tearoff=False)
        for kuerzel, (beschreibung, endung, _) in exporte.FORMATE.items():
            export.add_command(label=f"{beschreibung} (.{endung}) …", command=lambda k=kuerzel: self.exportieren(k))
        export.add_separator()
        export.add_command(label="Alle Formate in einen Ordner …", command=self.alle_exportieren)
        m.add_cascade(label="Export", menu=export)

        ansicht = tk.Menu(m, tearoff=False)
        ansicht.add_command(label="Live-Vorschau im Browser", accelerator="F5", command=self.live_vorschau)
        m.add_cascade(label="Ansicht", menu=ansicht)

        hilfe = tk.Menu(m, tearoff=False)
        hilfe.add_command(label="Kurzanleitung", accelerator="F1", command=self.hilfe)
        hilfe.add_command(label="Über", command=lambda: messagebox.showinfo(
            APP_NAME, f"{APP_NAME} {__version__}\n\nErstellt Lebensläufe als Word-, LibreOffice- "
                      f"und interaktive Web-Datei.\n\nFoto-Bearbeitung mit Pillow: {'ja' if bild.PILLOW else 'nein'}"))
        m.add_cascade(label="Hilfe", menu=hilfe)
        self.root.configure(menu=m)

        for taste, befehl in (("<Control-n>", self.neu), ("<Control-o>", self.oeffnen),
                              ("<Control-s>", self.speichern), ("<F5>", self.live_vorschau), ("<F1>", self.hilfe)):
            self.root.bind_all(taste, lambda e, b=befehl: (b(), "break")[1])

    def _oberflaeche(self):
        leiste = ttk.Frame(self.root, padding=(10, 8, 10, 4))
        leiste.pack(fill="x")
        ttk.Button(leiste, text="▶  Live-Vorschau", style="Haupt.TButton", command=self.live_vorschau).pack(side="left")
        ttk.Separator(leiste, orient="vertical").pack(side="left", fill="y", padx=10)
        ttk.Label(leiste, text="Export:").pack(side="left", padx=(0, 6))
        for kuerzel, text in (("docx", "Word (.docx)"), ("odt", "LibreOffice (.odt)"), ("html", "Webseite (.html)")):
            ttk.Button(leiste, text=text, command=lambda k=kuerzel: self.exportieren(k)).pack(side="left", padx=2)
        ttk.Button(leiste, text="Speichern", command=self.speichern).pack(side="right")

        teiler = ttk.PanedWindow(self.root, orient="horizontal")
        teiler.pack(fill="both", expand=True, padx=10, pady=(4, 0))

        links = ttk.Frame(teiler, padding=(0, 4, 6, 0))
        self.baum = ttk.Treeview(links, columns=("zeigen", "titel"), show="headings", selectmode="browse",
                                 style="Abschnitte.Treeview")
        self.baum.heading("zeigen", text="✓")
        self.baum.heading("titel", text="Abschnitte (ziehen = sortieren)", anchor="w")
        self.baum.column("zeigen", width=34, minwidth=34, stretch=False, anchor="center")
        self.baum.column("titel", width=230, anchor="w")
        self.baum.tag_configure("fest", background="#eef2f7")
        self.baum.tag_configure("aus", foreground="#9aa0a6")
        self.baum.pack(fill="both", expand=True)
        self.baum.bind("<<TreeviewSelect>>", lambda e: self.auswaehlen(self.baum.focus()))
        self.baum.bind("<ButtonPress-1>", self._baum_klick, add=True)
        self.baum.bind("<B1-Motion>", self._baum_ziehen)
        self.baum.bind("<ButtonRelease-1>", self._baum_loslassen)
        self.baum.bind("<space>", lambda e: (self.sichtbar_umschalten(self.baum.focus()), "break")[1])
        self.baum.bind("<Delete>", lambda e: self.abschnitt_loeschen())

        knoepfe = ttk.Frame(links, padding=(0, 6, 0, 0))
        knoepfe.pack(fill="x")
        hinzu = ttk.Menubutton(knoepfe, text="＋ Abschnitt")
        menue = tk.Menu(hinzu, tearoff=False)
        for typ, titel, extra in daten.ABSCHNITT_VORLAGEN:
            menue.add_command(label=titel, command=lambda t=typ, ti=titel, ex=extra: self.abschnitt_hinzu(t, ti, ex))
        menue.add_separator()
        menue.add_command(label="Eigener Abschnitt …", command=self.eigener_abschnitt)
        hinzu["menu"] = menue
        hinzu.pack(side="left")
        for text, befehl, tipp in (("✕", self.abschnitt_loeschen, "Löschen"), ("⧉", self.abschnitt_duplizieren, "Duplizieren"),
                                   ("↓", lambda: self.abschnitt_verschieben(1), "Nach unten"),
                                   ("↑", lambda: self.abschnitt_verschieben(-1), "Nach oben")):
            b = ttk.Button(knoepfe, text=text, width=3, command=befehl)
            b.pack(side="right", padx=1)
            _Tooltip(b, tipp)
        teiler.add(links, weight=0)

        self.editor = ScrollRahmen(teiler)
        teiler.add(self.editor, weight=1)

        self.statuszeile = ttk.Label(self.root, padding=(12, 4), style="Klein.TLabel", anchor="w")
        self.statuszeile.pack(fill="x")

    # ------------------------------------------------------------------ Abschnittsliste

    def _abschnitt(self, iid):
        return next((a for a in self.cv["abschnitte"] if a["id"] == iid), None)

    def baum_fuellen(self):
        self.baum.delete(*self.baum.get_children())
        self.baum.insert("", "end", iid="kopf", values=("✎", "Kopf & Foto"), tags=("fest",))
        self.baum.insert("", "end", iid="design", values=("◆", "Design & Layout"), tags=("fest",))
        for a in self.cv["abschnitte"]:
            self.baum.insert("", "end", iid=a["id"])
            self.baum_zeile(a)

    def baum_zeile(self, a):
        leer = "" if daten.hat_inhalt(a) else "   (leer)"
        self.baum.item(a["id"], values=(AN if a["zeigen"] else AUS, (a["titel"] or "Ohne Titel") + leer),
                       tags=() if a["zeigen"] else ("aus",))

    def _baum_klick(self, event):
        zeile = self.baum.identify_row(event.y)
        self._ziehen = zeile if zeile and zeile not in FEST else None
        if zeile and self.baum.identify_column(event.x) == "#1" and self.baum.identify_region(event.x, event.y) == "cell":
            self.sichtbar_umschalten(zeile)

    def _baum_ziehen(self, event):
        if not self._ziehen:
            return
        ziel = self.baum.identify_row(event.y)
        if ziel and ziel != self._ziehen:
            index = max(len(FEST), self.baum.index(ziel))
            self.baum.move(self._ziehen, "", index)

    def _baum_loslassen(self, _event):
        if not self._ziehen:
            return
        reihenfolge = [i for i in self.baum.get_children() if i not in FEST]
        alt = [a["id"] for a in self.cv["abschnitte"]]
        if reihenfolge != alt:
            self.cv["abschnitte"].sort(key=lambda a: reihenfolge.index(a["id"]))
            self.geaendert()
        self._ziehen = None

    def sichtbar_umschalten(self, iid):
        a = self._abschnitt(iid)
        if a:
            a["zeigen"] = not a["zeigen"]
            self.baum_zeile(a)
            if self.auswahl == iid and hasattr(self, "_zeigen_var"):
                self._zeigen_var.set(a["zeigen"])
            self.geaendert()

    def abschnitt_hinzu(self, typ, titel, extra=None):
        a = daten.neuer_abschnitt(typ, titel, **(extra or {}))
        self.cv["abschnitte"].append(a)
        self.baum.insert("", "end", iid=a["id"])
        self.baum_zeile(a)
        self.auswaehlen(a["id"])
        self.geaendert()

    def eigener_abschnitt(self):
        dialog = _EigenerAbschnittDialog(self.root)
        if dialog.ergebnis:
            titel, typ = dialog.ergebnis
            self.abschnitt_hinzu(typ, titel)

    def abschnitt_loeschen(self):
        a = self._abschnitt(self.auswahl)
        if not a:
            return
        if daten.hat_inhalt(a) and not messagebox.askyesno(
                "Abschnitt löschen", f"Den Abschnitt „{a['titel']}“ mit allen Einträgen löschen?\n\n"
                                     "Tipp: Zum Ausblenden reicht es, den Haken zu entfernen."):
            return
        index = self.cv["abschnitte"].index(a)
        self.cv["abschnitte"].remove(a)
        self.baum.delete(a["id"])
        rest = self.cv["abschnitte"]
        self.auswaehlen(rest[min(index, len(rest) - 1)]["id"] if rest else "kopf")
        self.geaendert()

    def abschnitt_duplizieren(self):
        a = self._abschnitt(self.auswahl)
        if not a:
            return
        neu = daten.normalisieren({"abschnitte": [daten.kopie(a)]})["abschnitte"][0]
        neu["id"] = daten.neue_id()
        for e in neu.get("felder", []) + [e for e in neu.get("eintraege", []) if isinstance(e, dict)]:
            e["id"] = daten.neue_id()
        neu["titel"] = a["titel"] + " (Kopie)"
        index = self.cv["abschnitte"].index(a) + 1
        self.cv["abschnitte"].insert(index, neu)
        self.baum.insert("", index + len(FEST), iid=neu["id"])
        self.baum_zeile(neu)
        self.auswaehlen(neu["id"])
        self.geaendert()

    def abschnitt_verschieben(self, richtung):
        a = self._abschnitt(self.auswahl)
        if not a:
            return
        liste = self.cv["abschnitte"]
        alt = liste.index(a)
        neu = alt + richtung
        if 0 <= neu < len(liste):
            liste.insert(neu, liste.pop(alt))
            self.baum.move(a["id"], "", neu + len(FEST))
            self.baum.see(a["id"])
            self.geaendert()

    # ------------------------------------------------------------------ Bearbeiten

    def auswaehlen(self, iid):
        if not iid or not self.baum.exists(iid):
            return
        if self.baum.selection() != (iid,):
            self.baum.selection_set(iid)
            self.baum.focus(iid)
            self.baum.see(iid)
        if iid != self.auswahl:
            self.auswahl = iid
            self.editor_neu()
            self.editor.nach_oben()

    def editor_neu(self):
        """Baut den rechten Bereich für die aktuelle Auswahl neu auf."""
        for kind in self.editor.innen.winfo_children():
            kind.destroy()
        rahmen = self.editor.innen
        rahmen.columnconfigure(1, weight=1)
        if self.auswahl == "kopf":
            self._editor_kopf(rahmen)
        elif self.auswahl == "design":
            self._editor_design(rahmen)
        else:
            a = self._abschnitt(self.auswahl)
            if a:
                getattr(self, f"_editor_{a['typ']}")(rahmen, a)

    # --- kleine Bausteine, die direkt in die Daten schreiben

    def _eingabe(self, eltern, obj, schluessel, breite=40, danach=None):
        var = tk.StringVar(value=obj[schluessel])

        def schreiben(*_):
            obj[schluessel] = var.get()
            if danach:
                danach()
            self.geaendert()
        var.trace_add("write", schreiben)
        feld = ttk.Entry(eltern, textvariable=var, width=breite)
        feld.var = var
        return feld

    def _textfeld(self, eltern, obj, schluessel, hoehe=6, als_liste=False):
        rahmen = ttk.Frame(eltern)
        feld = tk.Text(rahmen, height=hoehe, wrap="word", undo=True, relief="solid", borderwidth=1,
                       padx=6, pady=4, highlightthickness=1, highlightcolor="#4a7bd0")
        leiste = ttk.Scrollbar(rahmen, orient="vertical", command=feld.yview)
        feld.configure(yscrollcommand=leiste.set)
        feld.pack(side="left", fill="both", expand=True)
        leiste.pack(side="right", fill="y")
        wert = obj[schluessel]
        feld.insert("1.0", "\n".join(wert) if als_liste else wert)
        feld.edit_modified(False)

        def geaendert(_e=None):
            if feld.edit_modified():
                text = feld.get("1.0", "end-1c")
                obj[schluessel] = text.split("\n") if als_liste else text
                feld.edit_modified(False)
                self.geaendert()
        feld.bind("<<Modified>>", geaendert)
        return rahmen

    def _haken(self, eltern, obj, schluessel, text, danach=None):
        var = tk.BooleanVar(value=obj[schluessel])

        def schreiben():
            obj[schluessel] = var.get()
            if danach:
                danach()
            self.geaendert()
        knopf = ttk.Checkbutton(eltern, text=text, variable=var, command=schreiben)
        knopf.var = var
        return knopf

    def _ueberschrift(self, eltern, text, zeile, hinweis=None):
        ttk.Label(eltern, text=text, style="Titel.TLabel").grid(row=zeile, column=0, columnspan=4, sticky="w")
        if hinweis:
            ttk.Label(eltern, text=hinweis, style="Klein.TLabel", wraplength=640, justify="left").grid(
                row=zeile + 1, column=0, columnspan=4, sticky="w", pady=(2, 10))
        return zeile + 2

    def _kopfzeile_abschnitt(self, eltern, a, hinweis):
        """Titel, „anzeigen“-Haken und Hinweis – gleich für alle Abschnitte."""
        z = self._ueberschrift(eltern, a["titel"] or "Abschnitt", 0, hinweis)
        kopf = eltern.grid_slaves(row=0, column=0)[0]
        ttk.Label(eltern, text="Überschrift").grid(row=z, column=0, sticky="w", pady=3)

        def umbenannt():
            kopf.configure(text=a["titel"] or "Abschnitt")
            self.baum_zeile(a)
        titel = self._eingabe(eltern, a, "titel", danach=umbenannt)
        titel.grid(row=z, column=1, sticky="we", pady=3)
        zeigen = self._haken(eltern, a, "zeigen", "Abschnitt im Lebenslauf anzeigen", danach=lambda: self.baum_zeile(a))
        zeigen.grid(row=z + 1, column=1, sticky="w", pady=(0, 10))
        self._zeigen_var = zeigen.var
        return z + 2

    @staticmethod
    def _klein_knopf(eltern, text, befehl, tipp=None):
        knopf = ttk.Button(eltern, text=text, width=3, command=befehl)
        if tipp:
            _Tooltip(knopf, tipp)
        return knopf

    # --- Kopf

    def _editor_kopf(self, r):
        kopf = self.cv["kopf"]
        z = self._ueberschrift(r, "Kopf & Foto", 0, "Name, Berufsbezeichnung und Foto stehen ganz oben im Lebenslauf.")
        self._haken(r, kopf, "ueberschrift_zeigen", "Überschrift anzeigen:").grid(row=z, column=0, sticky="w", pady=3)
        self._eingabe(r, kopf, "ueberschrift").grid(row=z, column=1, sticky="we", pady=3)
        ttk.Label(r, text="Name").grid(row=z + 1, column=0, sticky="w", pady=3)
        name = self._eingabe(r, kopf, "name")
        name.grid(row=z + 1, column=1, sticky="we", pady=3)
        ttk.Label(r, text="Berufsbezeichnung").grid(row=z + 2, column=0, sticky="w", pady=3)
        self._eingabe(r, kopf, "beruf").grid(row=z + 2, column=1, sticky="we", pady=3)

        ttk.Label(r, text="Foto", style="Titel.TLabel").grid(row=z + 3, column=0, columnspan=2, sticky="w", pady=(18, 6))
        bereich = ttk.Frame(r)
        bereich.grid(row=z + 4, column=0, columnspan=2, sticky="w")
        self._foto_ref = self._vorschaubild()
        if self._foto_ref is not None:
            ttk.Label(bereich, image=self._foto_ref, relief="solid").grid(row=0, column=0, rowspan=4, padx=(0, 14))
        elif kopf["foto"]:
            ttk.Label(bereich, text="Foto gewählt ✓\n(Vorschau hier nur\nmit Pillow)", relief="solid",
                      padding=10, justify="center").grid(row=0, column=0, rowspan=4, padx=(0, 14))
        knoepfe = ttk.Frame(bereich)
        knoepfe.grid(row=0, column=1, sticky="w")
        ttk.Button(knoepfe, text="Foto wählen …", command=self.foto_waehlen).pack(side="left")
        if kopf["foto"]:
            ttk.Button(knoepfe, text="Entfernen", command=self.foto_entfernen).pack(side="left", padx=6)
        self._haken(bereich, kopf, "foto_zeigen", "Foto im Lebenslauf anzeigen").grid(row=1, column=1, sticky="w", pady=(8, 2))
        form = tk.StringVar(value=kopf["foto_form"])

        def form_setzen():
            kopf["foto_form"] = form.get()
            self.geaendert()
        for nr, (schluessel, text) in enumerate(daten.FOTO_FORMEN.items()):
            ttk.Radiobutton(bereich, text=text, value=schluessel, variable=form, command=form_setzen).grid(
                row=2 + nr, column=1, sticky="w")
        bereich.form_var = form
        if not bild.PILLOW:
            ttk.Label(r, text="Tipp: Mit „pip install pillow“ wird das Foto automatisch verkleinert, gedreht und "
                              "auch in LibreOffice rund zugeschnitten.", style="Klein.TLabel", wraplength=600).grid(
                row=z + 5, column=0, columnspan=2, sticky="w", pady=(10, 0))

    def _vorschaubild(self):
        foto = self.cv["kopf"]["foto"]
        if not foto:
            return None
        try:
            if bild.PILLOW:
                from PIL import Image, ImageTk
                with Image.open(io.BytesIO(bild.foto_bytes(foto))) as im:
                    im = im.convert("RGB")
                    im.thumbnail((110, 140))
                    return ImageTk.PhotoImage(im)
            if foto["mime"] == "image/png":
                ph = tk.PhotoImage(data=foto["daten"])
                faktor = max(1, math.ceil(max(ph.width() / 110, ph.height() / 140)))
                return ph.subsample(faktor)
        except (tk.TclError, OSError, ImportError):
            pass
        return None

    def foto_waehlen(self):
        pfad = filedialog.askopenfilename(title="Foto wählen", filetypes=[
            ("Bilder", "*.jpg *.jpeg *.png *.JPG *.JPEG *.PNG"), ("Alle Dateien", "*.*")])
        if not pfad:
            return
        try:
            self.cv["kopf"]["foto"] = bild.foto_laden(pfad)
        except (OSError, ValueError) as fehler:
            messagebox.showerror("Foto", str(fehler))
            return
        self.cv["kopf"]["foto_zeigen"] = True
        self.editor_neu()
        self.geaendert()

    def foto_entfernen(self):
        self.cv["kopf"]["foto"] = None
        self.editor_neu()
        self.geaendert()

    # --- Design

    def _editor_design(self, r):
        des = self.cv["design"]
        z = self._ueberschrift(r, "Design & Layout", 0, "Gilt für alle Exporte – Word, LibreOffice und Webseite.")
        ttk.Label(r, text="Vorlage").grid(row=z, column=0, sticky="w", pady=4)
        vorlage = ttk.Combobox(r, values=list(design.VORLAGEN.values()), state="readonly", width=20)
        vorlage.set(design.VORLAGEN[des["vorlage"]])
        vorlage.grid(row=z, column=1, sticky="w", pady=4)

        ttk.Label(r, text="Akzentfarbe").grid(row=z + 1, column=0, sticky="nw", pady=6)
        farben = ttk.Frame(r)
        farben.grid(row=z + 1, column=1, sticky="w", pady=6)
        for nr, (name, farbe) in enumerate(design.FARBEN):
            gewaehlt = des["farbe"].upper() == farbe.upper()
            feld = tk.Label(farben, bg=farbe, width=4, height=2, cursor="hand2",
                            relief="sunken" if gewaehlt else "flat", borderwidth=3,
                            highlightthickness=2, highlightbackground="#222" if gewaehlt else farbe)
            feld.grid(row=0, column=nr, padx=3)
            feld.bind("<Button-1>", lambda e, f=farbe: self._farbe_setzen(f))
            _Tooltip(feld, name)
        ttk.Button(farben, text="Eigene Farbe …", command=self._farbe_waehlen).grid(row=0, column=len(design.FARBEN), padx=(10, 0))
        ttk.Label(farben, text=f"Aktuell: {des['farbe']}", style="Klein.TLabel").grid(
            row=1, column=0, columnspan=len(design.FARBEN) + 1, sticky="w", pady=(4, 0))

        ttk.Label(r, text="Schriftart").grid(row=z + 2, column=0, sticky="w", pady=4)
        schrift = ttk.Combobox(r, values=list(design.SCHRIFTEN), state="readonly", width=20)
        schrift.set(des["schrift"])
        schrift.grid(row=z + 2, column=1, sticky="w", pady=4)
        schrift.bind("<<ComboboxSelected>>", lambda e: (des.__setitem__("schrift", schrift.get()), self.geaendert()))

        ttk.Label(r, text="Schriftgröße").grid(row=z + 3, column=0, sticky="w", pady=4)
        groesse = ttk.Combobox(r, values=[f"{g:g} pt" for g in design.SCHRIFTGROESSEN], state="readonly", width=20)
        groesse.set(f"{des['schriftgroesse']:g} pt")
        groesse.grid(row=z + 3, column=1, sticky="w", pady=4)
        groesse.bind("<<ComboboxSelected>>", lambda e: (
            des.__setitem__("schriftgroesse", design.SCHRIFTGROESSEN[groesse.current()]), self.geaendert()))

        ttk.Label(r, text="Linke Spalte").grid(row=z + 4, column=0, sticky="w", pady=4)
        spalte = ttk.Frame(r)
        spalte.grid(row=z + 4, column=1, sticky="w", pady=4)
        anzeige = ttk.Label(spalte, text=f"{des['spaltenbreite']:.0f} mm", width=7)
        regler = ttk.Scale(spalte, from_=25, to=70, length=220, value=des["spaltenbreite"])

        def spalte_setzen(wert):
            des["spaltenbreite"] = round(float(wert))
            anzeige.configure(text=f"{des['spaltenbreite']} mm")
            self.geaendert()
        regler.configure(command=spalte_setzen)
        regler.pack(side="left")
        anzeige.pack(side="left", padx=8)
        ttk.Label(spalte, text="(Zeiträume und Bezeichnungen)", style="Klein.TLabel").pack(side="left")

        ttk.Label(r, text="Abschluss", style="Titel.TLabel").grid(row=z + 5, column=0, columnspan=2, sticky="w", pady=(18, 6))
        self._haken(r, des, "unterschrift_zeigen", "Ort, Datum und Unterschriftslinie anzeigen").grid(
            row=z + 6, column=0, columnspan=2, sticky="w")
        ttk.Label(r, text="Ort").grid(row=z + 7, column=0, sticky="w", pady=3)
        self._eingabe(r, des, "ort", breite=30).grid(row=z + 7, column=1, sticky="w", pady=3)
        ttk.Label(r, text="Datum").grid(row=z + 8, column=0, sticky="w", pady=3)
        datum = ttk.Frame(r)
        datum.grid(row=z + 8, column=1, sticky="w", pady=3)
        self._eingabe(datum, des, "datum", breite=14).pack(side="left")
        ttk.Label(datum, text="  leer lassen = immer das aktuelle Datum", style="Klein.TLabel").pack(side="left")

    def _farbe_setzen(self, farbe):
        self.cv["design"]["farbe"] = design.farbe_pruefen(farbe, self.cv["design"]["farbe"])
        self.editor_neu()
        self.geaendert()

    def _farbe_waehlen(self):
        _, farbe = colorchooser.askcolor(color=self.cv["design"]["farbe"], title="Akzentfarbe wählen")
        if farbe:
            self._farbe_setzen(farbe)

    # --- Persönliche Daten

    def _editor_persoenlich(self, r, a):
        z = self._kopfzeile_abschnitt(r, a, "Haken = Feld erscheint im Lebenslauf. Leere Felder werden automatisch "
                                             "weggelassen. Bezeichnungen kannst du frei ändern.")
        tabelle = ttk.Frame(r)
        tabelle.grid(row=z, column=0, columnspan=2, sticky="we")
        tabelle.columnconfigure(2, weight=1)
        ttk.Label(tabelle, text="Bezeichnung", style="Klein.TLabel").grid(row=0, column=1, sticky="w")
        ttk.Label(tabelle, text="Inhalt", style="Klein.TLabel").grid(row=0, column=2, sticky="w")
        felder = a["felder"]
        for nr, feld in enumerate(felder, 1):
            self._haken(tabelle, feld, "zeigen", "").grid(row=nr, column=0, padx=(0, 4))
            self._eingabe(tabelle, feld, "label", breite=20).grid(row=nr, column=1, sticky="w", pady=2, padx=(0, 6))
            self._eingabe(tabelle, feld, "wert", danach=lambda: self.baum_zeile(a)).grid(
                row=nr, column=2, sticky="we", pady=2)
            self._zeilen_knoepfe(tabelle, nr, felder, feld).grid(row=nr, column=3, padx=(6, 0))
        ttk.Button(r, text="＋ Feld hinzufügen", command=lambda: self._neues_element(felder, daten.neues_feld())).grid(
            row=z + 1, column=0, columnspan=2, sticky="w", pady=10)

    def _zeilen_knoepfe(self, eltern, nr, liste, element):
        rahmen = ttk.Frame(eltern)
        self._klein_knopf(rahmen, "↑", lambda: self._element_verschieben(liste, element, -1), "Nach oben").pack(side="left")
        self._klein_knopf(rahmen, "↓", lambda: self._element_verschieben(liste, element, 1), "Nach unten").pack(side="left")
        self._klein_knopf(rahmen, "✕", lambda: self._element_loeschen(liste, element), "Löschen").pack(side="left")
        return rahmen

    def _neues_element(self, liste, element):
        liste.append(element)
        self.editor_neu()
        self.geaendert()
        self.root.after(50, lambda: self.editor.canvas.yview_moveto(1))

    def _element_verschieben(self, liste, element, richtung):
        alt = liste.index(element)
        neu = alt + richtung
        if 0 <= neu < len(liste):
            liste.insert(neu, liste.pop(alt))
            self.editor_neu()
            self.geaendert()

    def _element_loeschen(self, liste, element):
        liste.remove(element)
        self.editor_neu()
        self.geaendert()

    # --- Freitext

    def _editor_text(self, r, a):
        z = self._kopfzeile_abschnitt(r, a, "Freier Text, z. B. ein Kurzprofil. Eine Leerzeile beginnt einen neuen Absatz.")
        self._textfeld(r, a, "text", hoehe=14).grid(row=z, column=0, columnspan=2, sticky="we")

    # --- Stationen mit Zeitraum

    def _editor_eintraege(self, r, a):
        z = self._kopfzeile_abschnitt(r, a, "Stationen wie Berufserfahrung, Ausbildung oder Projekte. "
                                             "Haken in der Liste = Eintrag anzeigen.")
        liste_rahmen = ttk.Frame(r)
        liste_rahmen.grid(row=z, column=0, columnspan=2, sticky="we")
        liste_rahmen.columnconfigure(0, weight=1)
        liste = ttk.Treeview(liste_rahmen, columns=("zeigen", "zeitraum", "titel"), show="headings",
                             selectmode="browse", height=6)
        for spalte, text, breite, dehnen in (("zeigen", "✓", 34, False), ("zeitraum", "Zeitraum", 150, False),
                                             ("titel", "Titel / Position", 300, True)):
            liste.heading(spalte, text=text, anchor="w" if spalte != "zeigen" else "center")
            liste.column(spalte, width=breite, stretch=dehnen, anchor="center" if spalte == "zeigen" else "w")
        liste.tag_configure("aus", foreground="#9aa0a6")
        liste.grid(row=0, column=0, sticky="we")
        knoepfe = ttk.Frame(liste_rahmen)
        knoepfe.grid(row=0, column=1, sticky="n", padx=(8, 0))
        formular = ttk.Frame(r)
        formular.grid(row=z + 1, column=0, columnspan=2, sticky="we", pady=(12, 0))
        formular.columnconfigure(1, weight=1)
        zustand = {"fokus": False}

        def zeile(e):
            liste.item(e["id"], values=(AN if e["zeigen"] else AUS, daten.zeitraum(e["von"], e["bis"]),
                                        e["titel"] or e["organisation"] or "(neuer Eintrag)"),
                       tags=() if e["zeigen"] else ("aus",))

        def fuellen(auswahl=None):
            liste.delete(*liste.get_children())
            for e in a["eintraege"]:
                liste.insert("", "end", iid=e["id"])
                zeile(e)
            if auswahl and liste.exists(auswahl):
                liste.selection_set(auswahl)
                liste.focus(auswahl)
                liste.see(auswahl)
            elif a["eintraege"]:
                liste.selection_set(a["eintraege"][0]["id"])
                liste.focus(a["eintraege"][0]["id"])
            else:
                formular_zeigen(None)

        def gewaehlt():
            iid = liste.focus() or (liste.selection() or [None])[0]
            return next((e for e in a["eintraege"] if e["id"] == iid), None)

        def formular_zeigen(e):
            for kind in formular.winfo_children():
                kind.destroy()
            if e is None:
                ttk.Label(formular, text="Noch keine Einträge – mit „＋ Neu“ anlegen.", style="Klein.TLabel").grid(
                    row=0, column=0, sticky="w")
                return

            def aktualisieren():
                zeile(e)
                self.baum_zeile(a)
            self._haken(formular, e, "zeigen", "Eintrag im Lebenslauf anzeigen", danach=aktualisieren).grid(
                row=0, column=1, sticky="w", pady=(0, 6))
            ttk.Label(formular, text="Zeitraum").grid(row=1, column=0, sticky="w", pady=3)
            zeit = ttk.Frame(formular)
            zeit.grid(row=1, column=1, sticky="w", pady=3)
            ttk.Label(zeit, text="von").pack(side="left")
            von = self._eingabe(zeit, e, "von", breite=10, danach=aktualisieren)
            von.pack(side="left", padx=4)
            ttk.Label(zeit, text="bis").pack(side="left", padx=(6, 0))
            self._eingabe(zeit, e, "bis", breite=10, danach=aktualisieren).pack(side="left", padx=4)
            ttk.Label(zeit, text="z. B. 09/2023, 2019 oder „heute“", style="Klein.TLabel").pack(side="left", padx=6)
            for nr, (schluessel, text) in enumerate((("titel", "Titel / Position / Abschluss"),
                                                     ("organisation", "Firma / Schule / Einrichtung"),
                                                     ("ort", "Ort")), 2):
                ttk.Label(formular, text=text).grid(row=nr, column=0, sticky="w", pady=3, padx=(0, 10))
                self._eingabe(formular, e, schluessel, danach=aktualisieren).grid(row=nr, column=1, sticky="we", pady=3)
            ttk.Label(formular, text="Beschreibung").grid(row=5, column=0, sticky="nw", pady=(8, 3))
            ttk.Label(formular, text="Eine Zeile pro Punkt – Zeilen mit „-“ am Anfang werden zu Aufzählungspunkten.",
                      style="Klein.TLabel").grid(row=5, column=1, sticky="w", pady=(8, 3))
            self._textfeld(formular, e, "beschreibung", hoehe=6).grid(row=6, column=0, columnspan=2, sticky="we")
            if zustand["fokus"]:
                zustand["fokus"] = False
                von.focus_set()

        def neu():
            e = daten.neuer_eintrag()
            alt = gewaehlt()
            index = a["eintraege"].index(alt) + 1 if alt else len(a["eintraege"])
            a["eintraege"].insert(index, e)
            zustand["fokus"] = True
            fuellen(e["id"])
            self.geaendert()

        def duplizieren():
            alt = gewaehlt()
            if alt:
                e = dict(alt, id=daten.neue_id())
                a["eintraege"].insert(a["eintraege"].index(alt) + 1, e)
                fuellen(e["id"])
                self.geaendert()

        def verschieben(richtung):
            e = gewaehlt()
            if not e:
                return
            alt = a["eintraege"].index(e)
            if 0 <= alt + richtung < len(a["eintraege"]):
                a["eintraege"].insert(alt + richtung, a["eintraege"].pop(alt))
                fuellen(e["id"])
                self.geaendert()

        def loeschen():
            e = gewaehlt()
            if not e:
                return
            if any(e[k].strip() for k in ("titel", "organisation", "beschreibung")) and not messagebox.askyesno(
                    "Eintrag löschen", f"„{e['titel'] or e['organisation']}“ löschen?"):
                return
            index = a["eintraege"].index(e)
            a["eintraege"].remove(e)
            rest = a["eintraege"]
            fuellen(rest[min(index, len(rest) - 1)]["id"] if rest else None)
            self.baum_zeile(a)
            self.geaendert()

        def klick(event):
            iid = liste.identify_row(event.y)
            if iid and liste.identify_column(event.x) == "#1":
                e = next(x for x in a["eintraege"] if x["id"] == iid)
                e["zeigen"] = not e["zeigen"]
                zeile(e)
                formular_zeigen(e)
                self.baum_zeile(a)
                self.geaendert()

        liste.bind("<<TreeviewSelect>>", lambda ev: formular_zeigen(gewaehlt()))
        liste.bind("<ButtonPress-1>", klick, add=True)
        for text, befehl in (("＋ Neu", neu), ("⧉ Duplizieren", duplizieren), ("↑ Nach oben", lambda: verschieben(-1)),
                             ("↓ Nach unten", lambda: verschieben(1)), ("✕ Löschen", loeschen)):
            ttk.Button(knoepfe, text=text, command=befehl, width=13).pack(fill="x", pady=1)
        fuellen()

    # --- Kenntnisse mit Stufe

    def _editor_kenntnisse(self, r, a):
        z = self._kopfzeile_abschnitt(r, a, "Kenntnisse oder Sprachen mit Stufe 1–5. Stufe 0 = keine Punkte, nur der Text. "
                                             "„Eigener Text“ ersetzt den Namen der Stufe.")
        optionen = ttk.Frame(r)
        optionen.grid(row=z, column=0, columnspan=2, sticky="w", pady=(0, 10))
        ttk.Label(optionen, text="Skala").pack(side="left")
        skala = ttk.Combobox(optionen, values=list(daten.SKALEN_NAMEN.values()), state="readonly", width=16)
        skala.set(daten.SKALEN_NAMEN[a["skala"]])
        skala.pack(side="left", padx=(6, 18))
        ttk.Label(optionen, text="Darstellung").pack(side="left")
        anzeige = ttk.Combobox(optionen, values=list(daten.KENNTNIS_ANZEIGEN.values()), state="readonly", width=16)
        anzeige.set(daten.KENNTNIS_ANZEIGEN[a["anzeige"]])
        anzeige.pack(side="left", padx=6)

        def skala_setzen(_e):
            a["skala"] = list(daten.SKALEN_NAMEN)[skala.current()]
            self.editor_neu()
            self.geaendert()
        skala.bind("<<ComboboxSelected>>", skala_setzen)
        anzeige.bind("<<ComboboxSelected>>", lambda e: (
            a.__setitem__("anzeige", list(daten.KENNTNIS_ANZEIGEN)[anzeige.current()]), self.geaendert()))

        tabelle = ttk.Frame(r)
        tabelle.grid(row=z + 1, column=0, columnspan=2, sticky="we")
        tabelle.columnconfigure(1, weight=3)
        tabelle.columnconfigure(3, weight=1)
        for spalte, text in ((1, "Bezeichnung"), (2, "Stufe"), (3, "Eigener Text (optional)")):
            ttk.Label(tabelle, text=text, style="Klein.TLabel").grid(row=0, column=spalte, sticky="w")
        stufen = [f"{n} – {t}" if n else "0 – keine Punkte" for n, t in enumerate(daten.SKALEN[a["skala"]])]
        for nr, k in enumerate(a["eintraege"], 1):
            self._haken(tabelle, k, "zeigen", "").grid(row=nr, column=0, padx=(0, 4))
            self._eingabe(tabelle, k, "name", breite=22, danach=lambda: self.baum_zeile(a)).grid(
                row=nr, column=1, sticky="we", pady=2, padx=(0, 6))
            stufe = ttk.Combobox(tabelle, values=stufen, state="readonly", width=max(len(t) for t in stufen) - 2)
            stufe.current(k["stufe"])
            stufe.grid(row=nr, column=2, sticky="w", pady=2, padx=(0, 6))
            stufe.bind("<<ComboboxSelected>>", lambda e, k=k, s=stufe: (k.__setitem__("stufe", s.current()), self.geaendert()))
            self._eingabe(tabelle, k, "info", breite=12).grid(row=nr, column=3, sticky="we", pady=2)
            self._zeilen_knoepfe(tabelle, nr, a["eintraege"], k).grid(row=nr, column=4, padx=(6, 0))
        ttk.Button(r, text="＋ Hinzufügen", command=lambda: self._neues_element(a["eintraege"], daten.neue_kenntnis())).grid(
            row=z + 2, column=0, columnspan=2, sticky="w", pady=10)

    # --- Einfache Liste

    def _editor_liste(self, r, a):
        z = self._kopfzeile_abschnitt(r, a, "Eine Zeile pro Eintrag, z. B. Hobbys oder Stärken.")
        optionen = ttk.Frame(r)
        optionen.grid(row=z, column=0, columnspan=2, sticky="w", pady=(0, 8))
        ttk.Label(optionen, text="Darstellung:").pack(side="left", padx=(0, 8))
        var = tk.StringVar(value=a["anzeige"])
        for schluessel, text in daten.LISTEN_ANZEIGEN.items():
            ttk.Radiobutton(optionen, text=text, value=schluessel, variable=var,
                            command=lambda: (a.__setitem__("anzeige", var.get()), self.geaendert())).pack(side="left", padx=4)
        optionen.var = var
        self._textfeld(r, a, "eintraege", hoehe=10, als_liste=True).grid(row=z + 1, column=0, columnspan=2, sticky="we")

    # ------------------------------------------------------------------ Änderungen, Sichern, Vorschau

    def geaendert(self):
        self.ungespeichert = True
        self.titel_aktualisieren()
        self._spaeter("autosave", 800, self.autosave)
        if self.vorschau.laeuft:
            self._spaeter("vorschau", 350, self._vorschau_senden)
        if self.auswahl not in FEST:
            a = self._abschnitt(self.auswahl)
            if a:
                self._spaeter("baum", 300, lambda: self.baum.exists(a["id"]) and self.baum_zeile(a))

    def _spaeter(self, name, ms, befehl):
        if name in self._timer:
            self.root.after_cancel(self._timer[name])
        self._timer[name] = self.root.after(ms, lambda: (self._timer.pop(name, None), befehl()))

    def autosave(self):
        try:
            ORDNER.mkdir(parents=True, exist_ok=True)
            daten.speichern({"datei": self.datei, "ungespeichert": self.ungespeichert,
                             "export_ordner": self.export_ordner, "lebenslauf": self.cv}, str(AUTOSAVE))
        except OSError as fehler:
            self.status(f"Automatisches Sichern fehlgeschlagen: {fehler}")

    def titel_aktualisieren(self):
        name = os.path.basename(self.datei) if self.datei else "nicht als Datei gespeichert"
        stern = " •" if self.ungespeichert and self.datei else ""
        self.root.title(f"{APP_NAME} – {name}{stern}")

    def status(self, text):
        self.statuszeile.configure(text=text)

    def _vorschau_senden(self):
        self.vorschau.aktualisieren(export_html.erzeugen(self.cv, live=True))

    def live_vorschau(self):
        self._vorschau_senden()
        try:
            adresse = self.vorschau.oeffnen()
        except OSError as fehler:
            messagebox.showerror("Live-Vorschau", f"Die Vorschau konnte nicht gestartet werden:\n{fehler}")
            return
        self.status(f"Live-Vorschau läuft unter {adresse} – sie aktualisiert sich bei jeder Änderung.")

    # ------------------------------------------------------------------ Dateien

    def _verwerfen_ok(self) -> bool:
        if not self.ungespeichert:
            return True
        return messagebox.askyesno(APP_NAME, "Der aktuelle Lebenslauf wurde noch nicht als Datei gespeichert "
                                             "und wird ersetzt.\n\nTrotzdem fortfahren?", icon="warning")

    def _laden(self, cv, datei, hinweis):
        self.cv = cv
        self.datei = datei
        self.auswahl = None
        self.baum_fuellen()
        self.auswaehlen("kopf")
        self.ungespeichert = False
        self.titel_aktualisieren()
        self.autosave()
        if self.vorschau.laeuft:
            self._vorschau_senden()
        self.status(hinweis)

    def neu(self):
        if self._verwerfen_ok():
            self._laden(daten.leerer_lebenslauf(), None, "Neuer, leerer Lebenslauf.")

    def beispiel_laden(self):
        if self._verwerfen_ok():
            self._laden(daten.beispiel(), None, "Beispiel geladen.")

    def oeffnen(self):
        if not self._verwerfen_ok():
            return
        pfad = filedialog.askopenfilename(title="Lebenslauf öffnen", filetypes=[("Lebenslauf (JSON)", "*.json")],
                                          initialdir=os.path.dirname(self.datei) if self.datei else self.export_ordner)
        if not pfad:
            return
        try:
            cv = daten.laden(pfad)
        except (OSError, ValueError, json.JSONDecodeError) as fehler:
            messagebox.showerror(APP_NAME, f"Die Datei konnte nicht geöffnet werden:\n{fehler}")
            return
        self._laden(cv, os.path.abspath(pfad), f"Geöffnet: {pfad}")

    def speichern(self, neu=False):
        pfad = self.datei
        if neu or not pfad:
            pfad = filedialog.asksaveasfilename(
                title="Lebenslauf speichern", defaultextension=".json", filetypes=[("Lebenslauf (JSON)", "*.json")],
                initialfile=daten.dateiname(self.cv, "json"),
                initialdir=os.path.dirname(self.datei) if self.datei else self.export_ordner)
            if not pfad:
                return False
        try:
            daten.speichern(self.cv, pfad)
        except OSError as fehler:
            messagebox.showerror(APP_NAME, f"Speichern fehlgeschlagen:\n{fehler}")
            return False
        self.datei = os.path.abspath(pfad)
        self.ungespeichert = False
        self.titel_aktualisieren()
        self.autosave()
        self.status(f"Gespeichert: {pfad}")
        return True

    def exportieren(self, kuerzel):
        beschreibung, endung, _ = exporte.FORMATE[kuerzel]
        pfad = filedialog.asksaveasfilename(
            title=f"Als {beschreibung} exportieren", defaultextension="." + endung,
            filetypes=[(beschreibung, "*." + endung)], initialfile=daten.dateiname(self.cv, endung),
            initialdir=self.export_ordner)
        if not pfad:
            return
        if self._export_schreiben(kuerzel, pfad):
            self.export_ordner = os.path.dirname(pfad)
            self.autosave()
            self.status(f"Exportiert: {pfad}")
            if messagebox.askyesno("Export fertig", f"{os.path.basename(pfad)} wurde gespeichert.\n\nJetzt öffnen?"):
                datei_oeffnen(pfad)

    def _export_schreiben(self, kuerzel, pfad) -> bool:
        try:
            exporte.exportieren(self.cv, kuerzel, pfad)
            return True
        except PermissionError:
            messagebox.showerror("Export", f"{os.path.basename(pfad)} kann nicht geschrieben werden.\n\n"
                                           "Ist die Datei noch in Word oder LibreOffice geöffnet? "
                                           "Dann dort schließen und erneut versuchen.")
        except (OSError, ValueError) as fehler:
            messagebox.showerror("Export", f"Export fehlgeschlagen:\n{fehler}")
        return False

    def alle_exportieren(self):
        ordner = filedialog.askdirectory(title="Ordner für den Export wählen", initialdir=self.export_ordner)
        if not ordner:
            return
        fertig = []
        for kuerzel, (_, endung, _) in exporte.FORMATE.items():
            pfad = os.path.join(ordner, daten.dateiname(self.cv, endung))
            if self._export_schreiben(kuerzel, pfad):
                fertig.append(os.path.basename(pfad))
        if fertig:
            self.export_ordner = ordner
            self.autosave()
            self.status(f"{len(fertig)} Dateien exportiert nach {ordner}")
            if messagebox.askyesno("Export fertig", "Gespeichert:\n\n" + "\n".join(fertig) + "\n\nOrdner öffnen?"):
                datei_oeffnen(ordner)

    def hilfe(self):
        messagebox.showinfo("Kurzanleitung", HILFE)

    def beenden(self):
        for timer in list(self._timer.values()):
            self.root.after_cancel(timer)
        self.autosave()
        self.vorschau.stoppen()
        self.root.destroy()


class _Tooltip:
    """Kleiner Hinweistext, wenn die Maus über einem Element steht."""

    def __init__(self, widget, text):
        self.widget, self.text, self.fenster, self.timer = widget, text, None, None
        widget.bind("<Enter>", self._planen, add=True)
        widget.bind("<Leave>", self._weg, add=True)
        widget.bind("<ButtonPress>", self._weg, add=True)
        widget.bind("<Destroy>", self._weg, add=True)

    def _planen(self, _e):
        self._weg()
        self.timer = self.widget.after(500, self._zeigen)

    def _zeigen(self):
        self.timer = None
        if not self.widget.winfo_exists():
            return
        x = self.widget.winfo_rootx() + 10
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.fenster = tk.Toplevel(self.widget)
        self.fenster.wm_overrideredirect(True)
        self.fenster.wm_geometry(f"+{x}+{y}")
        tk.Label(self.fenster, text=self.text, background="#ffffe0", relief="solid", borderwidth=1,
                 padx=6, pady=2).pack()

    def _weg(self, _e=None):
        if self.timer:
            try:
                self.widget.after_cancel(self.timer)
            except tk.TclError:
                pass
            self.timer = None
        if self.fenster:
            try:
                self.fenster.destroy()
            except tk.TclError:
                pass
            self.fenster = None


class _EigenerAbschnittDialog(tk.Toplevel):
    def __init__(self, eltern):
        super().__init__(eltern)
        self.title("Eigener Abschnitt")
        self.transient(eltern)
        self.resizable(False, False)
        self.ergebnis = None
        rahmen = ttk.Frame(self, padding=16)
        rahmen.pack(fill="both", expand=True)
        ttk.Label(rahmen, text="Überschrift").grid(row=0, column=0, sticky="w", pady=4)
        self.titel = ttk.Entry(rahmen, width=34)
        self.titel.grid(row=0, column=1, sticky="we", pady=4)
        ttk.Label(rahmen, text="Art").grid(row=1, column=0, sticky="nw", pady=4)
        self.typ = tk.StringVar(value="eintraege")
        arten = ttk.Frame(rahmen)
        arten.grid(row=1, column=1, sticky="w", pady=4)
        for typ, text in daten.TYPEN.items():
            ttk.Radiobutton(arten, text=text, value=typ, variable=self.typ).pack(anchor="w")
        knoepfe = ttk.Frame(rahmen)
        knoepfe.grid(row=2, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(knoepfe, text="Abbrechen", command=self.destroy).pack(side="right")
        ttk.Button(knoepfe, text="Hinzufügen", command=self._ok).pack(side="right", padx=6)
        self.bind("<Return>", lambda e: self._ok())
        self.bind("<Escape>", lambda e: self.destroy())
        self.titel.focus_set()
        self.update_idletasks()
        self.geometry(f"+{eltern.winfo_rootx() + 120}+{eltern.winfo_rooty() + 120}")
        self.grab_set()
        self.wait_window()

    def _ok(self):
        titel = self.titel.get().strip()
        if not titel:
            self.titel.focus_set()
            return
        self.ergebnis = (titel, self.typ.get())
        self.destroy()


def starten(pfad: str | None = None) -> None:
    if sys.platform.startswith("win"):
        try:  # scharfe Schrift auf hochauflösenden Bildschirmen
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            pass
    root = tk.Tk()
    breite = min(1180, root.winfo_screenwidth() - 60)
    hoehe = min(780, root.winfo_screenheight() - 100)
    root.geometry(f"{breite}x{hoehe}")
    root.minsize(900, 560)
    App(root, pfad)
    root.mainloop()
