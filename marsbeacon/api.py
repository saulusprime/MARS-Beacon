# -*- coding: utf-8 -*-
"""Registro dichiarativo delle rotte API e generatore OpenAPI 3.1.

Fase 1 del programma API-first (TO-DO, P1): il registro e' l'unica
fonte di verita' del contratto — percorso, metodo, autenticazione,
schemi di richiesta e risposta di ogni endpoint — e da esso
derivano la spec OpenAPI 3.1 (``GET /api/v1/openapi.json``,
generata al volo; snapshot golden in ``docs/openapi.json``), la
**validazione delle richieste a runtime** (stessi schemi, col
mini-validatore in sola libreria standard qui sotto: il pacchetto
``jsonschema`` resta confinato alla suite di test) e i **contract
test** (ogni risposta reale validata contro gli schemi del
registro). Spec e codice non possono divergere per costruzione.

La versione del CONTRATTO (``API_CONTRACT_VERSION``) e'
indipendente dalla versione dello strumento: la 1.0.0 copre
l'intera superficie attuale (17 rotte). Modulo interno consumato
dal server (mars_gui.py, in futuro mars_api.py): non fa parte
della facciata dello strumento di audit.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple
import contextlib
import hashlib
import hmac
import importlib.util
import json
import os
import re
import secrets
import sqlite3
import threading
import time

import mars_audit as sra

from marsbeacon.base import CHUNK_WORDS_MAX
from marsbeacon.base import CHUNK_WORDS_MIN
from marsbeacon.base import CONFIG_THRESHOLDS
from marsbeacon.base import JUDGE_MODES
from marsbeacon.base import LIGHTHOUSE_DEVICES
from marsbeacon.base import LIGHTHOUSE_MODES
from marsbeacon.base import LIGHTHOUSE_PAGES_MAX
from marsbeacon.base import LIGHTHOUSE_PAGES_MIN
from marsbeacon.base import MARKET_WEIGHTS
from marsbeacon.base import MAX_WORKERS
from marsbeacon.base import RENDER_MODES
from marsbeacon.base import ROBOTS_MODES
from marsbeacon.base import SEARCH_CHECK_MODES
from marsbeacon.base import TOP_N_MAX
from marsbeacon.base import TOP_N_MIN
from marsbeacon.i18n import HTML_LANGS


# Versione del contratto API, indipendente dalla versione dello
# strumento: si muove solo quando cambia il contratto. La 1.0.0
# ha segnato il censimento completo della superficie (17 rotte);
# la 1.1.0 la parita' CLI-API su POST /api/audit (lang, soglie,
# queries_gsc, fail_under); la 1.2.0 GET /api/docs (documentazione
# Scalar); la 1.3.0 il modello a risorse della Fase 2 — job con id
# (/api/v1/audits), token Bearer (/api/v1/tokens), storico
# paginato, snapshot con id, errori uniformi sulle rotte v1.
API_CONTRACT_VERSION = "1.3.0"


# Nome del cookie di sessione: fa parte del contratto (schema di
# sicurezza nella spec). mars_gui dichiara lo stesso valore; un
# test ne verifica la coerenza.
SESSION_COOKIE_NAME = "mars_session"


# Modalita' di autenticazione delle rotte: nessuna, "session"
# (cookie O token Bearer: il doppio binario della Fase 0) oppure
# "cookie" (solo sessione: la gestione dei token, cosi' un token
# non puo' crearne o revocarne altri).
AUTH_NONE = "none"


AUTH_SESSION = "session"


AUTH_COOKIE = "cookie"


# Schema dell'errore degli endpoint legacy (/api/*): un oggetto
# {"error": messaggio in italiano}. L'oggetto errore uniforme
# {code, key, params, message} arrivera' con /api/v1 (Fase 2).
ERROR_SCHEMA: Dict[str, object] = {
    "type": "object",
    "properties": {"error": {"type": "string"}},
    "required": ["error"],
    "additionalProperties": False,
}


# Errore con codice macchina (oggi solo "profile_incomplete" sui
# download riservati alla registrazione completa).
CODED_ERROR_SCHEMA: Dict[str, object] = {
    "type": "object",
    "properties": {"error": {"type": "string"},
                   "code": {"type": "string"}},
    "required": ["error", "code"],
    "additionalProperties": False,
}


# Conferma semplice {"ok": true}.
OK_SCHEMA: Dict[str, object] = {
    "type": "object",
    "properties": {"ok": {"type": "boolean"}},
    "required": ["ok"],
    "additionalProperties": False,
}


# Conferma con id del job creato.
OK_ID_SCHEMA: Dict[str, object] = {
    "type": "object",
    "properties": {"ok": {"type": "boolean"},
                   "id": {"type": "string"}},
    "required": ["ok", "id"],
    "additionalProperties": False,
}


# Errore uniforme delle rotte /api/v1 (decisione di Fase 0):
# {code, key, message, params} — codice macchina, chiave i18n col
# meccanismo dei rilievi, messaggio italiano canonico, parametri.
# Le rotte legacy conservano {"error": messaggio}.
ERROR_V1_SCHEMA: Dict[str, object] = {
    "type": "object",
    "properties": {"error": {
        "type": "object",
        "properties": {
            "code": {"type": "string"},
            "key": {"type": "string"},
            "message": {"type": "string"},
            "params": {"type": "object"},
        },
        "required": ["code", "key", "message", "params"],
        "additionalProperties": False,
    }},
    "required": ["error"],
    "additionalProperties": False,
}


def _err_v1(description: str) -> Dict[str, object]:
    return {"description": description,
            "schema": ERROR_V1_SCHEMA}


# Utente autenticato come esposto da /api/me (forma del dict di
# UserStore.user_by_token).
USER_SCHEMA: Dict[str, object] = {
    "type": "object",
    "properties": {
        "id": {"type": "integer"},
        "nome": {"type": "string"},
        "email": {"type": "string"},
        "azienda": {"type": "string"},
        "telefono": {"type": "string"},
        "profile_complete": {"type": "boolean"},
        "next_check_in_s": {"type": "integer"},
    },
    "required": ["id", "nome", "email", "azienda", "telefono",
                 "profile_complete", "next_check_in_s"],
    "additionalProperties": False,
}


@dataclass(frozen=True)
class Route:
    """Una rotta del contratto: tutto cio' che serve a descriverla.

    ``responses`` mappa lo stato HTTP su un dizionario con
    "description" piu', a scelta: "schema" (corpo JSON, con
    "content_type" facoltativo per i media diversi da JSON),
    oppure "content" (mappa completa media type -> schema, per le
    risposte multi-formato come i referti), piu' "headers"
    facoltativi (es. Set-Cookie). ``request_schema`` e' lo schema
    JSON del corpo (solo POST); ``params`` sono i parametri di
    percorso e query ({"name", "in", "required", "schema",
    "description"}).
    """

    method: str
    path: str
    summary: str
    description: str = ""
    tags: Tuple[str, ...] = ()
    auth: str = AUTH_NONE
    params: Tuple[Dict[str, object], ...] = ()
    request_schema: Optional[Dict[str, object]] = None
    responses: Dict[int, Dict[str, object]] = field(
        default_factory=dict)


def _err(description: str) -> Dict[str, object]:
    return {"description": description, "schema": ERROR_SCHEMA}


def _schema_soglie() -> Dict[str, object]:
    """Schema del blocco "soglie" derivato da CONFIG_THRESHOLDS:
    la spec segue il registro delle soglie per costruzione (chiavi,
    tipi e intervalli non possono divergere)."""
    proprieta: Dict[str, object] = {}
    for chiave in sorted(CONFIG_THRESHOLDS):
        _, kind, minimo, massimo = CONFIG_THRESHOLDS[chiave]
        proprieta[chiave] = {
            "type": "integer" if kind is int else "number",
            "minimum": minimo, "maximum": massimo}
    return {
        "type": "object",
        "properties": proprieta,
        "additionalProperties": False,
        "description": "Soglie di prassi personalizzate "
                       "(equivalente di --config della CLI): i "
                       "rilievi dichiarano sempre la soglia "
                       "usata e il referto JSON le echeggia nel "
                       "blocco 'thresholds'. Coppie min/max "
                       "validate sul valore efficace.",
    }


# Conferma {ok, user}: registrazione, login, profilo.
OK_USER_SCHEMA: Dict[str, object] = {
    "type": "object",
    "properties": {"ok": {"type": "boolean"},
                   "user": USER_SCHEMA},
    "required": ["ok", "user"],
    "additionalProperties": False,
}


# Header Set-Cookie delle risposte che aprono o chiudono la
# sessione.
_SET_COOKIE_HEADER: Dict[str, object] = {
    "Set-Cookie": {
        "description": "Cookie di sessione (HttpOnly, "
                       "SameSite=Strict).",
        "schema": {"type": "string"},
    }}


# Snapshot del job di audit: la stessa forma per GET /api/status e
# per i messaggi dell'SSE. Le strutture profonde (sintesi, rilievi,
# esiti RRF) hanno la stessa natura del referto JSON, gia'
# documentato da schema_version: qui restano oggetti liberi.
SNAPSHOT_SCHEMA: Dict[str, object] = {
    "type": "object",
    "properties": {
        "id": {"type": "string",
               "description": "Id del job (vuoto per i job "
                              "avviati prima del modello a "
                              "risorse)."},
        "state": {"type": "string",
                  "enum": ["idle", "running", "done", "error",
                           "cancelled"]},
        "log": {"type": "array", "items": {"type": "string"}},
        "error": {"type": "string"},
        "config": {"type": "object",
                   "description": "Configurazione dell'audit "
                                  "avviato (echo del POST "
                                  "validato)."},
        "summary": {"type": "object",
                    "description": "Sintesi a fine audit: "
                                   "punteggi, citabilita', "
                                   "giudizio, Lighthouse, ancora "
                                   "di realta', delta — stessa "
                                   "natura del referto JSON "
                                   "(schema_version)."},
        "findings": {"type": "array", "items": {"type": "object"}},
        "remediation": {"type": "array",
                        "items": {"type": "object"}},
        "rrf": {"type": "array", "items": {"type": "object"}},
        "competitive": {"type": ["object", "null"]},
    },
    "required": ["id", "state", "log", "error", "config",
                 "summary", "findings", "remediation", "rrf",
                 "competitive"],
    "additionalProperties": False,
}


# Riga dello storico audit dell'utente (GET /api/history).
RUN_SCHEMA: Dict[str, object] = {
    "type": "object",
    "properties": {
        "id": {"type": "integer"},
        "site": {"type": "string"},
        "created_at": {"type": "number"},
        "overall": {"type": "number"},
        "scores": {"type": "object"},
        "critical": {"type": "integer"},
        "warning": {"type": "integer"},
        "info": {"type": "integer"},
        "has_report": {"type": "boolean"},
    },
    "required": ["id", "site", "created_at", "overall", "scores",
                 "critical", "warning", "info", "has_report"],
    "additionalProperties": False,
}


# Formati di referto prodotti dal job e relativi content type.
REPORT_FORMATS = ("html", "json", "text", "md", "csv")


REPORT_CTYPES = {
    "html": "text/html; charset=utf-8",
    "json": "application/json; charset=utf-8",
    "text": "text/plain; charset=utf-8",
    "md": "text/markdown; charset=utf-8",
    "csv": "text/csv; charset=utf-8",
}


# Corpo di POST /api/audit e /api/v1/audits (stesso handler,
# stesso schema): tutti i parametri della CLI.
AUDIT_REQUEST_SCHEMA: Dict[str, object] = {
    "type": "object",
    "properties": {
        "url": {"type": "string", "minLength": 1,
                "x-errore": "URL mancante.",
                "description": "Sito da analizzare "
                               "(https:// implicito se "
                               "manca lo schema)."},
        "max_pages": {"type": "number", "minimum": 1,
                      "maximum": 500, "default": 25},
        "rrf_k": {"type": "number", "minimum": 1,
                  "maximum": 1000, "default": 60},
        "top_n": {"type": "number",
                  "minimum": TOP_N_MIN,
                  "maximum": TOP_N_MAX, "default": 5},
        "chunk_words": {"type": "number",
                        "minimum": CHUNK_WORDS_MIN,
                        "maximum": CHUNK_WORDS_MAX,
                        "default": 220},
        "w_lex": {"type": "number", "minimum": 0.1,
                  "maximum": 10, "default": 1.0},
        "w_vec": {"type": "number", "minimum": 0.1,
                  "maximum": 10, "default": 1.0},
        "delay": {"type": "number", "minimum": 0,
                  "maximum": 10, "default": 0.5},
        "max_body": {"type": "number", "minimum": 1,
                     "maximum": 10240, "default": 10},
        "retries": {"type": "number", "minimum": 0,
                    "maximum": 10, "default": 2},
        "workers": {"type": "number", "minimum": 1,
                    "maximum": MAX_WORKERS, "default": 4},
        "render": {"type": "string",
                   "enum": list(RENDER_MODES),
                   "default": "off"},
        "market": {"type": "string",
                   "enum": sorted(MARKET_WEIGHTS),
                   "default": "occidentale"},
        "judge": {"type": "string",
                  "enum": list(JUDGE_MODES),
                  "default": "auto"},
        "lighthouse": {"type": "string",
                       "enum": list(LIGHTHOUSE_MODES),
                       "default": "off"},
        "lighthouse_pages": {
            "type": "number",
            "minimum": LIGHTHOUSE_PAGES_MIN,
            "maximum": LIGHTHOUSE_PAGES_MAX,
            "default": 3},
        "lighthouse_device": {
            "type": "string",
            "enum": list(LIGHTHOUSE_DEVICES),
            "default": "mobile"},
        "search_check": {
            "type": "string",
            "enum": list(SEARCH_CHECK_MODES),
            "default": "auto"},
        "robots": {"type": "string",
                   "enum": list(ROBOTS_MODES),
                   "default": "own",
                   "description": "Default 'own': la "
                                  "titolarita' e' "
                                  "dichiarata in "
                                  "registrazione."},
        "robots_ack": {
            "type": "boolean",
            "description": "Obbligatorio true con "
                           "robots=force: assunzione "
                           "esplicita di "
                           "responsabilita'."},
        "queries": {"type": "string",
                    "description": "Query di prova, una "
                                   "per riga."},
        "competitors": {"type": "string",
                        "description": "Siti concorrenti, "
                                       "uno per riga "
                                       "(max 3)."},
        "embeddings": {"type": "string",
                       "description": "Modello "
                                      "sentence-transformers"
                                      "; vuoto = auto, "
                                      "'none' = proxy."},
        "lang": {"type": "string",
                 "enum": list(HTML_LANGS),
                 "default": "it",
                 "description": "Lingua dei referti "
                                "scaricabili (html, text, "
                                "md, csv); il JSON resta "
                                "canonico in italiano."},
        "soglie": _schema_soglie(),
        "queries_gsc": {
            "type": "string",
            "description": "Contenuto dell'export CSV "
                           "\"Query\" di Google Search "
                           "Console (rapporto "
                           "Rendimento): prime 15 per "
                           "clic e impressioni, "
                           "deduplicate. Non combinabile "
                           "con 'queries'."},
        "fail_under": {
            "type": ["number", "null"],
            "minimum": 0, "maximum": 100,
            "description": "Gate di regressione: la "
                           "sintesi del job echeggia "
                           "soglia ed esito "
                           "(fail_under, gate_passed)."},
    },
    "required": ["url"],
    "additionalProperties": False,
}


ROUTES: Tuple[Route, ...] = (
    Route(
        "GET", "/api/v1/openapi.json",
        summary="Spec OpenAPI 3.1 del contratto",
        description="Generata al volo dal registro dichiarativo "
                    "delle rotte: e' sempre allineata al codice "
                    "per costruzione. Lo snapshot versionato nel "
                    "repository (docs/openapi.json) e' un golden "
                    "verificato dalla suite.",
        tags=("contratto",),
        responses={200: {"description": "La spec OpenAPI.",
                         "schema": {"type": "object"}}},
    ),
    Route(
        "GET", "/api/docs",
        summary="Documentazione navigabile del contratto (Scalar)",
        description="Lettore Scalar vendorizzato in modalita' "
                    "markup: nessuna origine esterna (font "
                    "predefiniti disattivati in favore del "
                    "Titillium Web del brand; la CSP della GUI "
                    "blocca comunque ogni caricamento fuori da "
                    "'self'). La spec grezza resta su "
                    "/api/v1/openapi.json, importabile in "
                    "qualunque strumento.",
        tags=("contratto",),
        responses={200: {"description": "Pagina HTML della "
                                        "documentazione.",
                         "schema": {"type": "string"},
                         "content_type": "text/html"}},
    ),
    Route(
        "GET", "/api/env",
        summary="Capacita' del server e valori suggeriti",
        description="Versioni, RAM disponibile, disponibilita' "
                    "delle dipendenze opzionali (embedding, "
                    "rendering, giudizio LLM, ancora di realta', "
                    "Lighthouse) con i motivi dichiarati quando "
                    "mancano.",
        tags=("ambiente",),
        responses={200: {
            "description": "Stato dell'ambiente di esecuzione.",
            "schema": {
                "type": "object",
                "properties": {
                    "tool_version": {"type": "string"},
                    "gui_version": {"type": "string"},
                    "default_max_body_mb": {"type": "integer"},
                    "available_ram_mb":
                        {"type": ["number", "null"]},
                    "suggested_max_body_mb":
                        {"type": ["integer", "null"]},
                    "embeddings_available": {"type": "boolean"},
                    "render_available": {"type": "boolean"},
                    "judge_available": {"type": "boolean"},
                    "judge_reason": {"type": "string"},
                    "lighthouse_available": {"type": "boolean"},
                    "lighthouse_reason": {"type": "string"},
                    "lighthouse_version": {"type": "string"},
                    "search_check_available": {"type": "boolean"},
                    "search_check_reason": {"type": "string"},
                    "default_embeddings_model": {"type": "string"},
                },
                "required": [
                    "tool_version", "gui_version",
                    "default_max_body_mb", "available_ram_mb",
                    "suggested_max_body_mb",
                    "embeddings_available", "render_available",
                    "judge_available", "judge_reason",
                    "lighthouse_available", "lighthouse_reason",
                    "lighthouse_version",
                    "search_check_available",
                    "search_check_reason",
                    "default_embeddings_model"],
                "additionalProperties": False,
            }}},
    ),
    Route(
        "GET", "/api/me",
        summary="Utente della sessione corrente",
        description="Con sessione valida restituisce l'utente; "
                    "senza, authenticated=false (mai 401: e' la "
                    "rotta con cui il frontend scopre lo stato).",
        tags=("account",),
        responses={200: {
            "description": "Stato di autenticazione.",
            "schema": {
                "type": "object",
                "properties": {
                    "authenticated": {"type": "boolean"},
                    "user": USER_SCHEMA,
                },
                "required": ["authenticated"],
                "additionalProperties": False,
            }}},
    ),
    Route(
        "POST", "/api/cancel",
        summary="Annulla l'audit in corso",
        description="Annullamento cooperativo: interrompe "
                    "richieste e attese alla prima occasione "
                    "utile, senza risultati parziali; non consuma "
                    "lo slot orario.",
        tags=("audit",),
        auth=AUTH_SESSION,
        responses={
            202: {"description": "Annullamento avviato.",
                  "schema": {
                      "type": "object",
                      "properties": {"ok": {"type": "boolean"}},
                      "required": ["ok"],
                      "additionalProperties": False}},
            401: _err("Accesso richiesto."),
            409: _err("Nessun audit in corso da annullare."),
        },
    ),
    Route(
        "POST", "/api/citations/events",
        summary="Annota un evento sul grafico delle citazioni",
        description="Aggiunge un pin-evento allo storico "
                    "(eventi.jsonl): data, etichetta e sito "
                    "facoltativo.",
        tags=("citazioni",),
        auth=AUTH_SESSION,
        request_schema={
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "pattern": r"^\d{4}-\d{2}-\d{2}$",
                    "x-errore": "Data non valida: usa AAAA-MM-GG.",
                },
                "label": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 120,
                    "x-errore": "Etichetta mancante o troppo "
                                "lunga (max 120).",
                },
                "site": {"type": "string"},
            },
            "required": ["date", "label"],
            "additionalProperties": False,
        },
        responses={
            201: {"description": "Evento registrato.",
                  "schema": {
                      "type": "object",
                      "properties": {
                          "ok": {"type": "boolean"},
                          "event": {
                              "type": "object",
                              "properties": {
                                  "date": {"type": "string"},
                                  "label": {"type": "string"},
                                  "site": {"type": "string"},
                              },
                              "required": ["date", "label"],
                              "additionalProperties": False,
                          },
                      },
                      "required": ["ok", "event"],
                      "additionalProperties": False}},
            400: _err("Richiesta non valida (motivo nel "
                      "messaggio)."),
            401: _err("Accesso richiesto."),
            500: _err("Evento non salvabile su disco."),
        },
    ),
    Route(
        "POST", "/api/register",
        summary="Registrazione rapida",
        description="Crea l'account e apre la sessione. La "
                    "registrazione include l'accettazione delle "
                    "condizioni di servizio con la dichiarazione "
                    "di titolarita' dei siti da analizzare; "
                    "azienda e telefono (facoltativi qui) "
                    "completano il profilo e sbloccano il "
                    "download dei referti.",
        tags=("account",),
        request_schema={
            "type": "object",
            "properties": {
                "nome": {
                    "type": "string", "minLength": 2,
                    "x-errore": "Indica il tuo nome."},
                "email": {
                    "type": "string",
                    "pattern": r"^[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}$",
                    "x-errore": "Email non valida."},
                "password": {
                    "type": "string", "minLength": 8,
                    "x-errore": "La password deve avere almeno 8 "
                                "caratteri."},
                "tos": {
                    "enum": [True],
                    "x-errore": "Per registrarti devi accettare "
                                "le condizioni di servizio e "
                                "dichiarare che il sito da "
                                "analizzare e' di tua "
                                "proprieta'."},
                "azienda": {"type": "string"},
                "telefono": {"type": "string"},
            },
            "required": ["nome", "email", "password", "tos"],
            "additionalProperties": False,
        },
        responses={
            201: {"description": "Account creato, sessione "
                                 "aperta.",
                  "schema": OK_USER_SCHEMA,
                  "headers": _SET_COOKIE_HEADER},
            400: _err("Dati non validi (motivo nel messaggio)."),
            409: _err("Email gia' registrata."),
        },
    ),
    Route(
        "POST", "/api/login",
        summary="Accesso con email e password",
        tags=("account",),
        request_schema={
            "type": "object",
            "properties": {
                "email": {"type": "string"},
                "password": {"type": "string"},
            },
            "required": ["email", "password"],
            "additionalProperties": False,
        },
        responses={
            200: {"description": "Sessione aperta.",
                  "schema": OK_USER_SCHEMA,
                  "headers": _SET_COOKIE_HEADER},
            400: _err("Corpo della richiesta non valido."),
            401: _err("Credenziali errate."),
        },
    ),
    Route(
        "POST", "/api/logout",
        summary="Chiusura della sessione",
        description="Sempre 200: il cookie viene fatto scadere "
                    "anche se la sessione non esiste piu'.",
        tags=("account",),
        responses={
            200: {"description": "Sessione chiusa.",
                  "schema": OK_SCHEMA,
                  "headers": _SET_COOKIE_HEADER},
        },
    ),
    Route(
        "POST", "/api/profile",
        summary="Completamento del profilo",
        description="Azienda e telefono completano la "
                    "registrazione e sbloccano il download dei "
                    "referti.",
        tags=("account",),
        auth=AUTH_SESSION,
        request_schema={
            "type": "object",
            "properties": {
                "azienda": {
                    "type": "string", "minLength": 1,
                    "x-errore": "Per completare la registrazione "
                                "servono azienda e telefono."},
                "telefono": {
                    "type": "string", "minLength": 1,
                    "x-errore": "Per completare la registrazione "
                                "servono azienda e telefono."},
            },
            "required": ["azienda", "telefono"],
            "additionalProperties": False,
        },
        responses={
            200: {"description": "Profilo aggiornato.",
                  "schema": OK_USER_SCHEMA},
            400: _err("Azienda o telefono mancanti."),
            401: _err("Accesso richiesto."),
        },
    ),
    Route(
        "POST", "/api/audit",
        summary="Avvia un audit",
        description="Un audit alla volta (409 se occupato) e uno "
                    "slot orario per utente (429 con retry_in_s). "
                    "L'avanzamento arriva da GET /api/status o "
                    "dall'SSE di GET /api/events; i referti dei "
                    "cinque formati da GET /api/report/{formato}. "
                    "I campi numerici accettano anche stringhe "
                    "numeriche; i campi omessi usano i default "
                    "indicati.",
        tags=("audit",),
        auth=AUTH_SESSION,
        request_schema=AUDIT_REQUEST_SCHEMA,
        responses={
            202: {"description": "Audit avviato (job con id: le "
                                 "rotte /api/v1/audits/{id} lo "
                                 "indirizzano).",
                  "schema": OK_ID_SCHEMA},
            400: _err("Configurazione non valida (motivo nel "
                      "messaggio)."),
            401: _err("Accesso richiesto."),
            409: _err("Un audit e' gia' in corso."),
            429: {"description": "Slot orario gia' consumato.",
                  "schema": {
                      "type": "object",
                      "properties": {
                          "error": {"type": "string"},
                          "retry_in_s": {"type": "integer"}},
                      "required": ["error", "retry_in_s"],
                      "additionalProperties": False}},
        },
    ),
    Route(
        "GET", "/api/status",
        summary="Stato e sintesi dell'audit",
        description="Snapshot del job: stato, log completo e — a "
                    "fine audit — sintesi, rilievi, piano di "
                    "remediation, esiti RRF e confronto "
                    "competitivo. Il polling e' il ripiego "
                    "dichiarato dell'SSE di GET /api/events.",
        tags=("audit",),
        auth=AUTH_SESSION,
        responses={
            200: {"description": "Snapshot corrente.",
                  "schema": SNAPSHOT_SCHEMA},
            401: _err("Accesso richiesto."),
        },
    ),
    Route(
        "GET", "/api/events",
        summary="Avanzamento push (Server-Sent Events)",
        description="Invia lo snapshot di GET /api/status a ogni "
                    "variazione (payload JSON nel campo data) e "
                    "chiude il flusso allo stato terminale; il "
                    "client ripiega sul polling se il flusso non "
                    "e' disponibile.",
        tags=("audit",),
        auth=AUTH_SESSION,
        responses={
            200: {"description": "Flusso di eventi con lo "
                                 "snapshot serializzato.",
                  "schema": {"type": "string"},
                  "content_type": "text/event-stream"},
            401: _err("Accesso richiesto."),
        },
    ),
    Route(
        "GET", "/api/report/{formato}",
        summary="Referto dell'ultimo audit concluso",
        description="Una sola scansione produce tutti i formati. "
                    "Riservato alla registrazione completa "
                    "(azienda e telefono nel profilo). L'HTML e' "
                    "servito con la CSP dedicata del referto "
                    "(script inline autonomo, nessuna origine "
                    "esterna).",
        tags=("audit",),
        auth=AUTH_SESSION,
        params=(
            {"name": "formato", "in": "path", "required": True,
             "schema": {"type": "string",
                        "enum": ["html", "json", "text", "md",
                                 "csv"]},
             "description": "Formato del referto."},
            {"name": "download", "in": "query", "required": False,
             "schema": {"type": "string"},
             "description": "Se presente, risposta come "
                            "allegato (Content-Disposition)."},
        ),
        responses={
            200: {"description": "Il referto nel formato "
                                 "richiesto.",
                  "content": {
                      "text/html": {"type": "string"},
                      "application/json": {"type": "object"},
                      "text/plain": {"type": "string"},
                      "text/markdown": {"type": "string"},
                      "text/csv": {"type": "string"}}},
            401: _err("Accesso richiesto."),
            403: {"description": "Registrazione completa "
                                 "richiesta.",
                  "schema": CODED_ERROR_SCHEMA},
            404: _err("Referto non disponibile (nessun audit "
                      "concluso o formato sconosciuto)."),
        },
    ),
    Route(
        "GET", "/api/history",
        summary="Storico degli audit dell'utente",
        description="Le esecuzioni dell'utente dalla piu' "
                    "recente (max 50), con punteggi e conteggi "
                    "dei rilievi.",
        tags=("storico",),
        auth=AUTH_SESSION,
        params=(
            {"name": "limit", "in": "query", "required": False,
             "schema": {"type": "integer", "minimum": 1,
                        "maximum": 200, "default": 50},
             "description": "Righe per pagina."},
            {"name": "offset", "in": "query", "required": False,
             "schema": {"type": "integer", "minimum": 0,
                        "default": 0},
             "description": "Righe da saltare."},
        ),
        responses={
            200: {"description": "Righe dello storico (paginate).",
                  "schema": {
                      "type": "object",
                      "properties": {
                          "runs": {"type": "array",
                                   "items": RUN_SCHEMA},
                          "limit": {"type": "integer"},
                          "offset": {"type": "integer"}},
                      "required": ["runs", "limit", "offset"],
                      "additionalProperties": False}},
            400: _err("limit o offset non validi."),
            401: _err("Accesso richiesto."),
        },
    ),
    Route(
        "GET", "/api/history/report",
        summary="Referto JSON completo di un'esecuzione",
        description="Il referto salvato nello storico, riservato "
                    "al proprietario con registrazione completa.",
        tags=("storico",),
        auth=AUTH_SESSION,
        params=(
            {"name": "id", "in": "query", "required": True,
             "schema": {"type": "integer"},
             "description": "Id della riga di storico."},
            {"name": "download", "in": "query", "required": False,
             "schema": {"type": "string"},
             "description": "Se presente, risposta come "
                            "allegato."},
        ),
        responses={
            200: {"description": "Referto JSON completo "
                                 "(schema_version).",
                  "schema": {"type": "object"}},
            400: _err("Id non valido."),
            401: _err("Accesso richiesto."),
            403: {"description": "Registrazione completa "
                                 "richiesta.",
                  "schema": CODED_ERROR_SCHEMA},
            404: _err("Referto non trovato."),
        },
    ),
    Route(
        "GET", "/api/history/compare",
        summary="Confronto fra due audit dello storico",
        description="Delta completo (punteggi, rilievi "
                    "risolti/nuovi) fra due esecuzioni dello "
                    "stesso sito; l'ordine temporale lo decide "
                    "il server.",
        tags=("storico",),
        auth=AUTH_SESSION,
        params=(
            {"name": "a", "in": "query", "required": True,
             "schema": {"type": "integer"},
             "description": "Id della prima esecuzione."},
            {"name": "b", "in": "query", "required": True,
             "schema": {"type": "integer"},
             "description": "Id della seconda esecuzione."},
        ),
        responses={
            200: {"description": "Confronto calcolato.",
                  "schema": {
                      "type": "object",
                      "properties": {
                          "site": {"type": "string"},
                          "older_at": {"type": "number"},
                          "newer_at": {"type": "number"},
                          "delta": {"type": "object"}},
                      "required": ["site", "older_at", "newer_at",
                                   "delta"],
                      "additionalProperties": False}},
            400: _err("Id non validi o siti diversi."),
            401: _err("Accesso richiesto."),
            404: _err("Audit non confrontabili."),
            500: _err("Referto salvato illeggibile."),
        },
    ),
    Route(
        "POST", "/api/v1/audits",
        summary="Avvia un audit come job con id",
        description="Il modello a risorse della Fase 2: 202 con "
                    "l'id del job, da seguire su GET "
                    "/api/v1/audits/{id} (o sull'SSE per-job) e "
                    "da cui scaricare i referti in ogni formato "
                    "e lingua. Stesso corpo e stessi limiti di "
                    "POST /api/audit (un audit alla volta di "
                    "default, slot orario per utente); errori "
                    "nell'oggetto uniforme delle rotte v1.",
        tags=("audit",),
        auth=AUTH_SESSION,
        request_schema=AUDIT_REQUEST_SCHEMA,
        responses={
            202: {"description": "Job creato e avviato.",
                  "schema": OK_ID_SCHEMA},
            400: _err_v1("Configurazione non valida."),
            401: _err_v1("Accesso richiesto."),
            409: _err_v1("Concorrenza esaurita: un audit e' gia' "
                         "in corso."),
            429: _err_v1("Slot orario gia' consumato "
                         "(retry_in_s nei params)."),
        },
    ),
    Route(
        "GET", "/api/v1/audits/{id}",
        summary="Stato e sintesi di un job di audit",
        description="Lo snapshot del job (stesso schema di "
                    "GET /api/status), indirizzato per id; solo "
                    "il proprietario lo vede (404 altrimenti: "
                    "nessuna esistenza rivelata).",
        tags=("audit",),
        auth=AUTH_SESSION,
        params=(
            {"name": "id", "in": "path", "required": True,
             "schema": {"type": "string"},
             "description": "Id del job (dal 202 di creazione)."},
        ),
        responses={
            200: {"description": "Snapshot del job.",
                  "schema": SNAPSHOT_SCHEMA},
            401: _err_v1("Accesso richiesto."),
            404: _err_v1("Job inesistente o di un altro utente."),
        },
    ),
    Route(
        "DELETE", "/api/v1/audits/{id}",
        summary="Annulla un job di audit",
        description="Annullamento cooperativo per id (stesse "
                    "garanzie di POST /api/cancel: nessun "
                    "risultato parziale, slot orario non "
                    "consumato).",
        tags=("audit",),
        auth=AUTH_SESSION,
        params=(
            {"name": "id", "in": "path", "required": True,
             "schema": {"type": "string"},
             "description": "Id del job."},
        ),
        responses={
            202: {"description": "Annullamento avviato.",
                  "schema": OK_SCHEMA},
            401: _err_v1("Accesso richiesto."),
            404: _err_v1("Job inesistente o di un altro utente."),
            409: _err_v1("Il job non e' in corso."),
        },
    ),
    Route(
        "GET", "/api/v1/audits/{id}/report",
        summary="Referto di un job, in ogni formato e lingua",
        description="La stessa scansione produce tutti i formati "
                    "e, on-demand, tutte le lingue del referto "
                    "(reso dal contesto del job e messo in "
                    "cache): parita' con --lang senza rifare "
                    "l'audit. Riservato alla registrazione "
                    "completa.",
        tags=("audit",),
        auth=AUTH_SESSION,
        params=(
            {"name": "id", "in": "path", "required": True,
             "schema": {"type": "string"},
             "description": "Id del job."},
            {"name": "format", "in": "query", "required": False,
             "schema": {"type": "string",
                        "enum": list(REPORT_FORMATS),
                        "default": "json"},
             "description": "Formato del referto."},
            {"name": "lang", "in": "query", "required": False,
             "schema": {"type": "string",
                        "enum": list(HTML_LANGS)},
             "description": "Lingua del referto (default: quella "
                            "dell'audit; il JSON resta canonico "
                            "in italiano)."},
            {"name": "download", "in": "query", "required": False,
             "schema": {"type": "string"},
             "description": "Se presente, risposta come "
                            "allegato."},
        ),
        responses={
            200: {"description": "Il referto richiesto.",
                  "content": {
                      "text/html": {"type": "string"},
                      "application/json": {"type": "object"},
                      "text/plain": {"type": "string"},
                      "text/markdown": {"type": "string"},
                      "text/csv": {"type": "string"}}},
            400: _err_v1("Formato o lingua sconosciuti."),
            401: _err_v1("Accesso richiesto."),
            403: _err_v1("Registrazione completa richiesta "
                         "(code profile_incomplete)."),
            404: _err_v1("Job inesistente o audit non concluso."),
        },
    ),
    Route(
        "GET", "/api/v1/audits/{id}/events",
        summary="Avanzamento push di un job (SSE)",
        description="Come GET /api/events ma per-job: snapshot a "
                    "ogni variazione, flusso chiuso allo stato "
                    "terminale, polling come ripiego.",
        tags=("audit",),
        auth=AUTH_SESSION,
        params=(
            {"name": "id", "in": "path", "required": True,
             "schema": {"type": "string"},
             "description": "Id del job."},
        ),
        responses={
            200: {"description": "Flusso di eventi con lo "
                                 "snapshot serializzato.",
                  "schema": {"type": "string"},
                  "content_type": "text/event-stream"},
            401: _err_v1("Accesso richiesto."),
            404: _err_v1("Job inesistente o di un altro utente."),
        },
    ),
    Route(
        "POST", "/api/v1/tokens",
        summary="Crea un token API personale",
        description="Token Bearer per client macchina e "
                    "cross-origin (stesso perimetro del cookie: "
                    "slot orario e gating del profilo). Il "
                    "valore in chiaro esiste SOLO in questa "
                    "risposta; in tabella va lo SHA-256. La "
                    "gestione dei token richiede la sessione "
                    "cookie: un token non puo' crearne altri.",
        tags=("account",),
        auth=AUTH_COOKIE,
        request_schema={
            "type": "object",
            "properties": {
                "label": {"type": "string", "maxLength": 60,
                          "description": "Etichetta mnemonica "
                                         "facoltativa."},
            },
            "additionalProperties": False,
        },
        responses={
            201: {"description": "Token creato (valore visibile "
                                 "solo ora).",
                  "schema": {
                      "type": "object",
                      "properties": {
                          "ok": {"type": "boolean"},
                          "id": {"type": "integer"},
                          "label": {"type": "string"},
                          "token": {"type": "string"}},
                      "required": ["ok", "id", "label", "token"],
                      "additionalProperties": False}},
            400: _err_v1("Corpo della richiesta non valido."),
            401: _err_v1("Accesso richiesto (sessione)."),
        },
    ),
    Route(
        "GET", "/api/v1/tokens",
        summary="Elenca i token API personali",
        description="Solo i metadati (id, etichetta, date): il "
                    "valore del token non e' recuperabile.",
        tags=("account",),
        auth=AUTH_COOKIE,
        responses={
            200: {"description": "Token dell'utente.",
                  "schema": {
                      "type": "object",
                      "properties": {"tokens": {
                          "type": "array",
                          "items": {
                              "type": "object",
                              "properties": {
                                  "id": {"type": "integer"},
                                  "label": {"type": "string"},
                                  "created_at":
                                      {"type": "number"},
                                  "last_used_at":
                                      {"type": "number"}},
                              "required": ["id", "label",
                                           "created_at",
                                           "last_used_at"],
                              "additionalProperties": False}}},
                      "required": ["tokens"],
                      "additionalProperties": False}},
            401: _err_v1("Accesso richiesto (sessione)."),
        },
    ),
    Route(
        "DELETE", "/api/v1/tokens/{id}",
        summary="Revoca un token API",
        tags=("account",),
        auth=AUTH_COOKIE,
        params=(
            {"name": "id", "in": "path", "required": True,
             "schema": {"type": "integer"},
             "description": "Id del token (da GET "
                            "/api/v1/tokens)."},
        ),
        responses={
            200: {"description": "Token revocato.",
                  "schema": OK_SCHEMA},
            400: _err_v1("Id non valido."),
            401: _err_v1("Accesso richiesto (sessione)."),
            404: _err_v1("Token non trovato."),
        },
    ),
    Route(
        "GET", "/api/citations",
        summary="Storico del monitoraggio citazioni IA",
        description="Serie per sito dallo storico JSONL di "
                    "mars_citations.py e pin-evento annotati; "
                    "file assenti o righe malformate producono "
                    "liste vuote, mai errori.",
        tags=("citazioni",),
        auth=AUTH_SESSION,
        responses={
            200: {"description": "Serie e eventi.",
                  "schema": {
                      "type": "object",
                      "properties": {
                          "sites": {"type": "array",
                                    "items": {"type": "object"}},
                          "events": {
                              "type": "array",
                              "items": {
                                  "type": "object",
                                  "properties": {
                                      "date": {"type": "string"},
                                      "label": {"type": "string"},
                                      "site": {"type": "string"},
                                  },
                                  "required": ["date", "label"],
                              }}},
                      "required": ["sites", "events"],
                      "additionalProperties": False}},
            401: _err("Accesso richiesto."),
        },
    ),
)


def route_for(method: str, path: str) -> Optional[Route]:
    """La rotta registrata per (metodo, percorso), o None."""
    for route in ROUTES:
        if route.method == method and route.path == path:
            return route
    return None


# ------------------- validazione delle richieste -------------------

def _tipo_ok(value: object, tipo: str) -> bool:
    if tipo == "string":
        return isinstance(value, str)
    if tipo == "integer":
        return isinstance(value, int) \
            and not isinstance(value, bool)
    if tipo == "number":
        return isinstance(value, (int, float)) \
            and not isinstance(value, bool)
    if tipo == "boolean":
        return isinstance(value, bool)
    if tipo == "object":
        return isinstance(value, dict)
    if tipo == "array":
        return isinstance(value, list)
    if tipo == "null":
        return value is None
    return False


def _valida(schema: Dict[str, object], value: object,
            dove: str) -> List[str]:
    """Errori (in italiano) di ``value`` rispetto allo schema.

    Sottoinsieme di JSON Schema sufficiente al registro: type
    (anche unione), object con properties/required/
    additionalProperties, string con minLength/maxLength/pattern,
    numeri con minimum/maximum, enum, array con items. La chiave
    ``x-errore`` di uno schema sostituisce il messaggio generato:
    e' cosi' che i messaggi storici della GUI restano identici.
    """
    errori: List[str] = []
    custom = schema.get("x-errore")

    def aggiungi(messaggio: str) -> None:
        errori.append(str(custom) if custom else messaggio)

    tipi = schema.get("type")
    if tipi is not None:
        ammessi = tipi if isinstance(tipi, list) else [tipi]
        if not any(_tipo_ok(value, str(t)) for t in ammessi):
            aggiungi("%s: tipo non valido (atteso %s)."
                     % (dove, "/".join(str(t) for t in ammessi)))
            return errori

    if "enum" in schema and value not in list(
            schema["enum"]):  # type: ignore[arg-type]
        aggiungi("%s: valore fuori dall'elenco ammesso." % dove)
        return errori

    if isinstance(value, str):
        min_len = schema.get("minLength")
        if isinstance(min_len, int) and len(value) < min_len:
            aggiungi("%s: troppo corto (minimo %d)."
                     % (dove, min_len))
        max_len = schema.get("maxLength")
        if isinstance(max_len, int) and len(value) > max_len:
            aggiungi("%s: troppo lungo (massimo %d)."
                     % (dove, max_len))
        pattern = schema.get("pattern")
        if isinstance(pattern, str) \
                and not re.search(pattern, value):
            aggiungi("%s: formato non valido." % dove)

    if isinstance(value, (int, float)) \
            and not isinstance(value, bool):
        minimo = schema.get("minimum")
        if isinstance(minimo, (int, float)) and value < minimo:
            aggiungi("%s: sotto il minimo (%s)." % (dove, minimo))
        massimo = schema.get("maximum")
        if isinstance(massimo, (int, float)) and value > massimo:
            aggiungi("%s: sopra il massimo (%s)."
                     % (dove, massimo))

    if isinstance(value, dict):
        proprieta = schema.get("properties")
        proprieta = proprieta if isinstance(proprieta, dict) else {}
        for nome in schema.get("required") or []:  # type: ignore
            if nome not in value:
                sotto = proprieta.get(nome)
                manca = ("%s: campo obbligatorio mancante."
                         % nome)
                if isinstance(sotto, dict) \
                        and sotto.get("x-errore"):
                    manca = str(sotto["x-errore"])
                errori.append(manca)
        if schema.get("additionalProperties") is False:
            ignote = sorted(set(value) - set(proprieta))
            if ignote:
                aggiungi("Campi sconosciuti: %s."
                         % ", ".join(ignote))
        for nome, sotto in proprieta.items():
            if nome in value and isinstance(sotto, dict):
                errori.extend(_valida(sotto, value[nome], nome))

    if isinstance(value, list):
        items = schema.get("items")
        if isinstance(items, dict):
            for indice, elemento in enumerate(value):
                errori.extend(_valida(
                    items, elemento, "%s[%d]" % (dove, indice)))

    return errori


def validate_request(route: Route,
                     payload: object) -> List[str]:
    """Errori del corpo di richiesta rispetto allo schema della
    rotta (lista vuota = valido; rotta senza schema = valido)."""
    if route.request_schema is None:
        return []
    return _valida(route.request_schema, payload, "corpo")


# ---------------------- generatore OpenAPI ------------------------

def _operation_id(route: Route) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-",
                  route.path.lower()).strip("-")
    return "%s-%s" % (route.method.lower(), slug)


def _senza_estensioni(schema: object) -> object:
    """Copia dello schema senza le chiavi interne ``x-errore``
    (restano nel registro per la validazione runtime, non servono
    ai client della spec)."""
    if isinstance(schema, dict):
        return {chiave: _senza_estensioni(valore)
                for chiave, valore in schema.items()
                if chiave != "x-errore"}
    if isinstance(schema, list):
        return [_senza_estensioni(v) for v in schema]
    return schema


def openapi_spec() -> Dict[str, object]:
    """La spec OpenAPI 3.1 generata dal registro delle rotte."""
    paths: Dict[str, Dict[str, object]] = {}
    for route in ROUTES:
        operazione: Dict[str, object] = {
            "operationId": _operation_id(route),
            "summary": route.summary,
            "tags": list(route.tags),
        }
        if route.description:
            operazione["description"] = route.description
        if route.auth == AUTH_SESSION:
            operazione["security"] = [{"cookieSession": []},
                                      {"bearerAuth": []}]
        elif route.auth == AUTH_COOKIE:
            operazione["security"] = [{"cookieSession": []}]
        if route.params:
            operazione["parameters"] = [
                {"name": str(param["name"]),
                 "in": str(param["in"]),
                 "required": bool(param.get("required")),
                 "description": str(param.get("description", "")),
                 "schema": _senza_estensioni(param["schema"])}
                for param in route.params]
        if route.request_schema is not None:
            operazione["requestBody"] = {
                "required": True,
                "content": {"application/json": {
                    "schema": _senza_estensioni(
                        route.request_schema)}},
            }
        risposte: Dict[str, object] = {}
        for stato in sorted(route.responses):
            dettaglio = route.responses[stato]
            voce: Dict[str, object] = {
                "description": str(dettaglio.get("description",
                                                 ""))}
            contenuti = dettaglio.get("content")
            schema = dettaglio.get("schema")
            if isinstance(contenuti, dict):
                voce["content"] = {
                    str(tipo): {"schema": _senza_estensioni(sch)}
                    for tipo, sch in contenuti.items()}
            elif schema is not None:
                tipo = str(dettaglio.get("content_type",
                                         "application/json"))
                voce["content"] = {tipo: {
                    "schema": _senza_estensioni(schema)}}
            intestazioni = dettaglio.get("headers")
            if isinstance(intestazioni, dict):
                voce["headers"] = _senza_estensioni(intestazioni)
            risposte[str(stato)] = voce
        operazione["responses"] = risposte
        paths.setdefault(route.path, {})[
            route.method.lower()] = operazione

    return {
        "openapi": "3.1.0",
        "info": {
            "title": "MARS Beacon API",
            "version": API_CONTRACT_VERSION,
            "description":
                "Contratto dell'API locale di MARS Beacon, "
                "generato dal registro dichiarativo delle rotte "
                "(marsbeacon/api.py): spec e codice non possono "
                "divergere per costruzione. Gli errori sono "
                "{\"error\": messaggio in italiano} (piu' "
                "\"code\" macchina dove indicato). Un audit alla "
                "volta; slot orario per utente; download dei "
                "referti riservato alla registrazione completa.",
            "license": {"name": "Apache 2.0",
                        "identifier": "Apache-2.0"},
        },
        "servers": [{
            "url": "http://127.0.0.1:8765",
            "description": "Server locale (binding predefinito; "
                           "non esporre su reti non fidate senza "
                           "un reverse proxy con autenticazione)."
        }],
        "tags": [
            {"name": "contratto",
             "description": "La spec stessa."},
            {"name": "ambiente",
             "description": "Capacita' e versioni del server."},
            {"name": "account",
             "description": "Registrazione, sessione, profilo."},
            {"name": "audit",
             "description": "Avvio, stato, annullamento e "
                            "referti degli audit."},
            {"name": "storico",
             "description": "Esecuzioni salvate: righe, referti "
                            "completi, confronti."},
            {"name": "citazioni",
             "description": "Monitoraggio delle citazioni IA."},
        ],
        "paths": paths,
        "components": {"securitySchemes": {
            "cookieSession": {
                "type": "apiKey", "in": "cookie",
                "name": SESSION_COOKIE_NAME,
                "description": "Cookie di sessione emesso da "
                               "/api/register e /api/login "
                               "(HttpOnly, SameSite=Strict).",
            },
            "bearerAuth": {
                "type": "http", "scheme": "bearer",
                "description": "Token API personale (POST "
                               "/api/v1/tokens, valore visibile "
                               "solo alla creazione): per client "
                               "macchina e cross-origin, stesso "
                               "perimetro del cookie.",
            },
        }},
    }


# =================================================================
# Motore del server (P1, Fase 2): store utenti, job di audit e
# handler delle rotte del contratto, estratti da mars_gui.py con
# spostamento meccanico (stesso metodo della scomposizione
# v1.58.0). mars_gui.py resta il combinato statici+API (eredita
# ApiHandler e aggiunge i file statici della GUI via _fallback);
# mars_api.py serve la sola API. Gli stati mutabili (JOB, STORE,
# CITATIONS_HISTORY) vivono QUI: chi li sostituisce (test, entry)
# deve farlo su questo modulo.
# =================================================================

# Asset della pagina di documentazione (/api/docs): l'unica
# concessione "statica" del motore — whitelist puntuale usata da
# _fallback, nessuna navigazione del filesystem. Il resto dei
# file della GUI vive solo nel server combinato.
DOCS_ASSETS = frozenset((
    "/vendor/scalar/standalone.js",
    "/vendor/bootstrap-italia/fonts/Titillium_Web/"
    "titillium-web-v10-latin-ext_latin-regular.woff2",
    "/vendor/bootstrap-italia/fonts/Titillium_Web/"
    "titillium-web-v10-latin-ext_latin-600.woff2",
    "/vendor/bootstrap-italia/fonts/Titillium_Web/"
    "titillium-web-v10-latin-ext_latin-700.woff2",
))


GUI_DIR = Path(__file__).resolve().parent.parent / "gui"

# Utenti e sessioni su SQLite accanto allo script (nel .gitignore).
# MARS_GUI_DB sposta il database altrove: serve al deploy systemd,
# dove /opt/seorrf e' in sola lettura e il DB vive nella
# StateDirectory (/var/lib/seorrf).
DB_PATH = Path(os.environ.get("MARS_GUI_DB")
               or Path(__file__).resolve().parent / "mars_gui.db")

# Storico del monitor citazioni (una riga JSON per esecuzione,
# scritto da mars_citations.py --history). Il default e' il file
# accanto agli script; sovrascrivibile con --citations-history, ad
# esempio /var/lib/seorrf/citazioni.jsonl nel deploy systemd.
CITATIONS_HISTORY = Path(__file__).resolve().parent \
    / "citazioni.jsonl"
SESSION_TTL_S = 7 * 24 * 3600
CHECK_INTERVAL_S = 3600  # un check per utente ogni ora
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
# Il referto HTML autonomo porta il proprio JavaScript inline
# (treemap e grafo interattivi, v1.53.0 del core): solo per quella
# risposta lo script inline e' ammesso — niente file esterni,
# le pagine della GUI restano sotto la CSP stretta.
REPORT_CSP = CSP + "; script-src 'unsafe-inline'"


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
                " info INTEGER NOT NULL,"
                " report_json TEXT NOT NULL DEFAULT '');"
                "CREATE TABLE IF NOT EXISTS api_tokens ("
                " id INTEGER PRIMARY KEY,"
                " user_id INTEGER NOT NULL,"
                " label TEXT NOT NULL DEFAULT '',"
                " token_hash TEXT NOT NULL UNIQUE,"
                " created_at REAL NOT NULL,"
                " last_used_at REAL NOT NULL DEFAULT 0);")
            # Migrazione dei database creati prima della 2.10.0
            # (multi-macchina: lo schema vecchio esiste davvero).
            cols = [r["name"] for r in
                    con.execute("PRAGMA table_info(audits)")]
            if "report_json" not in cols:
                con.execute("ALTER TABLE audits ADD COLUMN "
                            "report_json TEXT NOT NULL DEFAULT ''")

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

    @staticmethod
    def _utente(row: sqlite3.Row) -> Dict[str, object]:
        """Riga utente -> dizionario esposto dalle API (stessa
        forma per sessione cookie e token Bearer)."""
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
            return self._utente(row)

    # -------------------- token Bearer (API) ----------------------

    def create_api_token(self, user_id: int,
                         label: str = "") -> Tuple[int, str]:
        """Nuovo token Bearer: restituisce (id, token in chiaro).

        In tabella va solo lo SHA-256 del token — scelta
        dichiarata: il token e' casuale ad alta entropia, quindi
        l'hash veloce basta; il PBKDF2 serve alle password a bassa
        entropia e costerebbe 200k round a OGNI richiesta API. Il
        valore in chiaro esiste solo nella risposta di creazione.
        """
        token = "mars_" + secrets.token_hex(24)
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        with self.lock, self._connect() as con:
            cur = con.execute(
                "INSERT INTO api_tokens (user_id, label, "
                "token_hash, created_at) VALUES (?, ?, ?, ?)",
                (user_id, label, digest, time.time()))
            return int(cur.lastrowid), token

    def list_api_tokens(self, user_id: int
                        ) -> List[Dict[str, object]]:
        with self.lock, self._connect() as con:
            rows = con.execute(
                "SELECT id, label, created_at, last_used_at "
                "FROM api_tokens WHERE user_id = ? ORDER BY id",
                (user_id,)).fetchall()
        return [{"id": r["id"], "label": r["label"],
                 "created_at": r["created_at"],
                 "last_used_at": r["last_used_at"]}
                for r in rows]

    def revoke_api_token(self, user_id: int,
                         token_id: int) -> bool:
        with self.lock, self._connect() as con:
            cur = con.execute(
                "DELETE FROM api_tokens "
                "WHERE user_id = ? AND id = ?",
                (user_id, token_id))
            return cur.rowcount > 0

    def user_by_api_token(
            self, token: str) -> Optional[Dict[str, object]]:
        """Utente dietro un token Bearer (stesso perimetro del
        cookie: slot orario e gating del profilo identici)."""
        if not token:
            return None
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        with self.lock, self._connect() as con:
            row = con.execute(
                "SELECT u.*, t.id AS token_id FROM users u "
                "JOIN api_tokens t ON t.user_id = u.id "
                "WHERE t.token_hash = ?", (digest,)).fetchone()
            if row is None:
                return None
            con.execute(
                "UPDATE api_tokens SET last_used_at = ? "
                "WHERE id = ?", (time.time(), row["token_id"]))
            return self._utente(row)

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

    def add_audit(self, user_id: int, summary: Dict[str, object],
                  report_json: str = "") -> None:
        """Registra sintesi e referto JSON di un audit concluso."""
        with self.lock, self._connect() as con:
            con.execute(
                "INSERT INTO audits (user_id, site, created_at, "
                "overall, scores, critical, warning, info, "
                "report_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (user_id, str(summary.get("site", "")), time.time(),
                 float(summary.get("overall") or 0),
                 json.dumps(summary.get("scores") or {},
                            ensure_ascii=False),
                 int(summary.get("critical") or 0),
                 int(summary.get("warning") or 0),
                 int(summary.get("info") or 0),
                 report_json))

    def history(self, user_id: int, limit: int = 50,
                offset: int = 0) -> List[Dict[str, object]]:
        """Storico degli audit dell'utente, dal piu' recente
        (paginato con limit/offset)."""
        with self.lock, self._connect() as con:
            rows = con.execute(
                "SELECT id, site, created_at, overall, scores, "
                "critical, warning, info, "
                "report_json != '' AS has_report "
                "FROM audits WHERE user_id = ? "
                "ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (user_id, limit, offset)).fetchall()
        return [
            {
                "id": row["id"],
                "site": row["site"],
                "created_at": row["created_at"],
                "overall": row["overall"],
                "scores": json.loads(row["scores"]),
                "critical": row["critical"],
                "warning": row["warning"],
                "info": row["info"],
                "has_report": bool(row["has_report"]),
            }
            for row in rows
        ]

    def last_audit_report(self, user_id: int,
                          site: str) -> Optional[Dict[str, object]]:
        """Ultimo referto salvato dell'utente per lo stesso sito."""
        with self.lock, self._connect() as con:
            row = con.execute(
                "SELECT created_at, report_json FROM audits "
                "WHERE user_id = ? AND site = ? "
                "AND report_json != '' "
                "ORDER BY created_at DESC LIMIT 1",
                (user_id, site)).fetchone()
        if row is None:
            return None
        return {"created_at": row["created_at"],
                "report_json": row["report_json"]}

    def audit_report(self, user_id: int,
                     audit_id: int) -> Optional[Dict[str, object]]:
        """Referto salvato per l'export; solo se dell'utente."""
        with self.lock, self._connect() as con:
            row = con.execute(
                "SELECT id, site, created_at, report_json "
                "FROM audits WHERE id = ? AND user_id = ? "
                "AND report_json != ''",
                (audit_id, user_id)).fetchone()
        if row is None:
            return None
        return {"id": row["id"], "site": row["site"],
                "created_at": row["created_at"],
                "report_json": row["report_json"]}


