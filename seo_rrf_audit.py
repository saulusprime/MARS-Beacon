#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Audit SEO e RRF (Reciprocal Rank Fusion) di un sito web.

Lo script esegue una scansione di un sito (via sitemap o crawling
interno), ne estrae la struttura, e valuta quattro aree:

1. Tecnica          indicizzabilita', robots.txt, sitemap, crawler IA
2. Lessicale        segnali di tipo BM25 (title, heading, termini)
3. Semantica        chunk autoconsistenti, contenuto "answer-shaped"
4. Dati strutturati JSON-LD / Schema.org

In piu' esegue una **simulazione RRF**: costruisce due recuperatori
indipendenti (uno lessicale Okapi BM25, uno vettoriale) sui chunk del
sito, li fonde con la formula del Reciprocal Rank Fusion

    score(d) = somma su ogni lista di  1 / (k + rank_i(d))

e misura il *consenso*, cioe' quante volte lo stesso chunk compare in
alto in entrambe le liste. E' esattamente la logica con cui i motori
di ricerca ibridi e le pipeline RAG selezionano i passaggi da citare.

Riferimenti (fonti aperte e ufficiali):
  - Cormack, Clarke, Buettcher (2009), "Reciprocal Rank Fusion
    outperforms Condorcet and individual Rank Learning Methods",
    SIGIR '09.
  - Microsoft Learn, "Hybrid search scoring (RRF) - Azure AI Search":
    https://learn.microsoft.com/en-us/azure/search/hybrid-search-ranking
  - Elastic, "Reciprocal rank fusion":
    https://www.elastic.co/docs/reference/elasticsearch/rest-apis/
    reciprocal-rank-fusion
  - OpenSearch, "Introducing reciprocal rank fusion for hybrid search":
    https://opensearch.org/blog/introducing-reciprocal-rank-fusion-
    hybrid-search/
  - Robertson & Zaragoza (2009), "The Probabilistic Relevance
    Framework: BM25 and Beyond".
  - Schema.org, https://schema.org/

Dipendenze obbligatorie:  requests, beautifulsoup4, lxml
Dipendenze opzionali:     numpy, sentence-transformers

    pip install requests beautifulsoup4 lxml
    pip install sentence-transformers   # per embedding reali

Uso:
    python3 seo_rrf_audit.py https://www.example.com
    python3 seo_rrf_audit.py https://example.com --max-pages 40 \\
        --format html --output report.html
    python3 seo_rrf_audit.py https://example.com --queries q.txt \\
        --embeddings sentence-transformers/all-MiniLM-L6-v2

Licenza: MIT.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import html
import io
import json
import math
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import asdict, dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

try:
    import requests
except ImportError:  # pragma: no cover
    sys.exit("Manca 'requests'. Installa: pip install requests")

try:
    from bs4 import BeautifulSoup
except ImportError:  # pragma: no cover
    sys.exit("Manca 'beautifulsoup4'. Installa: pip install "
             "beautifulsoup4 lxml")


__version__ = "1.5.0"

# La pagina indicata nello user agent spiega chi e' il bot e come
# escluderlo; sovrascrivibile con --user-agent.
USER_AGENT = (
    "Mozilla/5.0 (compatible; SeoRrfAudit/%s; "
    "+https://github.com/saulusprime/SEO-RRF)" % __version__
)

# Token con cui lo strumento compare nel robots.txt (gruppo
# "User-agent: SeoRrfAudit"); usato da --respect-robots.
USER_AGENT_TOKEN = "SeoRrfAudit"

# Content-Type analizzabili: per tutto il resto (PDF, immagini,
# archivi...) il corpo non viene scaricato affatto — lo stato e gli
# header bastano ai rilievi. "gzip" copre le sitemap .xml.gz.
ANALYZABLE_CTYPES = ("html", "xml", "text/", "json", "gzip")

# Tetto al corpo di ogni risposta HTTP. L'intero corpo resta in RAM
# durante il parsing, e il conteggio avviene dopo la decompressione:
# protegge anche da corpi compressi che si espandono molto.
# Configurabile con --max-body.
DEFAULT_MAX_BODY_MB = 10

# Errori transitori: stati HTTP che meritano un nuovo tentativo.
# 404/403 e simili NON sono qui: sono segnali diagnostici dell'audit.
RETRY_STATUS: Tuple[int, ...] = (429, 500, 502, 503, 504)
DEFAULT_RETRIES = 2
RETRY_BACKOFF_S = 0.5   # attese: 0.5s, 1s, 2s... con tetto sotto
RETRY_MAX_WAIT_S = 8.0

# Crawler dei principali motori/assistenti IA. Fonte: documentazione
# pubblica dei rispettivi operatori.
AI_CRAWLERS: Tuple[str, ...] = (
    "GPTBot",
    "OAI-SearchBot",
    "ChatGPT-User",
    "ClaudeBot",
    "Claude-Web",
    "Google-Extended",
    "PerplexityBot",
    "CCBot",
    "Applebot-Extended",
    "Bingbot",
)

SEV_CRITICAL = "critical"
SEV_WARNING = "warning"
SEV_OK = "ok"
SEV_INFO = "info"

_SEVERITY_FACTOR: Dict[str, float] = {
    SEV_OK: 1.0,
    SEV_WARNING: 0.5,
    SEV_CRITICAL: 0.0,
}

AREA_TECH = "Tecnica"
AREA_LEX = "Lessicale (BM25)"
AREA_SEM = "Semantica (vettoriale)"
AREA_SD = "Dati strutturati"
AREA_RRF = "Simulazione RRF"

# Stopword italiane e inglesi. Lista minima e volutamente conservativa.
STOPWORDS: Set[str] = set("""
a ad agli ai al alla alle allo anche c che chi ci coi col come con cui
da dagli dai dal dalla dalle dallo degli dei del della delle dello di
dov dove e ed gli ha hai hanno ho i il in io la le lei li lo loro ma
me mi ne negli nei nel nella nelle nello noi non nostro o od ogni
per piu piu' quale quali quanto quel quella quelle quelli quello
questa queste questi questo qui sei si sia siamo siete solo sono su
sugli sui sul sulla sulle sullo suo sua suoi sue ti tra tu tuo tuoi
tutti tutto un una uno vi voi vostro
a about above after again against all am an and any are as at be
because been before being below between both but by can cannot could
did do does doing down during each few for from further had has have
having he her here hers him his how i if in into is it its itself me
more most my no nor not of off on once only or other our out over own
same she should so some such than that the their them then there
these they this those through to too under until up very was we were
what when where which while who whom why will with you your
""".split())

QUESTION_STARTERS: Tuple[str, ...] = (
    "cosa", "che cos", "come", "quando", "perche", "perche'", "quanto",
    "quanti", "quante", "quale", "quali", "chi", "dove", "conviene",
    "what", "how", "when", "why", "which", "who", "where", "is", "are",
    "can", "does", "do",
)

DEFINITION_RE = re.compile(
    r"\b(?:e'|è)\s+(?:un|una|uno|il|la|lo|l')\b"
    r"|\bsi\s+tratta\s+di\b"
    r"|\bconsiste\s+(?:in|nel|nella)\b"
    r"|\bsi\s+definisce\b"
    r"|\bsignifica\b"
    r"|\bis\s+a\b|\brefers\s+to\b|\bmeans\b",
    re.IGNORECASE,
)

EXAMPLE_RE = re.compile(
    r"\b(?:ad\s+esempio|per\s+esempio|esempio|es\.|caso\s+studio"
    r"|case\s+study|for\s+example|e\.g\.)\b",
    re.IGNORECASE,
)

# Aperture anaforiche: un chunk che inizia cosi' non e' autoconsistente.
ANAPHORA_RE = re.compile(
    r"^(?:questo|questa|questi|queste|cio'|ciò|esso|essa|essi|esse"
    r"|tale|tali|lo\s+stesso|la\s+stessa|quest'|it|this|that|these"
    r"|those|they|he|she|such)\b",
    re.IGNORECASE,
)

FAQ_HINT_RE = re.compile(
    r"\b(?:faq|domande\s+frequenti|domande\s+e\s+risposte"
    r"|frequently\s+asked)\b",
    re.IGNORECASE,
)

# Pagine segnaposto lasciate dai CMS: rumore puro per il recupero.
PLACEHOLDER_SLUGS: Tuple[str, ...] = (
    "sample-page", "pagina-di-esempio", "hello-world", "lorem-ipsum",
    "test-page", "pagina-test", "coming-soon", "elementor",
)

PLACEHOLDER_TEXT_RE = re.compile(
    r"this is an example page|questa (?:e'|è) una pagina di esempio"
    r"|welcome to wordpress|lorem ipsum dolor",
    re.IGNORECASE,
)

# Soft-404: pagine che rispondono 200 ma il cui contenuto dice
# "non trovato". Il segnale forte e' nel title/H1; nel corpo vale
# solo su pagine molto corte (vedi audit_technical).
SOFT_404_RE = re.compile(
    r"pagina non (?:e'|è|e|é)?\s*(?:stata\s+)?trovata"
    r"|contenuto non trovato|nessun risultato"
    r"|page (?:was\s+)?not found|nothing (?:was\s+)?found"
    r"|error(?:e)?\s*404|\b404\b",
    re.IGNORECASE,
)
SOFT_404_MAX_WORDS = 120

TOKEN_RE = re.compile(r"[a-zA-Zà-ÿÀ-Ÿ0-9][a-zA-Zà-ÿÀ-Ÿ0-9'’\-]*")

# Soglie di riferimento. Valori di prassi SEO, non standard normativi.
TITLE_MIN, TITLE_MAX = 30, 65
DESC_MIN, DESC_MAX = 110, 165
THIN_CONTENT_WORDS = 300
GOOD_CONTENT_WORDS = 700


def tokenize(text: str, keep_stopwords: bool = False) -> List[str]:
    """Tokenizza in minuscolo, opzionalmente senza stopword."""
    tokens = [m.group(0).lower() for m in TOKEN_RE.finditer(text)]
    if keep_stopwords:
        return tokens
    return [t for t in tokens if t not in STOPWORDS and len(t) > 2]


def char_ngrams(text: str, size: int = 4) -> List[str]:
    """N-grammi di caratteri, usati dal recuperatore di ripiego."""
    norm = re.sub(r"\s+", " ", text.lower().strip())
    if len(norm) < size:
        return [norm] if norm else []
    return [norm[i:i + size] for i in range(len(norm) - size + 1)]


def norm_url(url: str) -> str:
    """Normalizza un URL: rimuove fragment e slash finale ridondante."""
    parsed = urlparse(url)
    path = parsed.path or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path[:-1]
    return "%s://%s%s%s" % (
        parsed.scheme, parsed.netloc, path,
        "?" + parsed.query if parsed.query else "",
    )


def available_ram_mb() -> Optional[float]:
    """RAM disponibile in MB, dove il sistema la espone (POSIX)."""
    try:
        page = os.sysconf("SC_PAGE_SIZE")
        pages = os.sysconf("SC_AVPHYS_PAGES")
    except (AttributeError, ValueError, OSError):
        return None
    if page <= 0 or pages <= 0:
        return None
    return page * pages / 1048576.0


# --------------------------------------------------------------------
# Modelli di dato
# --------------------------------------------------------------------

@dataclass
class Finding:
    """Singolo rilievo dell'audit."""

    area: str
    severity: str
    title: str
    detail: str = ""
    fix: str = ""
    url: str = ""
    weight: float = 1.0

    def as_dict(self) -> Dict[str, object]:
        return asdict(self)


@dataclass
class Chunk:
    """Porzione di testo indicizzabile, come in una pipeline RAG."""

    url: str
    heading: str
    text: str
    index: int = 0

    @property
    def label(self) -> str:
        head = self.heading or "(senza heading)"
        return "%s  ·  %s" % (urlparse(self.url).path or "/", head[:60])

    @property
    def searchable(self) -> str:
        return "%s\n%s" % (self.heading, self.text)


@dataclass
class Page:
    """Rappresentazione di una pagina HTML analizzata."""

    url: str
    status: int = 0
    final_url: str = ""
    redirects: int = 0
    elapsed: float = 0.0
    html_bytes: int = 0
    lang: str = ""
    title: str = ""
    description: str = ""
    canonical: str = ""
    meta_robots: str = ""
    generator: str = ""
    og: Dict[str, str] = field(default_factory=dict)
    hreflang: List[str] = field(default_factory=list)
    headings: List[Tuple[int, str]] = field(default_factory=list)
    paragraphs: List[str] = field(default_factory=list)
    blocks: List[Tuple[str, str]] = field(default_factory=list)
    text: str = ""
    word_count: int = 0
    script_bytes: int = 0
    images: int = 0
    images_with_alt: int = 0
    internal_links: int = 0
    external_links: int = 0
    jsonld_types: List[str] = field(default_factory=list)
    jsonld_raw: List[dict] = field(default_factory=list)
    chunks: List[Chunk] = field(default_factory=list)
    error: str = ""

    @property
    def ok(self) -> bool:
        return self.status == 200 and not self.error

    @property
    def slug(self) -> str:
        return urlparse(self.url).path.strip("/").split("/")[-1] or "/"


# --------------------------------------------------------------------
# Recupero HTTP
# --------------------------------------------------------------------

