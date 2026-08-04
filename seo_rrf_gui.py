#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Interfaccia web locale per seo_rrf_audit.py.

Avvia un server HTTP sulla macchina locale (default 127.0.0.1:8765)
che serve una interfaccia grafica in Bootstrap Italia (cartella
``gui/``) e alcune API JSON per pilotare l'audit e fruire dei referti:

    GET  /                  interfaccia grafica
    GET  /api/env           versione, RAM disponibile, valori suggeriti
    POST /api/register      registrazione (nome, email, password, ToS)
    POST /api/login         accesso con email e password
    POST /api/logout        chiusura della sessione
    GET  /api/me            stato della sessione e profilo
    POST /api/profile       completamento profilo (azienda, telefono)
    GET  /api/history       storico degli audit dell'utente
    GET  /api/citations     storico del monitoraggio citazioni IA
                            (JSONL di seo_rrf_citations.py)
    GET  /api/events        avanzamento push (Server-Sent Events)
    POST /api/audit         avvia un check (richiede accesso; uno
                            per utente ogni ora)
    POST /api/cancel        annulla l'audit in corso
    GET  /api/status        stato, log, sintesi (richiede accesso)
    GET  /api/report/html   referto HTML (richiede profilo completo)
    GET  /api/report/json   referto JSON (richiede profilo completo)
    GET  /api/report/text   referto testuale (richiede profilo
                            completo)

Gli utenti sono su SQLite (seo_rrf_gui.db accanto allo script):
la registrazione richiede l'accettazione delle condizioni di
servizio con dichiarazione di proprieta' del sito analizzato.

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
import hashlib
import hmac
import json
import re
import secrets
import sqlite3
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import seo_rrf_audit as sra

__version__ = "2.9.0"

GUI_DIR = Path(__file__).resolve().parent / "gui"

# Utenti e sessioni su SQLite accanto allo script (nel .gitignore).
DB_PATH = Path(__file__).resolve().parent / "seo_rrf_gui.db"

# Storico del monitor citazioni (una riga JSON per esecuzione,
# scritto da seo_rrf_citations.py --history). Il default e' il file
# accanto agli script; sovrascrivibile con --citations-history, ad
# esempio /var/lib/seorrf/citazioni.jsonl nel deploy systemd.
CITATIONS_HISTORY = Path(__file__).resolve().parent \
    / "citazioni.jsonl"
SESSION_TTL_S = 7 * 24 * 3600
CHECK_INTERVAL_S = 3600  # un check per utente ogni ora
SESSION_COOKIE = "seo_rrf_session"
EMAIL_RE = re.compile(r"^[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}$")
PBKDF2_ROUNDS = 200_000

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


