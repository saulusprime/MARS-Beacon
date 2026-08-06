# -*- coding: utf-8 -*-
"""Flusso della GUI a pagine in un browser reale (P5).

Regressione per la classe di bug "elemento di un'altra pagina":
con app.js condiviso fra le tre pagine, un accesso non guardato a
un id assente fa morire il gestore senza sintomi visibili (es.
"Avvia audit" che non parte perche' clearErrors toccava
#audit-error, presente solo su scansione.html). L'unico modo di
coprirlo e' eseguire davvero il JavaScript: registrazione →
redirect alla configurazione → avvio → redirect alla scansione col
job nell'URL → risultati. Salta senza Playwright/Chromium, come il
test del rendering col browser reale.
"""

import threading
from http.server import ThreadingHTTPServer

import pytest

import mars_gui as gui
from marsbeacon import api as engine


@pytest.fixture()
def gui_server(tmp_path):
    engine.JOB = gui.Job()
    engine.STORE = gui.UserStore(tmp_path / "users.db")
    server = ThreadingHTTPServer(("127.0.0.1", 0), gui.Handler)
    threading.Thread(target=server.serve_forever,
                     daemon=True).start()
    yield "http://127.0.0.1:%d" % server.server_address[1]
    server.shutdown()


def test_flusso_completo_nel_browser(gui_server, site):
    pytest.importorskip("playwright")
    from playwright.sync_api import Error, sync_playwright

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Error:
            pytest.skip("Chromium di Playwright non installato")
        page = browser.new_page()
        errori = []
        page.on("pageerror", lambda e: errori.append(str(e)))

        # accesso: registrazione -> redirect alla configurazione
        page.goto(gui_server + "/accesso.html")
        page.fill("#r-nome", "Utente Browser")
        page.fill("#r-email", "browser@esempio.it")
        page.fill("#r-password", "passwordprova")
        page.check("#r-tos", force=True)  # la label copre il box
        page.click("#register-form button[type=submit]")
        page.wait_for_url("**/configurazione.html*",
                          timeout=10000)
        page.wait_for_selector("#audit-form", state="visible",
                               timeout=10000)

        # aiuti contestuali: il "?" apre e chiude l'hint
        assert page.eval_on_selector("#h-url", "n => n.hidden")
        page.click('button.lt-help[aria-controls="h-url"]')
        assert not page.eval_on_selector("#h-url",
                                         "n => n.hidden")

        # avvio -> redirect alla scansione col job nell'URL
        page.fill("#f-url", site)
        page.fill("#f-max-pages", "3")
        page.click("#submit-btn")
        page.wait_for_url("**/scansione.html?job=*",
                          timeout=15000)

        # audit del sito fixture: risultati senza errori di pagina
        page.wait_for_selector("#results-section:not([hidden])",
                               timeout=120000)
        assert page.eval_on_selector("#audit-error",
                                     "n => n.hidden")

        # deep-link: il ricaricamento ripristina dal job
        page.reload()
        page.wait_for_selector("#results-section:not([hidden])",
                               timeout=30000)

        assert errori == [], errori
        browser.close()
