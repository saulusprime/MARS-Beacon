# -*- coding: utf-8 -*-
"""Confronto competitivo: share of voice sul corpus fuso."""

import json

import mars_audit as sra


def _chunk(url, heading, text, index=0):
    return sra.Chunk(url=url, heading=heading, text=text, index=index)


def test_share_quando_il_concorrente_domina():
    own = [_chunk("https://mio.it/chi-siamo", "Chi siamo",
                  "una piccola azienda che lavora con passione "
                  "sul territorio da molti anni con i clienti")]
    comp = [
        _chunk("https://altro.it/g1", "Cos'e' il drenaggio linfatico",
               "il drenaggio linfatico manuale è una tecnica di "
               "massaggio dolce che favorisce il deflusso della "
               "linfa lungo le vie linfatiche del corpo", 0),
        _chunk("https://altro.it/g2", "Come funziona il drenaggio",
               "il drenaggio linfatico funziona con pressioni lente "
               "e ritmiche che stimolano la circolazione della "
               "linfa e riducono il gonfiore degli arti", 1),
    ]
    payload, findings = sra.simulate_share_of_voice(
        "https://mio.it", own, {"altro.it": comp},
        ["cos'e' il drenaggio linfatico"], k=60)

    assert payload is not None
    share = payload["share"]
    assert abs(sum(share.values()) - 100.0) < 0.5
    assert share["altro.it"] > share["mio.it"]
    sov = [f for f in findings if "Share of voice" in f.title]
    assert sov and sov[0].severity in (sra.SEV_WARNING,
                                       sra.SEV_CRITICAL)
    assert any("vinte interamente dai concorrenti" in f.title
               for f in findings)


def test_share_con_concorrente_vuoto():
    own = [_chunk("https://mio.it/a", "Drenaggio linfatico",
                  "il drenaggio linfatico manuale è una tecnica "
                  "di massaggio dolce per il deflusso della linfa "
                  "eseguita da fisioterapisti formati")]
    payload, findings = sra.simulate_share_of_voice(
        "https://mio.it", own, {"vuoto.it": []},
        ["cos'e' il drenaggio linfatico"], k=60)

    assert payload["share"]["mio.it"] == 100.0
    assert payload["share"]["vuoto.it"] == 0.0
    assert any("senza contenuto recuperabile" in f.title
               for f in findings)
    sov = [f for f in findings if "Share of voice" in f.title]
    assert sov[0].severity == sra.SEV_OK


def test_e2e_confronto_su_siti_di_prova(site, competitor_site):
    pages, findings, scores, results, mode, comp = sra.run_audit(
        base=site, max_pages=8, queries=[], model_name="",
        delay=0.0, k=60, verbose=False,
        competitors=[competitor_site])

    assert comp is not None
    hosts = comp["sites"]
    assert len(hosts) == 2 and comp["main"] == hosts[0]
    assert abs(sum(comp["share"].values()) - 100.0) < 0.5
    assert comp["chunks"][hosts[1]] > 0, \
        "il concorrente di prova deve produrre chunk"
    assert comp["queries"], "attese righe per query"
    assert any("Share of voice" in f.title for f in findings)

    report_json = json.loads(sra.render_json(
        site, pages, findings, scores, results, mode, 60, comp))
    assert report_json["competitive"]["share"] == comp["share"]
    report_text = sra.render_text(
        site, pages, findings, scores, results, mode, 60, comp)
    assert "CONFRONTO COMPETITIVO" in report_text
    report_html = sra.render_html(
        site, pages, findings, scores, results, mode, 60, comp)
    assert "Confronto competitivo" in report_html


def test_senza_concorrenti_nessuna_sezione(site):
    pages, findings, scores, results, mode, comp = sra.run_audit(
        base=site, max_pages=5, queries=["drenaggio linfatico"],
        model_name="", delay=0.0, k=60, verbose=False)
    assert comp is None
    report_json = json.loads(sra.render_json(
        site, pages, findings, scores, results, mode, 60, comp))
    assert report_json["competitive"] is None
    report_text = sra.render_text(
        site, pages, findings, scores, results, mode, 60, comp)
    assert "CONFRONTO COMPETITIVO" not in report_text


def test_parser_competitor_ripetibile():
    args = sra.build_parser().parse_args(
        ["https://x.it", "--competitor", "a.it",
         "--competitor", "b.it"])
    assert args.competitors == ["a.it", "b.it"]
    assert sra.build_parser().parse_args(["https://x.it"]).competitors \
        == []


def test_cli_troppi_concorrenti(capsys):
    rc = sra.main(["https://x.invalid",
                   "--competitor", "a.it", "--competitor", "b.it",
                   "--competitor", "c.it", "--competitor", "d.it"])
    capsys.readouterr()
    assert rc == 2