STORE: Optional[UserStore] = None


def get_store() -> UserStore:
    global STORE
    if STORE is None:
        STORE = UserStore(DB_PATH)
    return STORE


def _render_report(ctx: Dict[str, object], fmt: str,
                   lang: str) -> str:
    """Un referto dal contesto di un audit concluso.

    La stessa scansione produce tutti i formati e, a richiesta,
    tutte le lingue (Job.report con ``lang``); il JSON resta
    canonico in italiano.
    """
    comuni = dict(market=ctx["market"], judge=ctx["judge"],
                  delta=ctx["delta"],
                  lighthouse=ctx["lighthouse"],
                  search_check=ctx["search"])
    argomenti = (ctx["base"], ctx["pages"], ctx["findings"],
                 ctx["scores"], ctx["results"], ctx["mode"],
                 ctx["k"], ctx["competitive"])
    if fmt == "json":
        return sra.render_json(*argomenti, **comuni,
                               rrf_params=ctx["rrf_params"],
                               thresholds=ctx["soglie"] or None)
    renderer = {"html": sra.render_html, "text": sra.render_text,
                "md": sra.render_markdown,
                "csv": sra.render_csv}[fmt]
    return renderer(*argomenti, **comuni, lang=lang)


class Job:
    """Stato di un audit (job): identita', avanzamento, referti."""

    def __init__(self, job_id: str = "") -> None:
        self.lock = threading.Lock()
        self.job_id = job_id
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
        # contesto di rendering dell'audit concluso: alimenta i
        # referti on-demand in altre lingue (report con lang)
        self._ctx: Optional[Dict[str, object]] = None

    def snapshot(self) -> Dict[str, object]:
        with self.lock:
            return {
                "id": self.job_id,
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
        soglie = dict(cfg.get("soglie") or {})
        try:
            with contextlib.redirect_stderr(buf):
                # Soglie di prassi personalizzate (parita' con
                # --config della CLI): attive solo durante
                # l'audit, ripristino garantito dal finally.
                precedenti = (sra.apply_thresholds(soglie)
                              if soglie else {})
                try:
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
                        top_n=int(cfg.get("top_n",
                                          sra.DEFAULT_TOP_N)),
                        rrf_weights=cfg.get("rrf_weights"),
                        chunk_words=int(cfg.get(
                            "chunk_words",
                            sra.DEFAULT_CHUNK_WORDS)),
                        stop_event=self.stop_event)
                finally:
                    if precedenti:
                        sra.apply_thresholds(precedenti)
                lighthouse = sra.run_lighthouse(
                    str(cfg["url"]), pages,
                    mode=str(cfg.get("lighthouse",
                                     sra.LIGHTHOUSE_OFF)),
                    n_pages=int(cfg.get(
                        "lighthouse_pages",
                        sra.DEFAULT_LIGHTHOUSE_PAGES)),
                    device=str(cfg.get(
                        "lighthouse_device",
                        sra.LIGHTHOUSE_DEVICE_MOBILE)),
                    delay=float(cfg["delay"]),
                    verbose=True,
                    stop_event=self.stop_event)
                judge = sra.run_judge(results, pages, judge_mode,
                                      verbose=True)
                search = sra.run_search_check(
                    str(cfg["url"]), results,
                    str(cfg.get("search_check",
                                sra.SEARCH_CHECK_AUTO)),
                    verbose=True)
            buf.flush()
            findings = sra.merge_lighthouse_findings(findings,
                                                     lighthouse)
            lighthouse_score = sra.lighthouse_area_score(lighthouse)
            if lighthouse_score is not None:
                scores[sra.AREA_LIGHTHOUSE] = lighthouse_score
            lighthouse_block = sra.lighthouse_report_data(lighthouse)
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
        lang = str(cfg.get("lang", "it"))
        delta = None
        if self.user_id:
            previous = get_store().last_audit_report(
                self.user_id, base)
            if previous:
                try:
                    delta = compute_delta(
                        json.loads(str(previous["report_json"])),
                        sra.history_payload(
                            base, findings, scores,
                            lighthouse=lighthouse_block),
                        float(str(previous["created_at"])))
                except (ValueError, KeyError, TypeError):
                    delta = None  # referto vecchio illeggibile
        ctx: Dict[str, object] = {
            "base": base, "pages": pages, "findings": findings,
            "scores": scores, "results": results, "mode": mode,
            "k": k, "competitive": competitive, "market": market,
            "judge": judge, "delta": delta,
            "lighthouse": lighthouse_block, "search": search,
            "lang": lang, "soglie": soglie,
            "rrf_params": {
                "top_n": int(cfg.get("top_n",
                                     sra.DEFAULT_TOP_N)),
                "weights": list(cfg.get("rrf_weights")
                                or (1.0, 1.0)),
                "chunk_words": int(cfg.get(
                    "chunk_words", sra.DEFAULT_CHUNK_WORDS)),
            },
        }
        reports = {fmt: _render_report(ctx, fmt, lang)
                   for fmt in REPORT_FORMATS}
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
            "depth_distribution": sra.depth_distribution(pages,
                                                         base),
            "link_graph": sra.link_graph_data(pages, base),
            "citability": sra.citability_profiles(pages, scores,
                                                  market),
            "citability_actions": sra.citability_top_actions(
                findings, pages, scores, market),
            "judge": judge,
            "lighthouse": lighthouse_block,
            "search_check": search,
            "delta": delta,
            "critical": severities.count(sra.SEV_CRITICAL),
            "warning": severities.count(sra.SEV_WARNING),
            "info": severities.count(sra.SEV_INFO),
            "lang": lang,
            "thresholds": soglie or None,
            "fail_under": cfg.get("fail_under"),
            "gate_passed": (
                None if cfg.get("fail_under") is None
                else bool(sra.overall_score(scores)
                          >= float(str(cfg["fail_under"])))),
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        }
        if self.user_id:
            get_store().add_audit(self.user_id, summary,
                                  reports["json"])
        with self.lock:
            self.reports = reports
            self._ctx = ctx
            self.summary = summary
            self.findings = [f.as_dict() for f in findings]
            self.remediation = sra.build_remediation(
                findings, pages, scores, market)
            self.rrf = [sra.asdict(r) for r in results]
            self.competitive = competitive
            self.state = "done"

    def report(self, fmt: str,
               lang: Optional[str] = None) -> Optional[str]:
        """Referto del job; con una ``lang`` diversa dalla lingua
        del job viene reso al volo dal contesto e messo in cache:
        la parita' con --lang senza rifare la scansione."""
        with self.lock:
            ctx = self._ctx
            if lang is None or (ctx is not None
                                and lang == ctx["lang"]):
                return self.reports.get(fmt)
            if ctx is None:
                return None
            chiave = "%s@%s" % (fmt, lang)
            pronto = self.reports.get(chiave)
        if pronto is not None:
            return pronto
        testo = _render_report(ctx, fmt, lang)
        with self.lock:
            self.reports[chiave] = testo
        return testo


