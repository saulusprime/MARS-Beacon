# -*- coding: utf-8 -*-
"""i18n completa dei rilievi: catalogo EN, resolver, renderer."""

import seo_rrf_audit as sra


class _Zero(dict):
    """Dict che risponde 0 a ogni chiave: valida i template."""

    def __missing__(self, key):
        return 0


def test_template_en_formattabili():
    """Ogni template del catalogo deve formattare senza errori."""
    for key, entry in sra._FINDINGS_EN.items():
        for field, template in entry.items():
            try:
                template % _Zero()
            except (ValueError, TypeError) as exc:
                raise AssertionError(
                    "template %s.%s malformato: %s"
                    % (key, field, exc))


def test_fallback_su_chiave_o_parametri_mancanti():
    senza_chiave = sra.Finding(sra.AREA_LEX, sra.SEV_OK, "Titolo it")
    assert sra.finding_texts(senza_chiave, "en")["title"] == \
        "Titolo it"
    chiave_ignota = sra.Finding(sra.AREA_LEX, sra.SEV_OK,
                                "Titolo it", key="non.esiste")
    assert sra.finding_texts(chiave_ignota, "en")["title"] == \
        "Titolo it"
    # parametri incoerenti col template: resta l'italiano, campo
    # per campo, senza eccezioni
    rotto = sra.Finding(sra.AREA_LEX, sra.SEV_WARNING,
                        "2 title duplicati fra pagine",
                        key="lex.title.dup", params={})
    testi = sra.finding_texts(rotto, "en")
    assert testi["title"] == "2 title duplicati fra pagine"


def test_resolver_su_voci_del_piano():
    item = {"title": "Sito non in HTTPS", "fix": "f", "example": "",
            "key": "tech.https.missing", "params": {}}
    assert sra.finding_texts(item, "en")["title"] == \
        "Site not on HTTPS"
    assert sra.finding_texts(item, "it")["title"] == \
        "Sito non in HTTPS"


def test_audit_reale_tutto_tradotto(site):
    """Sul sito fixture ogni rilievo ha chiave e traduzione."""
    pages, findings, scores, results, mode, _ = sra.run_audit(
        base=site, max_pages=10, queries=[], model_name="none",
        delay=0.0, k=60, verbose=False)
    assert findings
    for f in findings:
        assert f.key, "rilievo senza chiave i18n: %r" % f.title
        en = sra.finding_texts(f, "en")["title"]
        assert en != f.title, \
            "titolo non tradotto (fallback?): %r" % f.title

    for render in (sra.render_text, sra.render_markdown,
                   sra.render_csv, sra.render_html):
        out = render(site, pages, findings, scores, results, mode,
                     60, lang="en")
        assert "Piano di remediation" not in out
        assert "Rilievi per area" not in out
        out_it = render(site, pages, findings, scores, results,
                        mode, 60)
        assert "Remediation plan" not in out_it


def test_csv_intestazioni_en():
    out = sra.render_csv("https://x.it", [], [], {}, [], "x", 60,
                         lang="en")
    assert out.lstrip("﻿").startswith(
        "site;area;severity;weight;title")
