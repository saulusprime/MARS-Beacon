# -*- coding: utf-8 -*-
"""Fixture comuni: sito di prova locale con difetti piantati.

Il sito serve robots.txt (GPTBot bloccato), sitemap, una home
duplicata su due URL, una pagina servizio ricca, una pagina
segnaposto WordPress, una pagina noindex e una risposta oversize
da 12 MB: ogni difetto corrisponde a un rilievo atteso nei test.
"""

import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

BIG_BYTES = 12 * 1048576

ROBOTS = """User-agent: GPTBot
Disallow: /

User-agent: SeoRrfAudit
Disallow: /riservata

User-agent: *
Disallow:

Sitemap: BASE/sitemap.xml
"""

SITEMAP = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<url><loc>BASE/</loc></url>
<url><loc>BASE/index.html</loc></url>
<url><loc>BASE/servizio-drenaggio/</loc></url>
<url><loc>BASE/sample-page/</loc></url>
<url><loc>BASE/noindex/</loc></url>
<url><loc>BASE/riservata/</loc></url>
<url><loc>BASE/big/</loc></url>
</urlset>
"""

HOME = """<!DOCTYPE html>
<html lang="it"><head><meta charset="utf-8">
<title>Centro Linfa — drenaggio linfatico manuale a Parma</title>
<meta name="description" content="Centro specializzato in drenaggio
linfatico manuale a Parma: trattamenti personalizzati, fisioterapisti
certificati e percorsi post-operatori su misura.">
<script type="application/ld+json">
{"@context": "https://schema.org", "@type": "Organization",
 "name": "Centro Linfa"}
</script>
</head><body>
<h1>Drenaggio linfatico manuale a Parma</h1>
<p>Il Centro Linfa offre trattamenti di drenaggio linfatico manuale
eseguiti da fisioterapisti certificati, con percorsi personalizzati
per ogni paziente e attenzione alla fase post-operatoria.</p>
<p>Riceviamo su appuntamento dal lunedi al venerdi; la prima
valutazione comprende un colloquio conoscitivo e la definizione del
piano di trattamento adatto alla persona.</p>
<p><a href="/servizio-drenaggio/">Scopri il servizio</a></p>
<p><a href="/riservata/">Documenti interni</a></p>
</body></html>
"""

RISERVATA = """<!DOCTYPE html>
<html lang="it"><head><meta charset="utf-8">
<title>Documenti interni</title></head><body>
<h1>Documenti interni</h1>
<p>Questa sezione è vietata all'agente dello strumento dal file
robots.txt e serve a verificare l'opzione di rispetto dei Disallow
durante la scansione del sito di prova.</p>
</body></html>
"""

SERVICE = """<!DOCTYPE html>
<html lang="it"><head><meta charset="utf-8">
<title>Drenaggio linfatico manuale: cos'e' e come funziona</title>
<meta name="description" content="Cos'e' il drenaggio linfatico
manuale, come funziona una seduta, quando serve e quanto costa:
guida completa con esempi e domande frequenti.">
</head><body>
<h1>Il drenaggio linfatico manuale</h1>
<h2>Cos'e' il drenaggio linfatico manuale?</h2>
<p>Il drenaggio linfatico manuale è una tecnica di massaggio dolce
che favorisce il deflusso della linfa attraverso movimenti lenti e
ritmici eseguiti lungo le vie linfatiche del corpo.</p>
<p>La tecnica viene applicata da personale formato e si svolge in
sedute della durata media di quarantacinque minuti, con frequenza
stabilita in base alla condizione della persona.</p>
<h2>Quando serve il trattamento?</h2>
<p>Il trattamento è indicato ad esempio dopo interventi chirurgici,
in presenza di gonfiori agli arti o durante percorsi riabilitativi
concordati con il medico curante che segue la persona.</p>
<h2>Domande frequenti</h2>
<p>Quanto costa una seduta? Il costo dipende dalla durata e dal
percorso concordato; il preventivo viene definito alla prima
valutazione insieme al fisioterapista di riferimento.</p>
</body></html>
"""

SAMPLE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>Sample Page</title></head><body>
<h1>Sample Page</h1>
<p>This is an example page. It's different from a blog post because
it will stay in one place and will show up in your site navigation
in most themes, as every new WordPress user quickly discovers.</p>
</body></html>
"""

NOINDEX = """<!DOCTYPE html>
<html lang="it"><head><meta charset="utf-8">
<title>Area riservata</title>
<meta name="robots" content="noindex, follow">
</head><body>
<h1>Area riservata</h1>
<p>Questa pagina è riservata agli operatori del centro e non deve
comparire nei risultati dei motori di ricerca pubblici.</p>
</body></html>
"""


