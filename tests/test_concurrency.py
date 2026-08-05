# -*- coding: utf-8 -*-
"""Fetch concorrente: rate limit preservato, equivalenza, velocita'."""

import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

import mars_audit as sra

HTML = (b"<html><head><title>Pagina</title></head>"
        b"<body><h1>Titolo</h1><p>" + b"contenuto utile " * 20 +
        b"</p></body></html>")


class TimedHandler(BaseHTTPRequestHandler):
    """Registra l'orario di arrivo di ogni richiesta; /lenta dorme."""

    def do_GET(self):  # noqa: N802 - firma di BaseHTTPServer
        with self.server.lock:
            self.server.hits.append((self.path, time.monotonic()))
        if self.path.startswith("/lenta"):
            time.sleep(0.25)
        if self.path == "/manca":
            self.send_response(404)
        else:
            self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(HTML)))
        self.end_headers()
        self.wfile.write(HTML)

    def log_message(self, fmt, *args):
        pass


@pytest.fixture()
def timed_site():
    server = ThreadingHTTPServer(("127.0.0.1", 0), TimedHandler)
    server.hits = []
    server.lock = threading.Lock()
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield "http://127.0.0.1:%d" % server.server_address[1], server
    server.shutdown()


def _fetcher(**kw):
    kw.setdefault("delay", 0.0)
    kw.setdefault("verbose", False)
    return sra.Fetcher(**kw)


def test_equivalenza_seriale_parallelo(timed_site):
    base, _ = timed_site
    urls = [base + "/a", base + "/manca", base + "/b", base + "/c"]
    seriale = sra.fetch_pages(_fetcher(), urls, workers=1)
    parallelo = sra.fetch_pages(_fetcher(), urls, workers=4)
    assert [p.url for p in parallelo] == [p.url for p in seriale]
    assert [p.status for p in parallelo] == [p.status for p in seriale]
    assert [p.ok for p in parallelo] == [p.ok for p in seriale]


def test_rate_limit_preservato_fra_thread(timed_site):
    base, server = timed_site
    delay = 0.15
    urls = [base + "/p%d" % i for i in range(5)]
    sra.fetch_pages(_fetcher(delay=delay), urls, workers=4)
    tempi = sorted(t for _, t in server.hits)
    assert len(tempi) == 5
    distanze = [b - a for a, b in zip(tempi, tempi[1:])]
    assert min(distanze) >= delay * 0.6, \
        "avvii troppo ravvicinati: %s" % distanze


def test_parallelo_sovrappone_le_attese(timed_site):
    base, _ = timed_site
    urls = [base + "/lenta%d" % i for i in range(6)]
    inizio = time.monotonic()
    pages = sra.fetch_pages(_fetcher(), urls, workers=6)
    durata = time.monotonic() - inizio
    assert len(pages) == 6 and all(p.ok for p in pages)
    # seriale sarebbe >= 6 * 0.25 = 1.5s; con 6 worker resta vicino
    # alla latenza singola. Soglia larga per la CI.
    assert durata < 1.0, "nessuna sovrapposizione: %.2fs" % durata


def test_errori_per_thread_non_si_mischiano(timed_site):
    base, _ = timed_site
    urls = [base + "/ok1", "http://127.0.0.1:9/irraggiungibile",
            base + "/ok2"]
    pages = sra.fetch_pages(_fetcher(retries=0, timeout=2), urls,
                            workers=3)
    assert pages[0].ok and pages[2].ok
    assert not pages[1].ok
    assert pages[1].error == "richiesta fallita"


def test_annullamento_in_parallelo(timed_site):
    base, _ = timed_site
    stop = threading.Event()
    stop.set()
    fetcher = _fetcher(stop_event=stop)
    with pytest.raises(sra.AuditCancelled):
        sra.fetch_pages(fetcher, [base + "/a", base + "/b"],
                        workers=4, stop_event=stop)


def test_cli_workers_validato(capsys):
    assert sra.build_parser().parse_args(["x.it"]).workers == \
        sra.DEFAULT_WORKERS
    rc = sra.main(["https://x.invalid", "--workers", "0"])
    capsys.readouterr()
    assert rc == 2
    rc = sra.main(["https://x.invalid", "--workers", "99"])
    capsys.readouterr()
    assert rc == 2