class Fetcher:
    """Client HTTP con user agent esplicito e pausa fra richieste."""

    def __init__(self, delay: float = 0.5, timeout: int = 20,
                 verbose: bool = True,
                 max_bytes: int = DEFAULT_MAX_BODY_MB * 1048576,
                 retries: int = DEFAULT_RETRIES,
                 backoff: float = RETRY_BACKOFF_S,
                 user_agent: str = USER_AGENT) -> None:
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": user_agent or USER_AGENT,
            "Accept-Language": "it,en;q=0.8",
        })
        self.delay = delay
        self.timeout = timeout
        self.verbose = verbose
        self.max_bytes = max(1, int(max_bytes))
        self.retries = max(0, int(retries))
        self.backoff = max(0.0, backoff)
        self.last_error = ""
        self._last = 0.0

    def _throttle(self) -> None:
        wait = self.delay - (time.time() - self._last)
        if wait > 0:
            time.sleep(wait)
        self._last = time.time()

    def get(self, url: str) -> Optional[requests.Response]:
        """Esegue una GET con retry esponenziale sui transitori.

        Sono transitori gli errori di rete e gli stati RETRY_STATUS
        (429/5xx); non lo sono gli altri stati HTTP, che l'audit deve
        riportare, e i corpi oltre il limite. Esauriti i tentativi
        restituisce l'ultima risposta (o None su errore di rete, con
        il motivo in ``last_error``).
        """
        attempts = self.retries + 1
        resp: Optional[requests.Response] = None
        for attempt in range(1, attempts + 1):
            resp = self._fetch_once(url)
            if not self._transient(resp) or attempt == attempts:
                return resp
            wait = min(self.backoff * (2 ** (attempt - 1)),
                       RETRY_MAX_WAIT_S)
            if resp is not None:
                retry_after = resp.headers.get("Retry-After", "")
                if retry_after.isdigit():
                    wait = max(wait, min(float(retry_after),
                                         RETRY_MAX_WAIT_S))
                reason = "HTTP %d" % resp.status_code
                resp.close()
            else:
                reason = self.last_error or "errore di rete"
            if self.verbose:
                print("  ! %s: nuovo tentativo %d/%d fra %.1fs"
                      % (reason, attempt + 1, attempts, wait),
                      file=sys.stderr)
            time.sleep(wait)
        return resp

    @staticmethod
    def _analyzable(ctype: str, url: str) -> bool:
        """True se il corpo va scaricato per l'analisi."""
        low = ctype.lower()
        if any(t in low for t in ANALYZABLE_CTYPES):
            return True
        # Sitemap compresse servite come octet-stream.
        return urlparse(url).path.lower().endswith(".gz")

    def _transient(self, resp: Optional[requests.Response]) -> bool:
        """True se l'esito merita un nuovo tentativo."""
        if resp is None:
            return self.last_error == "richiesta fallita"
        return resp.status_code in RETRY_STATUS

    def _fetch_once(self, url: str) -> Optional[requests.Response]:
        """Una singola GET, con throttle e limite sul corpo."""
        self._throttle()
        self.last_error = ""
        if self.verbose:
            print("  GET %s" % url, file=sys.stderr)
        try:
            resp = self.session.get(
                url, timeout=self.timeout, allow_redirects=True,
                stream=True)
        except requests.RequestException as exc:
            self.last_error = "richiesta fallita"
            if self.verbose:
                print("  ! errore: %s" % exc, file=sys.stderr)
            return None

        ctype = resp.headers.get("Content-Type", "")
        if ctype and not self._analyzable(ctype, resp.url or url):
            # Il chiamante vede stato e header e classifica l'URL come
            # non HTML; il corpo (magari un PDF da decine di MB) non
            # viene scaricato.
            resp.close()
            resp._content = b""
            if self.verbose:
                print("  - contenuto %s: corpo non scaricato"
                      % ctype.split(";")[0], file=sys.stderr)
            return resp

        limit_mb = self.max_bytes / 1048576.0
        declared = resp.headers.get("Content-Length", "")
        if declared.isdigit() and int(declared) > self.max_bytes:
            resp.close()
            self.last_error = (
                "corpo dichiarato di %.1f MB oltre il limite di "
                "%.0f MB" % (int(declared) / 1048576.0, limit_mb))
            if self.verbose:
                print("  ! %s" % self.last_error, file=sys.stderr)
            return None

        chunks: List[bytes] = []
        read = 0
        try:
            for chunk in resp.iter_content(chunk_size=65536):
                read += len(chunk)
                if read > self.max_bytes:
                    resp.close()
                    self.last_error = (
                        "corpo oltre il limite di %.0f MB" % limit_mb)
                    if self.verbose:
                        print("  ! %s, scaricamento interrotto"
                              % self.last_error, file=sys.stderr)
                    return None
                chunks.append(chunk)
        except requests.RequestException as exc:
            self.last_error = "richiesta fallita"
            if self.verbose:
                print("  ! errore: %s" % exc, file=sys.stderr)
            return None

        # Il corpo letto a blocchi va reso disponibile alle vie
        # ordinarie (resp.content / resp.text) usate dai chiamanti.
        resp._content = b"".join(chunks)
        return resp


# --------------------------------------------------------------------
# robots.txt e sitemap
# --------------------------------------------------------------------

class RobotsAudit:
    """Legge e interpreta il robots.txt del sito."""

    def __init__(self, base: str, fetcher: Fetcher) -> None:
        self.base = base
        self.fetcher = fetcher
        self.raw = ""
        self.found = False
        self.sitemaps: List[str] = []
        self.parser = RobotFileParser()

    def allowed(self, url: str) -> bool:
        """True se il robots.txt consente l'URL al nostro agente."""
        if not self.found:
            return True
        return self.parser.can_fetch(USER_AGENT_TOKEN, url)

    def run(self) -> List[Finding]:
        url = urljoin(self.base, "/robots.txt")
        resp = self.fetcher.get(url)
        findings: List[Finding] = []
        if resp is None or resp.status_code != 200:
            findings.append(Finding(
                AREA_TECH, SEV_WARNING, "robots.txt non raggiungibile",
                "Richiesta a %s fallita o non 200." % url,
                "Pubblica un robots.txt che dichiari la sitemap.",
                url=url))
            return findings

        self.found = True
        self.raw = resp.text
        self.parser.parse(self.raw.splitlines())
        self.sitemaps = re.findall(
            r"(?im)^\s*sitemap:\s*(\S+)", self.raw)

        findings.append(Finding(
            AREA_TECH, SEV_OK, "robots.txt presente",
            "%d righe." % len(self.raw.splitlines()), url=url))

        blocked = [name for name in AI_CRAWLERS
                   if not self.parser.can_fetch(name, self.base)]
        if blocked:
            findings.append(Finding(
                AREA_TECH, SEV_CRITICAL,
                "Crawler IA bloccati: %s" % ", ".join(blocked),
                "Questi agenti non possono accedere alla home. Se sono "
                "bloccati non entri in nessuna lista di recupero e "
                "l'RRF non ha nulla da fondere.",
                "Rimuovi i Disallow per gli agenti che vuoi ti citino.",
                url=url, weight=2.0))
        else:
            findings.append(Finding(
                AREA_TECH, SEV_OK, "Crawler IA ammessi",
                "Verificati: %s." % ", ".join(AI_CRAWLERS), url=url))

        if self.sitemaps:
            findings.append(Finding(
                AREA_TECH, SEV_OK, "Sitemap dichiarata nel robots.txt",
                ", ".join(self.sitemaps), url=url))
        else:
            findings.append(Finding(
                AREA_TECH, SEV_WARNING,
                "Nessuna sitemap dichiarata nel robots.txt",
                fix="Aggiungi la riga 'Sitemap: https://.../sitemap.xml'.",
                url=url))
        return findings


def parse_sitemap(url: str, fetcher: Fetcher,
                  depth: int = 0, seen: Optional[Set[str]] = None
                  ) -> List[Tuple[str, str]]:
    """Legge una sitemap (anche indice, anche .xml.gz).

    Restituisce coppie ``(loc, lastmod)``, con ``lastmod`` vuoto se
    assente. Le sitemap compresse vengono decompresse rispettando il
    tetto ``max_bytes`` del fetcher (il conteggio in download avviene
    prima dell'espansione).
    """
    seen = seen if seen is not None else set()
    if depth > 3 or url in seen:
        return []
    seen.add(url)
    resp = fetcher.get(url)
    if resp is None or resp.status_code != 200:
        return []
    body = resp.content
    if body[:2] == b"\x1f\x8b":
        try:
            with gzip.GzipFile(fileobj=io.BytesIO(body)) as handle:
                body = handle.read(fetcher.max_bytes + 1)
            if len(body) > fetcher.max_bytes:
                return []
        except OSError:
            return []
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        return []

    ns = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
    out: List[Tuple[str, str]] = []
    if root.tag.endswith("sitemapindex"):
        for node in root.findall("%ssitemap/%sloc" % (ns, ns)):
            if node.text:
                out.extend(parse_sitemap(
                    node.text.strip(), fetcher, depth + 1, seen))
    else:
        for node in root.findall("%surl" % ns):
            loc = node.find("%sloc" % ns)
            if loc is None or not loc.text:
                continue
            lastmod = node.find("%slastmod" % ns)
            out.append((loc.text.strip(),
                        (lastmod.text or "").strip()
                        if lastmod is not None else ""))
    return out


def discover_urls(base: str, robots: RobotsAudit, fetcher: Fetcher,
                  max_pages: int,
                  respect_robots: bool = False
                  ) -> Tuple[List[str], bool]:
    """Trova gli URL del sito da sitemap; se assente, crawla i link.

    Con ``max_pages`` inferiore agli URL in sitemap vengono preferite
    le pagine con ``lastmod`` piu' recente (ordinamento stabile: senza
    lastmod l'ordine della sitemap resta invariato).
    """
    candidates: List[Tuple[str, str]] = []
    for sm in robots.sitemaps or [urljoin(base, "/sitemap.xml"),
                                  urljoin(base, "/sitemap_index.xml")]:
        candidates.extend(parse_sitemap(sm, fetcher))
        if candidates:
            break

    host = urlparse(base).netloc
    lastmods: Dict[str, str] = {}
    for loc, lastmod in candidates:
        if urlparse(loc).netloc == host and loc not in lastmods:
            lastmods[loc] = lastmod
    # Il formato W3C (ISO 8601) ordina correttamente come stringa.
    urls = sorted(lastmods, key=lambda u: lastmods[u], reverse=True)
    if urls:
        return urls[:max_pages], True

    # Ripiego: crawling superficiale a partire dalla home.
    return crawl_links(base, fetcher, max_pages,
                       robots if respect_robots else None), False


def crawl_links(base: str, fetcher: Fetcher, max_pages: int,
                robots: Optional[RobotsAudit] = None) -> List[str]:
    """Crawling interno breadth-first, usato se manca la sitemap.

    Con ``robots`` valorizzato gli URL vietati al nostro agente non
    vengono scaricati.
    """
    host = urlparse(base).netloc
    queue: List[str] = [base]
    seen: Set[str] = {norm_url(base)}
    out: List[str] = []
    while queue and len(out) < max_pages:
        url = queue.pop(0)
        if robots is not None and not robots.allowed(url):
            continue
        resp = fetcher.get(url)
        if resp is None or resp.status_code != 200:
            continue
        if "html" not in resp.headers.get("Content-Type", ""):
            continue
        out.append(url)
        soup = BeautifulSoup(resp.text, "lxml")
        for anchor in soup.find_all("a", href=True):
            link = norm_url(urljoin(url, anchor["href"]))
            if urlparse(link).netloc != host or link in seen:
                continue
            if re.search(r"\.(pdf|jpe?g|png|gif|svg|zip|docx?)$",
                         link, re.I):
                continue
            seen.add(link)
            queue.append(link)
    return out


# --------------------------------------------------------------------
# Parsing della pagina
# --------------------------------------------------------------------

def _meta(soup: BeautifulSoup, name: str = "",
          prop: str = "") -> str:
    if name:
        tag = soup.find("meta", attrs={"name": re.compile(
            r"^%s$" % re.escape(name), re.I)})
    else:
        tag = soup.find("meta", attrs={"property": prop})
    if tag and tag.get("content"):
        return tag["content"].strip()
    return ""