JOB = Job()


# Registro dei job per id (P1, Fase 2): POST /api/v1/audits crea un
# job e le rotte v1 lo indirizzano per id; JOB resta il "job
# corrente" delle rotte legacy (l'ultimo creato). I job conclusi
# restano consultabili finche' il registro non supera JOBS_MAX
# (potatura dei piu' vecchi non in corso).
JOBS: Dict[str, Job] = {}


JOBS_LOCK = threading.Lock()


JOBS_MAX = 20


# Audit in parallelo ammessi (coda a concorrenza configurabile,
# decisione di Fase 0; default 1 = comportamento storico: 409
# quando occupato). Gli entry la espongono con --max-audit.
AUDIT_CONCURRENCY = 1


def _running_jobs() -> int:
    """Audit in corso: i job del registro piu' l'eventuale job
    legacy avviato fuori registro (test, fixture)."""
    occupati = sum(1 for job in JOBS.values()
                   if job.state == "running")
    if JOB.state == "running" and JOB.job_id not in JOBS:
        occupati += 1
    return occupati


def _prune_jobs() -> None:
    """Sotto JOBS_LOCK: elimina i job conclusi piu' vecchi."""
    while len(JOBS) > JOBS_MAX:
        for job_id, job in list(JOBS.items()):
            if job.state != "running":
                del JOBS[job_id]
                break
        else:
            break


