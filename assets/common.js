/* FST AUD 25 – gemeinsame Einstellungen und Hilfsfunktionen für alle Seiten. */
window.FST = (() => {
  'use strict';

  // Auf GitHub Pages (<owner>.github.io/<repo>/) werden Owner und Repo aus der Adresse
  // abgeleitet, damit auch eine Kopie des Repositorys ohne Änderungen funktioniert.
  const STANDARD = { owner: 'Yourworstdream', repo: 'FSTAUD25' };

  function repoErmitteln() {
    const host = location.hostname.match(/^([a-z\d-]+)\.github\.io$/i);
    const ordner = location.pathname.split('/').filter(Boolean)[0];
    if (!host || !ordner || /\.html?$/i.test(ordner)) return STANDARD;
    const gleich = host[1].toLowerCase() === STANDARD.owner.toLowerCase() && ordner === STANDARD.repo;
    return gleich ? STANDARD : { owner: host[1], repo: ordner };
  }

  const { owner, repo } = repoErmitteln();
  const REPO_URL = `https://github.com/${owner}/${repo}`;

  // Die IDs müssen zu .github/scripts/fortschritt.js passen.
  const SCHRITTE = [
    { id: 'anmeldung', nr: 1, kurz: 'Anmeldung', text: 'angemeldet' },
    { id: 'team', nr: 2, kurz: 'Einladung', text: 'Einladung angenommen' },
    { id: 'pr', nr: 3, kurz: 'PR', text: 'Pull Request geöffnet' },
    { id: 'merge', nr: 4, kurz: 'Merge', text: 'Pull Request gemerged' },
    { id: 'review', nr: 5, kurz: 'Review', text: 'fremden Pull Request geprüft' },
    { id: 'diskussion', nr: 6, kurz: 'Issue', text: 'in einem Issue mitgeredet' },
    { id: 'projekt', nr: 7, kurz: 'Wiki', text: 'Wiki-Seite gemerged' },
  ];

  // localStorage kann gesperrt sein (privates Fenster, Schulrechner) – dann einfach ohne.
  const PREFIX = 'fstaud25.';
  function lesen(schluessel) {
    try { return localStorage.getItem(PREFIX + schluessel); } catch { return null; }
  }
  function schreiben(schluessel, wert) {
    try { localStorage.setItem(PREFIX + schluessel, wert); } catch { /* ohne Speicher weitermachen */ }
  }

  const ZEICHEN = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
  function escape(text) {
    return String(text ?? '').replace(/[&<>"']/g, (z) => ZEICHEN[z]);
  }

  const rtf = new Intl.RelativeTimeFormat('de', { numeric: 'auto' });
  function relativeZeit(iso) {
    const sek = Math.round((new Date(iso).getTime() - Date.now()) / 1000);
    if (Number.isNaN(sek)) return '';
    if (Math.abs(sek) < 60) return 'gerade eben';
    if (Math.abs(sek) < 3600) return rtf.format(Math.round(sek / 60), 'minute');
    if (Math.abs(sek) < 86400) return rtf.format(Math.round(sek / 3600), 'hour');
    return rtf.format(Math.round(sek / 86400), 'day');
  }

  // "14:05" für heute, sonst "03.10. 14:05"
  function uhrzeit(iso) {
    const d = new Date(iso);
    const zeit = d.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' });
    const heute = d.toDateString() === new Date().toDateString();
    return heute ? zeit : `${d.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit' })} ${zeit}`;
  }

  function anzahlErledigt(t) {
    return SCHRITTE.filter((s) => t.erledigt && t.erledigt[s.id]).length;
  }

  async function fortschrittLaden() {
    const antwort = await fetch(`fortschritt.json?t=${Date.now()}`, { cache: 'no-store' });
    if (antwort.status === 404) return null;
    if (!antwort.ok) throw new Error(`HTTP ${antwort.status}`);
    return antwort.json();
  }

  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[data-repo]').forEach((a) => { a.href = REPO_URL + a.dataset.repo; });
  });

  return { owner, repo, REPO_URL, SCHRITTE, lesen, schreiben, escape, relativeZeit, uhrzeit, anzahlErledigt, fortschrittLaden };
})();
