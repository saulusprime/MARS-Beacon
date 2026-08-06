# -*- coding: utf-8 -*-
"""Applica un brand al bundle statico gui/ (white-label, P2).

Un unico file TOML per brand (vedi branding/) definisce token CSS,
logo, favicon, ragione sociale e (facoltativo) il footer completo.
Il tool genera gui/brand/brand.css, copia gli asset e riscrive le
regioni marcate <!-- brand:NOME inizio/fine --> di index.html e
tos.html. E' deterministico: stessa configurazione, stessi byte —
applicare il brand del repository su un albero pulito non produce
alcuna differenza (la suite lo verifica).

I contrasti WCAG AA delle coppie di colori realmente usate da
theme.css vengono verificati all'applicazione: un brand sotto la
soglia 4.5:1 viene rifiutato (uscita 2), perche' il bundle dichiara
la conformita' WCAG e non deve mentire.

Uso: python tools/brandizza.py branding/NOME.toml [--gui DIR]
"""
import argparse
import re
import shutil
import sys
from pathlib import Path

# Palette obbligatoria: chiave TOML -> custom property CSS.
TOKEN_CSS = {
    "teal": "--lt-teal",
    "teal_700": "--lt-teal-700",
    "teal_900": "--lt-teal-900",
    "navy": "--lt-navy",
    "navy_700": "--lt-navy-700",
    "gray_grave": "--lt-gray-grave",
    "aqua": "--lt-aqua",
    "aqua_soft": "--lt-aqua-soft",
    "mist": "--lt-mist",
    "orange": "--lt-orange",
    "orange_700": "--lt-orange-700",
    "ink": "--lt-ink",
    "ink_soft": "--lt-ink-soft",
    "border": "--lt-border",
}

CHIAVI_BRAND = {"nome", "sottonome", "ragione_sociale",
                "titolo_index", "anno", "copyright_dal"}

# Coppie (descrizione, testo, fondo) verificate a 4.5:1 (WCAG AA
# per testo normale). I grigi fissi sono quelli di theme.css
# (anagrafica, note e barra del footer scuro).
SOGLIA_CONTRASTO = 4.5
COPPIE_CONTRASTO = [
    ("bianco su teal (primario)", "#ffffff", "teal"),
    ("teal_700 su bianco (link)", "teal_700", "#ffffff"),
    ("bianco su teal_900 (footer)", "#ffffff", "teal_900"),
    ("aqua_soft su teal_900", "aqua_soft", "teal_900"),
    ("orange_700 su bianco", "orange_700", "#ffffff"),
    ("ink su bianco", "ink", "#ffffff"),
    ("ink_soft su bianco", "ink_soft", "#ffffff"),
    ("anagrafica #cdd8e4 su teal_900", "#cdd8e4", "teal_900"),
    ("note #aebfd0 su teal_900", "#aebfd0", "teal_900"),
    ("barra #aebfd0 su teal_700", "#aebfd0", "teal_700"),
]

TIPI_IMMAGINE = {".png": "image/png", ".svg": "image/svg+xml",
                 ".ico": "image/x-icon"}


class ErroreBrand(ValueError):
    """Errore d'uso: configurazione non valida (uscita 2)."""


def _luminanza(colore):
    """Luminanza relativa WCAG di un colore #rrggbb."""
    canali = []
    for i in (1, 3, 5):
        c = int(colore[i:i + 2], 16) / 255.0
        canali.append(c / 12.92 if c <= 0.04045
                      else ((c + 0.055) / 1.055) ** 2.4)
    r, g, b = canali
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrasto(testo, fondo):
    lt, lf = _luminanza(testo), _luminanza(fondo)
    chiaro, scuro = max(lt, lf), min(lt, lf)
    return (chiaro + 0.05) / (scuro + 0.05)


