# -*- coding: utf-8 -*-
"""Giudizio LLM sulla citabilita': server API Anthropic finto.

Il giudice e' attivo di default in modalita' "auto": questi test
verificano che senza chiave venga saltato (audit offline garantito
dalla fixture autouse di conftest) e che con chiave e base_url
verso il server finto produca verdetti, gestendo refusal e JSON
malformato senza mai far fallire il referto.
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

import mars_audit as sra

VERDETTI_JSON = json.dumps([
    {"id": 1, "score": 82, "reason": "Risposta diretta e completa"},
    {"id": 2, "score": 40, "reason": "Testo generico"},
])

# Stato modificato dai test per simulare i vari esiti.
RESPONSE_MODE = {"mode": "ok"}


def _fake_message():
    if RESPONSE_MODE["mode"] == "refusal":
        return {"id": "msg", "type": "message", "role": "assistant",
                "model": "claude-opus-5", "stop_reason": "refusal",
                "usage": {"input_tokens": 1, "output_tokens": 1},
                "content": []}
    testo = (VERDETTI_JSON if RESPONSE_MODE["mode"] == "ok"
             else "non sono JSON")
    return {"id": "msg", "type": "message", "role": "assistant",
            "model": "claude-opus-5", "stop_reason": "end_turn",
            "usage": {"input_tokens": 1, "output_tokens": 1},
            "content": [{"type": "text", "text": testo}]}


class FakeAnthropicHandler(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802 - firma di BaseHTTPServer
        length = int(self.headers.get("Content-Length", "0"))
        self.rfile.read(length)
        body = json.dumps(_fake_message()).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass


@pytest.fixture(scope="module")
def fake_anthropic():
    server = ThreadingHTTPServer(("127.0.0.1", 0),
                                 FakeAnthropicHandler)
    threading.Thread(target=server.serve_forever,
                     daemon=True).start()
    yield "http://127.0.0.1:%d" % server.server_address[1]
    server.shutdown()


def _pages_con_chunk():
    page = sra.Page(url="https://sito.test/a", status=200,
                    text="testo", word_count=400)
    page.chunks = [
        sra.Chunk(url=page.url, heading="Drenaggio",
                  text="Il drenaggio linfatico e' una tecnica...",
                  index=0),
        sra.Chunk(url=page.url, heading="Costi",
                  text="Una seduta costa in media 50 euro.",
                  index=1),
    ]
    return [page]


def _results(pages):
    c1, c2 = pages[0].chunks
    return [
        sra.QueryResult(query="cos'e' il drenaggio",
                        fused_top=[(c1.label, 0.03)]),
        sra.QueryResult(query="quanto costa il drenaggio",
                        fused_top=[(c2.label, 0.02)]),
        # Stesso vincitore della prima: va deduplicato.
        sra.QueryResult(query="drenaggio come funziona",
                        fused_top=[(c1.label, 0.01)]),
    ]


def _attiva(monkeypatch, fake_anthropic):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "chiave-di-prova")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", fake_anthropic)


# ---------------- disponibilita' e modalita' ----------------

def test_senza_chiave_auto_salta():
    assert sra.judge_unavailable() is not None
    pages = _pages_con_chunk()
    esito = sra.run_judge(_results(pages), pages)
    assert esito["status"] == "skipped"
    assert "ANTHROPIC_API_KEY" in esito["reason"]


def test_off_restituisce_none(monkeypatch, fake_anthropic):
    _attiva(monkeypatch, fake_anthropic)
    pages = _pages_con_chunk()
    assert sra.run_judge(_results(pages), pages,
                         sra.JUDGE_OFF) is None


def test_cli_on_senza_chiave_esce_con_2(site):
    rc = sra.main([site, "--judge", "on", "--quiet"])
    assert rc == 2


# ---------------- campionamento ----------------

def test_campione_deduplicato_e_limitato():
    pages = _pages_con_chunk()
    sample = sra._judge_sample(_results(pages), pages)
    assert len(sample) == 2  # il vincitore ripetuto conta una volta
    assert sample[0][0] == "cos'e' il drenaggio"
    assert sample[1][1].heading == "Costi"


# ---------------- esiti della chiamata ----------------

def test_verdetti_dal_server_finto(monkeypatch, fake_anthropic):
    _attiva(monkeypatch, fake_anthropic)
    RESPONSE_MODE["mode"] = "ok"
    pages = _pages_con_chunk()
    esito = sra.run_judge(_results(pages), pages)
    assert esito["status"] == "ok"
    assert esito["sampled"] == 2
    assert esito["average"] == 61.0  # (82+40)/2
    assert esito["verdicts"][0]["query"] == "cos'e' il drenaggio"
    assert esito["verdicts"][0]["score"] == 82.0
    assert esito["note"] == sra.JUDGE_NOTE


def test_refusal_diventa_errore_gestito(monkeypatch,
                                        fake_anthropic):
    _attiva(monkeypatch, fake_anthropic)
    RESPONSE_MODE["mode"] = "refusal"
    pages = _pages_con_chunk()
    esito = sra.run_judge(_results(pages), pages)
    RESPONSE_MODE["mode"] = "ok"
    assert esito["status"] == "error"
    assert "classificatori" in esito["reason"]


def test_json_malformato_errore_gestito(monkeypatch,
                                        fake_anthropic):
    _attiva(monkeypatch, fake_anthropic)
    RESPONSE_MODE["mode"] = "garbage"
    pages = _pages_con_chunk()
    esito = sra.run_judge(_results(pages), pages)
    RESPONSE_MODE["mode"] = "ok"
    assert esito["status"] == "error"
    assert "non interpretabile" in esito["reason"]


# ---------------- referti ----------------

def _giudizio_ok():
    return {"status": "ok", "model": "claude-opus-5", "sampled": 1,
            "average": 82.0, "note": sra.JUDGE_NOTE,
            "verdicts": [{"query": "cos'e' il drenaggio",
                          "label": "x", "score": 82.0,
                          "reason": "Risposta diretta"}]}


def _scores():
    return {sra.AREA_TECH: 80.0, sra.AREA_LEX: 60.0,
            sra.AREA_SEM: 70.0, sra.AREA_SD: 50.0,
            sra.AREA_RRF: 42.0}


def test_referti_includono_il_giudizio():
    pages = _pages_con_chunk()
    testo = sra.render_text("https://sito.test", pages, [],
                            _scores(), [], "char-tfidf",
                            judge=_giudizio_ok())
    assert "GIUDIZIO LLM SULLA CITABILITA'" in testo
    assert "scarto giudice-euristica" in testo
    pagina = sra.render_html("https://sito.test", pages, [],
                             _scores(), [], "char-tfidf",
                             judge=_giudizio_ok())
    assert "Giudizio LLM sulla citabilita'" in pagina
    assert "Risposta diretta" in pagina
    payload = json.loads(sra.render_json(
        "https://sito.test", pages, [], _scores(), [],
        "char-tfidf", judge=_giudizio_ok()))
    assert payload["judge"]["average"] == 82.0


def test_referto_dichiara_il_giudizio_saltato():
    testo = sra.render_text(
        "https://sito.test", _pages_con_chunk(), [], _scores(),
        [], "char-tfidf",
        judge={"status": "skipped", "reason": "chiave assente"})
    assert "Non eseguito: chiave assente" in testo
    testo_off = sra.render_text(
        "https://sito.test", _pages_con_chunk(), [], _scores(),
        [], "char-tfidf", judge=None)
    assert "GIUDIZIO LLM" not in testo_off
