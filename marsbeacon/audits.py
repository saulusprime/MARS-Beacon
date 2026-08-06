# -*- coding: utf-8 -*-
"""Controlli per area, punteggi, citabilita', storico, giudizio LLM,
audit Lighthouse e ancora di realta'.

Generato dalla scomposizione di mars_audit.py (v1.58.0): il
namespace pubblico resta mars_audit, questo modulo e' interno.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict
from dataclasses import dataclass
from dataclasses import field
from typing import Dict
from typing import List
from typing import Optional
from typing import Sequence
from typing import Set
from typing import Tuple
from urllib.parse import urlparse
import csv
import datetime
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time

from marsbeacon.base import (
    ABOUT_SLUGS,
    ANAPHORA_RE,
    ANCHOR_MIN_PAIRS,
    ANCHOR_VARIETY_GOOD,
    AREA_LEX,
    AREA_LIGHTHOUSE,
    AREA_RRF,
    AREA_SD,
    AREA_SEM,
    AREA_TECH,
    AuditCancelled,
    CHROME_PATHS,
    CITABILITY_DEPTH,
    CITABILITY_NOTE,
    CITABILITY_PROFILES,
    CITATIONS_GOOD,
    CITATION_RE,
    CLICKBAIT_RE,
    CONTACT_SLUGS,
    CROSS_GAIN_MIN,
    Chunk,
    DEFAULT_JUDGE,
    DEFAULT_LIGHTHOUSE_PAGES,
    DEFAULT_MARKET,
    DEFAULT_TOP_N,
    DEFINITION_RE,
    DEPTH_TARGET_WORDS,
    DESC_MAX,
    DESC_MIN,
    DIRECT_ANSWER_RE,
    DIVITIS_RATIO,
    EFFORT_MINUTES,
    EMAIL_RE,
    EXAMPLE_RE,
    EXTRACT_GOOD_SHARE,
    EXTRACT_MAX_WORDS,
    EXTRACT_MIN_WORDS,
    EX_FAQPAGE,
    EX_LOCALBUSINESS,
    FAQ_HINT_RE,
    FILLER_DENSITY,
    FILLER_MIN_HITS,
    FILLER_RE,
    FRESH_STALE_DAYS,
    FRESH_WARN_DAYS,
    Finding,
    GOOD_CONTENT_WORDS,
    JSONLD_CURRENCY_RE,
    JSONLD_DATE_KEYS,
    JSONLD_ISO_DATE_RE,
    JSONLD_PRICE_RE,
    JSONLD_REQUIRED,
    JSONLD_URL_KEYS,
    JSON_SCHEMA_VERSION,
    JUDGE_CHUNK_CHARS,
    JUDGE_MAX_CHUNKS,
    JUDGE_MAX_TOKENS,
    JUDGE_MODEL,
    JUDGE_NOTE,
    JUDGE_OFF,
    LIFECYCLE_HINTS,
    LIFECYCLE_SECTIONS,
    LIGHTHOUSE_CLI,
    LIGHTHOUSE_CRIT_SCORE,
    LIGHTHOUSE_CWV,
    LIGHTHOUSE_DEDUP,
    LIGHTHOUSE_DEVICE_DESKTOP,
    LIGHTHOUSE_DEVICE_MOBILE,
    LIGHTHOUSE_DIR,
    LIGHTHOUSE_HIGH_WEIGHT,
    LIGHTHOUSE_MAX_EVIDENCE,
    LIGHTHOUSE_NODE_MIN,
    LIGHTHOUSE_OFF,
    LIGHTHOUSE_PASS_SCORE,
    LIGHTHOUSE_PILLARS,
    LIGHTHOUSE_TIMEOUT_S,
    MARKET_WEIGHTS,
    PILLAR_ACCESS,
    PILLAR_SEC,
    PLACEHOLDER_SLUGS,
    PLACEHOLDER_TEXT_RE,
    Page,
    QUESTION_STARTERS,
    REFERENCES_HEADING_RE,
    SEARCH_CHECK_AUTO,
    SEARCH_CHECK_DELAY_S,
    SEARCH_CHECK_ENDPOINT,
    SEARCH_CHECK_ENV,
    SEARCH_CHECK_MAX_QUERIES,
    SEARCH_CHECK_NOTE,
    SEARCH_CHECK_OFF,
    SEARCH_CHECK_TOP_N,
    SEMANTIC_MIN_ELEMENTS,
    SEMANTIC_MIN_TYPES,
    SEV_CRITICAL,
    SEV_INFO,
    SEV_OK,
    SEV_WARNING,
    SOFT_404_MAX_WORDS,
    SOFT_404_RE,
    THIN_CONTENT_WORDS,
    TITLE_MAX,
    TITLE_MIN,
    _SEVERITY_FACTOR,
    __version__,
    estimate_effort,
    norm_url,
    requests,
    surface_math,
    tokenize)
from marsbeacon.crawler import (
    Fetcher,
    RobotsAudit,
    dedupe_pages,
    discover_urls,
    fetch_pages,
    is_js_heavy)
from marsbeacon.indexes import (
    BM25Index,
    VectorIndex,
    _bfs_depths,
    _build_link_edges,
    reciprocal_rank_fusion)


def build_remediation(
        findings: Sequence["Finding"],
        pages: Optional[Sequence["Page"]] = None,
        scores: Optional[Dict[str, Optional[float]]] = None,
        market: str = DEFAULT_MARKET) -> List[Dict[str, object]]:
    """Piano d'azione: critici e avvertenze ordinati per resa.

    Senza dati di citabilita' (pages/scores omessi) l'ordine e'
    gravita', poi peso decrescente: il contributo del rilievo al
    punteggio. Con pages e scores ogni intervento viene annotato con
    i guadagni per profilo di citabilita' (_citability_gains) e, a
    parita' di gravita', vengono promossi i rilievi col maggior
    guadagno sull'indice composito del mercato scelto: i problemi
    **trasversali**, che deprimono piu' profili insieme, salgono in
    testa. Ogni intervento porta la stima dello sforzo
    (minuti/ore/giorni); i critici da minuti sono "quick win".
    """
    order = {SEV_CRITICAL: 0, SEV_WARNING: 1}
    cit = (citability_profiles(pages, scores, market)
           if pages is not None and scores is not None else None)
    todo = [f for f in findings if f.severity in order]

    notes: Dict[int, Dict[str, object]] = {}
    if cit:
        totals: Dict[str, float] = {}
        for f in findings:
            if f.severity in _SEVERITY_FACTOR:
                totals[f.area] = totals.get(f.area, 0.0) + f.weight
        for f in todo:
            notes[id(f)] = _citability_gains(f, totals, cit)
        todo.sort(key=lambda f: (
            order[f.severity],
            -float(notes[id(f)]["index_gain"]),
            -f.weight))
    else:
        todo.sort(key=lambda f: (order[f.severity], -f.weight))

    plan: List[Dict[str, object]] = []
    for pos, f in enumerate(todo, 1):
        effort = estimate_effort(f)
        item: Dict[str, object] = {
            "priority": pos,
            "severity": f.severity,
            "area": f.area,
            "title": f.title,
            "fix": f.fix,
            "example": f.example,
            "url": f.url,
            "effort": effort,
            "quick_win": (effort == EFFORT_MINUTES
                          and f.severity == SEV_CRITICAL),
            # per la traduzione dei referti (finding_texts)
            "key": f.key,
            "params": dict(f.params),
        }
        if cit:
            item.update(notes[id(f)])
        plan.append(item)
    return plan


def find_system_chrome() -> Optional[str]:
    """Primo Chrome/Chromium di sistema esistente, o None.

    Stessi percorsi (CHROME_PATHS) usati dal rendering JavaScript
    come ripiego quando Playwright non ha un Chromium proprio.
    """
    for path in CHROME_PATHS:
        if os.path.exists(path):
            return path
    return None


def node_version() -> Optional[Tuple[int, ...]]:
    """Versione di Node come tupla, es. (22, 22, 1); None se assente."""
    node = shutil.which("node")
    if node is None:
        return None
    try:
        proc = subprocess.run([node, "--version"], capture_output=True,
                              text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    raw = proc.stdout.strip().lstrip("v")
    try:
        return tuple(int(n) for n in raw.split(".")[:3])
    except ValueError:
        return None


def lighthouse_version() -> Optional[str]:
    """Tag installato del fork (lighthouse/VERSIONE), o None."""
    try:
        with open(os.path.join(LIGHTHOUSE_DIR, "VERSIONE"),
                  encoding="utf-8") as fh:
            return fh.read().strip() or None
    except OSError:
        return None


def lighthouse_unavailable() -> Optional[str]:
    """None se l'audit Lighthouse puo' funzionare, altrimenti il motivo.

    Requisiti (docs/LIGHTHOUSE-FORK.md): fork installato accanto
    allo script da tools/update-lighthouse.sh, Node >=
    LIGHTHOUSE_NODE_MIN e un Chrome/Chromium di sistema.
    """
    if not os.path.isfile(LIGHTHOUSE_CLI):
        return ("fork Lighthouse non installato: esegui "
                "tools/update-lighthouse.sh")
    version = node_version()
    if version is None:
        return ("Node non trovato: il fork richiede Node >= %d.%d"
                % LIGHTHOUSE_NODE_MIN)
    if version < LIGHTHOUSE_NODE_MIN:
        return ("Node %s troppo vecchio: il fork richiede >= %d.%d"
                % (".".join(str(n) for n in version),
                   LIGHTHOUSE_NODE_MIN[0], LIGHTHOUSE_NODE_MIN[1]))
    if find_system_chrome() is None:
        return ("nessun Chrome/Chromium di sistema trovato: installa "
                "Google Chrome o Chromium")
    return None


def select_lighthouse_pages(base: str, pages: Sequence[Page],
                            n: int) -> List[str]:
    """Home + n pagine rappresentative da sottoporre a Lighthouse.

    Euristica dichiarata (decisione P1 "profondita'/traffico": i
    dati di traffico non esistono offline): dopo la home contano i
    link interni in ingresso — l'importanza che il sito stesso
    assegna alle pagine — e, a parita', la vicinanza alla home.
    Ordinamento deterministico; riusa il grafo dei link dell'audit.
    """
    good = [p for p in pages if p.ok]
    if not good:
        return []
    home = norm_url(base)
    edges, incoming = _build_link_edges(good)
    depth = _bfs_depths(edges, home)
    ranked = sorted(
        (p for p in good if norm_url(p.url) != home),
        key=lambda p: (-incoming.get(norm_url(p.url), 0),
                       depth.get(norm_url(p.url), 99),
                       norm_url(p.url)))
    urls = [p.url for p in good if norm_url(p.url) == home][:1]
    urls.extend(p.url for p in ranked[:n])
    return urls


def _kill_lighthouse(proc: "subprocess.Popen") -> None:
    """Termina il processo Node: prima con garbo, poi kill."""
    try:
        proc.terminate()
        proc.wait(timeout=5)
    except Exception:
        try:
            proc.kill()
            proc.wait(timeout=5)
        except Exception:
            pass  # gia' morto o non uccidibile: nulla da fare


def _lighthouse_page(url: str, device: str, node: str, chrome: str,
                     timeout_s: float,
                     stop_event: Optional["threading.Event"]
                     ) -> Tuple[Optional[Dict], Optional[str]]:
    """Un run di Lighthouse su una pagina: (LHR, None) o (None, errore).

    Il processo Node viene atteso a piccoli passi, cosi'
    l'annullamento cooperativo puo' ucciderlo alla prima occasione
    utile; oltre ``timeout_s`` il processo viene ucciso e il
    fallimento e' dichiarato senza fermare le altre pagine.
    """
    cmd = [node, LIGHTHOUSE_CLI, url, "--output=json", "--quiet",
           "--locale=it", "--chrome-flags=--headless=new"]
    if device == LIGHTHOUSE_DEVICE_DESKTOP:
        cmd.append("--preset=desktop")
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                env=dict(os.environ,
                                         CHROME_PATH=chrome))
    except OSError as exc:
        return None, "avvio impossibile: %s" % exc
    start = time.monotonic()
    while True:
        if stop_event is not None and stop_event.is_set():
            _kill_lighthouse(proc)
            raise AuditCancelled()
        try:
            out, err = proc.communicate(timeout=0.5)
            break
        except subprocess.TimeoutExpired:
            if time.monotonic() - start > timeout_s:
                _kill_lighthouse(proc)
                return None, "tempo scaduto (%d s)" % timeout_s
    if proc.returncode != 0:
        detail = (err or b"").decode("utf-8", "replace").strip()
        detail = detail.splitlines()[-1][:160] if detail \
            else "nessun dettaglio"
        return None, "uscita %d: %s" % (proc.returncode, detail)
    try:
        return json.loads(out.decode("utf-8", "replace")), None
    except ValueError:
        return None, "il referto LHR non e' JSON valido"


_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


# Catalogo inglese dei messaggi Lighthouse, caricato pigramente dal
# fork installato (decisione i18n P1: le stringhe localizzate le
# fornisce Lighthouse stesso, nessun catalogo interno da mantenere).
_LH_EN_CATALOG: Optional[Dict[str, str]] = None


def _lh_read_locale(filename: str) -> Dict[str, str]:
    """Messaggi id -> testo da un file di locale del fork.

    Vuoto se il file manca o non si legge: i testi dei rilievi
    Lighthouse restano in italiano nei referti tradotti — stesso
    fallback dichiarato, campo per campo, dei cataloghi dei
    rilievi.
    """
    catalog: Dict[str, str] = {}
    path = os.path.join(LIGHTHOUSE_DIR, "shared",
                        "localization", "locales", filename)
    try:
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
    except (OSError, ValueError):
        return catalog
    for msg_id, entry in raw.items():
        message = entry.get("message") \
            if isinstance(entry, dict) else None
        if isinstance(message, str):
            catalog[msg_id] = message
    return catalog


def _lh_en_catalog() -> Dict[str, str]:
    """Messaggi inglesi del fork (en-US.json), una volta sola."""
    global _LH_EN_CATALOG
    if _LH_EN_CATALOG is None:
        _LH_EN_CATALOG = _lh_read_locale("en-US.json")
    return _LH_EN_CATALOG


# Cache dei locale non inglesi del fork (fr.json, de.json, ...),
# caricati pigramente alla prima richiesta della lingua.
_LH_CATALOGS: Dict[str, Dict[str, str]] = {}


def lh_locale_catalog(lang: str) -> Dict[str, str]:
    """Messaggi del fork nella lingua del referto, una volta sola.

    Per l'inglese vale ``_lh_en_catalog()`` (risolto dal parser al
    parse-time: i referti gia' salvati nello storico restano
    leggibili); per le altre lingue il file e' ``<lang>.json`` e
    la risoluzione avviene al rendering dagli id dei messaggi.
    """
    if lang == "en":
        return _lh_en_catalog()
    if lang not in _LH_CATALOGS:
        _LH_CATALOGS[lang] = _lh_read_locale("%s.json" % lang)
    return _LH_CATALOGS[lang]


def _lh_message_ids(lhr: Dict[str, object]) -> Dict[str, str]:
    """Percorso nel LHR -> id del messaggio (icuMessagePaths).

    Il LHR dichiara quale messaggio localizzato ha prodotto ogni
    testo (``i18n.icuMessagePaths``): invertendo la mappa si
    risale, per ciascun audit, all'id con cui cercare il testo
    inglese nel catalogo del fork.
    """
    out: Dict[str, str] = {}
    i18n = lhr.get("i18n")
    paths = i18n.get("icuMessagePaths") \
        if isinstance(i18n, dict) else None
    if not isinstance(paths, dict):
        return out
    for msg_id, targets in paths.items():
        if not isinstance(targets, list):
            continue
        for target in targets:
            if isinstance(target, str):
                out[target] = msg_id
            elif isinstance(target, dict) \
                    and isinstance(target.get("path"), str):
                out[target["path"]] = msg_id
    return out


def _lh_en_text(reverse: Dict[str, str],
                path: str) -> Optional[str]:
    """Testo inglese del messaggio dietro ``path``, o None.

    I messaggi con placeholder ICU residui non vengono usati
    (niente interpolazione parziale: resta l'italiano).
    """
    msg_id = reverse.get(path)
    if not msg_id:
        return None
    text = _lh_en_catalog().get(msg_id)
    if not text or "{" in text:
        return None
    return text


def _strip_md_links(text: str) -> str:
    """Da ``[testo](url)`` a ``testo``: le description del LHR sono
    Markdown con link di approfondimento, i referti MARS sono prosa."""
    return _MD_LINK_RE.sub(r"\1", text or "").strip()


def _lhr_evidence(details: object) -> List[str]:
    """Prime evidenze leggibili dagli ``items`` dei details LHR.

    I details variano per tipo di audit (table, opportunity, list):
    si estrae il campo piu' informativo di ogni item — URL, selettore
    o snippet del nodo, etichetta — senza pretendere uno schema.
    """
    if not isinstance(details, dict):
        return []
    items = details.get("items")
    if not isinstance(items, list):
        return []
    out: List[str] = []
    for item in items[:LIGHTHOUSE_MAX_EVIDENCE]:
        if not isinstance(item, dict):
            continue
        label: object = None
        node = item.get("node")
        if isinstance(node, dict):
            label = node.get("selector") or node.get("snippet")
        if not label:
            for name in ("url", "source", "label", "text", "origin"):
                value = item.get(name)
                if isinstance(value, str) and value:
                    label = value
                    break
        if label:
            out.append(str(label)[:120])
    return out


def lighthouse_findings(data: Optional[Dict[str, object]]
                        ) -> List[Finding]:
    """Converte i LHR raccolti dal runner in rilievi MARS.

    Un rilievo per audit, aggregato su tutte le pagine esaminate
    (punteggio peggiore, peso massimo, URL riuniti); gli audit senza
    punteggio numerico (informative, manual, notApplicable, error)
    non generano rilievi. Gravita' dai bucket ufficiali Lighthouse:
    sotto LIGHTHOUSE_PASS_SCORE il rilievo esiste, sotto
    LIGHTHOUSE_CRIT_SCORE con peso >= LIGHTHOUSE_HIGH_WEIGHT e'
    critico, peso 0 e' informativo. ``pillar`` dalla mappatura di
    progetto LIGHTHOUSE_PILLARS (un audit referenziato da piu'
    categorie resta nella prima che lo cita); chiave di catalogo
    ``lh.<categoria>.<audit-id>``. Titoli e description arrivano dal
    LHR, gia' localizzato dal runner (``--locale=it``). Le categorie
    senza alcun audit sotto soglia producono un solo rilievo OK.
    """
    if not data or data.get("status") != "ok":
        return []
    failed: Dict[str, Dict[str, object]] = {}
    order: List[str] = []
    cat_scores: Dict[str, List[float]] = {}
    cat_titles: Dict[str, str] = {}
    cat_titles_en: Dict[str, str] = {}
    cat_titles_msg: Dict[str, str] = {}
    cat_failed: Set[str] = set()
    for res in data.get("results") or []:
        page_url = str(res.get("url") or "")
        lhr = res.get("lhr")
        if not isinstance(lhr, dict):
            continue
        audits = lhr.get("audits")
        if not isinstance(audits, dict):
            audits = {}  # LHR parziale: restano i punteggi di categoria
        categories = lhr.get("categories")
        if not isinstance(categories, dict):
            continue
        reverse = _lh_message_ids(lhr)
        for cat_id, cat in categories.items():
            if not isinstance(cat, dict):
                continue
            cat_titles.setdefault(cat_id,
                                  str(cat.get("title") or cat_id))
            cat_en = _lh_en_text(reverse,
                                 "categories.%s.title" % cat_id)
            if cat_en:
                cat_titles_en.setdefault(cat_id, cat_en)
            cat_msg = reverse.get("categories.%s.title" % cat_id)
            if cat_msg:
                cat_titles_msg.setdefault(cat_id, cat_msg)
            cat_score = cat.get("score")
            if isinstance(cat_score, (int, float)):
                cat_scores.setdefault(cat_id, []).append(
                    float(cat_score))
            for ref in cat.get("auditRefs") or []:
                if not isinstance(ref, dict):
                    continue
                audit_id = str(ref.get("id") or "")
                audit = audits.get(audit_id)
                if not isinstance(audit, dict):
                    continue
                score = audit.get("score")
                if not isinstance(score, (int, float)) \
                        or score >= LIGHTHOUSE_PASS_SCORE:
                    continue
                cat_failed.add(cat_id)
                entry = failed.get(audit_id)
                if entry is None:
                    order.append(audit_id)
                    failed[audit_id] = entry = {
                        "category": cat_id,
                        "score": float(score),
                        "weight": float(ref.get("weight") or 0),
                        "title": str(audit.get("title")
                                     or audit_id),
                        "description": str(
                            audit.get("description") or ""),
                        "display": str(
                            audit.get("displayValue") or ""),
                        "evidence": _lhr_evidence(
                            audit.get("details")),
                        "title_en": _lh_en_text(
                            reverse,
                            "audits[%s].title" % audit_id) or "",
                        "fix_en": _lh_en_text(
                            reverse,
                            "audits[%s].description"
                            % audit_id) or "",
                        "title_msg": reverse.get(
                            "audits[%s].title" % audit_id) or "",
                        "fix_msg": reverse.get(
                            "audits[%s].description"
                            % audit_id) or "",
                        "urls": [],
                    }
                else:
                    entry["score"] = min(entry["score"],
                                         float(score))
                    entry["weight"] = max(
                        entry["weight"],
                        float(ref.get("weight") or 0))
                if page_url and page_url not in entry["urls"]:
                    entry["urls"].append(page_url)

    findings: List[Finding] = []
    for audit_id in order:
        e = failed[audit_id]
        if e["weight"] <= 0:
            severity = SEV_INFO
        elif e["score"] < LIGHTHOUSE_CRIT_SCORE \
                and e["weight"] >= LIGHTHOUSE_HIGH_WEIGHT:
            severity = SEV_CRITICAL
        else:
            severity = SEV_WARNING
        parts: List[str] = []
        if e["display"]:
            parts.append(str(e["display"]))
        if e["urls"]:
            elenco = ", ".join(e["urls"][:3])
            if len(e["urls"]) > 3:
                elenco += " e altre %d" % (len(e["urls"]) - 3)
            parts.append("Pagine: %s" % elenco)
        if e["evidence"]:
            parts.append("Evidenze: %s" % "; ".join(e["evidence"]))
        findings.append(Finding(
            AREA_LIGHTHOUSE, severity,
            "Lighthouse: %s" % e["title"],
            detail="; ".join(parts),
            fix=_strip_md_links(str(e["description"])),
            url=e["urls"][0] if e["urls"] else "",
            weight=2.0 if e["weight"] >= LIGHTHOUSE_HIGH_WEIGHT
            else 1.0,
            pillar=LIGHTHOUSE_PILLARS.get(str(e["category"]),
                                          PILLAR_ACCESS),
            key="lh.%s.%s" % (e["category"], audit_id),
            params={"audit": audit_id,
                    "category": e["category"],
                    "score": round(float(e["score"]), 2),
                    "lh_weight": e["weight"],
                    "urls": ", ".join(e["urls"][:3]),
                    "display": e["display"],
                    "evidence": list(e["evidence"]),
                    "title_en": e["title_en"],
                    "fix_en": e["fix_en"],
                    "title_msg": e["title_msg"],
                    "fix_msg": e["fix_msg"]}))

    for cat_id in sorted(cat_scores):
        if cat_id in cat_failed:
            continue
        scores = cat_scores[cat_id]
        media = round(sum(scores) / len(scores) * 100)
        pagine = "sull'unica pagina esaminata" if len(scores) == 1 \
            else "sulle %d pagine esaminate" % len(scores)
        findings.append(Finding(
            AREA_LIGHTHOUSE, SEV_OK,
            "Lighthouse %s: nessun rilievo" % cat_titles[cat_id],
            "Punteggio %d/100 %s." % (media, pagine),
            pillar=LIGHTHOUSE_PILLARS.get(cat_id, PILLAR_ACCESS),
            key="lh.%s.ok" % cat_id,
            params={"category": cat_id, "score": media,
                    "pages": len(scores),
                    "cat_title_en": cat_titles_en.get(cat_id, ""),
                    "cat_title_msg": cat_titles_msg.get(cat_id,
                                                        "")}))

    errors = data.get("errors") or []
    if errors:
        findings.append(Finding(
            AREA_LIGHTHOUSE, SEV_INFO,
            "Lighthouse non completato su %d %s"
            % (len(errors),
               "pagina" if len(errors) == 1 else "pagine"),
            "; ".join("%s: %s" % (err.get("url", ""),
                                  err.get("error", ""))
                      for err in errors[:5]),
            pillar=PILLAR_ACCESS,
            key="lh.run.errors",
            params={"n": len(errors)}))
    return findings


def merge_lighthouse_findings(findings: Sequence[Finding],
                              lighthouse_data:
                              Optional[Dict[str, object]]
                              ) -> List[Finding]:
    """Fonde i rilievi Lighthouse nella lista MARS con deduplica.

    Regola di progetto (decisione P1): per gli audit in
    LIGHTHOUSE_DEDUP il rilievo MARS resta canonico e la conferma
    Lighthouse viene aggiunta come **evidenza** al suo dettaglio
    (con ``lh_confirm`` nei params, per il badge in GUI); il
    rilievo Lighthouse duplicato non entra in lista. Se MARS non ha
    un rilievo corrispondente — o ha solo un OK: divergenza fra i
    due strumenti — il rilievo Lighthouse resta, perche' porta
    informazione nuova. Gli audit fuori tabella entrano sempre.
    """
    merged = list(findings)
    if not lighthouse_data \
            or lighthouse_data.get("status") != "ok":
        return merged
    for lh in lighthouse_data.get("findings") or []:
        audit_id = str(lh.params.get("audit", ""))
        prefix = LIGHTHOUSE_DEDUP.get(audit_id)
        target = None
        if prefix:
            target = next(
                (f for f in merged
                 if f.key.startswith(prefix)
                 and f.severity != SEV_OK
                 and not f.key.startswith("lh.")), None)
        if target is None:
            merged.append(lh)
            continue
        titolo = lh.title
        if titolo.startswith("Lighthouse: "):
            titolo = titolo[len("Lighthouse: "):]
        nota = "Conferma Lighthouse: %s (punteggio %d/100)." \
            % (titolo, round(float(lh.params.get("score", 0)) * 100))
        target.detail = ("%s %s" % (target.detail, nota)).strip() \
            if target.detail else nota
        target.params["lh_confirm"] = audit_id
    return merged


def lighthouse_area_score(lighthouse_data:
                          Optional[Dict[str, object]]
                          ) -> Optional[float]:
    """Punteggio 0-100 della sesta area (decisione P1).

    Media semplice dei punteggi di categoria del LHR, ognuno
    mediato sulle pagine esaminate: tutte le categorie pesano
    uguale dentro l'area, e' l'area a pesare 1.0 nel complessivo.
    None senza dati (Lighthouse spento o saltato): l'area non
    esiste e i pesi del complessivo si rinormalizzano.
    """
    if not lighthouse_data \
            or lighthouse_data.get("status") != "ok":
        return None
    per_cat: Dict[str, List[float]] = {}
    for res in lighthouse_data.get("results") or []:
        lhr = res.get("lhr")
        if not isinstance(lhr, dict):
            continue
        categories = lhr.get("categories")
        if not isinstance(categories, dict):
            continue
        for cat_id, cat in categories.items():
            score = cat.get("score") if isinstance(cat, dict) \
                else None
            if isinstance(score, (int, float)):
                per_cat.setdefault(cat_id, []).append(float(score))
    if not per_cat:
        return None
    medie = [sum(v) / len(v) for v in per_cat.values()]
    return round(100.0 * sum(medie) / len(medie), 1)


def lighthouse_report_data(lighthouse_data:
                           Optional[Dict[str, object]]
                           ) -> Optional[Dict[str, object]]:
    """Blocco compatto per i referti (chiave JSON ``lighthouse``).

    None con Lighthouse spento: i referti non ne parlano. Con
    status "skipped" porta il **salto dichiarato** (modalita' e
    motivo); con "ok" device, pagine esaminate, tag del fork
    installato, errori per pagina e medie di categoria 0-100.
    Additivo allo schema JSON (``schema_version`` invariato).
    """
    if not lighthouse_data:
        return None
    mode = str(lighthouse_data.get("mode", ""))
    device = str(lighthouse_data.get("device", ""))
    if lighthouse_data.get("status") != "ok":
        return {"status": "skipped", "mode": mode,
                "device": device,
                "reason": str(lighthouse_data.get("reason", ""))}
    per_cat: Dict[str, List[float]] = {}
    titles: Dict[str, str] = {}
    pages_urls: List[str] = []
    for res in lighthouse_data.get("results") or []:
        url = str(res.get("url") or "")
        if url:
            pages_urls.append(url)
        lhr = res.get("lhr")
        if not isinstance(lhr, dict):
            continue
        categories = lhr.get("categories")
        if not isinstance(categories, dict):
            continue
        for cat_id, cat in categories.items():
            if not isinstance(cat, dict):
                continue
            titles.setdefault(cat_id,
                              str(cat.get("title") or cat_id))
            score = cat.get("score")
            if isinstance(score, (int, float)):
                per_cat.setdefault(cat_id, []).append(float(score))
    metrics: List[Dict[str, object]] = []
    for audit_id, label, good, poor in LIGHTHOUSE_CWV:
        worst: Optional[float] = None
        display = ""
        for res in lighthouse_data.get("results") or []:
            lhr = res.get("lhr")
            if not isinstance(lhr, dict):
                continue
            audits = lhr.get("audits")
            audit = audits.get(audit_id) \
                if isinstance(audits, dict) else None
            if not isinstance(audit, dict):
                continue
            value = audit.get("numericValue")
            if not isinstance(value, (int, float)):
                continue
            if worst is None or value > worst:
                worst = float(value)
                display = str(audit.get("displayValue") or "")
        if worst is None:
            continue
        verdict = ("buono" if worst <= good else
                   "da migliorare" if worst <= poor else "scarso")
        metrics.append({"id": audit_id, "label": label,
                        "value": round(worst, 3),
                        "display": display, "verdict": verdict})
    return {"status": "ok", "mode": mode, "device": device,
            "fork": lighthouse_version() or "",
            "pages": pages_urls,
            "errors": [dict(e) for e in
                       lighthouse_data.get("errors") or []],
            "categories": [
                {"id": cat_id,
                 "title": titles.get(cat_id, cat_id),
                 "score": round(100.0 * sum(vals) / len(vals))}
                for cat_id, vals in per_cat.items()],
            # Valore peggiore fra le pagine esaminate: dati lab,
            # non field — la GUI mostra la nota di onesta'.
            "metrics": metrics}


def run_lighthouse(base: str, pages: Sequence[Page],
                   mode: str = LIGHTHOUSE_OFF,
                   n_pages: int = DEFAULT_LIGHTHOUSE_PAGES,
                   device: str = LIGHTHOUSE_DEVICE_MOBILE,
                   delay: float = 0.5, verbose: bool = False,
                   stop_event: Optional["threading.Event"] = None,
                   timeout_s: float = LIGHTHOUSE_TIMEOUT_S
                   ) -> Optional[Dict[str, object]]:
    """Audit Lighthouse sulle pagine rappresentative del sito.

    Passo separato dopo ``run_audit()``, come il giudizio LLM:
    restituisce None con mode=off, altrimenti un dict con status
    "ok" (LHR per pagina piu' gli eventuali errori per pagina) o
    "skipped" (motivo dichiarato: requisiti assenti in modalita'
    auto — 'always' viene bloccato a monte). Un processo Node per
    pagina (``--output=json``), pausa ``delay`` fra le pagine,
    timeout e annullamento cooperativo con kill del processo. Gli
    errori di una pagina non fermano mai le altre ne' l'audit.
    """
    if mode == LIGHTHOUSE_OFF:
        return None
    reason = lighthouse_unavailable()
    if reason:
        if verbose:
            print("Lighthouse: saltato - %s" % reason,
                  file=sys.stderr)
        return {"status": "skipped", "mode": mode,
                "device": device, "reason": reason}
    urls = select_lighthouse_pages(base, pages, n_pages)
    if not urls:
        if verbose:
            print("Lighthouse: saltato - nessuna pagina analizzabile",
                  file=sys.stderr)
        return {"status": "skipped", "mode": mode, "device": device,
                "reason": "nessuna pagina analizzabile"}
    node = shutil.which("node")
    chrome = find_system_chrome()
    if verbose:
        print("Lighthouse: %d pagine (%s), timeout %d s a pagina"
              % (len(urls), device, timeout_s), file=sys.stderr)
    results: List[Dict[str, object]] = []
    errors: List[Dict[str, str]] = []
    for i, url in enumerate(urls):
        if i and delay > 0:
            if stop_event is not None:
                if stop_event.wait(delay):
                    raise AuditCancelled()
            else:
                time.sleep(delay)
        lhr, error = _lighthouse_page(url, device, node, chrome,
                                      timeout_s, stop_event)
        if error is not None:
            errors.append({"url": url, "error": error})
            if verbose:
                print("  ! Lighthouse %d/%d %s: %s"
                      % (i + 1, len(urls), url, error),
                      file=sys.stderr)
            continue
        results.append({"url": url, "lhr": lhr})
        if verbose:
            cats = lhr.get("categories", {}) \
                if isinstance(lhr, dict) else {}
            summary = ", ".join(
                "%s %d" % (key, round((cat.get("score") or 0) * 100))
                for key, cat in cats.items()) or "nessuna categoria"
            print("  Lighthouse %d/%d %s: %s"
                  % (i + 1, len(urls), url, summary),
                  file=sys.stderr)
    data: Dict[str, object] = {
        "status": "ok", "mode": mode, "device": device,
        "results": results, "errors": errors}
    data["findings"] = lighthouse_findings(data)
    if verbose:
        rilievi = data["findings"]
        print("Lighthouse: %d rilievi (%d critici, %d avvertenze)"
              % (len(rilievi),
                 sum(1 for f in rilievi
                     if f.severity == SEV_CRITICAL),
                 sum(1 for f in rilievi
                     if f.severity == SEV_WARNING)),
              file=sys.stderr)
    return data


def _audit_link_graph(pages: List[Page], base: str) -> List[Finding]:
    """Pagine orfane, profondita' di click e anchor generiche."""
    good = [p for p in pages if p.ok]
    if len(good) < 2:
        return []

    edges, incoming = _build_link_edges(good)

    out: List[Finding] = []
    home = norm_url(base)
    orphans = sorted(u for u in edges
                     if u != home and not incoming[u])
    if orphans:
        out.append(Finding(
            AREA_TECH, SEV_WARNING,
            "%d pagina/e senza link interni in ingresso (orfane)"
            % len(orphans),
            "Raggiungibili solo dalla sitemap: %s. Una pagina che "
            "nessuno linka riceve meno scansioni e meno peso."
            % ", ".join(orphans[:5]),
            "Linkale dalle pagine correlate (testo, menu o footer).",
            key="tech.links.orphans",
            params={"n": len(orphans),
                    "urls": ", ".join(orphans[:5])},
            example="Dalla pagina correlata:\n"
                    "<a href=\"/servizio-collegato/\">nome "
                    "descrittivo del servizio</a>"))
    else:
        out.append(Finding(
            AREA_TECH, SEV_OK,
            "Tutte le pagine hanno link interni in ingresso",
            key="tech.links.no_orphans"))

    if home in edges:
        depth = _bfs_depths(edges, home)
        deep = sorted(u for u, d in depth.items() if d > 3)
        if deep:
            out.append(Finding(
                AREA_TECH, SEV_WARNING,
                "%d pagina/e oltre 3 click dalla home" % len(deep),
                ", ".join(deep[:5]) + ".",
                "Accorcia i percorsi: le pagine profonde vengono "
                "scansionate e pesate meno.",
                key="tech.links.deep",
                params={"n": len(deep),
                        "urls": ", ".join(deep[:5])}))

    generic = sum(p.generic_anchors for p in good)
    if generic:
        out.append(Finding(
            AREA_TECH, SEV_INFO,
            "%d anchor generiche nei link interni" % generic,
            "Testi come \"clicca qui\" o \"leggi di piu'\" non "
            "dicono nulla sul contenuto di arrivo.",
            "Usa anchor descrittive con i termini della pagina "
            "di destinazione.",
            key="tech.links.generic_anchors",
            params={"n": generic}))
    return out


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
            "definitivi.", pillar=PILLAR_SEC,
            key="tech.redirect.http_left",
            params={"n": len(http_to_https),
                    "urls": ", ".join(
                        p.url for p in http_to_https[:5])},
            example="<!-- prima --> <a href=\"http://esempio.it/"
                    "servizio/\">\n<!-- dopo  --> "
                    "<a href=\"https://esempio.it/servizio/\">"))
    if www_mismatch:
        out.append(Finding(
            AREA_TECH, SEV_WARNING,
            "%d URL con host misto www/non-www" % len(www_mismatch),
            "Reindirizzati all'host canonico: %s."
            % ", ".join("%s -> %s" % (p.url, p.final_url)
                        for p in www_mismatch[:5]),
            "Usa un solo host (con o senza www) in sitemap e link "
            "interni.", key="tech.redirect.www_mixed",
            params={"n": len(www_mismatch),
                    "urls": ", ".join(
                        "%s -> %s" % (p.url, p.final_url)
                        for p in www_mismatch[:5])}))
    if moved:
        out.append(Finding(
            AREA_TECH, SEV_WARNING,
            "%d URL interni rispondono con redirect" % len(moved),
            "URL spostati: %s."
            % ", ".join("%s -> %s" % (p.url, p.final_url)
                        for p in moved[:5]),
            "Aggiorna sitemap e link interni alla destinazione "
            "finale dei redirect.",
            key="tech.redirect.moved",
            params={"n": len(moved),
                    "urls": ", ".join(
                        "%s -> %s" % (p.url, p.final_url)
                        for p in moved[:5])},
            example="Nella sitemap e nei link interni usa gia' "
                    "l'URL di arrivo:\n<url><loc>https://esempio.it/"
                    "nuova-pagina/</loc></url>"))
    chains = [p for p in pages if p.redirects > 1]
    if chains:
        out.append(Finding(
            AREA_TECH, SEV_WARNING,
            "%d URL con catena di redirect multipla" % len(chains),
            ", ".join("%s (%d passaggi)" % (p.url, p.redirects)
                      for p in chains[:5]) + ".",
            "Fai puntare ogni redirect direttamente alla "
            "destinazione finale (un solo passaggio).", weight=2.0,
            key="tech.redirect.chains",
            params={"n": len(chains),
                    "urls": ", ".join(
                        "%s (%d)" % (p.url, p.redirects)
                        for p in chains[:5])},
            example="# un solo salto, non a catena\n"
                    "Redirect 301 /vecchia/ "
                    "https://esempio.it/nuova/\n"
                    "# NON: /vecchia/ -> /intermedia/ -> /nuova/"))
    if not (http_to_https or www_mismatch or moved):
        out.append(Finding(
            AREA_TECH, SEV_OK, "Nessun redirect interno",
            "Tutti gli URL analizzati rispondono direttamente.",
            key="tech.redirect.none"))
    return out


