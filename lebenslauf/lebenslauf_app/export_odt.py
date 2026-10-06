"""Export als OpenDocument-Text (.odt) für LibreOffice/OpenOffice – ohne Zusatzbibliotheken.

Eine ODT-Datei ist ein ZIP-Archiv. Die Datei „mimetype“ muss als erste und unkomprimiert
darin liegen, sonst erkennen manche Programme das Format nicht.
"""
from __future__ import annotations

import datetime as _dt
import re
import struct

from . import dokument as dm
from .xmlhilfe import text as x
from .xmlhilfe import zip_schreiben

MIME = "application/vnd.oasis.opendocument.text"
NAMESPACES = (
    'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
    'xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0" '
    'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" '
    'xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" '
    'xmlns:draw="urn:oasis:names:tc:opendocument:xmlns:drawing:1.0" '
    'xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0" '
    'xmlns:xlink="http://www.w3.org/1999/xlink" '
    'xmlns:svg="urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0" '
    'xmlns:meta="urn:oasis:names:tc:opendocument:xmlns:meta:1.0" '
    'xmlns:dc="http://purl.org/dc/elements/1.1/" '
    'office:version="1.3"'
)


def _mm(wert: float) -> str:
    return f"{wert:.2f}mm"


def _pt(wert: float) -> str:
    return f"{wert:g}pt"


def _odf_text(wert: str) -> str:
    """Leerzeichenfolgen, Tabs und Zeilenumbrüche müssen in ODF als eigene Elemente stehen."""
    teile = []
    for i, zeile in enumerate(wert.split("\n")):
        if i:
            teile.append("<text:line-break/>")
        for stueck in re.split(r"(\t| {2,}|^ )", zeile):
            if not stueck:
                continue
            if stueck == "\t":
                teile.append("<text:tab/>")
            elif stueck.strip() == "":
                teile.append(f'<text:s text:c="{len(stueck)}"/>' if len(stueck) > 1 else "<text:s/>")
            else:
                teile.append(x(stueck))
    return "".join(teile)


def _dpi(daten: bytes):
    """Auflösung aus dem Bildkopf (JFIF bzw. PNG pHYs); LibreOffice rechnet damit die Originalgröße."""
    if daten[:2] == b"\xff\xd8" and daten[6:11] == b"JFIF\x00":
        einheit, dx, dy = daten[13], *struct.unpack(">HH", daten[14:18])
        if einheit == 1 and dx and dy:
            return dx, dy
        if einheit == 2 and dx and dy:
            return dx * 2.54, dy * 2.54
    if daten[:8] == b"\x89PNG\r\n\x1a\n":
        stelle = daten.find(b"pHYs")
        if stelle > 0:
            px, py, einheit = struct.unpack(">IIB", daten[stelle + 4:stelle + 13])
            if einheit == 1 and px and py:
                return px * 0.0254, py * 0.0254
    return 96, 96


