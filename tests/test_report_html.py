# -*- coding: utf-8 -*-
"""Referto HTML: ancore per rilievo, CSS di stampa, lingua cornice."""

import mars_audit as sra


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


def _findings():
    return [
        sra.Finding(sra.AREA_TECH, sra.SEV_CRITICAL,
                    "3 pagine non raggiungibili", detail="d",
                    fix="f"),
        sra.Finding(sra.AREA_LEX, sra.SEV_WARNING,
                    "2 title non ottimizzati"),
    ]


def _render(lang=None):
    scores = {sra.AREA_TECH: 55.0, sra.AREA_LEX: 80.0,
              sra.AREA_SEM: None, sra.AREA_SD: None,
              sra.AREA_RRF: None}
    kwargs = {} if lang is None else {"lang": lang}
    return sra.render_html("https://x.it", [], _findings(), scores,
                           [], "char-tfidf", 60, **kwargs)


def test_ancora_stabile_e_dedup():
    seen = {}
    a = sra._finding_anchor(sra.AREA_TECH,
                            "3 pagine non raggiungibili", seen)
    b = sra._finding_anchor(sra.AREA_TECH,
                            "7 pagine non raggiungibili", {})
    assert a == b, "i conteggi non devono cambiare l'ancora"
    assert a.startswith("r-tecnica-")
    # duplicato nello stesso referto: suffisso progressivo
    c = sra._finding_anchor(sra.AREA_TECH,
                            "3 pagine non raggiungibili", seen)
    assert c == a + "-2"


def test_referto_con_ancore_e_link():
    out = _render()
    slug = sra._finding_anchor(sra.AREA_TECH,
                               "3 pagine non raggiungibili", {})
    assert "id=\"%s\"" % slug in out
    # link dal piano di remediation (e/o dai top rilievi) all'ancora
    assert "class=\"rlink\" href=\"#%s\"" % slug in out
    # ancora-permalink accanto al titolo del rilievo
    assert "class=\"anchor\" href=\"#%s\"" % slug in out


def test_css_di_stampa_presente():
    out = _render()
    assert "@media print" in out
    assert "@page" in out
    assert "print-color-adjust" in out


def test_lingua_default_italiana_invariata():
    out = _render()
    assert "<html lang=\"it\">" in out
    assert "Piano di remediation" in out
    assert "Rilievi" in out or "Top rilievi" in out
    assert "Report in English" not in out


def test_lingua_en_cornice_e_nota_dichiarata():
    out = _render(lang="en")
    assert "<html lang=\"en\">" in out
    assert "Remediation plan" in out
    assert "Top findings" in out
    assert "Technical" in out and "Lexical (BM25)" in out
    # nota di onesta': le evidenze del sito restano nella sua lingua
    assert "Report in English" in out


def test_lingua_fr_cornice_e_nota_dichiarata():
    out = _render(lang="fr")
    assert "<html lang=\"fr\">" in out
    assert "Plan de remédiation" in out
    assert "Principaux constats" in out
    assert "Technique" in out and "Lexicale (BM25)" in out
    assert "Rapport en français" in out


def test_cataloghi_html_stesse_chiavi_tutte_le_lingue():
    it = set(sra._HTML_I18N["it"])
    assert set(sra._HTML_I18N) == set(sra.HTML_LANGS)
    for lingua in sra.HTML_LANGS:
        assert set(sra._HTML_I18N[lingua]) == it, lingua


def test_cli_lang_scelte():
    parser = sra.build_parser()
    assert parser.parse_args(["x.it"]).lang == "it"
    assert parser.parse_args(["x.it", "--lang", "en"]).lang == "en"
    for lingua in ("fr", "de", "es"):
        assert parser.parse_args(
            ["x.it", "--lang", lingua]).lang == lingua


# ------------- treemap e interattivita' (v1.53.0) -----------------