def _audit_msft_ai_optout(pages: Sequence[Page]) -> List[Finding]:
    """Opt-out dall'IA di Microsoft: meta noarchive/nocache.

    Microsoft non ha un token robots.txt dedicato all'IA (Bingbot
    e' il crawler della ricerca classica): l'uso dei contenuti in
    Bing Chat/Copilot e nel training dei modelli generativi si
    governa coi meta robots. NOARCHIVE esclude dalle risposte e
    dal training; NOCACHE limita a URL, titolo e snippet (mostrati
    nelle risposte e usati per il training); il meta scoped
    <meta name="bingbot"> prevale per Bing su quello generico;
    nessuno dei due tocca la ricerca classica. Fonte: Bing Blogs,
    settembre 2023, "Announcing new options for webmasters to
    control usage of their content in Bing Chat".
    """
    good = [p for p in pages if p.ok]
    if not good:
        return []
    noarchive: List[str] = []
    nocache: List[str] = []
    for p in good:
        # Per Bing il meta bingbot, se presente, prevale su robots.
        combined = (p.bingbot_meta or p.meta_robots or "").lower()
        if "noarchive" in combined:
            noarchive.append(p.url)
        elif "nocache" in combined:
            nocache.append(p.url)

    out: List[Finding] = []
    if noarchive:
        out.append(Finding(
            AREA_TECH, SEV_WARNING,
            "%d pagina/e escluse da Copilot (noarchive)"
            % len(noarchive),
            "Il meta noarchive esclude il contenuto dalle risposte "
            "di Bing Chat/Copilot e dal training dei modelli "
            "Microsoft (la ricerca classica non cambia): su queste "
            "pagine la citabilita' sul canale Microsoft e' zero. "
            "%s" % ", ".join(sorted(noarchive)[:5]),
            "Se l'esclusione non e' voluta rimuovi noarchive; per "
            "una presenza parziale (solo titolo, URL e snippet) "
            "usa nocache.",
            example="<meta name=\"bingbot\" content=\"nocache\">",
            weight=2.0, pillar=PILLAR_SEC,
            key="tech.msft.noarchive",
            params={"n": len(noarchive),
                    "urls": ", ".join(sorted(noarchive)[:5])}))
    if nocache:
        out.append(Finding(
            AREA_TECH, SEV_INFO,
            "%d pagina/e con presenza parziale in Copilot "
            "(nocache)" % len(nocache),
            "Con nocache Bing Chat/Copilot mostra solo URL, titolo "
            "e snippet della pagina e usa solo quegli elementi per "
            "il training Microsoft. %s"
            % ", ".join(sorted(nocache)[:5]),
            "Scelta legittima di opt-out parziale: verifica solo "
            "che sia voluta. Per la piena citabilita' su Copilot "
            "rimuovi il meta.", pillar=PILLAR_SEC,
            key="tech.msft.nocache",
            params={"n": len(nocache),
                    "urls": ", ".join(sorted(nocache)[:5])}))
    if not noarchive and not nocache:
        out.append(Finding(
            AREA_TECH, SEV_OK,
            "Nessun opt-out IA di Microsoft attivo",
            "Non esiste un token robots.txt dedicato all'IA di "
            "Microsoft: il controllo passa dai meta "
            "noarchive/nocache, qui assenti. I contenuti sono "
            "quindi utilizzabili nelle risposte di Copilot e nel "
            "training Microsoft; per l'opt-out usa noarchive "
            "(totale) o nocache (parziale).", pillar=PILLAR_SEC,
            key="tech.msft.no_optout"))
    return out