class _Schreiber:
    def __init__(self, dok: dm.Dokument):
        self.dok = dok
        self.stile = {}         # Schlüssel → Stilname
        self.stil_xml = []
        self.medien = []
        self.tabellen_nr = 0

    def _stil(self, praefix: str, schluessel: tuple, xml_vorlage: str) -> str:
        if schluessel not in self.stile:
            name = f"{praefix}{sum(1 for k in self.stile if k[0] == schluessel[0]) + 1}"
            self.stile[schluessel] = name
            self.stil_xml.append(xml_vorlage.format(name=name))
        return self.stile[schluessel]

    # ------------------------------------------------------------ Stile

    def absatz_stil(self, a: dm.Absatz) -> str:
        groesse = next((l.groesse for l in a.laeufe if l.groesse), None)
        schluessel = ("P", a.ausrichtung, a.vor, a.nach, a.linie_unten, a.linie_staerke,
                      a.mit_naechstem, a.ueberschrift, groesse)
        props = [f'fo:margin-top="{_pt(a.vor)}"', f'fo:margin-bottom="{_pt(a.nach)}"']
        if a.ausrichtung != "links":
            props.append(f'fo:text-align="{"end" if a.ausrichtung == "rechts" else "center"}"')
        if a.mit_naechstem:
            props.append('fo:keep-with-next="always"')
        if a.linie_unten:
            props.append(f'fo:border-bottom="{_pt(a.linie_staerke)} solid #{a.linie_unten}" '
                         'fo:border-top="none" fo:border-left="none" fo:border-right="none" fo:padding-bottom="1pt"')
        text_props = f'<style:text-properties fo:font-size="{_pt(groesse)}"/>' if groesse else ""
        eltern = "Heading_20_1" if a.ueberschrift else "Standard"
        return self._stil("P", schluessel,
                          f'<style:style style:name="{{name}}" style:family="paragraph" '
                          f'style:parent-style-name="{eltern}"><style:paragraph-properties {" ".join(props)}/>'
                          f"{text_props}</style:style>")

    def text_stil(self, l: dm.Lauf):
        props = []
        if l.fett:
            props.append('fo:font-weight="bold" style:font-weight-complex="bold"')
        if l.kursiv:
            props.append('fo:font-style="italic" style:font-style-complex="italic"')
        if l.farbe:
            props.append(f'fo:color="#{l.farbe}"')
        if l.groesse:
            props.append(f'fo:font-size="{_pt(l.groesse)}" style:font-size-complex="{_pt(l.groesse)}"')
        if l.sperrung:
            props.append(f'fo:letter-spacing="{_pt(l.sperrung)}"')
        if not props:
            return None
        return self._stil("T", ("T",) + tuple(props),
                          f'<style:style style:name="{{name}}" style:family="text">'
                          f'<style:text-properties {" ".join(props)}/></style:style>')

    # ------------------------------------------------------------ Inhalt

    def lauf(self, l: dm.Lauf) -> str:
        if l.bild is not None:
            return self.bild(l.bild)
        inhalt = _odf_text(l.text)
        stil = self.text_stil(l)
        if stil and inhalt:
            inhalt = f'<text:span text:style-name="{stil}">{inhalt}</text:span>'
        if l.link:
            inhalt = (f'<text:a xlink:type="simple" xlink:href="{x(l.link)}" '
                      f'text:style-name="Internet_20_link" text:visited-style-name="Internet_20_link">{inhalt}</text:a>')
        return inhalt

    def absatz(self, a: dm.Absatz) -> str:
        stil = self.absatz_stil(a)
        inhalt = "".join(self.lauf(l) for l in a.laeufe)
        if a.ueberschrift:
            return f'<text:h text:style-name="{stil}" text:outline-level="1">{inhalt}</text:h>'
        return f'<text:p text:style-name="{stil}">{inhalt}</text:p>'

    def bloecke(self, bloecke: list) -> str:
        teile, liste = [], []
        for b in bloecke + [None]:
            if isinstance(b, dm.Absatz) and b.aufzaehlung:
                liste.append(b)
                continue
            if liste:   # aufeinanderfolgende Aufzählungspunkte bilden eine Liste
                teile.append('<text:list text:style-name="L1">' + "".join(
                    f"<text:list-item>{self.absatz(p)}</text:list-item>" for p in liste) + "</text:list>")
                liste = []
            if isinstance(b, dm.Tabelle):
                teile.append(self.tabelle(b))
            elif isinstance(b, dm.Absatz):
                teile.append(self.absatz(b))
        return "".join(teile)

    def tabelle(self, t: dm.Tabelle) -> str:
        self.tabellen_nr += 1
        name = f"Tabelle{self.tabellen_nr}"
        breite = sum(t.spalten)
        self.stil_xml.append(
            f'<style:style style:name="{name}" style:family="table"><style:table-properties '
            f'style:width="{_mm(breite)}" table:align="left" fo:margin-left="0mm" fo:margin-top="0mm" '
            f'fo:margin-bottom="0mm"/></style:style>')
        spalten = []
        for nr, spalte in enumerate(t.spalten):
            cname = f"{name}.{chr(65 + nr)}"
            self.stil_xml.append(
                f'<style:style style:name="{cname}" style:family="table-column">'
                f'<style:table-column-properties style:column-width="{_mm(spalte)}"/></style:style>')
            spalten.append(f'<table:table-column table:style-name="{cname}"/>')
        zeilen_stil = self._stil("Z", ("Z", t.zeilen_zusammenhalten),
                                 '<style:style style:name="{name}" style:family="table-row">'
                                 '<style:table-row-properties fo:keep-together="'
                                 + ("always" if t.zeilen_zusammenhalten else "auto") + '"/></style:style>')
        zeilen = []
        for zeile in t.zeilen:
            zellen = []
            for nr, zelle in enumerate(zeile):
                rechts = 3 if nr < len(zeile) - 1 else 0
                vertikal = {"mitte": "middle", "unten": "bottom"}.get(zelle.vertikal, "top")
                zstil = self._stil("C", ("C", rechts, vertikal),
                                   '<style:style style:name="{name}" style:family="table-cell">'
                                   '<style:table-cell-properties fo:padding-left="0mm" '
                                   f'fo:padding-right="{_mm(rechts)}" fo:padding-top="0mm" fo:padding-bottom="0mm" '
                                   f'fo:border="none" style:vertical-align="{vertikal}"/></style:style>')
                inhalt = self.bloecke(zelle.inhalt) or "<text:p/>"
                zellen.append(f'<table:table-cell table:style-name="{zstil}" office:value-type="string">'
                              f"{inhalt}</table:table-cell>")
            zeilen.append(f'<table:table-row table:style-name="{zeilen_stil}">{"".join(zellen)}</table:table-row>')
        return (f'<table:table table:name="{name}" table:style-name="{name}">'
                f'{"".join(spalten)}{"".join(zeilen)}</table:table>')

    def bild(self, b) -> str:
        nr = len(self.medien) + 1
        pfad = f"Pictures/bild{nr}.{b.endung}"
        self.medien.append((pfad, b.daten, b.mime))
        clip = ""
        if any(b.zuschnitt):
            # Ausschnitt relativ zur Originalgröße des Bildes (aus Pixeln und Auflösung)
            dpi_x, dpi_y = _dpi(b.daten)
            breite = b.breite_px / dpi_x * 25.4
            hoehe = b.hoehe_px / dpi_y * 25.4
            l, o, r, u = b.zuschnitt
            clip = f' fo:clip="rect({_mm(o * hoehe)}, {_mm(r * breite)}, {_mm(u * hoehe)}, {_mm(l * breite)})"'
        stil = f"fr{nr}"
        self.stil_xml.append(
            f'<style:style style:name="{stil}" style:family="graphic"><style:graphic-properties '
            f'style:vertical-pos="top" style:vertical-rel="baseline" fo:border="none" fo:padding="0mm" '
            f'style:mirror="none"{clip}/></style:style>')
        return (f'<draw:frame draw:style-name="{stil}" draw:name="Foto {nr}" text:anchor-type="as-char" '
                f'svg:width="{_mm(b.breite_mm)}" svg:height="{_mm(b.hoehe_mm)}" draw:z-index="0">'
                f'<draw:image xlink:href="{pfad}" xlink:type="simple" xlink:show="embed" xlink:actuate="onLoad" '
                f'draw:mime-type="{b.mime}"/><svg:desc>Bewerbungsfoto</svg:desc></draw:frame>')

    # ------------------------------------------------------------ Paketteile

    def schriften(self) -> str:
        s = x(self.dok.schrift)
        return f'<office:font-face-decls><style:font-face style:name="{s}" svg:font-family="&apos;{s}&apos;"/></office:font-face-decls>'

    def content_xml(self) -> str:
        koerper = self.bloecke(self.dok.bloecke)
        liste = (
            '<text:list-style style:name="L1"><text:list-level-style-bullet text:level="1" text:bullet-char="•">'
            '<style:list-level-properties text:list-level-position-and-space-mode="label-alignment">'
            '<style:list-level-label-alignment text:label-followed-by="listtab" text:list-tab-stop-position="4.5mm" '
            'fo:text-indent="-4mm" fo:margin-left="4.5mm"/></style:list-level-properties>'
            f'<style:text-properties fo:color="#{self.dok.akzent}"/></text:list-level-style-bullet></text:list-style>'
        )
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            f"<office:document-content {NAMESPACES}>{self.schriften()}"
            f'<office:automatic-styles>{"".join(self.stil_xml)}{liste}</office:automatic-styles>'
            f"<office:body><office:text>{koerper}</office:text></office:body></office:document-content>"
        )

    def styles_xml(self) -> str:
        d = self.dok
        oben, rechts, unten, links = d.rand
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            f"<office:document-styles {NAMESPACES}>{self.schriften()}<office:styles>"
            '<style:default-style style:family="paragraph"><style:text-properties '
            f'style:font-name="{x(d.schrift)}" style:font-name-complex="{x(d.schrift)}" '
            f'fo:font-size="{_pt(d.groesse)}" style:font-size-complex="{_pt(d.groesse)}" '
            f'fo:color="#{d.textfarbe}" fo:language="de" fo:country="DE"/></style:default-style>'
            '<style:style style:name="Standard" style:family="paragraph" style:class="text">'
            '<style:paragraph-properties fo:line-height="110%" fo:margin-top="0pt" fo:margin-bottom="0pt"/></style:style>'
            '<style:style style:name="Heading_20_1" style:display-name="Heading 1" style:family="paragraph" '
            'style:parent-style-name="Standard" style:next-style-name="Standard" style:default-outline-level="1" '
            f'style:class="text"><style:text-properties fo:font-weight="bold" fo:color="#{d.akzent}"/></style:style>'
            '<style:style style:name="Internet_20_link" style:display-name="Internet link" style:family="text">'
            f'<style:text-properties fo:color="#{d.akzent}" style:text-underline-style="none"/></style:style>'
            "</office:styles><office:automatic-styles>"
            '<style:page-layout style:name="pm1"><style:page-layout-properties '
            f'fo:page-width="{_mm(dm.SEITE_BREITE)}" fo:page-height="{_mm(dm.SEITE_HOEHE)}" '
            f'style:print-orientation="portrait" fo:margin-top="{_mm(oben)}" fo:margin-bottom="{_mm(unten)}" '
            f'fo:margin-left="{_mm(links)}" fo:margin-right="{_mm(rechts)}"/></style:page-layout>'
            "</office:automatic-styles><office:master-styles>"
            '<style:master-page style:name="Standard" style:page-layout-name="pm1"/>'
            "</office:master-styles></office:document-styles>"
        )

    def meta_xml(self) -> str:
        jetzt = _dt.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            f"<office:document-meta {NAMESPACES}><office:meta>"
            "<meta:generator>Lebenslauf-Generator</meta:generator>"
            f"<dc:title>{x(self.dok.titel)}</dc:title><dc:creator>{x(self.dok.autor)}</dc:creator>"
            f"<meta:initial-creator>{x(self.dok.autor)}</meta:initial-creator>"
            f"<dc:language>{self.dok.sprache}</dc:language>"
            f"<meta:creation-date>{jetzt}</meta:creation-date><dc:date>{jetzt}</dc:date>"
            "</office:meta></office:document-meta>"
        )

    def manifest_xml(self) -> str:
        eintraege = [
            f'<manifest:file-entry manifest:full-path="/" manifest:version="1.3" manifest:media-type="{MIME}"/>',
            '<manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/>',
            '<manifest:file-entry manifest:full-path="styles.xml" manifest:media-type="text/xml"/>',
            '<manifest:file-entry manifest:full-path="meta.xml" manifest:media-type="text/xml"/>',
        ]
        eintraege += [f'<manifest:file-entry manifest:full-path="{pfad}" manifest:media-type="{mime}"/>'
                      for pfad, _, mime in self.medien]
        return ('<?xml version="1.0" encoding="UTF-8"?>'
                '<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" '
                f'manifest:version="1.3">{"".join(eintraege)}</manifest:manifest>')


def schreiben(dok: dm.Dokument, ziel) -> None:
    s = _Schreiber(dok)
    content = s.content_xml()          # zuerst: sammelt Stile und Bilder ein
    dateien = [
        ("mimetype", MIME, False),     # muss die erste Datei sein, unkomprimiert
        ("content.xml", content, True),
        ("styles.xml", s.styles_xml(), True),
        ("meta.xml", s.meta_xml(), True),
        ("META-INF/manifest.xml", s.manifest_xml(), True),
    ]
    dateien += [(pfad, daten, False) for pfad, daten, _ in s.medien]
    zip_schreiben(ziel, dateien)


def exportieren(cv: dict, ziel) -> None:
    schreiben(dm.klassisch(cv), ziel)
