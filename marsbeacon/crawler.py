# -*- coding: utf-8 -*-
"""Acquisizione: fetch, robots, scoperta URL, parsing, rendering JS,
chunking e deduplica delle pagine.

Generato dalla scomposizione di mars_audit.py (v1.58.0): il
namespace pubblico resta mars_audit, questo modulo e' interno.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import as_completed
from typing import Dict
from typing import List
from typing import Optional
from typing import Sequence
from typing import Set
from typing import Tuple
from urllib.parse import urljoin
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser
import gzip
import hashlib
import io
import json
import os
import re
import sys
import threading
import time
import xml.etree.ElementTree as ET

from marsbeacon.base import (
    AI_CRAWLERS,
    ANALYZABLE_CTYPES,
    AREA_TECH,
    AuditCancelled,
    BeautifulSoup,
    CHROME_PATHS,
    Chunk,
    DEFAULT_CHUNK_WORDS,
    DEFAULT_MAX_BODY_MB,
    DEFAULT_RETRIES,
    Finding,
    GENERIC_ANCHOR_RE,
    Page,
    RENDER_ALWAYS,
    RENDER_OFF,
    RENDER_SETTLE_MS,
    RETRY_BACKOFF_S,
    RETRY_MAX_WAIT_S,
    RETRY_STATUS,
    SEMANTIC_TAGS,
    SEV_CRITICAL,
    SEV_OK,
    SEV_WARNING,
    USER_AGENT,
    USER_AGENT_TOKEN,
    norm_url,
    requests,
    tokenize)


class Fetcher:
    """Client HTTP con user agent esplicito e pausa fra richieste."""

    def __init__(self, delay: float = 0.5, timeout: int = 20,
                 verbose: bool = True,
                 max_bytes: int = DEFAULT_MAX_BODY_MB * 1048576,
                 retries: int = DEFAULT_RETRIES,
                 backoff: float = RETRY_BACKOFF_S,
                 user_agent: str = USER_AGENT,
                 stop_event: Optional[threading.Event] = None) -> None:
        self._headers = {
            "User-Agent": user_agent or USER_AGENT,
            "Accept-Language": "it,en;q=0.8",
        }
        self.delay = delay
        self.timeout = timeout
        self.verbose = verbose
        self.max_bytes = max(1, int(max_bytes))
        self.retries = max(0, int(retries))
        self.backoff = max(0.0, backoff)
        self.stop_event = stop_event
        # Stato per il fetch concorrente: sessione HTTP ed esito
        # dell'ultima richiesta sono per-thread; il throttle assegna
        # gli slot di partenza in modo atomico.
        self._local = threading.local()
        self._lock = threading.Lock()
        self._next_slot = 0.0

    @property
    def last_error(self) -> str:
        """Esito dell'ultima richiesta DEL THREAD chiamante."""
        return getattr(self._local, "last_error", "")

    @last_error.setter
    def last_error(self, value: str) -> None:
        self._local.last_error = value

    def _session(self) -> requests.Session:
        """Una sessione HTTP per thread (requests non e' thread-safe)."""
        sess = getattr(self._local, "session", None)
        if sess is None:
            sess = requests.Session()
            sess.headers.update(self._headers)
            self._local.session = sess
        return sess

    def _check_stop(self) -> None:
        if self.stop_event is not None and self.stop_event.is_set():
            raise AuditCancelled()

    def _wait(self, seconds: float) -> None:
        """Attesa interrompibile dal flag di stop."""
        if self.stop_event is not None:
            self.stop_event.wait(seconds)
            self._check_stop()
        else:
            time.sleep(seconds)

    def _throttle(self) -> None:
        """Riserva atomicamente il prossimo slot di partenza."""
        with self._lock:
            now = time.time()
            start = max(now, self._next_slot)
            self._next_slot = start + self.delay
        wait = start - now
        if wait > 0:
            self._wait(wait)

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
            self._check_stop()
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
            self._wait(wait)
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
            resp = self._session().get(
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
                if self.stop_event is not None \
                        and self.stop_event.is_set():
                    resp.close()
                    raise AuditCancelled()
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
                url=url, key="tech.robots.missing",
                params={"url": url},
                example="# /robots.txt\nUser-agent: *\nDisallow:\n\n"
                        "Sitemap: https://esempio.it/sitemap.xml"))
            return findings

        self.found = True
        self.raw = resp.text
        self.parser.parse(self.raw.splitlines())
        self.sitemaps = re.findall(
            r"(?im)^\s*sitemap:\s*(\S+)", self.raw)

        findings.append(Finding(
            AREA_TECH, SEV_OK, "robots.txt presente",
            "%d righe." % len(self.raw.splitlines()), url=url,
            key="tech.robots.present",
            params={"n": len(self.raw.splitlines())}))

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
                url=url, weight=2.0, key="tech.robots.ai_blocked",
                params={"agents": ", ".join(blocked)},
                example="# robots.txt - sblocca gli agenti IA\n"
                        "User-agent: GPTBot\nDisallow:\n\n"
                        "User-agent: ClaudeBot\nDisallow:\n\n"
                        "User-agent: PerplexityBot\nDisallow:"))
        else:
            findings.append(Finding(
                AREA_TECH, SEV_OK, "Crawler IA ammessi",
                "Verificati: %s." % ", ".join(AI_CRAWLERS), url=url,
                key="tech.robots.ai_allowed",
                params={"agents": ", ".join(AI_CRAWLERS)}))

        if self.sitemaps:
            findings.append(Finding(
                AREA_TECH, SEV_OK, "Sitemap dichiarata nel robots.txt",
                ", ".join(self.sitemaps), url=url,
                key="tech.robots.sitemap_ok",
                params={"urls": ", ".join(self.sitemaps)}))
        else:
            findings.append(Finding(
                AREA_TECH, SEV_WARNING,
                "Nessuna sitemap dichiarata nel robots.txt",
                fix="Aggiungi la riga 'Sitemap: https://.../sitemap.xml'.",
                url=url, key="tech.robots.sitemap_missing",
                example="# in fondo al robots.txt\n"
                        "Sitemap: https://esempio.it/sitemap.xml"))
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