def parse_page(url: str, resp: requests.Response) -> Page:
    """Estrae da una risposta HTTP tutti i segnali utili all'audit."""
    page = Page(url=url, status=resp.status_code,
                final_url=resp.url, redirects=len(resp.history),
                elapsed=resp.elapsed.total_seconds(),
                html_bytes=len(resp.content))
    soup = BeautifulSoup(resp.text, "lxml")

    page.script_bytes = sum(
        len(s.get_text() or "") for s in soup.find_all("script"))

    html_tag = soup.find("html")
    if html_tag:
        page.lang = (html_tag.get("lang") or "").strip()

    if soup.title and soup.title.string:
        page.title = soup.title.string.strip()
    page.description = _meta(soup, name="description")
    page.meta_robots = _meta(soup, name="robots")
    page.generator = _meta(soup, name="generator")

    for prop in ("og:title", "og:description", "og:type", "og:locale",
                 "og:image", "og:site_name"):
        value = _meta(soup, prop=prop)
        if value:
            page.og[prop] = value

    canonical = soup.find("link", rel=lambda v: v and "canonical" in v)
    if canonical and canonical.get("href"):
        page.canonical = canonical["href"].strip()

    page.hreflang = [
        link.get("hreflang", "") for link in soup.find_all("link")
        if link.get("hreflang")
    ]

    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()

    # Una sola passata: BeautifulSoup restituisce i nodi nell'ordine del
    # documento, quindi `page.blocks` conserva l'alternanza reale
    # heading/paragrafo su cui si basa il chunking.
    for node in soup.find_all(["h1", "h2", "h3", "h4", "p", "li"]):
        txt = " ".join(node.get_text(" ").split())
        if not txt:
            continue
        if node.name.startswith("h"):
            page.headings.append((int(node.name[1]), txt))
            page.blocks.append(("h", txt))
        elif len(txt) >= 40:
            page.paragraphs.append(txt)
            page.blocks.append(("p", txt))

    body = soup.find("body") or soup
    page.text = " ".join(body.get_text(" ").split())
    page.word_count = len(tokenize(page.text, keep_stopwords=True))

    images = soup.find_all("img")
    page.images = len(images)
    page.images_with_alt = sum(
        1 for img in images if (img.get("alt") or "").strip())

    host = urlparse(url).netloc
    for anchor in soup.find_all("a", href=True):
        target = urlparse(urljoin(url, anchor["href"])).netloc
        if target == host:
            page.internal_links += 1
        elif target:
            page.external_links += 1

    page.jsonld_types, page.jsonld_raw = extract_jsonld(resp.text)
    page.chunks = build_chunks(page)
    return page


def extract_jsonld(raw_html: str) -> Tuple[List[str], List[dict]]:
    """Estrae i blocchi JSON-LD e l'inventario dei tipi @type."""
    soup = BeautifulSoup(raw_html, "lxml")
    types: List[str] = []
    blocks: List[dict] = []

    def walk(node: object) -> None:
        if isinstance(node, dict):
            value = node.get("@type")
            if isinstance(value, str):
                types.append(value)
            elif isinstance(value, list):
                types.extend(str(v) for v in value)
            for sub in node.values():
                walk(sub)
        elif isinstance(node, list):
            for sub in node:
                walk(sub)

    selector = {"type": "application/ld+json"}
    for tag in soup.find_all("script", attrs=selector):
        payload = tag.string or tag.get_text() or ""
        try:
            data = json.loads(payload)
        except (json.JSONDecodeError, TypeError):
            continue
        blocks.append(data if isinstance(data, dict) else {"@graph": data})
        walk(data)
    return sorted(set(types)), blocks


def build_chunks(page: Page, target_words: int = 220) -> List[Chunk]:
    """Spezza la pagina in chunk come farebbe un indicizzatore RAG.

    Il taglio segue gli heading: e' l'approssimazione piu' vicina al
    comportamento reale delle pipeline di ingestione.
    """
    sections: List[Tuple[str, List[str]]] = []
    current_head = page.title or page.slug
    buffer: List[str] = []

    # Scansione in ordine di documento: ogni heading apre una nuova
    # sezione, i paragrafi successivi le appartengono.
    blocks = page.blocks or [("p", p) for p in page.paragraphs]
    for kind, text in blocks:
        if kind == "h":
            if buffer:
                sections.append((current_head, buffer))
                buffer = []
            current_head = text
        else:
            buffer.append(text)
    if buffer:
        sections.append((current_head, buffer))

    chunks: List[Chunk] = []
    for heading, paras in sections:
        words: List[str] = []
        for para in paras:
            words.extend(para.split())
            if len(words) >= target_words:
                chunks.append(Chunk(page.url, heading, " ".join(words),
                                    len(chunks)))
                words = []
        if words:
            chunks.append(Chunk(page.url, heading, " ".join(words),
                                len(chunks)))
    return [c for c in chunks if len(c.text.split()) >= 15]


# --------------------------------------------------------------------
# Recuperatori: BM25 (lessicale) e vettoriale (semantico)
# --------------------------------------------------------------------