class UserStore:
    """Utenti, sessioni e limite orario dei check, su SQLite.

    Registrazione rapida (nome, email, password, accettazione delle
    condizioni con dichiarazione di proprieta' del sito) abilita il
    check; il profilo completato (azienda e telefono) sblocca il
    download dei referti. Password con PBKDF2-SHA256 e salt per
    utente; sessioni con token casuale e scadenza.
    """

    def __init__(self, path: Path) -> None:
        self.path = str(path)
        self.lock = threading.Lock()
        with self._connect() as con:
            con.executescript(
                "CREATE TABLE IF NOT EXISTS users ("
                " id INTEGER PRIMARY KEY,"
                " nome TEXT NOT NULL,"
                " email TEXT NOT NULL UNIQUE,"
                " pw_hash TEXT NOT NULL,"
                " salt TEXT NOT NULL,"
                " azienda TEXT NOT NULL DEFAULT '',"
                " telefono TEXT NOT NULL DEFAULT '',"
                " tos_at REAL NOT NULL,"
                " created_at REAL NOT NULL,"
                " last_check_at REAL NOT NULL DEFAULT 0);"
                "CREATE TABLE IF NOT EXISTS sessions ("
                " token TEXT PRIMARY KEY,"
                " user_id INTEGER NOT NULL,"
                " expires_at REAL NOT NULL);"
                "CREATE TABLE IF NOT EXISTS audits ("
                " id INTEGER PRIMARY KEY,"
                " user_id INTEGER NOT NULL,"
                " site TEXT NOT NULL,"
                " created_at REAL NOT NULL,"
                " overall REAL NOT NULL,"
                " scores TEXT NOT NULL,"
                " critical INTEGER NOT NULL,"
                " warning INTEGER NOT NULL,"
                " info INTEGER NOT NULL);")

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.path)
        con.row_factory = sqlite3.Row
        return con

    @staticmethod
    def _hash(password: str, salt: str) -> str:
        return hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt.encode("utf-8"),
            PBKDF2_ROUNDS).hex()

    def _new_session(self, con: sqlite3.Connection,
                     user_id: int) -> str:
        token = secrets.token_hex(32)
        con.execute(
            "INSERT INTO sessions (token, user_id, expires_at) "
            "VALUES (?, ?, ?)",
            (token, user_id, time.time() + SESSION_TTL_S))
        return token

    def register(self, nome: str, email: str, password: str,
                 azienda: str = "", telefono: str = ""
                 ) -> Tuple[str, str]:
        """Crea l'utente e apre la sessione: (token, "") o ("", err)."""
        with self.lock, self._connect() as con:
            exists = con.execute(
                "SELECT 1 FROM users WHERE email = ?",
                (email.lower(),)).fetchone()
            if exists:
                return "", "Esiste gia' un account con questa email."
            salt = secrets.token_hex(16)
            cur = con.execute(
                "INSERT INTO users (nome, email, pw_hash, salt, "
                "azienda, telefono, tos_at, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (nome, email.lower(), self._hash(password, salt),
                 salt, azienda, telefono, time.time(), time.time()))
            return self._new_session(con, cur.lastrowid), ""

    def login(self, email: str, password: str) -> Tuple[str, str]:
        with self.lock, self._connect() as con:
            row = con.execute(
                "SELECT id, pw_hash, salt FROM users WHERE email = ?",
                (email.lower(),)).fetchone()
            if row is None or not hmac.compare_digest(
                    row["pw_hash"],
                    self._hash(password, row["salt"])):
                return "", "Email o password non corretti."
            return self._new_session(con, row["id"]), ""

    def logout(self, token: str) -> None:
        with self.lock, self._connect() as con:
            con.execute("DELETE FROM sessions WHERE token = ?",
                        (token,))

    def user_by_token(self, token: str) -> Optional[Dict[str, object]]:
        if not token:
            return None
        with self.lock, self._connect() as con:
            row = con.execute(
                "SELECT u.* FROM users u JOIN sessions s "
                "ON s.user_id = u.id "
                "WHERE s.token = ? AND s.expires_at > ?",
                (token, time.time())).fetchone()
            if row is None:
                return None
            waited = time.time() - row["last_check_at"]
            return {
                "id": row["id"],
                "nome": row["nome"],
                "email": row["email"],
                "azienda": row["azienda"],
                "telefono": row["telefono"],
                "profile_complete": bool(row["azienda"].strip()
                                         and row["telefono"].strip()),
                "next_check_in_s": max(
                    0, int(CHECK_INTERVAL_S - waited)),
            }

    def update_profile(self, user_id: int, azienda: str,
                       telefono: str) -> None:
        with self.lock, self._connect() as con:
            con.execute(
                "UPDATE users SET azienda = ?, telefono = ? "
                "WHERE id = ?", (azienda, telefono, user_id))

    def record_check(self, user_id: int) -> None:
        with self.lock, self._connect() as con:
            con.execute(
                "UPDATE users SET last_check_at = ? WHERE id = ?",
                (time.time(), user_id))

    def clear_check(self, user_id: int) -> None:
        """Libera lo slot orario (es. dopo un audit annullato)."""
        with self.lock, self._connect() as con:
            con.execute(
                "UPDATE users SET last_check_at = 0 WHERE id = ?",
                (user_id,))

    def add_audit(self, user_id: int,
                  summary: Dict[str, object]) -> None:
        """Registra la sintesi di un audit concluso nello storico."""
        with self.lock, self._connect() as con:
            con.execute(
                "INSERT INTO audits (user_id, site, created_at, "
                "overall, scores, critical, warning, info) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (user_id, str(summary.get("site", "")), time.time(),
                 float(summary.get("overall") or 0),
                 json.dumps(summary.get("scores") or {},
                            ensure_ascii=False),
                 int(summary.get("critical") or 0),
                 int(summary.get("warning") or 0),
                 int(summary.get("info") or 0)))

    def history(self, user_id: int,
                limit: int = 50) -> List[Dict[str, object]]:
        """Storico degli audit dell'utente, dal piu' recente."""
        with self.lock, self._connect() as con:
            rows = con.execute(
                "SELECT * FROM audits WHERE user_id = ? "
                "ORDER BY created_at DESC LIMIT ?",
                (user_id, limit)).fetchall()
        return [
            {
                "site": row["site"],
                "created_at": row["created_at"],
                "overall": row["overall"],
                "scores": json.loads(row["scores"]),
                "critical": row["critical"],
                "warning": row["warning"],
                "info": row["info"],
            }
            for row in rows
        ]


