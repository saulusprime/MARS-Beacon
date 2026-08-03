# -*- coding: utf-8 -*-
"""API del server della GUI (seo_rrf_gui.py): auth, limiti, referti."""

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
def ambiente_pulito(tmp_path):
    gui.JOB = gui.Job()
    gui.STORE = gui.UserStore(tmp_path / "users.db")
    yield


def _api(base, path, payload=None, cookie=""):
    url = base + path
    if payload is None:
        req = urllib.request.Request(url)
    else:
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"})
    if cookie:
        req.add_header("Cookie", cookie)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, resp.read(), dict(resp.headers)
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(), dict(exc.headers)


def _register(base, email="paola@esempio.it", completo=False,
              nome="Paola Rossi"):
    """Registra un utente e restituisce il cookie di sessione."""
    payload = {"nome": nome, "email": email,
               "password": "segretissima", "tos": True}
    if completo:
        payload["azienda"] = "Centro Esempio"
        payload["telefono"] = "0521 123456"
    status, body, headers = _api(base, "/api/register", payload)
    assert status == 201, body
    return headers.get("Set-Cookie", "").split(";")[0]


def _attendi_stato(base, cookie, attesi, timeout=120):
    scadenza = time.time() + timeout
    snap = {}
    while time.time() < scadenza:
        _, body, _ = _api(base, "/api/status", cookie=cookie)
        snap = json.loads(body)
        if snap.get("state") in attesi:
            break
        time.sleep(0.3)
    return snap


def sra_version():
    import seo_rrf_audit
    return seo_rrf_audit.__version__


# ---------------- statici e ambiente ----------------

