# -*- coding: utf-8 -*-
"""Bundle statico separato (P1, Fase 3): base URL e accesso token.

Verifiche strutturali sul frontend: la base dell'API e'
configurabile (config.js), TUTTE le chiamate passano dal wrapper
apiFetch/apiUrl (nessuna fetch o EventSource con percorso api/
fuori dal wrapper), l'accesso con token esiste ed e' accessibile,
e il combinato resta a zero configurazione (base vuota).
"""

import os
import re
import subprocess

GUI = os.path.join(os.path.dirname(__file__), os.pardir, "gui")


def _leggi(nome):
    with open(os.path.join(GUI, nome), encoding="utf-8") as fh:
        return fh.read()


def test_config_js_base_api_e_fonts():
    config = _leggi("config.js")
    # il fonts-loader storico resta (test_gui lo verifica servito)
    assert "__PUBLIC_PATH__" in config
    # base API configurabile, vuota di default (zero config)
    assert 'window.MARS_API_BASE = ""' in config


def test_index_carica_config_prima_di_app():
    indice = _leggi("index.html")
    assert indice.index('src="config.js"') \
        < indice.index('src="app.js"')


def test_app_js_passa_sempre_dal_wrapper():
    app = _leggi("app.js")
    assert "window.MARS_API_BASE" in app
    # nessuna fetch diretta verso api/: tutte via apiFetch
    assert not re.search(r'(?<!api)fetch\("api/', app)
    assert 'apiFetch("api/' in app
    # l'unica fetch nuda e' dentro il wrapper, su apiUrl
    assert app.count("fetch(apiUrl(") == 1
    # SSE: base configurabile e guardia sul token (gli EventSource
    # non portano header: con token si va di polling)
    assert 'new EventSource(apiUrl("api/events"))' in app
    assert "window.EventSource && !apiToken" in app
    # download: link legati al wrapper (blob nell'assetto remoto)
    assert "bindApiLink(" in app
    assert "adaptStaticApiLinks" in app


def test_accesso_token_presente_e_accessibile():
    indice = _leggi("index.html")
    assert 'id="token-login"' in indice
    assert 'for="t-token"' in indice  # etichetta sul campo
    assert 'aria-describedby="token-hint"' in indice
    assert 'id="password-login"' in indice  # commutabile
    app = _leggi("app.js")
    assert "bindTokenLogin" in app
    assert "mars_api_token" in app  # persistenza locale
    # nel combinato (base vuota) il blocco token resta nascosto
    assert 'el("token-login").hidden = false' in app
    assert "if (REMOTE_API) {" in app


def test_javascript_sintatticamente_valido():
    for nome in ("app.js", "config.js"):
        esito = subprocess.run(
            ["node", "--check", os.path.join(GUI, nome)],
            capture_output=True, text=True)
        assert esito.returncode == 0, esito.stderr


def test_esempio_nginx_documenta_i_due_scenari():
    percorso = os.path.join(os.path.dirname(__file__), os.pardir,
                            "deploy", "nginx-mars.conf.example")
    with open(percorso, encoding="utf-8") as fh:
        testo = fh.read()
    assert "proxy_pass http://127.0.0.1:8766" in testo
    assert "--cors" in testo
    assert "MARS_API_BASE" in testo
    assert "white-label" in testo.lower()
    # SSE dietro proxy: buffering spento
    assert "proxy_buffering off" in testo
