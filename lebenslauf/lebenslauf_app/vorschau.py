"""Live-Vorschau im Browser: ein kleiner Webserver nur auf diesem Rechner (127.0.0.1).

Das Programm übergibt nach jeder Änderung die neue HTML-Seite; der Browser fragt
regelmäßig /version ab und lädt bei einer neuen Version automatisch neu.
"""
from __future__ import annotations

import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class LiveVorschau:
    def __init__(self):
        self._html = b""
        self._version = 0
        self._sperre = threading.Lock()
        self._server = None

    @property
    def laeuft(self) -> bool:
        return self._server is not None

    @property
    def adresse(self) -> str:
        return f"http://127.0.0.1:{self._server.server_address[1]}/" if self._server else ""

    def aktualisieren(self, html: str) -> None:
        with self._sperre:
            daten = html.encode("utf-8")
            if daten != self._html:
                self._html = daten
                self._version += 1

    def starten(self) -> str:
        if self._server is None:
            vorschau = self

            class Anfrage(BaseHTTPRequestHandler):
                def do_GET(self):  # noqa: N802 (Name von http.server vorgegeben)
                    # Nur Anfragen an diesen Rechner beantworten (Schutz gegen DNS-Rebinding)
                    port = self.server.server_address[1]
                    if self.headers.get("Host") not in (f"127.0.0.1:{port}", f"localhost:{port}"):
                        self.send_error(403)
                        return
                    with vorschau._sperre:
                        if self.path.split("?")[0] == "/version":
                            inhalt, typ = str(vorschau._version).encode(), "text/plain"
                        elif self.path.split("?")[0] in ("/", "/index.html"):
                            inhalt, typ = vorschau._html, "text/html; charset=utf-8"
                        else:
                            self.send_error(404)
                            return
                    self.send_response(200)
                    self.send_header("Content-Type", typ)
                    self.send_header("Content-Length", str(len(inhalt)))
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    self.wfile.write(inhalt)

                def log_message(self, *args):  # keine Ausgabe im Terminal
                    pass

            self._server = ThreadingHTTPServer(("127.0.0.1", 0), Anfrage)
            self._server.daemon_threads = True
            threading.Thread(target=self._server.serve_forever, daemon=True).start()
        return self.adresse

    def oeffnen(self) -> str:
        adresse = self.starten()
        webbrowser.open(adresse)
        return adresse

    def stoppen(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
