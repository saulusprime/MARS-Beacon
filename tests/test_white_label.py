# -*- coding: utf-8 -*-
"""White-label (P2): tools/brandizza.py e i brand in branding/.

Il contratto: un TOML per brand, applicazione deterministica al
bundle statico. Il repository DEVE coincidere col brand Lympha
applicato (idempotenza); il brand generico MARS Beacon non deve
lasciare alcuna traccia di Lympha nelle pagine; una configurazione
sotto soglia di contrasto o malformata viene rifiutata in italiano.
"""

import os
import shutil
import subprocess
import sys

RADICE = os.path.join(os.path.dirname(__file__), os.pardir)
GUI = os.path.join(RADICE, "gui")
TOOL = os.path.join(RADICE, "tools", "brandizza.py")
BRAND_LYMPHA = os.path.join(RADICE, "branding",
                            "lympha-technologies.toml")
BRAND_MARS = os.path.join(RADICE, "branding", "mars-beacon.toml")

# Le pagine del bundle (GUI a momenti distinti, P5) e i file che
# il tool riscrive (confronti byte per byte).
PAGINE = ("index.html", "accesso.html", "configurazione.html",
          "scansione.html", "tos.html")
RISCRITTI = PAGINE + (os.path.join("brand", "brand.css"),)


def _bundle(tmp_path):
    """Copia ridotta del bundle: le pagine e gli asset di brand."""
    destinazione = os.path.join(str(tmp_path), "gui")
    os.makedirs(destinazione)
    for nome in PAGINE:
        shutil.copy(os.path.join(GUI, nome), destinazione)
    shutil.copytree(os.path.join(GUI, "brand"),
                    os.path.join(destinazione, "brand"))
    return destinazione


def _applica(config, gui_dir):
    return subprocess.run(
        [sys.executable, TOOL, config, "--gui", gui_dir],
        capture_output=True, text=True)


def _leggi(base, nome):
    with open(os.path.join(base, nome), encoding="utf-8") as fh:
        return fh.read()


def test_il_repo_coincide_col_brand_lympha(tmp_path):
    """Idempotenza: applicare il brand del repository non deve
    cambiare un byte (gui/ E' lympha-technologies.toml applicato)."""
    bundle = _bundle(tmp_path)
    esito = _applica(BRAND_LYMPHA, bundle)
    assert esito.returncode == 0, esito.stderr
    for nome in RISCRITTI:
        assert _leggi(bundle, nome) == _leggi(GUI, nome), nome


def test_brand_generico_senza_tracce_lympha(tmp_path):
    bundle = _bundle(tmp_path)
    esito = _applica(BRAND_MARS, bundle)
    assert esito.returncode == 0, esito.stderr
    for nome in PAGINE:
        pagina = _leggi(bundle, nome)
        assert "Lympha" not in pagina, nome
        assert "lymphatech" not in pagina, nome
        # regioni ancora marcate: il bundle resta ri-brandizzabile
        for regione in ("testa", "testata", "footer"):
            assert "<!-- brand:%s inizio -->" % regione in pagina
        # niente footer-info: il footer minimo non mostra le
        # versioni (facoltativo dalla v2.39.0), l'anno resta
        assert 'id="footer-info"' not in pagina
        assert "data-year" in pagina
        assert 'href="brand/mars-logo.png"' in pagina  # favicon
    css = _leggi(bundle, os.path.join("brand", "brand.css"))
    assert "--lt-teal:         #4a5568;" in css
    assert "mars-beacon.toml" in css  # sorgente dichiarata
    # copyright_dal == anno: un anno solo, niente intervallo
    assert "2026–<span data-year>" not in _leggi(bundle,
                                                 "index.html")


def test_andata_e_ritorno_deterministici(tmp_path):
    """mars -> lympha riporta il bundle esattamente al repo."""
    bundle = _bundle(tmp_path)
    assert _applica(BRAND_MARS, bundle).returncode == 0
    assert _applica(BRAND_LYMPHA, bundle).returncode == 0
    for nome in RISCRITTI:
        assert _leggi(bundle, nome) == _leggi(GUI, nome), nome


def test_contrasto_insufficiente_respinto(tmp_path):
    bundle = _bundle(tmp_path)
    with open(BRAND_MARS, encoding="utf-8") as fh:
        testo = fh.read()
    config = os.path.join(str(tmp_path), "chiaro.toml")
    with open(config, "w", encoding="utf-8") as fh:
        fh.write(testo.replace('"#4a5568"', '"#eeeeee"'))
    esito = _applica(config, bundle)
    assert esito.returncode == 2
    assert "contrasto insufficiente" in esito.stderr
    assert "4.5" in esito.stderr  # la soglia e' dichiarata


def test_tabella_sconosciuta_respinta(tmp_path):
    bundle = _bundle(tmp_path)
    with open(BRAND_MARS, encoding="utf-8") as fh:
        testo = fh.read()
    config = os.path.join(str(tmp_path), "estranea.toml")
    with open(config, "w", encoding="utf-8") as fh:
        fh.write(testo + '\n[extra]\nchiave = "x"\n')
    esito = _applica(config, bundle)
    assert esito.returncode == 2
    assert "sconosciuta" in esito.stderr


def test_frammento_footer_senza_elementi_facoltativi(tmp_path):
    """footer-info e data-year sono facoltativi (dalla v2.39.0):
    il brand si applica, con avviso — app.js tollera l'assenza."""
    bundle = _bundle(tmp_path)
    with open(BRAND_LYMPHA, encoding="utf-8") as fh:
        testo = fh.read()
    config = os.path.join(str(tmp_path), "senza-anno.toml")
    with open(config, "w", encoding="utf-8") as fh:
        fh.write(testo.replace("data-year", "data-anno"))
    esito = _applica(config, bundle)
    assert esito.returncode == 0, esito.stderr
    assert "avviso" in esito.stderr
    assert "data-year" in esito.stderr


def test_frammento_footer_non_strutturale_respinto(tmp_path):
    """Il frammento deve restare l'elemento footer completo."""
    bundle = _bundle(tmp_path)
    with open(BRAND_LYMPHA, encoding="utf-8") as fh:
        testo = fh.read()
    config = os.path.join(str(tmp_path), "monco.toml")
    with open(config, "w", encoding="utf-8") as fh:
        fh.write(testo.replace("</footer>", "</footre>"))
    esito = _applica(config, bundle)
    assert esito.returncode == 2
    assert "footer completo" in esito.stderr
