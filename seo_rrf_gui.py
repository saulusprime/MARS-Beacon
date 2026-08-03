#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Interfaccia web locale per seo_rrf_audit.py.

Avvia un server HTTP sulla macchina locale (default 127.0.0.1:8765)
che serve una interfaccia grafica in Bootstrap Italia (cartella
``gui/``) e alcune API JSON per pilotare l'audit e fruire dei referti:

    GET  /                  interfaccia grafica
    GET  /api/env           versione, RAM disponibile, valori suggeriti
    POST /api/audit         avvia un audit (uno alla volta)
    GET  /api/status        stato, log di avanzamento, sintesi finale
    GET  /api/report/html   referto HTML dell'ultimo audit
    GET  /api/report/json   referto JSON
    GET  /api/report/text   referto testuale

L'audit viene eseguito in-process (import di ``seo_rrf_audit``): una
sola scansione del sito produce tutti e tre i formati di referto.
Nessuna dipendenza oltre a quelle dello script; il frontend usa asset
vendorizzati in ``gui/vendor`` e funziona anche senza rete.

Uso:
    python3 seo_rrf_gui.py [--host 127.0.0.1] [--port 8765]

Licenza: MIT.
"""

from __future__ import annotations

import argparse
import contextlib
import importlib.util
import json
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import seo_rrf_audit as sra

__version__ = "1.5.0"

GUI_DIR = Path(__file__).resolve().parent / "gui"

CONTENT_TYPES: Dict[str, str] = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".woff2": "font/woff2",
    ".woff": "font/woff",
    ".png": "image/png",
    ".ico": "image/x-icon",
}

CSP = ("default-src 'self'; style-src 'self' 'unsafe-inline'; "
       "img-src 'self' data:; object-src 'none'; "
       "frame-ancestors 'self'; base-uri 'self'")


class LineBuffer:
    """File-like che accumula righe complete in una lista condivisa."""

    def __init__(self, lines: List[str], lock: threading.Lock) -> None:
        self.lines = lines
        self.lock = lock
        self._partial = ""

    def write(self, text: str) -> int:
        self._partial += text
        while "\n" in self._partial:
            line, self._partial = self._partial.split("\n", 1)
            if line.strip():
                with self.lock:
                    self.lines.append(line.rstrip())
        return len(text)

    def flush(self) -> None:
        if self._partial.strip():
            with self.lock:
                self.lines.append(self._partial.rstrip())
        self._partial = ""


class Job:
    """Stato dell'audit corrente (uno alla volta)."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.state = "idle"  # idle | running | done | error
        self.log: List[str] = []
        self.error = ""
        self.config: Dict[str, object] = {}
        self.summary: Dict[str, object] = {}
        self.findings: List[Dict[str, object]] = []
        self.rrf: List[Dict[str, object]] = []
        self.competitive: Optional[Dict[str, object]] = None
        self.reports: Dict[str, str] = {}

    def snapshot(self) -> Dict[str, object]:
        with self.lock:
            return {
                "state": self.state,
                "log": list(self.log),
                "error": self.error,
                "config": dict(self.config),
                "summary": dict(self.summary),
                "findings": list(self.findings),
                "rrf": list(self.rrf),
                "competitive": self.competitive,
            }

    def start(self, config: Dict[str, object]) -> bool:
        """Passa a 'running' se libero; False se un audit e' in corso."""
        with self.lock:
            if self.state == "running":
                return False
            self.state = "running"
            self.log = []
            self.error = ""
            self.config = config
            self.summary = {}
            self.findings = []
            self.rrf = []
            self.competitive = None
            self.reports = {}
            return True

    def run(self) -> None:
        """Esegue l'audit (nel thread di lavoro) e salva i referti."""
        cfg = self.config
        buf = LineBuffer(self.log, self.lock)
        try:
            with contextlib.redirect_stderr(buf):
                (pages, findings, scores, results, mode,
                 competitive) = sra.run_audit(
                    base=str(cfg["url"]),
                    max_pages=int(cfg["max_pages"]),
                    queries=list(cfg["queries"]),
                    model_name=str(cfg["embeddings"]),
                    delay=float(cfg["delay"]),
                    k=int(cfg["rrf_k"]),
                    verbose=True,
                    max_body_mb=float(cfg["max_body"]),
                    respect_robots=bool(cfg["respect_robots"]),
                    retries=int(cfg["retries"]),
                    competitors=list(cfg["competitors"]))
            buf.flush()
        except Exception as exc:  # noqa: BLE001 - riportato alla GUI
            buf.flush()
            with self.lock:
                self.state = "error"
                self.error = "%s: %s" % (type(exc).__name__, exc)
            return

        k = int(cfg["rrf_k"])
        base = str(cfg["url"])
        reports = {
            "html": sra.render_html(base, pages, findings, scores,
                                    results, mode, k, competitive),
            "json": sra.render_json(base, pages, findings, scores,
                                    results, mode, k, competitive),
            "text": sra.render_text(base, pages, findings, scores,
                                    results, mode, k, competitive),
        }
        severities = [f.severity for f in findings]
        clean, flagged, broken = sra.page_status_counts(pages,
                                                        findings)
        summary = {
            "site": base,
            "overall": sra.overall_score(scores),
            "scores": scores,
            "vector_retriever": mode,
            "rrf_k": k,
            "pages_ok": len([p for p in pages if p.ok]),
            "pages_total": len(pages),
            "pages_clean": clean,
            "pages_flagged": flagged,
            "pages_error": broken,
            "chunks": sum(len(p.chunks) for p in pages if p.ok),
            "critical": severities.count(sra.SEV_CRITICAL),
            "warning": severities.count(sra.SEV_WARNING),
            "info": severities.count(sra.SEV_INFO),
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        }
        with self.lock:
            self.reports = reports
            self.summary = summary
            self.findings = [f.as_dict() for f in findings]
            self.rrf = [sra.asdict(r) for r in results]
            self.competitive = competitive
            self.state = "done"

    def report(self, fmt: str) -> Optional[str]:
        with self.lock:
            return self.reports.get(fmt)


