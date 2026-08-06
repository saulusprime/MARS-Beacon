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
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple
import re

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
# la 1.1.0 aggiunge la parita' CLI-API su POST /api/audit (lang,
# soglie, queries_gsc, fail_under). E' il numero che compare in
# info.version della spec.
API_CONTRACT_VERSION = "1.1.0"


# Nome del cookie di sessione: fa parte del contratto (schema di
# sicurezza nella spec). mars_gui dichiara lo stesso valore; un
# test ne verifica la coerenza.
SESSION_COOKIE_NAME = "mars_session"


# Modalita' di autenticazione delle rotte.
AUTH_NONE = "none"


AUTH_SESSION = "session"


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
    "required": ["state", "log", "error", "config", "summary",
                 "findings", "remediation", "rrf", "competitive"],
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
        request_schema={
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
        },
        responses={
            202: {"description": "Audit avviato.",
                  "schema": OK_SCHEMA},
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
        responses={
            200: {"description": "Righe dello storico.",
                  "schema": {
                      "type": "object",
                      "properties": {
                          "runs": {"type": "array",
                                   "items": RUN_SCHEMA}},
                      "required": ["runs"],
                      "additionalProperties": False}},
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
        "components": {"securitySchemes": {"cookieSession": {
            "type": "apiKey", "in": "cookie",
            "name": SESSION_COOKIE_NAME,
            "description": "Cookie di sessione emesso da "
                           "/api/register e /api/login (HttpOnly, "
                           "SameSite=Strict).",
        }}},
    }
