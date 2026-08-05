#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Monitoraggio delle citazioni IA effettive di un sito.

Interroga i principali assistenti IA con ricerca web sulle query
target del sito e verifica se il sito (ed eventuali concorrenti)
viene citato nelle risposte. Pensato per esecuzioni periodiche
(cron/systemd timer): ogni esecuzione puo' essere accodata a uno
storico JSONL e confrontata con la precedente.

Provider supportati:
  - anthropic   Claude (SDK ufficiale, strumento web_search).
                Richiede: pip install anthropic e ANTHROPIC_API_KEY
                (o un profilo `ant auth login`).
  - perplexity  Perplexity Sonar. Richiede PERPLEXITY_API_KEY.
  - openai      ChatGPT via Responses API con web_search.
                Richiede OPENAI_API_KEY.

Le chiavi API si passano SOLO via variabili d'ambiente, mai da
riga di comando.

Uso:
    python3 mars_citations.py https://miosito.it --queries q.txt
    python3 mars_citations.py https://miosito.it \\
        --from-audit referto.json --provider anthropic \\
        --competitor concorrente.it --history storico.jsonl \\
        --fail-under 30

Codici di uscita: 0 ok; 1 tasso di citazione sotto --fail-under;
2 errore d'uso o provider non configurato.

Licenza: MIT.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple
from urllib.parse import urlparse

import requests

__version__ = "1.2.0"

DEFAULT_MODEL = "claude-opus-5"
OPENAI_MODEL = "gpt-5.6"
MAX_QUERIES = 15
WEB_SEARCH_MAX_USES = 5
PAUSE_TURN_RESTARTS = 5


# --------------------------------------------------------------------
# Host e citazioni
# --------------------------------------------------------------------

def norm_host(url_or_host: str) -> str:
    """Host normalizzato: minuscolo, senza www., senza schema."""
    value = url_or_host.strip().lower()
    if "://" in value:
        value = urlparse(value).netloc or value
    value = value.split("/")[0].split(":")[0]
    if value.startswith("www."):
        value = value[4:]
    return value


def host_matches(url: str, target_host: str) -> bool:
    """True se l'URL appartiene all'host (sottodomini inclusi)."""
    host = norm_host(url)
    return host == target_host or host.endswith("." + target_host)


@dataclass
class ProviderAnswer:
    """Esito di una singola query su un provider."""

    provider: str
    query: str
    ok: bool = True
    error: str = ""
    cited_urls: List[str] = field(default_factory=list)
    searched_urls: List[str] = field(default_factory=list)


# --------------------------------------------------------------------
# Provider
# --------------------------------------------------------------------

