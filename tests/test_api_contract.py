# -*- coding: utf-8 -*-
"""Contratto API (P1 API-first, Fase 1): registro, spec, validazione.

Il registro dichiarativo delle rotte (marsbeacon/api.py) e' l'unica
fonte di verita': questi test verificano che la spec generata lo
copra per intero, che ogni schema sia JSON Schema valido
(``jsonschema``, solo in requirements-dev), che lo snapshot
``docs/openapi.json`` coincida col generato (pattern golden,
rigenerazione con MARS_RIGENERA_GOLDEN=1) e che le risposte REALI
del server validino contro gli schemi del registro.
"""

import json
import os
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import jsonschema
import pytest

import mars_gui as gui
from marsbeacon import api

GOLDEN_SPEC = os.path.join(os.path.dirname(__file__), os.pardir,
                           "docs", "openapi.json")


# ------------------------- registro e spec ------------------------

def test_spec_copre_il_registro():
    spec = api.openapi_spec()
    assert spec["openapi"] == "3.1.0"
    assert spec["info"]["version"] == api.API_CONTRACT_VERSION
    dichiarate = {(r.method, r.path) for r in api.ROUTES}
    generate = {
        (metodo.upper(), percorso)
        for percorso, operazioni in spec["paths"].items()
        for metodo in operazioni}
    assert generate == dichiarate
    for percorso, operazioni in spec["paths"].items():
        for operazione in operazioni.values():
            assert operazione["responses"], percorso


def test_cookie_di_sessione_coerente_col_server():
    assert api.SESSION_COOKIE_NAME == gui.SESSION_COOKIE
    schemi = api.openapi_spec()["components"]["securitySchemes"]
    assert schemi["cookieSession"]["name"] == gui.SESSION_COOKIE


def test_schemi_del_registro_sono_json_schema_validi():
    per_schema = []
    for rotta in api.ROUTES:
        if rotta.request_schema is not None:
            per_schema.append((rotta.path, rotta.request_schema))
        for stato, dettaglio in rotta.responses.items():
            if dettaglio.get("schema") is not None:
                per_schema.append(
                    ("%s %s" % (rotta.path, stato),
                     dettaglio["schema"]))
    assert per_schema
    for dove, schema in per_schema:
        jsonschema.Draft202012Validator.check_schema(schema)


def test_estensioni_interne_fuori_dalla_spec():
    # x-errore serve al validatore runtime, non ai client.
    assert "x-errore" not in json.dumps(api.openapi_spec())


def test_golden_openapi():
    reso = json.dumps(api.openapi_spec(), indent=2,
                      ensure_ascii=False) + "\n"
    if os.environ.get("MARS_RIGENERA_GOLDEN"):
        with open(GOLDEN_SPEC, "w", encoding="utf-8") as handle:
            handle.write(reso)
        pytest.skip("golden openapi rigenerato: rivedere il diff")
    with open(GOLDEN_SPEC, encoding="utf-8") as handle:
        atteso = handle.read()
    assert reso == atteso, (
        "docs/openapi.json non coincide con la spec generata dal "
        "registro. Se il cambiamento del contratto e' voluto: "
        "MARS_RIGENERA_GOLDEN=1 pytest tests/test_api_contract.py "
        "e revisione del diff (valutare il bump di "
        "API_CONTRACT_VERSION).")


# ---------------------- validatore runtime ------------------------

def _rotta_eventi():
    return api.route_for("POST", "/api/citations/events")


def test_validatore_payload_valido():
    assert api.validate_request(
        _rotta_eventi(),
        {"date": "2026-08-06", "label": "pubblicate le FAQ"}) == []
    assert api.validate_request(
        _rotta_eventi(),
        {"date": "2026-08-06", "label": "x",
         "site": "esempio.test"}) == []


def test_validatore_messaggi_storici_via_x_errore():
    errori = api.validate_request(
        _rotta_eventi(), {"date": "06/08/2026", "label": "ok"})
    assert errori == ["Data non valida: usa AAAA-MM-GG."]
    errori = api.validate_request(
        _rotta_eventi(), {"date": "2026-08-06", "label": "x" * 121})
    assert errori == ["Etichetta mancante o troppo lunga "
                      "(max 120)."]
    errori = api.validate_request(
        _rotta_eventi(), {"date": "2026-08-06", "label": ""})
    assert errori == ["Etichetta mancante o troppo lunga "
                      "(max 120)."]
    # campo obbligatorio assente: stesso messaggio dichiarato
    errori = api.validate_request(
        _rotta_eventi(), {"date": "2026-08-06"})
    assert errori == ["Etichetta mancante o troppo lunga "
                      "(max 120)."]