def test_squarify_riempie_l_area():
    rects = sra._squarify([6.0, 3.0, 1.0], 0, 0, 100, 50)
    assert len(rects) == 3
    area = sum(w * h for _x, _y, w, h in rects)
    assert abs(area - 5000) < 0.01
    for x, y, w, h in rects:
        assert x >= -0.01 and y >= -0.01
        assert x + w <= 100.01 and y + h <= 50.01
    x, y, w, h = rects[0]  # proporzionalita': 6/10 dell'area
    assert abs(w * h - 3000) < 0.01
    assert sra._squarify([], 0, 0, 10, 10) == []


def test_treemap_data_gravita_e_soglie():
    pages = [
        sra.Page(url="https://x.it/", status=200, word_count=600),
        sra.Page(url="https://x.it/a", status=200, word_count=300),
        sra.Page(url="https://x.it/b", status=200, word_count=100),
    ]
    findings = [
        sra.Finding(sra.AREA_LEX, sra.SEV_CRITICAL, "t",
                    url="https://x.it/a"),
        sra.Finding(sra.AREA_LEX, sra.SEV_WARNING, "t2",
                    url="https://x.it/b"),
        sra.Finding(sra.AREA_TECH, sra.SEV_CRITICAL, "di sito"),
    ]
    tmap = sra.treemap_data(pages, findings)
    per_url = {i["url"]: i for i in tmap["items"]}
    assert per_url["https://x.it/"]["severity"] == "ok"
    assert per_url["https://x.it/a"]["severity"] == "critical"
    assert per_url["https://x.it/b"]["severity"] == "warning"
    assert tmap["shown"] == 3 and tmap["total"] == 3
    # con una sola pagina il widget non esiste
    assert sra.treemap_data([pages[0]], []) is None


def test_referto_con_treemap_grafo_e_script():
    home = sra.Page(url="https://x.it/", status=200,
                    word_count=500)
    a = sra.Page(url="https://x.it/a", status=200, word_count=300)
    b = sra.Page(url="https://x.it/b", status=200, word_count=200)
    home.internal_targets = [sra.norm_url("https://x.it/a"),
                             sra.norm_url("https://x.it/b")]
    a.internal_targets = [sra.norm_url("https://x.it/b")]
    out = sra.render_html("https://x.it/", [home, a, b], [], {},
                          [], "char-tfidf")
    # treemap: svg, rettangoli focusabili, tabella di fallback
    assert "tm-svg" in out and "tm-rect" in out
    assert "tabindex=\"0\"" in out
    assert "<details>" in out
    # grafo: id, attributi data-* e controlli zoom
    assert "lg-svg" in out and "data-s=" in out
    assert "class=\"lg-node\"" in out and "data-i=" in out
    assert "id=\"lg-zin\"" in out
    # motore evoluto (v1.59.0): frecce, profondita' nei dati,
    # viste commutabili e legenda
    assert "marker-end=\"url(#lg-arr)\"" in out
    assert "data-depth=" in out and "data-r=" in out
    assert "id=\"lg-vanelli\"" in out
    assert "aria-pressed=\"true\"" in out
    assert "Legenda:" in out
    # script inline autonomo in coda, prima di </body>
    assert "<script>" in out and "querySelectorAll" in out
    assert out.rstrip().endswith("</html>")


# ------------- brand incorporato nel referto (v1.57.0) ------------

def test_brand_incorporato_e_fallback(monkeypatch):
    out = sra.render_html("https://x.it/", [], [], {}, [],
                          "char-tfidf")
    # Font e logo incorporati quando gli asset del repo ci sono.
    assert "@font-face" in out
    assert out.count("data:font/woff2;base64,") == 2
    assert "<svg class=\"logo-mark\"" in out
    assert "Lympha Technologies S.r.l." in out
    # Script distribuito da solo (asset assenti): fallback pulito,
    # firma testuale e font di sistema, mai un incorporo parziale.
    _patch(monkeypatch, "BRAND_DIR", "/non/esiste")
    _patch(monkeypatch, "FONTS_DIR", "/non/esiste")
    solo = sra.render_html("https://x.it/", [], [], {}, [],
                           "char-tfidf")
    assert "@font-face" not in solo
    assert "<svg class=\"logo-mark\"" not in solo
    assert "Lympha Technologies S.r.l." in solo
