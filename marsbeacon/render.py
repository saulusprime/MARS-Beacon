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
    build_remediation,
    citability_profiles,
    citability_top_actions,
    overall_score)
from marsbeacon.i18n import (
    _AREA_I18N,
    _HTML_I18N,
    csv_header,
    csv_yes,
    evidence_note,
    finding_texts,
    frame_text)


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
        return frame_text(it_text, en_text, lang)

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
    nota_evidenze = evidence_note(lang)
    if nota_evidenze:
        lines.append(nota_evidenze)
    lines.append("")
    lines.append(T("PUNTEGGI", "SCORES"))
    area_label = _AREA_I18N.get(lang, {})
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
                rrf_params: Optional[Dict[str, object]] = None,
                thresholds: Optional[Dict[str, object]] = None
                ) -> str:
    """Referto JSON, adatto a essere versionato o messo in pipeline.

    ``thresholds`` echeggia le soglie personalizzate da --config
    (None con i default): campo additivo, per la riproducibilita'
    — due referti con soglie diverse non sono confrontabili alla
    pari e il JSON lo dichiara.
    """
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
        "thresholds": thresholds,
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
        return frame_text(it_text, en_text, lang)

    marks = {SEV_CRITICAL: T("**[CRITICO]**", "**[CRITICAL]**"),
             SEV_WARNING: T("[AVVISO]", "[WARNING]"),
             SEV_OK: "[ok]", SEV_INFO: "[info]"}
    area_label = _AREA_I18N.get(lang, {})
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
    nota_evidenze = evidence_note(lang)
    if nota_evidenze:
        out.append("> %s" % nota_evidenze)
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
    azionabili (critici e avvertenze). Con una ``lang`` diversa da
    "it" le intestazioni e i testi dei rilievi sono tradotti (le
    evidenze del sito restano nella lingua del sito).
    """
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";", lineterminator="\n")
    writer.writerow(csv_header(lang))
    for f in findings:
        actionable = f.severity in (SEV_CRITICAL, SEV_WARNING)
        effort = estimate_effort(f) if actionable else ""
        quick = (csv_yes(lang)
                 if f.severity == SEV_CRITICAL
                 and effort == EFFORT_MINUTES else "")
        texts = finding_texts(f, lang)
        writer.writerow([base, f.area, f.severity, f.weight,
                         texts["title"], texts["detail"],
                         texts["fix"], f.url, effort, quick])
    return "\ufeff" + buffer.getvalue()