class AnthropicProvider:
    """Claude con ricerca web, tramite l'SDK ufficiale.

    Nota: la richiesta include di default il fallback server-side
    (``fallbacks="default"``): se i classificatori di sicurezza
    declinano una query, la stessa richiesta viene rieseguita sul
    modello di ripiego raccomandato invece di andare persa.
    """

    name = "anthropic"

    def __init__(self, model: str = DEFAULT_MODEL,
                 api_key: Optional[str] = None,
                 base_url: Optional[str] = None) -> None:
        try:
            import anthropic
        except ImportError:
            raise RuntimeError(
                "provider 'anthropic' richiede l'SDK ufficiale: "
                "pip install anthropic")
        kwargs: Dict[str, object] = {}
        if api_key:
            kwargs["api_key"] = api_key
        if base_url:
            kwargs["base_url"] = base_url
        self._anthropic = anthropic
        self._client = anthropic.Anthropic(**kwargs)
        self.model = model

    def ask(self, query: str) -> ProviderAnswer:
        answer = ProviderAnswer(provider=self.name, query=query)
        messages: List[Dict[str, object]] = [
            {"role": "user", "content": query}]
        try:
            for _ in range(PAUSE_TURN_RESTARTS):
                resp = self._client.beta.messages.create(
                    model=self.model,
                    max_tokens=16000,
                    betas=["server-side-fallback-2026-07-01"],
                    fallbacks="default",
                    tools=[{
                        "type": "web_search_20260209",
                        "name": "web_search",
                        "max_uses": WEB_SEARCH_MAX_USES,
                    }],
                    messages=messages,
                )
                self._collect(resp, answer)
                if resp.stop_reason == "pause_turn":
                    messages = [messages[0], {
                        "role": "assistant", "content": resp.content}]
                    continue
                if resp.stop_reason == "refusal":
                    answer.ok = False
                    answer.error = "richiesta declinata dai " \
                                   "classificatori di sicurezza"
                break
        except self._anthropic.APIError as exc:
            answer.ok = False
            answer.error = "errore API Anthropic: %s" % exc
        return answer

    @staticmethod
    def _collect(resp: object, answer: ProviderAnswer) -> None:
        """Estrae URL citati e fonti consultate dai blocchi."""
        for block in getattr(resp, "content", []) or []:
            btype = getattr(block, "type", "")
            if btype == "text":
                for cit in getattr(block, "citations", None) or []:
                    url = getattr(cit, "url", "") or ""
                    if url and url not in answer.cited_urls:
                        answer.cited_urls.append(url)
            elif btype == "web_search_tool_result":
                content = getattr(block, "content", None)
                if not isinstance(content, list):
                    continue  # oggetto errore, non lista di risultati
                for item in content:
                    url = getattr(item, "url", "") or ""
                    if url and url not in answer.searched_urls:
                        answer.searched_urls.append(url)


class PerplexityProvider:
    """Perplexity Sonar: risposte native con citazioni."""

    name = "perplexity"
    endpoint = "https://api.perplexity.ai/chat/completions"

    def __init__(self, api_key: Optional[str] = None,
                 endpoint: Optional[str] = None) -> None:
        self.api_key = api_key or os.environ.get(
            "PERPLEXITY_API_KEY", "")
        if not self.api_key:
            raise RuntimeError(
                "provider 'perplexity' richiede la variabile "
                "d'ambiente PERPLEXITY_API_KEY")
        if endpoint:
            self.endpoint = endpoint

    def ask(self, query: str) -> ProviderAnswer:
        answer = ProviderAnswer(provider=self.name, query=query)
        try:
            resp = requests.post(
                self.endpoint,
                headers={"Authorization": "Bearer %s" % self.api_key},
                json={"model": "sonar",
                      "messages": [{"role": "user", "content": query}]},
                timeout=60)
        except requests.RequestException as exc:
            answer.ok = False
            answer.error = "errore di rete: %s" % exc
            return answer
        if resp.status_code != 200:
            answer.ok = False
            answer.error = "HTTP %d" % resp.status_code
            return answer
        data = resp.json()
        for url in data.get("citations", []) or []:
            if isinstance(url, str) and url not in answer.cited_urls:
                answer.cited_urls.append(url)
        for item in data.get("search_results", []) or []:
            url = item.get("url", "") if isinstance(item, dict) else ""
            if url and url not in answer.searched_urls:
                answer.searched_urls.append(url)
        return answer