def test_statici_con_csp_e_traversal_negato(gui_base):
    for path, atteso in (("/", b"Audit SEO"),
                         ("/", b"Lympha"),
                         ("/app.js", b"use strict"),
                         ("/config.js", b"__PUBLIC_PATH__"),
                         ("/theme.css", b"--lt-teal"),
                         ("/tos.html", b"Condizioni di servizio"),
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
    assert env["default_embeddings_model"]


# ---------------- validazione della configurazione ----------------

def test_validazione_input(gui_base):
    cookie = _register(gui_base)
    status, body, _ = _api(gui_base, "/api/audit", {"url": ""},
                           cookie=cookie)
    assert status == 400 and b"URL" in body
    status, body, _ = _api(gui_base, "/api/audit",
                           {"url": "https://x.it", "max_pages": 9999},
                           cookie=cookie)
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


# ---------------- registrazione e accesso ----------------

def test_registrazione_valida_e_me(gui_base):
    cookie = _register(gui_base)
    status, body, _ = _api(gui_base, "/api/me", cookie=cookie)
    info = json.loads(body)
    assert status == 200 and info["authenticated"]
    assert info["user"]["email"] == "paola@esempio.it"
    assert info["user"]["profile_complete"] is False

    status, body, _ = _api(gui_base, "/api/me")
    assert not json.loads(body)["authenticated"]


def test_registrazione_rifiutata_senza_tos(gui_base):
    status, body, _ = _api(gui_base, "/api/register", {
        "nome": "Paola", "email": "p@esempio.it",
        "password": "segretissima", "tos": False})
    assert status == 400 and b"condizioni" in body


def test_registrazione_valida_campi(gui_base):
    base_payload = {"nome": "Paola", "email": "p@esempio.it",
                    "password": "segretissima", "tos": True}
    for campo, valore, errore in (
            ("nome", "", b"nome"),
            ("email", "non-una-email", b"Email"),
            ("password", "corta", b"password")):
        payload = dict(base_payload)
        payload[campo] = valore
        status, body, _ = _api(gui_base, "/api/register", payload)
        assert status == 400 and errore in body, campo


def test_email_duplicata(gui_base):
    _register(gui_base)
    status, body, _ = _api(gui_base, "/api/register", {
        "nome": "Altra", "email": "paola@esempio.it",
        "password": "unaltrapass", "tos": True})
    assert status == 409 and b"email" in body.lower()


def test_login_logout(gui_base):
    _register(gui_base)
    status, body, _ = _api(gui_base, "/api/login", {
        "email": "paola@esempio.it", "password": "sbagliata"})
    assert status == 401

    status, body, headers = _api(gui_base, "/api/login", {
        "email": "paola@esempio.it", "password": "segretissima"})
    assert status == 200
    cookie = headers.get("Set-Cookie", "").split(";")[0]

    status, _, _ = _api(gui_base, "/api/logout", {}, cookie=cookie)
    assert status == 200
    status, body, _ = _api(gui_base, "/api/me", cookie=cookie)
    assert not json.loads(body)["authenticated"]


# ---------------- gating: audit e referti ----------------

def test_audit_richiede_accesso(gui_base, site):
    status, body, _ = _api(gui_base, "/api/audit", {"url": site})
    assert status == 401
    status, _, _ = _api(gui_base, "/api/status")
    assert status == 401
    status, _, _ = _api(gui_base, "/api/report/html")
    assert status == 401


def test_referto_assente_prima_dell_audit(gui_base):
    cookie = _register(gui_base, completo=True)
    status, _, _ = _api(gui_base, "/api/report/html", cookie=cookie)
    assert status == 404


def test_ciclo_completo_referti_e_gating_profilo(gui_base, site):
    cookie = _register(gui_base)  # registrazione rapida
    status, body, _ = _api(gui_base, "/api/audit", {
        "url": site, "max_pages": 8, "delay": 0.2, "max_body": 10,
        "rrf_k": 60, "queries": "drenaggio linfatico"},
        cookie=cookie)
    assert status == 202, body

    # Un secondo utente trova il job occupato (409), non il limite.
    cookie2 = _register(gui_base, email="altro@esempio.it")
    status, _, _ = _api(gui_base, "/api/audit", {"url": site},
                        cookie=cookie2)
    assert status == 409

    snap = _attendi_stato(gui_base, cookie, ("done", "error"))
    assert snap["state"] == "done", snap.get("error")
    assert any(line.startswith("[5/5]") for line in snap["log"])
    assert snap["summary"]["pages_ok"] >= 1
    assert snap["findings"] and snap["rrf"]
    assert snap["remediation"]
    riass = snap["summary"]
    assert riass["pages_clean"] + riass["pages_flagged"] \
        + riass["pages_error"] == riass["pages_total"]

    # Registrazione rapida: il download e' negato con codice chiaro.
    status, body, _ = _api(gui_base, "/api/report/html",
                           cookie=cookie)
    assert status == 403
    assert json.loads(body)["code"] == "profile_incomplete"

    # Profilo completato: i tre referti si scaricano.
    status, _, _ = _api(gui_base, "/api/profile", {
        "azienda": "Centro Esempio", "telefono": "0521 123456"},
        cookie=cookie)
    assert status == 200
    status, body, _ = _api(gui_base, "/api/report/html",
                           cookie=cookie)
    assert status == 200 and body.startswith(b"<!DOCTYPE html>")
    status, body, _ = _api(gui_base, "/api/report/json",
                           cookie=cookie)
    assert status == 200 and json.loads(body)["scores"]
    status, body, headers = _api(
        gui_base, "/api/report/text?download=1", cookie=cookie)
    assert status == 200 and b"AUDIT" in body
    assert "attachment" in headers.get("Content-Disposition", "")


def test_limite_orario(gui_base, site):
    cookie = _register(gui_base, completo=True)
    status, _, _ = _api(gui_base, "/api/audit", {
        "url": site, "max_pages": 2, "delay": 0.0,
        "queries": "drenaggio linfatico"}, cookie=cookie)
    assert status == 202
    _attendi_stato(gui_base, cookie, ("done", "error"))

    status, body, _ = _api(gui_base, "/api/audit", {
        "url": site, "max_pages": 2, "delay": 0.0}, cookie=cookie)
    assert status == 429
    dati = json.loads(body)
    assert 0 < dati["retry_in_s"] <= gui.CHECK_INTERVAL_S
    assert "ora" in dati["error"]


def test_annullamento_audit(gui_base, site):
    cookie = _register(gui_base, completo=True)
    status, _, _ = _api(gui_base, "/api/cancel", {}, cookie=cookie)
    assert status == 409

    status, body, _ = _api(gui_base, "/api/audit", {
        "url": site, "max_pages": 8, "delay": 1.0,
        "queries": "drenaggio linfatico"}, cookie=cookie)
    assert status == 202, body
    time.sleep(0.5)
    status, _, _ = _api(gui_base, "/api/cancel", {}, cookie=cookie)
    assert status == 202

    snap = _attendi_stato(gui_base, cookie,
                          ("cancelled", "done", "error"), timeout=30)
    assert snap["state"] == "cancelled"
    assert not snap["summary"], "un audit annullato non ha risultati"

    # L'annullamento libera lo slot orario: si puo' ripartire subito.
    status, _, _ = _api(gui_base, "/api/audit", {
        "url": site, "max_pages": 2, "delay": 0.0,
        "queries": "drenaggio linfatico"}, cookie=cookie)
    assert status == 202
    snap = _attendi_stato(gui_base, cookie, ("done", "error"))
    assert snap["state"] == "done"