def test_validatore_campi_sconosciuti_e_tipi():
    errori = api.validate_request(
        _rotta_eventi(),
        {"date": "2026-08-06", "label": "ok", "extra": 1})
    assert any("Campi sconosciuti" in e for e in errori)
    errori = api.validate_request(
        _rotta_eventi(), {"date": 20260806, "label": "ok"})
    assert errori == ["Data non valida: usa AAAA-MM-GG."]
    # rotta senza schema di richiesta: sempre valida
    assert api.validate_request(
        api.route_for("POST", "/api/cancel"), {"x": 1}) == []


# ------------------- contract test sul server ---------------------

@pytest.fixture(scope="module")
def base():
    server = ThreadingHTTPServer(("127.0.0.1", 0), gui.Handler)
    thread = threading.Thread(target=server.serve_forever,
                              daemon=True)
    thread.start()
    yield "http://127.0.0.1:%d" % server.server_address[1]
    server.shutdown()


@pytest.fixture(autouse=True)
def ambiente_pulito(tmp_path):
    gui.JOB = gui.Job()
    gui.STORE = gui.UserStore(tmp_path / "users.db")
    gui.CITATIONS_HISTORY = tmp_path / "citazioni.jsonl"
    yield


def _api(base_url, path, payload=None, cookie=""):
    url = base_url + path
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
            return (resp.status, json.loads(resp.read()),
                    dict(resp.headers))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read()), dict(exc.headers)


def _registra(base_url, email="paola@esempio.it", completo=False):
    payload = {"nome": "Paola Rossi", "email": email,
               "password": "segretissima", "tos": True}
    if completo:
        payload.update(azienda="Centro Esempio",
                       telefono="0521 123456")
    stato, _, headers = _api(base_url, "/api/register", payload)
    assert stato == 201
    return headers.get("Set-Cookie", "").split(";")[0]


def _conforme(metodo, percorso, stato, corpo):
    """La risposta reale valida contro lo schema del registro."""
    rotta = api.route_for(metodo, percorso)
    assert rotta is not None, percorso
    dettaglio = rotta.responses.get(stato)
    assert dettaglio is not None, (percorso, stato)
    jsonschema.validate(corpo, dettaglio["schema"])


def test_contract_openapi_servita(base):
    stato, corpo, _ = _api(base, "/api/v1/openapi.json")
    assert stato == 200
    assert corpo == api.openapi_spec()


def test_contract_env(base):
    stato, corpo, _ = _api(base, "/api/env")
    assert stato == 200
    _conforme("GET", "/api/env", 200, corpo)


def test_contract_me_anonimo_e_autenticato(base):
    stato, corpo, _ = _api(base, "/api/me")
    assert (stato, corpo["authenticated"]) == (200, False)
    _conforme("GET", "/api/me", 200, corpo)
    cookie = _registra(base)
    stato, corpo, _ = _api(base, "/api/me", cookie=cookie)
    assert (stato, corpo["authenticated"]) == (200, True)
    _conforme("GET", "/api/me", 200, corpo)


def test_contract_cancel(base):
    stato, corpo, _ = _api(base, "/api/cancel", payload={})
    assert stato == 401
    _conforme("POST", "/api/cancel", 401, corpo)
    cookie = _registra(base)
    stato, corpo, _ = _api(base, "/api/cancel", payload={},
                           cookie=cookie)
    assert stato == 409  # nessun audit in corso
    _conforme("POST", "/api/cancel", 409, corpo)


def test_contract_eventi_citazioni(base):
    cookie = _registra(base)
    stato, corpo, _ = _api(base, "/api/citations/events",
                           {"date": "2026-08-06",
                            "label": "pubblicate le FAQ"},
                           cookie=cookie)
    assert stato == 201
    _conforme("POST", "/api/citations/events", 201, corpo)
    stato, corpo, _ = _api(base, "/api/citations/events",
                           {"date": "06/08/2026", "label": "x"},
                           cookie=cookie)
    assert stato == 400
    assert corpo["error"] == "Data non valida: usa AAAA-MM-GG."
    _conforme("POST", "/api/citations/events", 400, corpo)
    stato, corpo, _ = _api(base, "/api/citations/events",
                           {"date": "2026-08-06",
                            "label": "x" * 121},
                           cookie=cookie)
    assert stato == 400
    assert corpo["error"] == ("Etichetta mancante o troppo lunga "
                              "(max 120).")


