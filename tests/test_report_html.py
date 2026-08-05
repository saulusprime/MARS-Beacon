# -*- coding: utf-8 -*-
"""Referto HTML: ancore per rilievo, CSS di stampa, lingua cornice."""

import seo_rrf_audit as sra


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


def test_cataloghi_it_en_stesse_chiavi():
    it = set(sra._HTML_I18N["it"])
    en = set(sra._HTML_I18N["en"])
    assert it == en


def test_cli_lang_scelte():
    parser = sra.build_parser()
    assert parser.parse_args(["x.it"]).lang == "it"
    assert parser.parse_args(["x.it", "--lang", "en"]).lang == "en"
