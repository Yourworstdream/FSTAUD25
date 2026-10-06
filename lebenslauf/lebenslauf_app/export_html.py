"""Export als interaktive Webseite (.html) – eine einzelne Datei ohne externe Abhängigkeiten.

Funktionen der Seite: sanftes Einblenden beim Scrollen, animierte Kenntnis-Punkte,
Abschnitte ein-/ausklappen, Hell/Dunkel-Umschalter, E-Mail/Telefon per Klick kopieren,
Dauer jeder Station (z. B. „3 Jahre 2 Monate“), Inhaltsnavigation auf breiten Bildschirmen,
Lesefortschritt und eine saubere Druckansicht (Drucken → „Als PDF speichern“).
"""
from __future__ import annotations

import datetime as _dt
import html
import json

from . import bild, daten, design


def _e(text: str) -> str:
    return html.escape(str(text), quote=True)


def _mehrzeilig(text: str) -> str:
    return "<br>".join(_e(z) for z in text.split("\n"))


def _wert_html(label: str, wert: str) -> str:
    art, ziel = daten.link_ziel(label, wert)
    wert = wert.strip()
    if not art:
        return _mehrzeilig(wert)
    extern = ' target="_blank" rel="noopener"' if art == "web" else ""
    link = f'<a href="{_e(ziel)}"{extern}>{_e(wert)}</a>'
    if art in ("mail", "tel"):
        was = "E-Mail-Adresse" if art == "mail" else "Telefonnummer"
        link += (f' <button type="button" class="kopieren" data-kopieren="{_e(wert)}" data-was="{was}" '
                 f'title="{was} kopieren" aria-label="{was} kopieren">⧉</button>')
    return link


def _abschnitt_html(abschnitt: dict) -> str:
    typ = abschnitt["typ"]
    teile = []
    if typ == "persoenlich":
        for feld in daten.sichtbare_felder(abschnitt):
            teile.append(f'<div class="zeile feld erscheinen"><div class="links">{_e(feld["label"].strip())}</div>'
                         f'<div class="rechts">{_wert_html(feld["label"], feld["wert"])}</div></div>')
    elif typ == "text":
        for absatz in daten.text_absaetze(abschnitt["text"]):
            teile.append(f'<p class="fliesstext erscheinen">{_mehrzeilig(absatz)}</p>')
    elif typ == "eintraege":
        for e in daten.sichtbare_eintraege(abschnitt):
            rechts = []
            if e["titel"].strip():
                rechts.append(f'<h3>{_e(e["titel"].strip())}</h3>')
            unterzeile = ", ".join(t.strip() for t in (e["organisation"], e["ort"]) if t.strip())
            if unterzeile:
                rechts.append(f'<p class="unterzeile">{_e(unterzeile)}</p>')
            liste = []
            for punkt, text in daten.beschreibung_zeilen(e["beschreibung"]) + [(False, None)]:
                if punkt:
                    liste.append(f"<li>{_e(text)}</li>")
                    continue
                if liste:
                    rechts.append(f"<ul>{''.join(liste)}</ul>")
                    liste = []
                if text is not None:
                    rechts.append(f"<p>{_e(text)}</p>")
            teile.append(
                f'<div class="zeile eintrag erscheinen" data-von="{_e(e["von"].strip())}" data-bis="{_e(e["bis"].strip())}">'
                f'<div class="links"><span class="zeitraum">{_e(daten.zeitraum(e["von"], e["bis"]))}</span>'
                f'<span class="dauer"></span></div><div class="rechts">{"".join(rechts)}</div></div>')
    elif typ == "kenntnisse":
        anzeige = abschnitt["anzeige"]
        for k in daten.sichtbare_kenntnisse(abschnitt):
            text = daten.kenntnis_text(abschnitt, k)
            rechts = ""
            if anzeige in ("punkte", "punkte_text") and k["stufe"] > 0:
                titel = f"{text} ({k['stufe']} von 5)" if text else f"{k['stufe']} von 5"
                punkte = "".join(f'<i style="--i:{i}"{" class=an" if i < k["stufe"] else ""}></i>' for i in range(5))
                rechts += f'<span class="punkte" role="img" aria-label="{_e(titel)}" title="{_e(titel)}">{punkte}</span>'
            if text and (anzeige != "punkte" or k["stufe"] == 0):
                rechts += f'<span class="stufe">{_e(text)}</span>'
            teile.append(f'<div class="zeile kenntnis erscheinen"><div class="links name">{_e(k["name"].strip())}</div>'
                         f'<div class="rechts">{rechts}</div></div>')
    elif typ == "liste":
        punkte = daten.listen_punkte(abschnitt)
        klasse = "aufzaehlung" if abschnitt["anzeige"] == "aufzaehlung" else "tags"
        teile.append(f'<ul class="{klasse} erscheinen">' + "".join(f"<li>{_e(p)}</li>" for p in punkte) + "</ul>")
    return "".join(teile)