def carica_config(percorso: Path) -> dict:
    """Legge e valida il TOML di brand; solleva ErroreBrand."""
    try:
        import tomllib
    except ModuleNotFoundError:  # Python 3.10: ripiego dichiarato
        try:
            import tomli as tomllib  # type: ignore[no-redef]
        except ModuleNotFoundError:
            raise ErroreBrand(
                "serve Python >= 3.11 (modulo tomllib) oppure il "
                "pacchetto 'tomli' (pip install tomli).")
    try:
        with open(percorso, "rb") as handle:
            dati = tomllib.load(handle)
    except OSError as exc:
        raise ErroreBrand("impossibile leggere %s: %s"
                          % (percorso, exc))
    except tomllib.TOMLDecodeError as exc:
        raise ErroreBrand("TOML non valido in %s: %s"
                          % (percorso, exc))

    sconosciute = sorted(set(dati) - {"brand", "asset", "palette",
                                      "footer"})
    if sconosciute:
        raise ErroreBrand(
            "tabella sconosciuta: %s (previste [brand], [asset], "
            "[palette] e la facoltativa [footer])."
            % ", ".join(sconosciute))

    brand = dati.get("brand", {})
    extra = sorted(set(brand) - CHIAVI_BRAND)
    manca = sorted(CHIAVI_BRAND - set(brand))
    if extra:
        raise ErroreBrand("chiave sconosciuta in [brand]: %s"
                          % ", ".join(extra))
    if manca:
        raise ErroreBrand("chiave mancante in [brand]: %s"
                          % ", ".join(manca))
    for chiave in ("anno", "copyright_dal"):
        if not isinstance(brand[chiave], int):
            raise ErroreBrand("[brand] %s deve essere un intero."
                              % chiave)
    for chiave in CHIAVI_BRAND - {"anno", "copyright_dal"}:
        if not isinstance(brand[chiave], str) or not brand[chiave]:
            raise ErroreBrand("[brand] %s deve essere un testo "
                              "non vuoto." % chiave)

    asset = dati.get("asset", {})
    if sorted(asset) != ["favicon", "logo"]:
        raise ErroreBrand("[asset] richiede esattamente le chiavi "
                          "logo e favicon.")
    for chiave, valore in asset.items():
        suffisso = Path(str(valore)).suffix.lower()
        if suffisso not in TIPI_IMMAGINE:
            raise ErroreBrand(
                "[asset] %s: estensione %r non prevista (%s)."
                % (chiave, suffisso,
                   ", ".join(sorted(TIPI_IMMAGINE))))

    palette = dati.get("palette", {})
    extra = sorted(set(palette) - set(TOKEN_CSS))
    manca = sorted(set(TOKEN_CSS) - set(palette))
    if extra:
        raise ErroreBrand("colore sconosciuto in [palette]: %s"
                          % ", ".join(extra))
    if manca:
        raise ErroreBrand("colore mancante in [palette]: %s"
                          % ", ".join(manca))
    for chiave, valore in palette.items():
        if chiave == "border":
            continue  # stringa CSS libera (tipicamente rgba)
        if not re.fullmatch(r"#[0-9a-f]{6}", str(valore)):
            raise ErroreBrand(
                "[palette] %s: %r non e' un colore #rrggbb "
                "minuscolo." % (chiave, valore))

    footer = dati.get("footer", {})
    if footer:
        if sorted(footer) != ["frammento_html"]:
            raise ErroreBrand("[footer] prevede la sola chiave "
                              "frammento_html.")
        frammento = footer["frammento_html"]
        for atteso in ("<footer", "</footer>"):
            if atteso not in frammento:
                raise ErroreBrand(
                    "[footer] frammento_html senza %r: deve "
                    "essere l'elemento footer completo." % atteso)
        # Elementi facoltativi: la GUI li usa se ci sono (app.js
        # scrive le versioni in footer-info e aggiorna data-year),
        # ma un brand puo' legittimamente farne a meno.
        if 'id="footer-info"' not in frammento:
            print("avviso: [footer] senza id=\"footer-info\" — le "
                  "versioni non compariranno nel footer.",
                  file=sys.stderr)
        if "data-year" not in frammento:
            print("avviso: [footer] senza data-year — l'anno del "
                  "copyright non verra' aggiornato da app.js.",
                  file=sys.stderr)

    verifica_contrasti(palette)
    return dati