STORE: Optional[UserStore] = None


def get_store() -> UserStore:
    global STORE
    if STORE is None:
        STORE = UserStore(DB_PATH)
    return STORE


class Job:
    """Stato dell'audit corrente (uno alla volta)."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        # idle | running | done | error | cancelled
        self.state = "idle"
        self.stop_event = threading.Event()
        self.user_id = 0
        self.log: List[str] = []
        self.error = ""
        self.config: Dict[str, object] = {}
        self.summary: Dict[str, object] = {}
        self.findings: List[Dict[str, object]] = []
        self.remediation: List[Dict[str, object]] = []
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
                "remediation": list(self.remediation),
                "rrf": list(self.rrf),
                "competitive": self.competitive,
            }

    def start(self, config: Dict[str, object],
              user_id: int = 0) -> bool:
        """Passa a 'running' se libero; False se un audit e' in corso."""
        with self.lock:
            if self.state == "running":
                return False
            self.state = "running"
            self.user_id = user_id
            self.stop_event.clear()
            self.log = []
            self.error = ""
            self.config = config
            self.summary = {}
            self.findings = []
            self.remediation = []
            self.rrf = []
            self.competitive = None
            self.reports = {}
            return True

    def cancel(self) -> bool:
        """Chiede lo stop dell'audit in corso; False se non ce n'e'."""
        with self.lock:
            if self.state != "running":
                return False
            self.stop_event.set()
            return True

    def run(self) -> None:
        """Esegue l'audit (nel thread di lavoro) e salva i referti."""
        cfg = self.config
        buf = LineBuffer(self.log, self.lock)
        judge_mode = str(cfg.get("judge", sra.DEFAULT_JUDGE))
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
                    robots_mode=str(cfg["robots"]),
                    retries=int(cfg["retries"]),
                    workers=int(cfg["workers"]),
                    render=str(cfg["render"]),
                    competitors=list(cfg["competitors"]),
                    stop_event=self.stop_event)
                judge = sra.run_judge(results, pages, judge_mode,
                                      verbose=True)
            buf.flush()
        except sra.AuditCancelled:
            buf.flush()
            if self.user_id:
                # L'annullamento non consuma lo slot orario.
                get_store().clear_check(self.user_id)
            with self.lock:
                self.state = "cancelled"
            return
        except Exception as exc:  # noqa: BLE001 - riportato alla GUI
            buf.flush()
            with self.lock:
                self.state = "error"
                self.error = "%s: %s" % (type(exc).__name__, exc)
            return

        k = int(cfg["rrf_k"])
        base = str(cfg["url"])
        market = str(cfg.get("market", sra.DEFAULT_MARKET))
        reports = {
            "html": sra.render_html(base, pages, findings, scores,
                                    results, mode, k, competitive,
                                    market=market, judge=judge),
            "json": sra.render_json(base, pages, findings, scores,
                                    results, mode, k, competitive,
                                    market=market, judge=judge),
            "text": sra.render_text(base, pages, findings, scores,
                                    results, mode, k, competitive,
                                    market=market, judge=judge),
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
            "surface_math": sra.surface_math(pages),
            "citability": sra.citability_profiles(pages, scores,
                                                  market),
            "citability_actions": sra.citability_top_actions(
                findings, pages, scores, market),
            "judge": judge,
            "critical": severities.count(sra.SEV_CRITICAL),
            "warning": severities.count(sra.SEV_WARNING),
            "info": severities.count(sra.SEV_INFO),
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        }
        if self.user_id:
            get_store().add_audit(self.user_id, summary)
        with self.lock:
            self.reports = reports
            self.summary = summary
            self.findings = [f.as_dict() for f in findings]
            self.remediation = sra.build_remediation(
                findings, pages, scores, market)
            self.rrf = [sra.asdict(r) for r in results]
            self.competitive = competitive
            self.state = "done"

    def report(self, fmt: str) -> Optional[str]:
        with self.lock:
            return self.reports.get(fmt)