def _json_ld(cv: dict) -> str:
    person = {"@context": "https://schema.org", "@type": "Person"}
    if cv["kopf"]["name"].strip():
        person["name"] = cv["kopf"]["name"].strip()
    if cv["kopf"]["beruf"].strip():
        person["jobTitle"] = cv["kopf"]["beruf"].strip()
    links = []
    for abschnitt in daten.sichtbare_abschnitte(cv):
        if abschnitt["typ"] != "persoenlich":
            continue
        for feld in daten.sichtbare_felder(abschnitt):
            art, ziel = daten.link_ziel(feld["label"], feld["wert"])
            if art == "mail":
                person.setdefault("email", feld["wert"].strip())
            elif art == "tel":
                person.setdefault("telephone", feld["wert"].strip())
            elif art == "web":
                links.append(ziel)
    if links:
        person["sameAs"] = links
    text = json.dumps(person, ensure_ascii=False)
    return text.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def erzeugen(cv: dict, live: bool = False, heute: _dt.date | None = None) -> str:
    """Erzeugt die komplette HTML-Seite. `live=True` fügt das automatische Neuladen
    für die Live-Vorschau hinzu."""
    kopf, des = cv["kopf"], cv["design"]
    name = kopf["name"].strip()
    akzent = "#" + design.lesbare_akzentfarbe(des["farbe"])
    akzent_dunkel = "#" + design.mischen(akzent, "FFFFFF", 0.45)
    variablen = {
        "--akzent": akzent,
        "--akzent-weich": "#" + design.mischen(akzent, "FFFFFF", 0.92),
        "--akzent-linie": "#" + design.mischen(akzent, "FFFFFF", 0.55),
        "--schrift": design.SCHRIFTEN.get(des["schrift"], design.SCHRIFTEN["Georgia"]),
        "--basis": f"{des['schriftgroesse'] * 1.42:.1f}px",
        "--basis-druck": f"{des['schriftgroesse']}pt",
        "--spalte": f"{des['spaltenbreite']}mm",
    }
    dunkel = {
        "--akzent": akzent_dunkel,
        "--akzent-weich": "#" + design.mischen(akzent_dunkel, "151B23", 0.86),
        "--akzent-linie": "#" + design.mischen(akzent_dunkel, "151B23", 0.55),
    }
    css_vars = ";".join(f"{k}:{v}" for k, v in variablen.items())
    css_dunkel = ";".join(f"{k}:{v}" for k, v in dunkel.items())
    # Gedruckt wird immer hell – auch wenn gerade der Dunkelmodus aktiv ist
    css_druck = ";".join(f"{k}:{variablen[k]}" for k in dunkel)

    abschnitte = daten.sichtbare_abschnitte(cv)
    navigation, inhalt = [], []
    for nr, abschnitt in enumerate(abschnitte, 1):
        titel = _e(abschnitt["titel"].strip())
        navigation.append(f'<a href="#abschnitt-{nr}">{titel}</a>')
        inhalt.append(
            f'<section class="abschnitt" id="abschnitt-{nr}">'
            f'<h2><button type="button" class="abschnitt-knopf" aria-expanded="true" aria-controls="inhalt-{nr}">'
            f'<span>{titel}</span><span class="pfeil" aria-hidden="true"></span></button></h2>'
            f'<div class="abschnitt-inhalt" id="inhalt-{nr}"><div class="innen">{_abschnitt_html(abschnitt)}</div></div>'
            "</section>")

    kopf_text = []
    if kopf["ueberschrift_zeigen"] and kopf["ueberschrift"].strip():
        kopf_text.append(f'<p class="ueberschrift">{_e(kopf["ueberschrift"].strip())}</p>')
    if name:
        kopf_text.append(f"<h1>{_e(name)}</h1>")
    if kopf["beruf"].strip():
        kopf_text.append(f'<p class="beruf">{_e(kopf["beruf"].strip())}</p>')
    foto = ""
    if kopf["foto"] and kopf["foto_zeigen"]:
        foto = (f'<img class="foto {_e(kopf["foto_form"])}" src="{bild.data_url(kopf["foto"])}" '
                f'alt="{_e("Foto von " + name if name else "Bewerbungsfoto")}">')

    unterschrift = ""
    if des["unterschrift_zeigen"]:
        ort_datum = ", ".join(t for t in (des["ort"].strip(), daten.datum_text(cv, heute)) if t)
        unterschrift = (f'<footer class="unterschrift erscheinen"><p>{_e(ort_datum)}</p>'
                        f'<div class="linie"></div><p class="name">{_e(name)}</p></footer>')

    titel = f"Lebenslauf – {name}" if name else "Lebenslauf"
    beschreibung = ", ".join(t for t in (f"Lebenslauf von {name}" if name else "Lebenslauf",
                                         kopf["beruf"].strip()) if t)
    return f"""<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_e(titel)}</title>
<meta name="description" content="{_e(beschreibung)}">
<meta name="generator" content="Lebenslauf-Generator">
<script>document.documentElement.classList.add('js');{_THEMA_FRUEH}{_LIVE_FRUEH if live else ''}</script>
<script type="application/ld+json">{_json_ld(cv)}</script>
<style>
:root{{{css_vars}}}
:root[data-thema="dunkel"]{{{css_dunkel}}}
@media print{{:root[data-thema="dunkel"]{{{css_druck}}}}}
{_CSS}
</style>
</head>
<body>
<div class="fortschritt" aria-hidden="true"><span></span></div>
<div class="werkzeuge" role="toolbar" aria-label="Ansicht">
  <button type="button" data-aktion="klappen" title="Alle Abschnitte ein- oder ausklappen">Alle zuklappen</button>
  <button type="button" data-aktion="thema" title="Hell/Dunkel umschalten" aria-label="Hell/Dunkel umschalten"><svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><circle cx="12" cy="12" r="8.5" fill="none" stroke="currentColor" stroke-width="2"/><path d="M12 3.5a8.5 8.5 0 0 1 0 17z" fill="currentColor"/></svg></button>
  <button type="button" data-aktion="drucken" title="Drucken oder als PDF speichern">Drucken / PDF</button>
</div>
<nav class="inhaltsnav" aria-label="Abschnitte">{''.join(navigation)}</nav>
<main class="blatt">
<header class="kopf erscheinen"><div class="kopf-text">{''.join(kopf_text)}</div>{foto}</header>
{''.join(inhalt)}
{unterschrift}
</main>
<button type="button" class="nach-oben" aria-label="Nach oben" title="Nach oben">↑</button>
<div class="toast" role="status" aria-live="polite"></div>
<script>{_JS}{_LIVE_JS if live else ''}</script>
</body>
</html>
"""