def verifica_contrasti(palette: dict) -> list:
    """Ritorna [(descrizione, rapporto)]; ErroreBrand se sotto
    soglia."""
    esiti = []
    for descrizione, testo, fondo in COPPIE_CONTRASTO:
        colore_testo = palette.get(testo, testo)
        colore_fondo = palette.get(fondo, fondo)
        rapporto = _contrasto(colore_testo, colore_fondo)
        if rapporto < SOGLIA_CONTRASTO:
            raise ErroreBrand(
                "contrasto insufficiente (%s): %.1f:1 con %s su "
                "%s, servono almeno %.1f:1."
                % (descrizione, rapporto, colore_testo,
                   colore_fondo, SOGLIA_CONTRASTO))
        esiti.append((descrizione, rapporto))
    return esiti


def genera_brand_css(config: dict, nome_config: str) -> str:
    """Il layer di token: gui/brand/brand.css (generato)."""
    palette = config["palette"]
    contrasti = "\n".join(
        "     %-32s %4.1f:1" % (descrizione, rapporto)
        for descrizione, rapporto in verifica_contrasti(palette))
    righe_token = "\n".join(
        "  %-18s %s;" % (TOKEN_CSS[chiave] + ":", palette[chiave])
        for chiave in TOKEN_CSS)
    teal = palette["teal"]
    rgb = ", ".join(str(int(teal[i:i + 2], 16)) for i in (1, 3, 5))
    font = ('  --bs-body-font-family: "Titillium Web", system-ui, '
            '-apple-system, Segoe UI, Roboto, sans-serif;')
    return """\
/* =====================================================================
   Token di BRAND del bundle — FILE GENERATO, non modificare a mano.
   Sorgente: branding/%s, applicata da tools/brandizza.py.
   La STRUTTURA (componenti, selettori .lt-*) vive in theme.css e
   consuma questi token via var(--lt-*): per cambiare brand si
   modifica il TOML e si riapplica il tool.
   Contrasti verificati all'applicazione (soglia %.1f:1):
%s
   ===================================================================== */

:root {
  /* --- Palette brand --- */
%s

  /* --- Override variabili Bootstrap Italia / Bootstrap 5 --- */
  --bs-primary: var(--lt-teal);
  --bs-primary-rgb: %s;
  --bs-link-color: var(--lt-teal-700);
  --bs-link-hover-color: var(--lt-teal-900);
  --bs-body-color: var(--lt-ink);
%s
  --bs-border-radius: .75rem;
  --bs-border-radius-lg: 1.25rem;

  /* Altezza header sticky, usata per lo scroll-margin delle ancore */
  --lt-header-h: 84px;
}
""" % (nome_config, SOGLIA_CONTRASTO, contrasti, righe_token, rgb,
       font)


def sostituisci_regione(testo, nome, contenuto, pagina):
    """Riscrive la regione fra i marcatori brand:NOME."""
    inizio = "<!-- brand:%s inizio -->" % nome
    fine = "<!-- brand:%s fine -->" % nome
    for marcatore in (inizio, fine):
        if testo.count(marcatore) != 1:
            raise ErroreBrand(
                "%s: marcatore %r assente o duplicato." %
                (pagina, marcatore))
    prima, resto = testo.split(inizio, 1)
    _, dopo = resto.split(fine, 1)
    return prima + inizio + contenuto + fine + dopo


def testata_html(config: dict) -> str:
    brand = config["brand"]
    return """
      <div class="lt-brand">
        <img class="lt-logo" src="brand/%s" alt=""
             aria-hidden="true">
        <span>
          <span class="lt-name d-block">%s</span>
          <span class="lt-tag d-block">%s</span>
        </span>
      </div>
      """ % (config["asset"]["logo"], brand["nome"],
             brand["sottonome"])


def testa_html(config: dict, titolo: str) -> str:
    favicon = config["asset"]["favicon"]
    tipo = TIPI_IMMAGINE[Path(favicon).suffix.lower()]
    return """
  <title>%s</title>
  <link rel="icon" type="%s" href="brand/%s">
  """ % (titolo, tipo, favicon)