JOB = Job()


def read_citations_history(path: str) -> List[Dict[str, object]]:
    """Storico del monitor citazioni raggruppato per sito.

    Legge il JSONL scritto da seo_rrf_citations.py (una riga per
    esecuzione: generated_at, site, overall_rate, providers) e
    restituisce [{"site": host, "runs": [...]}] nell'ordine di
    prima apparizione, con al massimo le ultime 50 esecuzioni per
    sito. Righe malformate e file assente vengono ignorati: lo
    storico e' un di piu', non deve mai rompere la GUI.
    """
    sites: Dict[str, List[Dict[str, object]]] = {}
    order: List[str] = []
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
                if not isinstance(row, dict):
                    continue
                site = str(row.get("site", ""))
                if not site or not isinstance(
                        row.get("providers"), dict):
                    continue
                if site not in sites:
                    sites[site] = []
                    order.append(site)
                sites[site].append(row)
    except OSError:
        pass
    return [{"site": site, "runs": sites[site][-50:]}
            for site in order]


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
    workers = number("workers", sra.DEFAULT_WORKERS, 1,
                     sra.MAX_WORKERS)
    render = str(raw.get("render", sra.RENDER_OFF)).strip().lower()
    if render not in sra.RENDER_MODES:
        return None, "Valore non valido per 'render'."

    market = str(raw.get("market",
                         sra.DEFAULT_MARKET)).strip().lower()
    if market not in sra.MARKET_WEIGHTS:
        return None, "Valore non valido per 'market'."

    judge = str(raw.get("judge", sra.DEFAULT_JUDGE)).strip().lower()
    if judge not in sra.JUDGE_MODES:
        return None, "Valore non valido per 'judge'."
    if judge == sra.JUDGE_ON:
        judge_reason = sra.judge_unavailable()
        if judge_reason:
            return None, ("Giudizio LLM obbligatorio ma non "
                          "disponibile sul server: %s."
                          % judge_reason)

    # Predefinito "own": la registrazione include la dichiarazione di
    # titolarita' dei siti auditati (condizioni di servizio).
    robots = str(raw.get("robots", sra.ROBOTS_OWN)).strip().lower()
    if robots not in sra.ROBOTS_MODES:
        return None, "Valore non valido per 'robots'."
    if robots == sra.ROBOTS_FORCE \
            and raw.get("robots_ack") is not True:
        return None, ("Per ignorare i Disallow serve la conferma "
                      "esplicita di assunzione di responsabilita'.")
    checks = (("max_pages", max_pages), ("rrf_k", rrf_k),
              ("delay", delay), ("max_body", max_body),
              ("retries", retries), ("workers", workers))
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
        "workers": int(workers),
        "render": render,
        "robots": robots,
        "market": market,
        "judge": judge,
        "queries": queries,
        "embeddings": str(raw.get("embeddings", "")).strip(),
        "competitors": competitors,
    }, ""


