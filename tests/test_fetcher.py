# -*- coding: utf-8 -*-
"""Fetcher: limite --max-body e retry sugli errori transitori."""

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

import mars_audit as sra


class FlakyHandler(BaseHTTPRequestHandler):
    """Conta le richieste; /flaky fallisce due volte poi risponde."""

    def do_GET(self):  # noqa: N802 - firma di BaseHTTPServer
        hits = self.server.hits
        hits[self.path] = hits.get(self.path, 0) + 1
        body = b"<html><body>ok</body></html>"
        if self.path == "/flaky" and hits[self.path] < 3:
            status = 503
        elif self.path == "/down":
            status = 503
        elif self.path == "/manca":
            status = 404
        else:
            status = 200
        self.send_response(status)
        if status == 503:
            self.send_header("Retry-After", "0")
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass


@pytest.fixture()
def flaky():
    server = ThreadingHTTPServer(("127.0.0.1", 0), FlakyHandler)
    server.hits = {}
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield "http://127.0.0.1:%d" % server.server_address[1], server
    server.shutdown()


def _fetcher(**kw):
    kw.setdefault("delay", 0.0)
    kw.setdefault("verbose", False)
    kw.setdefault("backoff", 0.01)
    return sra.Fetcher(**kw)


def test_retry_recupera_dopo_503(flaky):
    base, server = flaky
    resp = _fetcher(retries=2).get(base + "/flaky")
    assert resp is not None and resp.status_code == 200
    assert server.hits["/flaky"] == 3


def test_senza_retry_il_503_resta(flaky):
    base, server = flaky
    resp = _fetcher(retries=0).get(base + "/flaky")
    assert resp is not None and resp.status_code == 503
    assert server.hits["/flaky"] == 1


def test_tentativi_esauriti_restituisce_ultima_risposta(flaky):
    base, server = flaky
    resp = _fetcher(retries=1).get(base + "/down")
    assert resp is not None and resp.status_code == 503
    assert server.hits["/down"] == 2


def test_il_404_non_viene_ritentato(flaky):
    base, server = flaky
    resp = _fetcher(retries=3).get(base + "/manca")
    assert resp is not None and resp.status_code == 404
    assert server.hits["/manca"] == 1


def test_oversize_non_viene_ritentato(site):
    fetcher = _fetcher(retries=3)
    assert fetcher.get(site + "/big/") is None
    assert "oltre il limite" in fetcher.last_error


def test_pagina_normale_resta_fruibile(site):
    fetcher = sra.Fetcher(delay=0.0, verbose=False)
    resp = fetcher.get(site + "/")
    assert resp is not None
    assert fetcher.last_error == ""
    assert "Centro Linfa" in resp.text
    assert resp.content.startswith(b"<!DOCTYPE html>")


def test_content_length_oltre_il_limite_rifiutato(site):
    fetcher = sra.Fetcher(delay=0.0, verbose=False)
    assert fetcher.get(site + "/big/") is None
    assert "oltre il limite" in fetcher.last_error


def test_limite_personalizzato_ammette_il_corpo(site):
    fetcher = sra.Fetcher(delay=0.0, verbose=False,
                          max_bytes=20 * 1048576)
    resp = fetcher.get(site + "/big/")
    assert resp is not None
    assert len(resp.content) == 12 * 1048576


def test_last_error_si_azzera(site):
    fetcher = sra.Fetcher(delay=0.0, verbose=False)
    fetcher.get(site + "/big/")
    assert fetcher.last_error
    fetcher.get(site + "/")
    assert fetcher.last_error == ""


def test_host_irraggiungibile(site):
    fetcher = _fetcher(timeout=2, retries=0)
    assert fetcher.get("http://127.0.0.1:9/") is None
    assert fetcher.last_error == "richiesta fallita"


def test_stop_event_gia_scattato_interrompe_subito(site):
    stop = threading.Event()
    stop.set()
    fetcher = _fetcher(stop_event=stop)
    with pytest.raises(sra.AuditCancelled):
        fetcher.get(site + "/")


def test_stop_event_interrompe_l_attesa_di_backoff(flaky):
    import time as _time
    base, _server = flaky
    stop = threading.Event()
    fetcher = _fetcher(retries=5, backoff=5.0, stop_event=stop)
    threading.Timer(0.2, stop.set).start()
    inizio = _time.time()
    with pytest.raises(sra.AuditCancelled):
        fetcher.get(base + "/down")
    assert _time.time() - inizio < 3, \
        "il backoff deve interrompersi senza attendere i 5 secondi"


def test_run_audit_annullabile(site):
    stop = threading.Event()
    stop.set()
    with pytest.raises(sra.AuditCancelled):
        sra.run_audit(base=site, max_pages=3, queries=[],
                      model_name="", delay=0.0, k=60, verbose=False,
                      stop_event=stop)
