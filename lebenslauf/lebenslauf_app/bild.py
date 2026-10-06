"""Foto: Einlesen, Bildgröße bestimmen und für die Exporte zuschneiden.

Pillow ist optional. Ohne Pillow wird das Foto unverändert eingebettet und nur über
Angaben im Dokument zugeschnitten (Word: Bildausschnitt, Webseite: CSS). Mit Pillow
wird es verkleinert, gedreht (EXIF), zugeschnitten und für runde Fotos freigestellt.
"""
from __future__ import annotations

import base64
import io
import struct
from dataclasses import dataclass

try:
    from PIL import Image, ImageDraw, ImageOps
    PILLOW = True
except ImportError:  # pragma: no cover - hängt von der Installation ab
    PILLOW = False

MAX_PIXEL = 1000          # längste Seite eines gespeicherten Fotos (mit Pillow)
MAX_BYTES = 8 * 1024 * 1024


@dataclass
class Bild:
    """Ein Foto, fertig zum Einbetten in ein Dokument."""
    daten: bytes
    mime: str                 # "image/jpeg" oder "image/png"
    breite_px: int
    hoehe_px: int
    breite_mm: float
    hoehe_mm: float
    zuschnitt: tuple = (0.0, 0.0, 0.0, 0.0)   # links, oben, rechts, unten (Anteil 0..1)
    rund: bool = False                         # rund darstellen (Word: Ellipse)
    freigestellt: bool = False                 # Pillow hat schon rund ausgeschnitten

    @property
    def endung(self) -> str:
        return "png" if self.mime == "image/png" else "jpeg"


def bild_info(daten: bytes):
    """Liest Typ und Pixelgröße aus dem Dateikopf (PNG, JPEG). Gibt (mime, breite, hoehe) zurück."""
    if daten[:8] == b"\x89PNG\r\n\x1a\n" and len(daten) >= 24:
        breite, hoehe = struct.unpack(">II", daten[16:24])
        return "image/png", breite, hoehe
    if daten[:2] == b"\xff\xd8":
        i = 2
        while i + 9 < len(daten):
            if daten[i] != 0xFF:
                i += 1
                continue
            marker = daten[i + 1]
            if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7 or marker == 0xFF:
                i += 1 if marker == 0xFF else 2
                continue
            laenge = struct.unpack(">H", daten[i + 2:i + 4])[0]
            # SOF-Marker (Start of Frame) enthalten die Bildgröße
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                hoehe, breite = struct.unpack(">HH", daten[i + 5:i + 9])
                return "image/jpeg", breite, hoehe
            i += 2 + laenge
    raise ValueError("Das Foto muss ein PNG- oder JPEG-Bild sein.")


def foto_laden(pfad: str) -> dict:
    """Liest eine Bilddatei ein und gibt den Wert für cv["kopf"]["foto"] zurück."""
    with open(pfad, "rb") as datei:
        daten = datei.read()
    if PILLOW:
        try:
            with Image.open(io.BytesIO(daten)) as bild:
                bild = ImageOps.exif_transpose(bild)
                bild.thumbnail((MAX_PIXEL, MAX_PIXEL))
                if bild.mode not in ("RGB", "L"):
                    hintergrund = Image.new("RGB", bild.size, "white")
                    hintergrund.paste(bild, mask=bild.convert("RGBA").getchannel("A"))
                    bild = hintergrund
                puffer = io.BytesIO()
                bild.convert("RGB").save(puffer, "JPEG", quality=88, optimize=True)
                daten = puffer.getvalue()
        except OSError as fehler:
            raise ValueError(f"Das Bild konnte nicht gelesen werden: {fehler}") from fehler
    mime, breite, hoehe = bild_info(daten)
    if breite == 0 or hoehe == 0:
        raise ValueError("Das Bild hat keine gültige Größe.")
    if len(daten) > MAX_BYTES:
        raise ValueError("Das Foto ist größer als 8 MB. Bitte verkleinern oder Pillow installieren "
                         "(pip install pillow), dann wird es automatisch verkleinert.")
    return {"daten": base64.b64encode(daten).decode("ascii"), "mime": mime}


def foto_bytes(foto: dict) -> bytes:
    return base64.b64decode(foto["daten"])


def zuschnitt_berechnen(breite: int, hoehe: int, ziel_breite: float, ziel_hoehe: float):
    """Mittiger Ausschnitt im gewünschten Seitenverhältnis als Anteile (links, oben, rechts, unten)."""
    ist = breite / hoehe
    soll = ziel_breite / ziel_hoehe
    if ist > soll:      # zu breit → links und rechts abschneiden
        rest = (1 - soll / ist) / 2
        return (rest, 0.0, rest, 0.0)
    if ist < soll:      # zu hoch → oben und unten abschneiden (oben etwas weniger: Kopf bleibt drin)
        rest = 1 - ist / soll
        return (0.0, rest * 0.35, 0.0, rest * 0.65)
    return (0.0, 0.0, 0.0, 0.0)


def fuer_dokument(foto: dict, form: str, breite_mm: float, hoehe_mm: float) -> Bild:
    """Bereitet das gespeicherte Foto für Word/LibreOffice vor."""
    daten = foto_bytes(foto)
    mime, breite, hoehe = bild_info(daten)
    zuschnitt = zuschnitt_berechnen(breite, hoehe, breite_mm, hoehe_mm)
    rund = form == "rund"
    if not PILLOW:
        return Bild(daten, mime, breite, hoehe, breite_mm, hoehe_mm, zuschnitt, rund)

    with Image.open(io.BytesIO(daten)) as quelle:
        quelle = quelle.convert("RGB")
        l, o, r, u = zuschnitt
        box = (round(l * breite), round(o * hoehe), round(breite - r * breite), round(hoehe - u * hoehe))
        bild = quelle.crop(box)
        # ca. 300 dpi reichen für den Druck
        ziel = (max(1, round(breite_mm / 25.4 * 300)), max(1, round(hoehe_mm / 25.4 * 300)))
        if bild.width > ziel[0]:
            bild = bild.resize(ziel, Image.LANCZOS)
        puffer = io.BytesIO()
        if rund:
            maske = Image.new("L", (bild.width * 4, bild.height * 4), 0)
            ImageDraw.Draw(maske).ellipse((0, 0, maske.width - 1, maske.height - 1), fill=255)
            bild = bild.convert("RGBA")
            bild.putalpha(maske.resize(bild.size, Image.LANCZOS))
            bild.save(puffer, "PNG", optimize=True)
            mime = "image/png"
        else:
            bild.save(puffer, "JPEG", quality=90, dpi=(300, 300))
            mime = "image/jpeg"
        return Bild(puffer.getvalue(), mime, bild.width, bild.height, breite_mm, hoehe_mm,
                    (0.0, 0.0, 0.0, 0.0), rund, freigestellt=rund)


def data_url(foto: dict) -> str:
    return f"data:{foto['mime']};base64,{foto['daten']}"