def _audit_anchor_variety(good: Sequence[Page]) -> List[Finding]:
    """Varieta' del profilo di anchor interni (da Features.md).

    Estende il controllo sulle anchor generiche: le coppie (testo,
    destinazione) vengono deduplicate sull'intero sito (il menu
    identico su ogni pagina conta una volta), poi la varieta' e'
    testi unici / coppie uniche. Sotto ANCHOR_VARIETY_GOOD lo
    stesso testo punta a piu' destinazioni: chi legge (umano o
    modello) non puo' prevedere dove porta il link. Sotto
    ANCHOR_MIN_PAIRS coppie non si giudica.
    """
    pairs: Set[Tuple[str, str]] = set()
    for p in good:
        pairs.update(p.internal_anchors)
    if len(pairs) < ANCHOR_MIN_PAIRS:
        return []
    by_text: Dict[str, Set[str]] = {}
    for text, target in pairs:
        by_text.setdefault(text, set()).add(target)
    ratio = len(by_text) / len(pairs)
    if ratio >= ANCHOR_VARIETY_GOOD:
        return [Finding(
            AREA_TECH, SEV_OK,
            "Profilo di anchor interni vario",
            "%d testi unici su %d coppie testo-destinazione "
            "(%.0f%%; soglia di prassi: %.0f%%)."
            % (len(by_text), len(pairs), 100 * ratio,
               100 * ANCHOR_VARIETY_GOOD),
            key="tech.anchors.varied",
            params={"texts": len(by_text), "pairs": len(pairs),
                    "pct": 100 * ratio,
                    "threshold": 100 * ANCHOR_VARIETY_GOOD})]
    ambigui = sorted(
        ((text, targets) for text, targets in by_text.items()
         if len(targets) > 1),
        key=lambda item: -len(item[1]))[:3]
    return [Finding(
        AREA_TECH, SEV_WARNING,
        "Profilo di anchor interni ripetitivo",
        "%d testi unici su %d coppie testo-destinazione (%.0f%%, "
        "soglia di prassi %.0f%%): lo stesso testo porta a "
        "destinazioni diverse e chi legge — umano o modello — non "
        "puo' prevedere dove va il link. %s"
        % (len(by_text), len(pairs), 100 * ratio,
           100 * ANCHOR_VARIETY_GOOD,
           "; ".join("\"%s\" -> %d destinazioni"
                     % (text, len(targets))
                     for text, targets in ambigui)),
        "Usa anchor descrittivi e distinti per destinazione: il "
        "testo del link deve dire cosa si trova dall'altra parte.",
        example="Prima: \"Leggi tutto\" -> /servizi, \"Leggi "
                "tutto\" -> /prezzi\n"
                "Dopo:  \"Tutti i servizi di drenaggio\" -> "
                "/servizi, \"Prezzi delle sedute\" -> /prezzi",
        weight=1.0, key="tech.anchors.repetitive",
        params={"texts": len(by_text), "pairs": len(pairs),
                "pct": 100 * ratio,
                "threshold": 100 * ANCHOR_VARIETY_GOOD,
                "examples": "; ".join(
                    "\"%s\" -> %d destinazioni"
                    % (text, len(targets))
                    for text, targets in ambigui)})]


OG_CORE = ("og:title", "og:description", "og:image")


