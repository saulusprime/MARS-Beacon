# -*- coding: utf-8 -*-
"""API del server della GUI (mars_gui.py): auth, limiti, referti."""

import json
import threading
import time
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

import mars_gui as gui


def _patch(monkeypatch, name, value):
    """Monkeypatch sulla facciata e su ogni modulo marsbeacon che
    espone il nome: dopo la scomposizione (v1.58.0) conta il
    namespace del consumatore, non solo quello pubblico."""
    import mars_audit
    import marsbeacon.audits
    import marsbeacon.base
    import marsbeacon.crawler
    import marsbeacon.indexes
    import marsbeacon.render
    for modulo in (mars_audit, marsbeacon.base, marsbeacon.crawler,
                   marsbeacon.indexes, marsbeacon.audits,
                   marsbeacon.render):
        if name in vars(modulo):
            monkeypatch.setattr(modulo, name, value)


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
    import mars_audit
    return mars_audit.__version__


# ---------------- statici e ambiente ----------------

def test_statici_con_csp_e_traversal_negato(gui_base):
    for path, atteso in (("/", b"MARS Beacon"),
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

    status, _, _ = _api(gui_base, "/../mars_audit.py")
    assert status == 404


def test_env(gui_base):
    status, body, _ = _api(gui_base, "/api/env")
    env = json.loads(body)
    assert status == 200
    assert env["tool_version"] == sra_version()
    assert env["default_max_body_mb"] == 10
    assert "embeddings_available" in env
    assert env["default_embeddings_model"]
    assert isinstance(env["lighthouse_available"], bool)
    assert isinstance(env["lighthouse_reason"], str)
    if env["lighthouse_available"]:
        assert env["lighthouse_reason"] == ""
    else:
        assert env["lighthouse_reason"]
    assert "lighthouse_version" in env


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


def test_validazione_robots_mode():
    config, err = gui.validate_config({"url": "x.it"})
    assert err == "" and config["robots"] == "own", \
        "default GUI: titolarita' dichiarata nelle condizioni"
    config, err = gui.validate_config(
        {"url": "x.it", "robots": "respect"})
    assert err == "" and config["robots"] == "respect"
    config, err = gui.validate_config(
        {"url": "x.it", "robots": "force"})
    assert config is None and "responsabilita" in err
    config, err = gui.validate_config(
        {"url": "x.it", "robots": "force", "robots_ack": True})
    assert err == "" and config["robots"] == "force"
    config, err = gui.validate_config(
        {"url": "x.it", "robots": "boh"})
    assert config is None and "robots" in err


def test_validazione_market():
    config, err = gui.validate_config({"url": "x.it"})
    assert err == "" and config["market"] == "occidentale", \
        "default GUI allineato al default della CLI"
    config, err = gui.validate_config(
        {"url": "x.it", "market": "Orientale"})
    assert err == "" and config["market"] == "orientale"
    config, err = gui.validate_config(
        {"url": "x.it", "market": "lunare"})
    assert config is None and "market" in err


def test_validazione_parametri_rrf():
    config, err = gui.validate_config({"url": "x.it"})
    assert err == "" and config["top_n"] == 5
    assert config["chunk_words"] == 220
    assert config["rrf_weights"] == (1.0, 1.0)
    config, err = gui.validate_config(
        {"url": "x.it", "top_n": 3, "chunk_words": 300,
         "w_lex": 2, "w_vec": 0.5})
    assert err == "" and config["rrf_weights"] == (2.0, 0.5)
    assert config["top_n"] == 3 and config["chunk_words"] == 300
    config, err = gui.validate_config({"url": "x.it", "top_n": 99})
    assert config is None and "top_n" in err
    config, err = gui.validate_config({"url": "x.it", "w_lex": 0})
    assert config is None and "w_lex" in err


def test_validazione_judge():
    config, err = gui.validate_config({"url": "x.it"})
    assert err == "" and config["judge"] == "auto", \
        "giudizio LLM attivo di default (auto)"
    config, err = gui.validate_config(
        {"url": "x.it", "judge": "off"})
    assert err == "" and config["judge"] == "off"
    config, err = gui.validate_config(
        {"url": "x.it", "judge": "boh"})
    assert config is None and "judge" in err
    # "on" senza chiave sul server: rifiutato con motivo chiaro.
    config, err = gui.validate_config(
        {"url": "x.it", "judge": "on"})
    assert config is None and "ANTHROPIC_API_KEY" in err


# ---------------- storico e delta per utente/dominio ----------------

def _referto(scores, findings):
    return {"site": "https://mio.it", "scores": scores,
            "generated_at": "2026-08-04T10:00:00+0200",
            "findings": findings}


def test_compute_delta_punteggi_e_rilievi():
    prima = _referto(
        {"Tecnica": 50.0, "Semantica (vettoriale)": 60.0,
         "overall": 55.0},
        [{"area": "Tecnica", "severity": "critical",
          "title": "Sito non in HTTPS"},
         {"area": "Lessicale (BM25)", "severity": "warning",
          "title": "5 title non ottimizzati"},
         {"area": "Tecnica", "severity": "ok",
          "title": "Canonical presenti"}])
    dopo = _referto(
        {"Tecnica": 70.0, "Semantica (vettoriale)": 58.0,
         "overall": 64.0},
        [{"area": "Lessicale (BM25)", "severity": "warning",
          "title": "2 title non ottimizzati"},
         {"area": "Semantica (vettoriale)", "severity": "warning",
          "title": "Nessuna sezione FAQ"}])
    delta = gui.compute_delta(prima, dopo, 1000.0)
    assert delta["scores"]["Tecnica"] == 20.0
    assert delta["scores"]["Semantica (vettoriale)"] == -2.0
    assert delta["scores"]["overall"] == 9.0
    assert delta["previous_at"] == 1000.0
    # HTTPS risolto; i title restano (conteggio normalizzato);
    # la FAQ e' nuova; i rilievi "ok" non contano.
    assert [f["title"] for f in delta["resolved"]] == \
        ["Sito non in HTTPS"]
    assert [f["title"] for f in delta["new"]] == \
        ["Nessuna sezione FAQ"]


def test_store_salva_ed_esporta_il_referto(tmp_path):
    store = gui.UserStore(tmp_path / "s.db")
    token, err = store.register("Paola", "p@e.it", "segretissima")
    assert err == ""
    uid = int(store.user_by_token(token)["id"])
    store.add_audit(uid, {"site": "https://mio.it", "overall": 40},
                    '{"quale": "vecchio"}')
    store.add_audit(uid, {"site": "https://mio.it", "overall": 50},
                    '{"quale": "nuovo"}')
    store.add_audit(uid, {"site": "https://altro.it",
                          "overall": 60}, "")

    runs = store.history(uid)
    assert runs[0]["site"] == "https://altro.it"
    assert runs[0]["has_report"] is False
    assert runs[1]["has_report"] is True

    ultimo = store.last_audit_report(uid, "https://mio.it")
    assert json.loads(ultimo["report_json"])["quale"] == "nuovo"

    esport = store.audit_report(uid, int(runs[1]["id"]))
    assert esport and esport["site"] == "https://mio.it"
    # Un altro utente non vede i referti altrui.
    token2, _ = store.register("Rosa", "r@e.it", "segretissima")
    uid2 = int(store.user_by_token(token2)["id"])
    assert store.audit_report(uid2, int(runs[1]["id"])) is None


def test_migrazione_schema_audits(tmp_path):
    """Un DB creato prima della 2.10.0 acquisisce report_json."""
    import sqlite3
    path = tmp_path / "vecchio.db"
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE audits (id INTEGER PRIMARY KEY, "
                "user_id INTEGER NOT NULL, site TEXT NOT NULL, "
                "created_at REAL NOT NULL, overall REAL NOT NULL, "
                "scores TEXT NOT NULL, critical INTEGER NOT NULL, "
                "warning INTEGER NOT NULL, info INTEGER NOT NULL)")
    con.execute("INSERT INTO audits (user_id, site, created_at, "
                "overall, scores, critical, warning, info) "
                "VALUES (7, 'https://mio.it', 1.0, 42, '{}', "
                "1, 2, 3)")
    con.commit()
    con.close()

    store = gui.UserStore(path)  # migrazione all'apertura
    runs = store.history(7)
    assert runs[0]["overall"] == 42
    assert runs[0]["has_report"] is False
    store.add_audit(7, {"site": "https://mio.it", "overall": 50},
                    '{"v": 2}')
    assert store.last_audit_report(7, "https://mio.it")


def test_export_referto_storico_via_api(gui_base):
    status, _, _ = _api(gui_base, "/api/history/report?id=1")
    assert status == 401

    cookie = _register(gui_base, email="rapida@e.it")
    status, body, _ = _api(gui_base, "/api/history/report?id=1",
                           cookie=cookie)
    assert status == 403
    assert json.loads(body)["code"] == "profile_incomplete"

    cookie = _register(gui_base, email="piena@e.it", completo=True)
    token = cookie.split("=", 1)[1]
    store = gui.get_store()
    uid = int(store.user_by_token(token)["id"])
    store.add_audit(uid, {"site": "https://mio.it", "overall": 70},
                    '{"scores": {"overall": 70}}')
    audit_id = store.history(uid)[0]["id"]

    status, body, headers = _api(
        gui_base, "/api/history/report?id=%d&download=1" % audit_id,
        cookie=cookie)
    assert status == 200
    assert json.loads(body)["scores"]["overall"] == 70
    assert "attachment" in headers.get("Content-Disposition", "")

    status, _, _ = _api(gui_base, "/api/history/report?id=99999",
                        cookie=cookie)
    assert status == 404
    status, _, _ = _api(gui_base, "/api/history/report?id=boh",
                        cookie=cookie)
    assert status == 400


def test_delta_fra_due_audit_stesso_sito(gui_base, site):
    """Il secondo audit sullo stesso dominio riporta il delta."""
    cookie = _register(gui_base, email="delta@e.it",
                       completo=True)
    token = cookie.split("=", 1)[1]
    status, _, _ = _api(gui_base, "/api/audit", {
        "url": site, "max_pages": 3, "delay": 0.0,
        "queries": "drenaggio linfatico"}, cookie=cookie)
    assert status == 202
    snap = _attendi_stato(gui_base, cookie, ("done", "error"))
    assert snap["state"] == "done", snap.get("error")
    assert snap["summary"]["delta"] is None, \
        "primo audit del dominio: nessun precedente"

    uid = int(gui.get_store().user_by_token(token)["id"])
    gui.get_store().clear_check(uid)
    status, _, _ = _api(gui_base, "/api/audit", {
        "url": site, "max_pages": 3, "delay": 0.0,
        "queries": "drenaggio linfatico"}, cookie=cookie)
    assert status == 202
    snap = _attendi_stato(gui_base, cookie, ("done", "error"))
    assert snap["state"] == "done", snap.get("error")
    delta = snap["summary"]["delta"]
    assert delta is not None and delta["previous_at"] > 0
    assert delta["new"] == [] and delta["resolved"] == [], \
        "stesso sito immutato: nessun rilievo nuovo o risolto"
    assert all(v == 0 for v in delta["scores"].values())
    # Entrambe le esecuzioni sono esportabili dallo storico.
    runs = gui.get_store().history(uid)
    assert len(runs) == 2
    assert all(r["has_report"] for r in runs)
    # Dalla 2.11.0 anche i referti scaricati includono il delta.
    status, body, _ = _api(gui_base, "/api/report/text",
                           cookie=cookie)
    assert status == 200
    assert b"RISPETTO ALL'ESECUZIONE PRECEDENTE" in body


# ---------------- storico citazioni IA ----------------

def _storico_citazioni(tmp_path):
    """Tre esecuzioni per mio.it, una per altro.it, una riga rotta."""
    def riga(sito, quando, rate_a, rate_p):
        return json.dumps({
            "generated_at": quando, "site": sito,
            "overall_rate": round((rate_a + rate_p) / 2, 1),
            "providers": {
                "anthropic": {"answered": 10, "failed": 0,
                              "site_cited": int(rate_a / 10),
                              "rate": rate_a,
                              "competitors_cited": {}},
                "perplexity": {"answered": 10, "failed": 0,
                               "site_cited": int(rate_p / 10),
                               "rate": rate_p,
                               "competitors_cited": {}},
            }})
    path = tmp_path / "citazioni.jsonl"
    path.write_text("\n".join([
        riga("mio.it", "2026-07-21T06:00:00+0200", 20.0, 10.0),
        "{questa riga non e' JSON valido",
        riga("altro.it", "2026-07-24T06:00:00+0200", 50.0, 40.0),
        riga("mio.it", "2026-07-28T06:00:00+0200", 30.0, 20.0),
        riga("mio.it", "2026-08-04T06:00:00+0200", 40.0, 20.0),
    ]) + "\n", encoding="utf-8")
    return path


def test_api_citazioni_richiede_accesso(gui_base):
    status, _, _ = _api(gui_base, "/api/citations")
    assert status == 401


def test_api_citazioni_raggruppa_per_sito(gui_base, tmp_path,
                                          monkeypatch):
    monkeypatch.setattr(gui, "CITATIONS_HISTORY",
                        _storico_citazioni(tmp_path))
    cookie = _register(gui_base)
    status, body, _ = _api(gui_base, "/api/citations",
                           cookie=cookie)
    assert status == 200
    sites = json.loads(body)["sites"]
    assert [s["site"] for s in sites] == ["mio.it", "altro.it"]
    corse = sites[0]["runs"]
    assert len(corse) == 3, "la riga malformata va ignorata"
    assert corse[-1]["providers"]["anthropic"]["rate"] == 40.0
    assert corse[0]["generated_at"].startswith("2026-07-21")


def test_api_citazioni_senza_storico(gui_base, tmp_path,
                                     monkeypatch):
    monkeypatch.setattr(gui, "CITATIONS_HISTORY",
                        tmp_path / "inesistente.jsonl")
    cookie = _register(gui_base)
    status, body, _ = _api(gui_base, "/api/citations",
                           cookie=cookie)
    assert status == 200
    assert json.loads(body)["sites"] == []


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
    # Ogni rilievo porta la tipologia MARS; il sito fixture in
    # http garantisce almeno un rilievo security.
    pillars = {f.get("pillar") for f in snap["findings"]}
    assert "security" in pillars
    assert pillars <= {"meta-fusion", "accessibility", "ranking",
                       "security"}
    riass = snap["summary"]
    assert riass["pages_clean"] + riass["pages_flagged"] \
        + riass["pages_error"] == riass["pages_total"]
    cit = riass["citability"]
    assert cit["market"] == "occidentale"
    assert len(cit["profiles"]) == 4
    azioni = riass["citability_actions"]
    assert azioni, "sito difettoso: azioni prioritarie attese"
    assert azioni[0]["best_profile"] in cit["market_weights"]
    assert "index_gain" in snap["remediation"][0], \
        "piano annotato coi guadagni di citabilita'"
    assert riass["judge"]["status"] == "skipped", \
        "senza chiave il giudizio auto si salta, audit offline"

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
    status, body, headers = _api(gui_base, "/api/report/html",
                                 cookie=cookie)
    assert status == 200 and body.startswith(b"<!DOCTYPE html>")
    # Il referto HTML porta JavaScript inline (treemap e grafo
    # interattivi): solo per questa risposta la CSP lo ammette.
    assert "script-src 'unsafe-inline'" \
        in headers.get("Content-Security-Policy", "")
    assert b"<script>" in body
    status, body, _ = _api(gui_base, "/api/report/json",
                           cookie=cookie)
    assert status == 200 and json.loads(body)["scores"]
    status, body, headers = _api(
        gui_base, "/api/report/text?download=1", cookie=cookie)
    assert status == 200 and b"MARS BEACON" in body
    assert "attachment" in headers.get("Content-Disposition", "")
    assert "script-src" not in headers.get(
        "Content-Security-Policy", "")


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

    # Il limite e' per singolo account, non complessivo: un secondo
    # utente non e' bloccato dal check appena fatto dal primo.
    cookie2 = _register(gui_base, email="carla@esempio.it",
                        completo=True, nome="Carla Bruni")
    status, body, _ = _api(gui_base, "/api/audit", {
        "url": site, "max_pages": 2, "delay": 0.0,
        "queries": "drenaggio linfatico"}, cookie=cookie2)
    assert status == 202, body
    _attendi_stato(gui_base, cookie2, ("done", "error"))

    # E il 429 del primo utente resta il suo, non del secondo.
    status, _, _ = _api(gui_base, "/api/audit", {
        "url": site, "max_pages": 2, "delay": 0.0}, cookie=cookie)
    assert status == 429


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


# ---------------- storico e avanzamento push ----------------

def test_storico_per_utente(gui_base, site):
    status, _, _ = _api(gui_base, "/api/history")
    assert status == 401

    cookie = _register(gui_base, completo=True)
    status, body, _ = _api(gui_base, "/api/history", cookie=cookie)
    assert status == 200 and json.loads(body)["runs"] == []

    status, _, _ = _api(gui_base, "/api/audit", {
        "url": site, "max_pages": 2, "delay": 0.0,
        "queries": "drenaggio linfatico"}, cookie=cookie)
    assert status == 202
    snap = _attendi_stato(gui_base, cookie, ("done", "error"))
    assert snap["state"] == "done"

    _, body, _ = _api(gui_base, "/api/history", cookie=cookie)
    runs = json.loads(body)["runs"]
    assert len(runs) == 1
    assert runs[0]["site"].startswith("http://127.0.0.1")
    assert 0 <= runs[0]["overall"] <= 100
    assert runs[0]["scores"]
    assert runs[0]["critical"] >= 1

    # Lo storico e' per utente: un altro account non vede nulla.
    cookie2 = _register(gui_base, email="altro@esempio.it")
    _, body, _ = _api(gui_base, "/api/history", cookie=cookie2)
    assert json.loads(body)["runs"] == []


def test_eventi_sse(gui_base):
    status, _, _ = _api(gui_base, "/api/events")
    assert status == 401

    cookie = _register(gui_base)
    req = urllib.request.Request(gui_base + "/api/events")
    req.add_header("Cookie", cookie)
    with urllib.request.urlopen(req, timeout=10) as resp:
        ctype = resp.headers.get("Content-Type", "")
        assert ctype.startswith("text/event-stream")
        body = resp.read()  # stato idle: un evento e chiusura
    assert body.startswith(b"data: ")
    snap = json.loads(body[len(b"data: "):].strip())
    assert snap["state"] == "idle"


def test_eventi_citazioni_nel_grafico(gui_base, tmp_path,
                                      monkeypatch):
    monkeypatch.setattr(gui, "CITATIONS_HISTORY",
                        _storico_citazioni(tmp_path))
    eventi = tmp_path / "eventi.jsonl"
    eventi.write_text(
        json.dumps({"date": "2026-07-25",
                    "label": "Pubblicate le FAQ"}) + "\n"
        "{riga rotta\n" +
        json.dumps({"date": "2026-08-01", "label": "Nuovo blog",
                    "site": "mio.it"}) + "\n", encoding="utf-8")
    cookie = _register(gui_base)
    status, body, _ = _api(gui_base, "/api/citations",
                           cookie=cookie)
    assert status == 200
    data = json.loads(body)
    assert [e["label"] for e in data["events"]] == \
        ["Pubblicate le FAQ", "Nuovo blog"]
    assert data["events"][1]["site"] == "mio.it"


def _referto_confronto(overall, findings):
    return json.dumps({
        "site": "https://mio.it",
        "generated_at": "2026-08-04T10:00:00+0200",
        "scores": {"Tecnica": overall, "overall": overall},
        "findings": findings})


def test_confronto_fra_due_audit_scelti(gui_base):
    status, _, _ = _api(gui_base, "/api/history/compare?a=1&b=2")
    assert status == 401

    cookie = _register(gui_base, email="cmp@e.it")
    token = cookie.split("=", 1)[1]
    store = gui.get_store()
    uid = int(store.user_by_token(token)["id"])
    store.add_audit(uid, {"site": "https://mio.it",
                          "overall": 40},
                    _referto_confronto(40.0, [
                        {"area": "Tecnica", "severity": "critical",
                         "title": "Sito non in HTTPS"}]))
    store.add_audit(uid, {"site": "https://mio.it",
                          "overall": 60},
                    _referto_confronto(60.0, []))
    store.add_audit(uid, {"site": "https://altro.it",
                          "overall": 50}, _referto_confronto(50, []))
    runs = store.history(uid)  # dal piu' recente
    id_vecchio = runs[2]["id"]
    id_nuovo = runs[1]["id"]
    id_altro = runs[0]["id"]

    # Ordine invertito nei parametri: il server ordina per data.
    status, body, _ = _api(
        gui_base, "/api/history/compare?a=%d&b=%d"
        % (id_nuovo, id_vecchio), cookie=cookie)
    assert status == 200
    data = json.loads(body)
    assert data["delta"]["scores"]["overall"] == 20.0
    assert [f["title"] for f in data["delta"]["resolved"]] == \
        ["Sito non in HTTPS"]
    assert data["delta"]["new"] == []

    status, _, _ = _api(gui_base, "/api/history/compare?a=%d&b=%d"
                        % (id_vecchio, id_altro), cookie=cookie)
    assert status == 400, "siti diversi non confrontabili"
    status, _, _ = _api(gui_base, "/api/history/compare?a=%d&b=%d"
                        % (id_vecchio, id_vecchio), cookie=cookie)
    assert status == 404, "stesso audit due volte"
    status, _, _ = _api(gui_base, "/api/history/compare?a=x&b=y",
                        cookie=cookie)
    assert status == 400


def test_aggiunta_evento_via_api(gui_base, tmp_path, monkeypatch):
    monkeypatch.setattr(gui, "CITATIONS_HISTORY",
                        tmp_path / "citazioni.jsonl")
    status, _, _ = _api(gui_base, "/api/citations/events",
                        {"date": "2026-08-04", "label": "x"})
    assert status == 401

    cookie = _register(gui_base, email="eventi@e.it")
    status, _, _ = _api(gui_base, "/api/citations/events",
                        {"date": "4 agosto", "label": "x"},
                        cookie=cookie)
    assert status == 400
    status, _, _ = _api(gui_base, "/api/citations/events",
                        {"date": "2026-08-04", "label": ""},
                        cookie=cookie)
    assert status == 400

    status, body, _ = _api(gui_base, "/api/citations/events",
                           {"date": "2026-08-04",
                            "label": "Pubblicate le FAQ",
                            "site": "mio.it"}, cookie=cookie)
    assert status == 201
    salvato = (tmp_path / "eventi.jsonl").read_text(
        encoding="utf-8")
    assert "Pubblicate le FAQ" in salvato

    status, body, _ = _api(gui_base, "/api/citations",
                           cookie=cookie)
    data = json.loads(body)
    assert data["events"][0]["label"] == "Pubblicate le FAQ"
    assert data["events"][0]["site"] == "mio.it"


# ---------------- Lighthouse nella GUI (v2.24.0) ------------------

def test_validazione_lighthouse(gui_base, monkeypatch):
    cookie = _register(gui_base, email="lhval@esempio.it")
    status, body, _ = _api(gui_base, "/api/audit",
                           {"url": "https://x.it",
                            "lighthouse": "forse"}, cookie=cookie)
    assert status == 400 and b"lighthouse" in body
    status, body, _ = _api(gui_base, "/api/audit",
                           {"url": "https://x.it",
                            "lighthouse_pages": 99}, cookie=cookie)
    assert status == 400 and b"lighthouse_pages" in body
    status, body, _ = _api(gui_base, "/api/audit",
                           {"url": "https://x.it",
                            "lighthouse_device": "tablet"},
                           cookie=cookie)
    assert status == 400 and b"lighthouse_device" in body
    _patch(monkeypatch, "lighthouse_unavailable",
                        lambda: "Node assente (finto)")
    status, body, _ = _api(gui_base, "/api/audit",
                           {"url": "https://x.it",
                            "lighthouse": "always"}, cookie=cookie)
    assert status == 400 and b"finto" in body


def test_lighthouse_nei_risultati_gui(gui_base, site, monkeypatch):
    import mars_audit as sra

    def lighthouse_finto(base, pages, mode="off", n_pages=3,
                         device="mobile", delay=0.5,
                         verbose=False, stop_event=None,
                         timeout_s=120):
        rilievo = sra.Finding(
            sra.AREA_LIGHTHOUSE, sra.SEV_WARNING,
            "Lighthouse: rilievo finto",
            pillar=sra.PILLAR_SEC,
            key="lh.best-practices.finto",
            params={"audit": "finto", "score": 0.3})
        return {"status": "ok", "mode": mode, "device": device,
                "results": [{"url": base, "lhr": {
                    "categories": {"performance": {
                        "title": "Prestazioni", "score": 0.8}},
                    "audits": {"largest-contentful-paint": {
                        "numericValue": 2000.0,
                        "displayValue": "2,0 s"}}}}],
                "errors": [], "findings": [rilievo]}

    _patch(monkeypatch, "run_lighthouse", lighthouse_finto)
    cookie = _register(gui_base, email="lhgui@esempio.it",
                       completo=True)
    status, _, _ = _api(gui_base, "/api/audit", {
        "url": site, "max_pages": 2, "delay": 0.0,
        "queries": "drenaggio linfatico",
        "lighthouse": "auto"}, cookie=cookie)
    assert status == 202
    snap = _attendi_stato(gui_base, cookie, ("done", "error"))
    assert snap["state"] == "done"
    # Il rilievo Lighthouse arriva col suo pillar per lo
    # smistamento nelle fisarmoniche (badge via chiave lh.*).
    lh = [f for f in snap["findings"]
          if str(f.get("key", "")).startswith("lh.")]
    assert lh and lh[0]["pillar"] == sra.PILLAR_SEC
    assert lh[0]["area"] == sra.AREA_LIGHTHOUSE
    # Sesta area nei punteggi e blocco lighthouse in sintesi.
    assert snap["summary"]["scores"][sra.AREA_LIGHTHOUSE] == 80.0
    assert snap["summary"]["lighthouse"]["status"] == "ok"
    assert snap["summary"]["lighthouse"]["device"] == "mobile"
    # Pannello CWV in sintesi: metrica col verdetto dalle soglie.
    metrica = snap["summary"]["lighthouse"]["metrics"][0]
    assert metrica["label"] == "LCP"
    assert metrica["verdict"] == "buono"
    assert metrica["display"] == "2,0 s"


def test_db_path_da_ambiente(tmp_path):
    """MARS_GUI_DB sposta il database (deploy systemd: /opt in
    sola lettura, DB nella StateDirectory)."""
    import os
    import subprocess
    import sys
    from pathlib import Path
    destinazione = tmp_path / "altrove.db"
    esito = subprocess.run(
        [sys.executable, "-c",
         "import mars_gui; print(mars_gui.DB_PATH)"],
        env={**os.environ, "MARS_GUI_DB": str(destinazione)},
        capture_output=True, text=True,
        cwd=str(Path(gui.__file__).resolve().parent))
    assert esito.returncode == 0, esito.stderr
    assert esito.stdout.strip() == str(destinazione)


# ------------- ancora di realta' nella GUI (v2.29.0) --------------

def test_validazione_search_check(gui_base):
    cookie = _register(gui_base, email="scval@esempio.it")
    status, body, _ = _api(gui_base, "/api/audit",
                           {"url": "https://x.it",
                            "search_check": "forse"},
                           cookie=cookie)
    assert status == 400 and b"search_check" in body
    # 'on' senza chiave (il conftest la rimuove): motivo dichiarato.
    status, body, _ = _api(gui_base, "/api/audit",
                           {"url": "https://x.it",
                            "search_check": "on"}, cookie=cookie)
    assert status == 400 and b"BRAVE_API_KEY" in body


def test_search_check_nei_risultati_gui(gui_base, site,
                                        monkeypatch):
    import mars_audit as sra

    def ancora_finta(base, results, mode="auto", verbose=False):
        return {"status": "ok", "engine": "brave", "site": "x",
                "top_n": 20, "found": 1,
                "note": sra.SEARCH_CHECK_NOTE,
                "queries": [{"query": "drenaggio",
                             "rrf_covered": True,
                             "rrf_consensus": 3,
                             "position": 4, "url": "u"}]}

    _patch(monkeypatch, "run_search_check", ancora_finta)
    cookie = _register(gui_base, email="scgui@esempio.it",
                       completo=True)
    status, _, _ = _api(gui_base, "/api/audit", {
        "url": site, "max_pages": 2, "delay": 0.0,
        "queries": "drenaggio linfatico"}, cookie=cookie)
    assert status == 202
    snap = _attendi_stato(gui_base, cookie, ("done", "error"))
    assert snap["state"] == "done"
    blocco = snap["summary"]["search_check"]
    assert blocco["status"] == "ok" and blocco["found"] == 1
    assert blocco["queries"][0]["position"] == 4
    # La sezione arriva anche nei referti scaricabili.
    status, body, _ = _api(gui_base, "/api/report/text",
                           cookie=cookie)
    assert status == 200 and b"ANCORA DI REALTA'" in body


def test_env_search_check(gui_base):
    _, body, _ = _api(gui_base, "/api/env")
    env = json.loads(body)
    assert isinstance(env["search_check_available"], bool)
    if env["search_check_available"]:
        assert env["search_check_reason"] == ""
    else:
        assert "BRAVE_API_KEY" in env["search_check_reason"]
