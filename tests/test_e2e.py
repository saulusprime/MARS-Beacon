# -*- coding: utf-8 -*-
"""End-to-end: run_audit sul sito di prova, renderer, codici CLI."""

import json

import seo_rrf_audit as sra


def _audit(site, k=48):
    return sra.run_audit(base=site, max_pages=10, queries=[],
                         model_name="", delay=0.0, k=k,
                         verbose=False)


def test_run_audit_rileva_i_difetti_piantati(site):
    pages, findings, scores, results, mode, _ = _audit(site)
    titoli = [f.title for f in findings]
    dettagli = " | ".join(f.detail for f in findings)

    assert any("Crawler IA bloccati" in t and "GPTBot" in t
               for t in titoli)
    assert any("segnaposto" in t for t in titoli)
    assert any("contenuto identico" in t for t in titoli)
    assert any("meta robots noindex" in t for t in titoli)
    assert any("non raggiungibili o in errore" in t for t in titoli)
    assert "oltre il limite" in dettagli

    assert mode == "char-tfidf"
    assert set(scores) == {sra.AREA_TECH, sra.AREA_LEX, sra.AREA_SEM,
                           sra.AREA_SD, sra.AREA_RRF}
    assert 0 <= sra.overall_score(scores) <= 100
    assert results, "attesi esiti RRF con query auto-generate"
    assert [p for p in pages if not p.ok], "attesa la pagina oversize"


def test_renderer_coerenti_e_k_propagato(site):
    pages, findings, scores, results, mode, _ = _audit(site, k=48)

    report_json = json.loads(sra.render_json(
        site, pages, findings, scores, results, mode, 48))
    assert report_json["rrf"]["k"] == 48
    assert report_json["version"] == sra.__version__
    assert report_json["scores"]["overall"] == \
        sra.overall_score(scores)
    assert len(report_json["findings"]) == len(findings)

    report_html = sra.render_html(
        site, pages, findings, scores, results, mode, 48)
    assert report_html.startswith("<!DOCTYPE html>")
    assert "char-tfidf" in report_html

    report_text = sra.render_text(
        site, pages, findings, scores, results, mode, 48)
    assert "AUDIT SEO + RRF" in report_text


def test_robots_allowed_per_il_nostro_agente(site):
    fetcher = sra.Fetcher(delay=0.0, verbose=False)
    robots = sra.RobotsAudit(site, fetcher)
    robots.run()
    assert robots.allowed(site + "/")
    assert not robots.allowed(site + "/riservata/")


def test_default_scansiona_anche_url_vietati(site):
    pages, _, _, _, _, _ = _audit(site)
    assert any(p.url.endswith("/riservata/") and p.ok for p in pages)


def test_respect_robots_esclude_url_vietati(site):
    pages, findings, _, _, _, _ = sra.run_audit(
        base=site, max_pages=10, queries=[], model_name="",
        delay=0.0, k=60, verbose=False, respect_robots=True)
    assert not any("/riservata/" in p.url for p in pages)
    assert any("rispetto del robots.txt" in f.title
               for f in findings)


def test_crawl_links_rispetta_robots(site):
    fetcher = sra.Fetcher(delay=0.0, verbose=False)
    robots = sra.RobotsAudit(site, fetcher)
    robots.run()
    senza = sra.crawl_links(site, fetcher, 10)
    con = sra.crawl_links(site, fetcher, 10, robots)
    assert any("/riservata" in u for u in senza)
    assert not any("/riservata" in u for u in con)


def test_parser_accetta_respect_robots():
    args = sra.build_parser().parse_args(
        ["https://x.it", "--respect-robots"])
    assert args.respect_robots
    args = sra.build_parser().parse_args(["https://x.it"])
    assert not args.respect_robots


def test_cli_referto_json_e_uscita_uno(site, tmp_path, capsys):
    out = tmp_path / "referto.json"
    rc = sra.main([site, "--quiet", "--delay", "0", "--format",
                   "json", "--output", str(out)])
    capsys.readouterr()
    assert rc == 1, "i difetti piantati devono dare uscita 1"
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["site"] == site


def test_cli_file_query_mancante(capsys):
    rc = sra.main(["https://x.invalid", "--queries", "/non/esiste.txt"])
    capsys.readouterr()
    assert rc == 2


def test_cli_max_body_non_valido(capsys):
    rc = sra.main(["https://x.invalid", "--max-body", "0"])
    capsys.readouterr()
    assert rc == 2