def fetch_pages(fetcher: Fetcher, urls: Sequence[str],
                workers: int = 1,
                stop_event: Optional["threading.Event"] = None
                ) -> List[Page]:
    """Scarica e classifica gli URL, nell'ordine dato.

    Con ``workers`` > 1 le richieste avvengono in parallelo, ma il
    rate limit non cambia: il throttle del Fetcher distanzia gli avvii
    di ``delay`` anche fra thread — la concorrenza sovrappone solo le
    attese di rete. L'annullamento (``stop_event``) interrompe anche i
    worker in attesa.
    """
    def one(url: str) -> Page:
        resp = fetcher.get(url)
        if resp is None:
            return Page(url=url,
                        error=fetcher.last_error or "richiesta fallita")
        ctype = resp.headers.get("Content-Type", "")
        if "html" not in ctype:
            return Page(url=url, status=resp.status_code,
                        error="non HTML (%s)" % ctype)
        return parse_page(url, resp)

    if workers <= 1 or len(urls) <= 1:
        pages: List[Page] = []
        for url in urls:
            if stop_event is not None and stop_event.is_set():
                raise AuditCancelled()
            pages.append(one(url))
        return pages

    results: List[Optional[Page]] = [None] * len(urls)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(one, url): i
                   for i, url in enumerate(urls)}
        try:
            for future in as_completed(futures):
                results[futures[future]] = future.result()
        except AuditCancelled:
            for future in futures:
                future.cancel()
            raise
    return [page for page in results if page is not None]


def is_js_heavy(page: Page) -> bool:
    """Contenuto probabilmente reso lato client (poco testo, molto
    JavaScript nell'HTML iniziale)."""
    return (page.html_bytes > 0
            and page.word_count < 120
            and page.script_bytes > page.html_bytes * 0.4)


class PageRenderer:
    """Rende le pagine in un browser headless tramite Playwright.

    Usa il Chromium gestito da Playwright se installato
    (``playwright install chromium``); altrimenti ripiega sul
    Chrome/Chromium di sistema. L'API sync di Playwright non e'
    thread-safe: il rendering avviene sempre in una passata seriale,
    dopo il fetch (eventualmente parallelo).
    """

    def __init__(self, user_agent: str = USER_AGENT,
                 timeout: int = 20, verbose: bool = True) -> None:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise RuntimeError(
                "il rendering JavaScript richiede Playwright: "
                "pip install playwright (poi 'playwright install "
                "chromium', oppure un Chrome/Chromium di sistema)")
        self.verbose = verbose
        self.timeout_ms = int(timeout * 1000)
        self._pw = sync_playwright().start()
        browser = None
        try:
            browser = self._pw.chromium.launch()
        except Exception:
            for path in CHROME_PATHS:
                if not os.path.exists(path):
                    continue
                try:
                    browser = self._pw.chromium.launch(
                        executable_path=path, args=["--no-sandbox"])
                    break
                except Exception:
                    continue
        if browser is None:
            self._pw.stop()
            raise RuntimeError(
                "nessun browser disponibile per il rendering: esegui "
                "'playwright install chromium' o installa "
                "Chrome/Chromium di sistema")
        self._browser = browser
        self._context = browser.new_context(user_agent=user_agent)

    def render(self, url: str) -> Optional[str]:
        """DOM renderizzato della pagina, o None se non riuscito."""
        try:
            page = self._context.new_page()
            try:
                page.goto(url, timeout=self.timeout_ms,
                          wait_until="load")
                try:
                    page.wait_for_load_state(
                        "networkidle", timeout=RENDER_SETTLE_MS)
                except Exception:
                    pass  # rete mai quieta (polling): il DOM c'e'
                return page.content()
            finally:
                page.close()
        except Exception as exc:
            if self.verbose:
                print("  ! rendering fallito per %s: %s"
                      % (url, str(exc).splitlines()[0][:120]),
                      file=sys.stderr)
            return None

    def close(self) -> None:
        for closer in (self._context.close, self._browser.close,
                       self._pw.stop):
            try:
                closer()
            except Exception:
                pass


