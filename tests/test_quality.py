# -*- coding: utf-8 -*-
"""Qualita' dell'analisi: llms.txt, JSON-LD, E-E-A-T, grafo link."""

import datetime

import requests

import seo_rrf_audit as sra


def _fetcher():
    return sra.Fetcher(delay=0.0, verbose=False)


def _fake_response(url, html_text):
    resp = requests.Response()
    resp.status_code = 200
    resp.url = url
    resp._content = html_text.encode("utf-8")
    resp.encoding = "utf-8"
    resp.elapsed = datetime.timedelta(0)
    return resp


# ---------------- llms.txt ----------------

def test_llms_txt_presente(site):
    finding = sra.check_llms_txt(site, _fetcher())
    assert finding.severity == sra.SEV_OK
    assert "llms.txt" in finding.title


def test_llms_txt_assente(competitor_site):
    finding = sra.check_llms_txt(competitor_site, _fetcher())
    assert finding.severity == sra.SEV_INFO
    assert "assente" in finding.title


# ---------------- lista crawler IA ----------------

def test_ai_crawlers_senza_bingbot_e_claude_web():
    assert "Bingbot" not in sra.AI_CRAWLERS
    assert "Claude-Web" not in sra.AI_CRAWLERS
    for token in ("GPTBot", "Claude-SearchBot", "Perplexity-User",
                  "Meta-ExternalAgent", "Amazonbot",
                  "MistralAI-User"):
        assert token in sra.AI_CRAWLERS


# ---------------- validazione JSON-LD ----------------

def test_jsonld_incompleto_segnalato():
    page = sra.Page(url="https://x.it/", status=200)
    page.jsonld_raw = [{"@type": "LocalBusiness", "name": "X"}]
    findings = sra.validate_jsonld([page])
    warn = [f for f in findings if f.severity == sra.SEV_WARNING]
    assert warn and "LocalBusiness" in warn[0].detail
    assert "address" in warn[0].detail
    assert "telephone" in warn[0].detail


def test_jsonld_completo_da_ok():
    page = sra.Page(url="https://x.it/", status=200)
    page.jsonld_raw = [{"@type": "WebSite", "name": "X",
                        "url": "https://x.it/"}]
    findings = sra.validate_jsonld([page])
    assert len(findings) == 1
    assert findings[0].severity == sra.SEV_OK


def test_faqpage_con_domande_incomplete():
    page = sra.Page(url="https://x.it/", status=200)
    page.jsonld_raw = [{
        "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": "Quanto costa?"},
            {"@type": "Question", "name": "Come funziona?",
             "acceptedAnswer": {"@type": "Answer",
                                "text": "Cosi'."}},
        ],
    }]
    findings = sra.validate_jsonld([page])
    faq = [f for f in findings if "FAQPage" in f.title]
    assert faq and "1 domanda" in faq[0].title


# ---------------- E-E-A-T ----------------

def test_eeat_tutti_i_segnali_presenti():
    html_text = """<!DOCTYPE html>
    <html lang="it"><head><meta charset="utf-8">
    <title>Chi siamo</title>
    <meta name="author" content="Paola Rossi">
    <meta property="article:published_time" content="2026-05-01">
    </head><body>
    <h1>Chi siamo</h1>
    <p>Il nostro team di fisioterapisti opera dal 2010 con
    formazione certificata e aggiornamento continuo.</p>
    <p><a href="tel:+390521123456">Chiamaci</a></p>
    </body></html>"""
    page = sra.parse_page("https://x.it/chi-siamo/",
                          _fake_response("https://x.it/chi-siamo/",
                                         html_text))
    assert page.author == "Paola Rossi"
    assert page.published == "2026-05-01"
    assert page.contact_links == 1
    findings = sra.audit_eeat([page])
    assert len(findings) == 4
    assert all(f.severity == sra.SEV_OK for f in findings)


def test_eeat_segnali_assenti():
    page = sra.Page(url="https://x.it/servizi/", status=200,
                    text="Elenco dei servizi offerti dal centro.")
    findings = sra.audit_eeat([page])
    assert len(findings) == 4
    assert all(f.severity == sra.SEV_WARNING for f in findings)
    titoli = " | ".join(f.title for f in findings)
    assert "autore" in titoli
    assert "chi siamo" in titoli


# ---------------- grafo dei link interni ----------------

def _pagina(url, targets=(), generic=0):
    page = sra.Page(url=url, status=200)
    page.internal_targets = [sra.norm_url(t) for t in targets]
    page.generic_anchors = generic
    return page


def test_grafo_orfane_profonde_e_anchor_generiche():
    base = "https://x.it/"
    pages = [
        _pagina("https://x.it/", ["https://x.it/a"], generic=2),
        _pagina("https://x.it/a", ["https://x.it/b"]),
        _pagina("https://x.it/b", ["https://x.it/c"]),
        _pagina("https://x.it/c", ["https://x.it/d"]),
        _pagina("https://x.it/d"),
        _pagina("https://x.it/orfana"),
    ]
    findings = sra._audit_link_graph(pages, base)
    titoli = " | ".join(f.title for f in findings)
    assert "orfane" in titoli
    assert any("orfana" in f.detail for f in findings)
    assert "oltre 3 click" in titoli
    assert "anchor generiche" in titoli


def test_grafo_sano_da_ok():
    base = "https://x.it/"
    pages = [
        _pagina("https://x.it/", ["https://x.it/a", "https://x.it/b"]),
        _pagina("https://x.it/a", ["https://x.it/"]),
        _pagina("https://x.it/b", ["https://x.it/a"]),
    ]
    findings = sra._audit_link_graph(pages, base)
    assert [f.severity for f in findings] == [sra.SEV_OK]


