# -*- coding: utf-8 -*-
"""Rendering JavaScript: euristica, passata di rendering, integrazione."""

import os

import pytest

import mars_audit as sra

RENDERED_HTML = """<!DOCTYPE html>
<html lang="it"><head><title>Drenaggio SPA - guida</title></head>
<body><h1>Drenaggio linfatico renderizzato</h1>
<p>Contenuto generato lato client con molte parole utili sul
drenaggio linfatico manuale, adesso visibile all'analisi.</p>
</body></html>"""


def _patch(monkeypatch, name, value):
    """Monkeypatch sulla facciata e su ogni modulo marsbeacon che
    espone il nome: dopo la scomposizione (v1.58.0) conta il
    namespace del consumatore, non solo quello pubblico."""
    import mars_audit
    import marsbeacon.audits
    import marsbeacon.base
    import marsbeacon.crawler
    import marsbeacon.i18n
    import marsbeacon.indexes
    import marsbeacon.render
    for modulo in (mars_audit, marsbeacon.base, marsbeacon.crawler,
                   marsbeacon.indexes, marsbeacon.audits,
                   marsbeacon.render, marsbeacon.i18n):
        if name in vars(modulo):
            monkeypatch.setattr(modulo, name, value)


class StubRenderer:
    """Sostituto di PageRenderer: nessun browser, HTML canned."""

    ultimo = None

    def __init__(self, **kwargs):
        StubRenderer.ultimo = self
        self.urls = []
        self.risposta = RENDERED_HTML

    def render(self, url):
        self.urls.append(url)
        return self.risposta

    def close(self):
        pass


def _page(url, words, script_ratio):
    page = sra.Page(url=url, status=200)
    page.html_bytes = 1000
    page.word_count = words
    page.script_bytes = int(1000 * script_ratio)
    page.title = "Caricamento..."
    return page


def test_is_js_heavy():
    assert sra.is_js_heavy(_page("http://x/a", 10, 0.8))
    assert not sra.is_js_heavy(_page("http://x/b", 500, 0.8))
    assert not sra.is_js_heavy(_page("http://x/c", 10, 0.1))


def test_auto_rende_solo_le_pagine_client_side(monkeypatch):
    _patch(monkeypatch, "PageRenderer", StubRenderer)
    normale = _page("http://x/normale", 500, 0.1)
    spa = _page("http://x/spa", 10, 0.8)
    pages, rese, fallite = sra.apply_rendering(
        [normale, spa], sra.RENDER_AUTO, delay=0, verbose=False)
    assert (rese, fallite) == (1, 0)
    assert StubRenderer.ultimo.urls == ["http://x/spa"]
    assert pages[0] is normale and not pages[0].rendered
    assert pages[1].rendered and pages[1].raw_js_heavy
    assert pages[1].title == "Drenaggio SPA - guida"
    assert pages[1].word_count > 10
    assert pages[1].status == 200


def test_always_rende_tutte_le_pagine_ok(monkeypatch):
    _patch(monkeypatch, "PageRenderer", StubRenderer)
    rotta = sra.Page(url="http://x/errore", error="richiesta fallita")
    pages, rese, _ = sra.apply_rendering(
        [_page("http://x/a", 500, 0.1), rotta,
         _page("http://x/b", 10, 0.8)],
        sra.RENDER_ALWAYS, delay=0, verbose=False)
    assert rese == 2
    assert pages[0].rendered and pages[2].rendered
    assert not pages[1].rendered, "le pagine in errore non si rendono"
    assert not pages[0].raw_js_heavy and pages[2].raw_js_heavy


def test_rendering_fallito_conserva_html_statico(monkeypatch):
    class StubRotto(StubRenderer):
        def render(self, url):
            return None

    _patch(monkeypatch, "PageRenderer", StubRotto)
    spa = _page("http://x/spa", 10, 0.8)
    pages, rese, fallite = sra.apply_rendering(
        [spa], sra.RENDER_AUTO, delay=0, verbose=False)
    assert (rese, fallite) == (0, 1)
    assert pages[0] is spa and not pages[0].rendered


def test_off_non_tocca_nulla(monkeypatch):
    def esplode(**kwargs):
        raise AssertionError("PageRenderer non va istanziato con off")

    _patch(monkeypatch, "PageRenderer", esplode)
    spa = _page("http://x/spa", 10, 0.8)
    pages, rese, fallite = sra.apply_rendering(
        [spa], sra.RENDER_OFF, delay=0, verbose=False)
    assert (rese, fallite) == (0, 0) and pages[0] is spa


def test_rilievo_js_heavy_scatta_anche_dopo_il_rendering():
    reso = _page("http://x/spa", 300, 0.05)
    reso.rendered = True
    reso.raw_js_heavy = True
    findings = sra.audit_technical([reso], "http://x", True)
    js = [f for f in findings
          if "molto JavaScript" in f.title]
    assert js and js[0].severity == sra.SEV_CRITICAL
    assert "non eseguono JavaScript" in js[0].detail


def test_cli_render_e_scelte():
    args = sra.build_parser().parse_args(["x.it", "--render", "auto"])
    assert args.render == sra.RENDER_AUTO
    assert sra.build_parser().parse_args(["x.it"]).render == \
        sra.RENDER_OFF
    with pytest.raises(SystemExit):
        sra.build_parser().parse_args(["x.it", "--render", "js"])


def test_gui_valida_render():
    import mars_gui as gui
    config, err = gui.validate_config(
        {"url": "x.it", "render": "auto"})
    assert err == "" and config["render"] == "auto"
    config, err = gui.validate_config(
        {"url": "x.it", "render": "sempre"})
    assert config is None and "render" in err
    config, _ = gui.validate_config({"url": "x.it"})
    assert config["render"] == "off"


CHROME_DISPONIBILE = any(os.path.exists(p) for p in sra.CHROME_PATHS)


@pytest.mark.skipif(not CHROME_DISPONIBILE,
                    reason="nessun Chrome/Chromium di sistema")
def test_integrazione_rendering_reale(site):
    pytest.importorskip("playwright")
    fetcher = sra.Fetcher(delay=0.0, verbose=False)
    resp = fetcher.get(site + "/spa/")
    statica = sra.parse_page(site + "/spa/", resp)
    assert sra.is_js_heavy(statica), \
        "la fixture SPA deve risultare client-side all'euristica"
    assert "renderizzato" not in statica.text

    pages, rese, fallite = sra.apply_rendering(
        [statica], sra.RENDER_AUTO, delay=0, verbose=False)
    assert (rese, fallite) == (1, 0)
    resa = pages[0]
    assert resa.rendered and resa.raw_js_heavy
    assert "Drenaggio SPA" in resa.title
    assert "renderizzato dal browser" in resa.text
    assert resa.chunks, "il contenuto renderizzato produce chunk"