JOB = Job()


def validate_config(raw: Dict[str, object]) -> Tuple[
        Optional[Dict[str, object]], str]:
    """Valida il corpo di POST /api/audit; (config, "") o (None, err)."""
    url = str(raw.get("url", "")).strip()
    if not url:
        return None, "URL mancante."
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    def number(name: str, default: float, lo: float,
               hi: float) -> Optional[float]:
        try:
            value = float(raw.get(name, default))
        except (TypeError, ValueError):
            return None
        return value if lo <= value <= hi else None

    max_pages = number("max_pages", 25, 1, 500)
    rrf_k = number("rrf_k", 60, 1, 1000)
    delay = number("delay", 0.5, 0, 10)
    max_body = number("max_body", sra.DEFAULT_MAX_BODY_MB, 1, 10240)
    retries = number("retries", sra.DEFAULT_RETRIES, 0, 10)
    checks = (("max_pages", max_pages), ("rrf_k", rrf_k),
              ("delay", delay), ("max_body", max_body),
              ("retries", retries))
    for name, value in checks:
        if value is None:
            return None, "Valore non valido per '%s'." % name

    queries = [q.strip() for q in str(raw.get("queries", "")).split("\n")
               if q.strip()]

    competitors = [c.strip() for c in
                   str(raw.get("competitors", "")).split("\n")
                   if c.strip()]
    if len(competitors) > 3:
        return None, "Massimo 3 siti concorrenti."
    competitors = [
        c if c.startswith(("http://", "https://")) else "https://" + c
        for c in competitors
    ]

    return {
        "url": url,
        "max_pages": int(max_pages),
        "rrf_k": int(rrf_k),
        "delay": delay,
        "max_body": max_body,
        "retries": int(retries),
        "queries": queries,
        "embeddings": str(raw.get("embeddings", "")).strip(),
        "respect_robots": bool(raw.get("respect_robots", False)),
        "competitors": competitors,
    }, ""