def test_anchor_generiche_riconosciute():
    for testo in ("Clicca qui", "leggi di più", "Read more", "QUI"):
        assert sra.GENERIC_ANCHOR_RE.match(testo), testo
    for testo in ("Scopri il servizio", "Guida al drenaggio"):
        assert not sra.GENERIC_ANCHOR_RE.match(testo), testo


# ---------------- installazione embedding rotta ----------------

def test_installazione_rotta_ripiega_su_tfidf(monkeypatch, capsys):
    """Un import che esplode (torch/numpy incompatibili) non deve
    propagare: si ripiega sul proxy dichiarandolo."""
    import sys as _sys
    import types

    rotto = types.ModuleType("sentence_transformers")

    def _boom(name):
        raise RuntimeError("ambiente rotto")

    rotto.__getattr__ = _boom
    monkeypatch.setitem(_sys.modules, "sentence_transformers", rotto)

    index = sra.VectorIndex(["primo documento", "secondo documento"],
                            model_name="qualunque")
    err = capsys.readouterr().err
    assert index.mode == "char-tfidf"
    assert "non utilizzabile" in err
    assert index.search("primo")


# ---------------- qualita' Schema.org: prezzi, media, rating ----------------

def _pagina_jsonld(*blocchi):
    page = sra.Page(url="https://x.it/", status=200)
    page.jsonld_raw = list(blocchi)
    return page


def test_offerta_con_prezzo_sporco_e_valuta_mancante():
    page = _pagina_jsonld({
        "@type": "Product", "name": "Pressoterapia",
        "offers": {"@type": "Offer", "price": "€ 50,00"},
    })
    findings = sra.validate_jsonld([page])
    titoli = " | ".join(f.title for f in findings)
    assert "prezzi delle offerte" in titoli
    dettagli = " | ".join(f.detail for f in findings)
    assert "non numerico" in dettagli
    assert "ISO 4217" in dettagli


def test_offerta_corretta_non_segnalata():
    page = _pagina_jsonld({
        "@type": "Product", "name": "Pressoterapia",
        "offers": {"@type": "Offer", "price": "50.00",
                   "priceCurrency": "EUR"},
    })
    findings = sra.validate_jsonld([page])
    assert not any("prezzi" in f.title for f in findings)


def test_product_senza_offerte_ne_giudizi():
    page = _pagina_jsonld({"@type": "Product", "name": "Kit"})
    findings = sra.validate_jsonld([page])
    assert any("senza offerte" in f.title for f in findings)


def test_video_senza_uploaddate_e_thumbnail_relativa():
    page = _pagina_jsonld({
        "@type": "VideoObject", "name": "Demo",
        "thumbnailUrl": "/img/demo.jpg",
    })
    findings = sra.validate_jsonld([page])
    dettagli = " | ".join(f.detail for f in findings)
    assert "VideoObject senza uploadDate" in dettagli
    assert any("non assoluti" in f.title for f in findings)


def test_rating_fuori_scala_e_senza_conteggio():
    page = _pagina_jsonld({
        "@type": "AggregateRating", "ratingValue": "6.2",
    })
    findings = sra.validate_jsonld([page])
    warn = [f for f in findings if "valutazion" in f.title]
    assert warn
    assert "fuori scala" in warn[0].detail
    assert "reviewCount" in warn[0].detail


def test_data_non_iso_segnalata():
    page = _pagina_jsonld({
        "@type": "Article", "headline": "T", "author": "A",
        "datePublished": "03/08/2026",
    })
    findings = sra.validate_jsonld([page])
    assert any("ISO 8601" in f.title for f in findings)


def test_evento_completo_e_coerente_da_ok():
    page = _pagina_jsonld({
        "@type": "Event", "name": "Open day",
        "startDate": "2026-09-12T10:00:00+02:00",
        "location": {"@type": "Place", "name": "Centro Linfa"},
        "image": "https://x.it/open-day.jpg",
    })
    findings = sra.validate_jsonld([page])
    assert len(findings) == 1
    assert findings[0].severity == sra.SEV_OK
    assert "coerente" in findings[0].title


# ---------------- piano di remediation ----------------

def test_build_remediation_ordina_per_gravita_e_peso():
    findings = [
        sra.Finding(sra.AREA_LEX, sra.SEV_WARNING, "w1", weight=1.0),
        sra.Finding(sra.AREA_TECH, sra.SEV_CRITICAL, "c1",
                    weight=1.0),
        sra.Finding(sra.AREA_SEM, sra.SEV_OK, "tutto bene"),
        sra.Finding(sra.AREA_SD, sra.SEV_CRITICAL, "c2", weight=3.0,
                    example="snippet"),
        sra.Finding(sra.AREA_RRF, sra.SEV_INFO, "nota"),
        sra.Finding(sra.AREA_LEX, sra.SEV_WARNING, "w2", weight=2.0),
    ]
    plan = sra.build_remediation(findings)
    assert [x["title"] for x in plan] == ["c2", "c1", "w2", "w1"]
    assert [x["priority"] for x in plan] == [1, 2, 3, 4]
    assert plan[0]["example"] == "snippet"


def test_rilievi_critici_portano_esempi():
    """I rilievi piu' comuni devono avere un esempio di fix."""
    page = sra.Page(url="https://x.it/pagina", status=200,
                    text="poco testo")
    findings = sra.audit_lexical([page])
    critici = [f for f in findings
               if f.severity == sra.SEV_CRITICAL and f.example]
    assert critici, "attesi esempi sui rilievi lessicali critici"


def test_eeat_warning_con_esempio():
    page = sra.Page(url="https://x.it/servizi/", status=200,
                    text="Elenco servizi.")
    findings = sra.audit_eeat([page])
    assert all(f.example for f in findings
               if f.severity == sra.SEV_WARNING)
