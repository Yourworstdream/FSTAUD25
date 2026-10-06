"""Tests für Datenmodell und Exporte.  Ausführen im Ordner lebenslauf/:

    python -m unittest discover -s tests -v
"""
import base64
import datetime
import io
import json
import os
import struct
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile
import zlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lebenslauf_app import bild, daten, dokument, export_docx, export_html, export_odt, exporte  # noqa: E402

HEUTE = datetime.date(2026, 10, 6)


def png(breite, hoehe):
    """Erzeugt ein kleines einfarbiges PNG ohne Zusatzbibliotheken."""
    def block(art, inhalt):
        return struct.pack(">I", len(inhalt)) + art + inhalt + struct.pack(">I", zlib.crc32(art + inhalt))
    zeilen = b"".join(b"\x00" + b"\x40\x70\xa0" * breite for _ in range(hoehe))
    return (b"\x89PNG\r\n\x1a\n" + block(b"IHDR", struct.pack(">IIBBBBB", breite, hoehe, 8, 2, 0, 0, 0))
            + block(b"IDAT", zlib.compress(zeilen)) + block(b"IEND", b""))


def mit_foto(cv, form="rechteckig"):
    cv["kopf"]["foto"] = {"daten": base64.b64encode(png(40, 60)).decode(), "mime": "image/png"}
    cv["kopf"]["foto_form"] = form
    return cv


def docx_teile(cv):
    puffer = io.BytesIO()
    export_docx.exportieren(cv, puffer)
    with zipfile.ZipFile(puffer) as z:
        return {name: z.read(name) for name in z.namelist()}


def odt_archiv(cv):
    puffer = io.BytesIO()
    export_odt.exportieren(cv, puffer)
    return zipfile.ZipFile(puffer)