class Handler(BaseHTTPRequestHandler):
    """Instrada API e file statici della GUI."""

    server_version = "SeoRrfGui/%s" % __version__

    def _send(self, status: int, body: bytes, ctype: str,
              download: str = "") -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", CSP)
        self.send_header("Cache-Control", "no-store")
        if download:
            self.send_header("Content-Disposition",
                             'attachment; filename="%s"' % download)
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, status: int, payload: Dict[str, object]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._send(status, body, CONTENT_TYPES[".json"])

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

    def do_GET(self) -> None:  # noqa: N802 - firma di BaseHTTPServer
        path = self.path.split("?", 1)[0]
        if path == "/api/env":
            ram = sra.available_ram_mb()
            suggested = (max(1, round(ram * 0.1))
                         if ram is not None else None)
            spec = importlib.util.find_spec("sentence_transformers")
            self._send_json(200, {
                "tool_version": sra.__version__,
                "gui_version": __version__,
                "default_max_body_mb": sra.DEFAULT_MAX_BODY_MB,
                "available_ram_mb": ram,
                "suggested_max_body_mb": suggested,
                "embeddings_available": spec is not None,
            })
        elif path == "/api/status":
            self._send_json(200, JOB.snapshot())
        elif path.startswith("/api/report/"):
            fmt = path.rsplit("/", 1)[-1]
            report = JOB.report(fmt)
            if fmt not in ("html", "json", "text") or report is None:
                self._send_json(404, {"error": "referto non disponibile"})
                return
            ctypes = {"html": CONTENT_TYPES[".html"],
                      "json": CONTENT_TYPES[".json"],
                      "text": "text/plain; charset=utf-8"}
            download = ""
            if "download" in self.path:
                ext = {"html": "html", "json": "json", "text": "txt"}
                download = "referto-seo-rrf.%s" % ext[fmt]
            self._send(200, report.encode("utf-8"), ctypes[fmt],
                       download=download)
        elif path.startswith("/api/"):
            self._send_json(404, {"error": "endpoint sconosciuto"})
        else:
            self._serve_static(path)

    def do_POST(self) -> None:  # noqa: N802 - firma di BaseHTTPServer
        if self.path.split("?", 1)[0] != "/api/audit":
            self._send_json(404, {"error": "endpoint sconosciuto"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = json.loads(self.rfile.read(length) or b"{}")
            if not isinstance(raw, dict):
                raise ValueError("atteso un oggetto JSON")
        except (ValueError, json.JSONDecodeError) as exc:
            self._send_json(400, {"error": "corpo non valido: %s" % exc})
            return

        config, err = validate_config(raw)
        if config is None:
            self._send_json(400, {"error": err})
            return
        if not JOB.start(config):
            self._send_json(409, {"error": "Un audit e' gia' in corso: "
                                           "attendi che finisca."})
            return
        threading.Thread(target=JOB.run, daemon=True).start()
        self._send_json(202, {"ok": True})

    def log_message(self, fmt: str, *args: object) -> None:
        pass  # niente rumore in console: il log utile e' nella GUI


def main(argv: Optional[List[str]] = None) -> int:
    """Punto di ingresso da riga di comando."""
    parser = argparse.ArgumentParser(
        prog="seo_rrf_gui.py",
        description="Interfaccia web locale per seo_rrf_audit.py.")
    parser.add_argument("--host", default="127.0.0.1",
                        help="indirizzo di ascolto (default 127.0.0.1; "
                             "non esporre su reti non fidate)")
    parser.add_argument("--port", type=int, default=8765,
                        help="porta di ascolto (default 8765)")
    parser.add_argument("--no-browser", action="store_true",
                        help="non aprire il browser all'avvio")
    parser.add_argument("--version", action="version",
                        version="%(prog)s " + __version__)
    args = parser.parse_args(argv)

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
