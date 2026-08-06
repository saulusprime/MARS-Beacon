#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Server SOLO API di MARS Beacon (programma API-first, Fase 2).

Espone esclusivamente le rotte del contratto OpenAPI — generate
dal registro di ``marsbeacon/api.py`` e servite su
``GET /api/v1/openapi.json``, con la documentazione navigabile su
``GET /api/docs`` (Scalar vendorizzato; i suoi asset sono l'unica
concessione statica, in whitelist puntuale). **Niente filesystem
statico, niente pagine della GUI**: il frontend vive altrove —
``mars_gui.py`` per il combinato a zero configurazione, oppure un
web server statico a separazione completata (Fase 3).

Stesso motore e stessa base dati del combinato (utenti e sessioni
su SQLite, ``MARS_GUI_DB`` per spostarla; un audit alla volta,
slot orario per utente). Ascolta solo su 127.0.0.1 di default:
non esporlo su reti non fidate senza un reverse proxy con
autenticazione.

Uso:
    python3 mars_api.py [--host 127.0.0.1] [--port 8766]
                        [--citations-history FILE]

Licenza: Apache 2.0.
"""

from __future__ import annotations

import argparse
import sys
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import List, Optional

from marsbeacon import api as mars_api

__version__ = "0.2.0"


class Handler(mars_api.ApiHandler):
    """Solo API: eredita il motore cosi' com'e'.

    Il ``_fallback`` del motore risponde 404 a tutto cio' che non
    e' una rotta del contratto o un asset in whitelist della
    pagina di documentazione.
    """

    app_version = __version__


def main(argv: Optional[List[str]] = None) -> int:
    """Punto di ingresso da riga di comando."""
    parser = argparse.ArgumentParser(
        prog="mars_api.py",
        description="Server solo-API di MARS Beacon: contratto "
                    "OpenAPI su /api/v1/openapi.json, "
                    "documentazione su /api/docs, nessun file "
                    "statico della GUI.")
    parser.add_argument("--host", default="127.0.0.1",
                        help="indirizzo di ascolto (default "
                             "127.0.0.1; non esporre su reti non "
                             "fidate)")
    parser.add_argument("--port", type=int, default=8766,
                        help="porta di ascolto (default 8766, per "
                             "convivere col combinato sulla 8765)")
    parser.add_argument("--citations-history", metavar="FILE",
                        default=str(mars_api.CITATIONS_HISTORY),
                        help="storico JSONL del monitoraggio "
                             "citazioni esposto da /api/citations "
                             "(default %s)"
                             % mars_api.CITATIONS_HISTORY)
    parser.add_argument("--cors", metavar="ORIGINE",
                        action="append", default=[],
                        help="origine cross-origin ammessa (es. "
                             "https://gui.esempio.it), ripetibile. "
                             "SPENTO di default: senza origini "
                             "dichiarate nessun header CORS; "
                             "cross-origin ci si autentica col "
                             "token Bearer, mai col cookie")
    parser.add_argument("--max-audit", type=int, default=1,
                        metavar="N",
                        help="audit in parallelo ammessi (default "
                             "1 = un audit alla volta, come il "
                             "combinato; oltre: 409 quando la "
                             "concorrenza e' esaurita)")
    parser.add_argument("--version", action="version",
                        version="%(prog)s " + __version__)
    args = parser.parse_args(argv)

    if args.max_audit < 1:
        print("--max-audit vuole un intero >= 1.", file=sys.stderr)
        return 2
    mars_api.CITATIONS_HISTORY = Path(args.citations_history)
    mars_api.CORS_ORIGINS = tuple(args.cors)
    mars_api.AUDIT_CONCURRENCY = args.max_audit

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print("API disponibile su http://%s:%d/ — contratto: "
          "/api/v1/openapi.json, documentazione: /api/docs "
          "(Ctrl+C per uscire)" % (args.host, args.port),
          file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nArresto.", file=sys.stderr)
        server.server_close()
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
