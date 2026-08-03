# -*- coding: utf-8 -*-
"""Monitoraggio citazioni IA: provider contro server API finti."""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

import seo_rrf_citations as src

FAKE_MESSAGE = {
    "id": "msg_test",
    "type": "message",
    "role": "assistant",
    "model": "claude-opus-5",
    "stop_reason": "end_turn",
    "usage": {"input_tokens": 10, "output_tokens": 20},
    "content": [
        {
            "type": "web_search_tool_result",
            "tool_use_id": "srvtoolu_1",
            "content": [
                {"type": "web_search_result",
                 "url": "https://mio.it/servizi",
                 "title": "Servizi", "encrypted_content": "x"},
                {"type": "web_search_result",
                 "url": "https://altro.it/guida",
                 "title": "Guida", "encrypted_content": "y"},
            ],
        },
        {
            "type": "text",
            "text": "Il drenaggio linfatico è una tecnica...",
            "citations": [
                {"type": "web_search_result_location",
                 "url": "https://www.mio.it/servizi",
                 "title": "Servizi", "cited_text": "...",
                 "encrypted_index": "z"},
            ],
        },
    ],
}

FAKE_PERPLEXITY = {
    "choices": [{"message": {"role": "assistant",
                             "content": "Risposta con fonti."}}],
    "citations": ["https://altro.it/guida", "https://terzo.it/blog"],
    "search_results": [{"url": "https://mio.it/faq"}],
}


class FakeApiHandler(BaseHTTPRequestHandler):
    """Risponde come Anthropic o Perplexity a seconda del percorso."""

    def do_POST(self):  # noqa: N802 - firma di BaseHTTPServer
        length = int(self.headers.get("Content-Length", "0"))
        self.rfile.read(length)
        if self.path.startswith("/v1/messages"):
            body = json.dumps(FAKE_MESSAGE).encode("utf-8")
        else:
            body = json.dumps(FAKE_PERPLEXITY).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass


@pytest.fixture(scope="module")
def fake_api():
    server = ThreadingHTTPServer(("127.0.0.1", 0), FakeApiHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield "http://127.0.0.1:%d" % server.server_address[1]
    server.shutdown()


def test_norm_host_e_match():
    assert src.norm_host("https://www.Mio.IT/pagina") == "mio.it"
    assert src.norm_host("mio.it:8080") == "mio.it"
    assert src.host_matches("https://blog.mio.it/post", "mio.it")
    assert not src.host_matches("https://mio.it.evil.com/", "mio.it")
    assert not src.host_matches("https://altromio.it/", "mio.it")


def test_provider_anthropic_estrae_citazioni(fake_api):
    provider = src.AnthropicProvider(api_key="test-key",
                                     base_url=fake_api)
    answer = provider.ask("cos'e' il drenaggio linfatico")
    assert answer.ok
    assert "https://www.mio.it/servizi" in answer.cited_urls
    assert "https://altro.it/guida" in answer.searched_urls


def test_provider_perplexity_estrae_citazioni(fake_api):
    provider = src.PerplexityProvider(api_key="test-key",
                                      endpoint=fake_api + "/chat")
    answer = provider.ask("cos'e' il drenaggio linfatico")
    assert answer.ok
    assert "https://altro.it/guida" in answer.cited_urls
    assert "https://mio.it/faq" in answer.searched_urls


def test_run_monitor_aggrega_e_rileva_concorrenti(fake_api):
    providers = [
        src.AnthropicProvider(api_key="k", base_url=fake_api),
        src.PerplexityProvider(api_key="k",
                               endpoint=fake_api + "/chat"),
    ]
    payload = src.run_monitor(
        "https://mio.it", ["query uno", "query due"], providers,
        competitors=["altro.it"], delay=0, verbose=False)

    ant = payload["providers"]["anthropic"]
    assert ant["answered"] == 2 and ant["site_cited"] == 2
    assert ant["rate"] == 100.0
    assert ant["competitors_cited"]["altro.it"] == 0

    ppx = payload["providers"]["perplexity"]
    assert ppx["site_cited"] == 0, \
        "Perplexity cita solo altro.it e terzo.it"
    assert ppx["competitors_cited"]["altro.it"] == 2
    assert ppx["results"][0]["site_consulted"] is True

    assert src.overall_rate(payload) == 50.0


def test_storico_e_delta(fake_api, tmp_path):
    history = tmp_path / "storico.jsonl"
    provider = src.AnthropicProvider(api_key="k", base_url=fake_api)
    payload = src.run_monitor("mio.it", ["q"], [provider],
                              delay=0, verbose=False)

    assert src.read_last_run(str(history), "mio.it") is None
    src.append_history(str(history), payload)
    src.append_history(str(history), payload)
    last = src.read_last_run(str(history), "mio.it")
    assert last is not None and last["overall_rate"] == 100.0

    text = src.render_text(payload, previous=last)
    assert "delta +0.0" in text
    data = json.loads(src.render_json(payload, previous=last))
    assert data["overall_rate"] == 100.0
    assert data["previous"]["site"] == "mio.it"


def test_query_da_referto_audit(tmp_path):
    report = tmp_path / "referto.json"
    report.write_text(json.dumps({
        "rrf_simulation": [{"query": "a"}, {"query": "b"}]}),
        encoding="utf-8")
    args = src.build_parser().parse_args(
        ["mio.it", "--from-audit", str(report)])
    queries, err = src.load_queries(args)
    assert err == "" and queries == ["a", "b"]


def test_errori_uso(capsys, tmp_path):
    assert src.main(["mio.it"]) == 2  # niente query
    assert src.main(["mio.it", "--queries", "/non/esiste"]) == 2
    troppi = ["mio.it", "--queries", "/x"]
    for host in ("a.it", "b.it", "c.it", "d.it"):
        troppi += ["--competitor", host]
    assert src.main(troppi) == 2
    capsys.readouterr()


def test_fail_under(fake_api, tmp_path, capsys, monkeypatch):
    queries = tmp_path / "q.txt"
    queries.write_text("query uno\n", encoding="utf-8")
    monkeypatch.setenv("PERPLEXITY_API_KEY", "test-key")
    monkeypatch.setattr(src.PerplexityProvider, "endpoint",
                        fake_api + "/chat")
    rc = src.main(["mio.it", "--queries", str(queries),
                   "--provider", "perplexity", "--delay", "0",
                   "--quiet", "--fail-under", "50"])
    capsys.readouterr()
    assert rc == 1, "Perplexity finto non cita mio.it: sotto soglia"