class Handler(BaseHTTPRequestHandler):
    """Instrada API e file statici della GUI."""

    server_version = "SeoRrfGui/%s" % __version__

    def _send(self, status: int, body: bytes, ctype: str,
              download: str = "", cookie: str = "") -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", CSP)
        self.send_header("Cache-Control", "no-store")
        if cookie:
            self.send_header("Set-Cookie", cookie)
        if download:
            self.send_header("Content-Disposition",
                             'attachment; filename="%s"' % download)
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, status: int, payload: Dict[str, object],
                   cookie: str = "") -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._send(status, body, CONTENT_TYPES[".json"],
                   cookie=cookie)

    # ---------------- sessione ----------------

    def _session_token(self) -> str:
        header = self.headers.get("Cookie", "")
        for part in header.split(";"):
            name, _, value = part.strip().partition("=")
            if name == SESSION_COOKIE:
                return value
        return ""

    def _session_user(self) -> Optional[Dict[str, object]]:
        return get_store().user_by_token(self._session_token())

    @staticmethod
    def _cookie(token: str, expire: bool = False) -> str:
        base = "%s=%s; Path=/; HttpOnly; SameSite=Strict" \
            % (SESSION_COOKIE, token)
        return base + "; Max-Age=0" if expire else base

    def _read_json(self) -> Optional[Dict[str, object]]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = json.loads(self.rfile.read(length) or b"{}")
            if not isinstance(raw, dict):
                raise ValueError("atteso un oggetto JSON")
            return raw
        except (ValueError, json.JSONDecodeError) as exc:
            self._send_json(400,
                            {"error": "corpo non valido: %s" % exc})
            return None

    def _stream_events(self) -> None:
        """Avanzamento push (Server-Sent Events).

        Invia lo snapshot quando cambia (nuove righe di log o cambio
        di stato) e chiude il flusso quando l'audit raggiunge uno
        stato terminale; il client ripiega sul polling se il flusso
        non e' disponibile.
        """
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Accel-Buffering", "no")
        self.send_header("Content-Security-Policy", CSP)
        self.end_headers()

        last_sent = None
        try:
            while True:
                snap = JOB.snapshot()
                marker = (snap["state"], len(snap["log"]))
                if marker != last_sent:
                    last_sent = marker
                    payload = json.dumps(snap, ensure_ascii=False)
                    self.wfile.write(
                        ("data: %s\n\n" % payload).encode("utf-8"))
                    self.wfile.flush()
                if snap["state"] != "running":
                    break
                time.sleep(0.3)
        except (BrokenPipeError, ConnectionResetError):
            pass  # client disconnesso: nessun rumore

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
            self._send_json(200, {
                "tool_version": sra.__version__,
                "gui_version": __version__,
                "default_max_body_mb": sra.DEFAULT_MAX_BODY_MB,
                "available_ram_mb": ram,
                "suggested_max_body_mb": suggested,
                "embeddings_available": sra.embeddings_available(),
                "render_available":
                    importlib.util.find_spec("playwright")
                    is not None,
                "judge_available":
                    sra.judge_unavailable() is None,
                "judge_reason": sra.judge_unavailable() or "",
                "default_embeddings_model":
                    sra.DEFAULT_EMBEDDINGS_MODEL,
            })
        elif path == "/api/me":
            user = self._session_user()
            if user is None:
                self._send_json(200, {"authenticated": False})
            else:
                self._send_json(200, {"authenticated": True,
                                      "user": user})
        elif path == "/api/status":
            if self._session_user() is None:
                self._send_json(401, {"error": "accesso richiesto"})
                return
            self._send_json(200, JOB.snapshot())
        elif path == "/api/history":
            user = self._session_user()
            if user is None:
                self._send_json(401, {"error": "accesso richiesto"})
                return
            self._send_json(200, {
                "runs": get_store().history(int(user["id"]))})
        elif path == "/api/citations":
            if self._session_user() is None:
                self._send_json(401, {"error": "accesso richiesto"})
                return
            self._send_json(200, {
                "sites": read_citations_history(
                    str(CITATIONS_HISTORY))})
        elif path == "/api/events":
            if self._session_user() is None:
                self._send_json(401, {"error": "accesso richiesto"})
                return
            self._stream_events()
        elif path.startswith("/api/report/"):
            user = self._session_user()
            if user is None:
                self._send_json(401, {"error": "accesso richiesto"})
                return
            if not user["profile_complete"]:
                self._send_json(403, {
                    "error": "Il download dei referti richiede la "
                             "registrazione completa: aggiungi "
                             "azienda e telefono al profilo.",
                    "code": "profile_incomplete"})
                return
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
        path = self.path.split("?", 1)[0]
        if path == "/api/register":
            self._post_register()
        elif path == "/api/login":
            self._post_login()
        elif path == "/api/logout":
            get_store().logout(self._session_token())
            self._send_json(200, {"ok": True},
                            cookie=self._cookie("", expire=True))
        elif path == "/api/profile":
            self._post_profile()
        elif path == "/api/cancel":
            if self._session_user() is None:
                self._send_json(401, {"error": "accesso richiesto"})
            elif JOB.cancel():
                self._send_json(202, {"ok": True})
            else:
                self._send_json(409, {"error": "Nessun audit in "
                                               "corso da annullare."})
        elif path == "/api/audit":
            self._post_audit()
        else:
            self._send_json(404, {"error": "endpoint sconosciuto"})

    def _post_register(self) -> None:
        raw = self._read_json()
        if raw is None:
            return
        nome = str(raw.get("nome", "")).strip()
        email = str(raw.get("email", "")).strip()
        password = str(raw.get("password", ""))
        if not raw.get("tos"):
            self._send_json(400, {
                "error": "Per registrarti devi accettare le "
                         "condizioni di servizio e dichiarare che il "
                         "sito da analizzare e' di tua proprieta'."})
            return
        if len(nome) < 2:
            self._send_json(400, {"error": "Indica il tuo nome."})
            return
        if not EMAIL_RE.match(email):
            self._send_json(400, {"error": "Email non valida."})
            return
        if len(password) < 8:
            self._send_json(400, {
                "error": "La password deve avere almeno 8 caratteri."})
            return
        token, err = get_store().register(
            nome, email, password,
            azienda=str(raw.get("azienda", "")).strip(),
            telefono=str(raw.get("telefono", "")).strip())
        if err:
            self._send_json(409, {"error": err})
            return
        user = get_store().user_by_token(token)
        self._send_json(201, {"ok": True, "user": user},
                        cookie=self._cookie(token))

    def _post_login(self) -> None:
        raw = self._read_json()
        if raw is None:
            return
        token, err = get_store().login(
            str(raw.get("email", "")).strip(),
            str(raw.get("password", "")))
        if err:
            self._send_json(401, {"error": err})
            return
        user = get_store().user_by_token(token)
        self._send_json(200, {"ok": True, "user": user},
                        cookie=self._cookie(token))

    def _post_profile(self) -> None:
        user = self._session_user()
        if user is None:
            self._send_json(401, {"error": "accesso richiesto"})
            return
        raw = self._read_json()
        if raw is None:
            return
        azienda = str(raw.get("azienda", "")).strip()
        telefono = str(raw.get("telefono", "")).strip()
        if not azienda or not telefono:
            self._send_json(400, {
                "error": "Per completare la registrazione servono "
                         "azienda e telefono."})
            return
        get_store().update_profile(int(user["id"]), azienda, telefono)
        self._send_json(200, {
            "ok": True,
            "user": get_store().user_by_token(
                self._session_token())})

    def _post_audit(self) -> None:
        user = self._session_user()
        if user is None:
            self._send_json(401, {
                "error": "Per avviare un check devi registrarti o "
                         "accedere."})
            return
        raw = self._read_json()
        if raw is None:
            return
        config, err = validate_config(raw)
        if config is None:
            self._send_json(400, {"error": err})
            return
        wait_s = int(user["next_check_in_s"])
        if wait_s > 0:
            self._send_json(429, {
                "error": "Hai gia' effettuato un check nell'ultima "
                         "ora: potrai avviarne un altro fra %d "
                         "minuti." % max(1, wait_s // 60),
                "retry_in_s": wait_s})
            return
        if not JOB.start(config, user_id=int(user["id"])):
            self._send_json(409, {"error": "Un audit e' gia' in corso: "
                                           "attendi che finisca."})
            return
        get_store().record_check(int(user["id"]))
        threading.Thread(target=JOB.run, daemon=True).start()
        self._send_json(202, {"ok": True})

    def log_message(self, fmt: str, *args: object) -> None:
        pass  # niente rumore in console: il log utile e' nella GUI


def main(argv: Optional[List[str]] = None) -> int:
    """Punto di ingresso da riga di comando."""
    global CITATIONS_HISTORY
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
    parser.add_argument("--citations-history", metavar="FILE",
                        default=str(CITATIONS_HISTORY),
                        help="storico JSONL del monitoraggio "
                             "citazioni da mostrare nella GUI "
                             "(default %s; nel deploy systemd "
                             "tipicamente /var/lib/seorrf/"
                             "citazioni.jsonl)" % CITATIONS_HISTORY)
    parser.add_argument("--version", action="version",
                        version="%(prog)s " + __version__)
    args = parser.parse_args(argv)

    CITATIONS_HISTORY = Path(args.citations_history)

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