def test_contract_account_registrazione_login_logout(base):
    stato, corpo, _ = _api(base, "/api/register",
                           {"nome": "Paola Rossi",
                            "email": "p@esempio.it",
                            "password": "segretissima"})
    assert stato == 400  # tos mancante
    _conforme("POST", "/api/register", 400, corpo)
    stato, corpo, headers = _api(base, "/api/register",
                                 {"nome": "Paola Rossi",
                                  "email": "p@esempio.it",
                                  "password": "segretissima",
                                  "tos": True})
    assert stato == 201
    _conforme("POST", "/api/register", 201, corpo)
    assert "Set-Cookie" in headers
    stato, corpo, _ = _api(base, "/api/register",
                           {"nome": "Paola Rossi",
                            "email": "p@esempio.it",
                            "password": "segretissima",
                            "tos": True})
    assert stato == 409  # email gia' registrata
    _conforme("POST", "/api/register", 409, corpo)
    stato, corpo, headers = _api(base, "/api/login",
                                 {"email": "p@esempio.it",
                                  "password": "segretissima"})
    assert stato == 200
    _conforme("POST", "/api/login", 200, corpo)
    assert "Set-Cookie" in headers
    cookie = headers.get("Set-Cookie", "").split(";")[0]
    stato, corpo, _ = _api(base, "/api/login",
                           {"email": "p@esempio.it",
                            "password": "sbagliata"})
    assert stato == 401
    _conforme("POST", "/api/login", 401, corpo)
    stato, corpo, _ = _api(base, "/api/logout", payload={},
                           cookie=cookie)
    assert stato == 200
    _conforme("POST", "/api/logout", 200, corpo)


def test_contract_profile(base):
    stato, corpo, _ = _api(base, "/api/profile",
                           {"azienda": "x", "telefono": "y"})
    assert stato == 401
    _conforme("POST", "/api/profile", 401, corpo)
    cookie = _registra(base)
    stato, corpo, _ = _api(base, "/api/profile",
                           {"azienda": "", "telefono": ""},
                           cookie=cookie)
    assert stato == 400
    _conforme("POST", "/api/profile", 400, corpo)
    stato, corpo, _ = _api(base, "/api/profile",
                           {"azienda": "Centro Esempio",
                            "telefono": "0521 123456"},
                           cookie=cookie)
    assert stato == 200
    _conforme("POST", "/api/profile", 200, corpo)
    assert corpo["user"]["profile_complete"] is True


def test_contract_status_history_citations(base):
    for percorso in ("/api/status", "/api/history",
                     "/api/citations"):
        stato, corpo, _ = _api(base, percorso)
        assert stato == 401, percorso
        _conforme("GET", percorso, 401, corpo)
    cookie = _registra(base)
    stato, corpo, _ = _api(base, "/api/status", cookie=cookie)
    assert (stato, corpo["state"]) == (200, "idle")
    _conforme("GET", "/api/status", 200, corpo)
    stato, corpo, _ = _api(base, "/api/history", cookie=cookie)
    assert (stato, corpo["runs"]) == (200, [])
    _conforme("GET", "/api/history", 200, corpo)
    stato, corpo, _ = _api(base, "/api/citations", cookie=cookie)
    assert stato == 200
    _conforme("GET", "/api/citations", 200, corpo)