def _audit_basic_meta(good: Sequence[Page]) -> List[Finding]:
    """Meta di base: charset, viewport e completezza Open Graph.

    Gli og:* sono estratti fin dalla v1.0 ma non erano mai stati
    valutati (da Features.md). La triade minima per le anteprime
    nei link condivisi e nelle risposte degli assistenti e'
    og:title, og:description, og:image; charset e viewport sono
    igiene tecnica di base (resa dei caratteri e mobile).
    """
    out: List[Finding] = []
    no_charset = [p.url for p in good if not p.has_charset]
    if no_charset:
        out.append(Finding(
            AREA_TECH, SEV_WARNING,
            "%d pagina/e senza charset dichiarato"
            % len(no_charset),
            ", ".join(sorted(no_charset)[:5]),
            "Dichiara la codifica in testa all'<head>.",
            key="tech.meta.charset",
            params={"n": len(no_charset),
                    "urls": ", ".join(sorted(no_charset)[:5])},
            example="<meta charset=\"utf-8\">"))
    no_viewport = [p.url for p in good if not p.has_viewport]
    if no_viewport:
        out.append(Finding(
            AREA_TECH, SEV_WARNING,
            "%d pagina/e senza meta viewport" % len(no_viewport),
            "Senza viewport la resa mobile non e' dichiarata: %s"
            % ", ".join(sorted(no_viewport)[:5]),
            "Aggiungi il viewport responsive.",
            key="tech.meta.viewport",
            params={"n": len(no_viewport),
                    "urls": ", ".join(sorted(no_viewport)[:5])},
            example="<meta name=\"viewport\" "
                    "content=\"width=device-width, "
                    "initial-scale=1\">"))
    no_og = [p.url for p in good if not p.og]
    partial: List[str] = []
    for p in good:
        if p.og:
            missing = [k for k in OG_CORE if not p.og.get(k)]
            if missing:
                partial.append("%s (manca %s)"
                               % (p.url, ", ".join(missing)))
    if no_og:
        out.append(Finding(
            AREA_TECH, SEV_WARNING,
            "%d pagina/e senza Open Graph" % len(no_og),
            "Le anteprime nei link condivisi (e in molte risposte "
            "degli assistenti) si costruiscono dagli og:*: senza, "
            "titolo e immagine li decide chi incolla il link. %s"
            % ", ".join(sorted(no_og)[:5]),
            "Aggiungi almeno la triade og:title, og:description, "
            "og:image.", key="tech.meta.og_missing",
            params={"n": len(no_og),
                    "urls": ", ".join(sorted(no_og)[:5])},
            example="<meta property=\"og:title\" "
                    "content=\"Drenaggio linfatico a Parma\">\n"
                    "<meta property=\"og:description\" "
                    "content=\"Sedute da 45 minuti con "
                    "fisioterapisti certificati.\">\n"
                    "<meta property=\"og:image\" "
                    "content=\"https://esempio.it/img/"
                    "studio.jpg\">"))
    if partial:
        out.append(Finding(
            AREA_TECH, SEV_WARNING,
            "Open Graph incompleto su %d pagina/e" % len(partial),
            "; ".join(partial[:5]),
            "Completa la triade og:title, og:description, "
            "og:image.", key="tech.meta.og_partial",
            params={"n": len(partial),
                    "urls": "; ".join(partial[:5])}))
    if not out and good:
        out.append(Finding(
            AREA_TECH, SEV_OK,
            "Meta di base a posto",
            "charset, viewport e Open Graph completi su tutte le "
            "%d pagine analizzate." % len(good),
            key="tech.meta.ok", params={"n": len(good)}))
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
            url=base, weight=2.0, pillar=PILLAR_SEC,
            key="tech.https.missing",
            example="# nginx\nreturn 301 https://$host$request_uri;\n"
                    "# Apache (.htaccess)\nRewriteEngine On\n"
                    "RewriteCond %{HTTPS} off\n"
                    "RewriteRule ^ https://%{HTTP_HOST}%{REQUEST_URI} "
                    "[L,R=301]"))
    else:
        out.append(Finding(AREA_TECH, SEV_OK, "HTTPS attivo",
                           url=base, pillar=PILLAR_SEC,
                           key="tech.https.ok"))

    broken = [p for p in pages if not p.ok]
    if broken:
        out.append(Finding(
            AREA_TECH, SEV_CRITICAL,
            "%d URL non raggiungibili o in errore" % len(broken),
            ", ".join("%s (%s)" % (p.url, p.status or p.error)
                      for p in broken[:5]),
            "Correggi o rimuovi dalla sitemap gli URL in errore.",
            key="tech.pages.broken",
            params={"n": len(broken),
                    "urls": ", ".join(
                        "%s (%s)" % (p.url, p.status or p.error)
                        for p in broken[:5])}))

    out.extend(_audit_redirects(pages))
    out.extend(_audit_link_graph(pages, base))

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
            "togli quelli vuoti dalla sitemap.", weight=2.0,
            key="tech.pages.soft404",
            params={"n": len(soft404),
                    "urls": ", ".join(p.url for p in soft404[:5])},
            example="La pagina inesistente deve rispondere con "
                    "stato 404, non 200:\n"
                    "# Apache (.htaccess)\n"
                    "ErrorDocument 404 /404.html\n"
                    "# niente redirect alla home al posto del 404"))

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
            weight=3.0, key="tech.pages.none"))
    elif n_pages == 1:
        out.append(Finding(
            AREA_TECH, SEV_CRITICAL,
            "Superficie indicizzabile minima (1 pagina)",
            "Con un solo documento la somma RRF non ha addendi: non "
            "esistono passaggi distinti da far emergere.",
            "Crea pagine autonome per ogni tema/servizio.",
            weight=3.0, key="tech.pages.single"))
    elif n_pages < 5:
        out.append(Finding(
            AREA_TECH, SEV_WARNING,
            "Poche pagine indicizzabili (%d)" % n_pages,
            fix="Amplia la superficie: una pagina per intento.",
            weight=2.0, key="tech.pages.few",
            params={"n": n_pages}))
    else:
        out.append(Finding(
            AREA_TECH, SEV_OK,
            "%d pagine indicizzabili analizzate" % n_pages,
            "%s%s." % (", ".join(p.url for p in good[:5]),
                       " e altre %d" % (n_pages - 5)
                       if n_pages > 5 else ""),
            key="tech.pages.ok",
            params={"n": n_pages,
                    "urls": ", ".join(p.url for p in good[:5]),
                    "more": max(0, n_pages - 5)}))

    if not from_sitemap:
        out.append(Finding(
            AREA_TECH, SEV_WARNING, "Sitemap XML assente o illeggibile",
            "URL individuati tramite crawling dei link interni.",
            "Pubblica una sitemap XML e dichiarala nel robots.txt.",
            key="tech.sitemap.missing",
            example="<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
                    "<urlset xmlns=\"http://www.sitemaps.org/schemas/"
                    "sitemap/0.9\">\n<url><loc>https://esempio.it/"
                    "</loc><lastmod>2026-08-03</lastmod></url>\n"
                    "</urlset>"))

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
            "sitemap.", weight=2.0, key="tech.pages.placeholder",
            params={"n": len(placeholders),
                    "urls": ", ".join(
                        p.url for p in placeholders[:5])}))

    noindex = [p for p in good
               if "noindex" in (p.meta_robots or "").lower()]
    if noindex:
        out.append(Finding(
            AREA_TECH, SEV_WARNING,
            "%d pagina/e con meta robots noindex" % len(noindex),
            ", ".join(p.url for p in noindex[:5]),
            "Verifica che l'esclusione sia voluta.",
            key="tech.pages.noindex",
            params={"n": len(noindex),
                    "urls": ", ".join(p.url for p in noindex[:5])},
            example="Se la pagina deve essere indicizzata, rimuovi "
                    "il meta o usa:\n<meta name=\"robots\" "
                    "content=\"index, follow\">"))

    out.extend(_audit_msft_ai_optout(good))
    out.extend(_audit_basic_meta(good))
    out.extend(_audit_anchor_variety(good))

    no_canonical = [p for p in good if not p.canonical]
    if no_canonical:
        out.append(Finding(
            AREA_TECH, SEV_WARNING,
            "%d pagina/e senza canonical" % len(no_canonical),
            ", ".join(p.url for p in no_canonical[:5]),
            "Dichiara <link rel=\"canonical\"> su ogni pagina.",
            key="tech.canonical.missing",
            params={"n": len(no_canonical),
                    "urls": ", ".join(
                        p.url for p in no_canonical[:5])},
            example="<link rel=\"canonical\" "
                    "href=\"https://esempio.it/servizio/\">"))
    elif good:
        out.append(Finding(
            AREA_TECH, SEV_OK, "Canonical presenti",
            "Dichiarato su tutte le %d pagine analizzate."
            % len(good),
            key="tech.canonical.ok", params={"n": len(good)}))

    no_lang = [p for p in good if not p.lang]
    if no_lang:
        out.append(Finding(
            AREA_TECH, SEV_WARNING,
            "%d pagina/e senza attributo lang" % len(no_lang),
            fix="Imposta <html lang=\"it\">: aiuta la selezione del "
                "modello linguistico in fase di analisi.",
            key="tech.lang.missing", params={"n": len(no_lang)}))

    js_heavy = [p for p in good
                if p.raw_js_heavy or is_js_heavy(p)]
    if js_heavy:
        rendered_any = any(p.rendered for p in js_heavy)
        detail = ("Il contenuto potrebbe essere reso lato client e "
                  "non essere visto dai crawler.")
        if rendered_any:
            detail = ("Il contenuto e' stato analizzato col "
                      "rendering JavaScript, ma i crawler che non "
                      "eseguono JavaScript (la maggior parte di "
                      "quelli IA) continuano a non vederlo.")
        out.append(Finding(
            AREA_TECH, SEV_CRITICAL,
            "%d pagina/e con testo scarso e molto JavaScript"
            % len(js_heavy), detail,
            "Attiva rendering server-side o pre-rendering.",
            weight=2.0,
            key=("tech.js.rendered" if rendered_any
                 else "tech.js.heavy"),
            params={"n": len(js_heavy)}))
    elif good:
        out.append(Finding(
            AREA_TECH, SEV_OK,
            "Contenuto presente nell'HTML iniziale",
            key="tech.js.ok"))

    slow = [p for p in good if p.elapsed > 2.0]
    if slow:
        out.append(Finding(
            AREA_TECH, SEV_WARNING,
            "%d pagina/e con risposta oltre 2 s" % len(slow),
            "Piu' lenta: %.2f s." % max(p.elapsed for p in slow),
            "Ottimizza cache e TTFB.",
            key="tech.slow",
            params={"n": len(slow),
                    "worst": max(p.elapsed for p in slow)}))

    langs = {p.lang.split("-")[0] for p in good if p.lang}
    multilingual = len(langs) > 1
    has_hreflang = any(p.hreflang for p in good)
    if multilingual and not has_hreflang:
        out.append(Finding(
            AREA_TECH, SEV_WARNING,
            "Sito multilingua senza hreflang",
            "Lingue rilevate: %s." % ", ".join(sorted(langs)),
            "Dichiara hreflang reciproci fra le versioni.",
            key="tech.hreflang.missing",
            params={"langs": ", ".join(sorted(langs))},
            example="<link rel=\"alternate\" hreflang=\"it\" "
                    "href=\"https://esempio.it/it/\">\n"
                    "<link rel=\"alternate\" hreflang=\"en\" "
                    "href=\"https://esempio.it/en/\">"))
    elif not multilingual:
        out.append(Finding(
            AREA_TECH, SEV_INFO, "Sito monolingua: hreflang non "
            "necessario", key="tech.hreflang.na"))
    return out


def _audit_clickbait(good: Sequence[Page]) -> List[Finding]:
    """Formule clickbait in title e H1-H3 (da Features.md).

    Un titolo sensazionalistico attira il click umano ma non dice
    nulla di estraibile: i motori generativi selezionano passaggi
    che rispondono, e "Non crederai a cosa..." non risponde a
    niente. Euristica dichiarata; scandisce solo title e heading
    (non il corpo) per contenere i falsi positivi.
    """
    colpiti: List[str] = []
    for p in good:
        sources = [("title", p.title)] + \
            [("h%d" % lvl, txt) for lvl, txt in p.headings
             if lvl <= 3]
        for origin, text in sources:
            if text and CLICKBAIT_RE.search(text):
                colpiti.append("%s (%s: \"%s\")"
                               % (p.url, origin, text[:60]))
    if colpiti:
        return [Finding(
            AREA_LEX, SEV_WARNING,
            "%d titoli o heading con formule clickbait"
            % len(colpiti),
            "Formule sensazionalistiche ed esclamazioni multiple "
            "attirano il click ma non rispondono a niente: i "
            "motori generativi selezionano titoli informativi. %s"
            % "; ".join(colpiti[:5]),
            "Riformula in stile informativo: il beneficio o la "
            "risposta nel titolo, senza iperboli.",
            key="lex.clickbait.found",
            params={"n": len(colpiti),
                    "examples": "; ".join(colpiti[:5])},
            example="Prima: \"Non crederai a cosa fa il "
                    "drenaggio!!\"\n"
                    "Dopo:  \"Drenaggio linfatico: benefici, "
                    "durata e costi di una seduta\"",
            weight=1.5)]
    return [Finding(
        AREA_LEX, SEV_OK,
        "Nessuna formula clickbait in title e heading",
        "Titoli in stile informativo su tutte le %d pagine "
        "analizzate." % len(good),
        key="lex.clickbait.none", params={"n": len(good)})]