class OpenAIProvider:
    """ChatGPT con ricerca web, via Responses API.

    POST /v1/responses con tool ``{"type": "web_search"}``: le
    citazioni stanno nelle annotation ``url_citation`` dei blocchi
    di testo del messaggio; le fonti consultate, quando esposte,
    nel campo ``sources`` dell'item ``web_search_call``. Fonte:
    developers.openai.com, guida "Web search" (verificata il
    2026-08-04).
    """

    name = "openai"
    endpoint = "https://api.openai.com/v1/responses"

    def __init__(self, model: str = OPENAI_MODEL,
                 api_key: Optional[str] = None,
                 endpoint: Optional[str] = None) -> None:
        self.api_key = api_key or os.environ.get(
            "OPENAI_API_KEY", "")
        if not self.api_key:
            raise RuntimeError(
                "provider 'openai' richiede la variabile "
                "d'ambiente OPENAI_API_KEY")
        if endpoint:
            self.endpoint = endpoint
        self.model = model

    def ask(self, query: str) -> ProviderAnswer:
        answer = ProviderAnswer(provider=self.name, query=query)
        try:
            resp = requests.post(
                self.endpoint,
                headers={"Authorization": "Bearer %s"
                                          % self.api_key},
                json={"model": self.model,
                      "tools": [{"type": "web_search"}],
                      "input": query},
                timeout=90)
        except requests.RequestException as exc:
            answer.ok = False
            answer.error = "errore di rete: %s" % exc
            return answer
        if resp.status_code != 200:
            answer.ok = False
            answer.error = "HTTP %d" % resp.status_code
            return answer
        data = resp.json()
        for item in data.get("output", []) or []:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "message":
                for block in item.get("content", []) or []:
                    if not isinstance(block, dict):
                        continue
                    for ann in block.get("annotations", []) or []:
                        if isinstance(ann, dict) \
                                and ann.get("type") \
                                == "url_citation":
                            url = str(ann.get("url", ""))
                            if url and url not in answer.cited_urls:
                                answer.cited_urls.append(url)
            elif item.get("type") == "web_search_call":
                action = item.get("action")
                sources = []
                if isinstance(action, dict):
                    sources = action.get("sources") or []
                sources = sources or item.get("sources") or []
                for src in sources:
                    url = (src.get("url", "")
                           if isinstance(src, dict) else str(src))
                    if url and url not in answer.searched_urls:
                        answer.searched_urls.append(url)
        return answer


PROVIDERS = {
    "anthropic": AnthropicProvider,
    "perplexity": PerplexityProvider,
    "openai": OpenAIProvider,
}


# --------------------------------------------------------------------
# Monitoraggio
# --------------------------------------------------------------------

def evaluate_answer(answer: ProviderAnswer, site_host: str,
                    competitor_hosts: Sequence[str]) -> Dict[str, object]:
    """Riduce una risposta al dato che interessa: chi e' citato."""
    return {
        "query": answer.query,
        "ok": answer.ok,
        "error": answer.error,
        "site_cited": any(host_matches(u, site_host)
                          for u in answer.cited_urls),
        "site_consulted": any(host_matches(u, site_host)
                              for u in answer.searched_urls),
        "competitors_cited": sorted({
            host for host in competitor_hosts
            for u in answer.cited_urls if host_matches(u, host)}),
        "cited_urls": answer.cited_urls,
    }


def run_monitor(site: str, queries: Sequence[str],
                providers: Sequence[object],
                competitors: Sequence[str] = (),
                delay: float = 1.0,
                verbose: bool = True) -> Dict[str, object]:
    """Esegue tutte le query su tutti i provider e aggrega."""
    site_host = norm_host(site)
    competitor_hosts = [norm_host(c) for c in competitors]
    payload: Dict[str, object] = {
        "tool": "mars_citations.py",
        "version": __version__,
        "site": site_host,
        "competitors": competitor_hosts,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "queries": list(queries),
        "providers": {},
    }
    for provider in providers:
        rows: List[Dict[str, object]] = []
        for i, query in enumerate(queries):
            if verbose:
                print("  [%s] %d/%d %s" % (provider.name, i + 1,
                                           len(queries), query),
                      file=sys.stderr)
            rows.append(evaluate_answer(provider.ask(query),
                                        site_host, competitor_hosts))
            if delay and i + 1 < len(queries):
                time.sleep(delay)
        answered = [r for r in rows if r["ok"]]
        cited = [r for r in answered if r["site_cited"]]
        comp_counts = {host: sum(1 for r in answered
                                 if host in r["competitors_cited"])
                       for host in competitor_hosts}
        payload["providers"][provider.name] = {
            "answered": len(answered),
            "failed": len(rows) - len(answered),
            "site_cited": len(cited),
            "rate": round(100.0 * len(cited) / len(answered), 1)
            if answered else 0.0,
            "competitors_cited": comp_counts,
            "results": rows,
        }
    return payload


