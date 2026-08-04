# -*- coding: utf-8 -*-
"""Sessione strumentale del protocollo screen reader (flussi 1-7).

Esegue i flussi di docs/ACCESSIBILITA.md nel browser reale e
verifica il contratto ARIA che l'albero di accessibilita' espone
all'AT: focus, annunci delle regioni di stato, etichette, stati.
NON sostituisce la sessione umana con VoiceOver/NVDA: ne e' la
preparazione strumentale.
"""
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import seo_rrf_gui as gui  # noqa: E402

PAGES = {
    "/": ("<!DOCTYPE html><html lang=\"it\"><head>"
          "<meta charset=\"utf-8\"><title>Demo | Home</title>"
          "</head><body><h1>Centro Demo</h1>"
          "<h2>Cos'è il drenaggio</h2><p>Il drenaggio linfatico "
          "è una tecnica di massaggio dolce che favorisce il "
          "deflusso della linfa. Una seduta dura 45 minuti.</p>"
          "<a href=\"/servizi\">Servizi</a></body></html>"),
    "/servizi": ("<!DOCTYPE html><html lang=\"it\"><head>"
                 "<meta charset=\"utf-8\"><title>Servizi</title>"
                 "</head><body><h1>Servizi</h1><p>Massaggi.</p>"
                 "<a href=\"/\">Home</a></body></html>"),
}


class SiteHandler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        page = PAGES.get(self.path.split("?")[0])
        if page is None:
            self.send_response(404)
            self.end_headers()
            return
        body = page.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type",
                         "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


ESITI = []


def check(flusso, nome, ok, dettaglio=""):
    ESITI.append((flusso, nome, bool(ok), dettaglio))
    stato = "OK " if ok else "FAIL"
    print("[%s] F%d %s%s" % (stato, flusso, nome,
                             " — " + dettaglio if dettaglio else ""),
          flush=True)