def exportieren(cv: dict, ziel: str) -> None:
    with open(ziel, "w", encoding="utf-8", newline="\n") as datei:
        datei.write(erzeugen(cv))


_THEMA_FRUEH = (
    "try{var t=localStorage.getItem('lebenslauf.thema');"
    "if(t==='dunkel'||(!t&&matchMedia('(prefers-color-scheme: dark)').matches))"
    "document.documentElement.dataset.thema='dunkel'}catch(e){}"
)

# Live-Vorschau: nach dem Neuladen keine Einblend-Animation und gleiche Scrollposition
_LIVE_FRUEH = "try{if(sessionStorage.getItem('lv-scroll')!==null)document.documentElement.classList.add('ohne-animation')}catch(e){}"

_LIVE_JS = """
(function(){
  var stand=null;
  try{var y=sessionStorage.getItem('lv-scroll');if(y!==null){sessionStorage.removeItem('lv-scroll');scrollTo(0,+y);}}catch(e){}
  function pruefen(){
    fetch('/version',{cache:'no-store'}).then(function(a){return a.text()}).then(function(v){
      if(stand===null)stand=v;
      else if(v!==stand){try{sessionStorage.setItem('lv-scroll',String(scrollY))}catch(e){}location.reload();return;}
      setTimeout(pruefen,600);
    }).catch(function(){setTimeout(pruefen,2000)});
  }
  pruefen();
})();
"""