def overall_rate(payload: Dict[str, object]) -> Optional[float]:
    """Tasso complessivo di citazione su tutti i provider."""
    answered = cited = 0
    for stats in payload["providers"].values():
        answered += stats["answered"]
        cited += stats["site_cited"]
    if not answered:
        return None
    return round(100.0 * cited / answered, 1)


# --------------------------------------------------------------------
# Storico
# --------------------------------------------------------------------

def read_last_run(path: str, site_host: str) -> Optional[Dict[str, object]]:
    """Ultima esecuzione registrata per lo stesso sito."""
    try:
        with open(path, encoding="utf-8") as handle:
            last = None
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if row.get("site") == site_host:
                    last = row
            return last
    except OSError:
        return None


def append_history(path: str, payload: Dict[str, object]) -> None:
    """Accoda l'esecuzione allo storico JSONL (senza i dettagli)."""
    compact = {
        "generated_at": payload["generated_at"],
        "site": payload["site"],
        "overall_rate": overall_rate(payload),
        "providers": {
            name: {k: stats[k] for k in
                   ("answered", "failed", "site_cited", "rate",
                    "competitors_cited")}
            for name, stats in payload["providers"].items()
        },
    }
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(compact, ensure_ascii=False) + "\n")


# --------------------------------------------------------------------
# Referti
# --------------------------------------------------------------------

def render_text(payload: Dict[str, object],
                previous: Optional[Dict[str, object]] = None) -> str:
    lines: List[str] = []
    lines.append("=" * 70)
    lines.append("CITAZIONI IA  ·  %s" % payload["site"])
    lines.append("=" * 70)
    for name, stats in payload["providers"].items():
        lines.append("")
        lines.append("[%s]  citato in %d risposte su %d (%.1f%%)"
                     "%s" % (name, stats["site_cited"],
                             stats["answered"], stats["rate"],
                             "  ·  %d query fallite" % stats["failed"]
                             if stats["failed"] else ""))
        for host, count in stats["competitors_cited"].items():
            lines.append("    concorrente %-32s citato %d volte"
                         % (host, count))
        for row in stats["results"]:
            if not row["ok"]:
                mark = "ERR"
            elif row["site_cited"]:
                mark = "CITATO"
            elif row["site_consulted"]:
                mark = "consultato"
            else:
                mark = "assente"
            extra = (" · concorrenti: %s"
                     % ", ".join(row["competitors_cited"])
                     if row["competitors_cited"] else "")
            lines.append("    %-46s %s%s"
                         % (row["query"][:46], mark, extra))
    rate = overall_rate(payload)
    lines.append("")
    lines.append("Tasso complessivo di citazione: %s"
                 % ("%.1f%%" % rate if rate is not None else "n/d"))
    if previous and previous.get("overall_rate") is not None \
            and rate is not None:
        delta = rate - previous["overall_rate"]
        lines.append("Esecuzione precedente (%s): %.1f%%  ·  delta %+.1f"
                     % (previous.get("generated_at", "?"),
                        previous["overall_rate"], delta))
    return "\n".join(lines)


def render_json(payload: Dict[str, object],
                previous: Optional[Dict[str, object]] = None) -> str:
    out = dict(payload)
    out["overall_rate"] = overall_rate(payload)
    out["previous"] = previous
    return json.dumps(out, indent=2, ensure_ascii=False)


# --------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------