class BM25Index:
    """Okapi BM25.

    idf(q)   = ln(1 + (N - n(q) + 0.5) / (n(q) + 0.5))
    score(d) = somma_q idf(q) * f*(k1+1) / (f + k1*(1-b+b*|d|/avgdl))

    Riferimento: Robertson & Zaragoza (2009).
    """

    def __init__(self, docs: Sequence[str], k1: float = 1.5,
                 b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self.corpus = [tokenize(d) for d in docs]
        self.doc_len = [len(d) for d in self.corpus]
        self.n_docs = len(self.corpus) or 1
        self.avgdl = (sum(self.doc_len) / self.n_docs) or 1.0
        self.freqs = [Counter(d) for d in self.corpus]
        df: Counter = Counter()
        for doc in self.corpus:
            df.update(set(doc))
        self.idf = {
            term: math.log(
                1.0 + (self.n_docs - n + 0.5) / (n + 0.5))
            for term, n in df.items()
        }

    def search(self, query: str) -> List[Tuple[int, float]]:
        """Restituisce (indice_doc, punteggio) ordinati decrescenti."""
        terms = tokenize(query)
        scores: List[Tuple[int, float]] = []
        for i, freq in enumerate(self.freqs):
            total = 0.0
            for term in terms:
                if term not in freq:
                    continue
                f = freq[term]
                denom = f + self.k1 * (
                    1 - self.b + self.b * self.doc_len[i] / self.avgdl)
                total += self.idf.get(term, 0.0) * f * (self.k1 + 1) / denom
            if total > 0:
                scores.append((i, total))
        scores.sort(key=lambda x: (-x[1], x[0]))
        return scores


class VectorIndex:
    """Recuperatore vettoriale.

    Se e' disponibile ``sentence-transformers`` usa embedding densi
    reali. Altrimenti ripiega su TF-IDF di n-grammi di caratteri con
    similarita' coseno: e' un *proxy* morfologico, non una vera
    rappresentazione semantica, e viene dichiarato come tale nel
    referto.
    """

    def __init__(self, docs: Sequence[str],
                 model_name: str = "") -> None:
        self.docs = list(docs)
        self.model = None
        self.mode = "char-tfidf"
        if model_name:
            self._load_model(model_name)
        if self.model is None:
            self._build_tfidf()

    def _load_model(self, model_name: str) -> None:
        try:
            from sentence_transformers import SentenceTransformer
            import numpy as np
        except ImportError:
            print("  ! sentence-transformers non disponibile: uso il "
                  "proxy TF-IDF su n-grammi.", file=sys.stderr)
            return
        try:
            self.model = SentenceTransformer(model_name)
            emb = self.model.encode(
                self.docs, normalize_embeddings=True,
                show_progress_bar=False)
            self.matrix = np.asarray(emb, dtype="float32")
            self.np = np
            self.mode = "embeddings:%s" % model_name
        except Exception as exc:  # pragma: no cover
            print("  ! modello non caricato (%s): uso TF-IDF." % exc,
                  file=sys.stderr)
            self.model = None

    def _build_tfidf(self) -> None:
        self.vectors: List[Dict[str, float]] = []
        grams = [char_ngrams(d) for d in self.docs]
        df: Counter = Counter()
        for gram in grams:
            df.update(set(gram))
        n_docs = len(self.docs) or 1
        self.idf = {
            g: math.log((1 + n_docs) / (1 + n)) + 1.0
            for g, n in df.items()
        }
        for gram in grams:
            self.vectors.append(self._vectorize(gram))

    def _vectorize(self, grams: Iterable[str]) -> Dict[str, float]:
        counts = Counter(grams)
        vec = {
            g: (1.0 + math.log(c)) * self.idf.get(g, 1.0)
            for g, c in counts.items()
        }
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        return {g: v / norm for g, v in vec.items()}

    def search(self, query: str) -> List[Tuple[int, float]]:
        if self.model is not None:
            emb = self.model.encode(
                [query], normalize_embeddings=True,
                show_progress_bar=False)
            sims = self.matrix @ self.np.asarray(emb[0], dtype="float32")
            pairs = [(i, float(s)) for i, s in enumerate(sims) if s > 0]
        else:
            qvec = self._vectorize(char_ngrams(query))
            pairs = []
            for i, vec in enumerate(self.vectors):
                small, big = (qvec, vec) if len(qvec) < len(vec) \
                    else (vec, qvec)
                sim = sum(v * big.get(g, 0.0) for g, v in small.items())
                if sim > 0:
                    pairs.append((i, sim))
        pairs.sort(key=lambda x: (-x[1], x[0]))
        return pairs


def reciprocal_rank_fusion(
        rankings: Sequence[Sequence[Tuple[int, float]]],
        k: int = 60, top_n: int = 10) -> List[Tuple[int, float]]:
    """Fonde piu' liste ordinate con la formula RRF.

        score(d) = somma_i 1 / (k + rank_i(d))

    Il rango parte da 1. Ogni lista pesa uguale, come in Elasticsearch.
    Riferimento: Cormack et al. (2009); Elastic; Microsoft Learn.
    """
    scores: Dict[int, float] = {}
    for ranking in rankings:
        for rank, (doc_id, _score) in enumerate(ranking, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
    fused = sorted(scores.items(), key=lambda x: (-x[1], x[0]))
    return fused[:top_n]


# --------------------------------------------------------------------
# Controlli per area
# --------------------------------------------------------------------

def _audit_redirects(pages: List[Page]) -> List[Finding]:
    """Rilievi sulle catene di redirect degli URL analizzati.

    Classifica ogni URL che atterra altrove rispetto a dove e' stato
    chiesto: solo schema (http che passa a https), solo www/non-www,
    oppure redirect generico (URL spostato). Le catene con piu' di un
    passaggio vengono evidenziate a parte.
    """
    out: List[Finding] = []
    http_to_https: List[Page] = []
    www_mismatch: List[Page] = []
    moved: List[Page] = []
    for p in pages:
        if not p.final_url:
            continue
        src, dst = urlparse(norm_url(p.url)), \
            urlparse(norm_url(p.final_url))
        if (src.scheme, src.netloc, src.path, src.query) == \
                (dst.scheme, dst.netloc, dst.path, dst.query):
            continue
        same_rest = (src.path, src.query) == (dst.path, dst.query)
        bare = dst.netloc[4:] if dst.netloc.startswith("www.") \
            else dst.netloc
        if same_rest and src.netloc == dst.netloc \
                and src.scheme == "http" and dst.scheme == "https":
            http_to_https.append(p)
        elif same_rest and {src.netloc, dst.netloc} == \
                {bare, "www." + bare}:
            www_mismatch.append(p)
        else:
            moved.append(p)

    if http_to_https:
        out.append(Finding(
            AREA_TECH, SEV_WARNING,
            "%d URL interni ancora in http" % len(http_to_https),
            "Reindirizzati alla versione https: %s. Ogni salto "
            "spreca crawl budget e diluisce i segnali."
            % ", ".join(p.url for p in http_to_https[:5]),
            "Aggiorna sitemap e link interni agli URL https "
            "definitivi."))
    if www_mismatch:
        out.append(Finding(
            AREA_TECH, SEV_WARNING,
            "%d URL con host misto www/non-www" % len(www_mismatch),
            "Reindirizzati all'host canonico: %s."
            % ", ".join("%s -> %s" % (p.url, p.final_url)
                        for p in www_mismatch[:5]),
            "Usa un solo host (con o senza www) in sitemap e link "
            "interni."))
    if moved:
        out.append(Finding(
            AREA_TECH, SEV_WARNING,
            "%d URL interni rispondono con redirect" % len(moved),
            "URL spostati: %s."
            % ", ".join("%s -> %s" % (p.url, p.final_url)
                        for p in moved[:5]),
            "Aggiorna sitemap e link interni alla destinazione "
            "finale dei redirect."))
    chains = [p for p in pages if p.redirects > 1]
    if chains:
        out.append(Finding(
            AREA_TECH, SEV_WARNING,
            "%d URL con catena di redirect multipla" % len(chains),
            ", ".join("%s (%d passaggi)" % (p.url, p.redirects)
                      for p in chains[:5]) + ".",
            "Fai puntare ogni redirect direttamente alla "
            "destinazione finale (un solo passaggio).", weight=2.0))
    if not (http_to_https or www_mismatch or moved):
        out.append(Finding(
            AREA_TECH, SEV_OK, "Nessun redirect interno",
            "Tutti gli URL analizzati rispondono direttamente."))
    return out


def audit_technical(pages: List[Page], base: str,
                    from_sitemap: bool) -> List[Finding]:
    """Controlli di indicizzabilita' e igiene tecnica."""
    out: List[Finding] = []
    good = [p for p in pages if p.ok]

    if urlparse(base).scheme != "https":
        out.append(Finding(
            AREA_TECH, SEV_CRITICAL, "Sito non in HTTPS",
            fix="Attiva un certificato TLS e reindirizza tutto a HTTPS.",
            url=base, weight=2.0))
    else:
        out.append(Finding(AREA_TECH, SEV_OK, "HTTPS attivo", url=base))

    broken = [p for p in pages if not p.ok]
    if broken:
        out.append(Finding(
            AREA_TECH, SEV_CRITICAL,
            "%d URL non raggiungibili o in errore" % len(broken),
            ", ".join("%s (%s)" % (p.url, p.status or p.error)
                      for p in broken[:5]),
            "Correggi o rimuovi dalla sitemap gli URL in errore."))

    out.extend(_audit_redirects(pages))

    soft404 = []
    for p in good:
        head = " ".join([p.title] + [t for _lvl, t in p.headings[:2]])
        if SOFT_404_RE.search(head) or (
                p.word_count <= SOFT_404_MAX_WORDS
                and SOFT_404_RE.search(p.text[:1500])):
            soft404.append(p)
    if soft404:
        out.append(Finding(
            AREA_TECH, SEV_WARNING,
            "%d possibile/i soft-404 (200 con contenuto \"non "
            "trovato\")" % len(soft404),
            "Rispondono 200 ma il contenuto dice che la pagina non "
            "esiste: %s. Entrano nell'indice come pagine vuote e "
            "diluiscono i segnali del sito."
            % ", ".join(p.url for p in soft404[:5]),
            "Fai rispondere 404 (o 410) agli URL inesistenti e "
            "togli quelli vuoti dalla sitemap.", weight=2.0))

    n_pages = len(good)
    if n_pages == 0:
        out.append(Finding(
            AREA_TECH, SEV_CRITICAL,
            "Nessuna pagina analizzabile",
            "Nessun URL ha restituito HTML valido: il sito e' "
            "irraggiungibile, blocca lo user-agent dello strumento o "
            "risponde solo a JavaScript. L'audit dei contenuti non e' "
            "stato eseguito.",
            "Verifica che il sito risponda e che non filtri i crawler.",
            weight=3.0))
    elif n_pages == 1:
        out.append(Finding(
            AREA_TECH, SEV_CRITICAL,
            "Superficie indicizzabile minima (1 pagina)",
            "Con un solo documento la somma RRF non ha addendi: non "
            "esistono passaggi distinti da far emergere.",
            "Crea pagine autonome per ogni tema/servizio.",
            weight=3.0))
    elif n_pages < 5:
        out.append(Finding(
            AREA_TECH, SEV_WARNING,
            "Poche pagine indicizzabili (%d)" % n_pages,
            fix="Amplia la superficie: una pagina per intento.",
            weight=2.0))
    else:
        out.append(Finding(
            AREA_TECH, SEV_OK,
            "%d pagine indicizzabili analizzate" % n_pages))

    if not from_sitemap:
        out.append(Finding(
            AREA_TECH, SEV_WARNING, "Sitemap XML assente o illeggibile",
            "URL individuati tramite crawling dei link interni.",
            "Pubblica una sitemap XML e dichiarala nel robots.txt."))

    placeholders = [
        p for p in good
        if p.slug in PLACEHOLDER_SLUGS
        or PLACEHOLDER_TEXT_RE.search(p.text[:2000])
    ]
    if placeholders:
        out.append(Finding(
            AREA_TECH, SEV_CRITICAL,
            "%d pagina/e segnaposto indicizzabili" % len(placeholders),
            "Rilevate: %s. Sono contenuti di default del CMS: rumore "
            "puro nell'indice e segnale di sito incompiuto."
            % ", ".join(p.url for p in placeholders[:5]),
            "Cancellale, oppure imposta noindex e togliile dalla "
            "sitemap.", weight=2.0))

    noindex = [p for p in good
               if "noindex" in (p.meta_robots or "").lower()]
    if noindex:
        out.append(Finding(
            AREA_TECH, SEV_WARNING,
            "%d pagina/e con meta robots noindex" % len(noindex),
            ", ".join(p.url for p in noindex[:5]),
            "Verifica che l'esclusione sia voluta."))

    no_canonical = [p for p in good if not p.canonical]
    if no_canonical:
        out.append(Finding(
            AREA_TECH, SEV_WARNING,
            "%d pagina/e senza canonical" % len(no_canonical),
            fix="Dichiara <link rel=\"canonical\"> su ogni pagina."))
    elif good:
        out.append(Finding(AREA_TECH, SEV_OK, "Canonical presenti"))

    no_lang = [p for p in good if not p.lang]
    if no_lang:
        out.append(Finding(
            AREA_TECH, SEV_WARNING,
            "%d pagina/e senza attributo lang" % len(no_lang),
            fix="Imposta <html lang=\"it\">: aiuta la selezione del "
                "modello linguistico in fase di analisi."))

    js_heavy = [
        p for p in good
        if p.html_bytes > 0
        and p.word_count < 120
        and p.script_bytes > p.html_bytes * 0.4
    ]
    if js_heavy:
        out.append(Finding(
            AREA_TECH, SEV_CRITICAL,
            "%d pagina/e con testo scarso e molto JavaScript"
            % len(js_heavy),
            "Il contenuto potrebbe essere reso lato client e non "
            "essere visto dai crawler.",
            "Attiva rendering server-side o pre-rendering.",
            weight=2.0))
    elif good:
        out.append(Finding(
            AREA_TECH, SEV_OK,
            "Contenuto presente nell'HTML iniziale"))

    slow = [p for p in good if p.elapsed > 2.0]
    if slow:
        out.append(Finding(
            AREA_TECH, SEV_WARNING,
            "%d pagina/e con risposta oltre 2 s" % len(slow),
            "Piu' lenta: %.2f s." % max(p.elapsed for p in slow),
            "Ottimizza cache e TTFB."))

    langs = {p.lang.split("-")[0] for p in good if p.lang}
    multilingual = len(langs) > 1
    has_hreflang = any(p.hreflang for p in good)
    if multilingual and not has_hreflang:
        out.append(Finding(
            AREA_TECH, SEV_WARNING,
            "Sito multilingua senza hreflang",
            "Lingue rilevate: %s." % ", ".join(sorted(langs)),
            "Dichiara hreflang reciproci fra le versioni."))
    elif not multilingual:
        out.append(Finding(
            AREA_TECH, SEV_INFO, "Sito monolingua: hreflang non "
            "necessario"))
    return out


def audit_lexical(pages: List[Page]) -> List[Finding]:
    """Segnali che alimentano il recuperatore lessicale (BM25)."""
    out: List[Finding] = []
    good = [p for p in pages if p.ok]
    if not good:
        return out

    host = urlparse(good[0].url).netloc.lower()

    missing_title = [p for p in good if not p.title]
    bad_title = [
        p for p in good if p.title and (
            host in p.title.lower().replace("www.", "")
            and len(p.title) < TITLE_MAX
            or len(p.title) < TITLE_MIN
            or len(p.title) > TITLE_MAX
        )
    ]
    dup_title = [t for t, c in Counter(
        p.title for p in good if p.title).items() if c > 1]

    if missing_title:
        out.append(Finding(
            AREA_LEX, SEV_CRITICAL,
            "%d pagina/e senza <title>" % len(missing_title),
            fix="Il title e' il segnale lessicale a peso piu' alto.",
            weight=2.0))
    if bad_title:
        out.append(Finding(
            AREA_LEX, SEV_CRITICAL,
            "%d title non ottimizzati" % len(bad_title),
            "Esempi: %s" % " | ".join(
                "%r (%d car.)" % (p.title, len(p.title))
                for p in bad_title[:3]),
            "Title unico, 30-65 caratteri, con i termini di ricerca "
            "reali; evita il nome dominio come titolo.", weight=2.0))
    if dup_title:
        out.append(Finding(
            AREA_LEX, SEV_WARNING,
            "%d title duplicati fra pagine" % len(dup_title),
            "; ".join(dup_title[:3]),
            "Ogni pagina deve avere un title distinto."))
    if not (missing_title or bad_title or dup_title):
        out.append(Finding(AREA_LEX, SEV_OK, "Title ben impostati"))

    no_desc = [p for p in good if not p.description]
    weak_desc = [
        p for p in good
        if p.description and len(p.description) < DESC_MIN
    ]
    long_desc = [p for p in good if len(p.description) > DESC_MAX]
    if no_desc:
        out.append(Finding(
            AREA_LEX, SEV_CRITICAL,
            "%d pagina/e senza meta description" % len(no_desc),
            fix="Scrivi 110-165 caratteri con servizio e territorio.",
            weight=1.5))
    if weak_desc:
        out.append(Finding(
            AREA_LEX, SEV_WARNING,
            "%d meta description troppo corte" % len(weak_desc),
            "Esempi: %s" % " | ".join(
                repr(p.description) for p in weak_desc[:3]),
            "Una description che ripete solo il nome dell'azienda non "
            "porta alcun segnale."))
    if long_desc:
        out.append(Finding(
            AREA_LEX, SEV_INFO,
            "%d meta description oltre %d caratteri"
            % (len(long_desc), DESC_MAX)))
    if not (no_desc or weak_desc):
        out.append(Finding(
            AREA_LEX, SEV_OK, "Meta description presenti e di lunghezza "
            "adeguata"))

    no_h1 = [p for p in good
             if not any(lv == 1 for lv, _ in p.headings)]
    multi_h1 = [p for p in good
                if sum(1 for lv, _ in p.headings if lv == 1) > 1]
    if no_h1:
        out.append(Finding(
            AREA_LEX, SEV_CRITICAL, "%d pagina/e senza H1" % len(no_h1),
            fix="Un solo H1 per pagina, con i termini principali.",
            weight=1.5))
    if multi_h1:
        out.append(Finding(
            AREA_LEX, SEV_WARNING,
            "%d pagina/e con piu' H1" % len(multi_h1)))
    if not (no_h1 or multi_h1):
        out.append(Finding(AREA_LEX, SEV_OK, "Struttura H1 corretta"))

    thin = [p for p in good if p.word_count < THIN_CONTENT_WORDS]
    if thin:
        out.append(Finding(
            AREA_LEX, SEV_CRITICAL,
            "%d pagina/e sotto %d parole"
            % (len(thin), THIN_CONTENT_WORDS),
            "Media sito: %d parole. Con cosi' poco testo i termini "
            "utili non raggiungono una frequenza sufficiente perche' "
            "BM25 li valorizzi."
            % (sum(p.word_count for p in good) / len(good)),
            "Porta le pagine chiave verso le %d+ parole con contenuto "
            "informativo, non promozionale." % GOOD_CONTENT_WORDS,
            weight=2.0))
    else:
        out.append(Finding(
            AREA_LEX, SEV_OK, "Volume di testo adeguato",
            "Media: %d parole per pagina."
            % (sum(p.word_count for p in good) / len(good))))

    acronyms = find_acronyms(good)
    expanded = {a for a, ok_ in acronyms.items() if ok_}
    if acronyms and len(expanded) < len(acronyms) / 2:
        out.append(Finding(
            AREA_LEX, SEV_WARNING,
            "Sigle usate senza forma estesa",
            "Non esplicitate: %s." % ", ".join(
                sorted(set(acronyms) - expanded)[:8]),
            "Scrivi 'SIGLA (forma estesa)' almeno alla prima "
            "occorrenza: copre entrambe le formulazioni di ricerca."))
    elif acronyms:
        out.append(Finding(
            AREA_LEX, SEV_OK,
            "Sigle accompagnate dalla forma estesa",
            ", ".join(sorted(expanded)[:8])))

    bad_slug = [p for p in good if re.search(r"[_%]|\d{4,}", p.slug)]
    if bad_slug:
        out.append(Finding(
            AREA_LEX, SEV_WARNING,
            "%d slug poco parlanti" % len(bad_slug),
            ", ".join(p.slug for p in bad_slug[:5]),
            "Usa slug tematici con trattini."))
    else:
        out.append(Finding(AREA_LEX, SEV_OK, "Slug tematici e leggibili"))

    total_img = sum(p.images for p in good)
    with_alt = sum(p.images_with_alt for p in good)
    if total_img and with_alt / total_img < 0.8:
        out.append(Finding(
            AREA_LEX, SEV_WARNING,
            "Attributi alt incompleti (%d/%d)" % (with_alt, total_img),
            fix="L'alt e' testo indicizzabile oltre che accessibilita'."))
    elif total_img:
        out.append(Finding(
            AREA_LEX, SEV_OK,
            "Attributi alt presenti (%d/%d)" % (with_alt, total_img)))
    return out


def find_acronyms(pages: List[Page]) -> Dict[str, bool]:
    """Trova le sigle e verifica se compaiono con la forma estesa."""
    text = " ".join(p.text for p in pages)
    result: Dict[str, bool] = {}
    for match in re.finditer(r"\b([A-Z]{2,6})\b", text):
        acr = match.group(1)
        if acr in {"IVA", "SRL", "SPA", "PEC", "CAP", "IT", "EU"}:
            continue
        pattern = re.compile(
            r"%s\s*[\(—\-–—:]|[\(—\-–—:]\s*%s"
            % (re.escape(acr), re.escape(acr)))
        result[acr] = bool(pattern.search(text))
    return dict(list(result.items())[:40])


def audit_semantic(pages: List[Page]) -> List[Finding]:
    """Segnali che alimentano il recuperatore vettoriale."""
    out: List[Finding] = []
    good = [p for p in pages if p.ok]
    if not good:
        return out

    chunks = [c for p in good for c in p.chunks]
    if not chunks:
        out.append(Finding(
            AREA_SEM, SEV_CRITICAL, "Nessun chunk estraibile",
            "Il sito non offre passaggi di testo indicizzabili.",
            "Scrivi paragrafi discorsivi di almeno 40-50 parole.",
            weight=3.0))
        return out

    out.append(Finding(
        AREA_SEM, SEV_OK if len(chunks) >= 20 else SEV_WARNING,
        "%d chunk indicizzabili su %d pagine"
        % (len(chunks), len(good)),
        "Ogni chunk e' un'occasione di comparire nelle liste: nella "
        "somma RRF il numero di passaggi pertinenti e' il vero "
        "moltiplicatore.",
        "" if len(chunks) >= 20 else
        "Aumenta il numero di passaggi tematici autonomi.",
        weight=2.0))

    anaphoric = [c for c in chunks if ANAPHORA_RE.match(c.text.strip())]
    ratio = len(anaphoric) / len(chunks)
    if ratio > 0.2:
        out.append(Finding(
            AREA_SEM, SEV_WARNING,
            "%.0f%% dei chunk non e' autoconsistente" % (ratio * 100),
            "Iniziano con un riferimento anaforico (questo, tale, "
            "cio'...): estratti da soli non rispondono a nulla.",
            "Riscrivi le aperture nominando esplicitamente il "
            "soggetto."))
    else:
        out.append(Finding(
            AREA_SEM, SEV_OK,
            "Chunk in larga parte autoconsistenti (%.0f%% anaforici)"
            % (ratio * 100)))

    headings = [h for p in good for _, h in p.headings]
    questions = [h for h in headings if is_question(h)]
    q_ratio = len(questions) / len(headings) if headings else 0.0
    if q_ratio < 0.1:
        out.append(Finding(
            AREA_SEM, SEV_CRITICAL,
            "Quasi nessun heading in forma di domanda (%d su %d)"
            % (len(questions), len(headings)),
            "E' il formato che i motori IA citano piu' spesso: "
            "domanda esplicita seguita da risposta diretta.",
            "Aggiungi heading tipo \"Cos'e' X?\", \"Come funziona X?\", "
            "\"Quanto costa X?\" con risposta secca in 2-3 righe.",
            weight=2.0))
    else:
        out.append(Finding(
            AREA_SEM, SEV_OK,
            "%d heading in forma di domanda (%.0f%%)"
            % (len(questions), q_ratio * 100)))

    has_faq = any(FAQ_HINT_RE.search(h) for h in headings) or any(
        FAQ_HINT_RE.search(p.text[:4000]) for p in good)
    if has_faq:
        out.append(Finding(AREA_SEM, SEV_OK, "Sezione FAQ rilevata"))
    else:
        out.append(Finding(
            AREA_SEM, SEV_CRITICAL, "Nessuna sezione FAQ",
            "Le FAQ allineano un chunk a un intento preciso e "
            "alimentano entrambi gli assi contemporaneamente.",
            "Aggiungi FAQ per pagina, marcate con FAQPage JSON-LD.",
            weight=1.5))

    definitions = sum(1 for c in chunks if DEFINITION_RE.search(c.text))
    def_ratio = definitions / len(chunks)
    if def_ratio < 0.1:
        out.append(Finding(
            AREA_SEM, SEV_WARNING,
            "Contenuto povero di definizioni (%.0f%% dei chunk)"
            % (def_ratio * 100),
            "Senza passaggi che spiegano *cos'e'* una cosa, gli "
            "embedding restano lontani dalle query informative.",
            "Aggiungi per ogni tema: cos'e' / come funziona / quando "
            "serve / esempio."))
    else:
        out.append(Finding(
            AREA_SEM, SEV_OK,
            "Presenti passaggi definitori (%.0f%% dei chunk)"
            % (def_ratio * 100)))

    examples = sum(1 for c in chunks if EXAMPLE_RE.search(c.text))
    if examples / len(chunks) < 0.05:
        out.append(Finding(
            AREA_SEM, SEV_WARNING, "Quasi nessun esempio concreto",
            fix="Esempi e casi studio sono i contenuti a piu' alta "
                "densita' semantica."))
    else:
        out.append(Finding(
            AREA_SEM, SEV_OK, "%d chunk con esempi concreti" % examples))

    tokens = tokenize(" ".join(c.text for c in chunks))
    unique = len(set(tokens))
    if unique < 300:
        out.append(Finding(
            AREA_SEM, SEV_WARNING,
            "Vocabolario ristretto (%d termini distinti)" % unique,
            "Poca varieta' lessicale significa copertura semantica "
            "limitata: intercetti poche riformulazioni della stessa "
            "domanda.",
            "Amplia i temi trattati e le formulazioni usate."))
    else:
        out.append(Finding(
            AREA_SEM, SEV_OK,
            "Vocabolario ampio (%d termini distinti)" % unique))
    return out


def is_question(text: str) -> bool:
    """Riconosce un heading formulato come domanda."""
    clean = text.strip().lower()
    if clean.endswith("?"):
        return True
    return any(clean.startswith(w) for w in QUESTION_STARTERS)


def audit_structured_data(pages: List[Page]) -> List[Finding]:
    """Presenza e copertura del markup Schema.org."""
    out: List[Finding] = []
    good = [p for p in pages if p.ok]
    if not good:
        return out

    all_types: Counter = Counter()
    for page in good:
        all_types.update(page.jsonld_types)

    if not all_types:
        out.append(Finding(
            AREA_SD, SEV_CRITICAL, "Nessun dato strutturato JSON-LD",
            "Senza markup l'entita' non viene riconosciuta e i "
            "contenuti non sono eleggibili per i risultati arricchiti.",
            "Aggiungi almeno Organization (o LocalBusiness), poi "
            "Service, FAQPage, BreadcrumbList, Article.",
            weight=2.0))
        return out

    out.append(Finding(
        AREA_SD, SEV_OK, "JSON-LD presente",
        "Tipi rilevati: %s." % ", ".join(
            "%s (x%d)" % (t, c) for t, c in all_types.most_common(12))))

    entity_types = {"Organization", "LocalBusiness", "Corporation",
                    "ProfessionalService", "Person"}
    if not entity_types & set(all_types):
        out.append(Finding(
            AREA_SD, SEV_CRITICAL, "Entita' principale non dichiarata",
            fix="Aggiungi Organization o LocalBusiness con nome, "
                "indirizzo, contatti e identificativi fiscali.",
            weight=1.5))
    else:
        out.append(Finding(
            AREA_SD, SEV_OK, "Entita' principale dichiarata"))

    for wanted, sev, why in (
        ("FAQPage", SEV_WARNING,
         "Le FAQ marcate sono il formato piu' citato dai motori IA."),
        ("BreadcrumbList", SEV_INFO,
         "Chiarisce la gerarchia del sito."),
        ("WebSite", SEV_INFO, "Utile per il sitelinks searchbox."),
    ):
        if wanted not in all_types:
            out.append(Finding(
                AREA_SD, sev, "Markup %s assente" % wanted, why,
                "Aggiungi il tipo %s dove pertinente." % wanted))

    covered = sum(1 for p in good if p.jsonld_types)
    if covered < len(good):
        out.append(Finding(
            AREA_SD, SEV_WARNING,
            "JSON-LD solo su %d pagine su %d" % (covered, len(good)),
            fix="Estendi il markup a tutte le pagine rilevanti."))
    return out


# --------------------------------------------------------------------
# Simulazione RRF
# --------------------------------------------------------------------

@dataclass
class QueryResult:
    """Esito della fusione RRF per una singola query."""

    query: str
    lexical_top: List[str] = field(default_factory=list)
    vector_top: List[str] = field(default_factory=list)
    fused_top: List[Tuple[str, float]] = field(default_factory=list)
    consensus: int = 0
    covered: bool = False


def auto_queries(pages: List[Page], limit: int = 12) -> List[str]:
    """Genera query informative dai temi rilevati sul sito.

    I temi sono bigrammi di termini adiacenti negli heading e nei title:
    un bigramma ("drenaggio linfatico") descrive un argomento, un token
    isolato ("funziona") no. I termini gia' presenti nei template
    interrogativi sono esclusi per non produrre query degeneri del tipo
    "come funziona funziona".
    """
    templates = ("cos'e' %s", "come funziona %s", "quanto costa %s")
    banned = {"cosa", "costa", "costo", "funziona", "funzionamento",
              "come", "quanto", "quali", "perche", "perché"}
    counts: Counter = Counter()

    for page in pages:
        sources = [h for _, h in page.headings]
        if page.title:
            sources.append(page.title.split("|")[0])
        for text in sources:
            terms = [t for t in tokenize(text)
                     if len(t) > 3 and t not in banned]
            for first, second in zip(terms, terms[1:]):
                counts["%s %s" % (first, second)] += 3
            if len(terms) == 1:
                counts[terms[0]] += 1

    topics = [t for t, _ in counts.most_common(limit)]
    if not topics:  # nessun bigramma utile: ripiego sui singoli termini
        single: Counter = Counter()
        for page in pages:
            single.update(t for t in tokenize(page.text)
                          if len(t) > 4 and t not in banned)
        topics = [t for t, _ in single.most_common(limit)]

    queries: List[str] = []
    for topic in topics:
        for tpl in templates:
            queries.append(tpl % topic)
            if len(queries) >= limit:
                return queries
    return queries


def simulate_rrf(pages: List[Page], queries: Sequence[str],
                 k: int = 60, top_n: int = 5,
                 model_name: str = "") -> Tuple[
                     List[QueryResult], List[Finding], str]:
    """Esegue BM25 + vettoriale e ne fonde i risultati con RRF."""
    chunks = [c for p in pages if p.ok for c in p.chunks]
    findings: List[Finding] = []
    if not chunks or not queries:
        findings.append(Finding(
            AREA_RRF, SEV_CRITICAL,
            "Simulazione RRF non eseguibile",
            "Servono almeno un chunk e una query.", weight=2.0))
        return [], findings, "n/d"

    corpus = [c.searchable for c in chunks]
    bm25 = BM25Index(corpus)
    vector = VectorIndex(corpus, model_name=model_name)

    results: List[QueryResult] = []
    for query in queries:
        lex = bm25.search(query)[:top_n * 4]
        vec = vector.search(query)[:top_n * 4]
        fused = reciprocal_rank_fusion([lex, vec], k=k, top_n=top_n)
        lex_ids = {i for i, _ in lex[:top_n]}
        vec_ids = {i for i, _ in vec[:top_n]}
        consensus = len(lex_ids & vec_ids)
        results.append(QueryResult(
            query=query,
            lexical_top=[chunks[i].label for i, _ in lex[:top_n]],
            vector_top=[chunks[i].label for i, _ in vec[:top_n]],
            fused_top=[(chunks[i].label, round(s, 5))
                       for i, s in fused],
            consensus=consensus,
            covered=bool(lex) and bool(vec),
        ))

    avg_consensus = sum(r.consensus for r in results) / len(results)
    consensus_ratio = avg_consensus / top_n
    if consensus_ratio < 0.2:
        sev, note = SEV_CRITICAL, (
            "Le due liste puntano a passaggi diversi: nessun documento "
            "accumula punteggio su entrambi gli assi.")
    elif consensus_ratio < 0.45:
        sev, note = SEV_WARNING, (
            "Consenso parziale fra i due recuperatori.")
    else:
        sev, note = SEV_OK, (
            "Buona sovrapposizione fra recupero lessicale e "
            "vettoriale.")
    findings.append(Finding(
        AREA_RRF, sev,
        "Consenso medio fra le liste: %.1f/%d (%.0f%%)"
        % (avg_consensus, top_n, consensus_ratio * 100),
        note + " Nella formula RRF un documento presente in entrambe "
        "le liste somma due addendi 1/(k+rank) e supera chi domina una "
        "lista sola.",
        "Ottimizza gli stessi passaggi su entrambi gli assi: termini "
        "espliciti (BM25) e spiegazione completa (vettoriale).",
        weight=2.0))

    uncovered = [r.query for r in results if not r.covered]
    if uncovered:
        findings.append(Finding(
            AREA_RRF, SEV_CRITICAL,
            "%d query senza alcun risultato" % len(uncovered),
            "Nessun chunk del sito risponde a: %s."
            % "; ".join(uncovered[:5]),
            "Crea contenuti dedicati a questi intenti.", weight=2.0))
    else:
        findings.append(Finding(
            AREA_RRF, SEV_OK,
            "Tutte le %d query trovano almeno un passaggio"
            % len(results)))

    return results, findings, vector.mode


# --------------------------------------------------------------------
# Confronto competitivo (share of voice)
# --------------------------------------------------------------------

@dataclass
class ShareResult:
    """Esito della fusione su corpus congiunto per una query."""

    query: str
    owners: List[str] = field(default_factory=list)
    labels: List[str] = field(default_factory=list)
    mine_in_top: int = 0
    best_rank_mine: int = 0  # 0 = assente dai primi top_n


def crawl_corpus(base: str, fetcher: Fetcher, max_pages: int,
                 respect_robots: bool = False) -> List[Page]:
    """Scansione leggera di un sito terzo: pagine e chunk, nessun
    rilievo. Usata per i concorrenti del confronto competitivo."""
    robots = RobotsAudit(base, fetcher)
    robots.run()  # rilievi ignorati: servono solo sitemap e permessi
    urls, _ = discover_urls(base, robots, fetcher, max_pages,
                            respect_robots)
    if norm_url(base) not in {norm_url(u) for u in urls}:
        urls.insert(0, base)
    if respect_robots:
        urls = [u for u in urls if robots.allowed(u)]
    pages: List[Page] = []
    for url in urls[:max_pages]:
        resp = fetcher.get(url)
        if resp is None:
            continue
        if "html" not in resp.headers.get("Content-Type", ""):
            continue
        pages.append(parse_page(url, resp))
    pages, _ = dedupe_pages(pages)
    return pages


def simulate_share_of_voice(
        base: str, own_chunks: List[Chunk],
        corpora: Dict[str, List[Chunk]], queries: Sequence[str],
        k: int = 60, top_n: int = 5, model_name: str = "") -> Tuple[
            Optional[Dict[str, object]], List[Finding]]:
    """Fonde il corpus proprio con quelli dei concorrenti e misura
    quanti dei primi ``top_n`` posti fusi appartengono a ciascun sito.

    Le query restano quelle del sito principale: la domanda a cui
    risponde e' "sui MIEI temi, chi viene recuperato al posto mio?".
    """
    main_host = urlparse(base).netloc
    findings: List[Finding] = []

    for host, cchunks in corpora.items():
        if not cchunks:
            findings.append(Finding(
                AREA_RRF, SEV_INFO,
                "Concorrente %s senza contenuto recuperabile" % host,
                "Nessuna pagina analizzabile: il confronto lo "
                "include con 0 passaggi."))

    chunks: List[Chunk] = list(own_chunks)
    owners: List[str] = [main_host] * len(own_chunks)
    for host, cchunks in corpora.items():
        chunks.extend(cchunks)
        owners.extend([host] * len(cchunks))

    if not chunks or not queries:
        findings.append(Finding(
            AREA_RRF, SEV_CRITICAL,
            "Confronto competitivo non eseguibile",
            "Servono almeno un chunk e una query.", weight=2.0))
        return None, findings

    corpus = [c.searchable for c in chunks]
    bm25 = BM25Index(corpus)
    vector = VectorIndex(corpus, model_name=model_name)
    sites = [main_host] + list(corpora)
    slot_counts = {host: 0 for host in sites}
    total_slots = 0
    results: List[ShareResult] = []

    for query in queries:
        lex = bm25.search(query)[:top_n * 4]
        vec = vector.search(query)[:top_n * 4]
        fused = reciprocal_rank_fusion([lex, vec], k=k, top_n=top_n)
        res = ShareResult(query=query)
        for rank, (idx, _score) in enumerate(fused, start=1):
            res.owners.append(owners[idx])
            res.labels.append(chunks[idx].label)
            slot_counts[owners[idx]] += 1
            if owners[idx] == main_host:
                res.mine_in_top += 1
                if not res.best_rank_mine:
                    res.best_rank_mine = rank
        total_slots += len(fused)
        results.append(res)

    share = {host: (slot_counts[host] / total_slots
                    if total_slots else 0.0) for host in sites}
    parity = 1.0 / max(1, len(sites))
    mine = share[main_host]
    breakdown = " · ".join(
        "%s %.0f%%%s" % (host, share[host] * 100,
                         " (tuo sito)" if host == main_host else "")
        for host in sites)

    if mine < parity * 0.5:
        sev, note = SEV_CRITICAL, (
            "I concorrenti occupano i posti che servirebbero a te: "
            "sui tuoi stessi temi vieni recuperato raramente.")
    elif mine < parity:
        sev, note = SEV_WARNING, (
            "Sei sotto la parita': sui tuoi temi i concorrenti "
            "vengono recuperati piu' spesso di te.")
    else:
        sev, note = SEV_OK, (
            "Tieni testa ai concorrenti sui tuoi temi.")
    findings.append(Finding(
        AREA_RRF, sev,
        "Share of voice: %.0f%% dei primi %d posti fusi "
        "(parita' %.0f%%)" % (mine * 100, top_n, parity * 100),
        "%s Ripartizione: %s." % (note, breakdown),
        "Rafforza i passaggi sulle query dove i concorrenti ti "
        "superano: stessi termini espliciti, risposta completa.",
        weight=2.0))

    absent = [r.query for r in results if r.mine_in_top == 0]
    if absent:
        sev = (SEV_CRITICAL if len(absent) * 2 > len(results)
               else SEV_WARNING)
        findings.append(Finding(
            AREA_RRF, sev,
            "%d query su %d vinte interamente dai concorrenti"
            % (len(absent), len(results)),
            "Nessun tuo passaggio fra i primi %d per: %s."
            % (top_n, "; ".join(absent[:5])),
            "Crea o riscrivi contenuti dedicati a questi intenti.",
            weight=2.0))
    else:
        findings.append(Finding(
            AREA_RRF, SEV_OK,
            "Presente nei primi %d per tutte le %d query"
            % (top_n, len(results))))

    payload: Dict[str, object] = {
        "main": main_host,
        "top_n": top_n,
        "sites": sites,
        "share": {h: round(share[h] * 100, 1) for h in sites},
        "chunks": {main_host: len(own_chunks),
                   **{h: len(c) for h, c in corpora.items()}},
        "queries": [asdict(r) for r in results],
    }
    return payload, findings


# --------------------------------------------------------------------
# Punteggi e referto
# --------------------------------------------------------------------

def area_score(findings: Sequence[Finding], area: str) -> Optional[float]:
    """Punteggio 0-100 dell'area, pesato per gravita'."""
    graded = [f for f in findings
              if f.area == area and f.severity in _SEVERITY_FACTOR]
    if not graded:
        return None
    total = sum(f.weight for f in graded)
    got = sum(f.weight * _SEVERITY_FACTOR[f.severity] for f in graded)
    return round(100.0 * got / total, 1) if total else None


def overall_score(scores: Dict[str, Optional[float]]) -> float:
    """Media pesata delle aree; lessicale e semantica pesano di piu'."""
    weights = {AREA_TECH: 1.0, AREA_LEX: 1.5, AREA_SEM: 1.5,
               AREA_SD: 1.0, AREA_RRF: 1.5}
    num = sum(weights[a] * s for a, s in scores.items() if s is not None)
    den = sum(weights[a] for a, s in scores.items() if s is not None)
    return round(num / den, 1) if den else 0.0


def render_text(base: str, pages: List[Page],
                findings: List[Finding],
                scores: Dict[str, Optional[float]],
                results: List[QueryResult], mode: str,
                k: int = 60,
                competitive: Optional[Dict[str, object]] = None
                ) -> str:
    """Referto testuale per la console."""
    marks = {SEV_CRITICAL: "[X]", SEV_WARNING: "[!]",
             SEV_OK: "[v]", SEV_INFO: "[i]"}
    lines: List[str] = []
    lines.append("=" * 70)
    lines.append("AUDIT SEO + RRF  ·  %s" % base)
    lines.append("=" * 70)
    lines.append("Pagine analizzate : %d" % len([p for p in pages if p.ok]))
    lines.append("Chunk indicizzati : %d"
                 % sum(len(p.chunks) for p in pages if p.ok))
    lines.append("Recuperatore vett.: %s" % mode)
    lines.append("")
    lines.append("PUNTEGGI")
    for area, score in scores.items():
        if score is None:
            continue
        bar = "#" * int(score / 5)
        lines.append("  %-24s %5.1f/100  %s" % (area, score, bar))
    lines.append("  %-24s %5.1f/100" % ("COMPLESSIVO",
                                        overall_score(scores)))
    lines.append("")

    for area in (AREA_TECH, AREA_LEX, AREA_SEM, AREA_SD, AREA_RRF):
        subset = [f for f in findings if f.area == area]
        if not subset:
            continue
        lines.append("-" * 70)
        lines.append(area.upper())
        lines.append("-" * 70)
        order = {SEV_CRITICAL: 0, SEV_WARNING: 1, SEV_INFO: 2,
                 SEV_OK: 3}
        for finding in sorted(subset, key=lambda f: order[f.severity]):
            lines.append("%s %s" % (marks[finding.severity],
                                    finding.title))
            if finding.detail:
                lines.append("    %s" % finding.detail)
            if finding.fix:
                lines.append("    -> Fix: %s" % finding.fix)
        lines.append("")

    if results:
        lines.append("-" * 70)
        lines.append("DETTAGLIO SIMULAZIONE RRF")
        lines.append("-" * 70)
        for res in results:
            lines.append("Query: %s   (consenso %d)"
                         % (res.query, res.consensus))
            for rank, (label, score) in enumerate(res.fused_top, 1):
                lines.append("   %d. %-52s  %.5f"
                             % (rank, label[:52], score))
            if not res.fused_top:
                lines.append("   (nessun passaggio recuperato)")
            lines.append("")

    if competitive:
        lines.append("-" * 70)
        lines.append("CONFRONTO COMPETITIVO  ·  share of voice sui "
                     "primi %d posti fusi" % competitive["top_n"])
        lines.append("-" * 70)
        share = competitive["share"]
        for host in competitive["sites"]:
            marker = "  <- tuo sito" if host == competitive["main"] \
                else ""
            lines.append("  %-38s %5.1f%%%s"
                         % (host, share[host], marker))
        lines.append("")
        for row in competitive["queries"]:
            best = ("miglior posizione %d" % row["best_rank_mine"]
                    if row["best_rank_mine"] else "ASSENTE")
            lines.append("  %-46s  tuoi %d/%d · %s"
                         % (row["query"][:46], row["mine_in_top"],
                            competitive["top_n"], best))
        lines.append("")
    return "\n".join(lines)


def score_verdict(value: float) -> Tuple[str, str, str]:
    """(etichetta, variabile colore, simbolo) per un punteggio 0-100.

    Soglie 40/70, le stesse delle barre di punteggio. Il simbolo
    accompagna sempre il colore (mai solo colore).
    """
    if value >= 70:
        return "Buono", "var(--good)", "&#10003;"
    if value >= 40:
        return "Da migliorare", "var(--warn)", "!"
    return "Critico", "var(--bad)", "&#10005;"


def page_status_counts(pages: List[Page],
                       findings: List[Finding]) -> Tuple[int, int, int]:
    """(senza rilievi, con rilievi, in errore) per il donut pagine.

    "Con rilievi" = pagine raggiungibili citate come riferimento da
    almeno un rilievo critico o avvertenza.
    """
    flagged_urls = {
        f.url for f in findings
        if f.url and f.severity in (SEV_CRITICAL, SEV_WARNING)
    }
    ok_pages = [p for p in pages if p.ok]
    flagged = len([p for p in ok_pages
                   if p.url in flagged_urls
                   or (p.final_url and p.final_url in flagged_urls)])
    return len(ok_pages) - flagged, flagged, len(pages) - len(ok_pages)


def _donut_svg(segments: List[Tuple[int, str]], total: int,
               label: str) -> str:
    """Donut SVG a segmenti (conteggio, colore) con foro centrale."""
    circ = 276.46  # 2 * pi * r, con r = 44
    parts = ["<svg viewBox=\"0 0 120 120\" width=\"116\" height=\"116\""
             " role=\"img\" aria-label=\"%s\">"
             "<g transform=\"rotate(-90 60 60)\">" % html.escape(label)]
    offset = 0.0
    for count, color in segments:
        if not count:
            continue
        span = circ * count / total
        # 2px di "aria" fra i segmenti, se il segmento li contiene.
        dash = max(span - 2.0, 1.0) if span > 3.0 else span
        parts.append(
            "<circle cx=\"60\" cy=\"60\" r=\"44\" fill=\"none\" "
            "stroke=\"%s\" stroke-width=\"14\" stroke-dasharray="
            "\"%.2f %.2f\" stroke-dashoffset=\"%.2f\"></circle>"
            % (color, dash, circ - dash, -offset))
        offset += span
    parts.append("</g></svg>")
    return "".join(parts)


def _render_hero(pages: List[Page], findings: List[Finding],
                 scores: Dict[str, Optional[float]]) -> str:
    """Testata visiva del referto: anello, verdetto, tile, donut."""
    esc = html.escape
    total = overall_score(scores)
    label, hue, mark = score_verdict(total)
    ring_c = 326.73  # 2 * pi * r, con r = 52

    sev_counts = Counter(f.severity for f in findings)
    clean, flagged, broken = page_status_counts(pages, findings)
    n_pages = len(pages)

    out: List[str] = ["<div class=\"hero\">"]
    out.append(
        "<div class=\"ringbox\" role=\"img\" aria-label=\"Punteggio "
        "complessivo %.0f su 100: %s\"><svg viewBox=\"0 0 120 120\" "
        "width=\"124\" height=\"124\" aria-hidden=\"true\">"
        "<circle class=\"rtrack\" cx=\"60\" cy=\"60\" r=\"52\"></circle>"
        "<circle class=\"rfill\" cx=\"60\" cy=\"60\" r=\"52\" "
        "style=\"stroke:%s;stroke-dasharray:%.2f %.2f\" "
        "transform=\"rotate(-90 60 60)\"></circle></svg>"
        "<div class=\"rnum\" aria-hidden=\"true\"><b>%.0f</b>"
        "<small>su 100</small></div></div>"
        % (total, esc(label), hue, ring_c * total / 100.0,
           ring_c, total))
    out.append(
        "<div class=\"heroside\"><p class=\"verdict\"><span class="
        "\"ico\" style=\"background:%s\">%s</span>%s</p>"
        "<p class=\"soglie\">buono &ge; 70 &middot; da migliorare "
        "40&ndash;69 &middot; critico &lt; 40</p><div class=\"tiles\">"
        % (hue, mark, esc(label)))
    for sev, label_it, color in (
            (SEV_CRITICAL, "Critici", "var(--bad)"),
            (SEV_WARNING, "Avvertenze", "var(--warn)"),
            (SEV_INFO, "Informazioni", "var(--muted)")):
        out.append(
            "<div class=\"tile\"><span class=\"lbl\"><span class="
            "\"dot\" style=\"background:%s\"></span>%s</span>"
            "<b>%d</b></div>"
            % (color, esc(label_it), sev_counts.get(sev, 0)))
    out.append("</div></div>")

    if n_pages:
        donut = _donut_svg(
            [(clean, "var(--good)"), (flagged, "var(--warn)"),
             (broken, "var(--bad)")], n_pages,
            "%d pagine: %d senza rilievi, %d con rilievi, %d in "
            "errore" % (n_pages, clean, flagged, broken))
        out.append(
            "<div class=\"donutbox\"><div class=\"donutwrap\">%s"
            "<div class=\"dnum\" aria-hidden=\"true\"><b>%d</b>"
            "<small>pagine</small></div></div>"
            "<ul class=\"dleg\" aria-hidden=\"true\">"
            "<li><span class=\"dot\" style=\"background:var(--good)\">"
            "</span>%d senza rilievi</li>"
            "<li><span class=\"dot\" style=\"background:var(--warn)\">"
            "</span>%d con rilievi</li>"
            "<li><span class=\"dot\" style=\"background:var(--bad)\">"
            "</span>%d in errore</li></ul></div>"
            % (donut, n_pages, clean, flagged, broken))
    out.append("</div>")
    return "".join(out)


def render_html(base: str, pages: List[Page],
                findings: List[Finding],
                scores: Dict[str, Optional[float]],
                results: List[QueryResult], mode: str,
                k: int = 60,
                competitive: Optional[Dict[str, object]] = None
                ) -> str:
    """Referto HTML autonomo, leggibile in chiaro e in scuro."""
    esc = html.escape
    colors = {SEV_CRITICAL: "var(--bad)", SEV_WARNING: "var(--warn)",
              SEV_OK: "var(--good)", SEV_INFO: "var(--muted)"}
    marks = {SEV_CRITICAL: "&#10005;", SEV_WARNING: "!",
             SEV_OK: "&#10003;", SEV_INFO: "i"}

    parts: List[str] = []
    parts.append(
        "<!DOCTYPE html><html lang=\"it\"><head>"
        "<meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,"
        "initial-scale=1\">"
        "<title>Audit SEO + RRF - %s</title><style>%s</style>"
        "</head><body><div class=\"wrap\">" % (esc(base), _CSS))

    parts.append("<h1>Audit SEO + RRF</h1>")
    parts.append("<p class=\"sub\">%s</p>" % esc(base))
    parts.append(
        "<p class=\"meta\">Pagine analizzate: %d &middot; chunk "
        "indicizzati: %d &middot; recuperatore vettoriale: <code>%s"
        "</code></p>" % (
            len([p for p in pages if p.ok]),
            sum(len(p.chunks) for p in pages if p.ok), esc(mode)))

    parts.append(_render_hero(pages, findings, scores))

    parts.append("<div class=\"scores\">")
    for area, score in scores.items():
        if score is None:
            continue
        hue = "var(--good)" if score >= 70 else (
            "var(--warn)" if score >= 40 else "var(--bad)")
        parts.append(
            "<div class=\"sc\"><h3>%s<span style=\"color:%s\">%.0f</span>"
            "</h3><div class=\"bar\"><div class=\"fill\" style=\"width:"
            "%.0f%%;background:%s\"></div></div></div>"
            % (esc(area), hue, score, score, hue))
    total = overall_score(scores)
    hue = "var(--good)" if total >= 70 else (
        "var(--warn)" if total >= 40 else "var(--bad)")
    parts.append(
        "<div class=\"sc tot\"><h3>Complessivo<span style=\"color:%s\">"
        "%.0f</span></h3><div class=\"bar\"><div class=\"fill\" "
        "style=\"width:%.0f%%;background:%s\"></div></div></div>"
        % (hue, total, total, hue))
    parts.append("</div>")

    order = {SEV_CRITICAL: 0, SEV_WARNING: 1, SEV_INFO: 2, SEV_OK: 3}
    for area in (AREA_TECH, AREA_LEX, AREA_SEM, AREA_SD, AREA_RRF):
        subset = sorted((f for f in findings if f.area == area),
                        key=lambda f: order[f.severity])
        if not subset:
            continue
        parts.append("<section><h2>%s</h2>" % esc(area))
        for finding in subset:
            parts.append(
                "<div class=\"find\"><span class=\"ico\" style=\""
                "background:%s\">%s</span><div class=\"txt\"><b>%s</b>"
                % (colors[finding.severity], marks[finding.severity],
                   esc(finding.title)))
            if finding.detail:
                parts.append("<span class=\"d\">%s</span>"
                             % esc(finding.detail))
            if finding.fix:
                parts.append("<span class=\"fix\">%s</span>"
                             % esc(finding.fix))
            parts.append("</div></div>")
        parts.append("</section>")

    if results:
        parts.append("<section><h2>Dettaglio simulazione RRF</h2>"
                     "<p class=\"meta\">Le tacche sul consenso sono "
                     "le soglie del giudizio: sotto il 20% e' "
                     "critico, sotto il 45% da migliorare.</p>"
                     "<table><thead><tr><th>Query</th><th>Consenso"
                     "</th><th>Passaggio in testa dopo la fusione</th>"
                     "<th>Punteggio</th></tr></thead><tbody>")
        for res in results:
            top = res.fused_top[0] if res.fused_top else ("-", 0.0)
            ratio = res.consensus / 5.0
            hue = "var(--good)" if ratio >= 0.45 else (
                "var(--warn)" if ratio >= 0.2 else "var(--bad)")
            parts.append(
                "<tr><td>%s</td><td class=\"cons\">"
                "<span class=\"mnum\">%d su 5</span>"
                "<div class=\"meter\" aria-hidden=\"true\">"
                "<div class=\"mfill\" style=\"width:%.0f%%;"
                "background:%s\"></div>"
                "<span class=\"tick\" style=\"left:20%%\"></span>"
                "<span class=\"tick\" style=\"left:45%%\"></span>"
                "</div></td><td>%s</td><td>%.5f</td></tr>"
                % (esc(res.query), res.consensus, ratio * 100,
                   hue, esc(str(top[0])), top[1]))
        parts.append("</tbody></table></section>")

    if competitive:
        share = competitive["share"]
        parity = 100.0 / max(1, len(competitive["sites"]))
        parts.append(
            "<section><h2>Confronto competitivo</h2>"
            "<p class=\"meta\">Share of voice sui primi %d posti "
            "delle liste fuse, sulle query dei temi del tuo sito. "
            "La tacca indica la parita' (%.0f%%): sopra la tacca si "
            "e' sopra la propria quota naturale.</p>"
            % (competitive["top_n"], parity))
        parts.append("<table><thead><tr><th>Sito</th>"
                     "<th>Share</th><th></th></tr></thead><tbody>")
        for host in competitive["sites"]:
            mine = host == competitive["main"]
            name = esc(host) + (" <strong>(tuo sito)</strong>"
                                if mine else "")
            hue = "var(--accent)" if mine else "var(--muted)"
            parts.append(
                "<tr><td>%s</td><td>%.1f%%</td>"
                "<td style=\"min-width:180px\">"
                "<div class=\"bar meter\">"
                "<div class=\"fill\" style=\"width:%.0f%%;"
                "background:%s\"></div>"
                "<span class=\"tick\" style=\"left:%.1f%%\"></span>"
                "</div></td></tr>"
                % (name, share[host], share[host], hue, parity))
        parts.append("</tbody></table>")
        parts.append("<table><thead><tr><th>Query</th>"
                     "<th>Tuoi passaggi</th><th>Migliore posizione"
                     "</th></tr></thead><tbody>")
        for row in competitive["queries"]:
            best = (str(row["best_rank_mine"])
                    if row["best_rank_mine"]
                    else "<strong>assente</strong>")
            parts.append(
                "<tr><td>%s</td><td>%d su %d</td><td>%s</td></tr>"
                % (esc(row["query"]), row["mine_in_top"],
                   competitive["top_n"], best))
        parts.append("</tbody></table></section>")

    parts.append(
        "<footer><p class=\"brand\">Lympha Technologies S.r.l.</p>"
        "<p>Generato da <code>seo_rrf_audit.py</code> v%s. "
        "La formula applicata e' <code>score(d) = &Sigma; 1/(k + "
        "rank_i(d))</code> con k=%d, pesi uguali per ogni lista.</p>"
        "<p>Riferimenti: Cormack et al. (SIGIR 2009); "
        "<a href=\"https://learn.microsoft.com/en-us/azure/search/"
        "hybrid-search-ranking\">Microsoft Learn</a>; "
        "<a href=\"https://www.elastic.co/docs/reference/elasticsearch/"
        "rest-apis/reciprocal-rank-fusion\">Elastic</a>; "
        "<a href=\"https://schema.org/\">Schema.org</a>.</p>"
        "</footer></div></body></html>" % (__version__, k))
    return "".join(parts)


_CSS = """
:root{--bg:#f7f8fa;--card:#fff;--ink:#14272b;--muted:#3c5054;
--line:#e3e7ee;--accent:#186078;--accent-soft:#eef6f7;--good:#0b8f6a;
--warn:#c2410c;--bad:#c62828}
@media(prefers-color-scheme:dark){:root{--bg:#0c1518;--card:#14262b;
--ink:#e8f1f2;--muted:#9ab4b9;--line:#24383d;--accent:#5bb6bf;
--accent-soft:#14333c;--good:#34d399;--warn:#fb923c;--bad:#f87171}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);line-height:1.55;
font-family:"Titillium Web",-apple-system,BlinkMacSystemFont,
"Segoe UI",Roboto,Arial,sans-serif;padding:32px 16px}
.wrap{max-width:880px;margin:0 auto}
h1{font-size:1.5rem;margin:0 0 4px}
.sub{color:var(--accent);font-size:.95rem;margin:0 0 4px}
.meta{color:var(--muted);font-size:.8rem;margin:0 0 22px}
.hero{display:flex;gap:26px;flex-wrap:wrap;align-items:center;
background:var(--card);border:1px solid var(--line);
border-radius:14px;padding:18px 22px;margin-bottom:16px}
.ringbox,.donutwrap{position:relative;flex:0 0 auto}
.rtrack{fill:none;stroke:var(--line);stroke-width:10}
.rfill{fill:none;stroke-width:10;stroke-linecap:round}
.rnum,.dnum{position:absolute;inset:0;display:flex;
flex-direction:column;align-items:center;justify-content:center;
line-height:1.05}
.rnum b{font-size:2rem}
.rnum small,.dnum small{font-size:.68rem;color:var(--muted)}
.dnum b{font-size:1.3rem}
.heroside{flex:1 1 200px;min-width:180px}
.verdict{display:flex;align-items:center;gap:8px;font-weight:700;
font-size:1.05rem;margin:0 0 2px}
.soglie{color:var(--muted);font-size:.75rem;margin:0 0 12px}
.tiles{display:flex;gap:10px;flex-wrap:wrap}
.tile{border:1px solid var(--line);border-radius:10px;
padding:7px 12px;min-width:96px}
.tile .lbl{display:flex;align-items:center;gap:6px;font-size:.72rem;
color:var(--muted)}
.tile b{display:block;font-size:1.35rem;margin-top:1px}
.dot{width:9px;height:9px;border-radius:50%;flex:0 0 auto;
display:inline-block}
.donutbox{display:flex;align-items:center;gap:14px}
.dleg{list-style:none;margin:0;padding:0;font-size:.78rem;
color:var(--muted)}
.dleg li{display:flex;align-items:center;gap:6px;margin:3px 0}
.meter{position:relative}
.meter .tick{position:absolute;top:-3px;bottom:-3px;width:2px;
background:var(--muted);opacity:.7}
.bar.meter{overflow:visible}
.bar.meter .fill{border-radius:999px}
td.cons{min-width:130px}
td.cons .mnum{display:block;font-variant-numeric:tabular-nums;
margin-bottom:4px}
td.cons .meter{height:7px;border-radius:999px;background:var(--line)}
td.cons .mfill{height:100%;border-radius:999px}
.scores{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:24px}
.sc{flex:1;min-width:150px;background:var(--card);
border:1px solid var(--line);border-radius:12px;padding:12px 14px}
.sc.tot{border-color:var(--accent)}
.sc h3{margin:0 0 8px;font-size:.78rem;font-weight:600;
color:var(--muted);display:flex;justify-content:space-between;
align-items:baseline;gap:6px}
.sc h3 span{font-size:1.35rem;font-weight:700}
.bar{height:7px;border-radius:999px;background:var(--line);
overflow:hidden}
.fill{height:100%}
section{background:var(--card);border:1px solid var(--line);
border-radius:14px;padding:16px 20px;margin-bottom:16px}
section h2{font-size:1rem;margin:0 0 12px}
.find{display:flex;gap:11px;padding:10px 0;
border-top:1px solid var(--line)}
.find:first-of-type{border-top:none}
.ico{flex:0 0 auto;width:19px;height:19px;border-radius:50%;
display:flex;align-items:center;justify-content:center;
font-size:.68rem;font-weight:800;color:#fff;margin-top:3px}
.txt{font-size:.9rem}
.d,.fix{display:block;margin-top:3px;font-size:.82rem;
color:var(--muted)}
.fix::before{content:"Fix: ";color:var(--accent);font-weight:600}
table{width:100%;border-collapse:collapse;font-size:.84rem}
th,td{text-align:left;padding:8px 10px;border-bottom:1px solid
var(--line);vertical-align:top}
th{font-size:.7rem;text-transform:uppercase;color:var(--muted)}
code{font-family:Menlo,Consolas,monospace;font-size:.85em;
background:var(--accent-soft);padding:1px 5px;border-radius:5px}
footer{color:var(--muted);font-size:.78rem;padding:0 4px}
footer a{color:var(--accent)}
footer .brand{color:var(--accent);font-weight:700;font-size:.88rem;
letter-spacing:.04em}
"""


def render_json(base: str, pages: List[Page],
                findings: List[Finding],
                scores: Dict[str, Optional[float]],
                results: List[QueryResult], mode: str,
                k: int = 60,
                competitive: Optional[Dict[str, object]] = None
                ) -> str:
    """Referto JSON, adatto a essere versionato o messo in pipeline."""
    payload = {
        "tool": "seo_rrf_audit.py",
        "version": __version__,
        "site": base,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "vector_retriever": mode,
        "rrf": {"k": k, "formula": "score(d)=sum 1/(k+rank_i(d))"},
        "scores": {**scores, "overall": overall_score(scores)},
        "pages": [
            {
                "url": p.url,
                "status": p.status,
                "final_url": p.final_url,
                "redirects": p.redirects,
                "title": p.title,
                "description": p.description,
                "word_count": p.word_count,
                "headings": len(p.headings),
                "chunks": len(p.chunks),
                "jsonld_types": p.jsonld_types,
            }
            for p in pages
        ],
        "findings": [f.as_dict() for f in findings],
        "rrf_simulation": [asdict(r) for r in results],
        "competitive": competitive,
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


# --------------------------------------------------------------------
# Orchestrazione
# --------------------------------------------------------------------

def dedupe_pages(pages: List[Page]) -> Tuple[List[Page], List[str]]:
    """Rimuove le pagine con testo identico servite da URL diversi.

    Tipico di `/` e `/index.html`, o di URL con parametri: sono lo
    stesso documento. Tenerli entrambi gonfierebbe artificialmente il
    numero di chunk e produrrebbe falsi allarmi sui title duplicati.
    Viene conservato l'URL piu' corto, che e' quasi sempre il canonico.
    """
    best: Dict[str, Page] = {}
    duplicates: List[str] = []
    order: List[str] = []

    for page in pages:
        if not page.ok or not page.text:
            order.append(page.url)
            best[page.url] = page
            continue
        digest = hashlib.sha1(page.text.encode("utf-8")).hexdigest()
        previous = best.get(digest)
        if previous is None:
            best[digest] = page
            order.append(digest)
            continue
        loser, winner = sorted(
            (page, previous), key=lambda p: (len(p.url), p.url),
            reverse=True)
        best[digest] = winner
        duplicates.append(loser.url)

    return [best[key] for key in order], duplicates


def run_audit(base: str, max_pages: int, queries: List[str],
              model_name: str, delay: float, k: int,
              verbose: bool,
              max_body_mb: float = DEFAULT_MAX_BODY_MB,
              respect_robots: bool = False,
              retries: int = DEFAULT_RETRIES,
              competitors: Optional[List[str]] = None,
              user_agent: str = USER_AGENT) -> Tuple[
                  List[Page], List[Finding],
                  Dict[str, Optional[float]], List[QueryResult], str,
                  Optional[Dict[str, object]]]:
    """Esegue l'intero audit e restituisce i risultati grezzi."""
    fetcher = Fetcher(delay=delay, verbose=verbose,
                      max_bytes=int(max_body_mb * 1048576),
                      retries=retries, user_agent=user_agent)

    if verbose:
        print("[1/5] robots.txt", file=sys.stderr)
    robots = RobotsAudit(base, fetcher)
    findings: List[Finding] = robots.run()

    if verbose:
        print("[2/5] scoperta URL", file=sys.stderr)
    urls, from_sitemap = discover_urls(base, robots, fetcher,
                                       max_pages, respect_robots)
    if norm_url(base) not in {norm_url(u) for u in urls}:
        urls.insert(0, base)
    if respect_robots:
        excluded = [u for u in urls if not robots.allowed(u)]
        urls = [u for u in urls if robots.allowed(u)]
        if excluded:
            findings.append(Finding(
                AREA_TECH, SEV_INFO,
                "%d URL esclusi per rispetto del robots.txt"
                % len(excluded),
                "Con --respect-robots gli URL vietati all'agente %s "
                "non vengono scaricati: %s."
                % (USER_AGENT_TOKEN,
                   ", ".join(sorted(excluded)[:5]))))
    urls = urls[:max_pages]

    if verbose:
        print("[3/5] scansione di %d pagine" % len(urls), file=sys.stderr)
    pages: List[Page] = []
    for url in urls:
        resp = fetcher.get(url)
        if resp is None:
            pages.append(Page(
                url=url,
                error=fetcher.last_error or "richiesta fallita"))
            continue
        ctype = resp.headers.get("Content-Type", "")
        if "html" not in ctype:
            pages.append(Page(url=url, status=resp.status_code,
                              error="non HTML (%s)" % ctype))
            continue
        pages.append(parse_page(url, resp))

    pages, duplicates = dedupe_pages(pages)
    if duplicates:
        findings.append(Finding(
            AREA_TECH, SEV_WARNING,
            "%d URL servono contenuto identico" % len(duplicates),
            "Stesso testo raggiungibile da piu' indirizzi: %s. "
            "I duplicati non aggiungono addendi alla somma RRF, "
            "diluiscono i segnali e sprecano budget di scansione."
            % ", ".join(sorted(duplicates)[:4]),
            "Scegli un URL canonico e reindirizza gli altri con un 301.",
            weight=1.0))

    if verbose:
        print("[4/5] controlli per area", file=sys.stderr)
    findings += audit_technical(pages, base, from_sitemap)
    findings += audit_lexical(pages)
    findings += audit_semantic(pages)
    findings += audit_structured_data(pages)

    if verbose:
        print("[5/5] simulazione RRF", file=sys.stderr)
    if not queries:
        queries = auto_queries([p for p in pages if p.ok])
    results, rrf_findings, mode = simulate_rrf(
        pages, queries, k=k, model_name=model_name)
    findings += rrf_findings

    competitive: Optional[Dict[str, object]] = None
    if competitors:
        if verbose:
            print("[extra] confronto competitivo", file=sys.stderr)
        corpora: Dict[str, List[Chunk]] = {}
        for comp in competitors:
            host = urlparse(comp).netloc
            if verbose:
                print("  scansione concorrente %s" % host,
                      file=sys.stderr)
            cpages = crawl_corpus(comp, fetcher, max_pages,
                                  respect_robots)
            corpora[host] = [c for p in cpages if p.ok
                             for c in p.chunks]
        own_chunks = [c for p in pages if p.ok for c in p.chunks]
        competitive, comp_findings = simulate_share_of_voice(
            base, own_chunks, corpora, queries, k=k,
            model_name=model_name)
        findings += comp_findings

    scores = {
        area: area_score(findings, area)
        for area in (AREA_TECH, AREA_LEX, AREA_SEM, AREA_SD, AREA_RRF)
    }
    return pages, findings, scores, results, mode, competitive


def build_parser() -> argparse.ArgumentParser:
    """Costruisce il parser degli argomenti da riga di comando."""
    parser = argparse.ArgumentParser(
        prog="seo_rrf_audit.py",
        description="Audit SEO e Reciprocal Rank Fusion di un sito.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Esempio:\n"
               "  python3 seo_rrf_audit.py https://example.com "
               "--format html --output report.html")
    parser.add_argument("url", help="URL di partenza del sito")
    parser.add_argument("--max-pages", type=int, default=25,
                        help="numero massimo di pagine (default 25)")
    parser.add_argument("--queries", metavar="FILE",
                        help="file con una query per riga; se omesso "
                             "le query sono generate dai temi del sito")
    parser.add_argument("--embeddings", metavar="MODELLO", default="",
                        help="modello sentence-transformers per il "
                             "recupero vettoriale reale")
    parser.add_argument("--rrf-k", type=int, default=60,
                        help="costante k della formula RRF "
                             "(default 60)")
    parser.add_argument("--delay", type=float, default=0.5,
                        help="pausa fra le richieste in secondi")
    parser.add_argument("--max-body", type=float,
                        default=DEFAULT_MAX_BODY_MB, metavar="MB",
                        help="dimensione massima del corpo di ogni "
                             "risposta, in MB (default %d). Il corpo "
                             "resta in RAM durante l'analisi: "
                             "dimensiona il valore sulla memoria "
                             "della tua macchina, di norma non oltre "
                             "un decimo della RAM disponibile"
                             % DEFAULT_MAX_BODY_MB)
    parser.add_argument("--format", choices=("text", "json", "html"),
                        default="text", help="formato del referto")
    parser.add_argument("--output", metavar="FILE",
                        help="scrive il referto su file")
    parser.add_argument("--competitor", metavar="URL",
                        action="append", dest="competitors",
                        default=[],
                        help="URL di un sito concorrente (ripetibile, "
                             "massimo 3): viene scansionato con gli "
                             "stessi limiti e confrontato sulle "
                             "stesse query per misurare la share of "
                             "voice nelle liste fuse")
    parser.add_argument("--retries", type=int,
                        default=DEFAULT_RETRIES, metavar="N",
                        help="tentativi aggiuntivi con backoff "
                             "esponenziale (0.5s, 1s, 2s...) su "
                             "errori di rete e HTTP 429/500/502/503/"
                             "504; rispetta Retry-After (default %d, "
                             "0 disattiva)" % DEFAULT_RETRIES)
    parser.add_argument("--user-agent", default=USER_AGENT,
                        metavar="UA", dest="user_agent",
                        help="header User-Agent inviato con ogni "
                             "richiesta; il predefinito identifica lo "
                             "strumento e rimanda alla pagina del "
                             "progetto (%s)" % USER_AGENT)
    parser.add_argument("--respect-robots", action="store_true",
                        help="rispetta i Disallow del robots.txt per "
                             "l'agente %s: gli URL vietati non "
                             "vengono scaricati (predefinito: scarica "
                             "comunque, trattandosi di un audit del "
                             "proprio sito)" % USER_AGENT_TOKEN)
    parser.add_argument("--quiet", action="store_true",
                        help="non stampa l'avanzamento")
    parser.add_argument("--version", action="version",
                        version="%(prog)s " + __version__)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Punto di ingresso da riga di comando."""
    args = build_parser().parse_args(argv)

    base = args.url
    if not base.startswith(("http://", "https://")):
        base = "https://" + base

    if len(args.competitors) > 3:
        print("Massimo 3 concorrenti con --competitor.",
              file=sys.stderr)
        return 2
    competitors = [
        c if c.startswith(("http://", "https://")) else "https://" + c
        for c in args.competitors
    ]

    if args.max_body <= 0:
        print("--max-body deve essere maggiore di zero.",
              file=sys.stderr)
        return 2
    ram = available_ram_mb()
    if ram is not None and args.max_body > ram * 0.1:
        print("Avviso: --max-body %.0f MB e' alto per questa "
              "macchina (RAM disponibile ora: %.0f MB). "
              "Suggerito un valore <= %.0f MB."
              % (args.max_body, ram, max(1.0, ram * 0.1)),
              file=sys.stderr)

    queries: List[str] = []
    if args.queries:
        try:
            with open(args.queries, encoding="utf-8") as handle:
                queries = [ln.strip() for ln in handle if ln.strip()]
        except OSError as exc:
            print("Impossibile leggere %s: %s" % (args.queries, exc),
                  file=sys.stderr)
            return 2

    try:
        pages, findings, scores, results, mode, competitive = \
            run_audit(
                base=base, max_pages=args.max_pages, queries=queries,
                model_name=args.embeddings, delay=args.delay,
                k=args.rrf_k, verbose=not args.quiet,
                max_body_mb=args.max_body,
                respect_robots=args.respect_robots,
                retries=max(0, args.retries),
                competitors=competitors,
                user_agent=args.user_agent)
    except KeyboardInterrupt:
        print("\nInterrotto dall'utente.", file=sys.stderr)
        return 130

    renderers = {"text": render_text, "json": render_json,
                 "html": render_html}
    report = renderers[args.format](
        base, pages, findings, scores, results, mode, args.rrf_k,
        competitive)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(report)
        print("Referto scritto in %s" % args.output, file=sys.stderr)
    else:
        print(report)

    critical = sum(1 for f in findings if f.severity == SEV_CRITICAL)
    return 1 if critical else 0


if __name__ == "__main__":
    sys.exit(main())