_CSS = """
:root{--text:#222;--grau:#5f6368;--linie:#d0d4d9;--papier:#fff;--grund:#e9edf2;
  --schatten:0 1px 2px rgb(0 0 0/.06),0 16px 48px rgb(20 35 60/.14);color-scheme:light}
:root[data-thema="dunkel"]{--text:#e6e9ed;--grau:#a2abb6;--linie:#3a4450;--papier:#151b23;--grund:#0b0f14;
  --schatten:0 16px 48px rgb(0 0 0/.55);color-scheme:dark}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:var(--grund);color:var(--text);font:var(--basis)/1.55 var(--schrift);
  -webkit-font-smoothing:antialiased;transition:background-color .35s,color .35s}
.blatt{position:relative;max-width:210mm;margin:56px auto 96px;padding:18mm 20mm 20mm;background:var(--papier);
  box-shadow:var(--schatten);border-radius:6px;transition:background-color .35s}
.kopf{display:flex;align-items:center;justify-content:space-between;gap:24px;padding-bottom:14px;
  border-bottom:2px solid var(--akzent);margin-bottom:4px}
.ueberschrift{margin:0 0 6px;font-size:.8em;font-weight:700;letter-spacing:.26em;text-transform:uppercase;color:var(--akzent)}
h1{margin:0;font-size:2.35em;line-height:1.1;color:var(--akzent);letter-spacing:-.01em}
.beruf{margin:.35em 0 0;font-size:1.15em;color:var(--grau)}
.foto{flex:none;width:35mm;height:45mm;object-fit:cover;object-position:50% 30%;border-radius:4px;
  box-shadow:0 4px 14px rgb(0 0 0/.16);transition:transform .45s cubic-bezier(.2,.8,.2,1),box-shadow .45s}
.foto.rund{width:38mm;height:38mm;border-radius:50%}
.foto:hover{transform:scale(1.04) rotate(-1.2deg);box-shadow:0 12px 30px rgb(0 0 0/.25)}
.abschnitt{margin-top:22px}
.abschnitt h2{margin:0 0 8px;font-size:1.22em}
.abschnitt-knopf{all:unset;box-sizing:border-box;display:flex;width:100%;align-items:center;justify-content:space-between;
  gap:12px;padding:2px 0 4px;border-bottom:1px solid var(--akzent-linie);color:var(--akzent);font-weight:700;cursor:pointer}
.abschnitt-knopf:focus-visible{outline:2px solid var(--akzent);outline-offset:4px;border-radius:2px}
.pfeil{flex:none;width:.5em;height:.5em;border-right:2px solid currentColor;border-bottom:2px solid currentColor;
  transform:translateY(-25%) rotate(45deg);transition:transform .3s,opacity .2s;opacity:.45}
.abschnitt-knopf:hover .pfeil{opacity:1}
.zu .pfeil{transform:rotate(-45deg)}
.abschnitt-inhalt{display:grid;grid-template-rows:1fr;transition:grid-template-rows .4s ease}
.zu .abschnitt-inhalt{grid-template-rows:0fr}
.innen{min-height:0;overflow:hidden;padding:0 8px;margin:0 -8px}
.zeile{display:grid;grid-template-columns:var(--spalte) 1fr;column-gap:3mm;padding:3px 8px;margin:0 -8px;
  border-radius:6px;transition:background-color .2s}
.feld:hover,.kenntnis:hover{background:var(--akzent-weich)}
.eintrag{position:relative;padding-top:6px;padding-bottom:9px}
.eintrag::before{content:"";position:absolute;left:0;top:9px;bottom:9px;width:3px;border-radius:3px;
  background:var(--akzent);transform:scaleY(0);transition:transform .25s}
.eintrag:hover{background:var(--akzent-weich)}
.eintrag:hover::before{transform:scaleY(1)}
.links{color:var(--grau)}
.kenntnis .name{color:var(--text)}
.dauer{display:block;font-size:.8em;opacity:.85}
.dauer:empty{display:none}
.eintrag h3{margin:0;font-size:1em}
.unterzeile{margin:0;color:var(--grau);font-style:italic}
.rechts p{margin:.15em 0}
.rechts ul{margin:.2em 0 0;padding-left:1.15em}
.rechts li::marker,.aufzaehlung li::marker{color:var(--akzent)}
.fliesstext{margin:.2em 0 .5em;max-width:62em}
a{color:var(--akzent);text-decoration:none;background:linear-gradient(currentColor,currentColor) 0 100%/0 1px no-repeat;
  transition:background-size .25s}
a:hover,a:focus-visible{background-size:100% 1px}
.kopieren{margin-left:6px;padding:0 6px;border:1px solid var(--linie);border-radius:6px;background:var(--papier);
  color:var(--grau);font:inherit;font-size:.85em;line-height:1.5;cursor:pointer;opacity:0;transition:opacity .2s,color .2s,border-color .2s}
.feld:hover .kopieren,.kopieren:focus-visible{opacity:1}
.kopieren:hover{color:var(--akzent);border-color:var(--akzent)}
@media (hover:none){.kopieren{opacity:1}}
.punkte{display:inline-flex;gap:5px;margin-right:12px;vertical-align:-1px}
.punkte i{position:relative;width:.72em;height:.72em;border-radius:50%;background:var(--linie)}
.punkte i.an::after{content:"";position:absolute;inset:0;border-radius:50%;background:var(--akzent);
  transition:transform .4s cubic-bezier(.3,1.6,.5,1) calc(var(--i) * 90ms + 120ms)}
.js .kenntnis:not(.sichtbar) .punkte i.an::after{transform:scale(0)}
.stufe{color:var(--grau)}
.tags{list-style:none;margin:2px 0 0;padding:0;display:flex;flex-wrap:wrap;gap:7px}
.tags li{padding:2px 13px;border:1px solid var(--akzent-linie);border-radius:999px;cursor:default;
  transition:background-color .2s,color .2s,transform .2s}
.tags li:hover{background:var(--akzent);border-color:var(--akzent);color:var(--papier);transform:translateY(-2px)}
.aufzaehlung{margin:.2em 0;padding-left:1.15em}
.unterschrift{margin-top:42px}
.unterschrift p{margin:0}
.unterschrift .linie{width:62mm;border-bottom:1px solid var(--grau);margin:40px 0 4px}
.unterschrift .name{color:var(--grau);font-size:.9em}
.js .erscheinen{opacity:0;transform:translateY(14px);transition:opacity .6s ease,transform .6s cubic-bezier(.2,.8,.2,1)}
.js .erscheinen.sichtbar{opacity:1;transform:none}
.ohne-animation .erscheinen,.ohne-animation .punkte i.an::after{transition:none!important}
.fortschritt{position:fixed;inset:0 0 auto;height:3px;z-index:20}
.fortschritt span{display:block;height:100%;width:0;background:var(--akzent)}
.werkzeuge{position:fixed;top:12px;right:12px;z-index:20;display:flex;gap:6px;padding:5px;border-radius:12px;
  background:color-mix(in srgb,var(--papier) 82%,transparent);backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);
  box-shadow:0 2px 12px rgb(0 0 0/.12)}
.werkzeuge button,.nach-oben{display:inline-flex;align-items:center;justify-content:center;border:1px solid var(--linie);background:var(--papier);color:var(--text);border-radius:8px;
  padding:5px 12px;font:600 13px/1.4 system-ui,-apple-system,"Segoe UI",sans-serif;cursor:pointer;transition:border-color .2s,color .2s}
.werkzeuge button:hover,.nach-oben:hover{border-color:var(--akzent);color:var(--akzent)}
.nach-oben{position:fixed;right:18px;bottom:18px;z-index:20;width:42px;height:42px;padding:0;border-radius:50%;font-size:18px;
  box-shadow:0 2px 12px rgb(0 0 0/.15);opacity:0;pointer-events:none;transform:translateY(10px);transition:opacity .3s,transform .3s}
.nach-oben.da{opacity:1;pointer-events:auto;transform:none}
.inhaltsnav{display:none}
@media (min-width:1200px){
  .inhaltsnav{display:flex;flex-direction:column;gap:2px;position:fixed;top:120px;width:190px;
    left:max(16px,calc(50% - 105mm - 230px));font:14px/1.4 system-ui,-apple-system,"Segoe UI",sans-serif}
  .inhaltsnav a{padding:5px 12px;border-left:2px solid var(--linie);color:var(--grau);background:none;transition:color .2s,border-color .2s}
  .inhaltsnav a:hover{color:var(--text)}
  .inhaltsnav a.aktiv{color:var(--akzent);border-color:var(--akzent);font-weight:600}
}
.toast{position:fixed;left:50%;bottom:24px;z-index:30;padding:9px 18px;border-radius:999px;background:var(--text);color:var(--papier);
  font:600 14px/1.4 system-ui,-apple-system,"Segoe UI",sans-serif;transform:translate(-50%,20px);opacity:0;pointer-events:none;
  transition:opacity .3s,transform .3s}
.toast.da{opacity:1;transform:translate(-50%,0)}
@media (max-width:760px){
  .blatt{margin:0;padding:64px 18px 48px;border-radius:0;box-shadow:none}
  .kopf{flex-direction:column-reverse;align-items:flex-start}
  h1{font-size:1.9em}
  .zeile{grid-template-columns:1fr;row-gap:1px}
  .eintrag .links{font-size:.92em}
  .werkzeuge{left:12px;right:12px;justify-content:flex-end}
}
@media (prefers-reduced-motion:reduce){
  html{scroll-behavior:auto}
  *,*::before,*::after{transition:none!important;animation:none!important}
  .js .erscheinen{opacity:1;transform:none}
}
@media print{
  @page{size:A4;margin:16mm 20mm 16mm 20mm}
  :root,:root[data-thema="dunkel"]{--text:#222;--grau:#5f6368;--linie:#d0d4d9;--papier:#fff;--grund:#fff;color-scheme:light}
  body{font-size:var(--basis-druck);background:#fff;-webkit-print-color-adjust:exact;print-color-adjust:exact}
  .blatt{margin:0;padding:0;max-width:none;box-shadow:none;border-radius:0}
  .werkzeuge,.fortschritt,.inhaltsnav,.toast,.nach-oben,.kopieren,.dauer,.pfeil{display:none!important}
  .js .erscheinen{opacity:1!important;transform:none!important}
  .zu .abschnitt-inhalt{grid-template-rows:1fr}
  .zeile{break-inside:avoid}
  .abschnitt h2{break-after:avoid}
  .foto{box-shadow:none}
  .tags{display:block}
  .tags li{display:inline;border:0;padding:0}
  .tags li:not(:last-child)::after{content:", "}
  *,*::before,*::after{transition:none!important;animation:none!important}
  .js .kenntnis:not(.sichtbar) .punkte i.an::after{transform:none}
}
"""

