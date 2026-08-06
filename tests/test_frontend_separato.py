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


def test_pagine_caricano_config_prima_dello_script():
    for nome in ("accesso.html", "configurazione.html",
                 "scansione.html"):
        pagina = _leggi(nome)
        assert pagina.index('src="config.js"') \
            < pagina.index('src="app.js"'), nome
    indice = _leggi("index.html")
    assert indice.index('src="config.js"') \
        < indice.index('src="smista.js"')
    # lo smistatore non e' l'applicazione: niente app.js
    assert 'src="app.js"' not in indice


def test_app_js_passa_sempre_dal_wrapper():
    app = _leggi("app.js")
    assert "window.MARS_API_BASE" in app
    # nessuna fetch diretta verso api/: tutte via apiFetch
    assert not re.search(r'(?<!api)fetch\("api/', app)
    assert 'apiFetch("api/' in app
    # l'unica fetch nuda e' dentro il wrapper, su apiUrl
    assert app.count("fetch(apiUrl(") == 1
    # SSE: base configurabile, per-job, e guardia sul token (gli
    # EventSource non portano header: con token si va di polling)
    assert 'apiUrl("api/v1/audits/" + jobId + "/events")' in app
    assert "window.EventSource && !apiToken" in app
    # download: link legati al wrapper (blob nell'assetto remoto)
    assert "bindApiLink(" in app
    assert "adaptStaticApiLinks" in app


def test_accesso_token_presente_e_accessibile():
    accesso = _leggi("accesso.html")
    assert 'id="token-login"' in accesso
    assert 'for="t-token"' in accesso  # etichetta sul campo
    assert 'aria-describedby="token-hint"' in accesso
    assert 'id="password-login"' in accesso  # commutabile
    app = _leggi("app.js")
    assert "bindTokenLogin" in app
    assert "mars_api_token" in app  # persistenza locale
    # nel combinato (base vuota) il blocco token resta nascosto
    assert 'el("token-login").hidden = false' in app
    assert "if (REMOTE_API) {" in app


def test_aiuti_contestuali_del_form():
    """Gli hint del form di configurazione sono nascosti e si
    aprono dall'icona "?" accanto all'etichetta (disclosure:
    aria-expanded/aria-controls; aria-describedby resta sul
    campo, quindi la descrizione arriva comunque alle AT)."""
    pagina = _leggi("configurazione.html")
    bottoni = re.findall(
        r'class="lt-help"\s+aria-controls="(h-[\w-]+)"', pagina)
    nascosti = re.findall(
        r'<small id="(h-[\w-]+)" class="form-text[^"]*" hidden>',
        pagina)
    assert sorted(bottoni) == sorted(nascosti)
    assert len(bottoni) >= 20
    # ogni bottone dichiara stato e nome proprio
    assert pagina.count('aria-expanded="false"') >= len(bottoni)
    assert pagina.count('aria-label="Aiuto: ') == len(bottoni)
    # la dichiarazione di responsabilita' robots resta in chiaro
    assert "h-robots-ack" not in bottoni
    assert ('id="h-robots-ack" class="form-text d-block mb-2">'
            in pagina)
    app = _leggi("app.js")
    assert "bindHelpButtons" in app
    css = _leggi("theme.css")
    assert "button.lt-help" in css


def test_javascript_sintatticamente_valido():
    for nome in ("app.js", "config.js", "smista.js"):
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


def test_modalita_embed():
    """Embed (P2): attivazione runtime e regole CSS presenti."""
    app = _leggi("app.js")
    assert "mars-embed" in app
    assert "window.MARS_EMBED" in app
    assert "embed=1" in app
    # anche lo smistatore propaga l'embed alle destinazioni
    smista = _leggi("smista.js")
    assert "mars-embed" in smista
    assert "embed=1" in smista
    config = _leggi("config.js")
    assert "window.MARS_EMBED = false" in config
    tema = _leggi("theme.css")
    assert "body.mars-embed .lt-header" in tema
    assert "body.mars-embed .lt-footer" in tema
    # ancore senza header sticky da compensare
    assert "--lt-header-h: 0px" in tema


def test_gui_migrata_alle_rotte_v1():
    """Il ciclo audit della GUI usa il modello a risorse: nessun
    riferimento alle cinque rotte legacy deprecate."""
    app = _leggi("app.js")
    for legacy in ('"api/audit"', '"api/status"', '"api/cancel"',
                   'api/events"', "api/report/"):
        assert legacy not in app, legacy
    assert 'apiFetch("api/v1/audits"' in app       # avvio
    assert '"api/v1/audits/" + jobId' in app       # polling/cancel
    assert "mars_job_id" in app                    # id persistito
    assert "setReportLinks" in app                 # referti per job
    assert "messaggioErrore" in app                # errori v1
    # i link statici dei referti sono dinamici (legati al job)
    for nome in ("index.html", "accesso.html",
                 "configurazione.html", "scansione.html"):
        assert "api/report/" not in _leggi(nome), nome


def test_gui_a_momenti_distinti():
    """P5: tre pagine dedicate piu' lo smistatore; guardia di
    accesso con rientro whitelistato e job nel deep-link."""
    attese = {"accesso.html": "accesso",
              "configurazione.html": "configurazione",
              "scansione.html": "scansione",
              "index.html": "smista"}
    for nome, pagina in attese.items():
        assert 'data-page="%s"' % pagina in _leggi(nome), nome
    # i momenti protetti hanno barra utente e uscita
    for nome in ("configurazione.html", "scansione.html"):
        contenuto = _leggi(nome)
        assert 'id="user-bar"' in contenuto, nome
        assert 'id="logout-btn"' in contenuto, nome
    # l'accesso non contiene il form dell'audit ne' i risultati
    accesso = _leggi("accesso.html")
    assert 'id="audit-form"' not in accesso
    assert 'id="results-section"' not in accesso
    # la configurazione non contiene i risultati, la scansione
    # non contiene il form
    assert 'id="results-section"' not in _leggi(
        "configurazione.html")
    scansione = _leggi("scansione.html")
    assert 'id="audit-form"' not in scansione
    assert 'id="no-job"' in scansione
    app = _leggi("app.js")
    # rientro dopo l'accesso solo su pagine interne (whitelist)
    assert "NEXT_RE" in app
    assert "encodeURIComponent(qui)" in app
    # avvio: redirect alla scansione col job nell'URL
    assert 'pageUrl("scansione.html"' in app
    assert '"job=" + encodeURIComponent(data.id)' in app
    # smistatore: destinazioni per stato di accesso
    smista = _leggi("smista.js")
    assert '"configurazione.html"' in smista
    assert '"accesso.html"' in smista
    assert "api/me" in smista