def load_queries(args: argparse.Namespace) -> Tuple[List[str], str]:
    """Query da --queries o --from-audit; (lista, errore)."""
    if args.queries:
        try:
            with open(args.queries, encoding="utf-8") as handle:
                return ([ln.strip() for ln in handle
                         if ln.strip()][:args.max_queries], "")
        except OSError as exc:
            return [], "Impossibile leggere %s: %s" % (args.queries, exc)
    if args.from_audit:
        try:
            with open(args.from_audit, encoding="utf-8") as handle:
                report = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            return [], "Referto non leggibile %s: %s" % (args.from_audit,
                                                         exc)
        queries = [row.get("query", "") for row
                   in report.get("rrf_simulation", [])]
        queries = [q for q in queries if q][:args.max_queries]
        if not queries:
            return [], "Nessuna query nel referto (rrf_simulation)."
        return queries, ""
    return [], "Servono le query: --queries FILE oppure --from-audit " \
               "REFERTO.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mars_citations.py",
        description="Monitoraggio delle citazioni IA effettive di un "
                    "sito nelle risposte degli assistenti con ricerca "
                    "web.")
    parser.add_argument("site", help="sito da monitorare (URL o host)")
    parser.add_argument("--queries", metavar="FILE",
                        help="file con una query per riga")
    parser.add_argument("--from-audit", metavar="REFERTO",
                        help="referto JSON di mars_audit.py da cui "
                             "riusare le query della simulazione RRF")
    parser.add_argument("--provider", action="append",
                        dest="providers", default=[],
                        choices=sorted(PROVIDERS),
                        help="provider da interrogare (ripetibile; "
                             "default: anthropic)")
    parser.add_argument("--competitor", metavar="HOST",
                        action="append", dest="competitors",
                        default=[],
                        help="concorrente di cui tracciare le "
                             "citazioni (ripetibile, max 3)")
    parser.add_argument("--model", default=DEFAULT_MODEL,
                        help="modello Claude per il provider "
                             "anthropic (default %s)" % DEFAULT_MODEL)
    parser.add_argument("--openai-model", default=OPENAI_MODEL,
                        dest="openai_model",
                        help="modello per il provider openai "
                             "(default %s)" % OPENAI_MODEL)
    parser.add_argument("--max-queries", type=int, default=MAX_QUERIES,
                        help="numero massimo di query (default %d)"
                             % MAX_QUERIES)
    parser.add_argument("--delay", type=float, default=1.0,
                        help="pausa fra le query in secondi")
    parser.add_argument("--history", metavar="FILE",
                        help="storico JSONL: accoda l'esecuzione e "
                             "mostra il delta con la precedente")
    parser.add_argument("--fail-under", type=float, metavar="PCT",
                        help="esce con codice 1 se il tasso "
                             "complessivo e' sotto questa soglia")
    parser.add_argument("--format", choices=("text", "json"),
                        default="text", help="formato del referto")
    parser.add_argument("--output", metavar="FILE",
                        help="scrive il referto su file")
    parser.add_argument("--quiet", action="store_true",
                        help="non stampa l'avanzamento")
    parser.add_argument("--version", action="version",
                        version="%(prog)s " + __version__)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    if len(args.competitors) > 3:
        print("Massimo 3 concorrenti con --competitor.",
              file=sys.stderr)
        return 2

    queries, err = load_queries(args)
    if err:
        print(err, file=sys.stderr)
        return 2

    provider_names = args.providers or ["anthropic"]
    providers: List[object] = []
    for name in dict.fromkeys(provider_names):
        try:
            if name == "anthropic":
                providers.append(AnthropicProvider(model=args.model))
            elif name == "openai":
                providers.append(
                    OpenAIProvider(model=args.openai_model))
            else:
                providers.append(PROVIDERS[name]())
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            return 2

    payload = run_monitor(args.site, queries, providers,
                          competitors=args.competitors,
                          delay=args.delay, verbose=not args.quiet)

    previous = None
    if args.history:
        previous = read_last_run(args.history, payload["site"])
        append_history(args.history, payload)

    renderers = {"text": render_text, "json": render_json}
    report = renderers[args.format](payload, previous)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(report)
        print("Referto scritto in %s" % args.output, file=sys.stderr)
    else:
        print(report)

    rate = overall_rate(payload)
    if args.fail_under is not None and rate is not None \
            and rate < args.fail_under:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
