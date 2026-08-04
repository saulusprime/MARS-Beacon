# -*- coding: utf-8 -*-
"""Storico e delta nella CLI (--history) e confronto nel core."""

import json

import seo_rrf_audit as sra


def _payload(scores, findings):
    return {"site": "https://mio.it", "scores": scores,
            "generated_at": "2026-08-04T10:00:00+0200",
            "findings": findings}


def test_history_payload_compatto():
    findings = [
        sra.Finding(sra.AREA_TECH, sra.SEV_CRITICAL,
                    "Sito non in HTTPS"),
        sra.Finding(sra.AREA_TECH, sra.SEV_OK, "HTTPS attivo"),
        sra.Finding(sra.AREA_LEX, sra.SEV_INFO, "Nota"),
        sra.Finding(sra.AREA_LEX, sra.SEV_WARNING,
                    "2 title non ottimizzati"),
    ]
    scores = {sra.AREA_TECH: 50.0, sra.AREA_LEX: 60.0,
              sra.AREA_SEM: None, sra.AREA_SD: 40.0,
              sra.AREA_RRF: 30.0}
    row = sra.history_payload("https://mio.it", findings, scores)
    assert row["site"] == "https://mio.it"
    assert row["created_at"] > 0
    assert row["scores"]["overall"] == sra.overall_score(scores)
    # Solo critici e avvertenze, con i soli campi che servono.
    assert [f["title"] for f in row["findings"]] == \
        ["Sito non in HTTPS", "2 title non ottimizzati"]
    assert set(row["findings"][0]) == {"area", "severity", "title"}


def test_read_history_last_per_sito(tmp_path):
    path = tmp_path / "storico.jsonl"
    righe = [
        json.dumps({"site": "https://mio.it", "created_at": 1.0,
                    "scores": {}, "findings": []}),
        "{riga rotta",
        json.dumps({"site": "https://altro.it", "created_at": 2.0,
                    "scores": {}, "findings": []}),
        json.dumps({"site": "https://mio.it", "created_at": 3.0,
                    "scores": {}, "findings": []}),
    ]
    path.write_text("\n".join(righe) + "\n", encoding="utf-8")
    ultimo = sra.read_history_last(str(path), "https://mio.it")
    assert ultimo and ultimo["created_at"] == 3.0
    assert sra.read_history_last(str(path), "https://mai.it") is None
    assert sra.read_history_last(str(tmp_path / "no.jsonl"),
                                 "https://mio.it") is None


def test_referti_riportano_il_delta():
    prima = _payload(
        {sra.AREA_TECH: 50.0, "overall": 55.0},
        [{"area": sra.AREA_TECH, "severity": "critical",
          "title": "Sito non in HTTPS"}])
    dopo = _payload(
        {sra.AREA_TECH: 70.0, "overall": 64.0},
        [{"area": sra.AREA_SEM, "severity": "warning",
          "title": "Nessuna sezione FAQ"}])
    delta = sra.compute_delta(prima, dopo, 1000.0)
    pages = [sra.Page(url="https://mio.it/", status=200,
                      text="x", word_count=300)]
    scores = {sra.AREA_TECH: 70.0, sra.AREA_LEX: 60.0,
              sra.AREA_SEM: 50.0, sra.AREA_SD: 40.0,
              sra.AREA_RRF: 30.0}
    testo = sra.render_text("https://mio.it", pages, [], scores,
                            [], "char-tfidf", delta=delta)
    assert "RISPETTO ALL'ESECUZIONE PRECEDENTE" in testo
    assert "%s +20.0" % sra.AREA_TECH in testo
    assert "Risolti (1):" in testo and "Sito non in HTTPS" in testo
    assert "Nuovi (1):" in testo

    pagina = sra.render_html("https://mio.it", pages, [], scores,
                             [], "char-tfidf", delta=delta)
    assert "Rispetto all'esecuzione precedente" in pagina
    assert "Risolti (1)" in pagina and "Nuovi (1)" in pagina

    payload = json.loads(sra.render_json(
        "https://mio.it", pages, [], scores, [], "char-tfidf",
        delta=delta))
    assert payload["delta"]["scores"][sra.AREA_TECH] == 20.0


