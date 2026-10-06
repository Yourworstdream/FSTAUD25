"""Export als Word-Dokument (.docx, Office Open XML) – ohne Zusatzbibliotheken.

Eine DOCX-Datei ist ein ZIP-Archiv mit XML-Dateien. Die Reihenfolge der XML-Elemente
folgt dem Standard (ECMA-376), damit Word die Datei ohne Reparatur-Meldung öffnet.
"""
from __future__ import annotations

import datetime as _dt

from . import dokument as dm
from .xmlhilfe import text as x
from .xmlhilfe import zip_schreiben

TWIP_PRO_MM = 1440 / 25.4
EMU_PRO_MM = 36000

NS_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_WP = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
NS_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
NS_PIC = "http://schemas.openxmlformats.org/drawingml/2006/picture"
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def _tw(mm: float) -> int:
    return round(mm * TWIP_PRO_MM)


class _Schreiber:
    def __init__(self, dok: dm.Dokument):
        self.dok = dok
        self.beziehungen = [
            ("rIdStyles", f"{REL}/styles", "styles.xml", False),
            ("rIdSettings", f"{REL}/settings", "settings.xml", False),
            ("rIdNumbering", f"{REL}/numbering", "numbering.xml", False),
        ]
        self.medien = []      # [(pfad im Archiv, bytes)]
        self.bild_nr = 0

    def beziehung(self, typ: str, ziel: str, extern: bool = False) -> str:
        for rid, t, z, e in self.beziehungen:
            if t == typ and z == ziel:
                return rid
        rid = f"rId{len(self.beziehungen) + 1}"
        self.beziehungen.append((rid, typ, ziel, extern))
        return rid

    # ------------------------------------------------------------ Bausteine

    def lauf(self, lauf: dm.Lauf) -> str:
        if lauf.bild is not None:
            return f"<w:r>{self.bild(lauf.bild)}</w:r>"
        rpr = []
        if lauf.link:
            rpr.append('<w:rStyle w:val="Hyperlink"/>')
        if lauf.fett:
            rpr.append("<w:b/><w:bCs/>")
        if lauf.kursiv:
            rpr.append("<w:i/><w:iCs/>")
        if lauf.farbe:
            rpr.append(f'<w:color w:val="{lauf.farbe}"/>')
        if lauf.sperrung:
            rpr.append(f'<w:spacing w:val="{round(lauf.sperrung * 20)}"/>')
        if lauf.groesse:
            halb = round(lauf.groesse * 2)
            rpr.append(f'<w:sz w:val="{halb}"/><w:szCs w:val="{halb}"/>')
        teile = []
        for i, zeile in enumerate(lauf.text.split("\n")):
            if i:
                teile.append("<w:br/>")
            if zeile:
                teile.append(f'<w:t xml:space="preserve">{x(zeile)}</w:t>')
        run = f"<w:r>{'<w:rPr>' + ''.join(rpr) + '</w:rPr>' if rpr else ''}{''.join(teile)}</w:r>"
        if lauf.link:
            rid = self.beziehung(f"{REL}/hyperlink", lauf.link, extern=True)
            return f'<w:hyperlink r:id="{rid}" w:history="1">{run}</w:hyperlink>'
        return run

    def absatz(self, a: dm.Absatz) -> str:
        ppr = []
        if a.ueberschrift:
            ppr.append('<w:pStyle w:val="Heading1"/>')
        elif a.aufzaehlung:
            ppr.append('<w:pStyle w:val="ListParagraph"/>')
        if a.mit_naechstem:
            ppr.append("<w:keepNext/>")
        if a.aufzaehlung:
            ppr.append('<w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr>')
        if a.linie_unten:
            ppr.append(f'<w:pBdr><w:bottom w:val="single" w:sz="{max(2, round(a.linie_staerke * 8))}" '
                       f'w:space="1" w:color="{a.linie_unten}"/></w:pBdr>')
        ppr.append(f'<w:spacing w:before="{round(a.vor * 20)}" w:after="{round(a.nach * 20)}"/>')
        jc = {"rechts": "right", "mitte": "center"}.get(a.ausrichtung)
        if jc:
            ppr.append(f'<w:jc w:val="{jc}"/>')
        # Die Absatzmarke bekommt die Größe des ersten Laufs – wichtig für leere Absätze
        erste_groesse = next((l.groesse for l in a.laeufe if l.groesse), None)
        if erste_groesse:
            halb = round(erste_groesse * 2)
            ppr.append(f'<w:rPr><w:sz w:val="{halb}"/><w:szCs w:val="{halb}"/></w:rPr>')
        return f"<w:p><w:pPr>{''.join(ppr)}</w:pPr>{''.join(self.lauf(l) for l in a.laeufe)}</w:p>"

    def tabelle(self, t: dm.Tabelle) -> str:
        breiten = [_tw(mm) for mm in t.spalten]
        rand_rechts = _tw(3)
        xml = [
            "<w:tbl><w:tblPr>",
            f'<w:tblW w:w="{sum(breiten)}" w:type="dxa"/>',
            '<w:tblInd w:w="0" w:type="dxa"/>',
            "<w:tblBorders>" + "".join(f'<w:{s} w:val="nil"/>' for s in
                                       ("top", "left", "bottom", "right", "insideH", "insideV")) + "</w:tblBorders>",
            '<w:tblLayout w:type="fixed"/>',
            '<w:tblCellMar><w:top w:w="0" w:type="dxa"/><w:left w:w="0" w:type="dxa"/>'
            '<w:bottom w:w="0" w:type="dxa"/><w:right w:w="0" w:type="dxa"/></w:tblCellMar>',
            '<w:tblLook w:val="0000" w:firstRow="0" w:lastRow="0" w:firstColumn="0" w:lastColumn="0" '
            'w:noHBand="1" w:noVBand="1"/>',
            "</w:tblPr><w:tblGrid>",
            "".join(f'<w:gridCol w:w="{b}"/>' for b in breiten),
            "</w:tblGrid>",
        ]
        for zeile in t.zeilen:
            xml.append("<w:tr>")
            if t.zeilen_zusammenhalten:
                xml.append("<w:trPr><w:cantSplit/></w:trPr>")
            for nr, zelle in enumerate(zeile):
                tcpr = [f'<w:tcW w:w="{breiten[nr]}" w:type="dxa"/>']
                if nr < len(zeile) - 1:
                    tcpr.append(f'<w:tcMar><w:right w:w="{rand_rechts}" w:type="dxa"/></w:tcMar>')
                v = {"mitte": "center", "unten": "bottom"}.get(zelle.vertikal)
                if v:
                    tcpr.append(f'<w:vAlign w:val="{v}"/>')
                inhalt = self.bloecke(zelle.inhalt)
                # Jede Zelle muss mit einem Absatz enden
                if not zelle.inhalt or isinstance(zelle.inhalt[-1], dm.Tabelle):
                    inhalt += "<w:p/>"
                xml.append(f"<w:tc><w:tcPr>{''.join(tcpr)}</w:tcPr>{inhalt}</w:tc>")
            xml.append("</w:tr>")
        xml.append("</w:tbl>")
        return "".join(xml)

    def bild(self, b) -> str:
        self.bild_nr += 1
        nr = self.bild_nr
        pfad = f"media/bild{nr}.{b.endung}"
        self.medien.append((f"word/{pfad}", b.daten))
        rid = self.beziehung(f"{REL}/image", pfad)
        cx, cy = round(b.breite_mm * EMU_PRO_MM), round(b.hoehe_mm * EMU_PRO_MM)
        l, o, r, u = (round(w * 100000) for w in b.zuschnitt)
        ausschnitt = f'<a:srcRect l="{l}" t="{o}" r="{r}" b="{u}"/>' if any((l, o, r, u)) else ""
        form = "ellipse" if b.rund and not b.freigestellt else "rect"
        return (
            f'<w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0">'
            f'<wp:extent cx="{cx}" cy="{cy}"/><wp:effectExtent l="0" t="0" r="0" b="0"/>'
            f'<wp:docPr id="{nr}" name="Foto {nr}" descr="Bewerbungsfoto"/>'
            f'<wp:cNvGraphicFramePr><a:graphicFrameLocks noChangeAspect="1"/></wp:cNvGraphicFramePr>'
            f'<a:graphic><a:graphicData uri="{NS_PIC}"><pic:pic>'
            f'<pic:nvPicPr><pic:cNvPr id="{nr}" name="bild{nr}.{b.endung}"/><pic:cNvPicPr/></pic:nvPicPr>'
            f'<pic:blipFill><a:blip r:embed="{rid}"/>{ausschnitt}<a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
            f'<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
            f'<a:prstGeom prst="{form}"><a:avLst/></a:prstGeom></pic:spPr>'
            f'</pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing>'
        )

    def bloecke(self, bloecke: list) -> str:
        return "".join(self.tabelle(b) if isinstance(b, dm.Tabelle) else self.absatz(b) for b in bloecke)

    # ------------------------------------------------------------ Paketteile

    def document_xml(self) -> str:
        oben, rechts, unten, links = (_tw(mm) for mm in self.dok.rand)
        koerper = self.bloecke(self.dok.bloecke)
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<w:document xmlns:w="{NS_W}" xmlns:r="{NS_R}" xmlns:wp="{NS_WP}" xmlns:a="{NS_A}" xmlns:pic="{NS_PIC}">'
            f"<w:body>{koerper}"
            f'<w:sectPr><w:pgSz w:w="{_tw(dm.SEITE_BREITE)}" w:h="{_tw(dm.SEITE_HOEHE)}"/>'
            f'<w:pgMar w:top="{oben}" w:right="{rechts}" w:bottom="{unten}" w:left="{links}" '
            f'w:header="567" w:footer="567" w:gutter="0"/><w:cols w:space="708"/></w:sectPr>'
            "</w:body></w:document>"
        )

    def styles_xml(self) -> str:
        d = self.dok
        schrift = x(d.schrift)
        halb = round(d.groesse * 2)
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<w:styles xmlns:w="{NS_W}">'
            "<w:docDefaults><w:rPrDefault><w:rPr>"
            f'<w:rFonts w:ascii="{schrift}" w:hAnsi="{schrift}" w:eastAsia="{schrift}" w:cs="{schrift}"/>'
            f'<w:color w:val="{d.textfarbe}"/><w:sz w:val="{halb}"/><w:szCs w:val="{halb}"/>'
            f'<w:lang w:val="{d.sprache}" w:eastAsia="{d.sprache}" w:bidi="ar-SA"/>'
            "</w:rPr></w:rPrDefault>"
            '<w:pPrDefault><w:pPr><w:spacing w:after="0" w:line="264" w:lineRule="auto"/></w:pPr></w:pPrDefault>'
            "</w:docDefaults>"
            '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:qFormat/></w:style>'
            '<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/>'
            '<w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:uiPriority w:val="9"/><w:qFormat/>'
            '<w:pPr><w:keepNext/><w:outlineLvl w:val="0"/></w:pPr>'
            f'<w:rPr><w:b/><w:bCs/><w:color w:val="{d.akzent}"/></w:rPr></w:style>'
            '<w:style w:type="paragraph" w:styleId="ListParagraph"><w:name w:val="List Paragraph"/>'
            '<w:basedOn w:val="Normal"/><w:uiPriority w:val="34"/><w:qFormat/></w:style>'
            '<w:style w:type="character" w:default="1" w:styleId="DefaultParagraphFont">'
            '<w:name w:val="Default Paragraph Font"/><w:uiPriority w:val="1"/><w:semiHidden/></w:style>'
            '<w:style w:type="character" w:styleId="Hyperlink"><w:name w:val="Hyperlink"/>'
            f'<w:basedOn w:val="DefaultParagraphFont"/><w:rPr><w:color w:val="{d.akzent}"/></w:rPr></w:style>'
            '<w:style w:type="table" w:default="1" w:styleId="TableNormal"><w:name w:val="Normal Table"/>'
            '<w:uiPriority w:val="99"/><w:semiHidden/><w:tblPr><w:tblInd w:w="0" w:type="dxa"/>'
            '<w:tblCellMar><w:top w:w="0" w:type="dxa"/><w:left w:w="108" w:type="dxa"/>'
            '<w:bottom w:w="0" w:type="dxa"/><w:right w:w="108" w:type="dxa"/></w:tblCellMar></w:tblPr></w:style>'
            "</w:styles>"
        )

    def numbering_xml(self) -> str:
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<w:numbering xmlns:w="{NS_W}">'
            '<w:abstractNum w:abstractNumId="0"><w:multiLevelType w:val="singleLevel"/>'
            '<w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="bullet"/><w:lvlText w:val="•"/>'
            f'<w:lvlJc w:val="left"/><w:pPr><w:ind w:left="{_tw(4.5)}" w:hanging="{_tw(4)}"/></w:pPr>'
            f'<w:rPr><w:color w:val="{self.dok.akzent}"/></w:rPr></w:lvl></w:abstractNum>'
            '<w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num>'
            "</w:numbering>"
        )

    def settings_xml(self) -> str:
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<w:settings xmlns:w="{NS_W}"><w:zoom w:percent="100"/><w:defaultTabStop w:val="708"/>'
            '<w:characterSpacingControl w:val="doNotCompress"/>'
            '<w:compat><w:compatSetting w:name="compatibilityMode" w:uri="http://schemas.microsoft.com/office/word" w:val="15"/></w:compat>'
            "</w:settings>"
        )

    def rels_xml(self) -> str:
        teile = []
        for rid, typ, ziel, extern in self.beziehungen:
            modus = ' TargetMode="External"' if extern else ""
            teile.append(f'<Relationship Id="{rid}" Type="{typ}" Target="{x(ziel)}"{modus}/>')
        return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                + "".join(teile) + "</Relationships>")