# Origini cross-origin ammesse (CORS): SPENTO di default, si
# attiva solo con un elenco esplicito (decisione di Fase 0; entry
# mars_api: --cors). Cross-origin ci si autentica col token
# Bearer: il cookie SameSite=Strict non viaggia e non concediamo
# credenziali (mai Allow-Credentials).
CORS_ORIGINS: Tuple[str, ...] = ()


# Dalla 2.11.0 il confronto fra esecuzioni vive nel core (riusato
# anche dalla CLI con --history): l'alias mantiene la firma storica.
compute_delta = sra.compute_delta


def read_citations_events(path: str) -> List[Dict[str, str]]:
    """Eventi-annotazione per il grafico citazioni (pin-evento).

    File JSONL accanto allo storico citazioni (eventi.jsonl): una
    riga per evento, es.
    ``{"date": "2026-07-21", "label": "Pubblicate le FAQ"}``
    (campo opzionale "site" per filtrare). Righe malformate e file
    assente vengono ignorati; scritto a mano o da automazioni.
    """
    events: List[Dict[str, str]] = []
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
                date = str(row.get("date", "")).strip()[:10]
                label = str(row.get("label", "")).strip()
                if date and label:
                    events.append({
                        "date": date, "label": label,
                        "site": str(row.get("site", "")).strip()})
    except OSError:
        pass
    events.sort(key=lambda e: e["date"])
    return events