class DatenTest(unittest.TestCase):
    def test_beispiel_ist_gueltig(self):
        cv = daten.beispiel()
        self.assertEqual(daten.normalisieren(json.loads(json.dumps(cv))), cv)

    def test_speichern_und_laden(self):
        cv = mit_foto(daten.beispiel())
        with tempfile.TemporaryDirectory() as ordner:
            pfad = os.path.join(ordner, "cv.json")
            daten.speichern(cv, pfad)
            self.assertEqual(daten.laden(pfad), cv)
            self.assertEqual(os.listdir(ordner), ["cv.json"])   # keine Temp-Dateien übrig

    def test_unvollstaendige_datei_wird_ergaenzt(self):
        cv = daten.normalisieren({"abschnitte": [{"typ": "kenntnisse", "eintraege": [{"name": "SPS", "stufe": 9}]},
                                                 {"typ": "gibtsnicht"}, "Unsinn"]})
        self.assertEqual(len(cv["abschnitte"]), 1)
        kenntnis = cv["abschnitte"][0]["eintraege"][0]
        self.assertEqual(kenntnis["stufe"], 5)
        self.assertTrue(kenntnis["zeigen"])
        self.assertEqual(cv["design"]["schrift"], "Georgia")

    def test_ungueltige_datei(self):
        for falsch in ([], {"kopf": {}}, "text"):
            with self.assertRaises(ValueError):
                daten.normalisieren(falsch)

    def test_doppelte_ids_werden_ersetzt(self):
        cv = daten.beispiel()
        cv["abschnitte"][1]["id"] = cv["abschnitte"][0]["id"]
        cv["abschnitte"][2]["id"] = "kopf"
        ids = [a["id"] for a in daten.normalisieren(cv)["abschnitte"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertNotIn("kopf", ids)

    def test_fremde_farbe_und_foto_werden_abgelehnt(self):
        cv = daten.beispiel()
        cv["design"]["farbe"] = "red;background:url(x)"
        cv["kopf"]["foto"] = {"daten": "\"><script>", "mime": "image/png"}
        cv = daten.normalisieren(cv)
        self.assertEqual(cv["design"]["farbe"], daten.standard_design()["farbe"])
        self.assertIsNone(cv["kopf"]["foto"])

    def test_link_erkennung(self):
        self.assertEqual(daten.link_ziel("E-Mail", "a@b.de"), ("mail", "mailto:a@b.de"))
        self.assertEqual(daten.link_ziel("Telefon", "0631 123 45"), ("tel", "tel:063112345"))
        self.assertEqual(daten.link_ziel("GitHub", "github.com/max"), ("web", "https://github.com/max"))
        self.assertEqual(daten.link_ziel("Geburtsdatum", "14.03.2001"), (None, None))
        self.assertEqual(daten.link_ziel("Notiz", "javascript:alert(1)"), (None, None))

    def test_beschreibung_zeilen(self):
        self.assertEqual(daten.beschreibung_zeilen("- eins\n\n• zwei\nText"),
                         [(True, "eins"), (True, "zwei"), (False, "Text")])

    def test_dateiname(self):
        cv = daten.beispiel()
        cv["kopf"]["name"] = "Jörg O'Neil / Test"
        self.assertEqual(daten.dateiname(cv, "docx"), "Lebenslauf_Jörg_O_Neil_Test.docx")


class BildTest(unittest.TestCase):
    def test_bild_info_png(self):
        self.assertEqual(bild.bild_info(png(40, 60)), ("image/png", 40, 60))

    def test_kein_bild(self):
        with self.assertRaises(ValueError):
            bild.bild_info(b"GIF89a....")

    def test_zuschnitt(self):
        links, oben, rechts, unten = bild.zuschnitt_berechnen(200, 100, 35, 45)
        self.assertAlmostEqual(links, rechts)
        self.assertAlmostEqual((1 - links - rechts) * 200 / 100, 35 / 45)
        self.assertEqual((oben, unten), (0, 0))


class DocxTest(unittest.TestCase):
    PFLICHT = ["[Content_Types].xml", "_rels/.rels", "word/document.xml", "word/styles.xml",
               "word/_rels/document.xml.rels", "word/numbering.xml", "word/settings.xml", "docProps/core.xml"]

    def test_aufbau_und_inhalt(self):
        teile = docx_teile(mit_foto(daten.beispiel()))
        for name in self.PFLICHT:
            self.assertIn(name, teile)
        for name, inhalt in teile.items():
            if name.endswith((".xml", ".rels")):
                ET.fromstring(inhalt)          # wohlgeformtes XML
        text = teile["word/document.xml"].decode()
        for erwartet in ("Max Mustermann", "Berufserfahrung", "Muster Automation GmbH", "Muttersprache"):
            self.assertIn(erwartet, text)
        self.assertTrue(any(n.startswith("word/media/") for n in teile))
        self.assertIn("mailto:max.mustermann@example.com", teile["word/_rels/document.xml.rels"].decode())

    def test_ausgeblendetes_fehlt(self):
        cv = daten.beispiel()
        cv["abschnitte"][2]["zeigen"] = False                    # Berufserfahrung
        cv["abschnitte"][0]["felder"][3]["zeigen"] = False       # Geburtsdatum
        cv["abschnitte"][3]["eintraege"][0]["zeigen"] = False    # Techniker-Weiterbildung
        text = docx_teile(cv)["word/document.xml"].decode()
        for fehlt in ("Servicetechniker (befristet)", "14.03.2001", "Staatlich geprüfter Techniker"):
            self.assertNotIn(fehlt, text)
        self.assertIn("Ausbildung Elektroniker", text)

    def test_leerer_lebenslauf(self):
        teile = docx_teile(daten.leerer_lebenslauf())
        ET.fromstring(teile["word/document.xml"])

    def test_sonderzeichen(self):
        cv = daten.beispiel()
        cv["kopf"]["name"] = "Ä & <Ö> \"Ü\" \x0b"
        ET.fromstring(docx_teile(cv)["word/document.xml"])


class OdtTest(unittest.TestCase):
    def test_aufbau(self):
        with odt_archiv(mit_foto(daten.beispiel(), "rund")) as z:
            erste = z.infolist()[0]
            self.assertEqual(erste.filename, "mimetype")
            self.assertEqual(erste.compress_type, zipfile.ZIP_STORED)
            self.assertEqual(z.read("mimetype"), b"application/vnd.oasis.opendocument.text")
            for name in ("content.xml", "styles.xml", "meta.xml", "META-INF/manifest.xml"):
                ET.fromstring(z.read(name))
            content = z.read("content.xml").decode()
            self.assertIn("Max Mustermann", content)
            self.assertTrue(any(n.startswith("Pictures/") for n in z.namelist()))

    def test_leerzeichen(self):
        self.assertEqual(export_odt._odf_text("a  b"), 'a<text:s text:c="2"/>b')
        self.assertEqual(export_odt._odf_text("x\ny"), "x<text:line-break/>y")


class HtmlTest(unittest.TestCase):
    def test_inhalt_und_escape(self):
        cv = daten.beispiel()
        cv["abschnitte"][1]["text"] = "<script>alert(1)</script>"
        seite = export_html.erzeugen(cv, heute=HEUTE)
        self.assertIn("Max Mustermann", seite)
        self.assertNotIn("<script>alert(1)", seite)
        self.assertIn("&lt;script&gt;", seite)
        self.assertIn('href="mailto:max.mustermann@example.com"', seite)
        self.assertIn("Musterstadt, 06.10.2026", seite)
        self.assertNotIn("lv-scroll", seite)
        self.assertIn("lv-scroll", export_html.erzeugen(cv, live=True))

    def test_json_ld_kann_nicht_ausbrechen(self):
        cv = daten.beispiel()
        cv["kopf"]["name"] = "</script><b>"
        seite = export_html.erzeugen(cv)
        self.assertNotIn("</script><b>", seite)
        self.assertEqual(seite.count("</script>"), 3)   # nur die eigenen Script-Tags

    def test_ausgeblendet(self):
        cv = daten.beispiel()
        cv["abschnitte"][5]["zeigen"] = False   # Fachkenntnisse
        self.assertNotIn("Fachkenntnisse", export_html.erzeugen(cv))


class ExportTest(unittest.TestCase):
    def test_alle_formate_als_datei(self):
        cv = mit_foto(daten.beispiel())
        with tempfile.TemporaryDirectory() as ordner:
            for kuerzel, (_, endung, _) in exporte.FORMATE.items():
                pfad = os.path.join(ordner, daten.dateiname(cv, endung))
                exporte.exportieren(cv, kuerzel, pfad)
                self.assertGreater(os.path.getsize(pfad), 1000)

    def test_dokumentmodell_spaltenbreite(self):
        cv = daten.beispiel()
        cv["design"]["spaltenbreite"] = 55
        tabellen = [b for b in dokument.klassisch(cv).bloecke if isinstance(b, dokument.Tabelle)]
        self.assertTrue(all(t.spalten[0] == 55 for t in tabellen))


if __name__ == "__main__":
    unittest.main()