def footer_html(config: dict) -> str:
    footer = config.get("footer", {})
    if footer:
        return "\n" + footer["frammento_html"].strip("\n") + "\n  "
    brand = config["brand"]
    if brand["copyright_dal"] == brand["anno"]:
        periodo = "<span data-year>%d</span>" % brand["anno"]
    else:
        periodo = ("%d–<span data-year>%d</span>"
                   % (brand["copyright_dal"], brand["anno"]))
    return """
  <footer class="lt-footer py-4">
    <div class="container small">
      <p class="mb-1">
        <span class="lt-name">%s</span>
      </p>
      <p class="mb-0">Copyright © %s %s</p>
    </div>
  </footer>
  """ % (brand["ragione_sociale"], periodo,
         brand["ragione_sociale"])


def applica(percorso_config: Path, gui: Path) -> list:
    """Applica il brand; ritorna l'elenco dei file scritti."""
    config = carica_config(percorso_config)
    if not (gui / "index.html").is_file():
        raise ErroreBrand("%s non sembra il bundle gui/ "
                          "(index.html assente)." % gui)
    scritti = []

    # Asset: nome semplice = gia' in gui/brand; con directory =
    # copiato dentro gui/brand (percorso relativo al TOML).
    for chiave in ("logo", "favicon"):
        valore = config["asset"][chiave]
        if "/" in valore:
            sorgente = (percorso_config.parent / valore).resolve()
            if not sorgente.is_file():
                raise ErroreBrand("[asset] %s: %s non esiste."
                                  % (chiave, sorgente))
            destinazione = gui / "brand" / Path(valore).name
            shutil.copyfile(sorgente, destinazione)
            config["asset"][chiave] = Path(valore).name
            scritti.append(destinazione)
        elif not (gui / "brand" / valore).is_file():
            raise ErroreBrand(
                "[asset] %s: %s non e' in gui/brand/ (usare un "
                "percorso relativo al TOML per copiarlo)."
                % (chiave, valore))

    percorso_css = gui / "brand" / "brand.css"
    percorso_css.write_text(
        genera_brand_css(config, percorso_config.name),
        encoding="utf-8")
    scritti.append(percorso_css)

    brand = config["brand"]
    pagine = {
        "index.html": (("testa",
                        testa_html(config, brand["titolo_index"])),
                       ("testata", testata_html(config)),
                       ("footer", footer_html(config))),
        "tos.html": (("testa",
                      testa_html(config, "Condizioni di servizio "
                                 "— MARS Beacon")),
                     ("testata", testata_html(config)),
                     ("ragione-sociale", brand["ragione_sociale"]),
                     ("footer", footer_html(config))),
    }
    for nome_pagina, regioni in pagine.items():
        pagina = gui / nome_pagina
        testo = pagina.read_text(encoding="utf-8")
        for nome_regione, contenuto in regioni:
            testo = sostituisci_regione(testo, nome_regione,
                                        contenuto, nome_pagina)
        pagina.write_text(testo, encoding="utf-8")
        scritti.append(pagina)
    return scritti


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="brandizza.py",
        description="Applica un brand TOML al bundle statico "
                    "della GUI (white-label).")
    parser.add_argument("config", help="file TOML del brand "
                        "(vedi branding/)")
    parser.add_argument("--gui", default=None, metavar="DIR",
                        help="bundle da brandizzare (default: la "
                        "gui/ del repository)")
    argomenti = parser.parse_args(argv)
    gui = (Path(argomenti.gui) if argomenti.gui
           else Path(__file__).resolve().parents[1] / "gui")
    try:
        scritti = applica(Path(argomenti.config), gui)
    except ErroreBrand as exc:
        print("brandizza: %s" % exc, file=sys.stderr)
        return 2
    for percorso in scritti:
        print("scritto %s" % percorso)
    return 0


if __name__ == "__main__":
    sys.exit(main())