def test_contract_referti_e_storico_protetti(base):
    stato, corpo, _ = _api(base, "/api/report/html")
    assert stato == 401
    _conforme("GET", "/api/report/{formato}", 401, corpo)
    cookie = _registra(base)  # profilo incompleto
    stato, corpo, _ = _api(base, "/api/report/html", cookie=cookie)
    assert (stato, corpo["code"]) == (403, "profile_incomplete")
    _conforme("GET", "/api/report/{formato}", 403, corpo)
    stato, corpo, _ = _api(base, "/api/history/report?id=1",
                           cookie=cookie)
    assert stato == 403
    _conforme("GET", "/api/history/report", 403, corpo)
    completo = _registra(base, email="c@esempio.it",
                         completo=True)
    stato, corpo, _ = _api(base, "/api/report/html",
                           cookie=completo)
    assert stato == 404  # nessun audit concluso
    _conforme("GET", "/api/report/{formato}", 404, corpo)
    stato, corpo, _ = _api(base, "/api/history/report?id=abc",
                           cookie=completo)
    assert stato == 400
    _conforme("GET", "/api/history/report", 400, corpo)
    stato, corpo, _ = _api(base, "/api/history/report?id=999",
                           cookie=completo)
    assert stato == 404
    _conforme("GET", "/api/history/report", 404, corpo)
    stato, corpo, _ = _api(base, "/api/history/compare",
                           cookie=completo)
    assert stato == 400
    _conforme("GET", "/api/history/compare", 400, corpo)
    stato, corpo, _ = _api(base, "/api/history/compare?a=1&b=2",
                           cookie=completo)
    assert stato == 404
    _conforme("GET", "/api/history/compare", 404, corpo)


def test_contract_audit_ed_eventi(base):
    stato, corpo, _ = _api(base, "/api/audit", {"url": "x.it"})
    assert stato == 401
    _conforme("POST", "/api/audit", 401, corpo)
    stato, corpo, _ = _api(base, "/api/events")
    assert stato == 401
    _conforme("GET", "/api/events", 401, corpo)
    cookie = _registra(base)
    stato, corpo, _ = _api(base, "/api/audit", {}, cookie=cookie)
    assert (stato, corpo["error"]) == (400, "URL mancante.")
    _conforme("POST", "/api/audit", 400, corpo)
    stato, corpo, _ = _api(base, "/api/audit",
                           {"url": "x.it", "render": "boh"},
                           cookie=cookie)
    assert stato == 400
    assert "render" in corpo["error"]
    _conforme("POST", "/api/audit", 400, corpo)


# ------------- parita' CLI-API (lang, soglie, GSC, gate) ----------

def test_validate_config_parita_cli_api():
    base_cfg = {"url": "esempio.test"}
    cfg, err = gui.validate_config(dict(base_cfg))
    assert err == "" and cfg["lang"] == "it"
    assert cfg["soglie"] == {} and cfg["fail_under"] is None

    cfg, err = gui.validate_config(
        {**base_cfg, "lang": "fr", "fail_under": 70,
         "soglie": {"title_min": 25}})
    assert err == ""
    assert cfg["lang"] == "fr"
    assert cfg["fail_under"] == 70.0
    assert cfg["soglie"] == {"title_min": 25}

    _, err = gui.validate_config({**base_cfg, "lang": "xx"})
    assert err == "Valore non valido per 'lang'."
    _, err = gui.validate_config({**base_cfg, "fail_under": 101})
    assert err == "Valore non valido per 'fail_under'."
    _, err = gui.validate_config({**base_cfg, "soglie": [1]})
    assert err == "Il campo 'soglie' vuole un oggetto."
    _, err = gui.validate_config(
        {**base_cfg, "soglie": {"inventata": 1}})
    assert "Soglia sconosciuta" in err
    _, err = gui.validate_config(
        {**base_cfg, "soglie": {"title_min": 70}})
    assert "deve restare minore" in err


def test_validate_config_queries_gsc():
    csv_gsc = ("Query piu' frequenti,Clic,Impressioni\n"
               "drenaggio linfatico,120,1500\n"
               "linfodrenaggio costi,80,900\n"
               "drenaggio linfatico,10,50\n")
    cfg, err = gui.validate_config(
        {"url": "esempio.test", "queries_gsc": csv_gsc})
    assert err == ""
    assert cfg["queries"] == ["drenaggio linfatico",
                              "linfodrenaggio costi"]

    _, err = gui.validate_config(
        {"url": "esempio.test", "queries": "una query",
         "queries_gsc": csv_gsc})
    assert "non sono combinabili" in err
    _, err = gui.validate_config(
        {"url": "esempio.test", "queries_gsc": "Query\n"})
    assert "Nessuna query utilizzabile" in err


def test_parse_gsc_queries_da_testo():
    import mars_audit as sra
    testo = ("﻿Query;Clic;Impressioni\n"
             "seconda;5;100\nprima;50;10\n")
    assert sra.parse_gsc_queries(testo) == ["prima", "seconda"]
    assert sra.parse_gsc_queries("") == []