def audit_lexical(pages: List[Page]) -> List[Finding]:
    """Segnali che alimentano il recuperatore lessicale (BM25)."""
    out: List[Finding] = []
    good = [p for p in pages if p.ok]
    if not good:
        return out

    out.extend(_audit_clickbait(good))

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
            weight=2.0, key="lex.title.missing",
            params={"n": len(missing_title)}))
    if bad_title:
        out.append(Finding(
            AREA_LEX, SEV_CRITICAL,
            "%d title non ottimizzati" % len(bad_title),
            "Esempi: %s" % " | ".join(
                "%r (%d car.)" % (p.title, len(p.title))
                for p in bad_title[:3]),
            "Title unico, %d-%d caratteri, con i termini di ricerca "
            "reali; evita il nome dominio come titolo."
            % (TITLE_MIN, TITLE_MAX), weight=2.0,
            key="lex.title.bad",
            params={"n": len(bad_title),
                    "min": TITLE_MIN, "max": TITLE_MAX,
                    "examples": " | ".join(
                        "%r (%d car.)" % (p.title, len(p.title))
                        for p in bad_title[:3])},
            example="<title>Drenaggio linfatico manuale a Parma | "
                    "Centro Esempio</title>\n"
                    "(52 caratteri: servizio + territorio + brand)"))
    if dup_title:
        out.append(Finding(
            AREA_LEX, SEV_WARNING,
            "%d title duplicati fra pagine" % len(dup_title),
            "; ".join(dup_title[:3]),
            "Ogni pagina deve avere un title distinto.",
            key="lex.title.dup",
            params={"n": len(dup_title),
                    "examples": "; ".join(dup_title[:3])}))
    if not (missing_title or bad_title or dup_title):
        out.append(Finding(AREA_LEX, SEV_OK, "Title ben impostati",
                           key="lex.title.ok"))

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
            ", ".join(p.url for p in no_desc[:5]),
            "Scrivi %d-%d caratteri con servizio e territorio."
            % (DESC_MIN, DESC_MAX),
            weight=1.5, key="lex.desc.missing",
            params={"n": len(no_desc),
                    "min": DESC_MIN, "max": DESC_MAX,
                    "urls": ", ".join(p.url for p in no_desc[:5])},
            example="<meta name=\"description\" content=\"Drenaggio "
                    "linfatico manuale a Parma:\nsedute da 45 minuti "
                    "con fisioterapisti certificati, percorsi "
                    "post-operatori\ne prima valutazione "
                    "gratuita.\">"))
    if weak_desc:
        out.append(Finding(
            AREA_LEX, SEV_WARNING,
            "%d meta description troppo corte" % len(weak_desc),
            "Esempi: %s" % " | ".join(
                repr(p.description) for p in weak_desc[:3]),
            "Una description che ripete solo il nome dell'azienda non "
            "porta alcun segnale.",
            key="lex.desc.short",
            params={"n": len(weak_desc),
                    "examples": " | ".join(
                        repr(p.description)
                        for p in weak_desc[:3])}))
    if long_desc:
        out.append(Finding(
            AREA_LEX, SEV_INFO,
            "%d meta description oltre %d caratteri"
            % (len(long_desc), DESC_MAX),
            key="lex.desc.long",
            params={"n": len(long_desc), "max": DESC_MAX}))
    if not (no_desc or weak_desc):
        out.append(Finding(
            AREA_LEX, SEV_OK, "Meta description presenti e di lunghezza "
            "adeguata", key="lex.desc.ok"))

    no_h1 = [p for p in good
             if not any(lv == 1 for lv, _ in p.headings)]
    multi_h1 = [p for p in good
                if sum(1 for lv, _ in p.headings if lv == 1) > 1]
    if no_h1:
        out.append(Finding(
            AREA_LEX, SEV_CRITICAL, "%d pagina/e senza H1" % len(no_h1),
            ", ".join(p.url for p in no_h1[:5]),
            "Un solo H1 per pagina, con i termini principali.",
            weight=1.5, key="lex.h1.missing",
            params={"n": len(no_h1),
                    "urls": ", ".join(p.url for p in no_h1[:5])},
            example="<h1>Drenaggio linfatico manuale: cos'e' e "
                    "come funziona</h1>"))
    if multi_h1:
        out.append(Finding(
            AREA_LEX, SEV_WARNING,
            "%d pagina/e con piu' H1" % len(multi_h1),
            key="lex.h1.multi", params={"n": len(multi_h1)}))
    if not (no_h1 or multi_h1):
        out.append(Finding(AREA_LEX, SEV_OK, "Struttura H1 corretta",
                           key="lex.h1.ok"))

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
            weight=2.0, key="lex.words.thin",
            params={"n": len(thin), "min": THIN_CONTENT_WORDS,
                    "avg": sum(p.word_count for p in good)
                    // len(good),
                    "target": GOOD_CONTENT_WORDS},
            example="Struttura tipo per una pagina servizio:\n"
                    "<h2>Cos'e' ...?</h2> <h2>Come funziona una "
                    "seduta</h2>\n<h2>Quando serve</h2> <h2>Quanto "
                    "costa</h2> <h2>Domande frequenti</h2>"))
    else:
        out.append(Finding(
            AREA_LEX, SEV_OK, "Volume di testo adeguato",
            "Media: %d parole per pagina."
            % (sum(p.word_count for p in good) / len(good)),
            key="lex.words.ok",
            params={"avg": sum(p.word_count for p in good)
                    // len(good)}))

    acronyms = find_acronyms(good)
    expanded = {a for a, ok_ in acronyms.items() if ok_}
    if acronyms and len(expanded) < len(acronyms) / 2:
        out.append(Finding(
            AREA_LEX, SEV_WARNING,
            "Sigle usate senza forma estesa",
            "Non esplicitate: %s." % ", ".join(
                sorted(set(acronyms) - expanded)[:8]),
            "Scrivi 'SIGLA (forma estesa)' almeno alla prima "
            "occorrenza: copre entrambe le formulazioni di ricerca.",
            key="lex.acronyms.bare",
            params={"list": ", ".join(
                sorted(set(acronyms) - expanded)[:8])}))
    elif acronyms:
        out.append(Finding(
            AREA_LEX, SEV_OK,
            "Sigle accompagnate dalla forma estesa",
            ", ".join(sorted(expanded)[:8]),
            key="lex.acronyms.ok",
            params={"list": ", ".join(sorted(expanded)[:8])}))

    bad_slug = [p for p in good if re.search(r"[_%]|\d{4,}", p.slug)]
    if bad_slug:
        out.append(Finding(
            AREA_LEX, SEV_WARNING,
            "%d slug poco parlanti" % len(bad_slug),
            ", ".join(p.slug for p in bad_slug[:5]),
            "Usa slug tematici con trattini.",
            key="lex.slug.bad",
            params={"n": len(bad_slug),
                    "slugs": ", ".join(
                        p.slug for p in bad_slug[:5])}))
    else:
        out.append(Finding(AREA_LEX, SEV_OK, "Slug tematici e leggibili",
                           key="lex.slug.ok"))

    total_img = sum(p.images for p in good)
    with_alt = sum(p.images_with_alt for p in good)
    if total_img and with_alt / total_img < 0.8:
        out.append(Finding(
            AREA_LEX, SEV_WARNING,
            "Attributi alt incompleti (%d/%d)" % (with_alt, total_img),
            fix="L'alt e' testo indicizzabile oltre che accessibilita'.",
            key="lex.alt.partial",
            params={"with_alt": with_alt, "total": total_img},
            example="<img src=\"seduta.jpg\" alt=\"fisioterapista "
                    "esegue drenaggio linfatico\nmanuale sulla gamba "
                    "di una paziente\">"))
    elif total_img:
        out.append(Finding(
            AREA_LEX, SEV_OK,
            "Attributi alt presenti (%d/%d)" % (with_alt, total_img),
            key="lex.alt.ok",
            params={"with_alt": with_alt, "total": total_img}))
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


def _audit_extractability(good: Sequence[Page]) -> List[Finding]:
    """Estraibilita' diretta: paragrafi citabili cosi' come sono.

    Numeratore: paragrafi di EXTRACT_MIN-EXTRACT_MAX parole che
    aprono con una risposta esplicita (DIRECT_ANSWER_RE) o con una
    definizione nelle prime battute (DEFINITION_RE). Denominatore:
    i paragrafi sostanziosi (>= 10 parole), per non farsi gonfiare
    il conto dal boilerplate. Metrica da Features.md, innestata
    nell'area semantica (alimenta la lente Claude dei profili di
    citabilita').
    """
    substantial = [par for p in good for par in p.paragraphs
                   if len(par.split()) >= 10]
    if not substantial:
        return []
    direct = 0
    for par in substantial:
        words = len(par.split())
        if not EXTRACT_MIN_WORDS <= words <= EXTRACT_MAX_WORDS:
            continue
        if DIRECT_ANSWER_RE.search(par) \
                or DEFINITION_RE.search(par[:90]):
            direct += 1
    share = direct / len(substantial)
    detail = ("%d paragrafi su %d aprono con una risposta "
              "esplicita in %d-%d parole (%.0f%% contro una "
              "soglia di prassi del %.0f%%): sono i passaggi che "
              "un assistente puo' citare cosi' come sono."
              % (direct, len(substantial), EXTRACT_MIN_WORDS,
                 EXTRACT_MAX_WORDS, 100 * share,
                 100 * EXTRACT_GOOD_SHARE))
    extract_params = {
        "direct": direct, "total": len(substantial),
        "min": EXTRACT_MIN_WORDS, "max": EXTRACT_MAX_WORDS,
        "pct": 100 * share, "threshold": 100 * EXTRACT_GOOD_SHARE}
    if share >= EXTRACT_GOOD_SHARE:
        return [Finding(AREA_SEM, SEV_OK,
                        "Buona estraibilita' diretta", detail,
                        key="sem.extract.ok",
                        params=extract_params)]
    return [Finding(
        AREA_SEM, SEV_WARNING,
        "Pochi paragrafi a risposta diretta", detail,
        "Riformula i paragrafi chiave aprendo con la risposta "
        "(\"X e' ...\", \"Si', ...\", \"In sintesi ...\") e "
        "tienili fra %d e %d parole."
        % (EXTRACT_MIN_WORDS, EXTRACT_MAX_WORDS),
        key="sem.extract.low", params=extract_params,
        example="Prima: \"Nel panorama attuale del benessere, "
                "molte persone si chiedono quale percorso...\"\n"
                "Dopo:  \"Il drenaggio linfatico e' un massaggio "
                "dolce che favorisce il deflusso della linfa: "
                "una seduta dura 45 minuti e costa 40-80 euro.\"",
        weight=1.5)]


def _audit_filler(good: Sequence[Page]) -> List[Finding]:
    """Densita' informativa: pagine sature di filler di marketing.

    Una pagina e' "satura" quando le formule di FILLER_RE sono
    almeno FILLER_MIN_HITS e almeno una ogni 100 parole
    (FILLER_DENSITY): soglie di prassi, dichiarate nel referto.
    Metrica da Features.md.
    """
    saturated: List[str] = []
    total_hits = 0
    for p in good:
        if not p.text or p.word_count < 50:
            continue
        hits = FILLER_RE.findall(p.text)
        total_hits += len(hits)
        if len(hits) >= FILLER_MIN_HITS \
                and len(hits) / p.word_count >= FILLER_DENSITY:
            esempi = sorted({h.strip().lower() for h in hits})[:3]
            saturated.append("%s (%d formule: %s)"
                             % (p.url, len(hits),
                                ", ".join("\"%s\"" % e
                                          for e in esempi)))
    if saturated:
        return [Finding(
            AREA_SEM, SEV_WARNING,
            "%d pagina/e sature di formule di marketing"
            % len(saturated),
            "Il filler occupa spazio senza dire nulla di "
            "estraibile (soglia di prassi: almeno %d formule e "
            "una ogni 100 parole). %s"
            % (FILLER_MIN_HITS, "; ".join(saturated[:5])),
            "Sostituisci le formule generiche con informazioni "
            "verificabili: numeri, durate, prezzi, procedure.",
            key="sem.filler.saturated",
            params={"n": len(saturated), "min": FILLER_MIN_HITS,
                    "examples": "; ".join(saturated[:5])},
            example="Prima: \"Siamo leader di mercato, qualita' e "
                    "professionalita' al tuo servizio.\"\n"
                    "Dopo:  \"Dal 2012 abbiamo seguito oltre 400 "
                    "pazienti post-operatori; la prima valutazione "
                    "e' gratuita e dura 30 minuti.\"",
            weight=1.5)]
    if any(p.text and p.word_count >= 50 for p in good):
        return [Finding(
            AREA_SEM, SEV_OK,
            "Filler di marketing sotto controllo",
            "%d formule generiche in tutto il sito: il testo "
            "utile domina." % total_hits,
            key="sem.filler.ok", params={"n": total_hits})]
    return []


def _audit_lifecycle(good: Sequence[Page]) -> List[Finding]:
    """Ciclo di vita dell'argomento negli heading (da Features.md).

    Sei sezioni canoniche: definizione, storia, casi d'uso,
    limiti, FAQ, prospettive. La copertura e' misurata su title e
    heading H1-H4 dell'intero sito; soglie di prassi dichiarate:
    5+/6 completo, 3-4 incompleto (peso 1), 0-2 scoperto (peso 2).
    """
    texts: List[str] = []
    for p in good:
        if p.title:
            texts.append(p.title)
        texts.extend(h for lvl, h in p.headings if lvl <= 4)
    if not texts:
        return []
    covered: Dict[str, str] = {}
    for name, pattern in LIFECYCLE_SECTIONS:
        for text in texts:
            if pattern.search(text):
                covered[name] = text.strip()[:60]
                break
    missing = [name for name, _ in LIFECYCLE_SECTIONS
               if name not in covered]
    trovate = "; ".join(
        "%s (\"%s\")" % (name, covered[name])
        for name, _ in LIFECYCLE_SECTIONS if name in covered)
    if len(covered) >= 5:
        return [Finding(
            AREA_SEM, SEV_OK,
            "Ciclo di vita dell'argomento coperto (%d su 6)"
            % len(covered),
            "Sezioni trovate negli heading: %s." % trovate,
            key="sem.lifecycle.ok",
            params={"n": len(covered), "found": trovate})]
    return [Finding(
        AREA_SEM, SEV_WARNING,
        "Ciclo di vita dell'argomento incompleto (%d su 6)"
        % len(covered),
        "Una trattazione completa copre definizione, storia, casi "
        "d'uso, limiti, FAQ e prospettive: e' il contenuto che i "
        "motori generativi possono citare per ogni taglio di "
        "domanda. %s Mancano: %s."
        % ("Trovate: %s." % trovate if trovate else "",
           ", ".join(missing)),
        "Aggiungi le sezioni mancanti con heading espliciti "
        "(anche distribuite su piu' pagine).",
        example="\n".join("<h2>%s</h2>" % LIFECYCLE_HINTS[name]
                          for name in missing),
        weight=2.0 if len(covered) <= 2 else 1.0,
        key="sem.lifecycle.partial",
        params={"n": len(covered),
                "found": ("Trovate: %s." % trovate
                          if trovate else ""),
                "missing": ", ".join(missing)})]


def _page_last_update(page: Page) -> Optional["datetime.date"]:
    """Data di aggiornamento piu' recente dichiarata dalla pagina.

    Guarda i meta article:published_time/modified_time e i campi
    datePublished/dateModified nel JSON-LD; le date non ISO vengono
    ignorate (la validita' dei formati e' gia' un controllo
    Schema.org).
    """
    raw_dates = [d for d in (page.modified, page.published) if d]
    for node in _jsonld_nodes(page.jsonld_raw):
        for key in ("dateModified", "datePublished"):
            value = node.get(key)
            if isinstance(value, str):
                raw_dates.append(value)
    parsed = []
    for raw in raw_dates:
        try:
            parsed.append(
                datetime.date.fromisoformat(raw.strip()[:10]))
        except ValueError:
            continue
    return max(parsed) if parsed else None


def _audit_freshness(good: Sequence[Page],
                     today: Optional["datetime.date"] = None
                     ) -> List[Finding]:
    """Freschezza dei contenuti (da Features.md).

    La *presenza* delle date e' gia' un segnale E-E-A-T: qui se ne
    valuta l'**eta'**. Conta l'aggiornamento dichiarato piu'
    recente dell'intero sito; le pagine piu' vecchie sono riportate
    come evidenza. Senza alcuna data non c'e' rilievo (per non
    punire due volte lo stesso difetto). Soglie di prassi: oltre
    un anno avvertenza, oltre due anni peso doppio.
    """
    today = today or datetime.date.today()
    dated: List[Tuple["datetime.date", str]] = []
    for p in good:
        last = _page_last_update(p)
        if last:
            dated.append((last, p.url))
    if not dated:
        return []
    newest, newest_url = max(dated)
    age = (today - newest).days
    if age <= FRESH_WARN_DAYS:
        return [Finding(
            AREA_SEM, SEV_OK,
            "Contenuti aggiornati di recente",
            "Ultimo aggiornamento dichiarato: %s su %s (%d giorni "
            "fa)." % (newest.isoformat(), newest_url, max(0, age)),
            key="sem.fresh.ok",
            params={"date": newest.isoformat(),
                    "url": newest_url, "days": max(0, age)})]
    stale = sorted(dated)[:5]
    quanto = ("due anni" if age > FRESH_STALE_DAYS else "un anno")
    return [Finding(
        AREA_SEM, SEV_WARNING,
        "Contenuti fermi da oltre %s" % quanto,
        "L'aggiornamento dichiarato piu' recente e' del %s (%d "
        "giorni fa). I motori generativi preferiscono fonti "
        "mantenute: una data ferma segnala contenuto "
        "potenzialmente superato. Pagine piu' datate: %s."
        % (newest.isoformat(), age,
           ", ".join("%s (%s)" % (url, day.isoformat())
                     for day, url in stale)),
        "Rivedi i contenuti chiave e dichiara l'aggiornamento con "
        "article:modified_time o dateModified nel JSON-LD.",
        example="<meta property=\"article:modified_time\" "
                "content=\"%s\">" % today.isoformat(),
        weight=2.0 if age > FRESH_STALE_DAYS else 1.0,
        key=("sem.fresh.very_stale" if age > FRESH_STALE_DAYS
             else "sem.fresh.stale"),
        params={"date": newest.isoformat(), "days": age,
                "stale": ", ".join(
                    "%s (%s)" % (url, day.isoformat())
                    for day, url in stale)})]


def _audit_references(good: Sequence[Page]) -> List[Finding]:
    """Riferimenti bibliografici (da Features.md).

    Tre segnali sull'intero sito: una sezione fonti negli heading
    H2-H4 (REFERENCES_HEADING_RE), citazioni accademiche nel testo
    ([1] o (Autore, anno), CITATION_RE) e i link esterni come
    contesto. Basta una sezione fonti O almeno CITATIONS_GOOD
    citazioni per l'OK: soglia di prassi, dichiarata. "Fonti
    primarie" non e' verificabile offline: i link esterni sono
    riportati come indizio, non giudicati.
    """
    section = ""
    citations = 0
    external = 0
    for p in good:
        external += p.external_links
        if not section:
            for lvl, heading in p.headings:
                if 2 <= lvl <= 4 \
                        and REFERENCES_HEADING_RE.search(heading):
                    section = heading.strip()[:60]
                    break
        citations += len(CITATION_RE.findall(p.text or ""))
    if not any(p.text for p in good):
        return []

    contesto = ("Sezione fonti %s; %d citazioni accademiche nel "
                "testo; %d link esterni in tutto il sito"
                % ("\"%s\"" % section if section else "assente",
                   citations, external))
    if section or citations >= CITATIONS_GOOD:
        return [Finding(
            AREA_SEM, SEV_OK,
            "Riferimenti a fonti presenti",
            "%s (soglia di prassi: una sezione fonti o almeno %d "
            "citazioni)." % (contesto, CITATIONS_GOOD),
            key="sem.refs.ok",
            params={"context": contesto,
                    "threshold": CITATIONS_GOOD})]
    return [Finding(
        AREA_SEM, SEV_WARNING,
        "Nessun riferimento a fonti esterne",
        "%s. Citare le fonti rafforza i segnali E-E-A-T e da' "
        "agli assistenti IA qualcosa da verificare: i contenuti "
        "con riferimenti sono piu' citabili." % contesto,
        "Aggiungi una sezione \"Fonti\" con link a linee guida, "
        "studi o documentazione ufficiale (o citazioni nel testo).",
        key="sem.refs.missing", params={"context": contesto},
        example="<h2>Fonti</h2>\n<ul>\n"
                "<li><a href=\"https://www.iss.it/...\">Istituto "
                "Superiore di Sanita' — linee guida</a></li>\n"
                "<li><a href=\"https://pubmed.ncbi.nlm.nih.gov/"
                "...\">Studio clinico di riferimento</a></li>\n"
                "</ul>",
        weight=1.0)]


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
            weight=3.0, key="sem.chunks.none"))
        return out

    out.extend(_audit_extractability(good))
    out.extend(_audit_filler(good))
    out.extend(_audit_lifecycle(good))
    out.extend(_audit_references(good))
    out.extend(_audit_freshness(good))

    out.append(Finding(
        AREA_SEM, SEV_OK if len(chunks) >= 20 else SEV_WARNING,
        "%d chunk indicizzabili su %d pagine"
        % (len(chunks), len(good)),
        "Ogni chunk e' un'occasione di comparire nelle liste: nella "
        "somma RRF il numero di passaggi pertinenti e' il vero "
        "moltiplicatore.",
        "" if len(chunks) >= 20 else
        "Aumenta il numero di passaggi tematici autonomi.",
        weight=2.0,
        key=("sem.chunks.ok" if len(chunks) >= 20
             else "sem.chunks.few"),
        params={"chunks": len(chunks), "pages": len(good)}))

    anaphoric = [c for c in chunks if ANAPHORA_RE.match(c.text.strip())]
    ratio = len(anaphoric) / len(chunks)
    if ratio > 0.2:
        out.append(Finding(
            AREA_SEM, SEV_WARNING,
            "%.0f%% dei chunk non e' autoconsistente" % (ratio * 100),
            "Iniziano con un riferimento anaforico (questo, tale, "
            "cio'...): estratti da soli non rispondono a nulla. "
            "Esempi: %s."
            % "; ".join("\"%s...\"" % c.text.strip()[:60]
                        for c in anaphoric[:3]),
            "Riscrivi le aperture nominando esplicitamente il "
            "soggetto.",
            key="sem.anaphora.high",
            params={"pct": ratio * 100,
                    "examples": "; ".join(
                        "\"%s...\"" % c.text.strip()[:60]
                        for c in anaphoric[:3])},
            example="Prima: \"Questo trattamento e' indicato dopo "
                    "gli interventi.\"\nDopo:  \"Il drenaggio "
                    "linfatico manuale e' indicato dopo gli "
                    "interventi.\""))
    else:
        out.append(Finding(
            AREA_SEM, SEV_OK,
            "Chunk in larga parte autoconsistenti (%.0f%% anaforici)"
            % (ratio * 100),
            key="sem.anaphora.ok", params={"pct": ratio * 100}))

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
            weight=2.0, key="sem.questions.few",
            params={"n": len(questions), "total": len(headings)}))
    else:
        out.append(Finding(
            AREA_SEM, SEV_OK,
            "%d heading in forma di domanda (%.0f%%)"
            % (len(questions), q_ratio * 100),
            "Esempi: %s."
            % "; ".join("\"%s\"" % q[:60] for q in questions[:3]),
            key="sem.questions.ok",
            params={"n": len(questions), "pct": q_ratio * 100,
                    "examples": "; ".join(
                        "\"%s\"" % q[:60]
                        for q in questions[:3])}))

    has_faq = any(FAQ_HINT_RE.search(h) for h in headings) or any(
        FAQ_HINT_RE.search(p.text[:4000]) for p in good)
    if has_faq:
        faq_where = next(
            (p.url for p in good
             if any(FAQ_HINT_RE.search(h) for _, h in p.headings)
             or FAQ_HINT_RE.search(p.text[:4000])), "")
        out.append(Finding(
            AREA_SEM, SEV_OK, "Sezione FAQ rilevata",
            "Rilevata su %s." % faq_where if faq_where else "",
            key="sem.faq.ok", params={"url": faq_where}))
    else:
        out.append(Finding(
            AREA_SEM, SEV_CRITICAL, "Nessuna sezione FAQ",
            "Le FAQ allineano un chunk a un intento preciso e "
            "alimentano entrambi gli assi contemporaneamente.",
            "Aggiungi FAQ per pagina, marcate con FAQPage JSON-LD.",
            weight=1.5, key="sem.faq.missing",
            example="<h2>Domande frequenti</h2>\n"
                    "<h3>Quanto costa una seduta?</h3>\n"
                    "<p>Da 40 a 80 euro, in base a durata e zona "
                    "trattata.</p>\npiu' il markup:\n" + EX_FAQPAGE))

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
            "serve / esempio.",
            key="sem.defs.low", params={"pct": def_ratio * 100}))
    else:
        out.append(Finding(
            AREA_SEM, SEV_OK,
            "Presenti passaggi definitori (%.0f%% dei chunk)"
            % (def_ratio * 100),
            key="sem.defs.ok", params={"pct": def_ratio * 100}))

    examples = sum(1 for c in chunks if EXAMPLE_RE.search(c.text))
    if examples / len(chunks) < 0.05:
        out.append(Finding(
            AREA_SEM, SEV_WARNING, "Quasi nessun esempio concreto",
            fix="Esempi e casi studio sono i contenuti a piu' alta "
                "densita' semantica.",
            key="sem.examples.few"))
    else:
        out.append(Finding(
            AREA_SEM, SEV_OK, "%d chunk con esempi concreti" % examples,
            key="sem.examples.ok", params={"n": examples}))

    tokens = tokenize(" ".join(c.text for c in chunks))
    unique = len(set(tokens))
    if unique < 300:
        out.append(Finding(
            AREA_SEM, SEV_WARNING,
            "Vocabolario ristretto (%d termini distinti)" % unique,
            "Poca varieta' lessicale significa copertura semantica "
            "limitata: intercetti poche riformulazioni della stessa "
            "domanda.",
            "Amplia i temi trattati e le formulazioni usate.",
            key="sem.vocab.narrow", params={"n": unique}))
    else:
        out.append(Finding(
            AREA_SEM, SEV_OK,
            "Vocabolario ampio (%d termini distinti)" % unique,
            key="sem.vocab.ok", params={"n": unique}))
    return out


