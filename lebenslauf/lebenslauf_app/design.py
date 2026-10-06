"""Design-Einstellungen: Vorlagen, Farben, Schriften und Farb-Hilfsfunktionen."""
from __future__ import annotations

import re

VORLAGEN = {"klassisch": "Klassisch"}

# (Name, Farbe) – die erste ist die Standardfarbe
FARBEN = [
    ("Dunkelblau", "#1F4E79"),
    ("Petrol", "#0F6E6E"),
    ("Bordeaux", "#7A1F2B"),
    ("Dunkelgrün", "#2E5E3A"),
    ("Anthrazit", "#3A434B"),
    ("Schwarz", "#1A1A1A"),
]

# Schriftname (so steht er in Word/LibreOffice) → Schriftstapel für die Webseite
SCHRIFTEN = {
    "Georgia": "Georgia, 'Times New Roman', serif",
    "Cambria": "Cambria, Caladea, Georgia, serif",
    "Times New Roman": "'Times New Roman', 'Liberation Serif', Times, serif",
    "Garamond": "Garamond, 'EB Garamond', 'Times New Roman', serif",
    "Calibri": "Calibri, Carlito, 'Segoe UI', Arial, sans-serif",
    "Arial": "Arial, 'Liberation Sans', Helvetica, sans-serif",
}

SCHRIFTGROESSEN = [9.5, 10, 10.5, 11, 11.5, 12]

TEXT = "222222"     # Fließtext
GRAU = "5F6368"     # Nebeninformationen (Ort, Zeitraum, Bezeichnungen)
HELLGRAU = "D0D4D9"  # leere Punkte bei Kenntnissen

# Fotogrößen in mm (Breite, Höhe)
FOTO_MASSE = {"rechteckig": (35.0, 45.0), "rund": (38.0, 38.0)}


def farbe_pruefen(wert, standard: str) -> str:
    """Gibt eine gültige Farbe im Format #RRGGBB zurück."""
    if isinstance(wert, str) and re.fullmatch(r"#?[0-9a-fA-F]{6}", wert.strip()):
        return "#" + wert.strip().lstrip("#").upper()
    return standard


def hex6(farbe: str) -> str:
    """'#1f4e79' → '1F4E79' (so erwarten es Word und LibreOffice)."""
    return farbe.lstrip("#").upper()


def _rgb(farbe: str):
    f = hex6(farbe)
    return int(f[0:2], 16), int(f[2:4], 16), int(f[4:6], 16)


def mischen(farbe: str, ziel: str, anteil: float) -> str:
    """Mischt `farbe` mit `ziel` (anteil 0 = nur farbe, 1 = nur ziel). Ergebnis ohne '#'."""
    a, b = _rgb(farbe), _rgb(ziel)
    return "".join(f"{round(x + (y - x) * anteil):02X}" for x, y in zip(a, b))


def helligkeit(farbe: str) -> float:
    """Relative Helligkeit nach WCAG (0 = schwarz, 1 = weiß)."""
    def kanal(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = _rgb(farbe)
    return 0.2126 * kanal(r) + 0.7152 * kanal(g) + 0.0722 * kanal(b)


def lesbare_akzentfarbe(farbe: str) -> str:
    """Zu helle Akzentfarben werden für Text auf weißem Papier abgedunkelt."""
    f = hex6(farbe)
    while helligkeit(f) > 0.25:
        f = mischen(f, "000000", 0.15)
    return f