def _attendi(base_url, cookie, attesi, timeout=120):
    import time as _time
    scadenza = _time.time() + timeout
    snap = {}
    while _time.time() < scadenza:
        _, snap, _ = _api(base_url, "/api/status", cookie=cookie)
        if snap.get("state") in attesi:
            break
        _time.sleep(0.3)
    return snap


def test_contract_audit_e2e_parita(base, site):
    """Audit reale sul sito fixture con lingua, soglie e gate:
    la sintesi echeggia tutto e i referti rispettano lingua e
    soglie personalizzate."""
    cookie = _registra(base, email="parita@esempio.it",
                       completo=True)
    stato, corpo, _ = _api(
        base, "/api/audit",
        {"url": site, "max_pages": 4, "delay": 0,
         "lighthouse": "off", "lang": "en",
         "soglie": {"title_min": 190, "title_max": 195},
         "fail_under": 100},
        cookie=cookie)
    assert (stato, corpo) == (202, {"ok": True})
    snap = _attendi(base, cookie, ("done", "error"))
    assert snap["state"] == "done", snap.get("error")
    _conforme("GET", "/api/status", 200, snap)

    sintesi = snap["summary"]
    assert sintesi["lang"] == "en"
    assert sintesi["thresholds"] == {"title_min": 190,
                                     "title_max": 195}
    assert sintesi["fail_under"] == 100.0
    assert sintesi["gate_passed"] is False

    stato, testo, _ = _api_grezza(base, "/api/report/text",
                                  cookie=cookie)
    assert stato == 200
    assert "Pages analysed" in testo
    assert "190-195 characters" in testo
    stato, referto_json, _ = _api_grezza(base, "/api/report/json",
                                         cookie=cookie)
    assert stato == 200
    assert json.loads(referto_json)["thresholds"] == {
        "title_min": 190, "title_max": 195}
    # ripristino verificato: i default non sono rimasti alterati
    import mars_audit as sra
    assert sra.TITLE_MIN == 30 and sra.TITLE_MAX == 65


def _api_grezza(base_url, path, cookie=""):
    req = urllib.request.Request(base_url + path)
    if cookie:
        req.add_header("Cookie", cookie)
    try:
        with urllib.request.urlopen(req) as resp:
            return (resp.status, resp.read().decode("utf-8"),
                    dict(resp.headers))
    except urllib.error.HTTPError as exc:
        return (exc.code, exc.read().decode("utf-8"),
                dict(exc.headers))


# ------------------- documentazione Scalar (/api/docs) ------------

def test_contract_docs_scalar(base):
    stato, corpo, headers = _api_grezza(base, "/api/docs")
    assert stato == 200
    assert headers.get("Content-Type", "").startswith("text/html")
    # punta alla spec generata e al bundle vendorizzato
    assert 'data-url="/api/v1/openapi.json"' in corpo
    assert "/vendor/scalar/standalone.js" in corpo
    # font predefiniti (fonts.scalar.com) spenti, brand al loro posto
    assert '"withDefaultFonts": false' in corpo
    assert "Titillium Web" in corpo
    # nessuna origine esterna nella pagina; CSP stretta della GUI
    assert "http://" not in corpo and "https://" not in corpo
    assert headers.get("Content-Security-Policy") == gui.CSP


def test_bundle_scalar_vendorizzato_e_pulito():
    vendor = os.path.join(os.path.dirname(__file__), os.pardir,
                          "gui", "vendor", "scalar")
    bundle = os.path.join(vendor, "standalone.js")
    assert os.path.isfile(bundle), \
        "bundle assente: tools/update-scalar.sh"
    assert os.path.isfile(os.path.join(vendor, "VERSIONE"))
    assert os.path.isfile(os.path.join(vendor, "ORIGINI.txt"))
    testo = open(bundle, encoding="utf-8",
                 errors="replace").read()
    # denylist telemetria (pattern anti-telemetria del fork
    # Lighthouse): il bundle non deve contenere questi host
    for host in ("sentry.io", "google-analytics",
                 "googletagmanager", "posthog", "hotjar",
                 "plausible.io"):
        assert host not in testo, host
    # il bundle resta autonomo: niente chunk dinamici
    assert "dist/browser/chunks" not in testo