def is_question(text: str) -> bool:
    """Riconosce un heading formulato come domanda."""
    clean = text.strip().lower().lstrip("¿¡ ")
    if clean.endswith("?"):
        return True
    return any(clean.startswith(w) for w in QUESTION_STARTERS)


def _jsonld_nodes(blocks: Sequence[object]):
    """Itera tutti i dict annidati nei blocchi JSON-LD."""
    stack: List[object] = list(blocks)
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            yield node
            stack.extend(node.values())
        elif isinstance(node, list):
            stack.extend(node)


def _node_types(node: Dict[str, object]) -> List[str]:
    raw = node.get("@type")
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, list):
        return [str(t) for t in raw]
    return []


def _as_list(value: object) -> List[object]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _as_number(value: object) -> Optional[float]:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def validate_jsonld(pages: List[Page]) -> List[Finding]:
    """Qualita' del markup Schema.org, non solo inventario.

    Due livelli: proprieta' minime per tipo (JSONLD_REQUIRED) e
    controlli sui valori — prezzi e valute delle offerte, rating
    dentro la scala, date ISO 8601, URL di media assoluti, coppie
    domanda/risposta di FAQPage, Product senza offerte o giudizi.
    """
    problems: Dict[str, Set[str]] = {}
    checked: Counter = Counter()
    faq_broken = 0
    offer_issues: List[str] = []
    bare_products = 0
    rating_issues: List[str] = []
    bad_dates: List[str] = []
    bad_urls: List[str] = []

    for page in pages:
        for node in _jsonld_nodes(page.jsonld_raw):
            types = _node_types(node)
            for typ in types:
                required = JSONLD_REQUIRED.get(typ)
                if required is None:
                    continue
                checked[typ] += 1
                missing = {p for p in required if not node.get(p)}
                if missing:
                    problems.setdefault(typ, set()).update(missing)

            if "FAQPage" in types:
                for question in _as_list(node.get("mainEntity")):
                    if not isinstance(question, dict):
                        faq_broken += 1
                        continue
                    answer = question.get("acceptedAnswer")
                    if not question.get("name") \
                            or not isinstance(answer, dict) \
                            or not answer.get("text"):
                        faq_broken += 1

            if "Offer" in types or "AggregateOffer" in types:
                checked["Offer"] += 1
                price = node.get("price")
                if price is None:
                    price = node.get("lowPrice")
                if price is None \
                        and not node.get("priceSpecification"):
                    offer_issues.append(
                        "offerta senza price ne' priceSpecification")
                if price is not None \
                        and not JSONLD_PRICE_RE.match(str(price)):
                    offer_issues.append(
                        "price \"%s\" non numerico" % price)
                currency = node.get("priceCurrency")
                if price is not None and (
                        not currency
                        or not JSONLD_CURRENCY_RE.match(
                            str(currency))):
                    offer_issues.append(
                        "priceCurrency \"%s\" non ISO 4217"
                        % (currency or "assente"))

            if "Product" in types and not (
                    node.get("offers") or node.get("review")
                    or node.get("aggregateRating")):
                bare_products += 1

            if types and {"AggregateRating", "Rating"} & set(types):
                value = _as_number(node.get("ratingValue"))
                best = _as_number(node.get("bestRating"))
                worst = _as_number(node.get("worstRating"))
                best = 5.0 if best is None else best
                worst = 1.0 if worst is None else worst
                if value is not None \
                        and not worst <= value <= best:
                    rating_issues.append(
                        "ratingValue %s fuori scala %g-%g"
                        % (node.get("ratingValue"), worst, best))
                if "AggregateRating" in types \
                        and not node.get("reviewCount") \
                        and not node.get("ratingCount"):
                    rating_issues.append(
                        "AggregateRating senza reviewCount o "
                        "ratingCount")

            if "ImageObject" in types:
                checked["ImageObject"] += 1
                if not node.get("contentUrl") and not node.get("url"):
                    problems.setdefault("ImageObject", set()).add(
                        "contentUrl")

            for key in JSONLD_DATE_KEYS:
                value = node.get(key)
                if isinstance(value, str) and value \
                        and not JSONLD_ISO_DATE_RE.match(value):
                    bad_dates.append("%s=\"%s\"" % (key, value[:40]))

            for key in JSONLD_URL_KEYS:
                for item in _as_list(node.get(key)):
                    if isinstance(item, str) and item \
                            and not item.startswith(
                                ("http://", "https://")):
                        bad_urls.append(
                            "%s=\"%s\"" % (key, item[:60]))

    out: List[Finding] = []
    if problems:
        detail = "; ".join(
            "%s senza %s" % (typ, ", ".join(sorted(miss)))
            for typ, miss in sorted(problems.items()))
        out.append(Finding(
            AREA_SD, SEV_WARNING,
            "JSON-LD incompleto per %d tipo/i" % len(problems),
            "Proprieta' minime mancanti: %s." % detail,
            "Completa le proprieta' indicate: senza, il tipo non "
            "e' eleggibile per i risultati arricchiti.",
            key="sd.check.incomplete",
            params={"n": len(problems), "list": detail}))
    if faq_broken:
        out.append(Finding(
            AREA_SD, SEV_WARNING,
            "%d domanda/e FAQPage incomplete" % faq_broken,
            "Ogni voce di mainEntity richiede una Question con "
            "name e un acceptedAnswer con text.",
            "Completa le coppie domanda/risposta nel markup.",
            key="sd.check.faq", params={"n": faq_broken}))
    if offer_issues:
        out.append(Finding(
            AREA_SD, SEV_WARNING,
            "%d problema/i nei prezzi delle offerte" %
            len(offer_issues),
            "; ".join(offer_issues[:4]) + ".",
            "In price solo il numero con il punto decimale (niente "
            "simboli di valuta); la valuta in priceCurrency (codice "
            "ISO 4217, es. EUR).",
            key="sd.check.offers",
            params={"n": len(offer_issues)},
            example="\"offers\": {\"@type\": \"Offer\",\n"
                    " \"price\": \"50.00\", \"priceCurrency\": "
                    "\"EUR\",\n \"availability\": "
                    "\"https://schema.org/InStock\"}"))
    if bare_products:
        out.append(Finding(
            AREA_SD, SEV_WARNING,
            "%d Product senza offerte ne' giudizi" % bare_products,
            "Un Product privo di offers, review e aggregateRating "
            "non e' eleggibile per i risultati arricchiti di "
            "prodotto.",
            "Aggiungi almeno offers (con price e priceCurrency) "
            "oppure review/aggregateRating.",
            key="sd.check.product", params={"n": bare_products},
            example="\"aggregateRating\": {\"@type\": "
                    "\"AggregateRating\",\n \"ratingValue\": "
                    "\"4.8\", \"reviewCount\": \"27\"}"))
    if rating_issues:
        out.append(Finding(
            AREA_SD, SEV_WARNING,
            "%d valutazione/i incoerenti" % len(rating_issues),
            "; ".join(rating_issues[:4]) + ".",
            "ratingValue dentro la scala dichiarata (default 1-5) "
            "e conteggio recensioni in reviewCount o ratingCount.",
            key="sd.check.rating",
            params={"n": len(rating_issues)}))
    if bad_dates:
        out.append(Finding(
            AREA_SD, SEV_WARNING,
            "%d data/e non in formato ISO 8601" % len(bad_dates),
            "; ".join(bad_dates[:4]) + ".",
            "Usa AAAA-MM-GG, con l'eventuale orario dopo la T "
            "(es. 2026-08-03T09:30:00+02:00).",
            key="sd.check.dates",
            params={"n": len(bad_dates),
                    "list": "; ".join(bad_dates[:4])}))
    if bad_urls:
        out.append(Finding(
            AREA_SD, SEV_WARNING,
            "%d URL di media non assoluti nel markup" % len(bad_urls),
            "; ".join(bad_urls[:4]) + ".",
            "In image, logo, thumbnailUrl, contentUrl ed embedUrl "
            "servono URL http(s) completi.",
            key="sd.check.urls",
            params={"n": len(bad_urls),
                    "list": "; ".join(bad_urls[:4])}))
    if checked and not out:
        out.append(Finding(
            AREA_SD, SEV_OK,
            "Markup Schema.org coerente (%d tipi verificati)"
            % len(checked),
            "Verificati: %s." % ", ".join(sorted(checked)),
            key="sd.check.ok",
            params={"n": len(checked),
                    "types": ", ".join(sorted(checked))}))
    return out


def audit_eeat(pages: List[Page]) -> List[Finding]:
    """Segnali E-E-A-T: autore, date, chi siamo, contatti."""
    good = [p for p in pages if p.ok]
    if not good:
        return []

    author_note = next(
        ("meta author \"%s\" su %s" % (p.author, p.url)
         for p in good if p.author), "")
    dates_note = next(
        ("%s su %s" % ("article:published_time" if p.published
                       else "article:modified_time", p.url)
         for p in good if p.published or p.modified), "")
    for page in good:
        if author_note and dates_note:
            break
        for node in _jsonld_nodes(page.jsonld_raw):
            if not author_note and node.get("author"):
                author_note = "author nel JSON-LD di %s" % page.url
            if not dates_note and (node.get("datePublished")
                                   or node.get("dateModified")):
                dates_note = ("datePublished nel JSON-LD di %s"
                              % page.url)

    def find_slug(slugs: Tuple[str, ...]) -> str:
        wanted = set(slugs)
        for page in good:
            if page.slug.lower() in wanted:
                return page.url
            for target in page.internal_targets:
                seg = urlparse(target).path.strip("/") \
                    .split("/")[-1].lower()
                if seg in wanted:
                    return target
        return ""

    about_note = find_slug(ABOUT_SLUGS)
    if about_note:
        about_note = "rilevata: %s" % about_note

    contact_pages = [p for p in good if p.contact_links]
    if contact_pages:
        contact_note = "link tel:/mailto: su %d pagina/e (es. %s)" \
            % (len(contact_pages), contact_pages[0].url)
    else:
        contact_note = find_slug(CONTACT_SLUGS)
        if contact_note:
            contact_note = "pagina contatti: %s" % contact_note
        else:
            with_mail = next(
                (p.url for p in good if EMAIL_RE.search(p.text)), "")
            contact_note = ("email nel testo di %s" % with_mail
                            if with_mail else "")

    out: List[Finding] = []
    signals = (
        ("author", author_note, "Autore dei contenuti dichiarato",
         "Nessun autore dichiarato",
         "Aggiungi il meta author o la proprieta' author nel "
         "JSON-LD: i motori IA pesano chi firma i contenuti.",
         "<meta name=\"author\" content=\"Dott.ssa Paola Rossi\">\n"
         "oppure nel JSON-LD:\n"
         "\"author\": {\"@type\": \"Person\", \"name\": "
         "\"Paola Rossi\"}"),
        ("dates", dates_note,
         "Date di pubblicazione/aggiornamento presenti",
         "Nessuna data di pubblicazione o aggiornamento",
         "Esponi article:published_time/modified_time o "
         "datePublished/dateModified nel JSON-LD.",
         "<meta property=\"article:published_time\" "
         "content=\"2026-08-03\">\n"
         "oppure nel JSON-LD:\n"
         "\"datePublished\": \"2026-08-03\", "
         "\"dateModified\": \"2026-08-03\""),
        ("about", about_note, "Pagina \"chi siamo\" presente",
         "Nessuna pagina \"chi siamo\" rilevata",
         "Una pagina che presenta persone e competenze e' il "
         "segnale di esperienza piu' diretto.",
         "Crea /chi-siamo/ con: chi cura i contenuti, titoli e "
         "formazione,\nda quanto tempo, foto reali. Linkala dal "
         "footer di ogni pagina."),
        ("contact", contact_note, "Contatti verificabili presenti",
         "Nessun contatto verificabile rilevato",
         "Esponi telefono ed email (link tel:/mailto:) o una "
         "pagina contatti.",
         "<a href=\"tel:+390521123456\">0521 123456</a>\n"
         "<a href=\"mailto:info@esempio.it\">info@esempio.it</a>"),
    )
    for slug, evidence, ok_title, warn_title, fix, example in signals:
        if evidence:
            out.append(Finding(
                AREA_SEM, SEV_OK, "E-E-A-T: %s" % ok_title,
                evidence[0].upper() + evidence[1:] + ".",
                key="sem.eeat.%s.ok" % slug))
        else:
            out.append(Finding(
                AREA_SEM, SEV_WARNING, "E-E-A-T: %s" % warn_title,
                fix=fix, example=example,
                key="sem.eeat.%s.missing" % slug))
    return out


def _audit_semantic_html(good: Sequence[Page]) -> List[Finding]:
    """HTML semantico e "divitis" (da Features.md).

    I chunker dei motori generativi segmentano sui tag di
    sezionamento (article, section, figure...): una pagina di soli
    <div> e' piu' difficile da spezzare in blocchi coerenti. Due
    controlli con soglie di prassi dichiarate: almeno
    SEMANTIC_MIN_TYPES tipi di tag semantici per pagina, e <div>
    sotto DIVITIS_RATIO degli elementi. Le pagine con meno di
    SEMANTIC_MIN_ELEMENTS elementi sono fuori dal conto.
    """
    eligible = [p for p in good
                if p.element_count >= SEMANTIC_MIN_ELEMENTS]
    if not eligible:
        return []
    out: List[Finding] = []
    poveri = [p for p in eligible
              if p.semantic_tag_types < SEMANTIC_MIN_TYPES]
    if poveri:
        out.append(Finding(
            AREA_SD, SEV_WARNING,
            "%d pagina/e senza markup semantico" % len(poveri),
            "Meno di %d tipi di tag di sezionamento (article, "
            "section, main, figure...): i chunker dei motori "
            "generativi hanno meno appigli per segmentare il "
            "contenuto in blocchi coerenti. %s"
            % (SEMANTIC_MIN_TYPES,
               ", ".join(p.url for p in poveri[:5])),
            "Racchiudi il contenuto principale in <main> e "
            "<article>, le sezioni tematiche in <section> con il "
            "loro heading, immagini e didascalie in <figure>.",
            key="sd.semantic.poor",
            params={"n": len(poveri), "min": SEMANTIC_MIN_TYPES,
                    "urls": ", ".join(p.url for p in poveri[:5])},
            example="<main><article>\n  <section>\n    <h2>Cos'e' "
                    "il servizio</h2>\n    <p>...</p>\n  "
                    "</section>\n  <figure><img src=\"...\" "
                    "alt=\"...\">\n    <figcaption>Didascalia"
                    "</figcaption></figure>\n</article></main>",
            weight=1.0))
    divitis = [p for p in eligible
               if p.div_count / p.element_count > DIVITIS_RATIO]
    if divitis:
        out.append(Finding(
            AREA_SD, SEV_WARNING,
            "%d pagina/e con eccesso di <div> (divitis)"
            % len(divitis),
            "Piu' della meta' degli elementi e' un <div> "
            "generico: %s."
            % ", ".join("%s (%d%%)"
                        % (p.url, round(100 * p.div_count
                                        / p.element_count))
                        for p in divitis[:5]),
            "Sostituisci i <div> strutturali con i tag semantici "
            "equivalenti: il markup diventa auto-descrittivo.",
            weight=1.0, key="sd.semantic.divitis",
            params={"n": len(divitis),
                    "urls": ", ".join(
                        "%s (%d%%)"
                        % (p.url, round(100 * p.div_count
                                        / p.element_count))
                        for p in divitis[:5])}))
    if not out:
        out.append(Finding(
            AREA_SD, SEV_OK,
            "Markup semantico in uso",
            "Tutte le %d pagine analizzabili usano i tag di "
            "sezionamento e tengono i <div> sotto il %d%% degli "
            "elementi." % (len(eligible),
                           round(100 * DIVITIS_RATIO)),
            key="sd.semantic.ok",
            params={"n": len(eligible),
                    "max": round(100 * DIVITIS_RATIO)}))
    return out


def audit_structured_data(pages: List[Page]) -> List[Finding]:
    """Presenza e copertura del markup Schema.org."""
    out: List[Finding] = []
    good = [p for p in pages if p.ok]
    if not good:
        return out

    out.extend(_audit_semantic_html(good))

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
            weight=2.0, example=EX_LOCALBUSINESS,
            key="sd.jsonld.none"))
        return out

    out.append(Finding(
        AREA_SD, SEV_OK, "JSON-LD presente",
        "Tipi rilevati: %s." % ", ".join(
            "%s (x%d)" % (t, c) for t, c in all_types.most_common(12)),
        key="sd.jsonld.ok",
        params={"types": ", ".join(
            "%s (x%d)" % (t, c)
            for t, c in all_types.most_common(12))}))

    entity_types = {"Organization", "LocalBusiness", "Corporation",
                    "ProfessionalService", "Person"}
    if not entity_types & set(all_types):
        out.append(Finding(
            AREA_SD, SEV_CRITICAL, "Entita' principale non dichiarata",
            fix="Aggiungi Organization o LocalBusiness con nome, "
                "indirizzo, contatti e identificativi fiscali.",
            weight=1.5, example=EX_LOCALBUSINESS,
            key="sd.entity.missing"))
    else:
        out.append(Finding(
            AREA_SD, SEV_OK, "Entita' principale dichiarata",
            key="sd.entity.ok"))

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
                "Aggiungi il tipo %s dove pertinente." % wanted,
                example=EX_FAQPAGE if wanted == "FAQPage" else "",
                key="sd.type.%s" % wanted.lower(),
                params={"type": wanted}))

    covered = sum(1 for p in good if p.jsonld_types)
    if covered < len(good):
        out.append(Finding(
            AREA_SD, SEV_WARNING,
            "JSON-LD solo su %d pagine su %d" % (covered, len(good)),
            fix="Estendi il markup a tutte le pagine rilevanti.",
            key="sd.jsonld.partial",
            params={"covered": covered, "total": len(good)}))

    out.extend(validate_jsonld(good))
    return out


