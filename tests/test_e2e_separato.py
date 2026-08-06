# -*- coding: utf-8 -*-
"""E2E a origini separate (P1, Fase 4): statici + API con CORS.

Il frontend statico vive su un'origine (una copia del bundle gui/
con MARS_API_BASE valorizzata, servita da un web server statico
qualunque), l'API su un'altra con le origini CORS dichiarate: il
ciclo completo audit -> referti passa dal token Bearer con
l'header Origin, come farebbe il browser. Nessun browser reale:
la parte visuale e' coperta dalla verifica AT strumentale; qui si
prova il CONTRATTO dell'assetto separato.
"""

import json
import os
import shutil
import threading
import urllib.error
import urllib.request
from functools import partial
from http.server import SimpleHTTPRequestHandler
from http.server import ThreadingHTTPServer

import pytest

import mars_api as solo
import mars_gui as gui
from marsbeacon import api

GUI_DIR = os.path.join(os.path.dirname(__file__), os.pardir,
                       "gui")


@pytest.fixture(autouse=True)
def ambiente_pulito(tmp_path):
    api.JOB = gui.Job()
    api.STORE = gui.UserStore(tmp_path / "users.db")
    api.CITATIONS_HISTORY = tmp_path / "citazioni.jsonl"
    yield


@pytest.fixture()
def origini(tmp_path, monkeypatch):
    """(base_api, base_statici): due origini, CORS dichiarato."""
    api_server = ThreadingHTTPServer(("127.0.0.1", 0),
                                     solo.Handler)
    threading.Thread(target=api_server.serve_forever,
                     daemon=True).start()
    base_api = "http://127.0.0.1:%d" % api_server.server_address[1]

    # il bundle si distribuisce per copia: config.js con la base
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    for nome in ("index.html", "app.js"):
        shutil.copy(os.path.join(GUI_DIR, nome), bundle / nome)
    with open(os.path.join(GUI_DIR, "config.js"),
              encoding="utf-8") as fh:
        config = fh.read()
    assert 'window.MARS_API_BASE = ""' in config
    (bundle / "config.js").write_text(
        config.replace('window.MARS_API_BASE = ""',
                       'window.MARS_API_BASE = "%s"' % base_api),
        encoding="utf-8")

    handler = partial(SimpleHTTPRequestHandler,
                      directory=str(bundle))
    static_server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=static_server.serve_forever,
                     daemon=True).start()
    base_statici = "http://127.0.0.1:%d" \
        % static_server.server_address[1]

    monkeypatch.setattr(api, "CORS_ORIGINS", (base_statici,))
    yield base_api, base_statici
    api_server.shutdown()
    static_server.shutdown()


def _req(url, payload=None, method=None, headers=None):
    dati = (json.dumps(payload).encode("utf-8")
            if payload is not None else None)
    req = urllib.request.Request(url, data=dati, method=method)
    if payload is not None:
        req.add_header("Content-Type", "application/json")
    for nome, valore in (headers or {}).items():
        req.add_header(nome, valore)
    try:
        with urllib.request.urlopen(req) as resp:
            return (resp.status, resp.read(),
                    dict(resp.headers))
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(), dict(exc.headers)


def test_e2e_origini_separate_ciclo_completo(origini, site):
    base_api, base_statici = origini

    # 1) il server statico serve il bundle ma non l'API
    stato, corpo, _ = _req(base_statici + "/index.html")
    assert stato == 200 and b"MARS" in corpo
    stato, corpo, _ = _req(base_statici + "/config.js")
    assert stato == 200 and base_api.encode() in corpo
    stato, _, _ = _req(base_statici + "/api/env")
    assert stato == 404

    # 2) il server API non serve il frontend
    stato, corpo, _ = _req(base_api + "/index.html")
    assert stato == 404
    assert json.loads(corpo) == {"error": "non trovato"}

    # 3) preparazione account e token (come dal combinato)
    stato, _, intestazioni = _req(
        base_api + "/api/register",
        {"nome": "Paola Rossi", "email": "sep@esempio.it",
         "password": "segretissima", "tos": True,
         "azienda": "Centro Esempio", "telefono": "0521 1"})
    assert stato == 201
    cookie = intestazioni.get("Set-Cookie", "").split(";")[0]
    stato, corpo, _ = _req(base_api + "/api/v1/tokens",
                           {"label": "frontend separato"},
                           headers={"Cookie": cookie})
    assert stato == 201
    token = json.loads(corpo)["token"]

    # 4) il "browser" dell'origine statica: Origin + Bearer
    browser = {"Origin": base_statici,
               "Authorization": "Bearer %s" % token}
    stato, corpo, intestazioni = _req(
        base_api + "/api/v1/audits",
        {"url": site, "max_pages": 3, "delay": 0,
         "lighthouse": "off", "lang": "en"}, headers=browser)
    assert stato == 202
    assert intestazioni.get("Access-Control-Allow-Origin") \
        == base_statici
    job_id = json.loads(corpo)["id"]

    import time as _t
    fine = _t.time() + 120
    snap = {}
    while _t.time() < fine:
        stato, corpo, intestazioni = _req(
            base_api + "/api/v1/audits/%s" % job_id,
            headers=browser)
        assert stato == 200
        assert intestazioni.get("Access-Control-Allow-Origin") \
            == base_statici
        snap = json.loads(corpo)
        if snap["state"] in ("done", "error"):
            break
        _t.sleep(0.3)
    assert snap["state"] == "done", snap.get("error")

    stato, corpo, intestazioni = _req(
        base_api + "/api/v1/audits/%s/report?format=text&lang=fr"
        % job_id, headers=browser)
    assert stato == 200
    assert "Pages analysées" in corpo.decode("utf-8")
    assert intestazioni.get("Access-Control-Allow-Origin") \
        == base_statici

    # 5) preflight e origine estranea
    stato, _, intestazioni = _req(
        base_api + "/api/v1/audits", method="OPTIONS",
        headers={"Origin": base_statici})
    assert stato == 204
    assert "Authorization" in intestazioni.get(
        "Access-Control-Allow-Headers", "")
    stato, _, intestazioni = _req(
        base_api + "/api/env",
        headers={"Origin": "https://estranea.test"})
    assert stato == 200
    assert "Access-Control-Allow-Origin" not in intestazioni