def apply_rendering(pages: List[Page], mode: str,
                    user_agent: str = USER_AGENT,
                    delay: float = 0.5, timeout: int = 20,
                    verbose: bool = True,
                    stop_event: Optional["threading.Event"] = None
                    ) -> Tuple[List[Page], int, int]:
    """Sostituisce il contenuto delle pagine col DOM renderizzato.

    I metadati HTTP (stato, redirect, tempi, dimensioni) restano
    quelli della risposta reale; ``raw_js_heavy`` conserva l'esito
    dell'euristica sul sorgente statico, cosi' il rilievo sui
    contenuti invisibili ai crawler senza JavaScript scatta comunque.
    Restituisce (pagine, renderizzate, fallite).
    """
    targets = [i for i, p in enumerate(pages)
               if p.ok and (mode == RENDER_ALWAYS or is_js_heavy(p))]
    if mode == RENDER_OFF or not targets:
        return pages, 0, 0

    renderer = PageRenderer(user_agent=user_agent, timeout=timeout,
                            verbose=verbose)
    rendered = failed = 0
    try:
        for pos, index in enumerate(targets):
            if stop_event is not None and stop_event.is_set():
                raise AuditCancelled()
            old = pages[index]
            if verbose:
                print("  RENDER %s" % old.url, file=sys.stderr)
            html = renderer.render(old.url)
            if html is None:
                failed += 1
            else:
                fresh = Page(url=old.url, status=old.status,
                             final_url=old.final_url,
                             redirects=old.redirects,
                             elapsed=old.elapsed,
                             html_bytes=old.html_bytes)
                extract_content(fresh, html)
                fresh.rendered = True
                fresh.raw_js_heavy = is_js_heavy(old)
                pages[index] = fresh
                rendered += 1
            if delay and pos + 1 < len(targets):
                if stop_event is not None:
                    stop_event.wait(delay)
                else:
                    time.sleep(delay)
    finally:
        renderer.close()
    return pages, rendered, failed


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
    extract_content(page, resp.text)
    return page


def extract_content(page: Page, raw_html: str) -> None:
    """Popola i campi di contenuto della pagina dal sorgente HTML.

    Separata da ``parse_page`` perche' usata anche dal rendering
    JavaScript: i metadati HTTP restano quelli della risposta reale,
    il contenuto puo' venire dal DOM renderizzato dal browser.
    """
    url = page.url
    soup = BeautifulSoup(raw_html, "lxml")

    page.script_bytes = sum(
        len(s.get_text() or "") for s in soup.find_all("script"))

    page.semantic_tag_types = sum(
        1 for tag in SEMANTIC_TAGS if soup.find(tag) is not None)
    page.div_count = len(soup.find_all("div"))
    page.element_count = len(soup.find_all(True))

    html_tag = soup.find("html")
    if html_tag:
        page.lang = (html_tag.get("lang") or "").strip()

    if soup.title and soup.title.string:
        page.title = soup.title.string.strip()
    page.description = _meta(soup, name="description")
    page.meta_robots = _meta(soup, name="robots")
    page.bingbot_meta = _meta(soup, name="bingbot")
    page.generator = _meta(soup, name="generator")
    page.author = _meta(soup, name="author")
    page.published = _meta(soup, prop="article:published_time")
    page.modified = _meta(soup, prop="article:modified_time")

    for prop in ("og:title", "og:description", "og:type", "og:locale",
                 "og:image", "og:site_name"):
        value = _meta(soup, prop=prop)
        if value:
            page.og[prop] = value

    page.has_charset = bool(
        soup.find("meta", charset=True)
        or soup.find("meta", attrs={
            "http-equiv": re.compile("content-type", re.IGNORECASE)}))
    page.has_viewport = bool(_meta(soup, name="viewport"))

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
        href = anchor["href"].strip()
        if href.lower().startswith(("tel:", "mailto:")):
            page.contact_links += 1
            continue
        absolute = urljoin(url, href)
        target = urlparse(absolute).netloc
        if target == host:
            page.internal_links += 1
            target_norm = norm_url(absolute)
            page.internal_targets.append(target_norm)
            text = " ".join(anchor.get_text(" ").split())
            if GENERIC_ANCHOR_RE.match(text):
                page.generic_anchors += 1
            if len(text) >= 3:
                page.internal_anchors.append(
                    (text.lower(), target_norm))
        elif target:
            page.external_links += 1

    page.jsonld_types, page.jsonld_raw = extract_jsonld(raw_html)
    page.chunks = build_chunks(page)


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


def build_chunks(page: Page,
                 target_words: int = DEFAULT_CHUNK_WORDS
                 ) -> List[Chunk]:
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