class SiteHandler(BaseHTTPRequestHandler):
    """Serve il sito di prova con i difetti piantati."""

    def _send(self, body: bytes, ctype: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - firma di BaseHTTPServer
        base = "http://127.0.0.1:%d" % self.server.server_address[1]
        html = "text/html; charset=utf-8"
        routes = {
            "/": (HOME, html),
            "/index.html": (HOME, html),
            "/servizio-drenaggio/": (SERVICE, html),
            "/sample-page/": (SAMPLE, html),
            "/noindex/": (NOINDEX, html),
            "/riservata/": (RISERVATA, html),
            "/riservata": (RISERVATA, html),
            "/robots.txt": (ROBOTS, "text/plain; charset=utf-8"),
            "/sitemap.xml": (SITEMAP, "application/xml"),
        }
        if self.path in routes:
            body, ctype = routes[self.path]
            self._send(body.replace("BASE", base).encode("utf-8"),
                       ctype)
        elif self.path == "/big/":
            self.send_response(200)
            self.send_header("Content-Type", html)
            self.send_header("Content-Length", str(BIG_BYTES))
            self.end_headers()
            try:
                sent = 0
                block = b"x" * 65536
                while sent < BIG_BYTES:
                    self.wfile.write(block)
                    sent += len(block)
            except (BrokenPipeError, ConnectionResetError):
                pass
        else:
            body = b"<html><body>non trovata</body></html>"
            self.send_response(404)
            self.send_header("Content-Type", html)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    def log_message(self, fmt: str, *args: object) -> None:
        pass


@pytest.fixture(scope="session")
def site():
    """URL base del sito di prova, servito per l'intera sessione."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), SiteHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield "http://127.0.0.1:%d" % server.server_address[1]
    server.shutdown()


COMP_ROBOTS = """User-agent: *
Disallow:

Sitemap: BASE/sitemap.xml
"""

COMP_SITEMAP = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<url><loc>BASE/</loc></url>
<url><loc>BASE/guida-drenaggio/</loc></url>
</urlset>
"""

COMP_HOME = """<!DOCTYPE html>
<html lang="it"><head><meta charset="utf-8">
<title>Drenaggio linfatico manuale: la guida completa</title>
<meta name="description" content="Tutto sul drenaggio linfatico
manuale: definizione, benefici, controindicazioni e costi, spiegati
dai nostri fisioterapisti specializzati.">
</head><body>
<h1>Drenaggio linfatico manuale</h1>
<h2>Cos'e' il drenaggio linfatico manuale?</h2>
<p>Il drenaggio linfatico manuale è una tecnica di massaggio che
stimola la circolazione della linfa con manovre lente, superficiali
e ritmiche, eseguite lungo il decorso dei vasi linfatici del corpo
da un fisioterapista con formazione specifica certificata.</p>
<h2>Come funziona il drenaggio linfatico?</h2>
<p>Il drenaggio linfatico funziona applicando pressioni leggere e
progressive che favoriscono il riassorbimento dei liquidi e il
deflusso della linfa verso le stazioni linfonodali principali, con
benefici documentati su gonfiori ed edemi post-chirurgici.</p>
<p><a href="/guida-drenaggio/">Approfondisci nella guida</a></p>
</body></html>
"""

COMP_GUIDE = """<!DOCTYPE html>
<html lang="it"><head><meta charset="utf-8">
<title>Quanto costa il drenaggio linfatico manuale</title>
<meta name="description" content="Prezzi e durata delle sedute di
drenaggio linfatico manuale: la guida con esempi concreti.">
</head><body>
<h1>Costi e durata del drenaggio linfatico manuale</h1>
<h2>Quanto costa una seduta di drenaggio linfatico?</h2>
<p>Una seduta di drenaggio linfatico manuale costa in media fra i
quaranta e gli ottanta euro, ad esempio in base alla durata, alla
zona trattata e all'esperienza del fisioterapista che esegue il
trattamento manuale sul paziente in studio.</p>
<h2>Quante sedute di drenaggio linfatico servono?</h2>
<p>Il numero di sedute di drenaggio linfatico manuale dipende dalla
condizione: per un edema post-operatorio si parte in genere da un
ciclo di dieci sedute, con frequenza bisettimanale concordata con il
medico curante e il fisioterapista di riferimento.</p>
</body></html>
"""


class CompetitorHandler(BaseHTTPRequestHandler):
    """Concorrente di prova: forte sugli stessi temi del sito."""

    def _send(self, body: bytes, ctype: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - firma di BaseHTTPServer
        base = "http://127.0.0.1:%d" % self.server.server_address[1]
        html = "text/html; charset=utf-8"
        routes = {
            "/": (COMP_HOME, html),
            "/guida-drenaggio/": (COMP_GUIDE, html),
            "/robots.txt": (COMP_ROBOTS, "text/plain; charset=utf-8"),
            "/sitemap.xml": (COMP_SITEMAP, "application/xml"),
        }
        if self.path in routes:
            body, ctype = routes[self.path]
            self._send(body.replace("BASE", base).encode("utf-8"),
                       ctype)
        else:
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()

    def log_message(self, fmt: str, *args: object) -> None:
        pass


@pytest.fixture(scope="session")
def competitor_site():
    """URL base del sito concorrente di prova."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), CompetitorHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield "http://127.0.0.1:%d" % server.server_address[1]
    server.shutdown()
