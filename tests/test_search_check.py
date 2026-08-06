"""Ancora di realta' (Brave Search): server API finto locale.

Pattern del monitor citazioni: nessuna chiamata reale, chiave ed
endpoint puntano al server finto — la suite resta offline per
costruzione (conftest rimuove BRAVE_API_KEY dall'ambiente).
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import pytest

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


class _BraveFinto(BaseHTTPRequestHandler):
    """Risponde come la Brave Search API: URL per query."""

    esiti = {}
    fallisci = False

    def do_GET(self):  # noqa: N802 - firma di BaseHTTPServer
        if self.fallisci:
            self.send_response(500)
            self.end_headers()
            return
        q = parse_qs(urlparse(self.path).query).get("q", [""])[0]
        body = json.dumps({"web": {"results": [
            {"url": u, "title": "t"}
            for u in self.esiti.get(q, [])]}}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@pytest.fixture()
def brave(monkeypatch):
    server = ThreadingHTTPServer(("127.0.0.1", 0), _BraveFinto)
    threading.Thread(target=server.serve_forever,
                     daemon=True).start()
    _BraveFinto.esiti = {}
    _BraveFinto.fallisci = False
    monkeypatch.setenv("BRAVE_API_KEY", "chiave-finta")
    monkeypatch.setenv(
        "BRAVE_BASE_URL",
        "http://127.0.0.1:%d/res/v1/web/search"
        % server.server_address[1])
    _patch(monkeypatch, "SEARCH_CHECK_DELAY_S", 0)
    yield _BraveFinto
    server.shutdown()


def _query(q, covered=True, consensus=3):
    return sra.QueryResult(query=q, covered=covered,
                           consensus=consensus)


def test_off_e_salto_dichiarato(capsys):
    assert sra.run_search_check(
        "https://x.it", [], mode=sra.SEARCH_CHECK_OFF) is None
    data = sra.run_search_check(
        "https://x.it", [_query("a")],
        mode=sra.SEARCH_CHECK_AUTO, verbose=True)
    assert data["status"] == "skipped"
    assert "BRAVE_API_KEY" in data["reason"]
    assert "saltata" in capsys.readouterr().err


def test_posizioni_e_confronto_rrf(brave):
    brave.esiti = {
        "cos'e' il drenaggio": ["https://altro.it/",
                                "https://www.x.it/drenaggio"],
        "quanto costa": ["https://altro.it/",
                         "https://terzo.it/"],
    }
    data = sra.run_search_check(
        "https://x.it",
        [_query("cos'e' il drenaggio", covered=True),
         _query("quanto costa", covered=False, consensus=0)],
        mode=sra.SEARCH_CHECK_AUTO)
    assert data["status"] == "ok" and data["found"] == 1
    prima, seconda = data["queries"]
    assert prima["position"] == 2  # "www." normalizzato
    assert prima["url"].endswith("/drenaggio")
    assert prima["rrf_covered"] is True
    assert seconda["position"] is None
    assert seconda["rrf_consensus"] == 0
    assert data["note"] == sra.SEARCH_CHECK_NOTE


def test_tutte_le_richieste_fallite(brave):
    brave.fallisci = True
    data = sra.run_search_check(
        "https://x.it", [_query("a"), _query("b")],
        mode=sra.SEARCH_CHECK_AUTO)
    assert data["status"] == "error"
    assert "fallite" in data["reason"]


def test_referti_dichiarano_l_ancora():
    ok = {"status": "ok", "engine": "brave", "site": "x.it",
          "top_n": 20, "found": 1, "note": sra.SEARCH_CHECK_NOTE,
          "queries": [
              {"query": "drenaggio", "rrf_covered": True,
               "rrf_consensus": 3, "position": 2,
               "url": "https://x.it/d"},
              {"query": "costi", "rrf_covered": False,
               "rrf_consensus": 0, "position": None,
               "url": ""}]}
    testo = sra.render_text("https://x.it", [], [], {}, [],
                            "char-tfidf", search_check=ok)
    assert "ANCORA DI REALTA'" in testo
    assert "posizione #2" in testo
    assert "assente dai primi 20" in testo
    html_out = sra.render_html("https://x.it", [], [], {}, [],
                               "char-tfidf", search_check=ok)
    assert "Ancora di realta" in html_out and "#2" in html_out
    md = sra.render_markdown("https://x.it", [], [], {}, [],
                             "char-tfidf", search_check=ok)
    assert "## Ancora di realta' (Brave Search)" in md
    dati = json.loads(sra.render_json(
        "https://x.it", [], [], {}, [], "char-tfidf",
        search_check=ok))
    assert dati["search_check"]["found"] == 1
    salto = {"status": "skipped", "engine": "brave",
             "reason": "variabile d'ambiente BRAVE_API_KEY "
                       "assente"}
    testo2 = sra.render_text("https://x.it", [], [], {}, [],
                             "char-tfidf", search_check=salto)
    assert "Non eseguita" in testo2 and "BRAVE_API_KEY" in testo2


def test_cli_on_richiede_chiave(capsys):
    rc = sra.main(["https://x.invalid", "--search-check", "on"])
    assert rc == 2
    assert "BRAVE_API_KEY" in capsys.readouterr().err


def test_flag_default_auto():
    args = sra.build_parser().parse_args(["https://x.it"])
    assert args.search_check == sra.SEARCH_CHECK_AUTO
