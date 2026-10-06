"""Alle Exportformate an einer Stelle."""
from __future__ import annotations

from . import export_docx, export_html, export_odt

# Kürzel → (Beschreibung, Dateiendung, Funktion)
FORMATE = {
    "docx": ("Word-Dokument", "docx", export_docx.exportieren),
    "odt": ("LibreOffice-Dokument", "odt", export_odt.exportieren),
    "html": ("Interaktive Webseite", "html", export_html.exportieren),
}


def exportieren(cv: dict, format_: str, ziel: str) -> None:
    if format_ not in FORMATE:
        raise ValueError(f"Unbekanntes Format: {format_}")
    FORMATE[format_][2](cv, ziel)
