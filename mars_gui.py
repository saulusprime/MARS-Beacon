#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Interfaccia web locale per mars_audit.py (server combinato).

Avvia un server HTTP sulla macchina locale (default 127.0.0.1:8765)
che serve la GUI in Bootstrap Italia (cartella ``gui/``) INSIEME
alle rotte API del contratto: e' il combinato a zero
configurazione. Dalla Fase 2 del programma API-first il motore del
server — store utenti, job di audit, handler delle rotte — vive in
``marsbeacon/api.py``: questo script eredita ``ApiHandler`` e
aggiunge i file statici della GUI tramite l'hook ``_fallback``
(spostamento meccanico, facciata invariata: i nomi storici restano
importabili da qui). Il gemello ``mars_api.py`` serve la SOLA API.

Le rotte sono censite nel contratto OpenAPI generato dal registro
(GET /api/v1/openapi.json, documentazione su GET /api/docs);
l'elenco leggibile e' nella docstring di marsbeacon/api.py e nel
README. Gli utenti sono su SQLite (mars_gui.db accanto allo
script; MARS_GUI_DB lo sposta): la registrazione richiede
l'accettazione delle condizioni di servizio con dichiarazione di
proprieta' del sito analizzato.

L'audit viene eseguito in-process (import di ``mars_audit``): una
sola scansione del sito produce tutti i formati di referto.
Nessuna dipendenza oltre a quelle dello script; il frontend usa
asset vendorizzati in ``gui/vendor`` e funziona anche senza rete.

Uso:
    python3 mars_gui.py [--host 127.0.0.1] [--port 8765]

Licenza: Apache 2.0.
"""

from __future__ import annotations

import argparse
import sys
import webbrowser
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import List, Optional

import mars_audit as sra  # noqa: F401 - namespace storico (gui.sra)

from marsbeacon import api as mars_api
from marsbeacon.api import (  # noqa: F401 - facciata del combinato
    CHECK_INTERVAL_S,
    CITATIONS_HISTORY,
    CONTENT_TYPES,
    CSP,
    DB_PATH)
from marsbeacon.api import (  # noqa: F401
    DOCS_ASSETS,
    EMAIL_RE,
    GUI_DIR,
    JOB,
    Job)
from marsbeacon.api import (  # noqa: F401
    LineBuffer,
    PBKDF2_ROUNDS,
    REPORT_CSP,
    SESSION_TTL_S,
    STORE)
from marsbeacon.api import (  # noqa: F401
    ApiHandler,
    UserStore,
    compute_delta,
    get_store,
    read_citations_events)
from marsbeacon.api import (  # noqa: F401
    read_citations_history,
    validate_config)

__version__ = "2.40.0"

# Nome storico del cookie di sessione: la costante canonica e' nel
# contratto (marsbeacon.api.SESSION_COOKIE_NAME).
SESSION_COOKIE = mars_api.SESSION_COOKIE_NAME


class Handler(mars_api.ApiHandler):
    """Il combinato: rotte API del motore + file statici della GUI."""

    server_version = "SeoRrfGui/%s" % __version__
    app_version = __version__

    def _serve_static(self, path: str) -> None:
        rel = path.lstrip("/") or "index.html"
        target = (GUI_DIR / rel).resolve()
        if GUI_DIR not in target.parents and target != GUI_DIR:
            self._send_json(404, {"error": "non trovato"})
            return
        if not target.is_file():
            self._send_json(404, {"error": "non trovato"})
            return
        ctype = CONTENT_TYPES.get(target.suffix.lower(),
                                  "application/octet-stream")
        self._send(200, target.read_bytes(), ctype)

    def _fallback(self, path: str) -> None:
        # A differenza del motore solo-API, il combinato serve
        # l'intero frontend statico della GUI.
        self._serve_static(path)


def main(argv: Optional[List[str]] = None) -> int:
    """Punto di ingresso da riga di comando."""
    parser = argparse.ArgumentParser(
        prog="mars_gui.py",
        description="Interfaccia web locale per mars_audit.py.")
    parser.add_argument("--host", default="127.0.0.1",
                        help="indirizzo di ascolto (default 127.0.0.1; "
                             "non esporre su reti non fidate)")
    parser.add_argument("--port", type=int, default=8765,
                        help="porta di ascolto (default 8765)")
    parser.add_argument("--no-browser", action="store_true",
                        help="non aprire il browser all'avvio")
    parser.add_argument("--citations-history", metavar="FILE",
                        default=str(CITATIONS_HISTORY),
                        help="storico JSONL del monitoraggio "
                             "citazioni da mostrare nella GUI "
                             "(default %s; nel deploy systemd "
                             "tipicamente /var/lib/seorrf/"
                             "citazioni.jsonl)" % CITATIONS_HISTORY)
    parser.add_argument("--frame-ancestors", metavar="ORIGINE",
                        action="append", default=[],
                        help="origine autorizzata a incorniciare "
                             "la GUI in un iframe (es. "
                             "https://lymphatech.it), ripetibile "
                             "— modalita' embed con ?embed=1. "
                             "Senza origini dichiarate la CSP "
                             "resta frame-ancestors 'self'")
    parser.add_argument("--version", action="version",
                        version="%(prog)s " + __version__)
    args = parser.parse_args(argv)

    mars_api.CITATIONS_HISTORY = Path(args.citations_history)
    mars_api.FRAME_ANCESTORS = tuple(args.frame_ancestors)

    if not GUI_DIR.is_dir():
        print("Cartella 'gui/' non trovata accanto allo script.",
              file=sys.stderr)
        return 2

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    address = "http://%s:%d/" % (args.host, args.port)
    print("Interfaccia disponibile su %s (Ctrl+C per uscire)" % address,
          file=sys.stderr)
    if not args.no_browser:
        webbrowser.open(address)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nArresto.", file=sys.stderr)
        server.server_close()
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