_JS = r"""
(function(){
  'use strict';
  var wurzel=document.documentElement;
  function speichern(k,v){try{localStorage.setItem(k,v)}catch(e){}}

  // Einblenden beim Scrollen
  var elemente=[].slice.call(document.querySelectorAll('.erscheinen'));
  if('IntersectionObserver' in window&&!wurzel.classList.contains('ohne-animation')){
    var beobachter=new IntersectionObserver(function(eintraege){
      eintraege.forEach(function(e){if(e.isIntersecting){e.target.classList.add('sichtbar');beobachter.unobserve(e.target);}});
    },{rootMargin:'0px 0px -6% 0px'});
    document.querySelectorAll('.innen').forEach(function(innen){
      [].slice.call(innen.querySelectorAll('.erscheinen')).forEach(function(el,i){el.style.transitionDelay=Math.min(i,8)*55+'ms';});
    });
    elemente.forEach(function(el){beobachter.observe(el);});
  }else{
    elemente.forEach(function(el){el.classList.add('sichtbar');});
  }

  // Dauer der Stationen berechnen, z. B. "3 Jahre 2 Monate"
  var HEUTE=['heute','jetzt','aktuell','laufend','derzeit','present','now','today'];
  function monat(text){
    text=(text||'').trim().toLowerCase();
    if(HEUTE.indexOf(text)>=0){var d=new Date();return d.getFullYear()*12+d.getMonth();}
    var m=text.match(/^(\d{1,2})[.\/-](\d{4})$/);
    return m&&+m[1]>=1&&+m[1]<=12?+m[2]*12+(+m[1]-1):null;
  }
  document.querySelectorAll('.eintrag[data-von]').forEach(function(el){
    var von=monat(el.dataset.von),bis=monat(el.dataset.bis);
    if(von===null||bis===null||bis<von)return;
    var n=bis-von+1,j=Math.floor(n/12),m=n%12,teile=[];
    if(j)teile.push(j+(j===1?' Jahr':' Jahre'));
    if(m)teile.push(m+(m===1?' Monat':' Monate'));
    el.querySelector('.dauer').textContent=teile.join(' ');
  });

  // Abschnitte ein- und ausklappen
  var klappKnopf=document.querySelector('[data-aktion="klappen"]');
  function setzen(abschnitt,offen){
    abschnitt.classList.toggle('zu',!offen);
    abschnitt.querySelector('.abschnitt-knopf').setAttribute('aria-expanded',String(offen));
  }
  function klappKnopfAktualisieren(){
    var alleZu=!document.querySelector('.abschnitt:not(.zu)');
    if(klappKnopf)klappKnopf.textContent=alleZu?'Alle aufklappen':'Alle zuklappen';
  }
  document.querySelectorAll('.abschnitt-knopf').forEach(function(knopf){
    knopf.addEventListener('click',function(){
      var abschnitt=knopf.closest('.abschnitt');
      setzen(abschnitt,abschnitt.classList.contains('zu'));
      abschnitt.querySelectorAll('.erscheinen').forEach(function(el){el.classList.add('sichtbar');});
      klappKnopfAktualisieren();
    });
  });

  // Werkzeugleiste
  document.querySelector('.werkzeuge').addEventListener('click',function(ev){
    var knopf=ev.target.closest('button');if(!knopf)return;
    var aktion=knopf.dataset.aktion;
    if(aktion==='thema'){
      var neu=wurzel.dataset.thema==='dunkel'?'hell':'dunkel';
      wurzel.dataset.thema=neu;speichern('lebenslauf.thema',neu);
    }else if(aktion==='drucken'){
      window.print();
    }else if(aktion==='klappen'){
      var oeffnen=!document.querySelector('.abschnitt:not(.zu)');
      document.querySelectorAll('.abschnitt').forEach(function(a){setzen(a,oeffnen);});
      klappKnopfAktualisieren();
    }
  });

  // Kopieren von E-Mail und Telefon
  var toast=document.querySelector('.toast'),toastZeit;
  function melden(text){
    toast.textContent=text;toast.classList.add('da');
    clearTimeout(toastZeit);toastZeit=setTimeout(function(){toast.classList.remove('da');},2200);
  }
  function kopieren(text){
    if(navigator.clipboard&&window.isSecureContext)return navigator.clipboard.writeText(text);
    return new Promise(function(ok,fehler){
      var feld=document.createElement('textarea');feld.value=text;feld.setAttribute('readonly','');
      feld.style.position='fixed';feld.style.opacity='0';document.body.appendChild(feld);feld.select();
      var geklappt=false;try{geklappt=document.execCommand('copy');}catch(e){}
      feld.remove();geklappt?ok():fehler();
    });
  }
  document.querySelectorAll('.kopieren').forEach(function(knopf){
    knopf.addEventListener('click',function(){
      kopieren(knopf.dataset.kopieren).then(function(){melden(knopf.dataset.was+' kopiert ✓');},
        function(){melden('Kopieren nicht möglich');});
    });
  });

  // Lesefortschritt, Nach-oben-Knopf und aktive Navigation
  var balken=document.querySelector('.fortschritt span'),nachOben=document.querySelector('.nach-oben');
  var links=[].slice.call(document.querySelectorAll('.inhaltsnav a')),wartet=false;
  function scrollen(){
    wartet=false;
    var max=document.documentElement.scrollHeight-innerHeight;
    balken.style.width=(max>0?Math.min(100,scrollY/max*100):0)+'%';
    nachOben.classList.toggle('da',scrollY>400);
    var aktiv=null;
    links.forEach(function(a){var z=document.querySelector(a.getAttribute('href'));if(z&&z.getBoundingClientRect().top<innerHeight*0.35)aktiv=a;});
    links.forEach(function(a){a.classList.toggle('aktiv',a===aktiv);});
  }
  addEventListener('scroll',function(){if(!wartet){wartet=true;requestAnimationFrame(scrollen);}},{passive:true});
  addEventListener('resize',scrollen);
  nachOben.addEventListener('click',function(){scrollTo({top:0,behavior:'smooth'});});
  links.forEach(function(a){a.addEventListener('click',function(){
    var ziel=document.querySelector(a.getAttribute('href'));if(ziel&&ziel.classList.contains('zu'))setzen(ziel,true);
  });});
  scrollen();
})();
"""
