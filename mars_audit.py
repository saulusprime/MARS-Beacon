#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MARS Beacon — Meta-fusion, Accessibility, Ranking & Security Audit.

Audit SEO e RRF (Reciprocal Rank Fusion) di un sito web.

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

Dai punteggi di area deriva i **profili di citabilita'** per
assistente IA (Claude, ChatGPT/Perplexity, Qwen, Kimi) con indice
composito pesato per mercato (--market): stime euristiche
dichiarate, non comportamento documentato dai vendor.

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

Se sentence-transformers e' installato gli embedding reali si
attivano da soli con un modello multilingue predefinito; --embeddings
sceglie un modello diverso, --embeddings none forza il proxy
char-tfidf.

Uso:
    python3 mars_audit.py https://www.example.com
    python3 mars_audit.py https://example.com --max-pages 40 \\
        --format html --output report.html
    python3 mars_audit.py https://example.com --queries q.txt \\
        --embeddings sentence-transformers/all-MiniLM-L6-v2

Licenza: Apache 2.0.
"""

# Facciata di compatibilita' (v1.58.0): il codice vive nel
# package marsbeacon/ (base, crawler, indexes, audits,
# render); questo modulo riesporta ogni nome — GUI, test e
# integrazioni continuano a usare `import mars_audit` — e
# conserva la CLI: `python3 mars_audit.py URL` come sempre.

from __future__ import annotations

from dataclasses import asdict  # noqa: F401
from typing import Dict  # noqa: F401
from typing import List  # noqa: F401
from typing import Optional  # noqa: F401
from typing import Sequence  # noqa: F401
from typing import Tuple  # noqa: F401
from urllib.parse import urlparse  # noqa: F401
import argparse  # noqa: F401
import json  # noqa: F401
import re  # noqa: F401
import shutil  # noqa: F401
import subprocess  # noqa: F401
import sys  # noqa: F401
import threading  # noqa: F401
import time  # noqa: F401

from marsbeacon.base import (  # noqa: F401
    ABOUT_SLUGS,
    AI_CRAWLERS,
    ALL_AREAS,
    ANALYZABLE_CTYPES)
from marsbeacon.base import (  # noqa: F401
    ANAPHORA_RE,
    ANCHOR_MIN_PAIRS,
    ANCHOR_VARIETY_GOOD,
    AREA_LEX)
from marsbeacon.base import (  # noqa: F401
    AREA_LIGHTHOUSE,
    AREA_PILLARS,
    AREA_RRF,
    AREA_SD)
from marsbeacon.base import (  # noqa: F401
    AREA_SEM,
    AREA_TECH,
    AuditCancelled,
    CHROME_PATHS)
from marsbeacon.base import (  # noqa: F401
    CHUNK_WORDS_MAX,
    CHUNK_WORDS_MIN,
    CITABILITY_DEPTH,
    CITABILITY_NOTE)
from marsbeacon.base import (  # noqa: F401
    CITABILITY_PROFILES,
    CITATIONS_GOOD,
    CITATION_RE,
    CLICKBAIT_RE)
from marsbeacon.base import (  # noqa: F401
    CONFIG_ORDERED_PAIRS,
    CONFIG_TABLE,
    CONFIG_THRESHOLDS,
    _CONFIG_MODULES,
    apply_thresholds,
    check_thresholds,
    load_thresholds)
from marsbeacon.base import (  # noqa: F401
    CONTACT_SLUGS,
    CROSS_GAIN_MIN,
    Chunk,
    DEFAULT_CHUNK_WORDS)
from marsbeacon.base import (  # noqa: F401
    DEFAULT_EMBEDDINGS_MODEL,
    DEFAULT_JUDGE,
    DEFAULT_LIGHTHOUSE_PAGES,
    DEFAULT_MARKET)
from marsbeacon.base import (  # noqa: F401
    DEFAULT_MAX_BODY_MB,
    DEFAULT_RETRIES,
    DEFAULT_TOP_N,
    DEFAULT_WORKERS)
from marsbeacon.base import (  # noqa: F401
    DEFINITION_RE,
    DEPTH_TARGET_WORDS,
    DESC_MAX,
    DESC_MIN)
from marsbeacon.base import (  # noqa: F401
    DIRECT_ANSWER_RE,
    DIVITIS_RATIO,
    EFFORT_DAYS,
    EFFORT_HOURS)
from marsbeacon.base import (  # noqa: F401
    EFFORT_MINUTES,
    EMAIL_RE,
    EXAMPLE_RE,
    EXTRACT_GOOD_SHARE)
from marsbeacon.base import (  # noqa: F401
    EXTRACT_MAX_WORDS,
    EXTRACT_MIN_WORDS,
    EX_FAQPAGE,
    EX_LOCALBUSINESS)
from marsbeacon.base import (  # noqa: F401
    FAQ_HINT_RE,
    FILLER_DENSITY,
    FILLER_MIN_HITS,
    FILLER_RE)
from marsbeacon.base import (  # noqa: F401
    FRESH_STALE_DAYS,
    FRESH_WARN_DAYS,
    Finding,
    GENERIC_ANCHOR_RE)
from marsbeacon.base import (  # noqa: F401
    GOOD_CONTENT_WORDS,
    IGNORE_ROBOTS_ACK,
    JSONLD_CURRENCY_RE,
    JSONLD_DATE_KEYS)
from marsbeacon.base import (  # noqa: F401
    JSONLD_ISO_DATE_RE,
    JSONLD_PRICE_RE,
    JSONLD_REQUIRED,
    JSONLD_URL_KEYS)
from marsbeacon.base import (  # noqa: F401
    JSON_SCHEMA_VERSION,
    JUDGE_AUTO,
    JUDGE_CHUNK_CHARS,
    JUDGE_MAX_CHUNKS)
from marsbeacon.base import (  # noqa: F401
    JUDGE_MAX_TOKENS,
    JUDGE_MODEL,
    JUDGE_MODES,
    JUDGE_NOTE)
from marsbeacon.base import (  # noqa: F401
    JUDGE_OFF,
    JUDGE_ON,
    LIFECYCLE_HINTS,
    LIFECYCLE_SECTIONS)
from marsbeacon.base import (  # noqa: F401
    LIGHTHOUSE_ALWAYS,
    LIGHTHOUSE_AUTO,
    LIGHTHOUSE_CLI,
    LIGHTHOUSE_CRIT_SCORE)
from marsbeacon.base import (  # noqa: F401
    LIGHTHOUSE_CWV,
    LIGHTHOUSE_DEDUP,
    LIGHTHOUSE_DEVICES,
    LIGHTHOUSE_DEVICE_DESKTOP)
from marsbeacon.base import (  # noqa: F401
    LIGHTHOUSE_DEVICE_MOBILE,
    LIGHTHOUSE_DIR,
    LIGHTHOUSE_HIGH_WEIGHT,
    LIGHTHOUSE_MAX_EVIDENCE)
from marsbeacon.base import (  # noqa: F401
    LIGHTHOUSE_MODES,
    LIGHTHOUSE_NODE_MIN,
    LIGHTHOUSE_OFF,
    LIGHTHOUSE_PAGES_MAX)
from marsbeacon.base import (  # noqa: F401
    LIGHTHOUSE_PAGES_MIN,
    LIGHTHOUSE_PASS_SCORE,
    LIGHTHOUSE_PILLARS,
    LIGHTHOUSE_TIMEOUT_S)
from marsbeacon.base import (  # noqa: F401
    MARKET_WEIGHTS,
    MAX_WORKERS,
    PILLAR_ACCESS,
    PILLAR_META)
from marsbeacon.base import (  # noqa: F401
    PILLAR_RANK,
    PILLAR_SEC,
    PLACEHOLDER_SLUGS,
    PLACEHOLDER_TEXT_RE)
from marsbeacon.base import (  # noqa: F401
    Page,
    QUESTION_STARTERS,
    REFERENCES_HEADING_RE,
    RENDER_ALWAYS)
from marsbeacon.base import (  # noqa: F401
    RENDER_AUTO,
    RENDER_MODES,
    RENDER_OFF,
    RENDER_SETTLE_MS)
from marsbeacon.base import (  # noqa: F401
    RETRY_BACKOFF_S,
    RETRY_MAX_WAIT_S,
    RETRY_STATUS,
    ROBOTS_FORCE)
from marsbeacon.base import (  # noqa: F401
    ROBOTS_MODES,
    ROBOTS_OWN,
    ROBOTS_RESPECT,
    SEARCH_CHECK_AUTO)
from marsbeacon.base import (  # noqa: F401
    SEARCH_CHECK_DELAY_S,
    SEARCH_CHECK_ENDPOINT,
    SEARCH_CHECK_ENV,
    SEARCH_CHECK_MAX_QUERIES)
from marsbeacon.base import (  # noqa: F401
    SEARCH_CHECK_MODES,
    SEARCH_CHECK_NOTE,
    SEARCH_CHECK_OFF,
    SEARCH_CHECK_ON)
from marsbeacon.base import (  # noqa: F401
    SEARCH_CHECK_TOP_N,
    SEMANTIC_MIN_ELEMENTS,
    SEMANTIC_MIN_TYPES,
    SEMANTIC_TAGS)
from marsbeacon.base import (  # noqa: F401
    SEV_CRITICAL,
    SEV_INFO,
    SEV_OK,
    SEV_WARNING)
from marsbeacon.base import (  # noqa: F401
    SOFT_404_MAX_WORDS,
    SOFT_404_RE,
    STOPWORDS,
    THIN_CONTENT_WORDS)
from marsbeacon.base import (  # noqa: F401
    TITLE_MAX,
    TITLE_MIN,
    TOKEN_RE,
    TOP_N_MAX)
from marsbeacon.base import (  # noqa: F401
    TOP_N_MIN,
    USER_AGENT,
    USER_AGENT_TOKEN,
    _EFFORT_DAYS_RE)
from marsbeacon.base import (  # noqa: F401
    _EFFORT_MINUTES_RE,
    _SEVERITY_FACTOR,
    __version__,
    available_ram_mb)
from marsbeacon.base import (  # noqa: F401
    char_ngrams,
    estimate_effort,
    norm_url,
    surface_math)
from marsbeacon.base import tokenize  # noqa: F401
from marsbeacon.crawler import (  # noqa: F401
    Fetcher,
    PageRenderer,
    RobotsAudit,
    _meta)
from marsbeacon.crawler import (  # noqa: F401
    apply_rendering,
    build_chunks,
    crawl_links,
    dedupe_pages)
from marsbeacon.crawler import (  # noqa: F401
    discover_urls,
    extract_content,
    extract_jsonld,
    fetch_pages)
from marsbeacon.crawler import (  # noqa: F401
    is_js_heavy,
    parse_page,
    parse_sitemap)
from marsbeacon.indexes import (  # noqa: F401
    BM25Index,
    GRAPH_H,
    GRAPH_LABEL_ALL,
    GRAPH_MAX_NODES)
from marsbeacon.indexes import (  # noqa: F401
    GRAPH_W,
    VectorIndex,
    _bfs_depths,
    _build_link_edges)
from marsbeacon.indexes import (  # noqa: F401
    _force_layout,
    _quiet_huggingface,
    _squarify,
    check_llms_txt)
from marsbeacon.indexes import (  # noqa: F401
    depth_distribution,
    embeddings_available,
    link_graph_data,
    reciprocal_rank_fusion)
from marsbeacon.indexes import resolve_model_name, treemap_data  # noqa: F401
from marsbeacon.audits import (  # noqa: F401
    BRAND_DIR,
    GSC_QUERIES_LIMIT,
    OG_CORE,
    QUERY_BANNED)
from marsbeacon.audits import (  # noqa: F401
    QUERY_TEMPLATES,
    QueryResult,
    ShareResult,
    _LH_CATALOGS,
    _LH_EN_CATALOG)
from marsbeacon.audits import (  # noqa: F401
    _MD_LINK_RE,
    _as_list,
    _as_number,
    _audit_anchor_variety)
from marsbeacon.audits import (  # noqa: F401
    _audit_basic_meta,
    _audit_clickbait,
    _audit_extractability,
    _audit_filler)
from marsbeacon.audits import (  # noqa: F401
    _audit_freshness,
    _audit_lifecycle,
    _audit_link_graph,
    _audit_msft_ai_optout)
from marsbeacon.audits import (  # noqa: F401
    _audit_redirects,
    _audit_references,
    _audit_semantic_html,
    _bare_host)
from marsbeacon.audits import (  # noqa: F401
    _citability_gains,
    _finding_key,
    _jsonld_nodes,
    _judge_prompt)
from marsbeacon.audits import (  # noqa: F401
    _judge_sample,
    _kill_lighthouse,
    _lh_en_catalog,
    _lh_en_text,
    _lh_read_locale)
from marsbeacon.audits import (  # noqa: F401
    _lh_message_ids,
    _lhr_evidence,
    _lighthouse_page,
    _node_types)
from marsbeacon.audits import (  # noqa: F401
    _page_last_update,
    _site_position,
    _strip_md_links,
    append_history)
from marsbeacon.audits import (  # noqa: F401
    area_score,
    audit_eeat,
    audit_lexical,
    audit_semantic)
from marsbeacon.audits import (  # noqa: F401
    audit_structured_data,
    audit_technical,
    auto_queries,
    build_remediation)
from marsbeacon.audits import (  # noqa: F401
    citability_profiles,
    citability_top_actions,
    compute_delta,
    crawl_corpus)
from marsbeacon.audits import (  # noqa: F401
    dominant_language,
    find_acronyms,
    find_system_chrome,
    history_payload)
from marsbeacon.audits import (  # noqa: F401
    is_question,
    judge_unavailable,
    lh_locale_catalog,
    lighthouse_area_score)
from marsbeacon.audits import (  # noqa: F401
    lighthouse_findings,
    lighthouse_report_data,
    lighthouse_unavailable,
    lighthouse_version,
    load_gsc_queries)
from marsbeacon.audits import (  # noqa: F401
    merge_lighthouse_findings,
    node_version,
    overall_score,
    parse_gsc_queries,
    read_history_last)
from marsbeacon.audits import (  # noqa: F401
    run_judge,
    run_lighthouse,
    run_search_check,
    search_check_unavailable)
from marsbeacon.audits import (  # noqa: F401
    select_lighthouse_pages,
    simulate_rrf,
    simulate_share_of_voice,
    validate_jsonld)
from marsbeacon.i18n import (  # noqa: F401
    HTML_LANGS,
    _AREA_I18N,
    _FINDINGS_BY_LANG,
    _FINDINGS_DE,
    _FINDINGS_EN)
from marsbeacon.i18n import (  # noqa: F401
    _FINDINGS_ES,
    _FINDINGS_FR,
    _FRAME_I18N,
    _HTML_I18N,
    _LH_FRAME)
from marsbeacon.i18n import (  # noqa: F401
    _lighthouse_texts,
    csv_header,
    csv_yes,
    evidence_note,
    finding_texts,
    frame_text)
from marsbeacon.render import (  # noqa: F401
    FONTS_DIR,
    _CSS,
    _FONT_FILES,
    _REPORT_JS)
from marsbeacon.render import (  # noqa: F401
    _brand_font_css,
    _brand_logo_svg,
    _donut_svg,
    _finding_anchor)
from marsbeacon.render import (  # noqa: F401
    _md_cell,
    _render_hero,
    page_status_counts)
from marsbeacon.render import (  # noqa: F401
    render_csv,
    render_html,
    render_json,
    render_markdown)
from marsbeacon.render import render_text, score_verdict  # noqa: F401


def run_audit(base: str, max_pages: int, queries: List[str],
              model_name: str, delay: float, k: int,
              verbose: bool,
              max_body_mb: float = DEFAULT_MAX_BODY_MB,
              robots_mode: str = ROBOTS_RESPECT,
              retries: int = DEFAULT_RETRIES,
              competitors: Optional[List[str]] = None,
              user_agent: str = USER_AGENT,
              workers: int = DEFAULT_WORKERS,
              render: str = RENDER_OFF,
              top_n: int = DEFAULT_TOP_N,
              rrf_weights: Optional[Sequence[float]] = None,
              chunk_words: int = DEFAULT_CHUNK_WORDS,
              stop_event: Optional[threading.Event] = None) -> Tuple[
                  List[Page], List[Finding],
                  Dict[str, Optional[float]], List[QueryResult], str,
                  Optional[Dict[str, object]]]:
    """Esegue l'intero audit e restituisce i risultati grezzi.

    Con ``stop_event`` valorizzato l'audit e' annullabile: quando
    l'evento scatta viene sollevata ``AuditCancelled`` alla prima
    occasione utile (richieste HTTP e confini di fase).
    """
    def check_stop() -> None:
        if stop_event is not None and stop_event.is_set():
            raise AuditCancelled()

    requested_model = model_name
    model_name = resolve_model_name(model_name)
    if verbose and model_name and not requested_model.strip():
        print("sentence-transformers rilevato: recupero vettoriale "
              "con il modello predefinito %s (usa --embeddings none "
              "per il proxy char-tfidf)" % model_name,
              file=sys.stderr)

    if render != RENDER_OFF:
        # Verifica subito che Playwright e un browser ci siano:
        # meglio fallire prima della scansione che a meta' audit.
        PageRenderer(user_agent=user_agent, verbose=False).close()

    fetcher = Fetcher(delay=delay, verbose=verbose,
                      max_bytes=int(max_body_mb * 1048576),
                      retries=retries, user_agent=user_agent,
                      stop_event=stop_event)

    if verbose:
        print("[1/5] robots.txt", file=sys.stderr)
    robots = RobotsAudit(base, fetcher)
    findings: List[Finding] = robots.run()

    respect_main = robots_mode == ROBOTS_RESPECT
    respect_comp = robots_mode != ROBOTS_FORCE
    if robots_mode == ROBOTS_OWN:
        findings.append(Finding(
            AREA_TECH, SEV_INFO,
            "Sito dichiarato di propria titolarita'",
            "I Disallow del robots.txt non vengono applicati al "
            "sito auditato (--own-site); restano applicati agli "
            "eventuali concorrenti.",
            key="tech.robots.own"))
    elif robots_mode == ROBOTS_FORCE:
        findings.append(Finding(
            AREA_TECH, SEV_INFO,
            "Disallow del robots.txt ignorati su richiesta esplicita",
            "Scansione oltre i Disallow attivata con --ignore-robots "
            "%s: la responsabilita' della scansione e' stata assunta "
            "esplicitamente dall'utente."
            % IGNORE_ROBOTS_ACK,
            key="tech.robots.forced",
            params={"ack": IGNORE_ROBOTS_ACK}))

    if verbose:
        print("[2/5] scoperta URL", file=sys.stderr)
    urls, from_sitemap = discover_urls(base, robots, fetcher,
                                       max_pages, respect_main)
    if norm_url(base) not in {norm_url(u) for u in urls}:
        urls.insert(0, base)
    if respect_main:
        excluded = [u for u in urls if not robots.allowed(u)]
        urls = [u for u in urls if robots.allowed(u)]
        if excluded:
            findings.append(Finding(
                AREA_TECH, SEV_INFO,
                "%d URL esclusi per rispetto del robots.txt"
                % len(excluded),
                "I Disallow rivolti all'agente %s vengono rispettati "
                "(comportamento predefinito): %s. Usa --own-site se "
                "il sito e' tuo."
                % (USER_AGENT_TOKEN,
                   ", ".join(sorted(excluded)[:5])),
                key="tech.robots.excluded",
                params={"n": len(excluded),
                        "agent": USER_AGENT_TOKEN,
                        "urls": ", ".join(sorted(excluded)[:5])}))
    urls = urls[:max_pages]

    if verbose:
        print("[3/5] scansione di %d pagine (%d in parallelo)"
              % (len(urls), max(1, workers)), file=sys.stderr)
    pages = fetch_pages(fetcher, urls, workers=workers,
                        stop_event=stop_event)

    if render != RENDER_OFF:
        if verbose:
            print("[3b/5] rendering JavaScript (%s)" % render,
                  file=sys.stderr)
        pages, n_rendered, n_failed = apply_rendering(
            pages, render, user_agent=user_agent, delay=delay,
            verbose=verbose, stop_event=stop_event)
        if n_rendered:
            findings.append(Finding(
                AREA_TECH, SEV_INFO,
                "%d pagina/e analizzate col rendering JavaScript"
                % n_rendered,
                "Modalita' --render %s: il contenuto proviene dal "
                "DOM renderizzato in un browser headless; stato "
                "HTTP, redirect e tempi restano quelli della "
                "risposta originale." % render,
                key="tech.render.done",
                params={"n": n_rendered, "mode": render}))
        if n_failed:
            findings.append(Finding(
                AREA_TECH, SEV_WARNING,
                "Rendering non riuscito per %d pagina/e" % n_failed,
                "Per queste pagine e' stato analizzato l'HTML "
                "statico.",
                "Riprova, o aumenta il timeout se il sito e' lento.",
                key="tech.render.failed",
                params={"n": n_failed}))

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
            weight=1.0, key="tech.pages.duplicates",
            params={"n": len(duplicates),
                    "urls": ", ".join(sorted(duplicates)[:4])},
            example="Redirect 301 /index.html https://esempio.it/\n"
                    "e sulla pagina canonica:\n<link rel=\"canonical\""
                    " href=\"https://esempio.it/\">"))

    if chunk_words != DEFAULT_CHUNK_WORDS:
        # Il chunking di default avviene in extract_content: con un
        # target diverso si ricostruisce (i blocchi sono conservati).
        for p in pages:
            if p.ok:
                p.chunks = build_chunks(p, target_words=chunk_words)

    check_stop()
    if verbose:
        print("[4/5] controlli per area", file=sys.stderr)
    findings.append(check_llms_txt(base, fetcher))
    findings += audit_technical(pages, base, from_sitemap)
    findings += audit_lexical(pages)
    findings += audit_semantic(pages)
    findings += audit_eeat(pages)
    findings += audit_structured_data(pages)

    if verbose:
        print("[5/5] simulazione RRF", file=sys.stderr)
    check_stop()
    if not queries:
        queries = auto_queries([p for p in pages if p.ok])
    results, rrf_findings, mode = simulate_rrf(
        pages, queries, k=k, top_n=top_n, model_name=model_name,
        weights=rrf_weights)
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
                                  respect_comp, workers=workers)
            if chunk_words != DEFAULT_CHUNK_WORDS:
                for p in cpages:
                    if p.ok:
                        p.chunks = build_chunks(
                            p, target_words=chunk_words)
            corpora[host] = [c for p in cpages if p.ok
                             for c in p.chunks]
        own_chunks = [c for p in pages if p.ok for c in p.chunks]
        competitive, comp_findings = simulate_share_of_voice(
            base, own_chunks, corpora, queries, k=k, top_n=top_n,
            model_name=model_name, weights=rrf_weights)
        findings += comp_findings

    scores = {
        area: area_score(findings, area)
        for area in (AREA_TECH, AREA_LEX, AREA_SEM, AREA_SD, AREA_RRF)
    }
    return pages, findings, scores, results, mode, competitive


def build_parser() -> argparse.ArgumentParser:
    """Costruisce il parser degli argomenti da riga di comando."""
    parser = argparse.ArgumentParser(
        prog="mars_audit.py",
        description="MARS Beacon (Meta-fusion, Accessibility, "
                    "Ranking & Security Audit): audit SEO e "
                    "Reciprocal Rank Fusion di un sito.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Esempio:\n"
               "  python3 mars_audit.py https://example.com "
               "--format html --output report.html")
    parser.add_argument("url", help="URL di partenza del sito")
    parser.add_argument("--max-pages", type=int, default=25,
                        help="numero massimo di pagine (default 25)")
    parser.add_argument("--queries", metavar="FILE",
                        help="file con una query per riga; se omesso "
                             "le query sono generate dai temi del sito")
    parser.add_argument("--queries-gsc", metavar="CSV",
                        dest="queries_gsc",
                        help="export CSV 'Query' di Google Search "
                             "Console (Rendimento): usa le query "
                             "reali (prime %d per clic e "
                             "impressioni) al posto di quelle "
                             "auto-generate; non combinabile con "
                             "--queries" % GSC_QUERIES_LIMIT)
    parser.add_argument("--embeddings", metavar="MODELLO", default="",
                        help="modello sentence-transformers per il "
                             "recupero vettoriale reale. Se omesso e "
                             "la libreria e' installata viene usato "
                             "%s; 'none' forza il proxy char-tfidf"
                             % DEFAULT_EMBEDDINGS_MODEL)
    parser.add_argument("--rrf-k", type=int, default=60,
                        help="costante k della formula RRF "
                             "(default 60)")
    parser.add_argument("--top-n", type=int, dest="top_n",
                        default=DEFAULT_TOP_N, metavar="N",
                        help="posti fusi considerati per query "
                             "(da %d a %d, default %d): governa "
                             "consenso e share of voice"
                             % (TOP_N_MIN, TOP_N_MAX,
                                DEFAULT_TOP_N))
    parser.add_argument("--rrf-weights", default="1,1",
                        metavar="LES,VET", dest="rrf_weights",
                        help="variante RRF pesata: pesi delle due "
                             "liste (lessicale,vettoriale), due "
                             "numeri positivi separati da virgola; "
                             "'1,1' e' l'RRF classico (default)")
    parser.add_argument("--chunk-words", type=int,
                        dest="chunk_words",
                        default=DEFAULT_CHUNK_WORDS, metavar="N",
                        help="dimensione obiettivo dei chunk in "
                             "parole (da %d a %d, default %d): il "
                             "taglio segue comunque gli heading"
                             % (CHUNK_WORDS_MIN, CHUNK_WORDS_MAX,
                                DEFAULT_CHUNK_WORDS))
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
    parser.add_argument("--format",
                        choices=("text", "json", "html", "md",
                                 "csv"),
                        default="text",
                        help="formato del referto: text, json, "
                             "html autonomo, md (Markdown per "
                             "issue/PR, piano come task list) o "
                             "csv (rilievi per Excel/Sheets, "
                             "';' e BOM)")
    parser.add_argument("--lang", choices=HTML_LANGS,
                        default="it",
                        help="lingua del referto per i formati "
                             "html, text, md e csv: cornice E "
                             "rilievi (titoli, dettagli, fix, "
                             "esempi via catalogo — una tabella "
                             "per lingua: en, fr, de, es). Le "
                             "evidenze citate dal sito (URL, "
                             "estratti) restano nella lingua del "
                             "sito, dichiarato nel referto. Il "
                             "JSON resta canonico in italiano con "
                             "chiave e parametri di traduzione "
                             "per rilievo (default it)")
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
    parser.add_argument("--market", choices=tuple(MARKET_WEIGHTS),
                        default=DEFAULT_MARKET,
                        help="mercato di riferimento per l'indice "
                             "composito dei profili di citabilita' "
                             "per assistente IA: 'occidentale' pesa "
                             "di piu' ChatGPT/Perplexity e Claude, "
                             "'orientale' Qwen e Kimi, 'globale' "
                             "pesa tutti allo stesso modo "
                             "(default %s)" % DEFAULT_MARKET)
    parser.add_argument("--config", metavar="FILE",
                        help="file TOML con le soglie di prassi "
                             "personalizzate (tabella [soglie]: "
                             "title_min/max, description_min/max, "
                             "parole_scarse/obiettivo, "
                             "estraibilita_minima, "
                             "varieta_anchor_minima — esempio "
                             "commentato in "
                             "docs/soglie.esempio.toml). I valori "
                             "sostituiscono i default in tutto "
                             "l'audit, i rilievi dichiarano le "
                             "soglie usate e il referto JSON le "
                             "echeggia nel blocco 'thresholds'. "
                             "Richiede Python >= 3.11 (tomllib) "
                             "oppure il pacchetto tomli")
    parser.add_argument("--history", metavar="FILE",
                        help="storico JSONL delle esecuzioni: "
                             "legge l'ultima riga dello stesso "
                             "sito per riportare nei referti il "
                             "delta (punteggi per area, rilievi "
                             "nuovi/risolti) e accoda una riga "
                             "compatta per l'esecuzione corrente. "
                             "Trasforma l'audit in monitoraggio "
                             "anche da riga di comando/cron")
    parser.add_argument("--fail-under", type=float, metavar="PUNTI",
                        help="esce con codice 1 se il punteggio "
                             "complessivo (0-100) e' sotto questa "
                             "soglia: gate di regressione per gli "
                             "audit schedulati (cron/systemd), in "
                             "aggiunta all'uscita 1 sui rilievi "
                             "critici")
    parser.add_argument("--judge", choices=JUDGE_MODES,
                        default=DEFAULT_JUDGE,
                        help="giudizio LLM sulla citabilita' dei "
                             "passaggi migliori tramite l'API "
                             "Anthropic (SDK ufficiale, chiave solo "
                             "da ANTHROPIC_API_KEY): 'auto' "
                             "(default) lo esegue se la chiave e' "
                             "presente, 'on' lo pretende (errore "
                             "senza chiave), 'off' lo disattiva. "
                             "Una sola richiesta API per audit, "
                             "con costi a carico della chiave")
    parser.add_argument("--search-check",
                        choices=SEARCH_CHECK_MODES,
                        default=SEARCH_CHECK_AUTO,
                        dest="search_check",
                        help="ancora di realta': cerca il sito "
                             "sulle query dell'audit con la Brave "
                             "Search API (chiave solo da %s) e "
                             "confronta il ranking reale col "
                             "consenso RRF simulato. 'auto' "
                             "(default) parte solo con la chiave "
                             "presente, 'on' la pretende, 'off' "
                             "disattiva. Max %d query, una "
                             "richiesta al secondo, costi a "
                             "carico della chiave"
                             % (SEARCH_CHECK_ENV,
                                SEARCH_CHECK_MAX_QUERIES))
    parser.add_argument("--render", choices=RENDER_MODES,
                        default=RENDER_OFF,
                        help="rendering JavaScript con browser "
                             "headless (richiede Playwright): 'auto' "
                             "rende solo le pagine con contenuto "
                             "lato client, 'always' tutte; il "
                             "rendering e' seriale e rispetta "
                             "--delay fra le pagine (default off)")
    parser.add_argument("--lighthouse", choices=LIGHTHOUSE_MODES,
                        default=LIGHTHOUSE_OFF,
                        help="audit Lighthouse (Performance, "
                             "Accessibilita', SEO, Best Practices) "
                             "col fork installato da "
                             "tools/update-lighthouse.sh; richiede "
                             "Node >= %d.%d e Chrome/Chromium. "
                             "'auto' lo esegue se i requisiti ci "
                             "sono, altrimenti salto dichiarato; "
                             "'always' li pretende (errore d'uso "
                             "senza); default off"
                             % LIGHTHOUSE_NODE_MIN)
    parser.add_argument("--lighthouse-pages", type=int,
                        default=DEFAULT_LIGHTHOUSE_PAGES,
                        metavar="N",
                        help="pagine rappresentative sottoposte a "
                             "Lighthouse oltre alla home, da %d a "
                             "%d (default %d; ~10-30 s a pagina)"
                             % (LIGHTHOUSE_PAGES_MIN,
                                LIGHTHOUSE_PAGES_MAX,
                                DEFAULT_LIGHTHOUSE_PAGES))
    parser.add_argument("--lighthouse-device",
                        choices=LIGHTHOUSE_DEVICES,
                        default=LIGHTHOUSE_DEVICE_MOBILE,
                        help="dispositivo emulato da Lighthouse, "
                             "con throttling corrispondente: "
                             "'mobile' (default, come PageSpeed) "
                             "o 'desktop'")
    parser.add_argument("--workers", type=int,
                        default=DEFAULT_WORKERS, metavar="N",
                        help="richieste in parallelo durante la "
                             "scansione, da 1 a %d (default %d; 1 = "
                             "seriale). Il ritmo verso il sito non "
                             "cambia: gli avvii restano distanziati "
                             "di --delay, i worker sovrappongono "
                             "solo le attese di rete"
                             % (MAX_WORKERS, DEFAULT_WORKERS))
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
    parser.add_argument("--own-site", action="store_true",
                        help="dichiara che il sito auditato e' di "
                             "tua titolarita' (o sei autorizzato): "
                             "i Disallow del robots.txt non vengono "
                             "applicati al sito; restano applicati "
                             "ai concorrenti di --competitor")
    parser.add_argument("--ignore-robots", metavar="ACCETTO",
                        default=None,
                        help="ignora i Disallow del robots.txt anche "
                             "su siti non tuoi (concorrenti "
                             "compresi). Richiede l'accettazione "
                             "esplicita di responsabilita': passa il "
                             "valore letterale '%s'"
                             % IGNORE_ROBOTS_ACK)
    parser.add_argument("--respect-robots", action="store_true",
                        help="deprecato: il rispetto dei Disallow "
                             "per l'agente %s e' ora il comportamento "
                             "predefinito; il flag resta accettato "
                             "per compatibilita' e non puo' essere "
                             "combinato con --own-site o "
                             "--ignore-robots" % USER_AGENT_TOKEN)
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
    if not 1 <= args.workers <= MAX_WORKERS:
        print("--workers deve essere fra 1 e %d." % MAX_WORKERS,
              file=sys.stderr)
        return 2
    if not TOP_N_MIN <= args.top_n <= TOP_N_MAX:
        print("--top-n deve essere fra %d e %d."
              % (TOP_N_MIN, TOP_N_MAX), file=sys.stderr)
        return 2
    if not CHUNK_WORDS_MIN <= args.chunk_words <= CHUNK_WORDS_MAX:
        print("--chunk-words deve essere fra %d e %d."
              % (CHUNK_WORDS_MIN, CHUNK_WORDS_MAX),
              file=sys.stderr)
        return 2
    try:
        parts = str(args.rrf_weights).split(",")
        if len(parts) != 2:
            raise ValueError("servono due pesi")
        rrf_weights = (float(parts[0]), float(parts[1]))
        if rrf_weights[0] <= 0 or rrf_weights[1] <= 0:
            raise ValueError("pesi non positivi")
    except ValueError:
        print("--rrf-weights vuole due numeri positivi separati "
              "da virgola, es. 1,1 oppure 1.5,1.", file=sys.stderr)
        return 2

    if args.ignore_robots is not None:
        if args.respect_robots or args.own_site:
            print("--ignore-robots non e' combinabile con "
                  "--respect-robots o --own-site.", file=sys.stderr)
            return 2
        if args.ignore_robots.strip().lower() != IGNORE_ROBOTS_ACK:
            print("Per ignorare i Disallow serve l'accettazione "
                  "esplicita di responsabilita': --ignore-robots %s"
                  % IGNORE_ROBOTS_ACK, file=sys.stderr)
            return 2
        robots_mode = ROBOTS_FORCE
    elif args.own_site:
        if args.respect_robots:
            print("--own-site non e' combinabile con "
                  "--respect-robots.", file=sys.stderr)
            return 2
        robots_mode = ROBOTS_OWN
    else:
        robots_mode = ROBOTS_RESPECT
    if args.judge == JUDGE_ON:
        judge_reason = judge_unavailable()
        if judge_reason:
            print("--judge on richiede il giudizio LLM: %s"
                  % judge_reason, file=sys.stderr)
            return 2
    if not (LIGHTHOUSE_PAGES_MIN <= args.lighthouse_pages
            <= LIGHTHOUSE_PAGES_MAX):
        print("--lighthouse-pages deve essere fra %d e %d."
              % (LIGHTHOUSE_PAGES_MIN, LIGHTHOUSE_PAGES_MAX),
              file=sys.stderr)
        return 2
    if args.lighthouse == LIGHTHOUSE_ALWAYS:
        lighthouse_reason = lighthouse_unavailable()
        if lighthouse_reason:
            print("--lighthouse always richiede l'audit "
                  "Lighthouse: %s" % lighthouse_reason,
                  file=sys.stderr)
            return 2
    if args.search_check == SEARCH_CHECK_ON:
        sc_reason = search_check_unavailable()
        if sc_reason:
            print("--search-check on richiede l'ancora di "
                  "realta': %s" % sc_reason, file=sys.stderr)
            return 2
    ram = available_ram_mb()
    if ram is not None and args.max_body > ram * 0.1:
        print("Avviso: --max-body %.0f MB e' alto per questa "
              "macchina (RAM disponibile ora: %.0f MB). "
              "Suggerito un valore <= %.0f MB."
              % (args.max_body, ram, max(1.0, ram * 0.1)),
              file=sys.stderr)

    if args.fail_under is not None \
            and not 0 <= args.fail_under <= 100:
        print("--fail-under vuole una soglia fra 0 e 100.",
              file=sys.stderr)
        return 2

    soglie: Dict[str, object] = {}
    if args.config:
        try:
            soglie = load_thresholds(args.config)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        apply_thresholds(soglie)
        if soglie and not args.quiet:
            print("Soglie personalizzate da %s: %s"
                  % (args.config,
                     ", ".join("%s=%s" % coppia
                               for coppia in sorted(soglie.items()))),
                  file=sys.stderr)

    if args.queries and args.queries_gsc:
        print("--queries e --queries-gsc non sono combinabili: "
              "scegli una sola sorgente di query.", file=sys.stderr)
        return 2

    queries: List[str] = []
    if args.queries:
        try:
            with open(args.queries, encoding="utf-8") as handle:
                queries = [ln.strip() for ln in handle if ln.strip()]
        except OSError as exc:
            print("Impossibile leggere %s: %s" % (args.queries, exc),
                  file=sys.stderr)
            return 2
    elif args.queries_gsc:
        try:
            queries = load_gsc_queries(args.queries_gsc)
        except OSError as exc:
            print("Impossibile leggere %s: %s"
                  % (args.queries_gsc, exc), file=sys.stderr)
            return 2
        if not queries:
            print("Nessuna query utilizzabile in %s."
                  % args.queries_gsc, file=sys.stderr)
            return 2
        if not args.quiet:
            print("%d query reali da Search Console" % len(queries),
                  file=sys.stderr)

    try:
        pages, findings, scores, results, mode, competitive = \
            run_audit(
                base=base, max_pages=args.max_pages, queries=queries,
                model_name=args.embeddings, delay=args.delay,
                k=args.rrf_k, verbose=not args.quiet,
                max_body_mb=args.max_body,
                robots_mode=robots_mode,
                retries=max(0, args.retries),
                competitors=competitors,
                user_agent=args.user_agent,
                workers=args.workers,
                render=args.render,
                top_n=args.top_n,
                rrf_weights=rrf_weights,
                chunk_words=args.chunk_words)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\nInterrotto dall'utente.", file=sys.stderr)
        return 130

    try:
        lighthouse_data = run_lighthouse(
            base, pages, args.lighthouse, args.lighthouse_pages,
            args.lighthouse_device, delay=args.delay,
            verbose=not args.quiet)
    except KeyboardInterrupt:
        print("\nInterrotto dall'utente.", file=sys.stderr)
        return 130
    findings = merge_lighthouse_findings(findings, lighthouse_data)
    lighthouse_score = lighthouse_area_score(lighthouse_data)
    if lighthouse_score is not None:
        scores[AREA_LIGHTHOUSE] = lighthouse_score
    lighthouse_block = lighthouse_report_data(lighthouse_data)

    judge_data = run_judge(results, pages, args.judge,
                           verbose=not args.quiet)
    search_data = run_search_check(base, results,
                                   args.search_check,
                                   verbose=not args.quiet)

    delta = None
    current_row = history_payload(base, findings, scores,
                                  lighthouse=lighthouse_block)
    if args.history:
        previous = read_history_last(args.history, base)
        if previous:
            try:
                delta = compute_delta(
                    previous, current_row,
                    float(previous.get("created_at") or 0))
            except (ValueError, KeyError, TypeError):
                delta = None  # riga precedente illeggibile

    renderers = {"text": render_text, "json": render_json,
                 "html": render_html, "md": render_markdown,
                 "csv": render_csv}
    extra: Dict[str, object] = {}
    if args.format == "json":
        extra["rrf_params"] = {
            "top_n": args.top_n,
            "weights": list(rrf_weights),
            "chunk_words": args.chunk_words,
        }
        extra["thresholds"] = soglie or None
    if args.format in ("html", "text", "md", "csv"):
        extra["lang"] = args.lang
    report = renderers[args.format](
        base, pages, findings, scores, results, mode, args.rrf_k,
        competitive, market=args.market, judge=judge_data,
        delta=delta, lighthouse=lighthouse_block,
        search_check=search_data, **extra)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(report)
        print("Referto scritto in %s" % args.output, file=sys.stderr)
    else:
        print(report)

    if args.history:
        try:
            append_history(args.history, current_row)
        except OSError as exc:
            print("Avviso: impossibile aggiornare lo storico %s: %s"
                  % (args.history, exc), file=sys.stderr)

    critical = sum(1 for f in findings if f.severity == SEV_CRITICAL)
    overall = overall_score(scores)
    if args.fail_under is not None and overall < args.fail_under:
        print("Punteggio complessivo %.1f sotto la soglia "
              "--fail-under %g." % (overall, args.fail_under),
              file=sys.stderr)
        return 1
    return 1 if critical else 0


if __name__ == "__main__":
    sys.exit(main())