def read_citations_history(path: str) -> List[Dict[str, object]]:
    """Storico del monitor citazioni raggruppato per sito.

    Legge il JSONL scritto da mars_citations.py (una riga per
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
    top_n = number("top_n", sra.DEFAULT_TOP_N,
                   sra.TOP_N_MIN, sra.TOP_N_MAX)
    chunk_words = number("chunk_words", sra.DEFAULT_CHUNK_WORDS,
                         sra.CHUNK_WORDS_MIN, sra.CHUNK_WORDS_MAX)
    w_lex = number("w_lex", 1.0, 0.1, 10)
    w_vec = number("w_vec", 1.0, 0.1, 10)
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

    lighthouse = str(raw.get("lighthouse",
                             sra.LIGHTHOUSE_OFF)).strip().lower()
    if lighthouse not in sra.LIGHTHOUSE_MODES:
        return None, "Valore non valido per 'lighthouse'."
    if lighthouse == sra.LIGHTHOUSE_ALWAYS:
        lighthouse_reason = sra.lighthouse_unavailable()
        if lighthouse_reason:
            return None, ("Audit Lighthouse obbligatorio ma non "
                          "disponibile sul server: %s."
                          % lighthouse_reason)
    lighthouse_pages = number("lighthouse_pages",
                              sra.DEFAULT_LIGHTHOUSE_PAGES,
                              sra.LIGHTHOUSE_PAGES_MIN,
                              sra.LIGHTHOUSE_PAGES_MAX)
    lighthouse_device = str(raw.get(
        "lighthouse_device",
        sra.LIGHTHOUSE_DEVICE_MOBILE)).strip().lower()
    if lighthouse_device not in sra.LIGHTHOUSE_DEVICES:
        return None, "Valore non valido per 'lighthouse_device'."

    search_check = str(raw.get(
        "search_check", sra.SEARCH_CHECK_AUTO)).strip().lower()
    if search_check not in sra.SEARCH_CHECK_MODES:
        return None, "Valore non valido per 'search_check'."
    if search_check == sra.SEARCH_CHECK_ON:
        search_reason = sra.search_check_unavailable()
        if search_reason:
            return None, ("Ancora di realta' obbligatoria ma non "
                          "disponibile sul server: %s."
                          % search_reason)

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
              ("retries", retries), ("workers", workers),
              ("top_n", top_n), ("chunk_words", chunk_words),
              ("w_lex", w_lex), ("w_vec", w_vec),
              ("lighthouse_pages", lighthouse_pages))
    for name, value in checks:
        if value is None:
            return None, "Valore non valido per '%s'." % name

    lang = str(raw.get("lang", "it")).strip().lower()
    if lang not in sra.HTML_LANGS:
        return None, "Valore non valido per 'lang'."

    fail_under = raw.get("fail_under")
    if fail_under is not None:
        try:
            fail_under = float(fail_under)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return None, "Valore non valido per 'fail_under'."
        if not 0 <= fail_under <= 100:
            return None, "Valore non valido per 'fail_under'."

    soglie_raw = raw.get("soglie")
    soglie: Dict[str, object] = {}
    if soglie_raw is not None:
        if not isinstance(soglie_raw, dict):
            return None, "Il campo 'soglie' vuole un oggetto."
        try:
            soglie = sra.check_thresholds(soglie_raw)
        except ValueError as exc:
            return None, str(exc)

    queries = [q.strip() for q in str(raw.get("queries", "")).split("\n")
               if q.strip()]

    queries_gsc = str(raw.get("queries_gsc", ""))
    if queries_gsc.strip():
        if queries:
            return None, ("'queries' e 'queries_gsc' non sono "
                          "combinabili: scegli una sola sorgente "
                          "di query.")
        queries = sra.parse_gsc_queries(queries_gsc)
        if not queries:
            return None, ("Nessuna query utilizzabile nell'export "
                          "Search Console.")

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
        "lighthouse": lighthouse,
        "lighthouse_pages": int(lighthouse_pages),
        "lighthouse_device": lighthouse_device,
        "search_check": search_check,
        "top_n": int(top_n),
        "chunk_words": int(chunk_words),
        "rrf_weights": (float(w_lex), float(w_vec)),
        "queries": queries,
        "embeddings": str(raw.get("embeddings", "")).strip(),
        "competitors": competitors,
        "lang": lang,
        "soglie": soglie,
        "fail_under": fail_under,
    }, ""


class ApiHandler(BaseHTTPRequestHandler):
    """Instrada le sole rotte API del contratto (piu' la pagina
    /api/docs coi suoi asset, in whitelist puntuale: nessun
    filesystem statico generale). Il server combinato della GUI
    (mars_gui.Handler) eredita e aggiunge i file statici tramite
    l'hook _fallback."""

    server_version = "MarsBeaconApi/%s" % API_CONTRACT_VERSION
    # Versione dell'applicazione che monta il motore (la GUI o
    # l'entry solo-API): compare come gui_version in /api/env.
    app_version = ""

    def _send(self, status: int, body: bytes, ctype: str,
              download: str = "", cookie: str = "",
              csp: str = "") -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", csp or CSP)
        self.send_header("Cache-Control", "no-store")
        origin = self.headers.get("Origin", "")
        if origin and origin in CORS_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
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
            if name == SESSION_COOKIE_NAME:
                return value
        return ""

    def _session_user(self) -> Optional[Dict[str, object]]:
        return get_store().user_by_token(self._session_token())

    def _bearer_user(self) -> Optional[Dict[str, object]]:
        header = self.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return None
        return get_store().user_by_api_token(header[7:].strip())

    def _auth_user(self) -> Optional[Dict[str, object]]:
        """Utente autenticato: cookie di sessione O token Bearer
        (doppio binario della Fase 0; stesso perimetro — slot
        orario e gating del profilo valgono per entrambi). La
        GESTIONE dei token resta solo via sessione."""
        return self._session_user() or self._bearer_user()

    def _send_v1_error(self, status: int, code: str,
                       message: str,
                       params: Optional[Dict[str, object]] = None
                       ) -> None:
        """Errore uniforme delle rotte /api/v1: {code, key,
        message, params} — stesso meccanismo chiave+parametri dei
        rilievi (decisione di Fase 0); il messaggio italiano
        resta canonico. Le rotte legacy conservano {"error"}."""
        self._send_json(status, {"error": {
            "code": code, "key": "api.err.%s" % code,
            "message": message, "params": params or {}}})

    def do_OPTIONS(self) -> None:  # noqa: N802 - BaseHTTPServer
        """Preflight CORS: header solo per le origini dichiarate
        in CORS_ORIGINS (spento di default)."""
        origin = self.headers.get("Origin", "")
        self.send_response(204)
        if origin and origin in CORS_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Methods",
                             "GET, POST, DELETE, OPTIONS")
            self.send_header("Access-Control-Allow-Headers",
                             "Content-Type, Authorization")
            self.send_header("Access-Control-Max-Age", "600")
        self.send_header("Content-Length", "0")
        self.end_headers()

    @staticmethod
    def _cookie(token: str, expire: bool = False) -> str:
        base = "%s=%s; Path=/; HttpOnly; SameSite=Strict" \
            % (SESSION_COOKIE_NAME, token)
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

    def _stream_events(self, job: Job) -> None:
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
                snap = job.snapshot()
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

    def do_GET(self) -> None:  # noqa: N802 - firma di BaseHTTPServer
        path = self.path.split("?", 1)[0]
        if path == "/api/v1/openapi.json":
            # Contratto API generato al volo dal registro delle
            # rotte (marsbeacon/api.py): mai letto da file.
            self._send_json(200, openapi_spec())
        elif path == "/api/docs":
            # Documentazione navigabile del contratto: Scalar
            # vendorizzato in modalita' markup, CSP stretta.
            self._send_file("api-docs.html")
        elif path == "/api/env":
            ram = sra.available_ram_mb()
            suggested = (max(1, round(ram * 0.1))
                         if ram is not None else None)
            lighthouse_reason = sra.lighthouse_unavailable()
            search_reason = sra.search_check_unavailable()
            self._send_json(200, {
                "tool_version": sra.__version__,
                "gui_version": self.app_version,
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
                "lighthouse_available": lighthouse_reason is None,
                "lighthouse_reason": lighthouse_reason or "",
                "lighthouse_version": sra.lighthouse_version() or "",
                "search_check_available": search_reason is None,
                "search_check_reason": search_reason or "",
                "default_embeddings_model":
                    sra.DEFAULT_EMBEDDINGS_MODEL,
            })
        elif path == "/api/me":
            user = self._auth_user()
            if user is None:
                self._send_json(200, {"authenticated": False})
            else:
                self._send_json(200, {"authenticated": True,
                                      "user": user})
        elif path == "/api/status":
            if self._auth_user() is None:
                self._send_json(401, {"error": "accesso richiesto"})
                return
            self._send_json(200, JOB.snapshot())
        elif path == "/api/history":
            user = self._auth_user()
            if user is None:
                self._send_json(401, {"error": "accesso richiesto"})
                return
            query = self.path.split("?", 1)[-1] \
                if "?" in self.path else ""
            params = dict(part.split("=", 1)
                          for part in query.split("&")
                          if "=" in part)
            try:
                limit = int(params.get("limit", "50"))
                offset = int(params.get("offset", "0"))
            except (TypeError, ValueError):
                self._send_json(400, {"error": "limit e offset "
                                               "vogliono numeri "
                                               "interi"})
                return
            if not (1 <= limit <= 200 and offset >= 0):
                self._send_json(400, {"error": "limit fra 1 e 200 "
                                               "e offset >= 0"})
                return
            self._send_json(200, {
                "runs": get_store().history(int(user["id"]),
                                            limit=limit,
                                            offset=offset),
                "limit": limit, "offset": offset})
        elif path == "/api/citations":
            if self._auth_user() is None:
                self._send_json(401, {"error": "accesso richiesto"})
                return
            self._send_json(200, {
                "sites": read_citations_history(
                    str(CITATIONS_HISTORY)),
                "events": read_citations_events(
                    str(CITATIONS_HISTORY.with_name(
                        "eventi.jsonl")))})
        elif path == "/api/history/compare":
            user = self._auth_user()
            if user is None:
                self._send_json(401, {"error": "accesso richiesto"})
                return
            query = self.path.split("?", 1)[-1] \
                if "?" in self.path else ""
            params = dict(part.split("=", 1)
                          for part in query.split("&")
                          if "=" in part)
            try:
                id_a = int(params.get("a", ""))
                id_b = int(params.get("b", ""))
            except (ValueError, TypeError):
                self._send_json(400, {"error": "id non validi"})
                return
            uid = int(user["id"])
            rec_a = get_store().audit_report(uid, id_a)
            rec_b = get_store().audit_report(uid, id_b)
            if rec_a is None or rec_b is None or id_a == id_b:
                self._send_json(404, {"error": "audit non "
                                               "confrontabili"})
                return
            if rec_a["site"] != rec_b["site"]:
                self._send_json(400, {
                    "error": "Gli audit da confrontare devono "
                             "riguardare lo stesso sito."})
                return
            older, newer = sorted(
                (rec_a, rec_b),
                key=lambda r: float(str(r["created_at"])))
            try:
                delta = sra.compute_delta(
                    json.loads(str(older["report_json"])),
                    json.loads(str(newer["report_json"])),
                    float(str(older["created_at"])))
            except (ValueError, KeyError, TypeError):
                self._send_json(500, {"error": "referto salvato "
                                               "illeggibile"})
                return
            self._send_json(200, {
                "site": newer["site"],
                "older_at": older["created_at"],
                "newer_at": newer["created_at"],
                "delta": delta})
        elif path == "/api/history/report":
            user = self._auth_user()
            if user is None:
                self._send_json(401, {"error": "accesso richiesto"})
                return
            if not user["profile_complete"]:
                self._send_json(403, {
                    "error": "L'export dei referti richiede la "
                             "registrazione completa: aggiungi "
                             "azienda e telefono al profilo.",
                    "code": "profile_incomplete"})
                return
            query = self.path.split("?", 1)[-1] \
                if "?" in self.path else ""
            try:
                audit_id = int(dict(
                    part.split("=", 1) for part in query.split("&")
                    if "=" in part).get("id", ""))
            except (ValueError, TypeError):
                self._send_json(400, {"error": "id non valido"})
                return
            stored = get_store().audit_report(int(user["id"]),
                                              audit_id)
            if stored is None:
                self._send_json(404, {"error": "referto non "
                                               "trovato"})
                return
            download = ""
            if "download" in query:
                download = "audit-%d.json" % audit_id
            self._send(200,
                       str(stored["report_json"]).encode("utf-8"),
                       CONTENT_TYPES[".json"], download=download)
        elif path == "/api/events":
            if self._auth_user() is None:
                self._send_json(401, {"error": "accesso richiesto"})
                return
            self._stream_events(JOB)
        elif path.startswith("/api/report/"):
            user = self._auth_user()
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
            if fmt not in ("html", "json", "text", "md", "csv") \
                    or report is None:
                self._send_json(404, {"error": "referto non disponibile"})
                return
            ctypes = REPORT_CTYPES
            download = ""
            if "download" in self.path:
                ext = {"html": "html", "json": "json",
                       "text": "txt", "md": "md", "csv": "csv"}
                nome = ("rilievi-mars" if fmt == "csv"
                        else "referto-mars")
                download = "%s.%s" % (nome, ext[fmt])
            self._send(200, report.encode("utf-8"), ctypes[fmt],
                       download=download,
                       csp=REPORT_CSP if fmt == "html" else "")
        elif path.startswith("/api/v1/audits/"):
            self._get_v1_audit(path)
        elif path == "/api/v1/tokens":
            self._get_v1_tokens()
        elif path.startswith("/api/"):
            self._send_json(404, {"error": "endpoint sconosciuto"})
        else:
            self._fallback(path)

    def _fallback(self, path: str) -> None:
        """Percorsi fuori da /api/: il motore serve SOLO gli asset
        della pagina di documentazione (whitelist puntuale, niente
        filesystem statico); mars_gui.Handler sovrascrive con i
        file statici della GUI."""
        if path in DOCS_ASSETS:
            self._send_file(path.lstrip("/"))
        else:
            self._send_json(404, {"error": "non trovato"})

    def _send_file(self, rel: str) -> None:
        """Un file noto della cartella gui/ (pagina docs e asset in
        whitelist): lettura puntuale, nessuna navigazione."""
        target = GUI_DIR / rel
        if not target.is_file():
            self._send_json(404, {"error": "non trovato"})
            return
        ctype = CONTENT_TYPES.get(target.suffix.lower(),
                                  "application/octet-stream")
        self._send(200, target.read_bytes(), ctype)

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
        elif path == "/api/citations/events":
            if self._auth_user() is None:
                self._send_json(401, {"error": "accesso richiesto"})
                return
            raw = self._read_json()
            if raw is None:
                return
            date = str(raw.get("date", "")).strip()
            label = str(raw.get("label", "")).strip()
            site = str(raw.get("site", "")).strip()
            evento = {"date": date, "label": label}
            if site:
                evento["site"] = site
            # Validazione dal registro del contratto: stessi
            # schemi della spec OpenAPI, messaggi storici
            # preservati via x-errore.
            rotta = route_for("POST",
                              "/api/citations/events")
            errori = validate_request(rotta, evento)
            if errori:
                self._send_json(400, {"error": errori[0]})
                return
            try:
                with open(CITATIONS_HISTORY.with_name(
                        "eventi.jsonl"), "a",
                        encoding="utf-8") as handle:
                    handle.write(json.dumps(
                        evento, ensure_ascii=False) + "\n")
            except OSError as exc:
                self._send_json(500, {"error": "impossibile "
                                               "salvare l'evento: "
                                               "%s" % exc})
                return
            self._send_json(201, {"ok": True, "event": evento})
        elif path == "/api/cancel":
            if self._auth_user() is None:
                self._send_json(401, {"error": "accesso richiesto"})
            elif JOB.cancel():
                self._send_json(202, {"ok": True})
            else:
                self._send_json(409, {"error": "Nessun audit in "
                                               "corso da annullare."})
        elif path == "/api/audit":
            self._post_audit()
        elif path == "/api/v1/audits":
            self._post_audit(v1=True)
        elif path == "/api/v1/tokens":
            self._post_v1_token()
        else:
            self._send_json(404, {"error": "endpoint sconosciuto"})

    def do_DELETE(self) -> None:  # noqa: N802 - BaseHTTPServer
        path = self.path.split("?", 1)[0]
        if path.startswith("/api/v1/audits/"):
            self._delete_v1_audit(path)
        elif path.startswith("/api/v1/tokens/"):
            self._delete_v1_token(path)
        else:
            self._send_json(404, {"error": "endpoint sconosciuto"})

    # ---------------- rotte /api/v1 (job e token) -----------------

    def _job_v1(self, job_id: str) -> Tuple[Optional[Job],
                                            Optional[Dict[str,
                                                          object]]]:
        """Job per id, solo del proprietario. Risponde da solo su
        errore e ritorna (None, None); i job altrui non esistono
        (404: nessuna esistenza rivelata)."""
        user = self._auth_user()
        if user is None:
            self._send_v1_error(401, "unauthorized",
                                "Accesso richiesto.")
            return None, None
        job = JOBS.get(job_id)
        if job is None or job.user_id != int(user["id"]):
            self._send_v1_error(404, "not_found",
                                "Audit non trovato.",
                                {"id": job_id})
            return None, None
        return job, user

    def _get_v1_audit(self, path: str) -> None:
        parti = path[len("/api/v1/audits/"):].split("/")
        if len(parti) == 1:
            job, _ = self._job_v1(parti[0])
            if job is not None:
                self._send_json(200, job.snapshot())
        elif len(parti) == 2 and parti[1] == "report":
            self._get_v1_report(parti[0])
        elif len(parti) == 2 and parti[1] == "events":
            job, _ = self._job_v1(parti[0])
            if job is not None:
                self._stream_events(job)
        else:
            self._send_v1_error(404, "not_found",
                                "Percorso sconosciuto.")

    def _get_v1_report(self, job_id: str) -> None:
        job, user = self._job_v1(job_id)
        if job is None or user is None:
            return
        if not user["profile_complete"]:
            self._send_v1_error(
                403, "profile_incomplete",
                "Il download dei referti richiede la "
                "registrazione completa: aggiungi azienda e "
                "telefono al profilo.")
            return
        query = self.path.split("?", 1)[-1] \
            if "?" in self.path else ""
        params = dict(part.split("=", 1)
                      for part in query.split("&") if "=" in part)
        fmt = params.get("format", "json")
        lang = params.get("lang", "")
        if fmt not in REPORT_FORMATS:
            self._send_v1_error(400, "invalid_format",
                                "Formato del referto sconosciuto.",
                                {"format": fmt})
            return
        if lang and lang not in sra.HTML_LANGS:
            self._send_v1_error(400, "invalid_lang",
                                "Lingua del referto sconosciuta.",
                                {"lang": lang})
            return
        report = job.report(fmt, lang or None)
        if report is None:
            self._send_v1_error(404, "report_not_ready",
                                "Referto non disponibile: l'audit "
                                "non e' concluso.")
            return
        download = ""
        if "download" in params:
            ext = {"html": "html", "json": "json", "text": "txt",
                   "md": "md", "csv": "csv"}
            nome = ("rilievi-mars" if fmt == "csv"
                    else "referto-mars")
            download = "%s.%s" % (nome, ext[fmt])
        self._send(200, report.encode("utf-8"),
                   REPORT_CTYPES[fmt], download=download,
                   csp=REPORT_CSP if fmt == "html" else "")

    def _delete_v1_audit(self, path: str) -> None:
        resto = path[len("/api/v1/audits/"):]
        if "/" in resto:
            self._send_v1_error(404, "not_found",
                                "Percorso sconosciuto.")
            return
        job, _ = self._job_v1(resto)
        if job is None:
            return
        if job.cancel():
            self._send_json(202, {"ok": True})
        else:
            self._send_v1_error(409, "not_running",
                                "Nessun audit in corso da "
                                "annullare.")

    def _post_v1_token(self) -> None:
        # Gestione dei token SOLO via sessione cookie: un token
        # non puo' crearne o revocarne altri.
        user = self._session_user()
        if user is None:
            self._send_v1_error(401, "unauthorized",
                                "Accesso richiesto (sessione).")
            return
        raw = self._read_json()
        if raw is None:
            return
        label = str(raw.get("label", "")).strip()[:60]
        token_id, token = get_store().create_api_token(
            int(user["id"]), label)
        # il token in chiaro esiste solo in questa risposta
        self._send_json(201, {"ok": True, "id": token_id,
                              "label": label, "token": token})

    def _get_v1_tokens(self) -> None:
        user = self._session_user()
        if user is None:
            self._send_v1_error(401, "unauthorized",
                                "Accesso richiesto (sessione).")
            return
        self._send_json(200, {
            "tokens": get_store().list_api_tokens(
                int(user["id"]))})

    def _delete_v1_token(self, path: str) -> None:
        user = self._session_user()
        if user is None:
            self._send_v1_error(401, "unauthorized",
                                "Accesso richiesto (sessione).")
            return
        resto = path[len("/api/v1/tokens/"):]
        try:
            token_id = int(resto)
        except (TypeError, ValueError):
            self._send_v1_error(400, "invalid_id",
                                "Id del token non valido.",
                                {"id": resto})
            return
        if get_store().revoke_api_token(int(user["id"]), token_id):
            self._send_json(200, {"ok": True})
        else:
            self._send_v1_error(404, "not_found",
                                "Token non trovato.",
                                {"id": token_id})

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
        user = self._auth_user()
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

    def _audit_error(self, v1: bool, status: int, code: str,
                     message: str,
                     params: Optional[Dict[str, object]] = None
                     ) -> None:
        """Stesso handler, due stili: le rotte legacy conservano
        {"error"} (piu' retry_in_s sul 429), le /api/v1 usano
        l'oggetto uniforme."""
        if v1:
            self._send_v1_error(status, code, message, params)
            return
        corpo: Dict[str, object] = {"error": message}
        if params and "retry_in_s" in params:
            corpo["retry_in_s"] = params["retry_in_s"]
        self._send_json(status, corpo)

    def _post_audit(self, v1: bool = False) -> None:
        global JOB
        user = self._auth_user()
        if user is None:
            self._audit_error(v1, 401, "unauthorized",
                              "Per avviare un check devi "
                              "registrarti o accedere.")
            return
        raw = self._read_json()
        if raw is None:
            return
        config, err = validate_config(raw)
        if config is None:
            self._audit_error(v1, 400, "invalid_config", err)
            return
        wait_s = int(user["next_check_in_s"])
        if wait_s > 0:
            self._audit_error(
                v1, 429, "hourly_slot",
                "Hai gia' effettuato un check nell'ultima ora: "
                "potrai avviarne un altro fra %d minuti."
                % max(1, wait_s // 60),
                {"retry_in_s": wait_s})
            return
        with JOBS_LOCK:
            if _running_jobs() >= AUDIT_CONCURRENCY:
                self._audit_error(v1, 409, "busy",
                                  "Un audit e' gia' in corso: "
                                  "attendi che finisca.")
                return
            job = Job(job_id=secrets.token_hex(8))
            job.start(config, user_id=int(user["id"]))
            JOBS[job.job_id] = job
            _prune_jobs()
            JOB = job
        get_store().record_check(int(user["id"]))
        threading.Thread(target=job.run, daemon=True).start()
        self._send_json(202, {"ok": True, "id": job.job_id})

    def log_message(self, fmt: str, *args: object) -> None:
        pass  # niente rumore in console: il log utile e' nella GUI
