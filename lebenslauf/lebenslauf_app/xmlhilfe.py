"""Kleine Helfer zum Schreiben von XML und ZIP-Paketen (DOCX und ODT sind ZIP-Dateien mit XML)."""
from __future__ import annotations

import re
import time
import zipfile

# Zeichen, die in XML 1.0 nicht vorkommen dürfen (z. B. Steuerzeichen aus kopiertem Text)
_UNGUELTIG = re.compile("[^\u0009\u000A\u000D -퟿-�\U00010000-\U0010FFFF]")


def text(wert: str) -> str:
    """Escape für Text- und Attributinhalte."""
    wert = _UNGUELTIG.sub("", str(wert))
    return (wert.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def zip_schreiben(ziel, dateien: list) -> None:
    """Schreibt [(name, bytes|str, komprimieren), ...] in ein ZIP-Archiv.
    Feste Zeitstempel sorgen dafür, dass gleiche Inhalte gleiche Dateien ergeben."""
    zeit = time.localtime()[:6]
    with zipfile.ZipFile(ziel, "w") as archiv:
        for name, inhalt, komprimieren in dateien:
            info = zipfile.ZipInfo(name, date_time=zeit)
            info.compress_type = zipfile.ZIP_DEFLATED if komprimieren else zipfile.ZIP_STORED
            info.external_attr = 0o644 << 16
            if isinstance(inhalt, str):
                inhalt = inhalt.encode("utf-8")
            archiv.writestr(info, inhalt)
