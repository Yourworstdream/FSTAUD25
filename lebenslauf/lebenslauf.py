#!/usr/bin/env python3
"""Lebenslauf-Generator – Startdatei.

    python lebenslauf.py                       Programm mit Oberfläche starten
    python lebenslauf.py mein_lebenslauf.json  … und gleich eine Datei öffnen

Export ohne Oberfläche (z. B. für Skripte):

    python lebenslauf.py --export mein_lebenslauf.json --format docx odt html --ziel ausgabe/
    python lebenslauf.py --beispiel --format docx          (Beispiel-Lebenslauf exportieren)
"""
from __future__ import annotations

import argparse
import os
import sys

if sys.version_info < (3, 8):
    sys.exit("Der Lebenslauf-Generator braucht Python 3.8 oder neuer.")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lebenslauf_app import daten, exporte  # noqa: E402


def befehlszeile(argumente: list) -> int:
    parser = argparse.ArgumentParser(description="Lebenslauf-Generator")
    parser.add_argument("datei", nargs="?", help="Lebenslauf-Datei (.json), die geöffnet werden soll")
    parser.add_argument("--export", metavar="JSON", help="diese Datei ohne Oberfläche exportieren")
    parser.add_argument("--beispiel", action="store_true", help="den eingebauten Beispiel-Lebenslauf exportieren")
    parser.add_argument("--format", nargs="+", choices=list(exporte.FORMATE), default=list(exporte.FORMATE),
                        help="Exportformate (Standard: alle)")
    parser.add_argument("--ziel", default=".", help="Ordner für die exportierten Dateien (Standard: aktueller Ordner)")
    args = parser.parse_args(argumente)

    if not (args.export or args.beispiel):
        try:
            from lebenslauf_app import gui
        except ImportError:
            print("tkinter fehlt. Unter Linux z. B. installieren mit:  sudo apt install python3-tk", file=sys.stderr)
            return 1
        gui.starten(args.datei)
        return 0

    try:
        cv = daten.beispiel() if args.beispiel else daten.laden(args.export)
    except (OSError, ValueError) as fehler:
        print(f"Fehler beim Laden: {fehler}", file=sys.stderr)
        return 1
    os.makedirs(args.ziel, exist_ok=True)
    for kuerzel in args.format:
        pfad = os.path.join(args.ziel, daten.dateiname(cv, exporte.FORMATE[kuerzel][1]))
        exporte.exportieren(cv, kuerzel, pfad)
        print(f"✓ {pfad}")
    return 0


if __name__ == "__main__":
    sys.exit(befehlszeile(sys.argv[1:]))
