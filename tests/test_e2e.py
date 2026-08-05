# -*- coding: utf-8 -*-
"""End-to-end: run_audit sul sito di prova, renderer, codici CLI."""

import json

import mars_audit as sra


def _audit(site, k=48):
    return sra.run_audit(base=site, max_pages=10, queries=[],
                         model_name="none", delay=0.0, k=k,
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

    # Widget di sintesi: anello del punteggio, tile di severita',
    # donut delle pagine, meter del consenso con tacche di soglia.
    assert "class=\"hero\"" in report_html
    assert "rfill" in report_html
    assert "Punteggio complessivo" in report_html
    assert "class=\"tile\"" in report_html
    assert "donutbox" in report_html
    assert "class=\"tick\"" in report_html

    clean, flagged, broken = sra.page_status_counts(pages, findings)
    assert clean + flagged + broken == len(pages)
    assert broken >= 1, "attesa la pagina oversize fra gli errori"

    # Matematica del problema: superficie attuale vs potenziale.
    assert report_json["surface_math"]["chunks_potential"] > 0
    assert "La matematica del problema" in report_html

    # Piano di remediation: nei tre formati, ordinato dai critici,
    # con sforzo stimato per intervento.
    assert report_json["remediation"]
    assert all(i["effort"] in (sra.EFFORT_MINUTES, sra.EFFORT_HOURS,
                               sra.EFFORT_DAYS)
               for i in report_json["remediation"])
    assert any(i["quick_win"] for i in report_json["remediation"]), \
        "il segnaposto critico del sito fixture e' un quick win"
    assert report_json["remediation"][0]["severity"] == \
        sra.SEV_CRITICAL
    assert "Piano di remediation" in report_html
    assert "class=\"ex\"" in report_html

    # Dettagli arricchiti: le query verificate sono elencate.
    coperte = [f for f in findings
               if "trovano almeno un passaggio" in f.title]
    if coperte:
        assert "Query verificate:" in coperte[0].detail

    report_text = sra.render_text(
        site, pages, findings, scores, results, mode, 48)
    assert "MARS BEACON" in report_text
    assert "PIANO DI REMEDIATION" in report_text
    assert "MATEMATICA DEL PROBLEMA" in report_text
    assert "sforzo:" in report_text


def test_robots_allowed_per_il_nostro_agente(site):
    fetcher = sra.Fetcher(delay=0.0, verbose=False)
    robots = sra.RobotsAudit(site, fetcher)
    robots.run()
    assert robots.allowed(site + "/")
    assert not robots.allowed(site + "/riservata/")


def test_default_rispetta_i_disallow(site):
    pages, findings, _, _, _, _ = _audit(site)
    assert not any("/riservata/" in p.url for p in pages)
    assert any("rispetto del robots.txt" in f.title
               for f in findings)


def test_own_site_analizza_tutto(site):
    pages, findings, _, _, _, _ = sra.run_audit(
        base=site, max_pages=10, queries=[], model_name="",
        delay=0.0, k=60, verbose=False,
        robots_mode=sra.ROBOTS_OWN)
    assert any(p.url.endswith("/riservata/") and p.ok for p in pages)
    assert any("propria titolarita'" in f.title for f in findings)


def test_force_ignora_disallow_con_responsabilita(site):
    pages, findings, _, _, _, _ = sra.run_audit(
        base=site, max_pages=10, queries=[], model_name="",
        delay=0.0, k=60, verbose=False,
        robots_mode=sra.ROBOTS_FORCE)
    assert any(p.url.endswith("/riservata/") and p.ok for p in pages)
    assert any("richiesta esplicita" in f.title for f in findings)


def test_crawl_links_rispetta_robots(site):
    fetcher = sra.Fetcher(delay=0.0, verbose=False)
    robots = sra.RobotsAudit(site, fetcher)
    robots.run()
    senza = sra.crawl_links(site, fetcher, 10)
    con = sra.crawl_links(site, fetcher, 10, robots)
    assert any("/riservata" in u for u in senza)
    assert not any("/riservata" in u for u in con)


def test_parser_opzioni_robots():
    parser = sra.build_parser()
    assert parser.parse_args(["x.it"]).own_site is False
    assert parser.parse_args(["x.it", "--own-site"]).own_site
    assert parser.parse_args(
        ["x.it", "--ignore-robots", "accetto"]).ignore_robots == \
        "accetto"
    # deprecato ma ancora accettato
    assert parser.parse_args(["x.it", "--respect-robots"]) \
        .respect_robots


def test_cli_robots_conflitti_e_ack(capsys):
    assert sra.main(["https://x.invalid", "--ignore-robots",
                     "si"]) == 2, "ack sbagliato"
    assert sra.main(["https://x.invalid", "--ignore-robots",
                     "accetto", "--own-site"]) == 2
    assert sra.main(["https://x.invalid", "--own-site",
                     "--respect-robots"]) == 2
    capsys.readouterr()


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


def test_cli_fail_under_fuori_scala(capsys):
    assert sra.main(["https://x.invalid", "--fail-under", "101"]) == 2
    assert sra.main(["https://x.invalid", "--fail-under", "-1"]) == 2
    capsys.readouterr()


def test_cli_fail_under_gate_sul_punteggio(site, capsys):
    # soglia massima: il gate scatta e lo dichiara su stderr
    rc = sra.main([site, "--quiet", "--delay", "0",
                   "--fail-under", "100"])
    err = capsys.readouterr().err
    assert rc == 1
    assert "sotto la soglia" in err

    # soglia minima: il gate non scatta, resta l'uscita 1 sui critici
    rc = sra.main([site, "--quiet", "--delay", "0",
                   "--fail-under", "0"])
    err = capsys.readouterr().err
    assert rc == 1, "i difetti piantati devono dare uscita 1"
    assert "sotto la soglia" not in err