@dataclass
class QueryResult:
    """Esito della fusione RRF per una singola query."""

    query: str
    lexical_top: List[str] = field(default_factory=list)
    vector_top: List[str] = field(default_factory=list)
    fused_top: List[Tuple[str, float]] = field(default_factory=list)
    consensus: int = 0
    covered: bool = False


# Template delle query auto-generate, per lingua prevalente del
# sito (attributo lang delle pagine). Il default resta l'italiano.
QUERY_TEMPLATES: Dict[str, Tuple[str, ...]] = {
    "it": ("cos'e' %s", "come funziona %s", "quanto costa %s"),
    "en": ("what is %s", "how does %s work",
           "how much does %s cost"),
    "fr": ("qu'est-ce que %s", "comment fonctionne %s",
           "combien coûte %s"),
    "de": ("was ist %s", "wie funktioniert %s", "was kostet %s"),
    "es": ("qué es %s", "cómo funciona %s", "cuánto cuesta %s"),
}


# Termini dei template (tutte le lingue): esclusi dai temi per non
# produrre query degeneri tipo "come funziona funziona".
QUERY_BANNED = {
    "cosa", "costa", "costo", "funziona", "funzionamento", "come",
    "quanto", "quali", "perche", "perché",
    "what", "does", "work", "much", "cost",
    "est", "que", "comment", "fonctionne", "combien", "coute",
    "coûte",
    "was", "ist", "wie", "funktioniert", "kostet",
    "qué", "cómo", "cuánto", "cuanto", "cuesta",
}


# Query reali da Google Search Console: quante prenderne dal CSV.
GSC_QUERIES_LIMIT = 15


def load_gsc_queries(path: str,
                     limit: int = GSC_QUERIES_LIMIT) -> List[str]:
    """Query reali dall'export CSV di Google Search Console.

    Legge il CSV "Query" dell'export Rendimento (intestazioni
    italiane o inglesi, delimitatore virgola o punto e virgola,
    BOM tollerato), ordina per clic e poi impressioni decrescenti
    e restituisce fino a ``limit`` query deduplicate. Righe vuote
    o coi numeri illeggibili non fermano l'import: clic e
    impressioni sono interi, i separatori delle migliaia vengono
    ignorati.
    """
    with open(path, encoding="utf-8-sig", newline="") as handle:
        sample = handle.read(4096)
        handle.seek(0)
        delimiter = (";" if sample.count(";") > sample.count(",")
                     else ",")
        reader = csv.reader(handle, delimiter=delimiter)
        header = next(reader, None)
        if not header:
            return []
        low = [h.strip().lower() for h in header]

        def col(*prefixes: str) -> Optional[int]:
            for i, name in enumerate(low):
                if any(name.startswith(p) for p in prefixes):
                    return i
            return None

        q_col = col("query", "top quer", "consultas")
        q_col = 0 if q_col is None else q_col
        c_col = col("clic", "click")
        i_col = col("impression", "impressioni")

        def num(row: List[str], idx: Optional[int]) -> int:
            if idx is None or idx >= len(row):
                return 0
            digits = re.sub(r"[^\d]", "", row[idx])
            return int(digits) if digits else 0

        rows: List[Tuple[int, int, str]] = []
        for row in reader:
            if not row or q_col >= len(row):
                continue
            query = row[q_col].strip()
            if query:
                rows.append((num(row, c_col), num(row, i_col),
                             query))

    rows.sort(key=lambda r: (-r[0], -r[1]))
    seen: Set[str] = set()
    out: List[str] = []
    for _clicks, _imps, query in rows:
        if query.lower() in seen:
            continue
        seen.add(query.lower())
        out.append(query)
        if len(out) >= limit:
            break
    return out


def dominant_language(pages: Sequence[Page]) -> str:
    """Lingua prevalente dichiarata dalle pagine (default 'it').

    Conta gli attributi lang delle pagine analizzabili (senza la
    regione: it-IT -> it); una lingua fuori da QUERY_TEMPLATES
    ricade sull'italiano.
    """
    counts: Counter = Counter()
    for page in pages:
        if page.ok and page.lang:
            counts[page.lang.split("-")[0].strip().lower()] += 1
    if not counts:
        return "it"
    lang = counts.most_common(1)[0][0]
    return lang if lang in QUERY_TEMPLATES else "it"


def auto_queries(pages: List[Page], limit: int = 12) -> List[str]:
    """Genera query informative dai temi rilevati sul sito.

    I temi sono bigrammi di termini adiacenti negli heading e nei title:
    un bigramma ("drenaggio linfatico") descrive un argomento, un token
    isolato ("funziona") no. I termini gia' presenti nei template
    interrogativi sono esclusi per non produrre query degeneri del tipo
    "come funziona funziona".
    """
    templates = QUERY_TEMPLATES[dominant_language(pages)]
    banned = QUERY_BANNED
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
                 k: int = 60, top_n: int = DEFAULT_TOP_N,
                 model_name: str = "",
                 weights: Optional[Sequence[float]] = None) -> Tuple[
                     List[QueryResult], List[Finding], str]:
    """Esegue BM25 + vettoriale e ne fonde i risultati con RRF."""
    chunks = [c for p in pages if p.ok for c in p.chunks]
    findings: List[Finding] = []
    if not chunks or not queries:
        findings.append(Finding(
            AREA_RRF, SEV_CRITICAL,
            "Simulazione RRF non eseguibile",
            "Servono almeno un chunk e una query.", weight=2.0,
            key="rrf.not_runnable"))
        return [], findings, "n/d"

    corpus = [c.searchable for c in chunks]
    bm25 = BM25Index(corpus)
    vector = VectorIndex(corpus, model_name=model_name)

    results: List[QueryResult] = []
    for query in queries:
        lex = bm25.search(query)[:top_n * 4]
        vec = vector.search(query)[:top_n * 4]
        fused = reciprocal_rank_fusion([lex, vec], k=k, top_n=top_n,
                                       weights=weights)
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
        sev, level = SEV_CRITICAL, "low"
        note = ("Le due liste puntano a passaggi diversi: nessun "
                "documento accumula punteggio su entrambi gli assi.")
    elif consensus_ratio < 0.45:
        sev, level = SEV_WARNING, "mid"
        note = "Consenso parziale fra i due recuperatori."
    else:
        sev, level = SEV_OK, "good"
        note = ("Buona sovrapposizione fra recupero lessicale e "
                "vettoriale.")
    per_query = "; ".join(
        "\"%s\" %d/%d" % (r.query, r.consensus, top_n)
        for r in results[:12])
    if len(results) > 12:
        per_query += "; ..."
    findings.append(Finding(
        AREA_RRF, sev,
        "Consenso medio fra le liste: %.1f/%d (%.0f%%)"
        % (avg_consensus, top_n, consensus_ratio * 100),
        note + " Nella formula RRF un documento presente in entrambe "
        "le liste somma due addendi 1/(k+rank) e supera chi domina una "
        "lista sola. Consenso per query: %s." % per_query,
        "Ottimizza gli stessi passaggi su entrambi gli assi: termini "
        "espliciti (BM25) e spiegazione completa (vettoriale).",
        weight=2.0, key="rrf.consensus.%s" % level,
        params={"avg": avg_consensus, "top_n": top_n,
                "pct": consensus_ratio * 100,
                "per_query": per_query},
        example="Prima (solo lessicale): \"Drenaggio linfatico. "
                "Chiama per info.\"\n"
                "Dopo (entrambi gli assi): \"Il drenaggio linfatico "
                "manuale e' un massaggio\ndolce che favorisce il "
                "deflusso della linfa: una seduta dura 45 minuti\ne "
                "il ciclo tipico va da 5 a 10 incontri.\""))

    uncovered = [r.query for r in results if not r.covered]
    if uncovered:
        findings.append(Finding(
            AREA_RRF, SEV_CRITICAL,
            "%d query senza alcun risultato" % len(uncovered),
            "Nessun chunk del sito risponde a: %s."
            % "; ".join(uncovered[:5]),
            "Crea contenuti dedicati a questi intenti.", weight=2.0,
            key="rrf.uncovered",
            params={"n": len(uncovered),
                    "queries": "; ".join(uncovered[:5])},
            example="Per ogni query scoperta, una sezione con "
                    "heading uguale alla domanda:\n"
                    "<h2>Quanto costa il drenaggio linfatico?</h2>\n"
                    "<p>Una seduta costa in media 40-80 euro, in "
                    "base a durata e zona trattata.</p>"))
    else:
        elenco = "; ".join("\"%s\"" % r.query for r in results[:12])
        if len(results) > 12:
            elenco += "; ..."
        findings.append(Finding(
            AREA_RRF, SEV_OK,
            "Tutte le %d query trovano almeno un passaggio"
            % len(results),
            "Query verificate: %s." % elenco,
            key="rrf.covered",
            params={"n": len(results), "queries": elenco}))

    return results, findings, vector.mode


@dataclass
class ShareResult:
    """Esito della fusione su corpus congiunto per una query."""

    query: str
    owners: List[str] = field(default_factory=list)
    labels: List[str] = field(default_factory=list)
    mine_in_top: int = 0
    best_rank_mine: int = 0  # 0 = assente dai primi top_n


def crawl_corpus(base: str, fetcher: Fetcher, max_pages: int,
                 respect_robots: bool = False,
                 workers: int = 1) -> List[Page]:
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
    pages = [p for p in fetch_pages(fetcher, urls[:max_pages],
                                    workers=workers,
                                    stop_event=fetcher.stop_event)
             if not p.error]
    pages, _ = dedupe_pages(pages)
    return pages


def simulate_share_of_voice(
        base: str, own_chunks: List[Chunk],
        corpora: Dict[str, List[Chunk]], queries: Sequence[str],
        k: int = 60, top_n: int = DEFAULT_TOP_N,
        model_name: str = "",
        weights: Optional[Sequence[float]] = None) -> Tuple[
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
                "include con 0 passaggi.",
                key="rrf.comp.empty", params={"host": host}))

    chunks: List[Chunk] = list(own_chunks)
    owners: List[str] = [main_host] * len(own_chunks)
    for host, cchunks in corpora.items():
        chunks.extend(cchunks)
        owners.extend([host] * len(cchunks))

    if not chunks or not queries:
        findings.append(Finding(
            AREA_RRF, SEV_CRITICAL,
            "Confronto competitivo non eseguibile",
            "Servono almeno un chunk e una query.", weight=2.0,
            key="rrf.comp.not_runnable"))
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
        fused = reciprocal_rank_fusion([lex, vec], k=k, top_n=top_n,
                                       weights=weights)
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
        sev, level = SEV_CRITICAL, "low"
        note = ("I concorrenti occupano i posti che servirebbero "
                "a te: sui tuoi stessi temi vieni recuperato "
                "raramente.")
    elif mine < parity:
        sev, level = SEV_WARNING, "mid"
        note = ("Sei sotto la parita': sui tuoi temi i "
                "concorrenti vengono recuperati piu' spesso di "
                "te.")
    else:
        sev, level = SEV_OK, "good"
        note = "Tieni testa ai concorrenti sui tuoi temi."
    findings.append(Finding(
        AREA_RRF, sev,
        "Share of voice: %.0f%% dei primi %d posti fusi "
        "(parita' %.0f%%)" % (mine * 100, top_n, parity * 100),
        "%s Ripartizione: %s." % (note, breakdown),
        "Rafforza i passaggi sulle query dove i concorrenti ti "
        "superano: stessi termini espliciti, risposta completa.",
        weight=2.0, key="rrf.share.%s" % level,
        params={"pct": mine * 100, "top_n": top_n,
                "parity": parity * 100,
                "breakdown": breakdown}))

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
            weight=2.0, key="rrf.comp.lost",
            params={"n": len(absent), "total": len(results),
                    "top_n": top_n,
                    "queries": "; ".join(absent[:5])}))
    else:
        elenco = "; ".join("\"%s\"" % r.query for r in results[:12])
        if len(results) > 12:
            elenco += "; ..."
        findings.append(Finding(
            AREA_RRF, SEV_OK,
            "Presente nei primi %d per tutte le %d query"
            % (top_n, len(results)),
            "Query del confronto: %s." % elenco,
            key="rrf.comp.present",
            params={"top_n": top_n, "n": len(results),
                    "queries": elenco}))

    presence: Counter = Counter()
    for res in results:
        for host in set(res.owners):
            presence[host] += 1

    payload: Dict[str, object] = {
        "main": main_host,
        "top_n": top_n,
        "sites": sites,
        "share": {h: round(share[h] * 100, 1) for h in sites},
        "chunks": {main_host: len(own_chunks),
                   **{h: len(c) for h, c in corpora.items()}},
        "presence": {h: presence.get(h, 0) for h in sites},
        "queries_total": len(results),
        "queries": [asdict(r) for r in results],
    }
    return payload, findings


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
    """Media pesata delle aree; lessicale e semantica pesano di piu'.

    La sesta area (Lighthouse) pesa 1.0 ed entra solo quando e'
    presente nel dict: senza Lighthouse i pesi si rinormalizzano
    da soli sulle aree rimaste (decisione P1).
    """
    weights = {AREA_TECH: 1.0, AREA_LEX: 1.5, AREA_SEM: 1.5,
               AREA_SD: 1.0, AREA_RRF: 1.5, AREA_LIGHTHOUSE: 1.0}
    num = sum(weights[a] * s for a, s in scores.items() if s is not None)
    den = sum(weights[a] for a, s in scores.items() if s is not None)
    return round(num / den, 1) if den else 0.0


def citability_profiles(
        pages: Sequence[Page],
        scores: Dict[str, Optional[float]],
        market: str = DEFAULT_MARKET) -> Optional[Dict[str, object]]:
    """Profili euristici di citabilita' per assistente IA.

    Ogni profilo e' la media dei punteggi di area ripesata secondo
    cio' che quel tipo di assistente plausibilmente premia (vedi
    CITABILITY_PROFILES); la "profondita' editoriale" deriva dalle
    parole medie per pagina rapportate a DEPTH_TARGET_WORDS.
    L'indice composito ripesa i profili secondo il mercato scelto
    (MARKET_WEIGHTS). Le componenti senza punteggio sono escluse
    rinormalizzando i pesi; se nessun profilo e' calcolabile
    restituisce None.
    """
    if market not in MARKET_WEIGHTS:
        raise ValueError("Mercato sconosciuto: %s" % market)

    components: Dict[str, Optional[float]] = dict(scores)
    math_data = surface_math(pages)
    components[CITABILITY_DEPTH] = (
        min(100.0, round(100.0 * float(math_data["words_avg"])
                         / DEPTH_TARGET_WORDS, 1))
        if math_data else None)

    profiles: List[Dict[str, object]] = []
    for key, label, focus, weights in CITABILITY_PROFILES:
        usable = {c: w for c, w in weights.items()
                  if components.get(c) is not None}
        den = sum(usable.values())
        score = (round(sum(w * components[c]
                           for c, w in usable.items()) / den, 1)
                 if den else None)
        profiles.append({
            "key": key, "label": label, "focus": focus,
            "score": score, "weights": dict(weights),
            "components": {c: components[c] for c in usable},
        })

    scored = [p for p in profiles if p["score"] is not None]
    if not scored:
        return None

    mkt = MARKET_WEIGHTS[market]
    den = sum(mkt[str(p["key"])] for p in scored)
    index = (round(sum(mkt[str(p["key"])] * float(p["score"])
                       for p in scored) / den, 1)
             if den else None)
    return {
        "market": market,
        "market_weights": dict(mkt),
        "depth_target_words": DEPTH_TARGET_WORDS,
        "profiles": profiles,
        "index": index,
        "note": CITABILITY_NOTE,
    }