def main():
    site_srv = ThreadingHTTPServer(("127.0.0.1", 0), SiteHandler)
    threading.Thread(target=site_srv.serve_forever,
                     daemon=True).start()
    site = "http://127.0.0.1:%d" % site_srv.server_address[1]

    gui.STORE = gui.UserStore(
        Path(tempfile.mkdtemp()) / "users.db")
    gui_srv = ThreadingHTTPServer(("127.0.0.1", 0), gui.Handler)
    threading.Thread(target=gui_srv.serve_forever,
                     daemon=True).start()
    base = "http://127.0.0.1:%d" % gui_srv.server_address[1]

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path="/usr/bin/google-chrome",
            args=["--no-sandbox"])
        page = browser.new_page(
            viewport={"width": 1280, "height": 900})
        page.goto(base)

        # ---- Flusso 1: orientamento iniziale ----
        check(1, "titolo pagina annunciabile",
              "MARS Audit" in page.title(), page.title())
        page.keyboard.press("Tab")
        primo = page.evaluate(
            "document.activeElement.textContent.trim()")
        check(1, "skip link primo con Tab",
              "contenuto principale" in primo.lower(), primo)
        headings = page.evaluate(
            "Array.from(document.querySelectorAll("
            "'h1,h2,h3')).map(h => h.textContent.trim())")
        check(1, "sezione Accesso raggiungibile per titoli",
              any("Accesso" in h for h in headings))

        # ---- Flusso 2: registrazione ----
        for campo, label_id in (("r-nome", None), ("r-email", None),
                                ("r-password", None)):
            testo = page.evaluate(
                "document.querySelector('label[for=\"%s\"]')"
                "?.textContent || ''" % campo)
            check(2, "etichetta con obbligo su #%s" % campo,
                  testo.strip() != "" and "*" in testo,
                  testo.strip()[:40])
        tos_label = page.evaluate(
            "document.querySelector('label[for=\"r-tos\"]')"
            "?.textContent || ''")
        check(2, "checkbox condizioni etichettato",
              "condizioni" in tos_label.lower())
        page.click("#register-form button[type=submit]")
        page.wait_for_timeout(400)
        focus_err = page.evaluate(
            "({id: document.activeElement.id,"
            " text: document.activeElement.textContent.trim()"
            ".slice(0, 80)})")
        check(2, "errore: focus sull'avviso e testo letto",
              focus_err["text"] != "" and focus_err["id"] != "",
              "%s: %s" % (focus_err["id"], focus_err["text"]))
        page.fill("#r-nome", "Paola Rossi")
        page.fill("#r-email", "at@esempio.it")
        page.fill("#r-password", "segretissima")
        page.click("label[for=\"r-tos\"]")
        page.click("#register-form button[type=submit]")
        page.wait_for_selector("#config-section:not([hidden])",
                               timeout=10000)
        annunci = page.evaluate(
            "Array.from(document.querySelectorAll("
            "'[role=\"status\"]')).map(e => e.textContent.trim())"
            ".filter(Boolean)")
        check(2, "registrazione annunciata in regione di stato",
              any("registrazione" in a.lower() or "check" in
                  a.lower() for a in annunci), "; ".join(annunci))

        # ---- Flusso 3: configurazione ----
        exp = page.evaluate(
            "document.querySelector('#config-heading button')"
            ".getAttribute('aria-expanded')")
        check(3, "accordion configurazione espanso annunciato",
              exp == "true", "aria-expanded=%s" % exp)
        descr_ok = page.evaluate("""(() => {
          const campi = document.querySelectorAll(
            '[aria-describedby]');
          let rotti = 0;
          campi.forEach((c) => c.getAttribute('aria-describedby')
            .split(/\\s+/).forEach((id) => {
              if (!document.getElementById(id)) { rotti += 1; }
            }));
          return {tot: campi.length, rotti: rotti};
        })()""")
        check(3, "suggerimenti collegati via aria-describedby",
              descr_ok["rotti"] == 0 and descr_ok["tot"] > 10,
              "%d campi, %d riferimenti rotti"
              % (descr_ok["tot"], descr_ok["rotti"]))

        # ---- Flusso 4: avvio e avanzamento ----
        page.fill("#f-url", site)
        page.fill("#f-max-pages", "3")
        page.fill("#f-delay", "1.5")
        page.click("#submit-btn")
        page.wait_for_timeout(700)
        focus_id = page.evaluate("document.activeElement.id")
        check(4, "focus sull'avanzamento all'avvio",
              "progress" in focus_id or "avanzamento" in focus_id,
              "activeElement=#%s" % focus_id)
        annulla = page.evaluate(
            "!!document.querySelector('#cancel-btn')"
            " && !document.querySelector('#cancel-btn').hidden")
        check(4, "bottone Annulla audit raggiungibile", annulla)
        stato_txt = ""
        for _ in range(80):
            stato_txt = page.evaluate(
                "Array.from(document.querySelectorAll("
                "'[role=\"status\"]')).map(e => e.textContent)"
                ".join(' ')")
            if "Fase" in stato_txt or "fase" in stato_txt:
                break
            time.sleep(0.2)
        check(4, "fasi annunciate dalla regione di stato",
              "ase" in stato_txt, stato_txt.strip()[:60])
        page.wait_for_selector("#results-section:not([hidden])",
                               timeout=120000)
        page.wait_for_timeout(600)

        # ---- Flusso 5: risultati ----
        focus_id = page.evaluate("document.activeElement.id")
        check(5, "focus sui risultati a fine audit",
              focus_id == "results-toggle",
              "activeElement=#%s" % focus_id)
        label_btn = page.evaluate(
            "document.querySelector('#scores button')"
            "?.getAttribute('aria-label') || ''")
        check(5, "punteggi per area: pulsanti con etichetta",
              "rilievi" in label_btn, label_btn[:60])
        badge = page.evaluate(
            "Array.from(document.querySelectorAll('.badge-sev'))"
            ".map(b => b.textContent.trim()).slice(0, 3)")
        check(5, "gravita' come testo, mai solo colore",
              any("Critico" in b or "Avvertenza" in b
                  or "OK" in b for b in badge), "; ".join(badge))
        captions = page.evaluate(
            "Array.from(document.querySelectorAll("
            "'table caption')).length")
        check(5, "tabelle con didascalia", captions >= 2,
              "%d caption" % captions)

        # ---- Flusso 6: download negato (profilo incompleto) ----
        dl = page.evaluate(
            "document.getElementById('dl-html')"
            ".getAttribute('aria-disabled')")
        nota = page.evaluate(
            "(() => { const n = document.getElementById("
            "'download-note'); return n && !n.hidden ? "
            "n.textContent.replace(/\\s+/g, ' ').trim() : ''; "
            "})()")
        check(6, "download disabilitato annunciato",
              dl == "true", "aria-disabled=%s" % dl)
        check(6, "nota esplicativa presente e leggibile",
              "registrazione completa" in nota, nota[:60])

        # ---- Flusso 7: widget grafici ----
        hero_labels = page.evaluate(
            "Array.from(document.querySelectorAll("
            "'#hero [aria-label], #hero [role=\"img\"]'))"
            ".map(e => e.getAttribute('aria-label') || '')"
            ".filter(Boolean)")
        check(7, "widget hero con aria-label parlanti",
              any("unteggio" in lab for lab in hero_labels),
              "; ".join(lab[:50] for lab in hero_labels[:2]))
        nascosti = page.evaluate(
            "document.querySelectorAll("
            "'#results-section [aria-hidden=\"true\"]').length")
        check(7, "dettagli decorativi aria-hidden", nascosti >= 3,
              "%d elementi" % nascosti)
        grafo_label = page.evaluate(
            "document.querySelector('#graph-svg svg')"
            "?.getAttribute('aria-label') || ''")
        check(7, "grafo dei link con aria-label",
              "rilievi" in grafo_label, grafo_label[:60])

        browser.close()

    ok = sum(1 for _f, _n, esito, _d in ESITI if esito)
    print("\nESITO: %d/%d controlli superati" % (ok, len(ESITI)))
    if ok != len(ESITI):
        sys.exit(1)


if __name__ == "__main__":
    main()
