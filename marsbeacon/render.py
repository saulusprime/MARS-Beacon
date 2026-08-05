# -*- coding: utf-8 -*-
"""Renderer dei referti (text/json/html/md/csv), cataloghi i18n,
CSS e JavaScript del referto, brand.

Generato dalla scomposizione di mars_audit.py (v1.58.0): il
namespace pubblico resta mars_audit, questo modulo e' interno.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple
import base64
import csv
import html
import io
import json
import os
import re
import time

from marsbeacon.base import (
    ALL_AREAS,
    AREA_LEX,
    AREA_RRF,
    AREA_SD,
    AREA_SEM,
    AREA_TECH,
    DEFAULT_MARKET,
    DEFAULT_TOP_N,
    EFFORT_MINUTES,
    Finding,
    JSON_SCHEMA_VERSION,
    Page,
    SEV_CRITICAL,
    SEV_INFO,
    SEV_OK,
    SEV_WARNING,
    __version__,
    estimate_effort,
    surface_math)
from marsbeacon.indexes import (
    GRAPH_LABEL_ALL,
    depth_distribution,
    link_graph_data,
    treemap_data)
from marsbeacon.audits import (
    BRAND_DIR,
    QueryResult,
    _finding_key,
    _strip_md_links,
    build_remediation,
    citability_profiles,
    citability_top_actions,
    overall_score)


FONTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "gui", "vendor", "bootstrap-italia", "fonts",
    "Titillium_Web")


# Pesi incorporati: regular (400) e bold (700), ~47 KB in base64.
# I pesi 600/800 usati dal CSS ripiegano sul 700 per la regola di
# font-matching: incorporarli costerebbe altri ~25 KB per una
# differenza di resa minima (valutazione del 2026-08-05).
_FONT_FILES = (
    ("titillium-web-v10-latin-ext_latin-regular.woff2", 400),
    ("titillium-web-v10-latin-ext_latin-700.woff2", 700),
)


def _brand_logo_svg() -> str:
    """Marchio SVG inline per il footer del referto, o vuota.

    Letto da gui/brand/lympha-mark.svg; se il file manca (script
    distribuito da solo) la firma resta testuale.
    """
    try:
        with open(os.path.join(BRAND_DIR, "lympha-mark.svg"),
                  encoding="utf-8") as fh:
            svg = fh.read().strip()
    except OSError:
        return ""
    if not svg.startswith("<svg"):
        return ""
    return svg.replace("<svg ", "<svg class=\"logo-mark\" ", 1)


def _brand_font_css() -> str:
    """Regole @font-face coi woff2 Titillium incorporati, o vuota.

    Tutto o niente: senza uno dei file si rinuncia (font di
    sistema), mai un incorporo parziale.
    """
    rules: List[str] = []
    for name, weight in _FONT_FILES:
        try:
            with open(os.path.join(FONTS_DIR, name), "rb") as fh:
                data = base64.b64encode(fh.read()).decode("ascii")
        except OSError:
            return ""
        rules.append(
            "@font-face{font-family:'Titillium Web';"
            "font-style:normal;font-weight:%d;font-display:swap;"
            "src:url(data:font/woff2;base64,%s) format('woff2')}"
            % (weight, data))
    return "".join(rules)


def render_text(base: str, pages: List[Page],
                findings: List[Finding],
                scores: Dict[str, Optional[float]],
                results: List[QueryResult], mode: str,
                k: int = 60,
                competitive: Optional[Dict[str, object]] = None,
                market: str = DEFAULT_MARKET,
                judge: Optional[Dict[str, object]] = None,
                delta: Optional[Dict[str, object]] = None,
                lighthouse: Optional[Dict[str, object]] = None,
                search_check: Optional[Dict[str, object]] = None,
                lang: str = "it") -> str:
    """Referto testuale per la console."""
    def T(it_text: str, en_text: str) -> str:
        return en_text if lang == "en" else it_text

    marks = {SEV_CRITICAL: "[X]", SEV_WARNING: "[!]",
             SEV_OK: "[v]", SEV_INFO: "[i]"}
    lines: List[str] = []
    lines.append("=" * 70)
    lines.append("MARS BEACON  ·  %s" % base)
    lines.append("Meta-fusion, Accessibility, Ranking & Security "
                 "Audit")
    lines.append("=" * 70)
    lines.append(T("Pagine analizzate : %d",
                   "Pages analysed    : %d")
                 % len([p for p in pages if p.ok]))
    lines.append(T("Chunk indicizzati : %d",
                   "Indexed chunks    : %d")
                 % sum(len(p.chunks) for p in pages if p.ok))
    lines.append(T("Recuperatore vett.: %s",
                   "Vector retriever  : %s") % mode)
    if lang == "en":
        lines.append("Note: quoted evidence from the audited site "
                     "stays in the site's language.")
    lines.append("")
    lines.append(T("PUNTEGGI", "SCORES"))
    area_label = {} if lang != "en" else {
        AREA_TECH: "Technical", AREA_LEX: "Lexical (BM25)",
        AREA_SEM: "Semantic (vector)", AREA_SD: "Structured data",
        AREA_RRF: "RRF simulation"}
    for area, score in scores.items():
        if score is None:
            continue
        bar = "#" * int(score / 5)
        lines.append("  %-24s %5.1f/100  %s"
                     % (area_label.get(area, area), score, bar))
    lines.append("  %-24s %5.1f/100"
                 % (T("COMPLESSIVO", "OVERALL"),
                    overall_score(scores)))
    lines.append("")

    if delta:
        marks_d = {SEV_CRITICAL: "[X]", SEV_WARNING: "[!]"}
        lines.append(T("RISPETTO ALL'ESECUZIONE PRECEDENTE  ·  %s",
                       "COMPARED WITH THE PREVIOUS RUN  ·  %s")
                     % (delta.get("previous_generated_at") or ""))
        variazioni = [
            "%s %+.1f" % (area_label.get(area, area), value)
            if value else "%s =" % area_label.get(area, area)
            for area, value in dict(delta["scores"]).items()]
        if variazioni:
            lines.append("  " + " · ".join(variazioni))
        for label, items in ((T("Risolti", "Resolved"),
                              delta["resolved"]),
                             (T("Nuovi", "New"), delta["new"])):
            lines.append("  %s (%d):" % (label, len(list(items)))
                         if items else
                         T("  %s: nessuno", "  %s: none") % label)
            for f in items:
                lines.append("    %s %s"
                             % (marks_d.get(str(f["severity"]),
                                            "[i]"), f["title"]))
        lines.append(T("  Nota: rilievi confrontati per tipo (i "
                       "conteggi nei titoli possono variare).",
                       "  Note: findings compared by type (counts "
                       "in titles may vary)."))
        lines.append("")

    cit = citability_profiles(pages, scores, market)
    if cit:
        lines.append(T("PROFILI DI CITABILITA' PER ASSISTENTE IA",
                       "CITABILITY PROFILES PER AI ASSISTANT"))
        for prof in cit["profiles"]:
            if prof["score"] is None:
                continue
            bar = "#" * int(prof["score"] / 5)
            lines.append("  %-24s %5.1f/100  %s"
                         % (prof["label"], prof["score"], bar))
        if cit["index"] is not None:
            lines.append("  %-24s %5.1f/100"
                         % (T("INDICE COMPOSITO", "COMPOSITE INDEX"),
                            cit["index"]))
        lines.append(T("  Pesi (mercato %s): %s",
                       "  Weights (%s market): %s")
                     % (cit["market"],
                        ", ".join("%s %d%%" % (key, round(100 * w))
                                  for key, w
                                  in cit["market_weights"].items())))
        actions = citability_top_actions(findings, pages, scores,
                                         market)
        if actions:
            lines.append(T("  Azioni con maggior guadagno di "
                           "profilo:",
                           "  Actions with the highest profile "
                           "gain:"))
            for act in actions:
                gain = ((T(" -> %s (+%.1f punti profilo)",
                           " -> %s (+%.1f profile points)")
                         % (act["best_label"], act["best_gain"]))
                        if act["best_profile"] else "")
                lines.append(T("   %d. [sforzo: %s] %s%s",
                               "   %d. [effort: %s] %s%s")
                             % (act["priority"], act["effort"],
                                finding_texts(act, lang)["title"],
                                gain))
        lines.append(T("  Nota: %s", "  Note: %s") % cit["note"])
        lines.append("")

    if judge:
        lines.append(T("GIUDIZIO LLM SULLA CITABILITA'",
                       "LLM JUDGEMENT ON CITABILITY"))
        if judge.get("status") == "ok":
            lines.append(T("  Modello: %s · passaggi valutati: %d "
                           "· media: %.1f/100",
                           "  Model: %s · passages judged: %d · "
                           "average: %.1f/100")
                         % (judge["model"], judge["sampled"],
                            judge["average"]))
            if cit and cit["index"] is not None:
                lines.append(T("  Indice euristico: %.1f — scarto "
                               "giudice-euristica: %+.1f",
                               "  Heuristic index: %.1f — "
                               "judge-heuristic gap: %+.1f")
                             % (cit["index"],
                                float(str(judge["average"]))
                                - float(str(cit["index"]))))
            for v in judge["verdicts"]:
                lines.append("  %5.1f/100  %s"
                             % (v["score"], v["query"]))
                if v["reason"]:
                    lines.append("             %s" % v["reason"])
            lines.append(T("  Nota: %s", "  Note: %s")
                         % judge["note"])
        else:
            lines.append(T("  Non eseguito: %s", "  Not run: %s")
                         % judge.get("reason", ""))
        lines.append("")

    if lighthouse:
        lines.append(T("AUDIT LIGHTHOUSE", "LIGHTHOUSE AUDIT"))
        if lighthouse.get("status") == "ok":
            fork = str(lighthouse.get("fork") or "")
            lines.append(
                (T("  Eseguito su %d pagina/e (%s)%s",
                   "  Run on %d page(s) (%s)%s"))
                % (len(lighthouse.get("pages") or []),
                   lighthouse.get("device", ""),
                   (", fork %s" % fork) if fork else ""))
            categorie = lighthouse.get("categories") or []
            if categorie:
                lines.append("  " + " · ".join(
                    "%s %d/100" % (c["title"], c["score"])
                    for c in categorie))
        else:
            lines.append(T("  Non eseguito: %s", "  Not run: %s")
                         % lighthouse.get("reason", ""))
        lines.append("")

    if search_check:
        lines.append(T("ANCORA DI REALTA' (BRAVE SEARCH)",
                       "REALITY ANCHOR (BRAVE SEARCH)"))
        if search_check.get("status") == "ok":
            interrogate = search_check.get("queries") or []
            lines.append(
                T("  Sito trovato per %d query su %d "
                  "(primi %d risultati)",
                  "  Site found for %d of %d queries "
                  "(top %d results)")
                % (search_check.get("found", 0),
                   len(interrogate),
                   search_check.get("top_n", 0)))
            for q in interrogate:
                if q.get("error"):
                    esito = T("errore: %s", "error: %s") \
                        % q["error"]
                elif q.get("position"):
                    esito = T("posizione #%d", "position #%d") \
                        % q["position"]
                else:
                    esito = T("assente dai primi %d",
                              "absent from the top %d") \
                        % search_check.get("top_n", 0)
                lines.append(
                    "  %s %s — %s · %s"
                    % ("[v]" if q.get("position") else "[x]",
                       q.get("query", ""), esito,
                       T("consenso RRF %s", "RRF consensus %s")
                       % q.get("rrf_consensus", 0)))
            lines.append(T("  Nota: %s", "  Note: %s")
                         % search_check.get("note", ""))
        else:
            lines.append(T("  Non eseguita: %s", "  Not run: %s")
                         % search_check.get("reason", ""))
        lines.append("")

    for area in ALL_AREAS:
        subset = [f for f in findings if f.area == area]
        if not subset:
            continue
        lines.append("-" * 70)
        lines.append(area_label.get(area, area).upper())
        lines.append("-" * 70)
        order = {SEV_CRITICAL: 0, SEV_WARNING: 1, SEV_INFO: 2,
                 SEV_OK: 3}
        for finding in sorted(subset, key=lambda f: order[f.severity]):
            texts = finding_texts(finding, lang)
            lines.append("%s %s" % (marks[finding.severity],
                                    texts["title"]))
            if texts["detail"]:
                lines.append("    %s" % texts["detail"])
            if texts["fix"]:
                lines.append("    -> Fix: %s" % texts["fix"])
        lines.append("")

    math = surface_math(pages)
    if math:
        lines.append("-" * 70)
        lines.append(T("LA MATEMATICA DEL PROBLEMA",
                       "THE MATHS OF THE PROBLEM"))
        lines.append("-" * 70)
        lines.append(T("  Superficie attuale   : %d pagine, %d "
                       "chunk (~%d parole/pagina)",
                       "  Current surface     : %d pages, %d "
                       "chunks (~%d words/page)")
                     % (math["pages"], math["chunks_now"],
                        math["words_avg"]))
        lines.append(T("  Superficie potenziale: ~%d chunk (%s)",
                       "  Potential surface   : ~%d chunks (%s)")
                     % (math["chunks_potential"], math["assumption"]))
        if math["multiplier"] is not None:
            lines.append(T("  Effetto sull'RRF     : ~%.1fx "
                           "occasioni di comparire nelle liste "
                           "fuse",
                           "  Effect on RRF       : ~%.1fx "
                           "opportunities to appear in the fused "
                           "lists")
                         % math["multiplier"])
        else:
            lines.append(T("  Effetto sull'RRF     : da 0 addendi "
                           "a ~%d occasioni di comparire nelle "
                           "liste",
                           "  Effect on RRF       : from 0 "
                           "addends to ~%d opportunities to "
                           "appear in the lists")
                         % math["chunks_potential"])
        lines.append("")

    plan = build_remediation(findings, pages, scores, market)
    if plan:
        quick = sum(1 for i in plan if i["quick_win"])
        criterio = (T("gravita' e guadagno di citabilita'",
                      "severity and citability gain")
                    if "index_gain" in plan[0] else
                    T("gravita' e peso", "severity and weight"))
        lines.append("-" * 70)
        lines.append(T("PIANO DI REMEDIATION  ·  %d interventi "
                       "per %s%s",
                       "REMEDIATION PLAN  ·  %d actions by %s%s")
                     % (len(plan), criterio,
                        " · %d quick win" % quick if quick else ""))
        lines.append("-" * 70)
        for item in plan:
            tag = (T("CRITICO", "CRITICAL")
                   if item["severity"] == SEV_CRITICAL
                   else T("AVVISO", "WARNING"))
            marker = "  ** QUICK WIN" if item["quick_win"] else ""
            texts = finding_texts(item, lang)
            lines.append(T("%2d. [%s · %s · sforzo: %s] %s%s",
                           "%2d. [%s · %s · effort: %s] %s%s")
                         % (item["priority"], tag,
                            area_label.get(str(item["area"]),
                                           item["area"]),
                            item["effort"], texts["title"], marker))
            if item.get("cross"):
                lines.append(T("    Trasversale: deprime %d "
                               "profili di citabilita' (risolto "
                               "vale +%.1f sull'indice)",
                               "    Cross-cutting: depresses %d "
                               "citability profiles (fixed it is "
                               "worth +%.1f on the index)")
                             % (len(list(item["profiles_hit"])),
                                item["index_gain"]))
            if texts["fix"]:
                lines.append("    Fix: %s" % texts["fix"])
            if texts["example"]:
                lines.append(T("    Esempio:", "    Example:"))
                for row in texts["example"].splitlines():
                    lines.append("        %s" % row)
            lines.append("")

    if results:
        lines.append("-" * 70)
        lines.append(T("DETTAGLIO SIMULAZIONE RRF",
                       "RRF SIMULATION DETAIL"))
        lines.append("-" * 70)
        for res in results:
            lines.append(T("Query: %s   (consenso %d)",
                           "Query: %s   (consensus %d)")
                         % (res.query, res.consensus))
            for rank, (label, score) in enumerate(res.fused_top, 1):
                lines.append("   %d. %-52s  %.5f"
                             % (rank, label[:52], score))
            if not res.fused_top:
                lines.append(T("   (nessun passaggio recuperato)",
                               "   (no passage retrieved)"))
            lines.append("")

    if competitive:
        lines.append("-" * 70)
        lines.append(T("CONFRONTO COMPETITIVO  ·  share of voice "
                       "sui primi %d posti fusi",
                       "COMPETITIVE COMPARISON  ·  share of voice "
                       "over the first %d fused slots")
                     % competitive["top_n"])
        lines.append("-" * 70)
        share = competitive["share"]
        for host in competitive["sites"]:
            marker = (T("  <- tuo sito", "  <- your site")
                      if host == competitive["main"] else "")
            lines.append("  %-38s %5.1f%%%s"
                         % (host, share[host], marker))
        lines.append("")
        for row in competitive["queries"]:
            best = (T("miglior posizione %d", "best position %d")
                    % row["best_rank_mine"]
                    if row["best_rank_mine"]
                    else T("ASSENTE", "ABSENT"))
            lines.append(T("  %-46s  tuoi %d/%d · %s",
                           "  %-46s  yours %d/%d · %s")
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


# Lingue dei referti (--lang, formati html/text/md/csv). La cornice
# HTML passa da _HTML_I18N; i rilievi da _FINDINGS_EN via
# finding_texts(). Le evidenze citate dal sito auditato restano
# nella lingua del sito (nota dichiarata nel referto).
HTML_LANGS = ("it", "en")


_HTML_I18N: Dict[str, Dict[str, str]] = {
    "it": {
        "hero.ring": "Punteggio complessivo %.0f su 100: %s",
        "hero.of100": "su 100",
        "hero.thresholds": "buono &ge; 70 &middot; da migliorare "
                           "40&ndash;69 &middot; critico &lt; 40",
        "verdict.Buono": "Buono",
        "verdict.Da migliorare": "Da migliorare",
        "verdict.Critico": "Critico",
        "tile.critical": "Critici",
        "tile.warning": "Avvertenze",
        "tile.info": "Informazioni",
        "hero.donut_aria": "%d pagine: %d senza rilievi, %d con "
                           "rilievi, %d in errore",
        "hero.pages": "pagine",
        "hero.clean": "%d senza rilievi",
        "hero.flagged": "%d con rilievi",
        "hero.broken": "%d in errore",
        "meta.line": "Pagine analizzate: %d &middot; chunk "
                     "indicizzati: %d &middot; recuperatore "
                     "vettoriale: <code>%s</code>",
        "note.findings_lang": "",
        "top.h": "Top rilievi",
        "top.critical": "CRITICO",
        "top.warning": "AVVISO",
        "gain.index": "+%.1f indice",
        "score.total": "Complessivo",
        "area.Tecnica": "Tecnica",
        "area.Lessicale (BM25)": "Lessicale (BM25)",
        "area.Semantica (vettoriale)": "Semantica (vettoriale)",
        "area.Dati strutturati": "Dati strutturati",
        "area.Simulazione RRF": "Simulazione RRF",
        "delta.h": "Rispetto all'esecuzione precedente",
        "delta.meta": "Confronto con l'audit del %s sullo stesso "
                      "sito: l'audit diventa monitoraggio. Rilievi "
                      "confrontati per tipo (i conteggi nei titoli "
                      "possono variare).",
        "delta.resolved": "Risolti",
        "delta.new": "Nuovi",
        "delta.none": "Nessuno.",
        "cit.h": "Profili di citabilita' per assistente IA",
        "cit.meta": "%s Mercato di riferimento: <b>%s</b> "
                    "(pesi: %s).",
        "cit.assistant": "Assistente",
        "cit.focus": "Cosa premia",
        "cit.score": "Punteggio",
        "cit.index": "Indice composito (mercato %s)",
        "cit.actions_h": "Top %d azioni prioritarie",
        "cit.actions_meta": "Le prime voci del piano di remediation "
                            "con il profilo che ne guadagna di piu' "
                            "(stima in punti profilo, stessa natura "
                            "euristica).",
        "cit.best": " &mdash; guadagna di piu': <b>%s</b> "
                    "(+%.1f punti profilo)",
        "badge.effort": "sforzo: %s",
        "badge.qw": "quick win",
        "badge.cross": "trasversale: %d profili &middot; "
                       "+%.1f indice",
        "judge.h": "Giudizio LLM sulla citabilita'",
        "judge.compare": " Indice euristico: %.1f — scarto "
                         "giudice-euristica: %+.1f.",
        "judge.meta": "Modello <code>%s</code> su %d passaggio/i "
                      "&middot; media <b>%.1f</b>/100.%s %s",
        "judge.query": "Query",
        "judge.score": "Punteggio",
        "judge.reason": "Motivazione",
        "judge.skipped": "Non eseguito: %s",
        "lh.h": "Audit Lighthouse",
        "lh.meta": "Eseguito su %d pagina/e (%s)%s.",
        "lh.fork": ", fork %s",
        "lh.cat": "Categoria",
        "lh.score": "Punteggio",
        "lh.skipped": "Non eseguito: %s",
        "tm.h": "Treemap della superficie contenutistica",
        "tm.meta": "Ogni rettangolo e' una pagina: area "
                   "proporzionale alle parole indicizzabili, "
                   "colore dalla gravita' dei rilievi che citano "
                   "la pagina. Mostrate %d pagine su %d "
                   "analizzabili.",
        "tm.aria": "Treemap delle pagine per parole "
                   "indicizzabili; i dati sono nella tabella "
                   "sottostante",
        "tm.title": "%s — %d parole, %d chunk, %s",
        "tm.table": "Dati della treemap in tabella",
        "tm.page": "Pagina",
        "tm.words": "Parole",
        "tm.chunks": "Chunk",
        "tm.sev": "Rilievi",
        "tm.sev_critical": "rilievi critici sulla pagina",
        "tm.sev_warning": "avvertenze sulla pagina",
        "tm.sev_ok": "nessun rilievo sulla pagina",
        "sc.h": "Ancora di realta' (Brave Search)",
        "sc.meta": "Sito trovato per %d query su %d (primi %d "
                   "risultati).",
        "sc.query": "Query",
        "sc.result": "Posizione reale",
        "sc.rrf": "Consenso RRF",
        "sc.pos": "#%d",
        "sc.absent": "assente dai primi %d",
        "sc.error": "errore: %s",
        "sc.skipped": "Non eseguita: %s",
        "lg.hint": "Con JavaScript attivo: trascina i nodi (la "
                   "fisica segue), clic su un nodo per bloccare "
                   "l'evidenziazione (Esc per liberarla), rotella "
                   "o pulsanti per lo zoom, trascina lo sfondo "
                   "per spostarti.",
        "lg.zin": "Ingrandisci",
        "lg.zout": "Riduci",
        "lg.reset": "Vista iniziale",
        "lg.vforza": "Vista a forza",
        "lg.vanelli": "Anelli di profondità",
        "lg.legend": "Legenda: ● home · ● entro 3 click · "
                     "● oltre 3 click o senza percorso; ampiezza "
                     "= link in ingresso; le frecce seguono la "
                     "direzione del link; negli anelli il cerchio "
                     "marcato è la soglia dei 3 click.",
        "lg.outgoing": "%d in uscita",
        "depth.h": "Profondita' di crawl",
        "depth.meta": "Quanti click servono dalla home per "
                      "raggiungere ogni pagina lungo i link "
                      "interni: oltre 3 click scansione e peso "
                      "calano.",
        "graph.h": "Architettura dei link interni",
        "graph.meta": "Ogni cerchio e' una pagina (ampiezza = link "
                      "in ingresso), la home e' al centro; in ambra "
                      "le pagine oltre 3 click o senza percorso. "
                      "Mostrate %d pagine su %d.",
        "graph.aria": "Grafo dei link interni; orfane e profondita' "
                      "sono nei rilievi dell'area tecnica",
        "graph.clicks": "%d click",
        "graph.sitemap_only": "solo da sitemap",
        "graph.node_title": "%s — %d link in ingresso, %s",
        "math.h": "La matematica del problema",
        "math.meta": "L'RRF premia chi compare in piu' liste con "
                     "piu' passaggi pertinenti: il numero di chunk "
                     "indicizzabili e' il vero moltiplicatore.",
        "math.now": "Superficie attuale",
        "math.now_v": "%d pagine, %d chunk (~%d parole/pagina)",
        "math.pot": "Superficie potenziale",
        "math.pot_v": "~%d chunk (%s)",
        "math.fx": "Effetto sull'RRF",
        "math.mult": "~%.1fx occasioni di comparire nelle liste "
                     "fuse",
        "math.zero": "da 0 addendi a ~%d occasioni di comparire "
                     "nelle liste",
        "plan.h": "Piano di remediation",
        "plan.crit_gain": "gravita' e guadagno di citabilita': in "
                          "testa i problemi trasversali, che "
                          "deprimono piu' profili insieme",
        "plan.crit_weight": "gravita' e peso: si parte da cio' che "
                            "rende di piu' sul punteggio",
        "plan.meta": "%d interventi ordinati per %s. Lo sforzo "
                     "stimato (minuti/ore/giorni) individua i "
                     "quick win%s.",
        "plan.quick_here": " — qui sono %d",
        "rrf.h": "Dettaglio simulazione RRF",
        "rrf.meta": "Le tacche sul consenso sono le soglie del "
                    "giudizio: sotto il 20% e' critico, sotto il "
                    "45% da migliorare.",
        "rrf.query": "Query",
        "rrf.consensus": "Consenso",
        "rrf.top": "Passaggio in testa dopo la fusione",
        "rrf.score": "Punteggio",
        "rrf.of5": "%d su 5",
        "comp.h": "Confronto competitivo",
        "comp.meta": "Share of voice sui primi %d posti delle "
                     "liste fuse, sulle query dei temi del tuo "
                     "sito. La tacca indica la parita' (%.0f%%): "
                     "sopra la tacca si e' sopra la propria quota "
                     "naturale.",
        "comp.site": "Sito",
        "comp.share": "Share",
        "comp.mine": " <strong>(tuo sito)</strong>",
        "comp.bubble_meta": "Mappa: orizzontale la share of voice, "
                            "verticale in quante query su %d il "
                            "sito compare, ampiezza della bolla il "
                            "corpus in chunk.",
        "comp.bubble_aria": "Mappa a bolle del posizionamento "
                            "competitivo; i valori sono nelle "
                            "tabelle",
        "comp.query": "Query",
        "comp.mine_passages": "Tuoi passaggi",
        "comp.best": "Migliore posizione",
        "comp.absent": "<strong>assente</strong>",
        "footer.gen": "Generato da <code>mars_audit.py</code> "
                      "v%s. La formula applicata e' <code>score(d) "
                      "= &Sigma; 1/(k + rank_i(d))</code> con k=%d, "
                      "pesi uguali per ogni lista.",
        "footer.refs": "Riferimenti",
        "anchor.label": "Link a questo rilievo",
    },
    "en": {
        "hero.ring": "Overall score %.0f out of 100: %s",
        "hero.of100": "out of 100",
        "hero.thresholds": "good &ge; 70 &middot; needs work "
                           "40&ndash;69 &middot; critical &lt; 40",
        "verdict.Buono": "Good",
        "verdict.Da migliorare": "Needs work",
        "verdict.Critico": "Critical",
        "tile.critical": "Critical",
        "tile.warning": "Warnings",
        "tile.info": "Notices",
        "hero.donut_aria": "%d pages: %d clean, %d with findings, "
                           "%d failing",
        "hero.pages": "pages",
        "hero.clean": "%d clean",
        "hero.flagged": "%d with findings",
        "hero.broken": "%d failing",
        "meta.line": "Pages analysed: %d &middot; indexed chunks: "
                     "%d &middot; vector retriever: <code>%s</code>",
        "note.findings_lang": "Report in English. Quoted evidence "
                              "from the audited site (URLs, page "
                              "excerpts) and the run-comparison "
                              "titles stay in the site's "
                              "language.",
        "top.h": "Top findings",
        "top.critical": "CRITICAL",
        "top.warning": "WARNING",
        "gain.index": "+%.1f index",
        "score.total": "Overall",
        "area.Tecnica": "Technical",
        "area.Lessicale (BM25)": "Lexical (BM25)",
        "area.Semantica (vettoriale)": "Semantic (vector)",
        "area.Dati strutturati": "Structured data",
        "area.Simulazione RRF": "RRF simulation",
        "delta.h": "Compared with the previous run",
        "delta.meta": "Comparison with the %s audit of the same "
                      "site: the audit becomes monitoring. "
                      "Findings are compared by type (counts in "
                      "titles may vary).",
        "delta.resolved": "Resolved",
        "delta.new": "New",
        "delta.none": "None.",
        "cit.h": "Citability profiles per AI assistant",
        "cit.meta": "%s Reference market: <b>%s</b> "
                    "(weights: %s).",
        "cit.assistant": "Assistant",
        "cit.focus": "What it rewards",
        "cit.score": "Score",
        "cit.index": "Composite index (%s market)",
        "cit.actions_h": "Top %d priority actions",
        "cit.actions_meta": "The first remediation-plan items with "
                            "the profile that gains the most "
                            "(estimate in profile points, same "
                            "heuristic nature).",
        "cit.best": " &mdash; gains the most: <b>%s</b> "
                    "(+%.1f profile points)",
        "badge.effort": "effort: %s",
        "badge.qw": "quick win",
        "badge.cross": "cross-cutting: %d profiles &middot; "
                       "+%.1f index",
        "judge.h": "LLM judgement on citability",
        "judge.compare": " Heuristic index: %.1f — judge-heuristic "
                         "gap: %+.1f.",
        "judge.meta": "Model <code>%s</code> on %d passage(s) "
                      "&middot; average <b>%.1f</b>/100.%s %s",
        "judge.query": "Query",
        "judge.score": "Score",
        "judge.reason": "Rationale",
        "judge.skipped": "Not run: %s",
        "lh.h": "Lighthouse audit",
        "lh.meta": "Run on %d page(s) (%s)%s.",
        "lh.fork": ", fork %s",
        "lh.cat": "Category",
        "lh.score": "Score",
        "lh.skipped": "Not run: %s",
        "tm.h": "Content surface treemap",
        "tm.meta": "Each rectangle is a page: area proportional "
                   "to indexable words, colour from the severity "
                   "of the findings referencing the page. Showing "
                   "%d pages out of %d analysable.",
        "tm.aria": "Treemap of pages by indexable words; the "
                   "data is in the table below",
        "tm.title": "%s — %d words, %d chunks, %s",
        "tm.table": "Treemap data as a table",
        "tm.page": "Page",
        "tm.words": "Words",
        "tm.chunks": "Chunks",
        "tm.sev": "Findings",
        "tm.sev_critical": "critical findings on the page",
        "tm.sev_warning": "warnings on the page",
        "tm.sev_ok": "no findings on the page",
        "sc.h": "Reality anchor (Brave Search)",
        "sc.meta": "Site found for %d of %d queries (top %d "
                   "results).",
        "sc.query": "Query",
        "sc.result": "Real position",
        "sc.rrf": "RRF consensus",
        "sc.pos": "#%d",
        "sc.absent": "absent from the top %d",
        "sc.error": "error: %s",
        "sc.skipped": "Not run: %s",
        "lg.hint": "With JavaScript enabled: drag nodes (the "
                   "physics follows), click a node to pin the "
                   "highlight (Esc releases it), mouse wheel or "
                   "buttons to zoom, drag the background to pan.",
        "lg.zin": "Zoom in",
        "lg.zout": "Zoom out",
        "lg.reset": "Initial view",
        "lg.vforza": "Force view",
        "lg.vanelli": "Depth rings",
        "lg.legend": "Legend: ● home · ● within 3 clicks · "
                     "● beyond 3 clicks or unreachable; size = "
                     "incoming links; arrows follow the link "
                     "direction; in the rings view the marked "
                     "circle is the 3-click threshold.",
        "lg.outgoing": "%d outgoing",
        "depth.h": "Crawl depth",
        "depth.meta": "How many clicks from the home page it takes "
                      "to reach each page along internal links: "
                      "beyond 3 clicks crawling and weight "
                      "decline.",
        "graph.h": "Internal link architecture",
        "graph.meta": "Each circle is a page (size = incoming "
                      "links), the home page is at the centre; "
                      "amber marks pages beyond 3 clicks or with "
                      "no path. Showing %d pages out of %d.",
        "graph.aria": "Internal link graph; orphans and depth are "
                      "covered by the technical-area findings",
        "graph.clicks": "%d clicks",
        "graph.sitemap_only": "sitemap only",
        "graph.node_title": "%s — %d incoming links, %s",
        "math.h": "The maths of the problem",
        "math.meta": "RRF rewards sites that appear in more lists "
                     "with more relevant passages: the number of "
                     "indexable chunks is the real multiplier.",
        "math.now": "Current surface",
        "math.now_v": "%d pages, %d chunks (~%d words/page)",
        "math.pot": "Potential surface",
        "math.pot_v": "~%d chunks (%s)",
        "math.fx": "Effect on RRF",
        "math.mult": "~%.1fx opportunities to appear in the fused "
                     "lists",
        "math.zero": "from 0 addends to ~%d opportunities to "
                     "appear in the lists",
        "plan.h": "Remediation plan",
        "plan.crit_gain": "severity and citability gain: "
                          "cross-cutting problems, which depress "
                          "several profiles at once, come first",
        "plan.crit_weight": "severity and weight: starting from "
                            "what yields the most on the score",
        "plan.meta": "%d actions sorted by %s. The estimated "
                     "effort (minutes/hours/days) singles out the "
                     "quick wins%s.",
        "plan.quick_here": " — %d here",
        "rrf.h": "RRF simulation detail",
        "rrf.meta": "The ticks on consensus are the judgement "
                    "thresholds: below 20% critical, below 45% "
                    "needs work.",
        "rrf.query": "Query",
        "rrf.consensus": "Consensus",
        "rrf.top": "Top passage after fusion",
        "rrf.score": "Score",
        "rrf.of5": "%d of 5",
        "comp.h": "Competitive comparison",
        "comp.meta": "Share of voice over the first %d fused "
                     "positions, on queries from your site's "
                     "themes. The tick marks parity (%.0f%%): "
                     "above it you exceed your natural share.",
        "comp.site": "Site",
        "comp.share": "Share",
        "comp.mine": " <strong>(your site)</strong>",
        "comp.bubble_meta": "Map: share of voice horizontally, in "
                            "how many of %d queries the site "
                            "appears vertically, bubble size the "
                            "corpus in chunks.",
        "comp.bubble_aria": "Bubble map of competitive "
                            "positioning; values are in the "
                            "tables",
        "comp.query": "Query",
        "comp.mine_passages": "Your passages",
        "comp.best": "Best position",
        "comp.absent": "<strong>absent</strong>",
        "footer.gen": "Generated by <code>mars_audit.py</code> "
                      "v%s. The applied formula is <code>score(d) "
                      "= &Sigma; 1/(k + rank_i(d))</code> with "
                      "k=%d, equal weights per list.",
        "footer.refs": "References",
        "anchor.label": "Link to this finding",
    },
}


# Catalogo inglese dei rilievi: chiave -> template dei testi
# (title/detail/fix/example) con parametri %(nome)s. Contiene SOLO
# l'inglese: l'italiano canonico vive nei punti di creazione dei
# Finding, quindi il referto italiano non passa mai dal catalogo
# (zero rischio di regressione). Le evidenze dinamiche nei params
# (URL, estratti del sito auditato) restano nella lingua del sito.
_FINDINGS_EN: Dict[str, Dict[str, str]] = {
    "tech.robots.missing": {
        "title": "robots.txt not reachable",
        "detail": "Request to %(url)s failed or returned non-200.",
        "fix": "Publish a robots.txt that declares the sitemap.",
    },
    "tech.robots.present": {
        "title": "robots.txt present",
        "detail": "%(n)d lines.",
    },
    "tech.robots.ai_blocked": {
        "title": "AI crawlers blocked: %(agents)s",
        "detail": "These agents cannot access the home page. If "
                  "they are blocked you enter no retrieval list "
                  "and RRF has nothing to fuse.",
        "fix": "Remove the Disallow rules for the agents you want "
               "to be cited by.",
        "example": "# robots.txt - unblock the AI agents\n"
                   "User-agent: GPTBot\nDisallow:\n\n"
                   "User-agent: ClaudeBot\nDisallow:\n\n"
                   "User-agent: PerplexityBot\nDisallow:",
    },
    "tech.robots.ai_allowed": {
        "title": "AI crawlers allowed",
        "detail": "Verified: %(agents)s.",
    },
    "tech.robots.sitemap_ok": {
        "title": "Sitemap declared in robots.txt",
        "detail": "%(urls)s",
    },
    "tech.robots.sitemap_missing": {
        "title": "No sitemap declared in robots.txt",
        "fix": "Add the line 'Sitemap: https://.../sitemap.xml'.",
        "example": "# at the end of robots.txt\n"
                   "Sitemap: https://esempio.it/sitemap.xml",
    },
    "tech.llms.present": {
        "title": "llms.txt present",
        "detail": "%(n)d lines.",
    },
    "tech.llms.missing": {
        "title": "llms.txt missing",
        "detail": "Emerging standard (llmstxt.org): a Markdown "
                  "index of the key content meant for AI agents.",
        "fix": "Consider publishing /llms.txt with your key "
               "content.",
    },
    "tech.links.orphans": {
        "title": "%(n)d page(s) with no incoming internal links "
                 "(orphans)",
        "detail": "Reachable only from the sitemap: %(urls)s. A "
                  "page nobody links to gets fewer crawls and "
                  "less weight.",
        "fix": "Link them from related pages (body copy, menu or "
               "footer).",
        "example": "From the related page:\n"
                   "<a href=\"/servizio-collegato/\">descriptive "
                   "name of the service</a>",
    },
    "tech.links.no_orphans": {
        "title": "Every page has incoming internal links",
    },
    "tech.links.deep": {
        "title": "%(n)d page(s) more than 3 clicks from the home "
                 "page",
        "detail": "%(urls)s.",
        "fix": "Shorten the paths: deep pages get crawled and "
               "weighted less.",
    },
    "tech.links.generic_anchors": {
        "title": "%(n)d generic anchors in internal links",
        "detail": "Texts like \"click here\" or \"read more\" say "
                  "nothing about the destination content.",
        "fix": "Use descriptive anchors with the destination "
               "page's terms.",
    },
    "tech.redirect.http_left": {
        "title": "%(n)d internal URLs still on http",
        "detail": "Redirected to the https version: %(urls)s. "
                  "Every hop wastes crawl budget and dilutes the "
                  "signals.",
        "fix": "Update sitemap and internal links to the final "
               "https URLs.",
        "example": "<!-- before --> <a href=\"http://esempio.it/"
                   "servizio/\">\n<!-- after  --> "
                   "<a href=\"https://esempio.it/servizio/\">",
    },
    "tech.redirect.www_mixed": {
        "title": "%(n)d URLs with mixed www/non-www host",
        "detail": "Redirected to the canonical host: %(urls)s.",
        "fix": "Use a single host (with or without www) in the "
               "sitemap and internal links.",
    },
    "tech.redirect.moved": {
        "title": "%(n)d internal URLs answer with a redirect",
        "detail": "Moved URLs: %(urls)s.",
        "fix": "Update sitemap and internal links to the final "
               "destination of the redirects.",
        "example": "In the sitemap and internal links use the "
                   "landing URL directly:\n<url><loc>https://"
                   "esempio.it/nuova-pagina/</loc></url>",
    },
    "tech.redirect.chains": {
        "title": "%(n)d URLs with a multi-hop redirect chain",
        "detail": "%(urls)s.",
        "fix": "Point every redirect straight to the final "
               "destination (a single hop).",
        "example": "# one hop, not a chain\n"
                   "Redirect 301 /vecchia/ "
                   "https://esempio.it/nuova/\n"
                   "# NOT: /vecchia/ -> /intermedia/ -> /nuova/",
    },
    "tech.redirect.none": {
        "title": "No internal redirects",
        "detail": "Every analysed URL answers directly.",
    },
    "tech.msft.noarchive": {
        "title": "%(n)d page(s) excluded from Copilot (noarchive)",
        "detail": "The noarchive meta excludes the content from "
                  "Bing Chat/Copilot answers and from Microsoft "
                  "model training (classic search is unaffected): "
                  "on these pages citability on the Microsoft "
                  "channel is zero. %(urls)s",
        "fix": "If the exclusion is unintended remove noarchive; "
               "for a partial presence (title, URL and snippet "
               "only) use nocache.",
    },
    "tech.msft.nocache": {
        "title": "%(n)d page(s) with partial presence in Copilot "
                 "(nocache)",
        "detail": "With nocache, Bing Chat/Copilot shows only the "
                  "page's URL, title and snippet and uses only "
                  "those elements for Microsoft training. "
                  "%(urls)s",
        "fix": "A legitimate partial opt-out: just check it is "
               "intended. For full citability on Copilot remove "
               "the meta.",
    },
    "tech.msft.no_optout": {
        "title": "No Microsoft AI opt-out active",
        "detail": "There is no robots.txt token dedicated to "
                  "Microsoft's AI: control goes through the "
                  "noarchive/nocache metas, absent here. Your "
                  "content can therefore be used in Copilot "
                  "answers and Microsoft training; to opt out use "
                  "noarchive (full) or nocache (partial).",
    },
    "tech.anchors.varied": {
        "title": "Varied internal anchor profile",
        "detail": "%(texts)d unique texts over %(pairs)d "
                  "text-destination pairs (%(pct).0f%%; common "
                  "practice threshold: %(threshold).0f%%).",
    },
    "tech.anchors.repetitive": {
        "title": "Repetitive internal anchor profile",
        "detail": "%(texts)d unique texts over %(pairs)d "
                  "text-destination pairs (%(pct).0f%%, common "
                  "practice threshold %(threshold).0f%%): the "
                  "same text leads to different destinations and "
                  "the reader — human or model — cannot predict "
                  "where the link goes. %(examples)s",
        "fix": "Use descriptive anchors, distinct per "
               "destination: the link text must say what is on "
               "the other side.",
        "example": "Before: \"Read more\" -> /servizi, \"Read "
                   "more\" -> /prezzi\n"
                   "After:  \"All lymphatic drainage services\" "
                   "-> /servizi, \"Session prices\" -> /prezzi",
    },
    "tech.meta.charset": {
        "title": "%(n)d page(s) without a declared charset",
        "detail": "%(urls)s",
        "fix": "Declare the encoding at the top of the <head>.",
    },
    "tech.meta.viewport": {
        "title": "%(n)d page(s) without a viewport meta",
        "detail": "Without a viewport the mobile rendering is "
                  "undeclared: %(urls)s",
        "fix": "Add the responsive viewport.",
    },
    "tech.meta.og_missing": {
        "title": "%(n)d page(s) without Open Graph",
        "detail": "Previews in shared links (and in many "
                  "assistant answers) are built from the og:* "
                  "tags: without them, whoever pastes the link "
                  "decides the title and image. %(urls)s",
        "fix": "Add at least the og:title, og:description, "
               "og:image triad.",
    },
    "tech.meta.og_partial": {
        "title": "Incomplete Open Graph on %(n)d page(s)",
        "detail": "%(urls)s",
        "fix": "Complete the og:title, og:description, og:image "
               "triad.",
    },
    "tech.meta.ok": {
        "title": "Basic metas in order",
        "detail": "charset, viewport and Open Graph complete on "
                  "all %(n)d analysed pages.",
    },
    "tech.https.missing": {
        "title": "Site not on HTTPS",
        "fix": "Enable a TLS certificate and redirect everything "
               "to HTTPS.",
    },
    "tech.https.ok": {
        "title": "HTTPS active",
    },
    "tech.pages.broken": {
        "title": "%(n)d URLs unreachable or failing",
        "detail": "%(urls)s",
        "fix": "Fix the failing URLs or remove them from the "
               "sitemap.",
    },
    "tech.pages.soft404": {
        "title": "%(n)d possible soft-404s (200 with \"not "
                 "found\" content)",
        "detail": "They answer 200 but the content says the page "
                  "does not exist: %(urls)s. They enter the index "
                  "as empty pages and dilute the site's signals.",
        "fix": "Make non-existent URLs answer 404 (or 410) and "
               "remove the empty ones from the sitemap.",
        "example": "The non-existent page must answer with status "
                   "404, not 200:\n# Apache (.htaccess)\n"
                   "ErrorDocument 404 /404.html\n"
                   "# no redirect to the home instead of the 404",
    },
    "tech.pages.none": {
        "title": "No analysable page",
        "detail": "No URL returned valid HTML: the site is "
                  "unreachable, blocks the tool's user-agent or "
                  "only responds to JavaScript. The content audit "
                  "was not performed.",
        "fix": "Check that the site responds and does not filter "
               "crawlers.",
    },
    "tech.pages.single": {
        "title": "Minimal indexable surface (1 page)",
        "detail": "With a single document the RRF sum has no "
                  "addends: there are no distinct passages to "
                  "surface.",
        "fix": "Create standalone pages for every topic/service.",
    },
    "tech.pages.few": {
        "title": "Few indexable pages (%(n)d)",
        "fix": "Widen the surface: one page per intent.",
    },
    "tech.pages.ok": {
        "title": "%(n)d indexable pages analysed",
        "detail": "First pages: %(urls)s.",
    },
    "tech.sitemap.missing": {
        "title": "XML sitemap missing or unreadable",
        "detail": "URLs discovered by crawling internal links.",
        "fix": "Publish an XML sitemap and declare it in "
               "robots.txt.",
    },
    "tech.pages.placeholder": {
        "title": "%(n)d indexable placeholder page(s)",
        "detail": "Detected: %(urls)s. They are default CMS "
                  "content: pure noise in the index and a signal "
                  "of an unfinished site.",
        "fix": "Delete them, or set noindex and remove them from "
               "the sitemap.",
    },
    "tech.pages.noindex": {
        "title": "%(n)d page(s) with a noindex robots meta",
        "detail": "%(urls)s",
        "fix": "Check the exclusion is intended.",
        "example": "If the page must be indexed, remove the meta "
                   "or use:\n<meta name=\"robots\" "
                   "content=\"index, follow\">",
    },
    "tech.canonical.missing": {
        "title": "%(n)d page(s) without a canonical",
        "detail": "%(urls)s",
        "fix": "Declare <link rel=\"canonical\"> on every page.",
    },
    "tech.canonical.ok": {
        "title": "Canonicals present",
        "detail": "Declared on all %(n)d analysed pages.",
    },
    "tech.lang.missing": {
        "title": "%(n)d page(s) without a lang attribute",
        "fix": "Set <html lang=\"it\">: it helps language-model "
               "selection during analysis.",
    },
    "tech.js.heavy": {
        "title": "%(n)d page(s) with little text and heavy "
                 "JavaScript",
        "detail": "The content may be rendered client-side and "
                  "not be seen by crawlers.",
        "fix": "Enable server-side rendering or pre-rendering.",
    },
    "tech.js.rendered": {
        "title": "%(n)d page(s) with little text and heavy "
                 "JavaScript",
        "detail": "The content was analysed with JavaScript "
                  "rendering, but crawlers that do not run "
                  "JavaScript (most AI crawlers) still cannot "
                  "see it.",
        "fix": "Enable server-side rendering or pre-rendering.",
    },
    "tech.js.ok": {
        "title": "Content present in the initial HTML",
    },
    "tech.slow": {
        "title": "%(n)d page(s) answering in more than 2 s",
        "detail": "Slowest: %(worst).2f s.",
        "fix": "Optimise caching and TTFB.",
    },
    "tech.hreflang.missing": {
        "title": "Multilingual site without hreflang",
        "detail": "Detected languages: %(langs)s.",
        "fix": "Declare reciprocal hreflang between the "
               "versions.",
    },
    "tech.hreflang.na": {
        "title": "Single-language site: hreflang not needed",
    },
    "lex.clickbait.found": {
        "title": "%(n)d titles or headings with clickbait "
                 "formulas",
        "detail": "Sensationalist formulas and multiple "
                  "exclamation marks attract the click but answer "
                  "nothing: generative engines select informative "
                  "titles. %(examples)s",
        "fix": "Rewrite in an informative style: the benefit or "
               "the answer in the title, no hyperbole.",
        "example": "Before: \"You won't believe what drainage "
                   "does!!\"\nAfter:  \"Lymphatic drainage: "
                   "benefits, duration and cost of a session\"",
    },
    "lex.clickbait.none": {
        "title": "No clickbait formula in titles and headings",
        "detail": "Informative-style titles on all %(n)d analysed "
                  "pages.",
    },
    "lex.title.missing": {
        "title": "%(n)d page(s) without a <title>",
        "fix": "The title is the highest-weight lexical signal.",
    },
    "lex.title.bad": {
        "title": "%(n)d titles not optimised",
        "detail": "Examples: %(examples)s",
        "fix": "Unique title, 30-65 characters, with the real "
               "search terms; avoid the domain name as a title.",
        "example": "<title>Drenaggio linfatico manuale a Parma | "
                   "Centro Esempio</title>\n"
                   "(52 characters: service + territory + brand)",
    },
    "lex.title.dup": {
        "title": "%(n)d titles duplicated across pages",
        "detail": "%(examples)s",
        "fix": "Every page must have a distinct title.",
    },
    "lex.title.ok": {
        "title": "Titles well set up",
    },
    "lex.desc.missing": {
        "title": "%(n)d page(s) without a meta description",
        "detail": "%(urls)s",
        "fix": "Write 110-165 characters with service and "
               "territory.",
    },
    "lex.desc.short": {
        "title": "%(n)d meta descriptions too short",
        "detail": "Examples: %(examples)s",
        "fix": "A description that only repeats the company name "
               "carries no signal.",
    },
    "lex.desc.long": {
        "title": "%(n)d meta descriptions above %(max)d "
                 "characters",
    },
    "lex.desc.ok": {
        "title": "Meta descriptions present and of adequate "
                 "length",
    },
    "lex.h1.missing": {
        "title": "%(n)d page(s) without an H1",
        "detail": "%(urls)s",
        "fix": "A single H1 per page, with the main terms.",
    },
    "lex.h1.multi": {
        "title": "%(n)d page(s) with multiple H1s",
    },
    "lex.h1.ok": {
        "title": "Correct H1 structure",
    },
    "lex.words.thin": {
        "title": "%(n)d page(s) below %(min)d words",
        "detail": "Site average: %(avg)d words. With so little "
                  "text the useful terms never reach a frequency "
                  "BM25 can reward.",
        "fix": "Bring the key pages towards %(target)d+ words of "
               "informative, non-promotional content.",
        "example": "Typical structure for a service page:\n"
                   "<h2>What is ...?</h2> <h2>How a session "
                   "works</h2>\n<h2>When it is needed</h2> "
                   "<h2>How much it costs</h2> <h2>FAQ</h2>",
    },
    "lex.words.ok": {
        "title": "Adequate text volume",
        "detail": "Average: %(avg)d words per page.",
    },
    "lex.acronyms.bare": {
        "title": "Acronyms used without their expanded form",
        "detail": "Not spelled out: %(list)s.",
        "fix": "Write 'ACRONYM (expanded form)' at least at the "
               "first occurrence: it covers both search "
               "phrasings.",
    },
    "lex.acronyms.ok": {
        "title": "Acronyms accompanied by their expanded form",
        "detail": "%(list)s",
    },
    "lex.slug.bad": {
        "title": "%(n)d slugs that say little",
        "detail": "%(slugs)s",
        "fix": "Use topical slugs with hyphens.",
    },
    "lex.slug.ok": {
        "title": "Topical, readable slugs",
    },
    "lex.alt.partial": {
        "title": "Incomplete alt attributes (%(with_alt)d/"
                 "%(total)d)",
        "fix": "The alt is indexable text as well as "
               "accessibility.",
    },
    "lex.alt.ok": {
        "title": "Alt attributes present (%(with_alt)d/"
                 "%(total)d)",
    },
    "sem.extract.ok": {
        "title": "Good direct extractability",
        "detail": "%(direct)d paragraphs out of %(total)d open "
                  "with an explicit answer in %(min)d-%(max)d "
                  "words (%(pct).0f%% against a common practice "
                  "threshold of %(threshold).0f%%): these are the "
                  "passages an assistant can quote as they are.",
    },
    "sem.extract.low": {
        "title": "Few direct-answer paragraphs",
        "detail": "%(direct)d paragraphs out of %(total)d open "
                  "with an explicit answer in %(min)d-%(max)d "
                  "words (%(pct).0f%% against a common practice "
                  "threshold of %(threshold).0f%%): these are the "
                  "passages an assistant can quote as they are.",
        "fix": "Rewrite the key paragraphs opening with the "
               "answer (\"X is ...\", \"Yes, ...\", \"In short "
               "...\") and keep them between %(min)d and %(max)d "
               "words.",
        "example": "Before: \"In today's wellness landscape, many "
                   "people wonder which path...\"\n"
                   "After:  \"Lymphatic drainage is a gentle "
                   "massage that eases lymph flow: a session "
                   "lasts 45 minutes and costs 40-80 euros.\"",
    },
    "sem.filler.saturated": {
        "title": "%(n)d page(s) saturated with marketing "
                 "formulas",
        "detail": "Filler takes up space without saying anything "
                  "extractable (common practice threshold: at "
                  "least %(min)d formulas and one every 100 "
                  "words). %(examples)s",
        "fix": "Replace the generic formulas with verifiable "
               "information: numbers, durations, prices, "
               "procedures.",
        "example": "Before: \"We are market leaders, quality and "
                   "professionalism at your service.\"\n"
                   "After:  \"Since 2012 we have followed more "
                   "than 400 post-surgery patients; the first "
                   "evaluation is free and takes 30 minutes.\"",
    },
    "sem.filler.ok": {
        "title": "Marketing filler under control",
        "detail": "%(n)d generic formulas across the whole site: "
                  "useful text dominates.",
    },
    "sem.lifecycle.ok": {
        "title": "Topic life cycle covered (%(n)d of 6)",
        "detail": "Sections found in the headings: %(found)s.",
    },
    "sem.lifecycle.partial": {
        "title": "Topic life cycle incomplete (%(n)d of 6)",
        "detail": "A complete treatment covers definition, "
                  "history, use cases, limits, FAQ and outlook: "
                  "it is the content generative engines can cite "
                  "for every angle of a question. %(found)s "
                  "Missing: %(missing)s.",
        "fix": "Add the missing sections with explicit headings "
               "(they can be spread across several pages).",
    },
    "sem.fresh.ok": {
        "title": "Recently updated content",
        "detail": "Most recent declared update: %(date)s on "
                  "%(url)s (%(days)d days ago).",
    },
    "sem.fresh.stale": {
        "title": "Content untouched for over a year",
        "detail": "The most recent declared update is from "
                  "%(date)s (%(days)d days ago). Generative "
                  "engines prefer maintained sources: a frozen "
                  "date signals possibly outdated content. Oldest "
                  "pages: %(stale)s.",
        "fix": "Review the key content and declare the update "
               "with article:modified_time or dateModified in "
               "the JSON-LD.",
    },
    "sem.fresh.very_stale": {
        "title": "Content untouched for over two years",
        "detail": "The most recent declared update is from "
                  "%(date)s (%(days)d days ago). Generative "
                  "engines prefer maintained sources: a frozen "
                  "date signals possibly outdated content. Oldest "
                  "pages: %(stale)s.",
        "fix": "Review the key content and declare the update "
               "with article:modified_time or dateModified in "
               "the JSON-LD.",
    },
    "sem.refs.ok": {
        "title": "References to sources present",
        "detail": "%(context)s (common practice threshold: a "
                  "sources section or at least %(threshold)d "
                  "citations).",
    },
    "sem.refs.missing": {
        "title": "No reference to external sources",
        "detail": "%(context)s. Citing sources strengthens "
                  "E-E-A-T signals and gives AI assistants "
                  "something to verify: referenced content is "
                  "more citable.",
        "fix": "Add a \"Sources\" section with links to "
               "guidelines, studies or official documentation "
               "(or citations in the text).",
    },
    "sem.chunks.none": {
        "title": "No extractable chunk",
        "detail": "The site offers no indexable text passages.",
        "fix": "Write discursive paragraphs of at least 40-50 "
               "words.",
    },
    "sem.chunks.ok": {
        "title": "%(chunks)d indexable chunks across %(pages)d "
                 "pages",
        "detail": "Every chunk is a chance to appear in the "
                  "lists: in the RRF sum the number of relevant "
                  "passages is the real multiplier.",
    },
    "sem.chunks.few": {
        "title": "%(chunks)d indexable chunks across %(pages)d "
                 "pages",
        "detail": "Every chunk is a chance to appear in the "
                  "lists: in the RRF sum the number of relevant "
                  "passages is the real multiplier.",
        "fix": "Increase the number of self-contained topical "
               "passages.",
    },
    "sem.anaphora.high": {
        "title": "%(pct).0f%% of the chunks are not "
                 "self-contained",
        "detail": "They open with an anaphoric reference (this, "
                  "such, that...): extracted on their own they "
                  "answer nothing. Examples: %(examples)s.",
        "fix": "Rewrite the openings naming the subject "
               "explicitly.",
        "example": "Before: \"This treatment is indicated after "
                   "surgery.\"\nAfter:  \"Manual lymphatic "
                   "drainage is indicated after surgery.\"",
    },
    "sem.anaphora.ok": {
        "title": "Chunks largely self-contained (%(pct).0f%% "
                 "anaphoric)",
    },
    "sem.questions.few": {
        "title": "Almost no question-form heading (%(n)d of "
                 "%(total)d)",
        "detail": "It is the format AI engines cite most often: "
                  "an explicit question followed by a direct "
                  "answer.",
        "fix": "Add headings like \"What is X?\", \"How does X "
               "work?\", \"How much does X cost?\" with a crisp "
               "2-3 line answer.",
    },
    "sem.questions.ok": {
        "title": "%(n)d question-form headings (%(pct).0f%%)",
        "detail": "Examples: %(examples)s.",
    },
    "sem.faq.ok": {
        "title": "FAQ section detected",
        "detail": "Detected on %(url)s.",
    },
    "sem.faq.missing": {
        "title": "No FAQ section",
        "detail": "FAQs align a chunk with a precise intent and "
                  "feed both axes at the same time.",
        "fix": "Add per-page FAQs, marked up with FAQPage "
               "JSON-LD.",
    },
    "sem.defs.low": {
        "title": "Content poor in definitions (%(pct).0f%% of "
                 "chunks)",
        "detail": "Without passages explaining *what* something "
                  "is, the embeddings stay far from "
                  "informational queries.",
        "fix": "For every topic add: what it is / how it works / "
               "when it is needed / an example.",
    },
    "sem.defs.ok": {
        "title": "Defining passages present (%(pct).0f%% of "
                 "chunks)",
    },
    "sem.examples.few": {
        "title": "Almost no concrete example",
        "fix": "Examples and case studies are the content with "
               "the highest semantic density.",
    },
    "sem.examples.ok": {
        "title": "%(n)d chunks with concrete examples",
    },
    "sem.vocab.narrow": {
        "title": "Narrow vocabulary (%(n)d distinct terms)",
        "detail": "Little lexical variety means limited semantic "
                  "coverage: you intercept few rephrasings of "
                  "the same question.",
        "fix": "Broaden the topics covered and the phrasings "
               "used.",
    },
    "sem.vocab.ok": {
        "title": "Broad vocabulary (%(n)d distinct terms)",
    },
    "sem.eeat.author.ok": {
        "title": "E-E-A-T: content author declared",
    },
    "sem.eeat.author.missing": {
        "title": "E-E-A-T: no author declared",
        "fix": "Add the author meta or the author property in "
               "the JSON-LD: AI engines weigh who signs the "
               "content.",
    },
    "sem.eeat.dates.ok": {
        "title": "E-E-A-T: publication/update dates present",
    },
    "sem.eeat.dates.missing": {
        "title": "E-E-A-T: no publication or update date",
        "fix": "Expose article:published_time/modified_time or "
               "datePublished/dateModified in the JSON-LD.",
    },
    "sem.eeat.about.ok": {
        "title": "E-E-A-T: \"about us\" page present",
    },
    "sem.eeat.about.missing": {
        "title": "E-E-A-T: no \"about us\" page detected",
        "fix": "A page introducing people and expertise is the "
               "most direct experience signal.",
        "example": "Create /chi-siamo/ with: who curates the "
                   "content, titles and training,\nsince when, "
                   "real photos. Link it from every page's "
                   "footer.",
    },
    "sem.eeat.contact.ok": {
        "title": "E-E-A-T: verifiable contacts present",
    },
    "sem.eeat.contact.missing": {
        "title": "E-E-A-T: no verifiable contact detected",
        "fix": "Expose phone and email (tel:/mailto: links) or a "
               "contact page.",
    },
    "sd.semantic.poor": {
        "title": "%(n)d page(s) without semantic markup",
        "detail": "Fewer than %(min)d sectioning tag types "
                  "(article, section, main, figure...): the "
                  "chunkers of generative engines have fewer "
                  "hooks to segment the content into coherent "
                  "blocks. %(urls)s",
        "fix": "Wrap the main content in <main> and <article>, "
               "topical sections in <section> with their "
               "heading, images and captions in <figure>.",
    },
    "sd.semantic.divitis": {
        "title": "%(n)d page(s) with an excess of <div> "
                 "(divitis)",
        "detail": "More than half the elements are a generic "
                  "<div>: %(urls)s.",
        "fix": "Replace structural <div>s with the equivalent "
               "semantic tags: the markup becomes "
               "self-describing.",
    },
    "sd.semantic.ok": {
        "title": "Semantic markup in use",
        "detail": "All %(n)d analysable pages use sectioning "
                  "tags and keep <div>s below %(max)d%% of the "
                  "elements.",
    },
    "sd.jsonld.none": {
        "title": "No JSON-LD structured data",
        "detail": "Without markup the entity is not recognised "
                  "and the content is not eligible for rich "
                  "results.",
        "fix": "Add at least Organization (or LocalBusiness), "
               "then Service, FAQPage, BreadcrumbList, Article.",
    },
    "sd.jsonld.ok": {
        "title": "JSON-LD present",
        "detail": "Detected types: %(types)s.",
    },
    "sd.entity.missing": {
        "title": "Main entity not declared",
        "fix": "Add Organization or LocalBusiness with name, "
               "address, contacts and tax identifiers.",
    },
    "sd.entity.ok": {
        "title": "Main entity declared",
    },
    "sd.type.faqpage": {
        "title": "FAQPage markup missing",
        "detail": "Marked-up FAQs are the format AI engines cite "
                  "the most.",
        "fix": "Add the FAQPage type where relevant.",
    },
    "sd.type.breadcrumblist": {
        "title": "BreadcrumbList markup missing",
        "detail": "It clarifies the site hierarchy.",
        "fix": "Add the BreadcrumbList type where relevant.",
    },
    "sd.type.website": {
        "title": "WebSite markup missing",
        "detail": "Useful for the sitelinks searchbox.",
        "fix": "Add the WebSite type where relevant.",
    },
    "sd.jsonld.partial": {
        "title": "JSON-LD on only %(covered)d pages out of "
                 "%(total)d",
        "fix": "Extend the markup to all relevant pages.",
    },
    "sd.check.incomplete": {
        "title": "Incomplete JSON-LD for %(n)d type(s)",
        "fix": "Complete the listed properties: without them the "
               "type is not eligible for rich results.",
    },
    "sd.check.faq": {
        "title": "%(n)d incomplete FAQPage question(s)",
        "detail": "Every mainEntity item requires a Question "
                  "with name and an acceptedAnswer with text.",
        "fix": "Complete the question/answer pairs in the "
               "markup.",
    },
    "sd.check.offers": {
        "title": "%(n)d issue(s) in offer prices",
        "fix": "In price only the number with a decimal point "
               "(no currency symbols); the currency in "
               "priceCurrency (ISO 4217 code, e.g. EUR).",
    },
    "sd.check.product": {
        "title": "%(n)d Product without offers or reviews",
        "detail": "A Product without offers, review and "
                  "aggregateRating is not eligible for product "
                  "rich results.",
        "fix": "Add at least offers (with price and "
               "priceCurrency) or review/aggregateRating.",
    },
    "sd.check.rating": {
        "title": "%(n)d inconsistent rating(s)",
        "fix": "ratingValue inside the declared scale (default "
               "1-5) and the review count in reviewCount or "
               "ratingCount.",
    },
    "sd.check.dates": {
        "title": "%(n)d date(s) not in ISO 8601 format",
        "detail": "%(list)s.",
        "fix": "Use YYYY-MM-DD, with the optional time after the "
               "T (e.g. 2026-08-03T09:30:00+02:00).",
    },
    "sd.check.urls": {
        "title": "%(n)d non-absolute media URLs in the markup",
        "detail": "%(list)s.",
        "fix": "image, logo, thumbnailUrl, contentUrl and "
               "embedUrl require full http(s) URLs.",
    },
    "sd.check.ok": {
        "title": "Consistent Schema.org markup (%(n)d types "
                 "verified)",
        "detail": "Verified: %(types)s.",
    },
    "rrf.not_runnable": {
        "title": "RRF simulation not runnable",
        "detail": "At least one chunk and one query are needed.",
    },
    "rrf.consensus.low": {
        "title": "Average consensus between the lists: "
                 "%(avg).1f/%(top_n)d (%(pct).0f%%)",
        "detail": "The two lists point to different passages: no "
                  "document accumulates score on both axes. In "
                  "the RRF formula a document present in both "
                  "lists sums two 1/(k+rank) addends and beats "
                  "one that dominates a single list. Consensus "
                  "per query: %(per_query)s.",
        "fix": "Optimise the same passages on both axes: "
               "explicit terms (BM25) and a complete explanation "
               "(vector).",
        "example": "Before (lexical only): \"Lymphatic drainage. "
                   "Call for info.\"\nAfter (both axes): \"Manual "
                   "lymphatic drainage is a gentle massage\nthat "
                   "eases lymph flow: a session lasts 45 minutes"
                   "\nand the typical cycle is 5 to 10 visits.\"",
    },
    "rrf.consensus.mid": {
        "title": "Average consensus between the lists: "
                 "%(avg).1f/%(top_n)d (%(pct).0f%%)",
        "detail": "Partial consensus between the two retrievers. "
                  "In the RRF formula a document present in both "
                  "lists sums two 1/(k+rank) addends and beats "
                  "one that dominates a single list. Consensus "
                  "per query: %(per_query)s.",
        "fix": "Optimise the same passages on both axes: "
               "explicit terms (BM25) and a complete explanation "
               "(vector).",
    },
    "rrf.consensus.good": {
        "title": "Average consensus between the lists: "
                 "%(avg).1f/%(top_n)d (%(pct).0f%%)",
        "detail": "Good overlap between lexical and vector "
                  "retrieval. In the RRF formula a document "
                  "present in both lists sums two 1/(k+rank) "
                  "addends and beats one that dominates a single "
                  "list. Consensus per query: %(per_query)s.",
    },
    "rrf.uncovered": {
        "title": "%(n)d queries with no result at all",
        "detail": "No chunk of the site answers: %(queries)s.",
        "fix": "Create content dedicated to these intents.",
        "example": "For every uncovered query, a section with a "
                   "heading equal to the question:\n"
                   "<h2>How much does lymphatic drainage cost?"
                   "</h2>\n<p>A session costs on average 40-80 "
                   "euros, depending on duration and treated "
                   "area.</p>",
    },
    "rrf.covered": {
        "title": "All %(n)d queries find at least one passage",
        "detail": "Verified queries: %(queries)s.",
    },
    "rrf.comp.empty": {
        "title": "Competitor %(host)s with no retrievable "
                 "content",
        "detail": "No analysable page: the comparison includes "
                  "it with 0 passages.",
    },
    "rrf.comp.not_runnable": {
        "title": "Competitive comparison not runnable",
        "detail": "At least one chunk and one query are needed.",
    },
    "rrf.share.low": {
        "title": "Share of voice: %(pct).0f%% of the first "
                 "%(top_n)d fused slots (parity %(parity).0f%%)",
        "detail": "Competitors occupy the slots you would need: "
                  "on your own topics you are rarely retrieved. "
                  "Breakdown: %(breakdown)s.",
        "fix": "Strengthen the passages on the queries where "
               "competitors beat you: same explicit terms, "
               "complete answer.",
    },
    "rrf.share.mid": {
        "title": "Share of voice: %(pct).0f%% of the first "
                 "%(top_n)d fused slots (parity %(parity).0f%%)",
        "detail": "You are below parity: on your topics "
                  "competitors get retrieved more often than "
                  "you. Breakdown: %(breakdown)s.",
        "fix": "Strengthen the passages on the queries where "
               "competitors beat you: same explicit terms, "
               "complete answer.",
    },
    "rrf.share.good": {
        "title": "Share of voice: %(pct).0f%% of the first "
                 "%(top_n)d fused slots (parity %(parity).0f%%)",
        "detail": "You hold your own against competitors on your "
                  "topics. Breakdown: %(breakdown)s.",
    },
    "rrf.comp.lost": {
        "title": "%(n)d queries out of %(total)d won entirely by "
                 "competitors",
        "detail": "None of your passages in the first %(top_n)d "
                  "for: %(queries)s.",
        "fix": "Create or rewrite content dedicated to these "
               "intents.",
    },
    "rrf.comp.present": {
        "title": "Present in the first %(top_n)d for all %(n)d "
                 "queries",
        "detail": "Comparison queries: %(queries)s.",
    },
    "tech.robots.own": {
        "title": "Site declared as your own",
        "detail": "The robots.txt Disallow rules are not applied "
                  "to the audited site (--own-site); they still "
                  "apply to any competitors.",
    },
    "tech.robots.forced": {
        "title": "robots.txt Disallow rules ignored on explicit "
                 "request",
        "detail": "Crawling beyond the Disallow rules was "
                  "enabled with --ignore-robots %(ack)s: "
                  "responsibility for the crawl was explicitly "
                  "assumed by the user.",
    },
    "tech.robots.excluded": {
        "title": "%(n)d URLs excluded out of respect for "
                 "robots.txt",
        "detail": "Disallow rules addressed to the %(agent)s "
                  "agent are respected (default behaviour): "
                  "%(urls)s. Use --own-site if the site is "
                  "yours.",
    },
    "tech.render.done": {
        "title": "%(n)d page(s) analysed with JavaScript "
                 "rendering",
        "detail": "Mode --render %(mode)s: the content comes "
                  "from the DOM rendered in a headless browser; "
                  "HTTP status, redirects and timings remain "
                  "those of the original response.",
    },
    "tech.render.failed": {
        "title": "Rendering failed for %(n)d page(s)",
        "detail": "For these pages the static HTML was "
                  "analysed.",
        "fix": "Retry, or raise the timeout if the site is "
               "slow.",
    },
    "tech.pages.duplicates": {
        "title": "%(n)d URLs serve identical content",
        "detail": "The same text is reachable from several "
                  "addresses: %(urls)s. Duplicates add no "
                  "addends to the RRF sum, dilute the signals "
                  "and waste crawl budget.",
        "fix": "Pick one canonical URL and redirect the others "
               "with a 301.",
    },
}


def finding_texts(source: object, lang: str = "it") -> Dict[str, str]:
    """Testi (title/detail/fix/example) nella lingua del referto.

    ``source`` e' un Finding oppure un dict con le stesse chiavi
    (es. voci del piano di remediation). Con "it", senza chiave o
    senza voce in catalogo restano i testi italiani canonici; un
    template incoerente coi params non interrompe mai il rendering
    (ripiega sull'italiano campo per campo).
    """
    if isinstance(source, Finding):
        data = {"title": source.title, "detail": source.detail,
                "fix": source.fix, "example": source.example}
        key: str = source.key
        params: Dict[str, object] = source.params
    else:
        src = dict(source)  # type: ignore[call-overload]
        data = {name: str(src.get(name) or "")
                for name in ("title", "detail", "fix", "example")}
        key = str(src.get("key") or "")
        params = dict(src.get("params") or {})  # type: ignore
    if lang == "it" or not key:
        return data
    if key.startswith("lh."):
        return _lighthouse_texts_en(data, key, params)
    entry = _FINDINGS_EN.get(key) or {}
    for name, template in entry.items():
        try:
            data[name] = template % params
        except (KeyError, TypeError, ValueError):
            pass  # parametri incoerenti: resta l'italiano
    return data


def _lighthouse_texts_en(data: Dict[str, str], key: str,
                         params: Dict[str, object]
                         ) -> Dict[str, str]:
    """Testi inglesi dei rilievi Lighthouse (decisione i18n P1).

    Il catalogo e' Lighthouse stesso: il parser salva nei params i
    testi inglesi presi dai file di locale del fork (``title_en``,
    ``fix_en``, ``cat_title_en`` via icuMessagePaths del LHR) e qui
    si ricompongono con la cornice inglese (Pages/Evidence/Score).
    Campo per campo: senza testo inglese resta l'italiano, lo
    stesso fallback dichiarato del catalogo _FINDINGS_EN.
    """
    out = dict(data)
    if key == "lh.run.errors":
        try:
            n = int(params.get("n", 0))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return out
        out["title"] = ("Lighthouse did not complete on %d page%s"
                        % (n, "" if n == 1 else "s"))
        return out
    if key.endswith(".ok"):
        cat_en = str(params.get("cat_title_en") or "")
        if cat_en:
            out["title"] = "Lighthouse %s: no findings" % cat_en
        try:
            pages = int(params.get("pages", 0))  # type: ignore
            out["detail"] = ("Score %d/100 on %d page%s examined."
                             % (int(params.get("score", 0)),  # type: ignore
                                pages, "" if pages == 1 else "s"))
        except (TypeError, ValueError):
            pass
        return out
    title_en = str(params.get("title_en") or "")
    if title_en:
        out["title"] = "Lighthouse: %s" % title_en
    fix_en = str(params.get("fix_en") or "")
    if fix_en:
        out["fix"] = _strip_md_links(fix_en)
    parts: List[str] = []
    display = str(params.get("display") or "")
    if display:
        parts.append(display)
    urls = str(params.get("urls") or "")
    if urls:
        parts.append("Pages: %s" % urls)
    evidence = params.get("evidence")
    if isinstance(evidence, list) and evidence:
        parts.append("Evidence: %s"
                     % "; ".join(str(e) for e in evidence))
    if parts:
        out["detail"] = "; ".join(parts)
    return out


def _finding_anchor(area: str, title: str,
                    seen: Dict[str, int]) -> str:
    """Ancora stabile di un rilievo nel referto HTML.

    Come in ``_finding_key``, i numeri nel titolo diventano "n":
    il link resta valido fra esecuzioni successive sullo stesso
    sito anche quando i conteggi cambiano. I duplicati nello
    stesso referto prendono un suffisso progressivo.
    """
    raw = "%s-%s" % (area, re.sub(r"\d+", "n", title))
    slug = re.sub(r"[^a-z0-9]+", "-", raw.lower()).strip("-")[:70]
    slug = "r-" + (slug.strip("-") or "rilievo")
    seen[slug] = seen.get(slug, 0) + 1
    if seen[slug] > 1:
        slug = "%s-%d" % (slug, seen[slug])
    return slug


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
                 scores: Dict[str, Optional[float]],
                 lang: str = "it") -> str:
    """Testata visiva del referto: anello, verdetto, tile, donut."""
    esc = html.escape
    lab = _HTML_I18N.get(lang) or _HTML_I18N["it"]
    total = overall_score(scores)
    label, hue, mark = score_verdict(total)
    label = lab.get("verdict." + label, label)
    ring_c = 326.73  # 2 * pi * r, con r = 52

    sev_counts = Counter(f.severity for f in findings)
    clean, flagged, broken = page_status_counts(pages, findings)
    n_pages = len(pages)

    out: List[str] = ["<div class=\"hero\">"]
    out.append(
        "<div class=\"ringbox\" role=\"img\" aria-label=\"%s\">"
        "<svg viewBox=\"0 0 120 120\" "
        "width=\"124\" height=\"124\" aria-hidden=\"true\">"
        "<circle class=\"rtrack\" cx=\"60\" cy=\"60\" r=\"52\"></circle>"
        "<circle class=\"rfill\" cx=\"60\" cy=\"60\" r=\"52\" "
        "style=\"stroke:%s;stroke-dasharray:%.2f %.2f\" "
        "transform=\"rotate(-90 60 60)\"></circle></svg>"
        "<div class=\"rnum\" aria-hidden=\"true\"><b>%.0f</b>"
        "<small>%s</small></div></div>"
        % (lab["hero.ring"] % (total, esc(label)), hue,
           ring_c * total / 100.0, ring_c, total,
           lab["hero.of100"]))
    out.append(
        "<div class=\"heroside\"><p class=\"verdict\"><span class="
        "\"ico\" style=\"background:%s\">%s</span>%s</p>"
        "<p class=\"soglie\">%s</p><div class=\"tiles\">"
        % (hue, mark, esc(label), lab["hero.thresholds"]))
    for sev, tile_key, color in (
            (SEV_CRITICAL, "tile.critical", "var(--bad)"),
            (SEV_WARNING, "tile.warning", "var(--warn)"),
            (SEV_INFO, "tile.info", "var(--muted)")):
        out.append(
            "<div class=\"tile\"><span class=\"lbl\"><span class="
            "\"dot\" style=\"background:%s\"></span>%s</span>"
            "<b>%d</b></div>"
            % (color, esc(lab[tile_key]), sev_counts.get(sev, 0)))
    out.append("</div></div>")

    if n_pages:
        donut = _donut_svg(
            [(clean, "var(--good)"), (flagged, "var(--warn)"),
             (broken, "var(--bad)")], n_pages,
            lab["hero.donut_aria"]
            % (n_pages, clean, flagged, broken))
        out.append(
            "<div class=\"donutbox\"><div class=\"donutwrap\">%s"
            "<div class=\"dnum\" aria-hidden=\"true\"><b>%d</b>"
            "<small>%s</small></div></div>"
            "<ul class=\"dleg\" aria-hidden=\"true\">"
            "<li><span class=\"dot\" style=\"background:var(--good)\">"
            "</span>%s</li>"
            "<li><span class=\"dot\" style=\"background:var(--warn)\">"
            "</span>%s</li>"
            "<li><span class=\"dot\" style=\"background:var(--bad)\">"
            "</span>%s</li></ul></div>"
            % (donut, n_pages, lab["hero.pages"],
               lab["hero.clean"] % clean,
               lab["hero.flagged"] % flagged,
               lab["hero.broken"] % broken))
    out.append("</div>")
    return "".join(out)


def render_html(base: str, pages: List[Page],
                findings: List[Finding],
                scores: Dict[str, Optional[float]],
                results: List[QueryResult], mode: str,
                k: int = 60,
                competitive: Optional[Dict[str, object]] = None,
                market: str = DEFAULT_MARKET,
                judge: Optional[Dict[str, object]] = None,
                delta: Optional[Dict[str, object]] = None,
                lighthouse: Optional[Dict[str, object]] = None,
                search_check: Optional[Dict[str, object]] = None,
                lang: str = "it") -> str:
    """Referto HTML autonomo, leggibile in chiaro e in scuro.

    ``lang`` governa la lingua della cornice (sezioni, tabelle,
    legende, catalogo ``_HTML_I18N``); i rilievi e i testi generati
    dall'audit restano in italiano e con "en" il referto lo
    dichiara in testa.
    """
    esc = html.escape
    lab = _HTML_I18N.get(lang) or _HTML_I18N["it"]
    lang = lang if lang in _HTML_I18N else "it"
    colors = {SEV_CRITICAL: "var(--bad)", SEV_WARNING: "var(--warn)",
              SEV_OK: "var(--good)", SEV_INFO: "var(--muted)"}
    marks = {SEV_CRITICAL: "&#10005;", SEV_WARNING: "!",
             SEV_OK: "&#10003;", SEV_INFO: "i"}

    # Ancore stabili per rilievo, nell'ordine in cui le sezioni per
    # area li mostrano; la mappa per chiave storica serve ai link
    # interni di "Top rilievi" e del piano di remediation.
    order = {SEV_CRITICAL: 0, SEV_WARNING: 1, SEV_INFO: 2, SEV_OK: 3}
    anchor_ids: Dict[int, str] = {}
    anchor_by_key: Dict[Tuple[str, str], str] = {}
    slug_seen: Dict[str, int] = {}
    for area in ALL_AREAS:
        for finding in sorted(
                (f for f in findings if f.area == area),
                key=lambda f: order[f.severity]):
            slug = _finding_anchor(area, finding.title, slug_seen)
            anchor_ids[id(finding)] = slug
            anchor_by_key.setdefault(
                _finding_key({"area": area,
                              "title": finding.title}), slug)

    def link_to(area: object, title: object) -> Tuple[str, str]:
        """(apertura, chiusura) del link all'ancora del rilievo."""
        slug = anchor_by_key.get(
            _finding_key({"area": str(area), "title": str(title)}))
        if not slug:
            return "", ""
        return "<a class=\"rlink\" href=\"#%s\">" % slug, "</a>"

    parts: List[str] = []
    parts.append(
        "<!DOCTYPE html><html lang=\"%s\"><head>"
        "<meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,"
        "initial-scale=1\">"
        "<title>MARS Beacon - %s</title><style>%s%s</style>"
        "</head><body><div class=\"wrap\">"
        % (lang, esc(base), _brand_font_css(), _CSS))

    parts.append("<h1>MARS Beacon</h1>")
    parts.append("<p class=\"meta\">Meta-fusion, Accessibility, "
                 "Ranking &amp; Security Audit</p>")
    parts.append("<p class=\"sub\">%s</p>" % esc(base))
    parts.append(
        "<p class=\"meta\">%s</p>" % (lab["meta.line"] % (
            len([p for p in pages if p.ok]),
            sum(len(p.chunks) for p in pages if p.ok), esc(mode))))
    if lab["note.findings_lang"]:
        parts.append("<p class=\"meta\"><em>%s</em></p>"
                     % lab["note.findings_lang"])

    parts.append(_render_hero(pages, findings, scores, lang))

    # Widget "Top rilievi": la testa del piano di remediation come
    # vista compatta trasversale alle aree (pattern Top Issues di
    # Ahrefs/Semrush); pallino + etichetta testuale, mai solo colore.
    top_plan = build_remediation(findings, pages, scores, market)[:5]
    if top_plan:
        parts.append("<section class=\"toplist\"><h2>%s"
                     "</h2><ol>" % lab["top.h"])
        for item in top_plan:
            sev = str(item["severity"])
            gain = ""
            if item.get("index_gain"):
                gain = (" <span class=\"eff\">%s</span>"
                        % (lab["gain.index"] % item["index_gain"]))
            a_open, a_close = link_to(item["area"], item["title"])
            parts.append(
                "<li><span class=\"dot\" style=\"background:%s\">"
                "</span> %s<b>%s</b>%s <span class=\"meta\">"
                "[%s · %s]</span>%s</li>"
                % (colors.get(sev, "var(--muted)"), a_open,
                   esc(finding_texts(item, lang)["title"]), a_close,
                   lab["top.critical"] if sev == SEV_CRITICAL
                   else lab["top.warning"],
                   esc(lab.get("area." + str(item["area"]),
                               str(item["area"]))), gain))
        parts.append("</ol></section>")

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
            % (esc(lab.get("area." + area, area)), hue, score,
               score, hue))
    total = overall_score(scores)
    hue = "var(--good)" if total >= 70 else (
        "var(--warn)" if total >= 40 else "var(--bad)")
    parts.append(
        "<div class=\"sc tot\"><h3>%s<span style=\"color:%s\">"
        "%.0f</span></h3><div class=\"bar\"><div class=\"fill\" "
        "style=\"width:%.0f%%;background:%s\"></div></div></div>"
        % (lab["score.total"], hue, total, total, hue))
    parts.append("</div>")

    if delta:
        parts.append(
            "<section><h2>%s</h2><p class=\"meta\">%s</p>"
            % (lab["delta.h"], lab["delta.meta"]
               % esc(str(delta.get("previous_generated_at") or ""))))
        variazioni = " · ".join(
            "%s <b>%+.1f</b>"
            % (esc(lab.get("area." + area, area)), value) if value
            else "%s =" % esc(lab.get("area." + area, area))
            for area, value in dict(delta["scores"]).items())
        if variazioni:
            parts.append("<p class=\"meta\">%s</p>" % variazioni)
        for label, items in ((lab["delta.resolved"],
                              delta["resolved"]),
                             (lab["delta.new"], delta["new"])):
            parts.append("<h3>%s (%d)</h3>"
                         % (label, len(list(items))))
            if not items:
                parts.append("<p class=\"meta\">%s</p>"
                             % lab["delta.none"])
            for f in items:
                sev = str(f["severity"])
                parts.append(
                    "<div class=\"find\"><span class=\"ico\" "
                    "style=\"background:%s\">%s</span>"
                    "<div class=\"txt\"><b>%s</b></div></div>"
                    % (colors.get(sev, "var(--muted)"),
                       marks.get(sev, "i"),
                       esc(str(f["title"]))))
        parts.append("</section>")

    cit = citability_profiles(pages, scores, market)
    if cit:
        pesi = ", ".join("%s %d%%" % (key, round(100 * w))
                         for key, w in cit["market_weights"].items())
        parts.append(
            "<section><h2>%s</h2><p class=\"meta\">%s</p>"
            "<table class=\"citprof\"><thead><tr><th>%s"
            "</th><th>%s</th><th>%s</th></tr>"
            "</thead><tbody>"
            % (lab["cit.h"],
               lab["cit.meta"] % (esc(cit["note"]),
                                  esc(cit["market"]), esc(pesi)),
               lab["cit.assistant"], lab["cit.focus"],
               lab["cit.score"]))
        for prof in cit["profiles"]:
            if prof["score"] is None:
                continue
            val = float(prof["score"])
            hue = "var(--good)" if val >= 70 else (
                "var(--warn)" if val >= 40 else "var(--bad)")
            parts.append(
                "<tr><td><b>%s</b></td><td>%s</td>"
                "<td style=\"color:%s\"><b>%.1f</b>/100"
                "<div class=\"bar\"><div class=\"fill\" style=\""
                "width:%.0f%%;background:%s\"></div></div>"
                "</td></tr>"
                % (esc(str(prof["label"])), esc(str(prof["focus"])),
                   hue, val, val, hue))
        if cit["index"] is not None:
            val = float(cit["index"])
            hue = "var(--good)" if val >= 70 else (
                "var(--warn)" if val >= 40 else "var(--bad)")
            parts.append(
                "<tr><th>%s</th>"
                "<td>&mdash;</td><td style=\"color:%s\">"
                "<b>%.1f</b>/100<div class=\"bar\">"
                "<div class=\"fill\" style=\"width:%.0f%%;"
                "background:%s\"></div></div></td></tr>"
                % (lab["cit.index"] % esc(cit["market"]), hue,
                   val, val, hue))
        parts.append("</tbody></table>")
        actions = citability_top_actions(findings, pages, scores,
                                         market)
        if actions:
            parts.append(
                "<h3>%s</h3><p class=\"meta\">%s</p>"
                "<ol class=\"cit-actions\">"
                % (lab["cit.actions_h"] % len(actions),
                   lab["cit.actions_meta"]))
            for act in actions:
                badges = ("<span class=\"eff\">%s</span>"
                          % (lab["badge.effort"]
                             % esc(str(act["effort"]))))
                if act["quick_win"]:
                    badges += ("<span class=\"qw\">%s</span>"
                               % lab["badge.qw"])
                gain = ""
                if act["best_profile"]:
                    gain = (lab["cit.best"]
                            % (esc(str(act["best_label"])),
                               act["best_gain"]))
                parts.append("<li>%s %s%s</li>"
                             % (esc(finding_texts(
                                 act, lang)["title"]),
                                badges, gain))
            parts.append("</ol>")
        parts.append("</section>")

    if judge:
        parts.append("<section><h2>%s</h2>" % lab["judge.h"])
        if judge.get("status") == "ok":
            confronto = ""
            if cit and cit["index"] is not None:
                confronto = (lab["judge.compare"]
                             % (cit["index"],
                                float(str(judge["average"]))
                                - float(str(cit["index"]))))
            parts.append(
                "<p class=\"meta\">%s</p>"
                "<table><thead><tr><th>%s</th><th>%s"
                "</th><th>%s</th></tr></thead><tbody>"
                % (lab["judge.meta"]
                   % (esc(str(judge["model"])), judge["sampled"],
                      judge["average"], esc(confronto),
                      esc(str(judge["note"]))),
                   lab["judge.query"], lab["judge.score"],
                   lab["judge.reason"]))
            for v in judge["verdicts"]:
                val = float(str(v["score"]))
                hue = "var(--good)" if val >= 70 else (
                    "var(--warn)" if val >= 40 else "var(--bad)")
                parts.append(
                    "<tr><td>%s</td><td style=\"color:%s\">"
                    "<b>%.1f</b>/100</td><td>%s</td></tr>"
                    % (esc(str(v["query"])), hue, val,
                       esc(str(v["reason"]))))
            parts.append("</tbody></table>")
        else:
            parts.append("<p class=\"meta\">%s</p>"
                         % (lab["judge.skipped"]
                            % esc(str(judge.get("reason", "")))))
        parts.append("</section>")

    if lighthouse:
        parts.append("<section><h2>%s</h2>" % lab["lh.h"])
        if lighthouse.get("status") == "ok":
            fork = str(lighthouse.get("fork") or "")
            parts.append(
                "<p class=\"meta\">%s</p>"
                % (lab["lh.meta"]
                   % (len(lighthouse.get("pages") or []),
                      esc(str(lighthouse.get("device", ""))),
                      (lab["lh.fork"] % esc(fork)) if fork
                      else "")))
            categorie = lighthouse.get("categories") or []
            if categorie:
                parts.append(
                    "<table><thead><tr><th>%s</th><th>%s</th>"
                    "</tr></thead><tbody>"
                    % (lab["lh.cat"], lab["lh.score"]))
                for c in categorie:
                    val = int(c["score"])
                    hue = "var(--good)" if val >= 90 else (
                        "var(--warn)" if val >= 50
                        else "var(--bad)")
                    parts.append(
                        "<tr><td>%s</td><td style=\"color:%s\">"
                        "<b>%d</b>/100</td></tr>"
                        % (esc(str(c["title"])), hue, val))
                parts.append("</tbody></table>")
        else:
            parts.append("<p class=\"meta\">%s</p>"
                         % (lab["lh.skipped"]
                            % esc(str(lighthouse.get(
                                "reason", "")))))
        parts.append("</section>")

    if search_check:
        parts.append("<section><h2>%s</h2>" % lab["sc.h"])
        if search_check.get("status") == "ok":
            interrogate = search_check.get("queries") or []
            top_n = int(search_check.get("top_n", 0) or 0)
            parts.append("<p class=\"meta\">%s %s</p>"
                         % (lab["sc.meta"]
                            % (search_check.get("found", 0),
                               len(interrogate), top_n),
                            esc(str(search_check.get("note",
                                                     "")))))
            parts.append(
                "<table><thead><tr><th>%s</th><th>%s</th>"
                "<th>%s</th></tr></thead><tbody>"
                % (lab["sc.query"], lab["sc.result"],
                   lab["sc.rrf"]))
            for q in interrogate:
                if q.get("error"):
                    esito = lab["sc.error"] \
                        % esc(str(q["error"]))
                elif q.get("position"):
                    esito = "<b>%s</b>" \
                        % (lab["sc.pos"] % q["position"])
                else:
                    esito = lab["sc.absent"] % top_n
                parts.append(
                    "<tr><td>%s</td><td>%s</td><td>%s</td></tr>"
                    % (esc(str(q.get("query", ""))), esito,
                       q.get("rrf_consensus", 0)))
            parts.append("</tbody></table>")
        else:
            parts.append("<p class=\"meta\">%s</p>"
                         % (lab["sc.skipped"]
                            % esc(str(search_check.get(
                                "reason", "")))))
        parts.append("</section>")

    for area in ALL_AREAS:
        subset = sorted((f for f in findings if f.area == area),
                        key=lambda f: order[f.severity])
        if not subset:
            continue
        parts.append("<section><h2>%s</h2>"
                     % esc(lab.get("area." + area, area)))
        for finding in subset:
            slug = anchor_ids[id(finding)]
            texts = finding_texts(finding, lang)
            parts.append(
                "<div class=\"find\" id=\"%s\"><span class=\"ico\" "
                "style=\"background:%s\">%s</span>"
                "<div class=\"txt\"><b>%s</b> "
                "<a class=\"anchor\" href=\"#%s\" "
                "aria-label=\"%s\">#</a>"
                % (slug, colors[finding.severity],
                   marks[finding.severity], esc(texts["title"]),
                   slug, lab["anchor.label"]))
            if texts["detail"]:
                parts.append("<span class=\"d\">%s</span>"
                             % esc(texts["detail"]))
            if texts["fix"]:
                parts.append("<span class=\"fix\">%s</span>"
                             % esc(texts["fix"]))
            parts.append("</div></div>")
        parts.append("</section>")

    depths = depth_distribution(pages, base)
    if depths:
        massimo = max(b["count"] for b in depths["buckets"]) or 1
        parts.append(
            "<section><h2>%s</h2><p class=\"meta\">%s</p>"
            "<table class=\"citprof\"><tbody>"
            % (lab["depth.h"], lab["depth.meta"]))
        for bucket in depths["buckets"]:
            width = 100.0 * bucket["count"] / massimo
            hue = ("var(--warn)" if "4+" in bucket["label"]
                   or "sitemap" in bucket["label"]
                   else "var(--good)")
            parts.append(
                "<tr><th>%s</th><td>%d</td><td style=\"width:50%%"
                "\"><div class=\"bar\"><div class=\"fill\" "
                "style=\"width:%.0f%%;background:%s\"></div></div>"
                "</td></tr>"
                % (esc(str(bucket["label"])), bucket["count"],
                   width, hue))
        parts.append("</tbody></table></section>")

    tmap = treemap_data(pages, findings)
    if tmap:
        parts.append(
            "<section><h2>%s</h2><p class=\"meta\">%s</p>"
            "<svg id=\"tm-svg\" viewBox=\"0 0 %d %d\" role=\"img\" "
            "aria-label=\"%s\" "
            "style=\"max-width:760px;width:100%%\">"
            % (lab["tm.h"],
               lab["tm.meta"] % (tmap["shown"], tmap["total"]),
               int(tmap["width"]), int(tmap["height"]),
               lab["tm.aria"]))
        fills = {"critical": "var(--bad)", "warning": "var(--warn)",
                 "ok": "var(--good)"}
        for item in tmap["items"]:
            titolo = (lab["tm.title"]
                      % (esc(str(item["label"])), item["words"],
                         item["chunks"],
                         lab["tm.sev_" + str(item["severity"])]))
            parts.append(
                "<rect x=\"%.1f\" y=\"%.1f\" width=\"%.1f\" "
                "height=\"%.1f\" fill=\"%s\" fill-opacity=\"0.75\" "
                "stroke=\"var(--bg)\" stroke-width=\"2\" "
                "class=\"tm-rect\" tabindex=\"0\" role=\"img\" "
                "aria-label=\"%s\"><title>%s</title></rect>"
                % (item["x"], item["y"], item["w"], item["h"],
                   fills[str(item["severity"])], titolo, titolo))
            if item["w"] >= 90 and item["h"] >= 26:
                parts.append(
                    "<text x=\"%.1f\" y=\"%.1f\" font-size=\"11\" "
                    "fill=\"var(--fg)\" stroke=\"var(--bg)\" "
                    "stroke-width=\"3\" paint-order=\"stroke\" "
                    "pointer-events=\"none\">%s</text>"
                    % (item["x"] + 6, item["y"] + 16,
                       esc(str(item["label"])[
                           :max(4, int(item["w"] // 7))])))
        parts.append("</svg><p id=\"tm-info\" class=\"meta\" "
                     "role=\"status\"></p>")
        parts.append(
            "<details><summary>%s</summary>"
            "<table><thead><tr><th>%s</th><th>%s</th><th>%s</th>"
            "<th>%s</th></tr></thead><tbody>"
            % (lab["tm.table"], lab["tm.page"], lab["tm.words"],
               lab["tm.chunks"], lab["tm.sev"]))
        for item in tmap["items"]:
            parts.append(
                "<tr><td>%s</td><td>%d</td><td>%d</td>"
                "<td>%s</td></tr>"
                % (esc(str(item["label"])), item["words"],
                   item["chunks"],
                   lab["tm.sev_" + str(item["severity"])]))
        parts.append("</tbody></table></details></section>")

    graph = link_graph_data(pages, base)
    if graph and graph["links"]:
        parts.append(
            "<section><h2>%s</h2>"
            "<p class=\"meta\">%s %s</p>"
            "<svg id=\"lg-svg\" viewBox=\"0 0 %.0f %.0f\" "
            "role=\"img\" aria-label=\"%s\" "
            "style=\"max-width:520px;width:100%%\">"
            % (lab["graph.h"],
               lab["graph.meta"] % (len(graph["nodes"]),
                                    graph["total"]),
               lab["lg.hint"],
               graph["width"], graph["height"],
               lab["graph.aria"]))
        # Frecce di direzione: marker normale ed evidenziato.
        parts.append(
            "<defs>"
            "<marker id=\"lg-arr\" viewBox=\"0 0 8 8\" refX=\"7\" "
            "refY=\"4\" markerWidth=\"5.5\" markerHeight=\"5.5\" "
            "orient=\"auto-start-reverse\">"
            "<path d=\"M0 0L8 4L0 8z\" "
            "style=\"fill:var(--line)\"/></marker>"
            "<marker id=\"lg-arr-hi\" viewBox=\"0 0 8 8\" "
            "refX=\"7\" refY=\"4\" markerWidth=\"5.5\" "
            "markerHeight=\"5.5\" orient=\"auto-start-reverse\">"
            "<path d=\"M0 0L8 4L0 8z\" "
            "style=\"fill:var(--accent)\"/></marker>"
            "</defs>")
        nodes = graph["nodes"]
        radii = [min(15.0, 5.0 + 1.8 * n["incoming"] ** 0.5)
                 for n in nodes]
        outgoing = [0] * len(nodes)
        for link in graph["links"]:
            outgoing[link["source"]] += 1
        for link in graph["links"]:
            a = nodes[link["source"]]
            b = nodes[link["target"]]
            # L'arco si ferma al bordo del nodo di destinazione,
            # cosi' la freccia resta visibile.
            dx = b["x"] - a["x"]
            dy = b["y"] - a["y"]
            lung = (dx * dx + dy * dy) ** 0.5 or 1.0
            acc = (radii[link["target"]] + 3.0) / lung
            parts.append(
                "<line x1=\"%.1f\" y1=\"%.1f\" x2=\"%.1f\" "
                "y2=\"%.1f\" stroke=\"var(--line)\" "
                "stroke-width=\"0.8\" "
                "marker-end=\"url(#lg-arr)\" data-s=\"%d\" "
                "data-t=\"%d\"/>"
                % (a["x"], a["y"], b["x"] - dx * acc,
                   b["y"] - dy * acc,
                   link["source"], link["target"]))
        if len(nodes) <= GRAPH_LABEL_ALL:
            labelled = {n["url"] for n in nodes}
        else:
            labelled = {n["url"] for n in sorted(
                nodes, key=lambda n: (not n["home"],
                                      -n["incoming"]))[:12]}
        for i, node in enumerate(nodes):
            problematico = (node["depth"] is None
                            or node["depth"] > 3)
            hue = ("var(--accent)" if node["home"] else
                   "var(--warn)" if problematico else
                   "var(--good)")
            r = radii[i]
            profondita = (lab["graph.clicks"] % node["depth"]
                          if node["depth"] is not None
                          else lab["graph.sitemap_only"])
            parts.append(
                "<circle cx=\"%.1f\" cy=\"%.1f\" r=\"%.1f\" "
                "fill=\"%s\" fill-opacity=\"0.75\" stroke=\"%s\" "
                "class=\"lg-node\" data-i=\"%d\" data-r=\"%.1f\" "
                "data-depth=\"%s\" tabindex=\"0\">"
                "<title>%s, %s</title></circle>"
                % (node["x"], node["y"], r, hue, hue, i, r,
                   "x" if node["depth"] is None
                   else node["depth"],
                   lab["graph.node_title"]
                   % (esc(str(node["label"])), node["incoming"],
                      profondita),
                   lab["lg.outgoing"] % outgoing[i]))
            if node["url"] in labelled:
                # Alone chiaro sotto il testo: leggibile anche
                # quando l'etichetta attraversa un arco.
                parts.append(
                    "<text x=\"%.1f\" y=\"%.1f\" font-size=\"11\" "
                    "fill=\"var(--fg)\" stroke=\"var(--bg)\" "
                    "stroke-width=\"3\" paint-order=\"stroke\" "
                    "pointer-events=\"none\" data-i=\"%d\">"
                    "%s</text>"
                    % (node["x"] + r + 3, node["y"] + 4, i,
                       esc(str(node["label"])[:30])))
        parts.append(
            "</svg>"
            "<p class=\"lg-controls\">"
            "<button type=\"button\" id=\"lg-vforza\" "
            "aria-pressed=\"true\">%s</button> "
            "<button type=\"button\" id=\"lg-vanelli\" "
            "aria-pressed=\"false\">%s</button> · "
            "<button type=\"button\" id=\"lg-zin\">%s</button> "
            "<button type=\"button\" id=\"lg-zout\">%s</button> "
            "<button type=\"button\" id=\"lg-reset\">%s</button>"
            "</p>"
            "<p class=\"meta\">%s</p>"
            "<p id=\"lg-info\" class=\"meta\" role=\"status\"></p>"
            "</section>"
            % (lab["lg.vforza"], lab["lg.vanelli"],
               lab["lg.zin"], lab["lg.zout"], lab["lg.reset"],
               lab["lg.legend"]))

    math = surface_math(pages)
    if math:
        effetto = (lab["math.mult"] % math["multiplier"]
                   if math["multiplier"] is not None else
                   lab["math.zero"] % math["chunks_potential"])
        parts.append(
            "<section><h2>%s</h2>"
            "<p class=\"meta\">%s</p>"
            "<table><tbody>"
            "<tr><th>%s</th><td>%s</td></tr>"
            "<tr><th>%s</th><td>%s</td></tr>"
            "<tr><th>%s</th><td>%s</td></tr>"
            "</tbody></table></section>"
            % (lab["math.h"], lab["math.meta"], lab["math.now"],
               lab["math.now_v"] % (math["pages"],
                                    math["chunks_now"],
                                    math["words_avg"]),
               lab["math.pot"],
               lab["math.pot_v"] % (math["chunks_potential"],
                                    esc(str(math["assumption"]))),
               lab["math.fx"], esc(effetto)))

    plan = build_remediation(findings, pages, scores, market)
    if plan:
        quick = sum(1 for i in plan if i["quick_win"])
        criterio = (lab["plan.crit_gain"]
                    if "index_gain" in plan[0]
                    else lab["plan.crit_weight"])
        parts.append(
            "<section><h2>%s</h2><p class=\"meta\">%s</p>"
            % (lab["plan.h"],
               lab["plan.meta"]
               % (len(plan), criterio,
                  lab["plan.quick_here"] % quick if quick else "")))
        for item in plan:
            sev = str(item["severity"])
            badges = ("<span class=\"eff\">%s</span>"
                      % (lab["badge.effort"]
                         % esc(str(item["effort"]))))
            if item["quick_win"]:
                badges += ("<span class=\"qw\">%s</span>"
                           % lab["badge.qw"])
            if item.get("cross"):
                badges += ("<span class=\"crossb\">%s</span>"
                           % (lab["badge.cross"]
                              % (len(list(item["profiles_hit"])),
                                 item["index_gain"])))
            a_open, a_close = link_to(item["area"], item["title"])
            texts = finding_texts(item, lang)
            parts.append(
                "<div class=\"find\"><span class=\"ico\" style=\""
                "background:%s\">%s</span><div class=\"txt\">"
                "%s<b>%d. %s</b>%s %s"
                % (colors[sev], marks[sev], a_open,
                   item["priority"], esc(texts["title"]),
                   a_close, badges))
            if texts["fix"]:
                parts.append("<span class=\"d\">%s</span>"
                             % esc(texts["fix"]))
            if texts["example"]:
                parts.append("<pre class=\"ex\">%s</pre>"
                             % esc(texts["example"]))
            parts.append("</div></div>")
        parts.append("</section>")

    if results:
        parts.append("<section><h2>%s</h2>"
                     "<p class=\"meta\">%s</p>"
                     "<table><thead><tr><th>%s</th><th>%s"
                     "</th><th>%s</th>"
                     "<th>%s</th></tr></thead><tbody>"
                     % (lab["rrf.h"], lab["rrf.meta"],
                        lab["rrf.query"], lab["rrf.consensus"],
                        lab["rrf.top"], lab["rrf.score"]))
        for res in results:
            top = res.fused_top[0] if res.fused_top else ("-", 0.0)
            ratio = res.consensus / 5.0
            hue = "var(--good)" if ratio >= 0.45 else (
                "var(--warn)" if ratio >= 0.2 else "var(--bad)")
            parts.append(
                "<tr><td>%s</td><td class=\"cons\">"
                "<span class=\"mnum\">%s</span>"
                "<div class=\"meter\" aria-hidden=\"true\">"
                "<div class=\"mfill\" style=\"width:%.0f%%;"
                "background:%s\"></div>"
                "<span class=\"tick\" style=\"left:20%%\"></span>"
                "<span class=\"tick\" style=\"left:45%%\"></span>"
                "</div></td><td>%s</td><td>%.5f</td></tr>"
                % (esc(res.query), lab["rrf.of5"] % res.consensus,
                   ratio * 100, hue, esc(str(top[0])), top[1]))
        parts.append("</tbody></table></section>")

    if competitive:
        share = competitive["share"]
        parity = 100.0 / max(1, len(competitive["sites"]))
        parts.append(
            "<section><h2>%s</h2><p class=\"meta\">%s</p>"
            % (lab["comp.h"],
               lab["comp.meta"] % (competitive["top_n"], parity)))
        parts.append("<table><thead><tr><th>%s</th>"
                     "<th>%s</th><th></th></tr></thead><tbody>"
                     % (lab["comp.site"], lab["comp.share"]))
        for host in competitive["sites"]:
            mine = host == competitive["main"]
            name = esc(host) + (lab["comp.mine"] if mine else "")
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

        # Mappa a bolle (pattern Semrush): x = share of voice,
        # y = query in cui il sito compare, raggio = corpus in
        # chunk. Decorativa: i numeri sono nelle tabelle.
        presence = competitive.get("presence") or {}
        chunks_by = competitive.get("chunks") or {}
        q_tot = int(competitive.get("queries_total") or 0)
        if presence and q_tot:
            parts.append(
                "<p class=\"meta\">%s</p>"
                "<svg viewBox=\"0 0 420 190\" role=\"img\" "
                "aria-label=\"%s\" "
                "style=\"max-width:460px;width:100%%\">"
                "<line x1=\"40\" y1=\"160\" x2=\"400\" y2=\"160\" "
                "stroke=\"var(--line)\"/>"
                "<line x1=\"40\" y1=\"20\" x2=\"40\" y2=\"160\" "
                "stroke=\"var(--line)\"/>"
                % (lab["comp.bubble_meta"] % q_tot,
                   lab["comp.bubble_aria"]))
            max_chunks = max(chunks_by.values()) or 1
            for host in competitive["sites"]:
                mine = host == competitive["main"]
                x = 40 + 360 * float(share.get(host, 0)) / 100.0
                y = 160 - 140 * presence.get(host, 0) / q_tot
                r = 5 + 14 * ((chunks_by.get(host, 0)
                               / max_chunks) ** 0.5)
                hue = "var(--accent)" if mine else "var(--muted)"
                parts.append(
                    "<circle cx=\"%.1f\" cy=\"%.1f\" r=\"%.1f\" "
                    "fill=\"%s\" fill-opacity=\"0.55\" "
                    "stroke=\"%s\"/>"
                    "<text x=\"%.1f\" y=\"%.1f\" font-size=\"10\" "
                    "fill=\"var(--fg)\">%s</text>"
                    % (x, y, r, hue, hue, x + r + 3, y + 3,
                       esc(host)))
            parts.append("</svg>")

        parts.append("<table><thead><tr><th>%s</th>"
                     "<th>%s</th><th>%s"
                     "</th></tr></thead><tbody>"
                     % (lab["comp.query"], lab["comp.mine_passages"],
                        lab["comp.best"]))
        for row in competitive["queries"]:
            best = (str(row["best_rank_mine"])
                    if row["best_rank_mine"]
                    else lab["comp.absent"])
            parts.append(
                "<tr><td>%s</td><td>%d su %d</td><td>%s</td></tr>"
                % (esc(row["query"]), row["mine_in_top"],
                   competitive["top_n"], best))
        parts.append("</tbody></table></section>")

    parts.append("<footer>")
    parts.append(_brand_logo_svg())
    parts.append(
        "<p class=\"brand\">Lympha Technologies S.r.l.</p>"
        "<p>%s</p>"
        "<p>%s: Cormack et al. (SIGIR 2009); "
        "<a href=\"https://learn.microsoft.com/en-us/azure/search/"
        "hybrid-search-ranking\">Microsoft Learn</a>; "
        "<a href=\"https://www.elastic.co/docs/reference/elasticsearch/"
        "rest-apis/reciprocal-rank-fusion\">Elastic</a>; "
        "<a href=\"https://schema.org/\">Schema.org</a>.</p>"
        "</footer></div>"
        % (lab["footer.gen"] % (__version__, k),
           lab["footer.refs"]))
    parts.append("<script>%s</script></body></html>" % _REPORT_JS)
    return "".join(parts)


# JavaScript inline del referto (decisione del 2026-08-05, che
# ribalta il vincolo "referto senza JavaScript"): progressive
# enhancement puro — l'SVG statico resta la base (stampa e no-JS
# invariati), il JS legge il DOM (data-*, <title>) senza payload
# propri. Vanilla, autonomo, nessuna origine esterna: il referto
# resta un file unico.
_REPORT_JS = """
(function () {
  "use strict";
  function titolo(el) {
    var t = el.querySelector("title");
    return t ? t.textContent : "";
  }
  /* Treemap: dettagli del rettangolo attivo nella regione di
     stato (hover e focus da tastiera). */
  var tmSvg = document.getElementById("tm-svg");
  var tmInfo = document.getElementById("tm-info");
  if (tmSvg && tmInfo) {
    Array.prototype.forEach.call(
      tmSvg.querySelectorAll(".tm-rect"), function (r) {
        function mostra() { tmInfo.textContent = titolo(r); }
        function pulisci() { tmInfo.textContent = ""; }
        r.addEventListener("pointerenter", mostra);
        r.addEventListener("focus", mostra);
        r.addEventListener("pointerleave", pulisci);
        r.addEventListener("blur", pulisci);
      });
  }
  /* Grafo dei link, motore evoluto: simulazione a forze viva
     (semina dal layout deterministico del core, si sveglia al
     trascinamento), vista alternativa ad anelli di profondita',
     frecce direzionali, evidenziazione bloccabile col clic (Esc
     libera). prefers-reduced-motion spegne ogni animazione: il
     disegno resta quello statico, pienamente fruibile. */
  var svg = document.getElementById("lg-svg");
  if (!svg) { return; }
  var info = document.getElementById("lg-info");
  var ridotto = window.matchMedia && window.matchMedia(
    "(prefers-reduced-motion: reduce)").matches;
  var base = svg.getAttribute("viewBox").split(" ").map(Number);
  var vb = base.slice();
  var nodi = Array.prototype.slice.call(
    svg.querySelectorAll(".lg-node"));
  var archi = Array.prototype.slice.call(
    svg.querySelectorAll("line"));
  var etichette = {};
  Array.prototype.forEach.call(
    svg.querySelectorAll("text[data-i]"), function (t) {
      etichette[t.getAttribute("data-i")] = t;
    });
  var N = nodi.length;
  var pos = [];
  var vel = [];
  var raggi = [];
  var prof = [];
  nodi.forEach(function (c) {
    pos.push([+c.getAttribute("cx"), +c.getAttribute("cy")]);
    vel.push([0, 0]);
    raggi.push(+c.getAttribute("data-r") || 6);
    var d = c.getAttribute("data-depth");
    prof.push(d === "x" ? null : +d);
  });
  var lati = archi.map(function (l) {
    return [+l.getAttribute("data-s"),
      +l.getAttribute("data-t")];
  });
  var vicini = nodi.map(function () { return []; });
  lati.forEach(function (st) {
    vicini[st[0]].push(st[1]);
    vicini[st[1]].push(st[0]);
  });

  function ridisegna() {
    var i, k;
    for (i = 0; i < N; i += 1) {
      nodi[i].setAttribute("cx", pos[i][0]);
      nodi[i].setAttribute("cy", pos[i][1]);
      var e = etichette[String(i)];
      if (e) {
        e.setAttribute("x", pos[i][0] + raggi[i] + 3);
        e.setAttribute("y", pos[i][1] + 4);
      }
    }
    for (k = 0; k < archi.length; k += 1) {
      var s = lati[k][0];
      var t = lati[k][1];
      var dx = pos[t][0] - pos[s][0];
      var dy = pos[t][1] - pos[s][1];
      var lun = Math.sqrt(dx * dx + dy * dy) || 1;
      var acc = (raggi[t] + 3) / lun;
      archi[k].setAttribute("x1", pos[s][0]);
      archi[k].setAttribute("y1", pos[s][1]);
      archi[k].setAttribute("x2", pos[t][0] - dx * acc);
      archi[k].setAttribute("y2", pos[t][1] - dy * acc);
    }
  }

  var vista = "forza";
  var blocco = null;
  var caldo = 0;
  var anim = null;
  function passo() {
    var i, j, k;
    for (i = 0; i < N; i += 1) {
      for (j = i + 1; j < N; j += 1) {
        var dx = pos[j][0] - pos[i][0];
        var dy = pos[j][1] - pos[i][1];
        var d2 = dx * dx + dy * dy + 0.01;
        var d = Math.sqrt(d2);
        var f = 900 / d2;
        vel[i][0] -= f * dx / d;
        vel[i][1] -= f * dy / d;
        vel[j][0] += f * dx / d;
        vel[j][1] += f * dy / d;
      }
    }
    for (k = 0; k < lati.length; k += 1) {
      var s = lati[k][0];
      var t = lati[k][1];
      var ex = pos[t][0] - pos[s][0];
      var ey = pos[t][1] - pos[s][1];
      var lun = Math.sqrt(ex * ex + ey * ey) || 1;
      var tira = (lun - 70) * 0.02;
      vel[s][0] += tira * ex / lun;
      vel[s][1] += tira * ey / lun;
      vel[t][0] -= tira * ex / lun;
      vel[t][1] -= tira * ey / lun;
    }
    var energia = 0;
    for (i = 0; i < N; i += 1) {
      if (i === blocco) {
        vel[i][0] = 0;
        vel[i][1] = 0;
        continue;
      }
      vel[i][0] += (base[2] / 2 - pos[i][0]) * 0.002;
      vel[i][1] += (base[3] / 2 - pos[i][1]) * 0.002;
      vel[i][0] *= 0.82;
      vel[i][1] *= 0.82;
      pos[i][0] += vel[i][0];
      pos[i][1] += vel[i][1];
      energia += vel[i][0] * vel[i][0] +
        vel[i][1] * vel[i][1];
    }
    ridisegna();
    caldo -= 1;
    if (vista === "forza" && !ridotto &&
        (energia > 0.4 || caldo > 0)) {
      anim = requestAnimationFrame(passo);
    } else {
      anim = null;
    }
  }
  function scalda(giri) {
    caldo = Math.max(caldo, giri || 30);
    if (vista !== "forza" || ridotto) { return; }
    if (anim === null) {
      anim = requestAnimationFrame(passo);
    }
  }

  var guide = [];
  function togliGuide() {
    guide.forEach(function (g) {
      if (g.parentNode) { g.parentNode.removeChild(g); }
    });
    guide = [];
  }
  function transizione(dest) {
    if (ridotto) {
      pos = dest;
      ridisegna();
      return;
    }
    var da = pos.map(function (p) { return p.slice(); });
    var t0 = null;
    function quadro(ts) {
      if (t0 === null) { t0 = ts; }
      var q = Math.min(1, (ts - t0) / 350);
      var morbo = q * (2 - q);
      for (var i = 0; i < N; i += 1) {
        pos[i][0] = da[i][0] +
          (dest[i][0] - da[i][0]) * morbo;
        pos[i][1] = da[i][1] +
          (dest[i][1] - da[i][1]) * morbo;
      }
      ridisegna();
      if (q < 1) { requestAnimationFrame(quadro); }
    }
    requestAnimationFrame(quadro);
  }
  function versoAnelli() {
    var maxD = 0;
    prof.forEach(function (d) {
      if (d !== null && d > maxD) { maxD = d; }
    });
    var esterno = maxD + 1;
    var cx = base[2] / 2;
    var cy = base[3] / 2;
    var rmax = Math.min(base[2], base[3]) / 2 - 24;
    function raggio(d) {
      return d / (esterno + 0.5) * rmax;
    }
    var perAnello = {};
    var i;
    for (i = 0; i < N; i += 1) {
      var d = prof[i] === null ? esterno : prof[i];
      (perAnello[d] = perAnello[d] || []).push(i);
    }
    var dest = new Array(N);
    Object.keys(perAnello).forEach(function (chiave) {
      var anello = +chiave;
      var gruppo = perAnello[chiave];
      gruppo.sort(function (a, b) {
        return Math.atan2(pos[a][1] - cy, pos[a][0] - cx) -
          Math.atan2(pos[b][1] - cy, pos[b][0] - cx);
      });
      gruppo.forEach(function (n, idx) {
        if (anello === 0) {
          dest[n] = [cx, cy];
          return;
        }
        var ang = -Math.PI / 2 +
          idx * 2 * Math.PI / gruppo.length;
        dest[n] = [cx + raggio(anello) * Math.cos(ang),
          cy + raggio(anello) * Math.sin(ang)];
      });
    });
    togliGuide();
    var primo = svg.querySelector("line");
    for (i = 1; i <= esterno; i += 1) {
      var cerchio = document.createElementNS(
        "http://www.w3.org/2000/svg", "circle");
      cerchio.setAttribute("cx", cx);
      cerchio.setAttribute("cy", cy);
      cerchio.setAttribute("r", raggio(i));
      cerchio.setAttribute("fill", "none");
      cerchio.setAttribute("stroke",
        i === 3 ? "var(--warn)" : "var(--line)");
      cerchio.setAttribute("stroke-width",
        i === 3 ? "1.4" : "0.7");
      cerchio.setAttribute("stroke-dasharray", "4 5");
      cerchio.setAttribute("pointer-events", "none");
      svg.insertBefore(cerchio, primo);
      guide.push(cerchio);
    }
    transizione(dest);
  }
  function bottoneVista(id, nome) {
    var b = document.getElementById(id);
    if (!b) { return; }
    b.addEventListener("click", function () {
      if (vista === nome) { return; }
      vista = nome;
      document.getElementById("lg-vforza").setAttribute(
        "aria-pressed", nome === "forza" ? "true" : "false");
      document.getElementById("lg-vanelli").setAttribute(
        "aria-pressed", nome === "anelli" ? "true" : "false");
      if (nome === "anelli") {
        if (anim !== null) {
          cancelAnimationFrame(anim);
          anim = null;
        }
        versoAnelli();
      } else {
        togliGuide();
        scalda(80);
        if (ridotto) { ridisegna(); }
      }
    });
  }
  bottoneVista("lg-vforza", "forza");
  bottoneVista("lg-vanelli", "anelli");

  function applica() {
    svg.setAttribute("viewBox", vb.join(" "));
  }
  function zoom(f, cx, cy) {
    var nw = Math.max(60, Math.min(base[2] * 3, vb[2] * f));
    var nh = nw * base[3] / base[2];
    var fx = cx === undefined ? vb[0] + vb[2] / 2 : cx;
    var fy = cy === undefined ? vb[1] + vb[3] / 2 : cy;
    vb = [fx - (fx - vb[0]) * nw / vb[2],
      fy - (fy - vb[1]) * nh / vb[3], nw, nh];
    applica();
  }
  function punto(ev) {
    var r = svg.getBoundingClientRect();
    return [vb[0] + (ev.clientX - r.left) / r.width * vb[2],
      vb[1] + (ev.clientY - r.top) / r.height * vb[3]];
  }

  var fisso = null;
  function evidenzia(i) {
    nodi.forEach(function (c, j) {
      c.setAttribute("fill-opacity",
        j === i || vicini[i].indexOf(j) !== -1
          ? "0.95" : "0.25");
    });
    archi.forEach(function (l, k) {
      var suo = lati[k][0] === i || lati[k][1] === i;
      l.setAttribute("stroke",
        suo ? "var(--accent)" : "var(--line)");
      l.setAttribute("stroke-width", suo ? "1.6" : "0.8");
      l.setAttribute("marker-end",
        suo ? "url(#lg-arr-hi)" : "url(#lg-arr)");
    });
    if (info) { info.textContent = titolo(nodi[i]); }
  }
  function spegni() {
    if (fisso !== null) {
      evidenzia(fisso);
      return;
    }
    nodi.forEach(function (c) {
      c.setAttribute("fill-opacity", "0.75");
    });
    archi.forEach(function (l) {
      l.setAttribute("stroke", "var(--line)");
      l.setAttribute("stroke-width", "0.8");
      l.setAttribute("marker-end", "url(#lg-arr)");
    });
    if (info) { info.textContent = ""; }
  }
  document.addEventListener("keydown", function (ev) {
    if (ev.key === "Escape" && fisso !== null) {
      fisso = null;
      spegni();
    }
  });

  var drag = null;
  var pan = null;
  var mosso = false;
  nodi.forEach(function (c, i) {
    c.addEventListener("pointerenter", function () {
      if (drag === null && fisso === null) { evidenzia(i); }
    });
    c.addEventListener("focus", function () {
      if (fisso === null) { evidenzia(i); }
    });
    c.addEventListener("pointerleave", function () {
      if (drag === null) { spegni(); }
    });
    c.addEventListener("blur", function () { spegni(); });
    c.addEventListener("click", function (ev) {
      ev.stopPropagation();
      if (mosso) {
        mosso = false;
        return;
      }
      fisso = fisso === i ? null : i;
      if (fisso === null) { spegni(); }
      else { evidenzia(i); }
    });
    c.addEventListener("pointerdown", function (ev) {
      drag = i;
      blocco = i;
      mosso = false;
      c.setPointerCapture(ev.pointerId);
      ev.preventDefault();
      ev.stopPropagation();
    });
    c.addEventListener("pointermove", function (ev) {
      if (drag !== i) { return; }
      var p = punto(ev);
      pos[i][0] = p[0];
      pos[i][1] = p[1];
      mosso = true;
      if (vista === "forza") { scalda(20); }
      ridisegna();
    });
    c.addEventListener("pointerup", function () {
      drag = null;
      blocco = null;
      if (vista === "forza" && mosso) { scalda(50); }
    });
  });
  svg.addEventListener("click", function (ev) {
    if (ev.target === svg && fisso !== null) {
      fisso = null;
      spegni();
    }
  });
  svg.addEventListener("pointerdown", function (ev) {
    if (ev.target === svg) {
      pan = [ev.clientX, ev.clientY, vb.slice()];
      svg.setPointerCapture(ev.pointerId);
    }
  });
  svg.addEventListener("pointermove", function (ev) {
    if (!pan) { return; }
    var r = svg.getBoundingClientRect();
    var sc = vb[2] / r.width;
    vb = [pan[2][0] - (ev.clientX - pan[0]) * sc,
      pan[2][1] - (ev.clientY - pan[1]) * sc,
      pan[2][2], pan[2][3]];
    applica();
  });
  svg.addEventListener("pointerup", function () { pan = null; });
  svg.addEventListener("wheel", function (ev) {
    ev.preventDefault();
    var p = punto(ev);
    zoom(ev.deltaY < 0 ? 0.82 : 1.22, p[0], p[1]);
  }, { passive: false });
  function bottone(id, fn) {
    var b = document.getElementById(id);
    if (b) { b.addEventListener("click", fn); }
  }
  bottone("lg-zin", function () { zoom(0.7); });
  bottone("lg-zout", function () { zoom(1.42); });
  bottone("lg-reset", function () {
    vb = base.slice();
    applica();
    spegni();
  });
})();
"""


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
pre.ex{font-family:Menlo,Consolas,monospace;font-size:.78rem;
background:var(--accent-soft);border-radius:8px;padding:10px 12px;
margin:6px 0 2px;overflow-x:auto;white-space:pre-wrap;
word-break:break-word}
.eff,.qw{display:inline-block;font-size:.68rem;font-weight:700;
padding:1px 8px;border-radius:999px;margin-left:6px;
vertical-align:2px}
.eff{background:var(--accent-soft);color:var(--accent)}
.citprof .bar{min-width:110px;margin-top:4px}
.toplist ol{margin:6px 0 0 18px;padding:0}
.toplist li{margin:.35rem 0}
.toplist .dot{display:inline-block;width:10px;height:10px;
border-radius:50%;vertical-align:baseline;margin-right:2px}
.toplist .meta{color:var(--muted);font-size:.85em}
.crossb{display:inline-block;font-size:.68rem;font-weight:700;
border-radius:4px;padding:1px 7px;margin-left:6px;
background:var(--accent);color:#fff}
.cit-actions{margin:6px 0 0 18px;padding:0}
.cit-actions li{margin:.4rem 0}
.qw{background:var(--good);color:#fff;text-transform:uppercase;
letter-spacing:.03em}
footer{color:var(--muted);font-size:.78rem;padding:0 4px}
footer a{color:var(--accent)}
.logo-mark{width:46px;height:46px;border-radius:9px;display:block;
margin-bottom:8px}
footer .brand{color:var(--accent);font-weight:700;font-size:.88rem;
letter-spacing:.04em}
.anchor{color:var(--muted);text-decoration:none;font-size:.85em;
opacity:.55}
.anchor:hover,.anchor:focus{opacity:1;color:var(--accent)}
.rlink{color:inherit;text-decoration:none;
border-bottom:1px dotted var(--muted)}
.rlink:hover,.rlink:focus{color:var(--accent);
border-bottom-color:var(--accent)}
.find:target{background:var(--accent-soft);border-radius:8px;
padding-left:8px;padding-right:8px}
.tm-rect:focus,.lg-node:focus{outline:2px solid var(--accent);
outline-offset:1px}
.lg-controls button{font:inherit;padding:2px 10px;margin-right:4px;
border:1px solid var(--line);border-radius:6px;
background:var(--card);color:var(--ink);cursor:pointer}
.lg-controls button:hover{border-color:var(--accent)}
.lg-controls button[aria-pressed="true"]{
border-color:var(--accent);color:var(--accent);font-weight:700}
@media print{.lg-controls{display:none}}
@media print{
:root{--bg:#fff;--card:#fff;--ink:#000;--muted:#444;--line:#bbb;
--accent:#0d4c60;--accent-soft:#eef2f4;--good:#0b6e54;
--warn:#9a3412;--bad:#a01e1e}
*{-webkit-print-color-adjust:exact;print-color-adjust:exact}
@page{margin:16mm 14mm}
body{background:#fff;padding:0;font-size:10.5pt}
.wrap{max-width:none}
section,.hero,.sc,.tile{box-shadow:none;border-color:#bbb}
.find,tr,.tile,.sc,.toplist li,.cit-actions li{
break-inside:avoid;page-break-inside:avoid}
h2,h3{break-after:avoid;page-break-after:avoid}
.anchor{display:none}
a,.rlink{color:inherit;text-decoration:none;border-bottom:none}
svg{max-height:70mm}
footer a::after{content:" (" attr(href) ")";font-size:.9em}
}
"""


def render_json(base: str, pages: List[Page],
                findings: List[Finding],
                scores: Dict[str, Optional[float]],
                results: List[QueryResult], mode: str,
                k: int = 60,
                competitive: Optional[Dict[str, object]] = None,
                market: str = DEFAULT_MARKET,
                judge: Optional[Dict[str, object]] = None,
                delta: Optional[Dict[str, object]] = None,
                lighthouse: Optional[Dict[str, object]] = None,
                search_check: Optional[Dict[str, object]] = None,
                rrf_params: Optional[Dict[str, object]] = None
                ) -> str:
    """Referto JSON, adatto a essere versionato o messo in pipeline."""
    rrf_obj: Dict[str, object] = {
        "k": k, "formula": "score(d)=sum w_i/(k+rank_i(d))"}
    rrf_obj.update(rrf_params or
                   {"top_n": DEFAULT_TOP_N, "weights": [1.0, 1.0]})
    payload = {
        "tool": "mars_audit.py",
        "version": __version__,
        "schema_version": JSON_SCHEMA_VERSION,
        "site": base,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "vector_retriever": mode,
        "rrf": rrf_obj,
        "scores": {**scores, "overall": overall_score(scores)},
        "citability": citability_profiles(pages, scores, market),
        "citability_actions": citability_top_actions(
            findings, pages, scores, market),
        "judge": judge,
        "lighthouse": lighthouse,
        "search_check": search_check,
        "delta": delta,
        "pages": [
            {
                "url": p.url,
                "status": p.status,
                "final_url": p.final_url,
                "redirects": p.redirects,
                "title": p.title,
                "description": p.description,
                "word_count": p.word_count,
                "rendered": p.rendered,
                "headings": len(p.headings),
                "chunks": len(p.chunks),
                "jsonld_types": p.jsonld_types,
            }
            for p in pages
        ],
        "findings": [f.as_dict() for f in findings],
        "surface_math": surface_math(pages),
        "depth_distribution": depth_distribution(pages, base),
        "link_graph": link_graph_data(pages, base),
        "remediation": build_remediation(findings, pages, scores,
                                         market),
        "rrf_simulation": [asdict(r) for r in results],
        "competitive": competitive,
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def _md_cell(value: object) -> str:
    """Testo sicuro dentro una cella di tabella Markdown."""
    return str(value).replace("|", "\\|").replace("\n", " ")


def render_markdown(base: str, pages: List[Page],
                    findings: List[Finding],
                    scores: Dict[str, Optional[float]],
                    results: List[QueryResult], mode: str,
                    k: int = 60,
                    competitive: Optional[Dict[str, object]] = None,
                    market: str = DEFAULT_MARKET,
                    judge: Optional[Dict[str, object]] = None,
                    delta: Optional[Dict[str, object]] = None,
                    lighthouse: Optional[Dict[str, object]] = None,
                    search_check: Optional[Dict[str, object]]
                    = None,
                    lang: str = "it") -> str:
    """Referto Markdown (GitHub-flavored), per issue e pull request.

    Il piano di remediation e' una task list `- [ ]`: incollato in
    una issue diventa una checklist spuntabile. Le gravita' sono
    marcatori testuali, mai solo colore.
    """
    def T(it_text: str, en_text: str) -> str:
        return en_text if lang == "en" else it_text

    marks = {SEV_CRITICAL: T("**[CRITICO]**", "**[CRITICAL]**"),
             SEV_WARNING: T("[AVVISO]", "[WARNING]"),
             SEV_OK: "[ok]", SEV_INFO: "[info]"}
    area_label = {} if lang != "en" else {
        AREA_TECH: "Technical", AREA_LEX: "Lexical (BM25)",
        AREA_SEM: "Semantic (vector)", AREA_SD: "Structured data",
        AREA_RRF: "RRF simulation"}
    out: List[str] = []
    out.append("# MARS Beacon — %s" % base)
    out.append("")
    out.append("*Meta-fusion, Accessibility, Ranking & Security "
               "Audit*")
    out.append("")
    out.append(T("Pagine analizzate: %d · chunk indicizzati: %d · "
                 "recuperatore vettoriale: `%s`",
                 "Pages analysed: %d · indexed chunks: %d · "
                 "vector retriever: `%s`")
               % (len([p for p in pages if p.ok]),
                  sum(len(p.chunks) for p in pages if p.ok), mode))
    out.append("")
    if lang == "en":
        out.append("> Quoted evidence from the audited site stays "
                   "in the site's language.")
        out.append("")
    out.append(T("## Punteggi", "## Scores"))
    out.append("")
    out.append(T("| Area | Punteggio |", "| Area | Score |"))
    out.append("|---|---:|")
    for area, score in scores.items():
        if score is not None:
            out.append("| %s | %.1f/100 |"
                       % (_md_cell(area_label.get(area, area)),
                          score))
    out.append(T("| **Complessivo** | **%.1f/100** |",
                 "| **Overall** | **%.1f/100** |")
               % overall_score(scores))
    out.append("")

    cit = citability_profiles(pages, scores, market)
    if cit:
        out.append(T("## Profili di citabilita' per assistente IA",
                     "## Citability profiles per AI assistant"))
        out.append("")
        out.append(T("| Profilo | Cosa premia | Punteggio |",
                     "| Profile | What it rewards | Score |"))
        out.append("|---|---|---:|")
        for prof in cit["profiles"]:
            if prof["score"] is not None:
                out.append("| %s | %s | %.1f/100 |"
                           % (_md_cell(prof["label"]),
                              _md_cell(prof["focus"]),
                              prof["score"]))
        if cit["index"] is not None:
            out.append(T("| **Indice composito (%s)** | | "
                         "**%.1f/100** |",
                         "| **Composite index (%s)** | | "
                         "**%.1f/100** |")
                       % (_md_cell(cit["market"]), cit["index"]))
        out.append("")
        out.append("> %s" % cit["note"])
        out.append("")

    if delta:
        out.append(T("## Rispetto all'esecuzione precedente (%s)",
                     "## Compared with the previous run (%s)")
                   % (delta.get("previous_generated_at") or ""))
        out.append("")
        variazioni = " · ".join(
            "%s **%+.1f**"
            % (_md_cell(area_label.get(area, area)), value)
            if value else "%s =" % _md_cell(area_label.get(area, area))
            for area, value in dict(delta["scores"]).items())
        if variazioni:
            out.append(variazioni)
            out.append("")
        for label, items in ((T("Risolti", "Resolved"),
                              delta["resolved"]),
                             (T("Nuovi", "New"), delta["new"])):
            out.append("**%s (%d):**" % (label, len(list(items))))
            for f in items:
                out.append("- %s %s"
                           % (marks.get(str(f["severity"]), ""),
                              f["title"]))
            if not items:
                out.append(T("- nessuno", "- none"))
            out.append("")

    if judge and judge.get("status") == "ok":
        out.append(T("## Giudizio LLM sulla citabilita'",
                     "## LLM judgement on citability"))
        out.append("")
        out.append(T("Modello `%s` su %d passaggio/i · media "
                     "**%.1f/100**.",
                     "Model `%s` on %d passage(s) · average "
                     "**%.1f/100**.") % (judge["model"],
                                         judge["sampled"],
                                         judge["average"]))
        out.append("")
        out.append(T("| Query | Punteggio | Motivazione |",
                     "| Query | Score | Rationale |"))
        out.append("|---|---:|---|")
        for v in judge["verdicts"]:
            out.append("| %s | %.1f | %s |"
                       % (_md_cell(v["query"]), v["score"],
                          _md_cell(v["reason"])))
        out.append("")
        out.append("> %s" % judge["note"])
        out.append("")

    if lighthouse:
        out.append(T("## Audit Lighthouse", "## Lighthouse audit"))
        out.append("")
        if lighthouse.get("status") == "ok":
            fork = str(lighthouse.get("fork") or "")
            out.append(
                (T("Eseguito su %d pagina/e (%s)%s.",
                   "Run on %d page(s) (%s)%s."))
                % (len(lighthouse.get("pages") or []),
                   lighthouse.get("device", ""),
                   (", fork %s" % fork) if fork else ""))
            out.append("")
            for c in lighthouse.get("categories") or []:
                out.append("- %s: **%d/100**"
                           % (_md_cell(str(c["title"])),
                              c["score"]))
        else:
            out.append(T("Non eseguito: %s", "Not run: %s")
                       % lighthouse.get("reason", ""))
        out.append("")

    if search_check:
        out.append(T("## Ancora di realta' (Brave Search)",
                     "## Reality anchor (Brave Search)"))
        out.append("")
        if search_check.get("status") == "ok":
            interrogate = search_check.get("queries") or []
            top_n = search_check.get("top_n", 0)
            out.append(
                (T("Sito trovato per %d query su %d "
                   "(primi %d risultati).",
                   "Site found for %d of %d queries "
                   "(top %d results)."))
                % (search_check.get("found", 0),
                   len(interrogate), top_n))
            out.append("")
            for q in interrogate:
                if q.get("error"):
                    esito = T("errore: %s", "error: %s") \
                        % q["error"]
                elif q.get("position"):
                    esito = T("posizione **#%d**",
                              "position **#%d**") % q["position"]
                else:
                    esito = T("assente dai primi %d",
                              "absent from the top %d") % top_n
                out.append("- %s — %s (%s %s)"
                           % (_md_cell(str(q.get("query", ""))),
                              esito,
                              T("consenso RRF", "RRF consensus"),
                              q.get("rrf_consensus", 0)))
            out.append("")
            out.append("> %s" % search_check.get("note", ""))
        else:
            out.append(T("Non eseguita: %s", "Not run: %s")
                       % search_check.get("reason", ""))
        out.append("")

    plan = build_remediation(findings, pages, scores, market)
    if plan:
        out.append(T("## Piano di remediation",
                     "## Remediation plan"))
        out.append("")
        for item in plan:
            tag = (T("CRITICO", "CRITICAL")
                   if item["severity"] == SEV_CRITICAL
                   else T("AVVISO", "WARNING"))
            extra = ""
            if item["quick_win"]:
                extra += " · QUICK WIN"
            if item.get("cross"):
                extra += (T(" · trasversale: %d profili",
                            " · cross-cutting: %d profiles")
                          % len(list(item["profiles_hit"])))
            out.append(T("- [ ] **%d.** %s _(%s · %s · sforzo: "
                         "%s%s)_",
                         "- [ ] **%d.** %s _(%s · %s · effort: "
                         "%s%s)_")
                       % (item["priority"],
                          finding_texts(item, lang)["title"], tag,
                          area_label.get(str(item["area"]),
                                         item["area"]),
                          item["effort"], extra))
        out.append("")

    out.append(T("## Rilievi per area", "## Findings by area"))
    for area in ALL_AREAS:
        subset = [f for f in findings if f.area == area]
        if not subset:
            continue
        out.append("")
        out.append("### %s" % area_label.get(area, area))
        out.append("")
        order = {SEV_CRITICAL: 0, SEV_WARNING: 1, SEV_INFO: 2,
                 SEV_OK: 3}
        for f in sorted(subset, key=lambda x: order[x.severity]):
            texts = finding_texts(f, lang)
            out.append("- %s %s" % (marks[f.severity],
                                    texts["title"]))
            if texts["detail"]:
                out.append("  %s" % texts["detail"])
            if texts["fix"]:
                out.append("  _Fix: %s_" % texts["fix"])
    out.append("")

    if results:
        out.append(T("## Simulazione RRF per query",
                     "## RRF simulation per query"))
        out.append("")
        out.append(T("| Query | Consenso | Primo passaggio fuso |",
                     "| Query | Consensus | Top fused passage |"))
        out.append("|---|---:|---|")
        for res in results:
            primo = (res.fused_top[0][0] if res.fused_top
                     else T("(nessuno)", "(none)"))
            out.append("| %s | %d | %s |"
                       % (_md_cell(res.query), res.consensus,
                          _md_cell(primo[:70])))
        out.append("")

    if competitive:
        out.append(T("## Share of voice (primi %d posti fusi)",
                     "## Share of voice (first %d fused slots)")
                   % competitive["top_n"])
        out.append("")
        out.append(T("| Sito | Quota |", "| Site | Share |"))
        out.append("|---|---:|")
        share = competitive["share"]
        for host in competitive["sites"]:
            marker = (T(" ← tuo sito", " ← your site")
                      if host == competitive["main"] else "")
            out.append("| %s%s | %.1f%% |"
                       % (_md_cell(host), marker, share[host]))
        out.append("")

    return "\n".join(out)


def render_csv(base: str, pages: List[Page],
               findings: List[Finding],
               scores: Dict[str, Optional[float]],
               results: List[QueryResult], mode: str,
               k: int = 60,
               competitive: Optional[Dict[str, object]] = None,
               market: str = DEFAULT_MARKET,
               judge: Optional[Dict[str, object]] = None,
               delta: Optional[Dict[str, object]] = None,
               lighthouse: Optional[Dict[str, object]] = None,
               search_check: Optional[Dict[str, object]] = None,
               lang: str = "it") -> str:
    """Export CSV dei rilievi, una riga per rilievo.

    I rilievi Lighthouse hanno gia' l'origine dichiarata (area
    "Performance (Lighthouse)", chiavi ``lh.*``): ``lighthouse``
    e' accettato per uniformita' di firma coi renderer di prosa.

    Pensato per Excel/Sheets: delimitatore ';' e BOM UTF-8 in
    testa, cosi' l'apertura diretta preserva accenti e colonne.
    Sforzo e quick win sono valorizzati solo per i rilievi
    azionabili (critici e avvertenze). Con ``lang="en"`` le
    intestazioni e i testi dei rilievi sono in inglese (le
    evidenze del sito restano nella lingua del sito).
    """
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";", lineterminator="\n")
    if lang == "en":
        writer.writerow(["site", "area", "severity", "weight",
                         "title", "detail", "fix", "url", "effort",
                         "quick_win"])
    else:
        writer.writerow(["sito", "area", "gravita", "peso",
                         "titolo", "dettaglio", "correzione", "url",
                         "sforzo", "quick_win"])
    for f in findings:
        actionable = f.severity in (SEV_CRITICAL, SEV_WARNING)
        effort = estimate_effort(f) if actionable else ""
        quick = (("si" if lang != "en" else "yes")
                 if f.severity == SEV_CRITICAL
                 and effort == EFFORT_MINUTES else "")
        texts = finding_texts(f, lang)
        writer.writerow([base, f.area, f.severity, f.weight,
                         texts["title"], texts["detail"],
                         texts["fix"], f.url, effort, quick])
    return "\ufeff" + buffer.getvalue()