def _citability_gains(f: "Finding", totals: Dict[str, float],
                      cit: Dict[str, object]) -> Dict[str, object]:
    """Guadagni stimati se il rilievo fosse risolto.

    La variazione dell'area e' esatta rispetto al modello di
    punteggio (peso x (1 - fattore di gravita') / somma dei pesi
    dell'area, in centesimi); il guadagno di un profilo e' quella
    variazione per il peso rinormalizzato che il profilo assegna
    all'area; il guadagno sull'indice composito usa i pesi del
    mercato. "profiles_hit" elenca i profili con guadagno di almeno
    CROSS_GAIN_MIN punti; con due o piu' il rilievo e' trasversale.
    """
    total = totals.get(f.area, 0.0)
    delta = (100.0 * f.weight
             * (1.0 - _SEVERITY_FACTOR[f.severity]) / total
             if total else 0.0)
    gains: Dict[str, float] = {}
    best_key, best_label, best_gain = "", "", 0.0
    for prof in cit["profiles"]:
        if prof["score"] is None:
            continue
        weights: Dict[str, float] = dict(prof["weights"])
        den = sum(weights[c] for c in dict(prof["components"]))
        share = weights.get(f.area, 0.0) / den if den else 0.0
        gain = round(delta * share, 1)
        gains[str(prof["key"])] = gain
        if gain > best_gain:
            best_key = str(prof["key"])
            best_label = str(prof["label"])
            best_gain = gain
    mkt: Dict[str, float] = dict(cit["market_weights"])
    hit = [key for key, gain in gains.items()
           if gain >= CROSS_GAIN_MIN]
    return {
        "gains": gains,
        "best_profile": best_key,
        "best_label": best_label,
        "best_gain": best_gain,
        "index_gain": round(sum(mkt.get(key, 0.0) * gain
                                for key, gain in gains.items()), 1),
        "profiles_hit": hit,
        "cross": len(hit) >= 2,
    }


def citability_top_actions(
        findings: Sequence["Finding"],
        pages: Sequence[Page],
        scores: Dict[str, Optional[float]],
        market: str = DEFAULT_MARKET,
        top: int = 3) -> List[Dict[str, object]]:
    """Le prime azioni del piano annotato con i guadagni di profilo.

    E' la testa di build_remediation() chiamata con i dati di
    citabilita': stesse priorita', stesse annotazioni. Vuota se i
    profili non sono calcolabili.
    """
    if citability_profiles(pages, scores, market) is None:
        return []
    return build_remediation(findings, pages, scores, market)[:top]


def _finding_key(finding: Dict[str, object]) -> Tuple[str, str]:
    """Chiave stabile di un rilievo fra due audit.

    I titoli incorporano conteggi che cambiano a ogni esecuzione
    ("3 title non ottimizzati" -> "2 title non ottimizzati"): i
    numeri vengono normalizzati a N perche' e' lo stesso problema
    che evolve, non un rilievo nuovo.
    """
    return (str(finding.get("area", "")),
            re.sub(r"\d+", "N", str(finding.get("title", ""))))


def compute_delta(previous: Dict[str, object],
                  current: Dict[str, object],
                  previous_at: float) -> Dict[str, object]:
    """Variazioni fra due esecuzioni sullo stesso sito.

    Accetta sia referti JSON completi sia le righe compatte dello
    storico (`history_payload`): servono solo scores, findings,
    site e generated_at. Punteggi: differenza per area (e
    complessivo) dove entrambe le esecuzioni hanno un valore.
    Rilievi: confronto dei soli critici e avvertenze per (area,
    titolo normalizzato): "nuovi" = solo nell'attuale, "risolti" =
    solo nel precedente. Euristica dichiarata: un rilievo
    riformulato conta come nuovo + risolto. La chiave
    ``lighthouse`` porta i delta dei punteggi di categoria
    Lighthouse, per le categorie presenti in entrambe le
    esecuzioni (dal blocco del referto JSON o dalla riga compatta
    dello storico).
    """
    def actionable(payload: Dict[str, object]) -> Dict[
            Tuple[str, str], Dict[str, object]]:
        out: Dict[Tuple[str, str], Dict[str, object]] = {}
        for f in payload.get("findings") or []:
            if f.get("severity") in (SEV_CRITICAL, SEV_WARNING):
                out.setdefault(_finding_key(f), f)
        return out

    def lighthouse_scores(payload: Dict[str, object]
                          ) -> Dict[str, Tuple[str, float]]:
        block = payload.get("lighthouse")
        if isinstance(block, dict):
            cats = block.get("categories")  # referto JSON completo
        else:
            cats = block  # riga compatta dello storico
        out: Dict[str, Tuple[str, float]] = {}
        if not isinstance(cats, list):
            return out
        for c in cats:
            if not isinstance(c, dict):
                continue
            cat_id = c.get("id")
            score = c.get("score")
            if cat_id is not None \
                    and isinstance(score, (int, float)):
                out[str(cat_id)] = (str(c.get("title") or cat_id),
                                    float(score))
        return out

    prev_scores = previous.get("scores") or {}
    cur_scores = current.get("scores") or {}
    scores = {}
    for area, value in cur_scores.items():
        before = prev_scores.get(area)
        if value is not None and before is not None:
            scores[area] = round(float(value) - float(before), 1)

    prev_lh = lighthouse_scores(previous)
    cur_lh = lighthouse_scores(current)
    lighthouse = [
        {"id": cat_id, "title": cur_lh[cat_id][0],
         "delta": round(cur_lh[cat_id][1] - prev_lh[cat_id][1], 1)}
        for cat_id in sorted(cur_lh) if cat_id in prev_lh]

    prev_f = actionable(previous)
    cur_f = actionable(current)
    slim = ("area", "title", "severity")
    return {
        "site": current.get("site", ""),
        "previous_at": previous_at,
        "previous_generated_at": previous.get("generated_at", ""),
        "scores": scores,
        "lighthouse": lighthouse,
        "new": [{k: cur_f[key].get(k, "") for k in slim}
                for key in sorted(cur_f) if key not in prev_f],
        "resolved": [{k: prev_f[key].get(k, "") for k in slim}
                     for key in sorted(prev_f) if key not in cur_f],
    }


def history_payload(base: str, findings: Sequence["Finding"],
                    scores: Dict[str, Optional[float]],
                    lighthouse: Optional[Dict[str, object]] = None
                    ) -> Dict[str, object]:
    """Riga compatta per lo storico JSONL: cio' che serve al delta.

    Contiene solo punteggi e rilievi azionabili (critici e
    avvertenze, con area/titolo/gravita'): abbastanza per
    compute_delta, abbastanza poco da tenere lo storico leggero.
    Con Lighthouse eseguito (``lighthouse`` = blocco di
    lighthouse_report_data) la riga porta anche i punteggi di
    categoria, per il delta fra esecuzioni.
    """
    row: Dict[str, object] = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "created_at": time.time(),
        "site": base,
        "tool_version": __version__,
        "schema_version": JSON_SCHEMA_VERSION,
        "scores": {**scores, "overall": overall_score(scores)},
        "findings": [
            {"area": f.area, "severity": f.severity,
             "title": f.title}
            for f in findings
            if f.severity in (SEV_CRITICAL, SEV_WARNING)
        ],
    }
    if lighthouse and lighthouse.get("status") == "ok":
        row["lighthouse"] = [
            {"id": c["id"], "title": c["title"],
             "score": c["score"]}
            for c in lighthouse.get("categories") or []]
    return row


def read_history_last(path: str,
                      site: str) -> Optional[Dict[str, object]]:
    """Ultima riga dello storico per lo stesso sito.

    Righe malformate e file assente vengono ignorati: lo storico
    non deve mai impedire l'audit.
    """
    last = None
    try:
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(row, dict) and row.get("site") == site:
                    last = row
    except OSError:
        return None
    return last


def append_history(path: str, payload: Dict[str, object]) -> None:
    """Accoda l'esecuzione allo storico JSONL."""
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def judge_unavailable() -> Optional[str]:
    """None se il giudizio LLM puo' funzionare, altrimenti il motivo.

    Stessa infrastruttura del monitor citazioni: SDK ufficiale
    anthropic e chiave solo dalla variabile d'ambiente
    ANTHROPIC_API_KEY (mai da riga di comando).
    """
    if importlib.util.find_spec("anthropic") is None:
        return "SDK anthropic non installato (pip install anthropic)"
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return "variabile d'ambiente ANTHROPIC_API_KEY assente"
    return None


def _judge_sample(results: Sequence[QueryResult],
                  pages: Sequence[Page]) -> List[Tuple[str, Chunk]]:
    """Campione da giudicare: primo passaggio fuso di ogni query.

    I passaggi sono deduplicati (lo stesso chunk puo' vincere piu'
    query) e limitati a JUDGE_MAX_CHUNKS per contenere i costi.
    """
    by_label = {c.label: c for p in pages if p.ok for c in p.chunks}
    sample: List[Tuple[str, Chunk]] = []
    seen: Set[str] = set()
    for res in results:
        if not res.fused_top:
            continue
        label = res.fused_top[0][0]
        chunk = by_label.get(label)
        if chunk is None or label in seen:
            continue
        seen.add(label)
        sample.append((res.query, chunk))
        if len(sample) >= JUDGE_MAX_CHUNKS:
            break
    return sample


def _judge_prompt(sample: Sequence[Tuple[str, "Chunk"]]) -> str:
    """Prompt unico per l'intero campione, risposta solo JSON."""
    parts = [
        "Sei un valutatore di citabilita' per assistenti IA con "
        "ricerca web. Per ogni voce giudica quanto il PASSAGGIO e' "
        "adatto a essere citato da un assistente che risponde alla "
        "QUERY: risposta diretta, autonoma e verificabile. Rispondi "
        "SOLO con un array JSON, un oggetto per voce, nel formato "
        "[{\"id\": 1, \"score\": 0-100, \"reason\": \"max 15 "
        "parole in italiano\"}]. Nessun altro testo.",
    ]
    for pos, (query, chunk) in enumerate(sample, 1):
        parts.append(
            "Voce %d\nQUERY: %s\nPASSAGGIO (sezione \"%s\"):\n%s"
            % (pos, query, chunk.heading or "senza heading",
               chunk.text[:JUDGE_CHUNK_CHARS]))
    return "\n\n".join(parts)


def run_judge(results: Sequence[QueryResult],
              pages: Sequence[Page],
              mode: str = DEFAULT_JUDGE,
              verbose: bool = False,
              model: str = JUDGE_MODEL) -> Optional[Dict[str, object]]:
    """Giudizio LLM sulla citabilita' dei passaggi migliori.

    Passo separato dopo run_audit(): l'audit in se' non contatta
    mai l'API. Restituisce None con mode=off; altrimenti un dict
    con status "ok" (verdetti e media), "skipped" (motivo) o
    "error" (motivo). Gli errori API non interrompono mai il
    referto. Una sola richiesta per audit.
    """
    if mode == JUDGE_OFF:
        return None
    reason = judge_unavailable()
    if reason:
        if verbose:
            print("Giudizio LLM saltato: %s" % reason,
                  file=sys.stderr)
        return {"status": "skipped", "reason": reason}
    sample = _judge_sample(results, pages)
    if not sample:
        return {"status": "skipped",
                "reason": "nessun passaggio recuperato dalla "
                          "simulazione RRF da giudicare"}
    if verbose:
        print("Giudizio LLM su %d passaggi (%s)..."
              % (len(sample), model), file=sys.stderr)

    import anthropic
    kwargs: Dict[str, object] = {}
    base_url = os.environ.get("ANTHROPIC_BASE_URL", "")
    if base_url:
        kwargs["base_url"] = base_url
    client = anthropic.Anthropic(**kwargs)
    try:
        resp = client.beta.messages.create(
            model=model,
            max_tokens=JUDGE_MAX_TOKENS,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            messages=[{"role": "user",
                       "content": _judge_prompt(sample)}],
        )
    except anthropic.APIError as exc:
        return {"status": "error",
                "reason": "errore API Anthropic: %s" % exc}
    if getattr(resp, "stop_reason", "") == "refusal":
        return {"status": "error",
                "reason": "richiesta declinata dai classificatori "
                          "di sicurezza"}

    text = "".join(getattr(b, "text", "") or ""
                   for b in getattr(resp, "content", []) or [])
    start, end = text.find("["), text.rfind("]")
    try:
        raw = json.loads(text[start:end + 1])
        if not isinstance(raw, list):
            raise ValueError("atteso un array JSON")
        verdicts: List[Dict[str, object]] = []
        for item in raw:
            pos = int(item["id"])
            if not 1 <= pos <= len(sample):
                continue
            query, chunk = sample[pos - 1]
            score = min(100.0, max(0.0, float(item["score"])))
            verdicts.append({
                "query": query,
                "label": chunk.label,
                "score": round(score, 1),
                "reason": str(item.get("reason", "")).strip(),
            })
        if not verdicts:
            raise ValueError("nessun verdetto riconosciuto")
    except (ValueError, KeyError, TypeError,
            json.JSONDecodeError) as exc:
        return {"status": "error",
                "reason": "risposta del modello non interpretabile "
                          "(%s)" % exc}
    average = round(sum(float(v["score"]) for v in verdicts)
                    / len(verdicts), 1)
    return {
        "status": "ok",
        "model": getattr(resp, "model", model) or model,
        "sampled": len(verdicts),
        "average": average,
        "verdicts": verdicts,
        "note": JUDGE_NOTE,
    }


# Risorse del brand incorporate nel referto HTML autonomo
# (v1.57.0): lette dagli asset della GUI quando lo script vive nel
# repository completo, con fallback dichiarato — firma testuale e
# font di sistema — quando mancano: il referto degrada con grazia.
BRAND_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "gui", "brand")


def search_check_unavailable() -> Optional[str]:
    """None se l'ancora di realta' puo' funzionare, o il motivo.

    Chiave solo dalla variabile d'ambiente BRAVE_API_KEY, mai da
    riga di comando: stessa infrastruttura del giudizio LLM.
    """
    if not os.environ.get(SEARCH_CHECK_ENV):
        return "variabile d'ambiente %s assente" % SEARCH_CHECK_ENV
    return None


def _bare_host(host: str) -> str:
    """Host senza 'www.' iniziale, per il confronto fra domini."""
    host = host.lower()
    return host[4:] if host.startswith("www.") else host


def _site_position(host: str, items: Sequence[Dict[str, object]]
                   ) -> Tuple[Optional[int], str]:
    """Prima posizione (1-based) del sito nei risultati, e URL."""
    for i, item in enumerate(items, 1):
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "")
        try:
            item_host = _bare_host(urlparse(url).netloc)
        except ValueError:
            continue
        if item_host == host:
            return i, url
    return None, ""


def run_search_check(base: str, results: Sequence[QueryResult],
                     mode: str = SEARCH_CHECK_AUTO,
                     verbose: bool = False
                     ) -> Optional[Dict[str, object]]:
    """Ancora di realta': posizionamento reale sulle query dell'audit.

    Passo separato dopo ``run_audit()``, come giudizio LLM e
    Lighthouse: interroga la Brave Search API sulle query della
    simulazione RRF e cerca il sito nei primi SEARCH_CHECK_TOP_N
    risultati, cosi' il referto affianca al consenso simulato un
    ranking reale. None con mode=off; dict con status "ok",
    "skipped" (motivo dichiarato) o "error". Gli errori di una
    query non fermano le altre e niente interrompe mai il referto.
    Max SEARCH_CHECK_MAX_QUERIES query, una richiesta al secondo
    (rate limit del piano base Brave); costi a carico della chiave.
    """
    if mode == SEARCH_CHECK_OFF:
        return None
    reason = search_check_unavailable()
    if reason:
        if verbose:
            print("Ancora di realta' saltata: %s" % reason,
                  file=sys.stderr)
        return {"status": "skipped", "engine": "brave",
                "reason": reason}
    if not results:
        return {"status": "skipped", "engine": "brave",
                "reason": "nessuna query dalla simulazione RRF"}
    host = _bare_host(urlparse(base).netloc)
    endpoint = os.environ.get("BRAVE_BASE_URL", "") \
        or SEARCH_CHECK_ENDPOINT
    headers = {"X-Subscription-Token":
               os.environ[SEARCH_CHECK_ENV],
               "Accept": "application/json"}
    queries = list(results)[:SEARCH_CHECK_MAX_QUERIES]
    if verbose:
        print("Ancora di realta' (Brave) su %d query..."
              % len(queries), file=sys.stderr)
    session = requests.Session()
    checked: List[Dict[str, object]] = []
    errors = 0
    for i, result in enumerate(queries):
        if i:
            time.sleep(SEARCH_CHECK_DELAY_S)
        entry: Dict[str, object] = {
            "query": result.query,
            "rrf_covered": bool(result.covered),
            "rrf_consensus": result.consensus,
            "position": None, "url": ""}
        try:
            resp = session.get(
                endpoint, headers=headers,
                params={"q": result.query,
                        "count": SEARCH_CHECK_TOP_N},
                timeout=20)
            resp.raise_for_status()
            items = (resp.json().get("web") or {}) \
                .get("results") or []
        except (requests.RequestException, ValueError) as exc:
            entry["error"] = str(exc).splitlines()[0][:160]
            errors += 1
            checked.append(entry)
            continue
        pos, url = _site_position(
            host, items[:SEARCH_CHECK_TOP_N])
        entry["position"] = pos
        entry["url"] = url
        checked.append(entry)
        if verbose:
            esito = ("#%d" % pos) if pos else \
                "assente dai primi %d" % SEARCH_CHECK_TOP_N
            print("  %s: %s" % (result.query, esito),
                  file=sys.stderr)
    if checked and errors == len(checked):
        return {"status": "error", "engine": "brave",
                "reason": "tutte le richieste sono fallite: %s"
                          % checked[0].get("error", "")}
    return {"status": "ok", "engine": "brave", "site": host,
            "top_n": SEARCH_CHECK_TOP_N, "queries": checked,
            "found": sum(1 for e in checked if e.get("position")),
            "note": SEARCH_CHECK_NOTE}