def _content_types() -> str:
    ct = "application/vnd.openxmlformats-officedocument.wordprocessingml"
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Default Extension="jpeg" ContentType="image/jpeg"/>'
        '<Default Extension="png" ContentType="image/png"/>'
        f'<Override PartName="/word/document.xml" ContentType="{ct}.document.main+xml"/>'
        f'<Override PartName="/word/styles.xml" ContentType="{ct}.styles+xml"/>'
        f'<Override PartName="/word/settings.xml" ContentType="{ct}.settings+xml"/>'
        f'<Override PartName="/word/numbering.xml" ContentType="{ct}.numbering+xml"/>'
        '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
        '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>'
        "</Types>"
    )


def _paket_rels() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f'<Relationship Id="rId1" Type="{REL}/officeDocument" Target="word/document.xml"/>'
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
        f'<Relationship Id="rId3" Type="{REL}/extended-properties" Target="docProps/app.xml"/>'
        "</Relationships>"
    )


def _core(dok: dm.Dokument) -> str:
    jetzt = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        f"<dc:title>{x(dok.titel)}</dc:title><dc:creator>{x(dok.autor)}</dc:creator>"
        f"<dc:language>{dok.sprache}</dc:language>"
        f'<dcterms:created xsi:type="dcterms:W3CDTF">{jetzt}</dcterms:created>'
        f'<dcterms:modified xsi:type="dcterms:W3CDTF">{jetzt}</dcterms:modified>'
        "</cp:coreProperties>"
    )


def _app() -> str:
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties">'
            "<Application>Lebenslauf-Generator</Application></Properties>")


def schreiben(dok: dm.Dokument, ziel) -> None:
    """Schreibt das Dokument als .docx nach `ziel` (Pfad oder Datei-Objekt)."""
    s = _Schreiber(dok)
    document = s.document_xml()          # zuerst: sammelt Bilder und Links ein
    dateien = [
        ("[Content_Types].xml", _content_types(), True),
        ("_rels/.rels", _paket_rels(), True),
        ("docProps/core.xml", _core(dok), True),
        ("docProps/app.xml", _app(), True),
        ("word/document.xml", document, True),
        ("word/styles.xml", s.styles_xml(), True),
        ("word/settings.xml", s.settings_xml(), True),
        ("word/numbering.xml", s.numbering_xml(), True),
        ("word/_rels/document.xml.rels", s.rels_xml(), True),
    ]
    dateien += [(pfad, daten, False) for pfad, daten in s.medien]
    zip_schreiben(ziel, dateien)


def exportieren(cv: dict, ziel) -> None:
    schreiben(dm.klassisch(cv), ziel)
