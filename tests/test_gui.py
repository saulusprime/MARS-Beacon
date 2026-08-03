# -*- coding: utf-8 -*-
"""API del server della GUI (seo_rrf_gui.py)."""

import json
import threading
import time
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

import seo_rrf_gui as gui


@pytest.fixture(scope="module")
def gui_base():
    server = ThreadingHTTPServer(("127.0.0.1", 0), gui.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield "http://127.0.0.1:%d" % server.server_address[1]
    server.shutdown()


@pytest.fixture(autouse=True)
def job_pulito():
    gui.JOB = gui.Job()
    yield


def _api(base, path, payload=None):
    url = base + path
    if payload is None:
        req = urllib.request.Request(url)
    else:
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, resp.read(), dict(resp.headers)
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(), dict(exc.headers)


def test_statici_con_csp_e_traversal_negato(gui_base):
    for path, atteso in (("/", b"Audit SEO"),
                         ("/", b"Lympha"),
                         ("/app.js", b"use strict"),
                         ("/config.js", b"__PUBLIC_PATH__"),
                         ("/theme.css", b"--lt-teal"),
                         ("/brand/lympha-brand.css", b"--lt-teal"),
                         ("/brand/lympha-mark.svg", b"<svg"),
                         ("/brand/favicon.png", b"PNG")):
        status, body, headers = _api(gui_base, path)
        assert status == 200 and atteso in body
        assert "Content-Security-Policy" in headers
        assert headers.get("X-Content-Type-Options") == "nosniff"

    status, _, _ = _api(gui_base, "/../seo_rrf_audit.py")
    assert status == 404


def test_env(gui_base):
    status, body, _ = _api(gui_base, "/api/env")
    env = json.loads(body)
    assert status == 200
    assert env["tool_version"] == sra_version()
    assert env["default_max_body_mb"] == 10
    assert "embeddings_available" in env


def sra_version():
    import seo_rrf_audit
    return seo_rrf_audit.__version__


def test_validazione_input(gui_base):
    status, body, _ = _api(gui_base, "/api/audit", {"url": ""})
    assert status == 400 and b"URL" in body
    status, body, _ = _api(gui_base, "/api/audit",
                           {"url": "https://x.it", "max_pages": 9999})
    assert status == 400 and b"max_pages" in body


def test_validazione_retries():
    config, err = gui.validate_config({"url": "x.it", "retries": 5})
    assert err == "" and config["retries"] == 5
    config, _ = gui.validate_config({"url": "x.it"})
    assert config["retries"] == 2
    config, err = gui.validate_config({"url": "x.it", "retries": 99})
    assert config is None and "retries" in err


def test_validazione_concorrenti():
    config, err = gui.validate_config(
        {"url": "x.it", "competitors": "a.it\nhttps://b.it\n"})
    assert err == ""
    assert config["competitors"] == ["https://a.it", "https://b.it"]
    config, err = gui.validate_config(
        {"url": "x.it", "competitors": "a.it\nb.it\nc.it\nd.it"})
    assert config is None and "3" in err
    config, _ = gui.validate_config({"url": "x.it"})
    assert config["competitors"] == []


def test_validazione_respect_robots():
    config, err = gui.validate_config(
        {"url": "x.it", "respect_robots": True})
    assert err == "" and config["respect_robots"] is True
    config, _ = gui.validate_config({"url": "x.it"})
    assert config["respect_robots"] is False


def test_referto_assente_prima_dell_audit(gui_base):
    status, _, _ = _api(gui_base, "/api/report/html")
    assert status == 404


def test_ciclo_completo_con_409_e_referti(gui_base, site):
    status, body, _ = _api(gui_base, "/api/audit", {
        "url": site, "max_pages": 8, "delay": 0.2, "max_body": 10,
        "rrf_k": 60, "queries": "drenaggio linfatico"})
    assert status == 202, body

    status, _, _ = _api(gui_base, "/api/audit", {"url": site})
    assert status == 409

    scadenza = time.time() + 120
    snap = {}
    while time.time() < scadenza:
        _, body, _ = _api(gui_base, "/api/status")
        snap = json.loads(body)
        if snap["state"] in ("done", "error"):
            break
        time.sleep(0.5)
    assert snap["state"] == "done", snap.get("error")
    assert any(line.startswith("[5/5]") for line in snap["log"])
    assert snap["summary"]["pages_ok"] >= 1
    assert snap["findings"] and snap["rrf"]

    # Campi per i widget di sintesi (anello, tile, donut pagine).
    riass = snap["summary"]
    assert riass["pages_clean"] + riass["pages_flagged"] \
        + riass["pages_error"] == riass["pages_total"]
    assert riass["info"] >= 0

    status, body, _ = _api(gui_base, "/api/report/html")
    assert status == 200 and body.startswith(b"<!DOCTYPE html>")
    status, body, _ = _api(gui_base, "/api/report/json")
    assert status == 200 and json.loads(body)["scores"]
    status, body, headers = _api(gui_base,
                                 "/api/report/text?download=1")
    assert status == 200 and b"AUDIT" in body
    assert "attachment" in headers.get("Content-Disposition", "")
