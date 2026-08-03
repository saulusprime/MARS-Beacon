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