def test_cli_due_esecuzioni_con_history(site, tmp_path):
    storico = tmp_path / "storico.jsonl"
    r1 = tmp_path / "r1.json"
    r2 = tmp_path / "r2.txt"

    rc = sra.main([site, "--max-pages", "3", "--delay", "0",
                   "--format", "json", "--output", str(r1),
                   "--history", str(storico), "--quiet"])
    assert rc == 1  # il sito fixture ha rilievi critici
    primo = json.loads(r1.read_text(encoding="utf-8"))
    assert primo["delta"] is None, "prima esecuzione: nessun delta"
    assert len(storico.read_text(
        encoding="utf-8").strip().splitlines()) == 1

    rc = sra.main([site, "--max-pages", "3", "--delay", "0",
                   "--format", "text", "--output", str(r2),
                   "--history", str(storico), "--quiet"])
    assert rc == 1
    testo = r2.read_text(encoding="utf-8")
    assert "RISPETTO ALL'ESECUZIONE PRECEDENTE" in testo
    assert "Risolti: nessuno" in testo
    assert "Nuovi: nessuno" in testo, "sito immutato fra le corse"
    assert len(storico.read_text(
        encoding="utf-8").strip().splitlines()) == 2


def test_schema_version_nel_referto_e_nello_storico():
    pages = [sra.Page(url="https://mio.it/", status=200,
                      text="x", word_count=300)]
    scores = {sra.AREA_TECH: 70.0, sra.AREA_LEX: 60.0,
              sra.AREA_SEM: 50.0, sra.AREA_SD: 40.0,
              sra.AREA_RRF: 30.0}
    payload = json.loads(sra.render_json(
        "https://mio.it", pages, [], scores, [], "char-tfidf"))
    assert payload["schema_version"] == sra.JSON_SCHEMA_VERSION
    assert isinstance(payload["schema_version"], int)

    riga = sra.history_payload("https://mio.it", [], scores)
    assert riga["schema_version"] == sra.JSON_SCHEMA_VERSION


# ---------------- renderer Markdown e CSV ----------------

def _dati_render():
    pages = [sra.Page(url="https://mio.it/", status=200,
                      text="x", word_count=300)]
    scores = {sra.AREA_TECH: 70.0, sra.AREA_LEX: 60.0,
              sra.AREA_SEM: 50.0, sra.AREA_SD: 40.0,
              sra.AREA_RRF: 30.0}
    findings = [
        sra.Finding(sra.AREA_TECH, sra.SEV_CRITICAL,
                    "Sito non in HTTPS",
                    "Dettaglio con | pipe;e punto e virgola",
                    "Attiva il TLS", url="https://mio.it/"),
        sra.Finding(sra.AREA_LEX, sra.SEV_OK, "Title a posto"),
    ]
    return pages, scores, findings


def test_render_markdown_struttura():
    pages, scores, findings = _dati_render()
    md = sra.render_markdown("https://mio.it", pages, findings,
                             scores, [], "char-tfidf")
    assert md.startswith("# Audit SEO + RRF — https://mio.it")
    assert "| Area | Punteggio |" in md
    assert "- [ ] **1.** Sito non in HTTPS" in md, \
        "il piano e' una task list spuntabile"
    assert "**[CRITICO]** Sito non in HTTPS" in md
    assert "[ok] Title a posto" in md
    assert "Profili di citabilita'" in md


def test_render_csv_rilievi():
    import csv as _csv
    import io as _io
    pages, scores, findings = _dati_render()
    out = sra.render_csv("https://mio.it", pages, findings,
                         scores, [], "char-tfidf")
    assert out.startswith("﻿"), "BOM per Excel"
    rows = list(_csv.reader(_io.StringIO(out.lstrip("﻿")),
                            delimiter=";"))
    assert rows[0][:4] == ["sito", "area", "gravita", "peso"]
    assert len(rows) == 3  # intestazione + 2 rilievi
    critico = rows[1]
    assert critico[2] == "critical"
    assert critico[4] == "Sito non in HTTPS"
    assert "| pipe;e punto e virgola" in critico[5], \
        "quoting corretto di ; e |"
    assert critico[8] == "ore" and critico[9] == "", \
        "quick win solo per i critici da minuti"
    ok = rows[2]
    assert ok[8] == "" and ok[9] == "", \
        "sforzo solo per i rilievi azionabili"


def test_cli_formato_md(site, tmp_path):
    out = tmp_path / "referto.md"
    rc = sra.main([site, "--max-pages", "2", "--delay", "0",
                   "--format", "md", "--output", str(out),
                   "--quiet"])
    assert rc == 1
    testo = out.read_text(encoding="utf-8")
    assert testo.startswith("# Audit SEO + RRF")
    assert "- [ ] **1.**" in testo


def test_referto_html_top_rilievi():
    pages, scores, findings = _dati_render()
    pagina = sra.render_html("https://mio.it", pages, findings,
                             scores, [], "char-tfidf")
    assert "Top rilievi" in pagina
    assert "class=\"toplist\"" in pagina
    assert "Sito non in HTTPS" in pagina
