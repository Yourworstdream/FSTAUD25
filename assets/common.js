/* FST AUD 25 – gemeinsame Einstellungen und Hilfsfunktionen
   für die Anleitung (index.html) und den Live-Fortschritt (fortschritt.html). */
window.FST = (() => {
  'use strict';

  // Standard-Repository. Auf GitHub Pages (<owner>.github.io/<repo>/) wird es aus der
  // Adresse abgeleitet, damit auch eine Kopie des Repositorys ohne Änderungen funktioniert.
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
  const SEITEN_URL = `https://${owner.toLowerCase()}.github.io/${repo}/`;

  // Die 7 Schritte – die IDs müssen zu .github/scripts/fortschritt.js passen.
  const SCHRITTE = [
    { id: 'anmeldung', nr: 1, titel: 'Angemeldet', icon: '📝', farbe: '#6366f1', text: 'GitHub-Konto erstellt und für die Klasse angemeldet' },
    { id: 'team', nr: 2, titel: 'Im Team', icon: '🤝', farbe: '#0ea5e9', text: 'Einladung ins Repository angenommen' },
    { id: 'pr', nr: 3, titel: 'Pull Request', icon: '🌿', farbe: '#10b981', text: 'Ersten Pull Request (Steckbrief) geöffnet' },
    { id: 'merge', nr: 4, titel: 'Gemerged', icon: '✅', farbe: '#22c55e', text: 'Eigener Pull Request wurde übernommen' },
    { id: 'review', nr: 5, titel: 'Review', icon: '👀', farbe: '#f59e0b', text: 'Pull Request einer anderen Person geprüft' },
    { id: 'diskussion', nr: 6, titel: 'Diskussion', icon: '💬', farbe: '#ec4899', text: 'Issue erstellt oder kommentiert' },
    { id: 'projekt', nr: 7, titel: 'Projekt', icon: '🚀', farbe: '#8b5cf6', text: 'Beitrag zum Automatisierungs-Wiki gemerged' },
  ];

  // localStorage kann gesperrt sein (privates Fenster, Schulrechner) – dann einfach ohne.
  const PREFIX = 'fstaud25.';
  function lesen(schluessel) {
    try { return localStorage.getItem(PREFIX + schluessel); } catch { return null; }
  }
  function schreiben(schluessel, wert) {
    try {
      if (wert == null) localStorage.removeItem(PREFIX + schluessel);
      else localStorage.setItem(PREFIX + schluessel, wert);
    } catch { /* ohne Speicher weitermachen */ }
  }

  const ZEICHEN = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
  function escape(text) {
    return String(text ?? '').replace(/[&<>"']/g, (z) => ZEICHEN[z]);
  }

  const rtf = new Intl.RelativeTimeFormat('de', { numeric: 'auto' });
  function datumZeit(iso) {
    return new Date(iso).toLocaleString('de-DE', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }) + ' Uhr';
  }
  function relativeZeit(iso) {
    if (!iso || iso === true) return '';
    const sek = Math.round((new Date(iso).getTime() - Date.now()) / 1000);
    const abs = Math.abs(sek);
    if (Number.isNaN(sek)) return '';
    if (abs < 45) return 'gerade eben';
    if (abs < 3600) return rtf.format(Math.round(sek / 60), 'minute');
    if (abs < 86400) return rtf.format(Math.round(sek / 3600), 'hour');
    if (abs < 86400 * 14) return rtf.format(Math.round(sek / 86400), 'day');
    return datumZeit(iso);
  }

  function anzahlErledigt(t) {
    return SCHRITTE.filter((s) => t.erledigt && t.erledigt[s.id]).length;
  }
  function naechsterSchritt(t) {
    return SCHRITTE.find((s) => !(t.erledigt && t.erledigt[s.id])) || null;
  }

  function sichereUrl(url, praefix = 'https://') {
    return typeof url === 'string' && url.startsWith(praefix) ? url : null;
  }

  function initialen(name) {
    return String(name || '?').split(/[\s._-]+/).filter(Boolean).slice(0, 2)
      .map((wort) => Array.from(wort)[0].toUpperCase()).join('');
  }
  function farbeAus(text) {
    let h = 7;
    for (const z of String(text)) h = (h * 31 + z.codePointAt(0)) % 360;
    return `hsl(${h} 55% 45%)`;
  }
  function avatarHtml(t) {
    const src = sichereUrl(t.avatar);
    if (src) return `<span class="avatar"><img src="${escape(src)}" alt="" loading="lazy" referrerpolicy="no-referrer"></span>`;
    return `<span class="avatar" style="background:${farbeAus(t.login || t.name)}" aria-hidden="true">${escape(initialen(t.name || t.login))}</span>`;
  }

  async function fortschrittLaden() {
    const antwort = await fetch(`fortschritt.json?t=${Date.now()}`, { cache: 'no-store' });
    if (antwort.status === 404) return null;
    if (!antwort.ok) throw new Error(`HTTP ${antwort.status}`);
    return antwort.json();
  }

  function themaUmschalten() {
    const wurzel = document.documentElement;
    const aktuell = wurzel.dataset.theme || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
    const neu = aktuell === 'dark' ? 'light' : 'dark';
    wurzel.dataset.theme = neu;
    schreiben('theme', neu);
  }

  function repoLinksSetzen(wurzel = document) {
    wurzel.querySelectorAll('[data-repo]').forEach((a) => { a.href = REPO_URL + a.dataset.repo; });
  }

  document.addEventListener('DOMContentLoaded', () => {
    repoLinksSetzen();
    document.querySelectorAll('[data-thema-knopf]').forEach((k) => k.addEventListener('click', themaUmschalten));
  });

  return {
    owner, repo, REPO_URL, SEITEN_URL, SCHRITTE,
    lesen, schreiben, escape, relativeZeit, datumZeit,
    anzahlErledigt, naechsterSchritt, sichereUrl, avatarHtml, fortschrittLaden, repoLinksSetzen,
  };
})();
