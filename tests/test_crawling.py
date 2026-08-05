# -*- coding: utf-8 -*-
"""Robustezza del crawling: redirect, soft-404, non-HTML, sitemap .gz."""

import mars_audit as sra


def _fetcher(**kw):
    kw.setdefault("delay", 0.0)
    kw.setdefault("verbose", False)
    return sra.Fetcher(**kw)


# ---------------- Content-Type non analizzabili ----------------

def test_pdf_corpo_non_scaricato(site):
    resp = _fetcher().get(site + "/doc.pdf")
    assert resp is not None
    assert resp.status_code == 200
    assert "pdf" in resp.headers["Content-Type"]
    assert resp.content == b""


def test_html_e_xml_restano_scaricati(site):
    fetcher = _fetcher()
    assert b"Centro Linfa" in fetcher.get(site + "/").content
    assert b"<urlset" in fetcher.get(site + "/sitemap.xml").content


# ---------------- redirect ----------------

def test_redirect_seguito_e_contato(site):
    resp = _fetcher().get(site + "/vecchia/")
    assert resp is not None and resp.status_code == 200
    page = sra.parse_page(site + "/vecchia/", resp)
    assert page.redirects == 1
    assert sra.norm_url(page.final_url) == \
        sra.norm_url(site + "/servizio-drenaggio/")


def test_rilievo_redirect_e_catena_multipla(site):
    resp = _fetcher().get(site + "/salto/")
    page = sra.parse_page(site + "/salto/", resp)
    assert page.redirects == 2
    titoli = [f.title for f in sra._audit_redirects([page])]
    assert any("rispondono con redirect" in t for t in titoli)
    assert any("catena di redirect multipla" in t for t in titoli)


def test_classificazione_http_https_e_www():
    misto = [
        sra.Page(url="http://esempio.it/a", status=200,
                 final_url="https://esempio.it/a", redirects=1),
        sra.Page(url="https://esempio.it/b", status=200,
                 final_url="https://www.esempio.it/b", redirects=1),
    ]
    titoli = [f.title for f in sra._audit_redirects(misto)]
    assert any("ancora in http" in t for t in titoli)
    assert any("www/non-www" in t for t in titoli)


def test_nessun_redirect_da_rilievo_ok(site):
    resp = _fetcher().get(site + "/")
    page = sra.parse_page(site + "/", resp)
    findings = sra._audit_redirects([page])
    assert [f.title for f in findings] == ["Nessun redirect interno"]
    assert findings[0].severity == sra.SEV_OK


# ---------------- soft-404 ----------------

def test_soft404_rilevata(site):
    resp = _fetcher().get(site + "/fantasma/")
    page = sra.parse_page(site + "/fantasma/", resp)
    assert page.ok, "la soft-404 risponde 200"
    findings = sra.audit_technical([page], site, True)
    assert any("soft-404" in f.title for f in findings)


def test_pagina_ricca_non_e_soft404(site):
    resp = _fetcher().get(site + "/servizio-drenaggio/")
    page = sra.parse_page(site + "/servizio-drenaggio/", resp)
    findings = sra.audit_technical([page], site, True)
    assert not any("soft-404" in f.title for f in findings)


# ---------------- sitemap .gz e lastmod ----------------

def test_sitemap_gz_decompressa_con_lastmod(site):
    coppie = sra.parse_sitemap(site + "/sitemap.xml.gz", _fetcher())
    assert len(coppie) == 3
    per_url = {loc: lastmod for loc, lastmod in coppie}
    assert per_url[site + "/sample-page/"] == ""
    assert per_url[site + "/servizio-drenaggio/"].startswith("2026-07")


def test_discover_urls_prioritizza_lastmod(site):
    fetcher = _fetcher()
    robots = sra.RobotsAudit(site, fetcher)
    robots.sitemaps = [site + "/sitemap.xml.gz"]
    urls, from_sitemap = sra.discover_urls(site, robots, fetcher, 10)
    assert from_sitemap
    assert urls[0] == site + "/servizio-drenaggio/"
    assert urls[-1] == site + "/sample-page/", \
        "senza lastmod si finisce in coda"


def test_sitemap_normale_conserva_l_ordine(site):
    fetcher = _fetcher()
    robots = sra.RobotsAudit(site, fetcher)
    robots.run()
    urls, from_sitemap = sra.discover_urls(site, robots, fetcher, 10)
    assert from_sitemap
    assert urls[0] == site + "/", \
        "senza lastmod l'ordine della sitemap resta invariato"
