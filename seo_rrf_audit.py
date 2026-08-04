#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Audit SEO e RRF (Reciprocal Rank Fusion) di un sito web.

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
    python3 seo_rrf_audit.py https://www.example.com
    python3 seo_rrf_audit.py https://example.com --max-pages 40 \\
        --format html --output report.html
    python3 seo_rrf_audit.py https://example.com --queries q.txt \\
        --embeddings sentence-transformers/all-MiniLM-L6-v2

Licenza: MIT.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import datetime
import gzip
import hashlib
import html
import importlib.util
import io
import json
import math
import logging
import os
import re
import sys
import threading
import time
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import asdict, dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

try:
    import requests
except ImportError:  # pragma: no cover
    sys.exit("Manca 'requests'. Installa: pip install requests")

try:
    from bs4 import BeautifulSoup
except ImportError:  # pragma: no cover
    sys.exit("Manca 'beautifulsoup4'. Installa: pip install "
             "beautifulsoup4 lxml")


__version__ = "1.30.0"

# La pagina indicata nello user agent spiega chi e' il bot e come
# escluderlo; sovrascrivibile con --user-agent.
USER_AGENT = (
    "Mozilla/5.0 (compatible; SeoRrfAudit/%s; "
    "+https://github.com/saulusprime/SEO-RRF)" % __version__
)

# Token con cui lo strumento compare nel robots.txt (gruppo
# "User-agent: SeoRrfAudit"); usato da --respect-robots.
USER_AGENT_TOKEN = "SeoRrfAudit"

# Modello multilingue usato quando sentence-transformers e'
# installato e l'utente non ne indica uno con --embeddings.
# "--embeddings none" forza comunque il proxy char-tfidf.
DEFAULT_EMBEDDINGS_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"

# Content-Type analizzabili: per tutto il resto (PDF, immagini,
# archivi...) il corpo non viene scaricato affatto — lo stato e gli
# header bastano ai rilievi. "gzip" copre le sitemap .xml.gz.
ANALYZABLE_CTYPES = ("html", "xml", "text/", "json", "gzip")

# Tetto al corpo di ogni risposta HTTP. L'intero corpo resta in RAM
# durante il parsing, e il conteggio avviene dopo la decompressione:
# protegge anche da corpi compressi che si espandono molto.
# Configurabile con --max-body.
DEFAULT_MAX_BODY_MB = 10

# Errori transitori: stati HTTP che meritano un nuovo tentativo.
# 404/403 e simili NON sono qui: sono segnali diagnostici dell'audit.
RETRY_STATUS: Tuple[int, ...] = (429, 500, 502, 503, 504)
DEFAULT_RETRIES = 2

# Richieste in parallelo durante la scansione delle pagine. Il rate
# limit non cambia: il throttle distanzia gli AVVII delle richieste
# di --delay anche fra thread; i worker sovrappongono solo le attese
# di rete. Configurabile con --workers (1 = seriale).
DEFAULT_WORKERS = 4
MAX_WORKERS = 16

# Politica sul robots.txt del sito auditato. Predefinito: i Disallow
# rivolti al nostro agente vengono RISPETTATI. "own" dichiara il sito
# di propria titolarita' (audit completo; i concorrenti restano
# protetti); "force" ignora i Disallow ovunque e richiede
# l'accettazione esplicita di responsabilita' (--ignore-robots accetto).
ROBOTS_RESPECT = "respect"
ROBOTS_OWN = "own"
ROBOTS_FORCE = "force"
ROBOTS_MODES = (ROBOTS_RESPECT, ROBOTS_OWN, ROBOTS_FORCE)
IGNORE_ROBOTS_ACK = "accetto"

# Rendering JavaScript (facoltativo, richiede Playwright).
# off = mai; auto = solo pagine con contenuto reso lato client;
# always = tutte le pagine analizzabili.
RENDER_OFF = "off"
RENDER_AUTO = "auto"
RENDER_ALWAYS = "always"
RENDER_MODES = (RENDER_OFF, RENDER_AUTO, RENDER_ALWAYS)
RENDER_SETTLE_MS = 2500
# Browser di sistema tentati se Playwright non ha un Chromium proprio.
CHROME_PATHS = (
    "/usr/bin/google-chrome",
    "/usr/bin/google-chrome-stable",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
    "/snap/bin/chromium",
)
RETRY_BACKOFF_S = 0.5   # attese: 0.5s, 1s, 2s... con tetto sotto
RETRY_MAX_WAIT_S = 8.0

# Crawler dei principali motori/assistenti IA. Fonte: documentazione
# pubblica dei rispettivi operatori.
# Token robots.txt degli agenti IA, tutti con documentazione
# ufficiale del vendor (verifica: 2026-08). Coprono training,
# ricerca/citazioni e fetch su richiesta utente:
#   OpenAI      developers.openai.com/api/docs/bots
#   Anthropic   support.claude.com (articolo 8896518; Claude-Web
#               e' deprecato e non compare piu')
#   Perplexity  docs.perplexity.ai/guides/bots
#   Google      developers.google.com/search/docs/crawling-indexing/
#               google-common-crawlers (Google-Extended: opt-out
#               training e grounding Gemini, non tocca la Search)
#   Meta        developers.facebook.com/docs/sharing/webmasters/
#               web-crawlers
#   Amazon      developer.amazon.com/amazonbot
#   Apple       support.apple.com/en-us/119829
#   CommonCrawl commoncrawl.org/ccbot
#   Mistral     docs.mistral.ai/robots/
# Bingbot NON e' qui: e' il crawler di ricerca classico di Bing
# (bloccarlo toglie il sito da Bing/Copilot); l'opt-out IA di
# Microsoft passa dai meta tag noarchive/nocache, non da un token.
# Bytespider (ByteDance) e' escluso: nessuna doc ufficiale e non
# rispetta robots.txt.
AI_CRAWLERS: Tuple[str, ...] = (
    "GPTBot",
    "OAI-SearchBot",
    "ChatGPT-User",
    "ClaudeBot",
    "Claude-SearchBot",
    "Claude-User",
    "PerplexityBot",
    "Perplexity-User",
    "Google-Extended",
    "Meta-ExternalAgent",
    "Amazonbot",
    "Applebot-Extended",
    "CCBot",
    "MistralAI-User",
)

SEV_CRITICAL = "critical"
SEV_WARNING = "warning"
SEV_OK = "ok"
SEV_INFO = "info"

_SEVERITY_FACTOR: Dict[str, float] = {
    SEV_OK: 1.0,
    SEV_WARNING: 0.5,
    SEV_CRITICAL: 0.0,
}

AREA_TECH = "Tecnica"
AREA_LEX = "Lessicale (BM25)"
AREA_SEM = "Semantica (vettoriale)"
AREA_SD = "Dati strutturati"
AREA_RRF = "Simulazione RRF"

# Profili euristici di citabilita' per assistente IA ("lenti per
# modello"). ATTENZIONE: le preferenze attribuite a ciascun
# assistente sono euristiche dichiarate, NON comportamento
# documentato dai vendor; i punteggi sono stime comparative ricavate
# dalle metriche dell'audit. Ogni profilo ripesa i punteggi di area
# (piu' la profondita' editoriale media) secondo cio' che
# plausibilmente conta di piu' per quel tipo di motore generativo.
CITABILITY_DEPTH = "Profondita' editoriale"
DEPTH_TARGET_WORDS = 900  # stesso target di surface_math (4 chunk)

CITABILITY_PROFILES = (
    ("claude", "Claude (Anthropic)",
     "contenuto estraibile, strutturato e autoconsistente",
     {AREA_SEM: 0.40, AREA_LEX: 0.25, AREA_TECH: 0.20,
      AREA_SD: 0.15}),
    ("chatgpt", "ChatGPT / Perplexity",
     "consenso fra piu' indici (RRF) e segnali lessicali",
     {AREA_RRF: 0.45, AREA_LEX: 0.25, AREA_TECH: 0.15,
      AREA_SEM: 0.15}),
    ("qwen", "Qwen (Alibaba)",
     "markup semantico e dati strutturati",
     {AREA_SD: 0.40, AREA_TECH: 0.25, AREA_SEM: 0.20,
      AREA_LEX: 0.15}),
    ("kimi", "Kimi (Moonshot AI)",
     "profondita' editoriale e completezza dell'argomento",
     {CITABILITY_DEPTH: 0.35, AREA_SEM: 0.30, AREA_SD: 0.20,
      AREA_LEX: 0.15}),
)

# Pesi dei profili nell'indice composito, per mercato di riferimento.
MARKET_WEIGHTS = {
    "occidentale": {"claude": 0.30, "chatgpt": 0.50,
                    "qwen": 0.10, "kimi": 0.10},
    "globale": {"claude": 0.25, "chatgpt": 0.25,
                "qwen": 0.25, "kimi": 0.25},
    "orientale": {"claude": 0.10, "chatgpt": 0.20,
                  "qwen": 0.35, "kimi": 0.35},
}
DEFAULT_MARKET = "occidentale"

CITABILITY_NOTE = (
    "Stime euristiche ricavate dalle metriche di questo audit: le "
    "preferenze attribuite a ciascun assistente non sono "
    "comportamento documentato dai vendor.")

# Sotto questo guadagno (punti profilo) un profilo non conta come
# "colpito" da un rilievo; un rilievo e' trasversale se colpisce
# almeno due profili.
CROSS_GAIN_MIN = 1.0

# Giudizio LLM sulla citabilita' dei passaggi migliori ("LLM as
# judge"). Attivo di default in modalita' "auto": parte da solo se
# l'SDK anthropic e la chiave ANTHROPIC_API_KEY sono presenti,
# altrimenti viene saltato e l'audit resta interamente offline.
# Una sola richiesta API per audit (campione di JUDGE_MAX_CHUNKS
# passaggi), con i costi a carico della chiave configurata.
JUDGE_AUTO = "auto"
JUDGE_ON = "on"
JUDGE_OFF = "off"
JUDGE_MODES = (JUDGE_AUTO, JUDGE_ON, JUDGE_OFF)
DEFAULT_JUDGE = JUDGE_AUTO
JUDGE_MODEL = "claude-opus-5"
JUDGE_MAX_CHUNKS = 5
JUDGE_CHUNK_CHARS = 1200
JUDGE_MAX_TOKENS = 1000
JUDGE_NOTE = (
    "Parere di un modello su un campione dei passaggi migliori: "
    "utile per tarare le stime euristiche, ma non riproducibile "
    "ne' garanzia di citazione.")

# Stopword italiane e inglesi. Lista minima e volutamente conservativa.
STOPWORDS: Set[str] = set("""
a ad agli ai al alla alle allo anche c che chi ci coi col come con cui
da dagli dai dal dalla dalle dallo degli dei del della delle dello di
dov dove e ed gli ha hai hanno ho i il in io la le lei li lo loro ma
me mi ne negli nei nel nella nelle nello noi non nostro o od ogni
per piu piu' quale quali quanto quel quella quelle quelli quello
questa queste questi questo qui sei si sia siamo siete solo sono su
sugli sui sul sulla sulle sullo suo sua suoi sue ti tra tu tuo tuoi
tutti tutto un una uno vi voi vostro
a about above after again against all am an and any are as at be
because been before being below between both but by can cannot could
did do does doing down during each few for from further had has have
having he her here hers him his how i if in into is it its itself me
more most my no nor not of off on once only or other our out over own
same she should so some such than that the their them then there
these they this those through to too under until up very was we were
what when where which while who whom why will with you your
au aux avec ce ces cette dans des donc du elle elles en est et été
être il ils je leur leurs lui mais même mes moi mon nos notre nous
où par pas plus pour qu que qui sa se ses son sont sur tes toi ton
une vos votre vous comme aussi bien tout tous toute toutes très sans
sous entre alors avant après chez encore toujours quand pourquoi
combien quel quelle quels quelles
aber alle allem allen aller alles als also am an ander andere auch
auf aus bei bin bis bist da damit dann das dass dein deine dem den
denn der des dessen dich die dies diese diesem diesen dieser dieses
doch dort du durch ein eine einem einen einer eines er es für habe
haben hat hatte hier ich ihr ihre im ist ja jede jedem jeden jeder
jedes kann kein keine können machen man mein meine mit muss nach
nicht nichts noch nun nur ob oder ohne sehr sein seine sich sie sind
so über um und uns unser unter vom von vor war waren warum was wenn
werden wie wieder will wir wird wo zu zum zur
al algo algunas algunos ante antes contra cual cuando desde donde
dos ella ellas ellos era eran esa esas ese eso esos esta estas este
esto estos fue fueron había han hasta hay las les los más mis mucho
muy nada ni nosotros nuestra nuestro os otra otras otro otros para
pero poco porque quien quienes qué ser sin sobre sois somos son soy
sus también tiene tienen todo todos tus unos usted vosotros ya yo
cómo cuánto cuál dónde
""".split())

QUESTION_STARTERS: Tuple[str, ...] = (
    "cosa", "che cos", "come", "quando", "perche", "perche'", "quanto",
    "quanti", "quante", "quale", "quali", "chi", "dove", "conviene",
    "what", "how", "when", "why", "which", "who", "where", "is", "are",
    "can", "does", "do",
    "comment", "pourquoi", "combien", "quel", "quelle", "quels",
    "quelles", "qu'est", "est-ce", "où",
    "wie", "was", "warum", "wann", "welche", "welcher", "welches",
    "wer", "wo", "ist", "sind", "kann",
    "cómo", "cuándo", "cuánto", "cuánta", "cuántos", "cuál",
    "cuáles", "quién", "dónde", "qué", "que es", "por que",
    "por qué", "puede",
)

DEFINITION_RE = re.compile(
    r"\b(?:e'|è)\s+(?:un|una|uno|il|la|lo|l')\b"
    r"|\bsi\s+tratta\s+di\b"
    r"|\bconsiste\s+(?:in|nel|nella)\b"
    r"|\bsi\s+definisce\b"
    r"|\bsignifica\b"
    r"|\bis\s+a\b|\brefers\s+to\b|\bmeans\b"
    r"|\best\s+(?:un|une|le|la|l')\b"
    r"|\bil\s+s'agit\s+de\b|\bconsiste\s+(?:à|en)\b"
    r"|\bsignifie\b|\bdésigne\b"
    r"|\bist\s+(?:ein|eine|der|die|das)\b"
    r"|\bbezeichnet\b|\bbedeutet\b"
    r"|\bversteht\s+man\b|\bhandelt\s+es\s+sich\s+um\b"
    r"|\bes\s+(?:un|una|el|la)\b|\bse\s+trata\s+de\b"
    r"|\bconsiste\s+en\b|\bse\s+define\s+como\b",
    re.IGNORECASE,
)

# Aperture "a risposta diretta" oltre alle definizioni: si'/no
# secco, sintesi dichiarata, passo numerato. Con DEFINITION_RE in
# apertura alimentano la metrica di estraibilita' diretta.
DIRECT_ANSWER_RE = re.compile(
    r"^(?:s[iì]|no|yes|oui|non|ja|nein),\s"
    r"|^(?:in\s+sintesi|in\s+breve|la\s+risposta\s+(?:e'|è)"
    r"|in\s+short|in\s+summary|the\s+answer\s+is"
    r"|en\s+r[ée]sum[ée]|en\s+bref|kurz\s+gesagt|zusammenfassend"
    r"|en\s+resumen|en\s+pocas\s+palabras)\b"
    r"|^\d+[.)]\s",
    re.IGNORECASE,
)

# Estraibilita' diretta: un paragrafo di 20-120 parole che apre con
# la risposta e' citabile da un assistente cosi' com'e'. Soglie di
# prassi (dichiarate nel referto), non standard normativi.
EXTRACT_MIN_WORDS = 20
EXTRACT_MAX_WORDS = 120
EXTRACT_GOOD_SHARE = 0.20

# Filler di marketing: frasi che occupano spazio senza dire nulla
# di estraibile. Un assistente non citera' mai "qualita' e
# professionalita' al tuo servizio". Euristica dichiarata, cinque
# lingue; soglie di prassi in _audit_filler.
FILLER_RE = re.compile(
    r"leader\s+(?:di\s+mercato|del\s+settore)"
    r"|soluzioni\s+innovative|a\s+360\s+gradi|scopri\s+di\s+pi[uù]"
    r"|clicca\s+qui|leggi\s+tutto|contattaci\s+per"
    r"|richiedi\s+un\s+preventivo|iscriviti\s+alla\s+newsletter"
    r"|seguici\s+su|senza\s+impegno|su\s+misura\s+per\s+te"
    r"|qualit[aà]\s+e\s+professionalit[aà]|al\s+(?:tuo|vostro)\s+"
    r"servizio|punto\s+di\s+riferimento|vasta\s+gamma"
    r"|market\s+leader|industry[- ]leading|cutting[- ]edge"
    r"|best\s+in\s+class|state\s+of\s+the\s+art|learn\s+more"
    r"|click\s+here|read\s+more|contact\s+us\s+for"
    r"|request\s+a\s+quote|sign\s+up\s+for|follow\s+us"
    r"|one[- ]stop[- ]shop"
    r"|leader\s+du\s+march[ée]|[aà]\s+la\s+pointe"
    r"|en\s+savoir\s+plus|cliquez\s+ici|contactez[- ]nous"
    r"|demandez\s+un\s+devis|suivez[- ]nous|large\s+gamme"
    r"|marktf[üu]hrer|ma[ßs]geschneidert|erfahren\s+sie\s+mehr"
    r"|klicken\s+sie\s+hier|kontaktieren\s+sie\s+uns"
    r"|jetzt\s+anfragen|folgen\s+sie\s+uns|breites\s+sortiment"
    r"|l[ií]der\s+del\s+mercado|descubre\s+m[aá]s"
    r"|haz\s+clic\s+aqu[ií]|cont[aá]ctanos"
    r"|solicita\s+un\s+presupuesto|s[ií]guenos|amplia\s+gama",
    re.IGNORECASE,
)
FILLER_MIN_HITS = 3       # sotto, non e' saturazione
FILLER_DENSITY = 0.01     # una formula ogni 100 parole

# Formule clickbait in title e heading: engagement bait che i
# motori generativi non premiano — un titolo informativo e' anche
# piu' estraibile. Euristica dichiarata, cinque lingue.
CLICKBAIT_RE = re.compile(
    r"non\s+crederai|incredibile|scioccante|sconvolgente"
    r"|devi\s+assolutamente|da\s+non\s+perdere|imperdibile"
    r"|il\s+segreto\s+(?:di|del|della|dello|dei|degli|delle|per)"
    r"|i\s+segreti\s+(?:di|del|della|dello|dei|degli|delle|per)"
    r"|la\s+verit[aà]\s+su|quello\s+che\s+non\s+ti\s+dicono"
    r"|\d+\s+motivi\s+per"
    r"|you\s+won'?t\s+believe|shocking|unbelievable"
    r"|mind[- ]blowing|the\s+secret\s+(?:of|to)"
    r"|the\s+truth\s+about|\d+\s+reasons\s+why"
    r"|what\s+they\s+don'?t\s+tell\s+you"
    r"|vous\s+ne\s+croirez\s+(?:pas|jamais)|incroyable|choquant"
    r"|le\s+secret\s+(?:de|du|des|pour)|la\s+v[ée]rit[ée]\s+sur"
    r"|[aà]\s+ne\s+pas\s+manquer|\d+\s+raisons"
    r"|du\s+wirst\s+nicht\s+glauben|unglaublich|schockierend"
    r"|das\s+geheimnis|die\s+wahrheit\s+[üu]ber"
    r"|\d+\s+gr[üu]nde,?\s+warum"
    r"|no\s+creer[aá]s|incre[ií]ble|impactante"
    r"|el\s+secreto\s+(?:de|del|para)|la\s+verdad\s+sobre"
    r"|\d+\s+razones\s+por|lo\s+que\s+no\s+te\s+cuentan"
    r"|!{2,}",
    re.IGNORECASE,
)

EXAMPLE_RE = re.compile(
    r"\b(?:ad\s+esempio|per\s+esempio|esempio|es\.|caso\s+studio"
    r"|case\s+study|for\s+example|e\.g\."
    r"|par\s+exemple|p\.\s?ex\.|exemple"
    r"|zum\s+beispiel|z\.\s?b\.|beispielsweise"
    r"|por\s+ejemplo|p\.\s?ej\.|ejemplo)\b",
    re.IGNORECASE,
)

# Aperture anaforiche: un chunk che inizia cosi' non e'
# autoconsistente. In tedesco i pronomi nudi es/er/sie restano
# fuori apposta: "Es gibt..." e' un espletivo comunissimo, non
# un'anafora.
ANAPHORA_RE = re.compile(
    r"^(?:questo|questa|questi|queste|cio'|ciò|esso|essa|essi|esse"
    r"|tale|tali|lo\s+stesso|la\s+stessa|quest'|it|this|that|these"
    r"|those|they|he|she|such"
    r"|cela|celui|celle|celles|ceux|ce\s+dernier"
    r"|cette\s+derni[èe]re"
    r"|dies|diese|dieser|dieses|diesem|diesen|derselbe|dieselbe"
    r"|solche|solcher|solches"
    r"|esto|esta|este|estos|estas|eso|esa|ese|esos|esas|ello"
    r"|dicho|dicha|dichos|dichas|el\s+mismo|la\s+misma)\b",
    re.IGNORECASE,
)

FAQ_HINT_RE = re.compile(
    r"\b(?:faq|domande\s+frequenti|domande\s+e\s+risposte"
    r"|frequently\s+asked"
    r"|foire\s+aux\s+questions|questions\s+fr[ée]quentes"
    r"|h[äa]ufig\s+gestellte\s+fragen|h[äa]ufige\s+fragen"
    r"|preguntas\s+frecuentes|preguntas\s+y\s+respuestas)\b",
    re.IGNORECASE,
)

# Ciclo di vita dell'argomento (da Features.md): le sei sezioni
# che rendono completa una trattazione agli occhi dei motori
# generativi. Copertura cercata in title e heading, cinque lingue.
LIFECYCLE_SECTIONS: Tuple[Tuple[str, "re.Pattern[str]"], ...] = (
    ("definizione", re.compile(
        r"cos'?\s?[eè]|che\s+cos|definizion|cosa\s+significa"
        r"|introduzion|what\s+is|definition|introduction"
        r"|qu'?est[- ]ce|d[ée]finition|was\s+ist|qu[ée]\s+es"
        r"|definici[oó]n", re.IGNORECASE)),
    ("storia", re.compile(
        r"storia|origin|evoluzion|history|evolution|histoire"
        r"|geschichte|ursprung|historia|evoluci[oó]n",
        re.IGNORECASE)),
    ("casi d'uso", re.compile(
        r"casi\s+d'?uso|applicazion|a\s+cosa\s+serve"
        r"|quando\s+serve|come\s+si\s+usa|use\s+case|application"
        r"|how\s+to\s+use|cas\s+d'usage|utilisation|anwendung"
        r"|einsatz|casos\s+de\s+uso|aplicacion|\busos\b",
        re.IGNORECASE)),
    ("limiti", re.compile(
        r"limit|controindicazion|svantagg|criticit|rischi"
        r"|drawback|\brisk|side\s+effect|contre[- ]indication"
        r"|inconv[ée]nient|grenzen|nachteil|risiken"
        r"|kontraindikation|l[ií]mite|limitacion|contraindicacion"
        r"|riesgo|desventaj", re.IGNORECASE)),
    ("faq", re.compile(
        r"\bfaq\b|domande\s+frequenti|domande\s+e\s+risposte"
        r"|frequently\s+asked|foire\s+aux\s+questions"
        r"|questions\s+fr[ée]quentes|h[äa]ufig\s+gestellte"
        r"|h[äa]ufige\s+fragen|preguntas\s+frecuentes",
        re.IGNORECASE)),
    ("prospettive", re.compile(
        r"prospettiv|futuro|tendenz|future|outlook|\btrend"
        r"|avenir|perspective|tendance|zukunft|ausblick"
        r"|perspectiva|tendencia", re.IGNORECASE)),
)

# Suggerimenti di heading per le sezioni mancanti del ciclo di vita.
LIFECYCLE_HINTS: Dict[str, str] = {
    "definizione": "Cos'e' <argomento>",
    "storia": "Storia e origini di <argomento>",
    "casi d'uso": "Quando serve <argomento>: casi d'uso",
    "limiti": "Limiti e controindicazioni",
    "faq": "Domande frequenti",
    "prospettive": "Prospettive e tendenze",
}

# Varieta' degli anchor interni (da Features.md): dopo la
# deduplica delle coppie (testo, destinazione) — il menu ripetuto
# su ogni pagina conta una volta — un profilo sano ha un testo per
# destinazione. Lo stesso testo verso destinazioni diverse e'
# ambiguita' ("leggi" -> 5 pagine). Soglie di prassi.
ANCHOR_MIN_PAIRS = 10
ANCHOR_VARIETY_GOOD = 0.8

# HTML semantico (da Features.md): i chunker dei motori generativi
# segmentano sui tag di sezionamento; una pagina di soli <div> e'
# piu' difficile da spezzare in blocchi coerenti. Soglie di prassi
# in _audit_semantic_html.
SEMANTIC_TAGS: Tuple[str, ...] = (
    "article", "section", "main", "aside", "details", "summary",
    "figure", "figcaption", "header", "footer", "nav",
)
DIVITIS_RATIO = 0.5       # oltre meta' <div> = divitis
SEMANTIC_MIN_TYPES = 2    # tipi di tag semantici attesi per pagina
SEMANTIC_MIN_ELEMENTS = 30  # sotto, la pagina e' troppo piccola

# Freschezza dei contenuti (da Features.md): eta' dell'ultimo
# aggiornamento dichiarato. Soglie di prassi a uno e due anni.
FRESH_WARN_DAYS = 365
FRESH_STALE_DAYS = 730

# Riferimenti bibliografici (da Features.md): sezione fonti negli
# heading e citazioni accademiche nel testo. Completano i segnali
# E-E-A-T: dare agli assistenti qualcosa da verificare.
REFERENCES_HEADING_RE = re.compile(
    r"riferiment|bibliograf|sitograf|\bfonti\b|references"
    r"|bibliography|\bsources\b|r[ée]f[ée]rences|quellen"
    r"|literaturverzeichnis|\bliteratur\b|referencias|fuentes",
    re.IGNORECASE,
)
CITATION_RE = re.compile(
    r"\[\d{1,3}\]"
    r"|\([A-ZÀ-Ý][a-zà-ÿ]+(?:\s+et\s+al\.?)?,?\s+(?:19|20)\d{2}\)",
)
CITATIONS_GOOD = 3  # soglia di prassi, dichiarata nel referto

# Pagine segnaposto lasciate dai CMS: rumore puro per il recupero.
PLACEHOLDER_SLUGS: Tuple[str, ...] = (
    "sample-page", "pagina-di-esempio", "hello-world", "lorem-ipsum",
    "test-page", "pagina-test", "coming-soon", "elementor",
)

PLACEHOLDER_TEXT_RE = re.compile(
    r"this is an example page|questa (?:e'|è) una pagina di esempio"
    r"|welcome to wordpress|lorem ipsum dolor",
    re.IGNORECASE,
)

# Anchor text generiche: non dicono nulla sul contenuto di arrivo.
GENERIC_ANCHOR_RE = re.compile(
    r"^(?:clicca qui|click here|qui|link|vai|continua|leggi tutto"
    r"|leggi di pi[uù]['’]?|read more|scopri di pi[uù]['’]?"
    r"|maggiori informazioni|per saperne di pi[uù]['’]?)\.?$",
    re.IGNORECASE,
)

# Slug che segnalano pagine di fiducia (E-E-A-T): chi siamo, contatti.
ABOUT_SLUGS: Tuple[str, ...] = (
    "chi-siamo", "chisiamo", "about", "about-us", "azienda",
    "la-nostra-storia", "il-team", "team", "storia",
)
CONTACT_SLUGS: Tuple[str, ...] = (
    "contatti", "contatto", "contact", "contacts", "contact-us",
    "dove-siamo",
)
EMAIL_RE = re.compile(
    r"\b[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}\b")

# Proprieta' minime dei tipi JSON-LD piu' comuni: senza queste il
# tipo non e' eleggibile per i risultati arricchiti (riferimento:
# schema.org e linee guida Google sui dati strutturati).
JSONLD_REQUIRED: Dict[str, Tuple[str, ...]] = {
    "Organization": ("name", "url"),
    "LocalBusiness": ("name", "address", "telephone"),
    "ProfessionalService": ("name", "address", "telephone"),
    "MedicalBusiness": ("name", "address", "telephone"),
    "MedicalClinic": ("name", "address", "telephone"),
    "FAQPage": ("mainEntity",),
    "BreadcrumbList": ("itemListElement",),
    "WebSite": ("name", "url"),
    "Article": ("headline", "datePublished", "author"),
    "BlogPosting": ("headline", "datePublished", "author"),
    "NewsArticle": ("headline", "datePublished", "author"),
    "Service": ("name", "provider"),
    "Person": ("name",),
    "Product": ("name",),
    "Review": ("author", "reviewRating"),
    "AggregateRating": ("ratingValue",),
    "VideoObject": ("name", "thumbnailUrl", "uploadDate"),
    "Event": ("name", "startDate", "location"),
    "Recipe": ("name", "image"),
    "HowTo": ("name", "step"),
    "JobPosting": ("title", "datePosted", "hiringOrganization",
                   "jobLocation"),
    "Course": ("name", "description", "provider"),
}

# Chiavi con date ISO 8601 (YYYY-MM-DD, eventualmente con orario).
JSONLD_DATE_KEYS: Tuple[str, ...] = (
    "datePublished", "dateModified", "uploadDate", "startDate",
    "endDate", "datePosted", "validThrough", "priceValidUntil",
)
JSONLD_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}([T ].+)?$")

# Chiavi con URL di media: devono essere assoluti (http/https).
JSONLD_URL_KEYS: Tuple[str, ...] = (
    "thumbnailUrl", "contentUrl", "embedUrl", "image", "logo",
)

# Prezzo secondo schema.org/Google: numero con punto decimale, senza
# simboli di valuta; la valuta va in priceCurrency (ISO 4217).
JSONLD_PRICE_RE = re.compile(r"^\d+(\.\d+)?$")
JSONLD_CURRENCY_RE = re.compile(r"^[A-Za-z]{3}$")

# Snippet riusati negli esempi di remediation.
EX_LOCALBUSINESS = (
    "<script type=\"application/ld+json\">\n"
    "{\"@context\": \"https://schema.org\","
    " \"@type\": \"LocalBusiness\",\n"
    " \"name\": \"Centro Esempio\","
    " \"url\": \"https://esempio.it/\",\n"
    " \"telephone\": \"+39 0521 123456\",\n"
    " \"address\": {\"@type\": \"PostalAddress\",\n"
    "  \"streetAddress\": \"Via Roma 1\","
    " \"addressLocality\": \"Parma\",\n"
    "  \"postalCode\": \"43121\", \"addressCountry\": \"IT\"}}\n"
    "</script>")

EX_FAQPAGE = (
    "<script type=\"application/ld+json\">\n"
    "{\"@context\": \"https://schema.org\","
    " \"@type\": \"FAQPage\", \"mainEntity\": [\n"
    " {\"@type\": \"Question\","
    " \"name\": \"Quanto costa una seduta?\",\n"
    "  \"acceptedAnswer\": {\"@type\": \"Answer\",\n"
    "   \"text\": \"Da 40 a 80 euro, in base a durata e zona "
    "trattata.\"}}]}\n"
    "</script>")

# Soft-404: pagine che rispondono 200 ma il cui contenuto dice
# "non trovato". Il segnale forte e' nel title/H1; nel corpo vale
# solo su pagine molto corte (vedi audit_technical).
SOFT_404_RE = re.compile(
    r"pagina non (?:e'|è|e|é)?\s*(?:stata\s+)?trovata"
    r"|contenuto non trovato|nessun risultato"
    r"|page (?:was\s+)?not found|nothing (?:was\s+)?found"
    r"|error(?:e)?\s*404|\b404\b",
    re.IGNORECASE,
)
SOFT_404_MAX_WORDS = 120

TOKEN_RE = re.compile(r"[a-zA-Zà-ÿÀ-Ÿ0-9][a-zA-Zà-ÿÀ-Ÿ0-9'’\-]*")

# Soglie di riferimento. Valori di prassi SEO, non standard normativi.
TITLE_MIN, TITLE_MAX = 30, 65
DESC_MIN, DESC_MAX = 110, 165
THIN_CONTENT_WORDS = 300
GOOD_CONTENT_WORDS = 700


def tokenize(text: str, keep_stopwords: bool = False) -> List[str]:
    """Tokenizza in minuscolo, opzionalmente senza stopword."""
    tokens = [m.group(0).lower() for m in TOKEN_RE.finditer(text)]
    if keep_stopwords:
        return tokens
    return [t for t in tokens if t not in STOPWORDS and len(t) > 2]


def char_ngrams(text: str, size: int = 4) -> List[str]:
    """N-grammi di caratteri, usati dal recuperatore di ripiego."""
    norm = re.sub(r"\s+", " ", text.lower().strip())
    if len(norm) < size:
        return [norm] if norm else []
    return [norm[i:i + size] for i in range(len(norm) - size + 1)]


def norm_url(url: str) -> str:
    """Normalizza un URL: rimuove fragment e slash finale ridondante."""
    parsed = urlparse(url)
    path = parsed.path or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path[:-1]
    return "%s://%s%s%s" % (
        parsed.scheme, parsed.netloc, path,
        "?" + parsed.query if parsed.query else "",
    )


def available_ram_mb() -> Optional[float]:
    """RAM disponibile in MB, dove il sistema la espone (POSIX)."""
    try:
        page = os.sysconf("SC_PAGE_SIZE")
        pages = os.sysconf("SC_AVPHYS_PAGES")
    except (AttributeError, ValueError, OSError):
        return None
    if page <= 0 or pages <= 0:
        return None
    return page * pages / 1048576.0


# --------------------------------------------------------------------
# Modelli di dato
# --------------------------------------------------------------------

class AuditCancelled(Exception):
    """Audit interrotto dall'utente tramite il flag di stop."""


@dataclass
class Finding:
    """Singolo rilievo dell'audit.

    ``example`` e' un esempio concreto di correzione (snippet di
    markup, righe di robots.txt, testo prima/dopo): alimenta il
    piano di remediation dei referti.
    """

    area: str
    severity: str
    title: str
    detail: str = ""
    fix: str = ""
    url: str = ""
    weight: float = 1.0
    example: str = ""

    def as_dict(self) -> Dict[str, object]:
        return asdict(self)


EFFORT_MINUTES = "minuti"
EFFORT_HOURS = "ore"
EFFORT_DAYS = "giorni"

# Classificazione dello sforzo per intervento: prima i lavori di
# contenuto/architettura (giorni), poi le correzioni di configurazione
# e meta (minuti); il resto (markup, redirect, media) vale ore.
_EFFORT_DAYS_RE = re.compile(
    r"testo scarso|superficie|poche pagine|nessuna pagina|chunk"
    r"|consenso|share of voice|query senza|vinte interamente"
    r"|contenut|faq|orfan|profondit|vocabolario|autoconsist"
    r"|molto javascript|heading in forma|definizion|esemp"
    r"|ciclo di vita",
    re.IGNORECASE)
_EFFORT_MINUTES_RE = re.compile(
    r"robots\.txt|sitemap|llms\.txt|noindex|canonical|title"
    r"|descript|segnaposto|senza attributo lang|hreflang|\balt\b"
    r"|contenuto identico|crawler ia bloccat|slug"
    r"|noarchive|nocache|copilot|clickbait"
    r"|charset|viewport|open graph",
    re.IGNORECASE)


def estimate_effort(finding: "Finding") -> str:
    """Stima a tre livelli dello sforzo per correggere il rilievo."""
    text = "%s %s" % (finding.title, finding.fix)
    if _EFFORT_DAYS_RE.search(text):
        return EFFORT_DAYS
    if _EFFORT_MINUTES_RE.search(text):
        return EFFORT_MINUTES
    return EFFORT_HOURS


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
        }
        if cit:
            item.update(notes[id(f)])
        plan.append(item)
    return plan


def surface_math(pages: Sequence[Page]) -> Optional[Dict[str, object]]:
    """La "matematica del problema": superficie attuale vs potenziale.

    Il potenziale e' una proiezione prudente a parita' di pagine:
    ogni pagina analizzabile portata ad almeno ~900 parole (4 chunk
    da ~220) piu' una sezione FAQ (1 chunk). Il moltiplicatore dice
    quante occasioni in piu' di comparire nelle liste RRF esistono
    gia' nel sito, senza nemmeno creare pagine nuove.
    """
    good = [p for p in pages if p.ok]
    if not good:
        return None
    chunks_now = sum(len(p.chunks) for p in good)
    potential = sum(max(len(p.chunks), 4) + 1 for p in good)
    words_avg = sum(p.word_count for p in good) // len(good)
    return {
        "pages": len(good),
        "chunks_now": chunks_now,
        "words_avg": words_avg,
        "chunks_potential": potential,
        "multiplier": (round(potential / chunks_now, 1)
                       if chunks_now else None),
        "assumption": "ogni pagina esistente portata ad almeno ~900 "
                      "parole (4 chunk) piu' una FAQ; nessuna pagina "
                      "nuova",
    }


@dataclass
class Chunk:
    """Porzione di testo indicizzabile, come in una pipeline RAG."""

    url: str
    heading: str
    text: str
    index: int = 0

    @property
    def label(self) -> str:
        head = self.heading or "(senza heading)"
        return "%s  ·  %s" % (urlparse(self.url).path or "/", head[:60])

    @property
    def searchable(self) -> str:
        return "%s\n%s" % (self.heading, self.text)


@dataclass
class Page:
    """Rappresentazione di una pagina HTML analizzata."""

    url: str
    status: int = 0
    final_url: str = ""
    redirects: int = 0
    elapsed: float = 0.0
    html_bytes: int = 0
    lang: str = ""
    title: str = ""
    description: str = ""
    canonical: str = ""
    meta_robots: str = ""
    bingbot_meta: str = ""
    semantic_tag_types: int = 0
    div_count: int = 0
    element_count: int = 0
    has_charset: bool = False
    has_viewport: bool = False
    generator: str = ""
    author: str = ""
    published: str = ""
    modified: str = ""
    contact_links: int = 0
    generic_anchors: int = 0
    internal_targets: List[str] = field(default_factory=list)
    internal_anchors: List[Tuple[str, str]] = field(
        default_factory=list)
    og: Dict[str, str] = field(default_factory=dict)
    hreflang: List[str] = field(default_factory=list)
    headings: List[Tuple[int, str]] = field(default_factory=list)
    paragraphs: List[str] = field(default_factory=list)
    blocks: List[Tuple[str, str]] = field(default_factory=list)
    text: str = ""
    word_count: int = 0
    script_bytes: int = 0
    rendered: bool = False
    raw_js_heavy: bool = False
    images: int = 0
    images_with_alt: int = 0
    internal_links: int = 0
    external_links: int = 0
    jsonld_types: List[str] = field(default_factory=list)
    jsonld_raw: List[dict] = field(default_factory=list)
    chunks: List[Chunk] = field(default_factory=list)
    error: str = ""

    @property
    def ok(self) -> bool:
        return self.status == 200 and not self.error

    @property
    def slug(self) -> str:
        return urlparse(self.url).path.strip("/").split("/")[-1] or "/"


# --------------------------------------------------------------------
# Recupero HTTP
# --------------------------------------------------------------------

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


# --------------------------------------------------------------------
# robots.txt e sitemap
# --------------------------------------------------------------------

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
                url=url,
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
            "%d righe." % len(self.raw.splitlines()), url=url))

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
                url=url, weight=2.0,
                example="# robots.txt - sblocca gli agenti IA\n"
                        "User-agent: GPTBot\nDisallow:\n\n"
                        "User-agent: ClaudeBot\nDisallow:\n\n"
                        "User-agent: PerplexityBot\nDisallow:"))
        else:
            findings.append(Finding(
                AREA_TECH, SEV_OK, "Crawler IA ammessi",
                "Verificati: %s." % ", ".join(AI_CRAWLERS), url=url))

        if self.sitemaps:
            findings.append(Finding(
                AREA_TECH, SEV_OK, "Sitemap dichiarata nel robots.txt",
                ", ".join(self.sitemaps), url=url))
        else:
            findings.append(Finding(
                AREA_TECH, SEV_WARNING,
                "Nessuna sitemap dichiarata nel robots.txt",
                fix="Aggiungi la riga 'Sitemap: https://.../sitemap.xml'.",
                url=url,
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


# --------------------------------------------------------------------
# Rendering JavaScript (facoltativo, via Playwright)
# --------------------------------------------------------------------

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


# --------------------------------------------------------------------
# Parsing della pagina
# --------------------------------------------------------------------

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


def build_chunks(page: Page, target_words: int = 220) -> List[Chunk]:
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


# --------------------------------------------------------------------
# Recuperatori: BM25 (lessicale) e vettoriale (semantico)
# --------------------------------------------------------------------

class BM25Index:
    """Okapi BM25.

    idf(q)   = ln(1 + (N - n(q) + 0.5) / (n(q) + 0.5))
    score(d) = somma_q idf(q) * f*(k1+1) / (f + k1*(1-b+b*|d|/avgdl))

    Riferimento: Robertson & Zaragoza (2009).
    """

    def __init__(self, docs: Sequence[str], k1: float = 1.5,
                 b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self.corpus = [tokenize(d) for d in docs]
        self.doc_len = [len(d) for d in self.corpus]
        self.n_docs = len(self.corpus) or 1
        self.avgdl = (sum(self.doc_len) / self.n_docs) or 1.0
        self.freqs = [Counter(d) for d in self.corpus]
        df: Counter = Counter()
        for doc in self.corpus:
            df.update(set(doc))
        self.idf = {
            term: math.log(
                1.0 + (self.n_docs - n + 0.5) / (n + 0.5))
            for term, n in df.items()
        }

    def search(self, query: str) -> List[Tuple[int, float]]:
        """Restituisce (indice_doc, punteggio) ordinati decrescenti."""
        terms = tokenize(query)
        scores: List[Tuple[int, float]] = []
        for i, freq in enumerate(self.freqs):
            total = 0.0
            for term in terms:
                if term not in freq:
                    continue
                f = freq[term]
                denom = f + self.k1 * (
                    1 - self.b + self.b * self.doc_len[i] / self.avgdl)
                total += self.idf.get(term, 0.0) * f * (self.k1 + 1) / denom
            if total > 0:
                scores.append((i, total))
        scores.sort(key=lambda x: (-x[1], x[0]))
        return scores


def _quiet_huggingface() -> None:
    """Zittisce il rumore dell'ecosistema Hugging Face nel log.

    Il caricamento del modello di embedding contatta l'HF Hub e senza
    token stampa su stderr avvisi in inglese sui rate limit (piu' le
    barre di avanzamento dei download): rumore puro nel log di
    avanzamento che la GUI mostra al cliente. L'avviso e' innocuo —
    il modello resta in cache locale dopo il primo download — e chi
    vuole limiti piu' alti puo' esportare HF_TOKEN, che le librerie
    leggono da sole. Le variabili gia' impostate dall'utente non
    vengono toccate.
    """
    os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
    os.environ.setdefault("HF_HUB_VERBOSITY", "error")
    os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
    for name in ("huggingface_hub", "transformers",
                 "sentence_transformers"):
        logging.getLogger(name).setLevel(logging.ERROR)


def embeddings_available() -> bool:
    """True se sentence-transformers e numpy sono importabili."""
    return (
        importlib.util.find_spec("sentence_transformers") is not None
        and importlib.util.find_spec("numpy") is not None
    )


def resolve_model_name(requested: str) -> str:
    """Modello di embedding effettivo a partire da --embeddings.

    Esplicito se indicato; "none"/"off"/"char-tfidf" forzano il
    proxy; vuoto con sentence-transformers installato attiva il
    modello multilingue predefinito (auto-rilevamento); altrimenti
    resta il proxy char-tfidf.
    """
    req = requested.strip()
    if req.lower() in ("none", "off", "char-tfidf"):
        return ""
    if req:
        return req
    return DEFAULT_EMBEDDINGS_MODEL if embeddings_available() else ""


class VectorIndex:
    """Recuperatore vettoriale.

    Se e' disponibile ``sentence-transformers`` usa embedding densi
    reali. Altrimenti ripiega su TF-IDF di n-grammi di caratteri con
    similarita' coseno: e' un *proxy* morfologico, non una vera
    rappresentazione semantica, e viene dichiarato come tale nel
    referto.
    """

    def __init__(self, docs: Sequence[str],
                 model_name: str = "") -> None:
        self.docs = list(docs)
        self.model = None
        self.mode = "char-tfidf"
        if model_name:
            self._load_model(model_name)
        if self.model is None:
            self._build_tfidf()

    def _load_model(self, model_name: str) -> None:
        _quiet_huggingface()
        try:
            from sentence_transformers import SentenceTransformer
            import numpy as np
        except ImportError:
            print("  ! sentence-transformers non disponibile: uso il "
                  "proxy TF-IDF su n-grammi.", file=sys.stderr)
            return
        except Exception as exc:
            # Installazioni rotte (es. torch/numpy incompatibili)
            # sollevano errori diversi da ImportError: il ripiego
            # deve restare pulito anche in quel caso.
            print("  ! sentence-transformers non utilizzabile "
                  "(%s: %s): uso il proxy TF-IDF su n-grammi."
                  % (type(exc).__name__, exc), file=sys.stderr)
            return
        try:
            self.model = SentenceTransformer(model_name)
            emb = self.model.encode(
                self.docs, normalize_embeddings=True,
                show_progress_bar=False)
            self.matrix = np.asarray(emb, dtype="float32")
            self.np = np
            self.mode = "embeddings:%s" % model_name
        except Exception as exc:  # pragma: no cover
            print("  ! modello non caricato (%s): uso TF-IDF." % exc,
                  file=sys.stderr)
            self.model = None

    def _build_tfidf(self) -> None:
        self.vectors: List[Dict[str, float]] = []
        grams = [char_ngrams(d) for d in self.docs]
        df: Counter = Counter()
        for gram in grams:
            df.update(set(gram))
        n_docs = len(self.docs) or 1
        self.idf = {
            g: math.log((1 + n_docs) / (1 + n)) + 1.0
            for g, n in df.items()
        }
        for gram in grams:
            self.vectors.append(self._vectorize(gram))

    def _vectorize(self, grams: Iterable[str]) -> Dict[str, float]:
        counts = Counter(grams)
        vec = {
            g: (1.0 + math.log(c)) * self.idf.get(g, 1.0)
            for g, c in counts.items()
        }
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        return {g: v / norm for g, v in vec.items()}

    def search(self, query: str) -> List[Tuple[int, float]]:
        if self.model is not None:
            emb = self.model.encode(
                [query], normalize_embeddings=True,
                show_progress_bar=False)
            sims = self.matrix @ self.np.asarray(emb[0], dtype="float32")
            pairs = [(i, float(s)) for i, s in enumerate(sims) if s > 0]
        else:
            qvec = self._vectorize(char_ngrams(query))
            pairs = []
            for i, vec in enumerate(self.vectors):
                small, big = (qvec, vec) if len(qvec) < len(vec) \
                    else (vec, qvec)
                sim = sum(v * big.get(g, 0.0) for g, v in small.items())
                if sim > 0:
                    pairs.append((i, sim))
        pairs.sort(key=lambda x: (-x[1], x[0]))
        return pairs


def reciprocal_rank_fusion(
        rankings: Sequence[Sequence[Tuple[int, float]]],
        k: int = 60, top_n: int = 10) -> List[Tuple[int, float]]:
    """Fonde piu' liste ordinate con la formula RRF.

        score(d) = somma_i 1 / (k + rank_i(d))

    Il rango parte da 1. Ogni lista pesa uguale, come in Elasticsearch.
    Riferimento: Cormack et al. (2009); Elastic; Microsoft Learn.
    """
    scores: Dict[int, float] = {}
    for ranking in rankings:
        for rank, (doc_id, _score) in enumerate(ranking, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
    fused = sorted(scores.items(), key=lambda x: (-x[1], x[0]))
    return fused[:top_n]


# --------------------------------------------------------------------
# Controlli per area
# --------------------------------------------------------------------

def check_llms_txt(base: str, fetcher: Fetcher) -> Finding:
    """Verifica la presenza di /llms.txt (standard emergente).

    E' un indice in Markdown dei contenuti pensato per gli agenti
    IA (llmstxt.org): assente non e' un errore, quindi il rilievo
    negativo e' solo informativo.
    """
    url = urljoin(base, "/llms.txt")
    resp = fetcher.get(url)
    if resp is not None and resp.status_code == 200 \
            and resp.text.strip() \
            and "html" not in resp.headers.get("Content-Type", ""):
        return Finding(
            AREA_TECH, SEV_OK, "llms.txt presente",
            "%d righe." % len(resp.text.splitlines()), url=url)
    return Finding(
        AREA_TECH, SEV_INFO, "llms.txt assente",
        "Standard emergente (llmstxt.org): un indice in Markdown "
        "dei contenuti chiave pensato per gli agenti IA.",
        "Valuta di pubblicare /llms.txt con i contenuti chiave.",
        url=url)


def _audit_link_graph(pages: List[Page], base: str) -> List[Finding]:
    """Pagine orfane, profondita' di click e anchor generiche."""
    good = [p for p in pages if p.ok]
    if len(good) < 2:
        return []

    by_url: Dict[str, Page] = {}
    for p in good:
        by_url.setdefault(norm_url(p.url), p)
        if p.final_url:
            by_url.setdefault(norm_url(p.final_url), p)

    edges: Dict[str, Set[str]] = {}
    incoming: Counter = Counter()
    for p in good:
        src = norm_url(p.url)
        outs: Set[str] = set()
        for target in p.internal_targets:
            dest = by_url.get(target)
            if dest is None:
                continue
            key = norm_url(dest.url)
            if key != src:
                outs.add(key)
                incoming[key] += 1
        edges[src] = outs

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
            example="Dalla pagina correlata:\n"
                    "<a href=\"/servizio-collegato/\">nome "
                    "descrittivo del servizio</a>"))
    else:
        out.append(Finding(
            AREA_TECH, SEV_OK,
            "Tutte le pagine hanno link interni in ingresso"))

    if home in edges:
        depth = {home: 0}
        queue = [home]
        while queue:
            node = queue.pop(0)
            for dest in sorted(edges.get(node, ())):
                if dest not in depth:
                    depth[dest] = depth[node] + 1
                    queue.append(dest)
        deep = sorted(u for u, d in depth.items() if d > 3)
        if deep:
            out.append(Finding(
                AREA_TECH, SEV_WARNING,
                "%d pagina/e oltre 3 click dalla home" % len(deep),
                ", ".join(deep[:5]) + ".",
                "Accorcia i percorsi: le pagine profonde vengono "
                "scansionate e pesate meno."))

    generic = sum(p.generic_anchors for p in good)
    if generic:
        out.append(Finding(
            AREA_TECH, SEV_INFO,
            "%d anchor generiche nei link interni" % generic,
            "Testi come \"clicca qui\" o \"leggi di piu'\" non "
            "dicono nulla sul contenuto di arrivo.",
            "Usa anchor descrittive con i termini della pagina "
            "di destinazione."))
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
            "definitivi.",
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
            "interni."))
    if moved:
        out.append(Finding(
            AREA_TECH, SEV_WARNING,
            "%d URL interni rispondono con redirect" % len(moved),
            "URL spostati: %s."
            % ", ".join("%s -> %s" % (p.url, p.final_url)
                        for p in moved[:5]),
            "Aggiorna sitemap e link interni alla destinazione "
            "finale dei redirect.",
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
            example="# un solo salto, non a catena\n"
                    "Redirect 301 /vecchia/ "
                    "https://esempio.it/nuova/\n"
                    "# NON: /vecchia/ -> /intermedia/ -> /nuova/"))
    if not (http_to_https or www_mismatch or moved):
        out.append(Finding(
            AREA_TECH, SEV_OK, "Nessun redirect interno",
            "Tutti gli URL analizzati rispondono direttamente."))
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
            weight=2.0))
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
            "rimuovi il meta."))
    if not noarchive and not nocache:
        out.append(Finding(
            AREA_TECH, SEV_OK,
            "Nessun opt-out IA di Microsoft attivo",
            "Non esiste un token robots.txt dedicato all'IA di "
            "Microsoft: il controllo passa dai meta "
            "noarchive/nocache, qui assenti. I contenuti sono "
            "quindi utilizzabili nelle risposte di Copilot e nel "
            "training Microsoft; per l'opt-out usa noarchive "
            "(totale) o nocache (parziale)."))
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
               100 * ANCHOR_VARIETY_GOOD))]
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
        weight=1.0)]


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
            example="<meta charset=\"utf-8\">"))
    no_viewport = [p.url for p in good if not p.has_viewport]
    if no_viewport:
        out.append(Finding(
            AREA_TECH, SEV_WARNING,
            "%d pagina/e senza meta viewport" % len(no_viewport),
            "Senza viewport la resa mobile non e' dichiarata: %s"
            % ", ".join(sorted(no_viewport)[:5]),
            "Aggiungi il viewport responsive.",
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
            "og:image.",
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
            "og:image."))
    if not out and good:
        out.append(Finding(
            AREA_TECH, SEV_OK,
            "Meta di base a posto",
            "charset, viewport e Open Graph completi su tutte le "
            "%d pagine analizzate." % len(good)))
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
            url=base, weight=2.0,
            example="# nginx\nreturn 301 https://$host$request_uri;\n"
                    "# Apache (.htaccess)\nRewriteEngine On\n"
                    "RewriteCond %{HTTPS} off\n"
                    "RewriteRule ^ https://%{HTTP_HOST}%{REQUEST_URI} "
                    "[L,R=301]"))
    else:
        out.append(Finding(AREA_TECH, SEV_OK, "HTTPS attivo", url=base))

    broken = [p for p in pages if not p.ok]
    if broken:
        out.append(Finding(
            AREA_TECH, SEV_CRITICAL,
            "%d URL non raggiungibili o in errore" % len(broken),
            ", ".join("%s (%s)" % (p.url, p.status or p.error)
                      for p in broken[:5]),
            "Correggi o rimuovi dalla sitemap gli URL in errore."))

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
            weight=3.0))
    elif n_pages == 1:
        out.append(Finding(
            AREA_TECH, SEV_CRITICAL,
            "Superficie indicizzabile minima (1 pagina)",
            "Con un solo documento la somma RRF non ha addendi: non "
            "esistono passaggi distinti da far emergere.",
            "Crea pagine autonome per ogni tema/servizio.",
            weight=3.0))
    elif n_pages < 5:
        out.append(Finding(
            AREA_TECH, SEV_WARNING,
            "Poche pagine indicizzabili (%d)" % n_pages,
            fix="Amplia la superficie: una pagina per intento.",
            weight=2.0))
    else:
        out.append(Finding(
            AREA_TECH, SEV_OK,
            "%d pagine indicizzabili analizzate" % n_pages,
            "%s%s." % (", ".join(p.url for p in good[:5]),
                       " e altre %d" % (n_pages - 5)
                       if n_pages > 5 else "")))

    if not from_sitemap:
        out.append(Finding(
            AREA_TECH, SEV_WARNING, "Sitemap XML assente o illeggibile",
            "URL individuati tramite crawling dei link interni.",
            "Pubblica una sitemap XML e dichiarala nel robots.txt.",
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
            "sitemap.", weight=2.0))

    noindex = [p for p in good
               if "noindex" in (p.meta_robots or "").lower()]
    if noindex:
        out.append(Finding(
            AREA_TECH, SEV_WARNING,
            "%d pagina/e con meta robots noindex" % len(noindex),
            ", ".join(p.url for p in noindex[:5]),
            "Verifica che l'esclusione sia voluta.",
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
            example="<link rel=\"canonical\" "
                    "href=\"https://esempio.it/servizio/\">"))
    elif good:
        out.append(Finding(
            AREA_TECH, SEV_OK, "Canonical presenti",
            "Dichiarato su tutte le %d pagine analizzate."
            % len(good)))

    no_lang = [p for p in good if not p.lang]
    if no_lang:
        out.append(Finding(
            AREA_TECH, SEV_WARNING,
            "%d pagina/e senza attributo lang" % len(no_lang),
            fix="Imposta <html lang=\"it\">: aiuta la selezione del "
                "modello linguistico in fase di analisi."))

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
            weight=2.0))
    elif good:
        out.append(Finding(
            AREA_TECH, SEV_OK,
            "Contenuto presente nell'HTML iniziale"))

    slow = [p for p in good if p.elapsed > 2.0]
    if slow:
        out.append(Finding(
            AREA_TECH, SEV_WARNING,
            "%d pagina/e con risposta oltre 2 s" % len(slow),
            "Piu' lenta: %.2f s." % max(p.elapsed for p in slow),
            "Ottimizza cache e TTFB."))

    langs = {p.lang.split("-")[0] for p in good if p.lang}
    multilingual = len(langs) > 1
    has_hreflang = any(p.hreflang for p in good)
    if multilingual and not has_hreflang:
        out.append(Finding(
            AREA_TECH, SEV_WARNING,
            "Sito multilingua senza hreflang",
            "Lingue rilevate: %s." % ", ".join(sorted(langs)),
            "Dichiara hreflang reciproci fra le versioni.",
            example="<link rel=\"alternate\" hreflang=\"it\" "
                    "href=\"https://esempio.it/it/\">\n"
                    "<link rel=\"alternate\" hreflang=\"en\" "
                    "href=\"https://esempio.it/en/\">"))
    elif not multilingual:
        out.append(Finding(
            AREA_TECH, SEV_INFO, "Sito monolingua: hreflang non "
            "necessario"))
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
            example="Prima: \"Non crederai a cosa fa il "
                    "drenaggio!!\"\n"
                    "Dopo:  \"Drenaggio linfatico: benefici, "
                    "durata e costi di una seduta\"",
            weight=1.5)]
    return [Finding(
        AREA_LEX, SEV_OK,
        "Nessuna formula clickbait in title e heading",
        "Titoli in stile informativo su tutte le %d pagine "
        "analizzate." % len(good))]


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
            weight=2.0))
    if bad_title:
        out.append(Finding(
            AREA_LEX, SEV_CRITICAL,
            "%d title non ottimizzati" % len(bad_title),
            "Esempi: %s" % " | ".join(
                "%r (%d car.)" % (p.title, len(p.title))
                for p in bad_title[:3]),
            "Title unico, 30-65 caratteri, con i termini di ricerca "
            "reali; evita il nome dominio come titolo.", weight=2.0,
            example="<title>Drenaggio linfatico manuale a Parma | "
                    "Centro Esempio</title>\n"
                    "(52 caratteri: servizio + territorio + brand)"))
    if dup_title:
        out.append(Finding(
            AREA_LEX, SEV_WARNING,
            "%d title duplicati fra pagine" % len(dup_title),
            "; ".join(dup_title[:3]),
            "Ogni pagina deve avere un title distinto."))
    if not (missing_title or bad_title or dup_title):
        out.append(Finding(AREA_LEX, SEV_OK, "Title ben impostati"))

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
            "Scrivi 110-165 caratteri con servizio e territorio.",
            weight=1.5,
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
            "porta alcun segnale."))
    if long_desc:
        out.append(Finding(
            AREA_LEX, SEV_INFO,
            "%d meta description oltre %d caratteri"
            % (len(long_desc), DESC_MAX)))
    if not (no_desc or weak_desc):
        out.append(Finding(
            AREA_LEX, SEV_OK, "Meta description presenti e di lunghezza "
            "adeguata"))

    no_h1 = [p for p in good
             if not any(lv == 1 for lv, _ in p.headings)]
    multi_h1 = [p for p in good
                if sum(1 for lv, _ in p.headings if lv == 1) > 1]
    if no_h1:
        out.append(Finding(
            AREA_LEX, SEV_CRITICAL, "%d pagina/e senza H1" % len(no_h1),
            ", ".join(p.url for p in no_h1[:5]),
            "Un solo H1 per pagina, con i termini principali.",
            weight=1.5,
            example="<h1>Drenaggio linfatico manuale: cos'e' e "
                    "come funziona</h1>"))
    if multi_h1:
        out.append(Finding(
            AREA_LEX, SEV_WARNING,
            "%d pagina/e con piu' H1" % len(multi_h1)))
    if not (no_h1 or multi_h1):
        out.append(Finding(AREA_LEX, SEV_OK, "Struttura H1 corretta"))

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
            weight=2.0,
            example="Struttura tipo per una pagina servizio:\n"
                    "<h2>Cos'e' ...?</h2> <h2>Come funziona una "
                    "seduta</h2>\n<h2>Quando serve</h2> <h2>Quanto "
                    "costa</h2> <h2>Domande frequenti</h2>"))
    else:
        out.append(Finding(
            AREA_LEX, SEV_OK, "Volume di testo adeguato",
            "Media: %d parole per pagina."
            % (sum(p.word_count for p in good) / len(good))))

    acronyms = find_acronyms(good)
    expanded = {a for a, ok_ in acronyms.items() if ok_}
    if acronyms and len(expanded) < len(acronyms) / 2:
        out.append(Finding(
            AREA_LEX, SEV_WARNING,
            "Sigle usate senza forma estesa",
            "Non esplicitate: %s." % ", ".join(
                sorted(set(acronyms) - expanded)[:8]),
            "Scrivi 'SIGLA (forma estesa)' almeno alla prima "
            "occorrenza: copre entrambe le formulazioni di ricerca."))
    elif acronyms:
        out.append(Finding(
            AREA_LEX, SEV_OK,
            "Sigle accompagnate dalla forma estesa",
            ", ".join(sorted(expanded)[:8])))

    bad_slug = [p for p in good if re.search(r"[_%]|\d{4,}", p.slug)]
    if bad_slug:
        out.append(Finding(
            AREA_LEX, SEV_WARNING,
            "%d slug poco parlanti" % len(bad_slug),
            ", ".join(p.slug for p in bad_slug[:5]),
            "Usa slug tematici con trattini."))
    else:
        out.append(Finding(AREA_LEX, SEV_OK, "Slug tematici e leggibili"))

    total_img = sum(p.images for p in good)
    with_alt = sum(p.images_with_alt for p in good)
    if total_img and with_alt / total_img < 0.8:
        out.append(Finding(
            AREA_LEX, SEV_WARNING,
            "Attributi alt incompleti (%d/%d)" % (with_alt, total_img),
            fix="L'alt e' testo indicizzabile oltre che accessibilita'.",
            example="<img src=\"seduta.jpg\" alt=\"fisioterapista "
                    "esegue drenaggio linfatico\nmanuale sulla gamba "
                    "di una paziente\">"))
    elif total_img:
        out.append(Finding(
            AREA_LEX, SEV_OK,
            "Attributi alt presenti (%d/%d)" % (with_alt, total_img)))
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
    if share >= EXTRACT_GOOD_SHARE:
        return [Finding(AREA_SEM, SEV_OK,
                        "Buona estraibilita' diretta", detail)]
    return [Finding(
        AREA_SEM, SEV_WARNING,
        "Pochi paragrafi a risposta diretta", detail,
        "Riformula i paragrafi chiave aprendo con la risposta "
        "(\"X e' ...\", \"Si', ...\", \"In sintesi ...\") e "
        "tienili fra %d e %d parole."
        % (EXTRACT_MIN_WORDS, EXTRACT_MAX_WORDS),
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
            "utile domina." % total_hits)]
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
            "Sezioni trovate negli heading: %s." % trovate)]
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
        weight=2.0 if len(covered) <= 2 else 1.0)]


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
            "fa)." % (newest.isoformat(), newest_url, max(0, age)))]
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
        weight=2.0 if age > FRESH_STALE_DAYS else 1.0)]


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
            "citazioni)." % (contesto, CITATIONS_GOOD))]
    return [Finding(
        AREA_SEM, SEV_WARNING,
        "Nessun riferimento a fonti esterne",
        "%s. Citare le fonti rafforza i segnali E-E-A-T e da' "
        "agli assistenti IA qualcosa da verificare: i contenuti "
        "con riferimenti sono piu' citabili." % contesto,
        "Aggiungi una sezione \"Fonti\" con link a linee guida, "
        "studi o documentazione ufficiale (o citazioni nel testo).",
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
            weight=3.0))
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
        weight=2.0))

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
            example="Prima: \"Questo trattamento e' indicato dopo "
                    "gli interventi.\"\nDopo:  \"Il drenaggio "
                    "linfatico manuale e' indicato dopo gli "
                    "interventi.\""))
    else:
        out.append(Finding(
            AREA_SEM, SEV_OK,
            "Chunk in larga parte autoconsistenti (%.0f%% anaforici)"
            % (ratio * 100)))

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
            weight=2.0))
    else:
        out.append(Finding(
            AREA_SEM, SEV_OK,
            "%d heading in forma di domanda (%.0f%%)"
            % (len(questions), q_ratio * 100),
            "Esempi: %s."
            % "; ".join("\"%s\"" % q[:60] for q in questions[:3])))

    has_faq = any(FAQ_HINT_RE.search(h) for h in headings) or any(
        FAQ_HINT_RE.search(p.text[:4000]) for p in good)
    if has_faq:
        faq_where = next(
            (p.url for p in good
             if any(FAQ_HINT_RE.search(h) for _, h in p.headings)
             or FAQ_HINT_RE.search(p.text[:4000])), "")
        out.append(Finding(
            AREA_SEM, SEV_OK, "Sezione FAQ rilevata",
            "Rilevata su %s." % faq_where if faq_where else ""))
    else:
        out.append(Finding(
            AREA_SEM, SEV_CRITICAL, "Nessuna sezione FAQ",
            "Le FAQ allineano un chunk a un intento preciso e "
            "alimentano entrambi gli assi contemporaneamente.",
            "Aggiungi FAQ per pagina, marcate con FAQPage JSON-LD.",
            weight=1.5,
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
            "serve / esempio."))
    else:
        out.append(Finding(
            AREA_SEM, SEV_OK,
            "Presenti passaggi definitori (%.0f%% dei chunk)"
            % (def_ratio * 100)))

    examples = sum(1 for c in chunks if EXAMPLE_RE.search(c.text))
    if examples / len(chunks) < 0.05:
        out.append(Finding(
            AREA_SEM, SEV_WARNING, "Quasi nessun esempio concreto",
            fix="Esempi e casi studio sono i contenuti a piu' alta "
                "densita' semantica."))
    else:
        out.append(Finding(
            AREA_SEM, SEV_OK, "%d chunk con esempi concreti" % examples))

    tokens = tokenize(" ".join(c.text for c in chunks))
    unique = len(set(tokens))
    if unique < 300:
        out.append(Finding(
            AREA_SEM, SEV_WARNING,
            "Vocabolario ristretto (%d termini distinti)" % unique,
            "Poca varieta' lessicale significa copertura semantica "
            "limitata: intercetti poche riformulazioni della stessa "
            "domanda.",
            "Amplia i temi trattati e le formulazioni usate."))
    else:
        out.append(Finding(
            AREA_SEM, SEV_OK,
            "Vocabolario ampio (%d termini distinti)" % unique))
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
            "e' eleggibile per i risultati arricchiti."))
    if faq_broken:
        out.append(Finding(
            AREA_SD, SEV_WARNING,
            "%d domanda/e FAQPage incomplete" % faq_broken,
            "Ogni voce di mainEntity richiede una Question con "
            "name e un acceptedAnswer con text.",
            "Completa le coppie domanda/risposta nel markup."))
    if offer_issues:
        out.append(Finding(
            AREA_SD, SEV_WARNING,
            "%d problema/i nei prezzi delle offerte" %
            len(offer_issues),
            "; ".join(offer_issues[:4]) + ".",
            "In price solo il numero con il punto decimale (niente "
            "simboli di valuta); la valuta in priceCurrency (codice "
            "ISO 4217, es. EUR).",
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
            example="\"aggregateRating\": {\"@type\": "
                    "\"AggregateRating\",\n \"ratingValue\": "
                    "\"4.8\", \"reviewCount\": \"27\"}"))
    if rating_issues:
        out.append(Finding(
            AREA_SD, SEV_WARNING,
            "%d valutazione/i incoerenti" % len(rating_issues),
            "; ".join(rating_issues[:4]) + ".",
            "ratingValue dentro la scala dichiarata (default 1-5) "
            "e conteggio recensioni in reviewCount o ratingCount."))
    if bad_dates:
        out.append(Finding(
            AREA_SD, SEV_WARNING,
            "%d data/e non in formato ISO 8601" % len(bad_dates),
            "; ".join(bad_dates[:4]) + ".",
            "Usa AAAA-MM-GG, con l'eventuale orario dopo la T "
            "(es. 2026-08-03T09:30:00+02:00)."))
    if bad_urls:
        out.append(Finding(
            AREA_SD, SEV_WARNING,
            "%d URL di media non assoluti nel markup" % len(bad_urls),
            "; ".join(bad_urls[:4]) + ".",
            "In image, logo, thumbnailUrl, contentUrl ed embedUrl "
            "servono URL http(s) completi."))
    if checked and not out:
        out.append(Finding(
            AREA_SD, SEV_OK,
            "Markup Schema.org coerente (%d tipi verificati)"
            % len(checked),
            "Verificati: %s." % ", ".join(sorted(checked))))
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
        (author_note, "Autore dei contenuti dichiarato",
         "Nessun autore dichiarato",
         "Aggiungi il meta author o la proprieta' author nel "
         "JSON-LD: i motori IA pesano chi firma i contenuti.",
         "<meta name=\"author\" content=\"Dott.ssa Paola Rossi\">\n"
         "oppure nel JSON-LD:\n"
         "\"author\": {\"@type\": \"Person\", \"name\": "
         "\"Paola Rossi\"}"),
        (dates_note, "Date di pubblicazione/aggiornamento presenti",
         "Nessuna data di pubblicazione o aggiornamento",
         "Esponi article:published_time/modified_time o "
         "datePublished/dateModified nel JSON-LD.",
         "<meta property=\"article:published_time\" "
         "content=\"2026-08-03\">\n"
         "oppure nel JSON-LD:\n"
         "\"datePublished\": \"2026-08-03\", "
         "\"dateModified\": \"2026-08-03\""),
        (about_note, "Pagina \"chi siamo\" presente",
         "Nessuna pagina \"chi siamo\" rilevata",
         "Una pagina che presenta persone e competenze e' il "
         "segnale di esperienza piu' diretto.",
         "Crea /chi-siamo/ con: chi cura i contenuti, titoli e "
         "formazione,\nda quanto tempo, foto reali. Linkala dal "
         "footer di ogni pagina."),
        (contact_note, "Contatti verificabili presenti",
         "Nessun contatto verificabile rilevato",
         "Esponi telefono ed email (link tel:/mailto:) o una "
         "pagina contatti.",
         "<a href=\"tel:+390521123456\">0521 123456</a>\n"
         "<a href=\"mailto:info@esempio.it\">info@esempio.it</a>"),
    )
    for evidence, ok_title, warn_title, fix, example in signals:
        if evidence:
            out.append(Finding(
                AREA_SEM, SEV_OK, "E-E-A-T: %s" % ok_title,
                evidence[0].upper() + evidence[1:] + "."))
        else:
            out.append(Finding(
                AREA_SEM, SEV_WARNING, "E-E-A-T: %s" % warn_title,
                fix=fix, example=example))
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
            weight=1.0))
    if not out:
        out.append(Finding(
            AREA_SD, SEV_OK,
            "Markup semantico in uso",
            "Tutte le %d pagine analizzabili usano i tag di "
            "sezionamento e tengono i <div> sotto il %d%% degli "
            "elementi." % (len(eligible),
                           round(100 * DIVITIS_RATIO))))
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
            weight=2.0, example=EX_LOCALBUSINESS))
        return out

    out.append(Finding(
        AREA_SD, SEV_OK, "JSON-LD presente",
        "Tipi rilevati: %s." % ", ".join(
            "%s (x%d)" % (t, c) for t, c in all_types.most_common(12))))

    entity_types = {"Organization", "LocalBusiness", "Corporation",
                    "ProfessionalService", "Person"}
    if not entity_types & set(all_types):
        out.append(Finding(
            AREA_SD, SEV_CRITICAL, "Entita' principale non dichiarata",
            fix="Aggiungi Organization o LocalBusiness con nome, "
                "indirizzo, contatti e identificativi fiscali.",
            weight=1.5, example=EX_LOCALBUSINESS))
    else:
        out.append(Finding(
            AREA_SD, SEV_OK, "Entita' principale dichiarata"))

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
                example=EX_FAQPAGE if wanted == "FAQPage" else ""))

    covered = sum(1 for p in good if p.jsonld_types)
    if covered < len(good):
        out.append(Finding(
            AREA_SD, SEV_WARNING,
            "JSON-LD solo su %d pagine su %d" % (covered, len(good)),
            fix="Estendi il markup a tutte le pagine rilevanti."))

    out.extend(validate_jsonld(good))
    return out


# --------------------------------------------------------------------
# Simulazione RRF
# --------------------------------------------------------------------

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
                 k: int = 60, top_n: int = 5,
                 model_name: str = "") -> Tuple[
                     List[QueryResult], List[Finding], str]:
    """Esegue BM25 + vettoriale e ne fonde i risultati con RRF."""
    chunks = [c for p in pages if p.ok for c in p.chunks]
    findings: List[Finding] = []
    if not chunks or not queries:
        findings.append(Finding(
            AREA_RRF, SEV_CRITICAL,
            "Simulazione RRF non eseguibile",
            "Servono almeno un chunk e una query.", weight=2.0))
        return [], findings, "n/d"

    corpus = [c.searchable for c in chunks]
    bm25 = BM25Index(corpus)
    vector = VectorIndex(corpus, model_name=model_name)

    results: List[QueryResult] = []
    for query in queries:
        lex = bm25.search(query)[:top_n * 4]
        vec = vector.search(query)[:top_n * 4]
        fused = reciprocal_rank_fusion([lex, vec], k=k, top_n=top_n)
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
        sev, note = SEV_CRITICAL, (
            "Le due liste puntano a passaggi diversi: nessun documento "
            "accumula punteggio su entrambi gli assi.")
    elif consensus_ratio < 0.45:
        sev, note = SEV_WARNING, (
            "Consenso parziale fra i due recuperatori.")
    else:
        sev, note = SEV_OK, (
            "Buona sovrapposizione fra recupero lessicale e "
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
        weight=2.0,
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
            "Query verificate: %s." % elenco))

    return results, findings, vector.mode


# --------------------------------------------------------------------
# Confronto competitivo (share of voice)
# --------------------------------------------------------------------

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
        k: int = 60, top_n: int = 5, model_name: str = "") -> Tuple[
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
                "include con 0 passaggi."))

    chunks: List[Chunk] = list(own_chunks)
    owners: List[str] = [main_host] * len(own_chunks)
    for host, cchunks in corpora.items():
        chunks.extend(cchunks)
        owners.extend([host] * len(cchunks))

    if not chunks or not queries:
        findings.append(Finding(
            AREA_RRF, SEV_CRITICAL,
            "Confronto competitivo non eseguibile",
            "Servono almeno un chunk e una query.", weight=2.0))
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
        fused = reciprocal_rank_fusion([lex, vec], k=k, top_n=top_n)
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
        sev, note = SEV_CRITICAL, (
            "I concorrenti occupano i posti che servirebbero a te: "
            "sui tuoi stessi temi vieni recuperato raramente.")
    elif mine < parity:
        sev, note = SEV_WARNING, (
            "Sei sotto la parita': sui tuoi temi i concorrenti "
            "vengono recuperati piu' spesso di te.")
    else:
        sev, note = SEV_OK, (
            "Tieni testa ai concorrenti sui tuoi temi.")
    findings.append(Finding(
        AREA_RRF, sev,
        "Share of voice: %.0f%% dei primi %d posti fusi "
        "(parita' %.0f%%)" % (mine * 100, top_n, parity * 100),
        "%s Ripartizione: %s." % (note, breakdown),
        "Rafforza i passaggi sulle query dove i concorrenti ti "
        "superano: stessi termini espliciti, risposta completa.",
        weight=2.0))

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
            weight=2.0))
    else:
        elenco = "; ".join("\"%s\"" % r.query for r in results[:12])
        if len(results) > 12:
            elenco += "; ..."
        findings.append(Finding(
            AREA_RRF, SEV_OK,
            "Presente nei primi %d per tutte le %d query"
            % (top_n, len(results)),
            "Query del confronto: %s." % elenco))

    payload: Dict[str, object] = {
        "main": main_host,
        "top_n": top_n,
        "sites": sites,
        "share": {h: round(share[h] * 100, 1) for h in sites},
        "chunks": {main_host: len(own_chunks),
                   **{h: len(c) for h, c in corpora.items()}},
        "queries": [asdict(r) for r in results],
    }
    return payload, findings


# --------------------------------------------------------------------
# Punteggi e referto
# --------------------------------------------------------------------

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
    """Media pesata delle aree; lessicale e semantica pesano di piu'."""
    weights = {AREA_TECH: 1.0, AREA_LEX: 1.5, AREA_SEM: 1.5,
               AREA_SD: 1.0, AREA_RRF: 1.5}
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
    riformulato conta come nuovo + risolto.
    """
    def actionable(payload: Dict[str, object]) -> Dict[
            Tuple[str, str], Dict[str, object]]:
        out: Dict[Tuple[str, str], Dict[str, object]] = {}
        for f in payload.get("findings") or []:
            if f.get("severity") in (SEV_CRITICAL, SEV_WARNING):
                out.setdefault(_finding_key(f), f)
        return out

    prev_scores = previous.get("scores") or {}
    cur_scores = current.get("scores") or {}
    scores = {}
    for area, value in cur_scores.items():
        before = prev_scores.get(area)
        if value is not None and before is not None:
            scores[area] = round(float(value) - float(before), 1)

    prev_f = actionable(previous)
    cur_f = actionable(current)
    slim = ("area", "title", "severity")
    return {
        "site": current.get("site", ""),
        "previous_at": previous_at,
        "previous_generated_at": previous.get("generated_at", ""),
        "scores": scores,
        "new": [{k: cur_f[key].get(k, "") for k in slim}
                for key in sorted(cur_f) if key not in prev_f],
        "resolved": [{k: prev_f[key].get(k, "") for k in slim}
                     for key in sorted(prev_f) if key not in cur_f],
    }


def history_payload(base: str, findings: Sequence["Finding"],
                    scores: Dict[str, Optional[float]]
                    ) -> Dict[str, object]:
    """Riga compatta per lo storico JSONL: cio' che serve al delta.

    Contiene solo punteggi e rilievi azionabili (critici e
    avvertenze, con area/titolo/gravita'): abbastanza per
    compute_delta, abbastanza poco da tenere lo storico leggero.
    """
    return {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "created_at": time.time(),
        "site": base,
        "tool_version": __version__,
        "scores": {**scores, "overall": overall_score(scores)},
        "findings": [
            {"area": f.area, "severity": f.severity,
             "title": f.title}
            for f in findings
            if f.severity in (SEV_CRITICAL, SEV_WARNING)
        ],
    }


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


def render_text(base: str, pages: List[Page],
                findings: List[Finding],
                scores: Dict[str, Optional[float]],
                results: List[QueryResult], mode: str,
                k: int = 60,
                competitive: Optional[Dict[str, object]] = None,
                market: str = DEFAULT_MARKET,
                judge: Optional[Dict[str, object]] = None,
                delta: Optional[Dict[str, object]] = None) -> str:
    """Referto testuale per la console."""
    marks = {SEV_CRITICAL: "[X]", SEV_WARNING: "[!]",
             SEV_OK: "[v]", SEV_INFO: "[i]"}
    lines: List[str] = []
    lines.append("=" * 70)
    lines.append("AUDIT SEO + RRF  ·  %s" % base)
    lines.append("=" * 70)
    lines.append("Pagine analizzate : %d" % len([p for p in pages if p.ok]))
    lines.append("Chunk indicizzati : %d"
                 % sum(len(p.chunks) for p in pages if p.ok))
    lines.append("Recuperatore vett.: %s" % mode)
    lines.append("")
    lines.append("PUNTEGGI")
    for area, score in scores.items():
        if score is None:
            continue
        bar = "#" * int(score / 5)
        lines.append("  %-24s %5.1f/100  %s" % (area, score, bar))
    lines.append("  %-24s %5.1f/100" % ("COMPLESSIVO",
                                        overall_score(scores)))
    lines.append("")

    if delta:
        marks_d = {SEV_CRITICAL: "[X]", SEV_WARNING: "[!]"}
        lines.append("RISPETTO ALL'ESECUZIONE PRECEDENTE  ·  %s"
                     % (delta.get("previous_generated_at") or ""))
        variazioni = [
            "%s %+.1f" % (area, value) if value else "%s =" % area
            for area, value in dict(delta["scores"]).items()]
        if variazioni:
            lines.append("  " + " · ".join(variazioni))
        for label, items in (("Risolti", delta["resolved"]),
                             ("Nuovi", delta["new"])):
            lines.append("  %s (%d):" % (label, len(list(items)))
                         if items else "  %s: nessuno" % label)
            for f in items:
                lines.append("    %s %s"
                             % (marks_d.get(str(f["severity"]),
                                            "[i]"), f["title"]))
        lines.append("  Nota: rilievi confrontati per tipo (i "
                     "conteggi nei titoli possono variare).")
        lines.append("")

    cit = citability_profiles(pages, scores, market)
    if cit:
        lines.append("PROFILI DI CITABILITA' PER ASSISTENTE IA")
        for prof in cit["profiles"]:
            if prof["score"] is None:
                continue
            bar = "#" * int(prof["score"] / 5)
            lines.append("  %-24s %5.1f/100  %s"
                         % (prof["label"], prof["score"], bar))
        if cit["index"] is not None:
            lines.append("  %-24s %5.1f/100" % ("INDICE COMPOSITO",
                                                cit["index"]))
        lines.append("  Pesi (mercato %s): %s"
                     % (cit["market"],
                        ", ".join("%s %d%%" % (key, round(100 * w))
                                  for key, w
                                  in cit["market_weights"].items())))
        actions = citability_top_actions(findings, pages, scores,
                                         market)
        if actions:
            lines.append("  Azioni con maggior guadagno di "
                         "profilo:")
            for act in actions:
                gain = (" -> %s (+%.1f punti profilo)"
                        % (act["best_label"], act["best_gain"])
                        if act["best_profile"] else "")
                lines.append("   %d. [sforzo: %s] %s%s"
                             % (act["priority"], act["effort"],
                                act["title"], gain))
        lines.append("  Nota: %s" % cit["note"])
        lines.append("")

    if judge:
        lines.append("GIUDIZIO LLM SULLA CITABILITA'")
        if judge.get("status") == "ok":
            lines.append("  Modello: %s · passaggi valutati: %d · "
                         "media: %.1f/100"
                         % (judge["model"], judge["sampled"],
                            judge["average"]))
            if cit and cit["index"] is not None:
                lines.append("  Indice euristico: %.1f — scarto "
                             "giudice-euristica: %+.1f"
                             % (cit["index"],
                                float(str(judge["average"]))
                                - float(str(cit["index"]))))
            for v in judge["verdicts"]:
                lines.append("  %5.1f/100  %s"
                             % (v["score"], v["query"]))
                if v["reason"]:
                    lines.append("             %s" % v["reason"])
            lines.append("  Nota: %s" % judge["note"])
        else:
            lines.append("  Non eseguito: %s"
                         % judge.get("reason", ""))
        lines.append("")

    for area in (AREA_TECH, AREA_LEX, AREA_SEM, AREA_SD, AREA_RRF):
        subset = [f for f in findings if f.area == area]
        if not subset:
            continue
        lines.append("-" * 70)
        lines.append(area.upper())
        lines.append("-" * 70)
        order = {SEV_CRITICAL: 0, SEV_WARNING: 1, SEV_INFO: 2,
                 SEV_OK: 3}
        for finding in sorted(subset, key=lambda f: order[f.severity]):
            lines.append("%s %s" % (marks[finding.severity],
                                    finding.title))
            if finding.detail:
                lines.append("    %s" % finding.detail)
            if finding.fix:
                lines.append("    -> Fix: %s" % finding.fix)
        lines.append("")

    math = surface_math(pages)
    if math:
        lines.append("-" * 70)
        lines.append("LA MATEMATICA DEL PROBLEMA")
        lines.append("-" * 70)
        lines.append("  Superficie attuale   : %d pagine, %d chunk "
                     "(~%d parole/pagina)"
                     % (math["pages"], math["chunks_now"],
                        math["words_avg"]))
        lines.append("  Superficie potenziale: ~%d chunk (%s)"
                     % (math["chunks_potential"], math["assumption"]))
        if math["multiplier"] is not None:
            lines.append("  Effetto sull'RRF     : ~%.1fx occasioni "
                         "di comparire nelle liste fuse"
                         % math["multiplier"])
        else:
            lines.append("  Effetto sull'RRF     : da 0 addendi a "
                         "~%d occasioni di comparire nelle liste"
                         % math["chunks_potential"])
        lines.append("")

    plan = build_remediation(findings, pages, scores, market)
    if plan:
        quick = sum(1 for i in plan if i["quick_win"])
        criterio = ("gravita' e guadagno di citabilita'"
                    if "index_gain" in plan[0] else
                    "gravita' e peso")
        lines.append("-" * 70)
        lines.append("PIANO DI REMEDIATION  ·  %d interventi per "
                     "%s%s"
                     % (len(plan), criterio,
                        " · %d quick win" % quick if quick else ""))
        lines.append("-" * 70)
        for item in plan:
            tag = ("CRITICO" if item["severity"] == SEV_CRITICAL
                   else "AVVISO")
            marker = "  ** QUICK WIN" if item["quick_win"] else ""
            lines.append("%2d. [%s · %s · sforzo: %s] %s%s"
                         % (item["priority"], tag, item["area"],
                            item["effort"], item["title"], marker))
            if item.get("cross"):
                lines.append("    Trasversale: deprime %d profili "
                             "di citabilita' (risolto vale +%.1f "
                             "sull'indice)"
                             % (len(list(item["profiles_hit"])),
                                item["index_gain"]))
            if item["fix"]:
                lines.append("    Fix: %s" % item["fix"])
            if item["example"]:
                lines.append("    Esempio:")
                for row in str(item["example"]).splitlines():
                    lines.append("        %s" % row)
            lines.append("")

    if results:
        lines.append("-" * 70)
        lines.append("DETTAGLIO SIMULAZIONE RRF")
        lines.append("-" * 70)
        for res in results:
            lines.append("Query: %s   (consenso %d)"
                         % (res.query, res.consensus))
            for rank, (label, score) in enumerate(res.fused_top, 1):
                lines.append("   %d. %-52s  %.5f"
                             % (rank, label[:52], score))
            if not res.fused_top:
                lines.append("   (nessun passaggio recuperato)")
            lines.append("")

    if competitive:
        lines.append("-" * 70)
        lines.append("CONFRONTO COMPETITIVO  ·  share of voice sui "
                     "primi %d posti fusi" % competitive["top_n"])
        lines.append("-" * 70)
        share = competitive["share"]
        for host in competitive["sites"]:
            marker = "  <- tuo sito" if host == competitive["main"] \
                else ""
            lines.append("  %-38s %5.1f%%%s"
                         % (host, share[host], marker))
        lines.append("")
        for row in competitive["queries"]:
            best = ("miglior posizione %d" % row["best_rank_mine"]
                    if row["best_rank_mine"] else "ASSENTE")
            lines.append("  %-46s  tuoi %d/%d · %s"
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
                 scores: Dict[str, Optional[float]]) -> str:
    """Testata visiva del referto: anello, verdetto, tile, donut."""
    esc = html.escape
    total = overall_score(scores)
    label, hue, mark = score_verdict(total)
    ring_c = 326.73  # 2 * pi * r, con r = 52

    sev_counts = Counter(f.severity for f in findings)
    clean, flagged, broken = page_status_counts(pages, findings)
    n_pages = len(pages)

    out: List[str] = ["<div class=\"hero\">"]
    out.append(
        "<div class=\"ringbox\" role=\"img\" aria-label=\"Punteggio "
        "complessivo %.0f su 100: %s\"><svg viewBox=\"0 0 120 120\" "
        "width=\"124\" height=\"124\" aria-hidden=\"true\">"
        "<circle class=\"rtrack\" cx=\"60\" cy=\"60\" r=\"52\"></circle>"
        "<circle class=\"rfill\" cx=\"60\" cy=\"60\" r=\"52\" "
        "style=\"stroke:%s;stroke-dasharray:%.2f %.2f\" "
        "transform=\"rotate(-90 60 60)\"></circle></svg>"
        "<div class=\"rnum\" aria-hidden=\"true\"><b>%.0f</b>"
        "<small>su 100</small></div></div>"
        % (total, esc(label), hue, ring_c * total / 100.0,
           ring_c, total))
    out.append(
        "<div class=\"heroside\"><p class=\"verdict\"><span class="
        "\"ico\" style=\"background:%s\">%s</span>%s</p>"
        "<p class=\"soglie\">buono &ge; 70 &middot; da migliorare "
        "40&ndash;69 &middot; critico &lt; 40</p><div class=\"tiles\">"
        % (hue, mark, esc(label)))
    for sev, label_it, color in (
            (SEV_CRITICAL, "Critici", "var(--bad)"),
            (SEV_WARNING, "Avvertenze", "var(--warn)"),
            (SEV_INFO, "Informazioni", "var(--muted)")):
        out.append(
            "<div class=\"tile\"><span class=\"lbl\"><span class="
            "\"dot\" style=\"background:%s\"></span>%s</span>"
            "<b>%d</b></div>"
            % (color, esc(label_it), sev_counts.get(sev, 0)))
    out.append("</div></div>")

    if n_pages:
        donut = _donut_svg(
            [(clean, "var(--good)"), (flagged, "var(--warn)"),
             (broken, "var(--bad)")], n_pages,
            "%d pagine: %d senza rilievi, %d con rilievi, %d in "
            "errore" % (n_pages, clean, flagged, broken))
        out.append(
            "<div class=\"donutbox\"><div class=\"donutwrap\">%s"
            "<div class=\"dnum\" aria-hidden=\"true\"><b>%d</b>"
            "<small>pagine</small></div></div>"
            "<ul class=\"dleg\" aria-hidden=\"true\">"
            "<li><span class=\"dot\" style=\"background:var(--good)\">"
            "</span>%d senza rilievi</li>"
            "<li><span class=\"dot\" style=\"background:var(--warn)\">"
            "</span>%d con rilievi</li>"
            "<li><span class=\"dot\" style=\"background:var(--bad)\">"
            "</span>%d in errore</li></ul></div>"
            % (donut, n_pages, clean, flagged, broken))
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
                delta: Optional[Dict[str, object]] = None) -> str:
    """Referto HTML autonomo, leggibile in chiaro e in scuro."""
    esc = html.escape
    colors = {SEV_CRITICAL: "var(--bad)", SEV_WARNING: "var(--warn)",
              SEV_OK: "var(--good)", SEV_INFO: "var(--muted)"}
    marks = {SEV_CRITICAL: "&#10005;", SEV_WARNING: "!",
             SEV_OK: "&#10003;", SEV_INFO: "i"}

    parts: List[str] = []
    parts.append(
        "<!DOCTYPE html><html lang=\"it\"><head>"
        "<meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,"
        "initial-scale=1\">"
        "<title>Audit SEO + RRF - %s</title><style>%s</style>"
        "</head><body><div class=\"wrap\">" % (esc(base), _CSS))

    parts.append("<h1>Audit SEO + RRF</h1>")
    parts.append("<p class=\"sub\">%s</p>" % esc(base))
    parts.append(
        "<p class=\"meta\">Pagine analizzate: %d &middot; chunk "
        "indicizzati: %d &middot; recuperatore vettoriale: <code>%s"
        "</code></p>" % (
            len([p for p in pages if p.ok]),
            sum(len(p.chunks) for p in pages if p.ok), esc(mode)))

    parts.append(_render_hero(pages, findings, scores))

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
            % (esc(area), hue, score, score, hue))
    total = overall_score(scores)
    hue = "var(--good)" if total >= 70 else (
        "var(--warn)" if total >= 40 else "var(--bad)")
    parts.append(
        "<div class=\"sc tot\"><h3>Complessivo<span style=\"color:%s\">"
        "%.0f</span></h3><div class=\"bar\"><div class=\"fill\" "
        "style=\"width:%.0f%%;background:%s\"></div></div></div>"
        % (hue, total, total, hue))
    parts.append("</div>")

    if delta:
        parts.append(
            "<section><h2>Rispetto all'esecuzione precedente</h2>"
            "<p class=\"meta\">Confronto con l'audit del %s sullo "
            "stesso sito: l'audit diventa monitoraggio. Rilievi "
            "confrontati per tipo (i conteggi nei titoli possono "
            "variare).</p>"
            % esc(str(delta.get("previous_generated_at") or "")))
        variazioni = " · ".join(
            "%s <b>%+.1f</b>" % (esc(area), value) if value
            else "%s =" % esc(area)
            for area, value in dict(delta["scores"]).items())
        if variazioni:
            parts.append("<p class=\"meta\">%s</p>" % variazioni)
        for label, items in (("Risolti", delta["resolved"]),
                             ("Nuovi", delta["new"])):
            parts.append("<h3>%s (%d)</h3>"
                         % (label, len(list(items))))
            if not items:
                parts.append("<p class=\"meta\">Nessuno.</p>")
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
            "<section><h2>Profili di citabilita' per assistente IA"
            "</h2><p class=\"meta\">%s Mercato di riferimento: "
            "<b>%s</b> (pesi: %s).</p>"
            "<table class=\"citprof\"><thead><tr><th>Assistente"
            "</th><th>Cosa premia</th><th>Punteggio</th></tr>"
            "</thead><tbody>"
            % (esc(cit["note"]), esc(cit["market"]), esc(pesi)))
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
                "<tr><th>Indice composito (mercato %s)</th>"
                "<td>&mdash;</td><td style=\"color:%s\">"
                "<b>%.1f</b>/100<div class=\"bar\">"
                "<div class=\"fill\" style=\"width:%.0f%%;"
                "background:%s\"></div></div></td></tr>"
                % (esc(cit["market"]), hue, val, val, hue))
        parts.append("</tbody></table>")
        actions = citability_top_actions(findings, pages, scores,
                                         market)
        if actions:
            parts.append(
                "<h3>Top %d azioni prioritarie</h3>"
                "<p class=\"meta\">Le prime voci del piano di "
                "remediation con il profilo che ne guadagna di "
                "piu' (stima in punti profilo, stessa natura "
                "euristica).</p><ol class=\"cit-actions\">"
                % len(actions))
            for act in actions:
                badges = ("<span class=\"eff\">sforzo: %s</span>"
                          % esc(str(act["effort"])))
                if act["quick_win"]:
                    badges += "<span class=\"qw\">quick win</span>"
                gain = ""
                if act["best_profile"]:
                    gain = (" &mdash; guadagna di piu': <b>%s</b> "
                            "(+%.1f punti profilo)"
                            % (esc(str(act["best_label"])),
                               act["best_gain"]))
                parts.append("<li>%s %s%s</li>"
                             % (esc(str(act["title"])), badges,
                                gain))
            parts.append("</ol>")
        parts.append("</section>")

    if judge:
        parts.append("<section><h2>Giudizio LLM sulla "
                     "citabilita'</h2>")
        if judge.get("status") == "ok":
            confronto = ""
            if cit and cit["index"] is not None:
                confronto = (" Indice euristico: %.1f — scarto "
                             "giudice-euristica: %+.1f."
                             % (cit["index"],
                                float(str(judge["average"]))
                                - float(str(cit["index"]))))
            parts.append(
                "<p class=\"meta\">Modello <code>%s</code> su %d "
                "passaggio/i · media <b>%.1f</b>/100.%s %s</p>"
                "<table><thead><tr><th>Query</th><th>Punteggio"
                "</th><th>Motivazione</th></tr></thead><tbody>"
                % (esc(str(judge["model"])), judge["sampled"],
                   judge["average"], esc(confronto),
                   esc(str(judge["note"]))))
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
            parts.append("<p class=\"meta\">Non eseguito: %s</p>"
                         % esc(str(judge.get("reason", ""))))
        parts.append("</section>")

    order = {SEV_CRITICAL: 0, SEV_WARNING: 1, SEV_INFO: 2, SEV_OK: 3}
    for area in (AREA_TECH, AREA_LEX, AREA_SEM, AREA_SD, AREA_RRF):
        subset = sorted((f for f in findings if f.area == area),
                        key=lambda f: order[f.severity])
        if not subset:
            continue
        parts.append("<section><h2>%s</h2>" % esc(area))
        for finding in subset:
            parts.append(
                "<div class=\"find\"><span class=\"ico\" style=\""
                "background:%s\">%s</span><div class=\"txt\"><b>%s</b>"
                % (colors[finding.severity], marks[finding.severity],
                   esc(finding.title)))
            if finding.detail:
                parts.append("<span class=\"d\">%s</span>"
                             % esc(finding.detail))
            if finding.fix:
                parts.append("<span class=\"fix\">%s</span>"
                             % esc(finding.fix))
            parts.append("</div></div>")
        parts.append("</section>")

    math = surface_math(pages)
    if math:
        effetto = ("~%.1fx occasioni di comparire nelle liste fuse"
                   % math["multiplier"]
                   if math["multiplier"] is not None else
                   "da 0 addendi a ~%d occasioni di comparire "
                   "nelle liste" % math["chunks_potential"])
        parts.append(
            "<section><h2>La matematica del problema</h2>"
            "<p class=\"meta\">L'RRF premia chi compare in piu' "
            "liste con piu' passaggi pertinenti: il numero di chunk "
            "indicizzabili e' il vero moltiplicatore.</p>"
            "<table><tbody>"
            "<tr><th>Superficie attuale</th><td>%d pagine, %d chunk "
            "(~%d parole/pagina)</td></tr>"
            "<tr><th>Superficie potenziale</th><td>~%d chunk "
            "(%s)</td></tr>"
            "<tr><th>Effetto sull'RRF</th><td>%s</td></tr>"
            "</tbody></table></section>"
            % (math["pages"], math["chunks_now"], math["words_avg"],
               math["chunks_potential"], esc(str(math["assumption"])),
               esc(effetto)))

    plan = build_remediation(findings, pages, scores, market)
    if plan:
        quick = sum(1 for i in plan if i["quick_win"])
        criterio = (
            "gravita' e guadagno di citabilita': in testa i "
            "problemi trasversali, che deprimono piu' profili "
            "insieme"
            if "index_gain" in plan[0] else
            "gravita' e peso: si parte da cio' che rende di piu' "
            "sul punteggio")
        parts.append(
            "<section><h2>Piano di remediation</h2>"
            "<p class=\"meta\">%d interventi ordinati per %s. "
            "Lo sforzo stimato (minuti/ore/giorni) "
            "individua i quick win%s.</p>"
            % (len(plan), criterio,
               " — qui sono %d" % quick if quick else ""))
        for item in plan:
            sev = str(item["severity"])
            badges = ("<span class=\"eff\">sforzo: %s</span>"
                      % esc(str(item["effort"])))
            if item["quick_win"]:
                badges += "<span class=\"qw\">quick win</span>"
            if item.get("cross"):
                badges += ("<span class=\"crossb\">trasversale: "
                           "%d profili · +%.1f indice</span>"
                           % (len(list(item["profiles_hit"])),
                              item["index_gain"]))
            parts.append(
                "<div class=\"find\"><span class=\"ico\" style=\""
                "background:%s\">%s</span><div class=\"txt\">"
                "<b>%d. %s</b> %s"
                % (colors[sev], marks[sev], item["priority"],
                   esc(str(item["title"])), badges))
            if item["fix"]:
                parts.append("<span class=\"d\">%s</span>"
                             % esc(str(item["fix"])))
            if item["example"]:
                parts.append("<pre class=\"ex\">%s</pre>"
                             % esc(str(item["example"])))
            parts.append("</div></div>")
        parts.append("</section>")

    if results:
        parts.append("<section><h2>Dettaglio simulazione RRF</h2>"
                     "<p class=\"meta\">Le tacche sul consenso sono "
                     "le soglie del giudizio: sotto il 20% e' "
                     "critico, sotto il 45% da migliorare.</p>"
                     "<table><thead><tr><th>Query</th><th>Consenso"
                     "</th><th>Passaggio in testa dopo la fusione</th>"
                     "<th>Punteggio</th></tr></thead><tbody>")
        for res in results:
            top = res.fused_top[0] if res.fused_top else ("-", 0.0)
            ratio = res.consensus / 5.0
            hue = "var(--good)" if ratio >= 0.45 else (
                "var(--warn)" if ratio >= 0.2 else "var(--bad)")
            parts.append(
                "<tr><td>%s</td><td class=\"cons\">"
                "<span class=\"mnum\">%d su 5</span>"
                "<div class=\"meter\" aria-hidden=\"true\">"
                "<div class=\"mfill\" style=\"width:%.0f%%;"
                "background:%s\"></div>"
                "<span class=\"tick\" style=\"left:20%%\"></span>"
                "<span class=\"tick\" style=\"left:45%%\"></span>"
                "</div></td><td>%s</td><td>%.5f</td></tr>"
                % (esc(res.query), res.consensus, ratio * 100,
                   hue, esc(str(top[0])), top[1]))
        parts.append("</tbody></table></section>")

    if competitive:
        share = competitive["share"]
        parity = 100.0 / max(1, len(competitive["sites"]))
        parts.append(
            "<section><h2>Confronto competitivo</h2>"
            "<p class=\"meta\">Share of voice sui primi %d posti "
            "delle liste fuse, sulle query dei temi del tuo sito. "
            "La tacca indica la parita' (%.0f%%): sopra la tacca si "
            "e' sopra la propria quota naturale.</p>"
            % (competitive["top_n"], parity))
        parts.append("<table><thead><tr><th>Sito</th>"
                     "<th>Share</th><th></th></tr></thead><tbody>")
        for host in competitive["sites"]:
            mine = host == competitive["main"]
            name = esc(host) + (" <strong>(tuo sito)</strong>"
                                if mine else "")
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
        parts.append("<table><thead><tr><th>Query</th>"
                     "<th>Tuoi passaggi</th><th>Migliore posizione"
                     "</th></tr></thead><tbody>")
        for row in competitive["queries"]:
            best = (str(row["best_rank_mine"])
                    if row["best_rank_mine"]
                    else "<strong>assente</strong>")
            parts.append(
                "<tr><td>%s</td><td>%d su %d</td><td>%s</td></tr>"
                % (esc(row["query"]), row["mine_in_top"],
                   competitive["top_n"], best))
        parts.append("</tbody></table></section>")

    parts.append(
        "<footer><p class=\"brand\">Lympha Technologies S.r.l.</p>"
        "<p>Generato da <code>seo_rrf_audit.py</code> v%s. "
        "La formula applicata e' <code>score(d) = &Sigma; 1/(k + "
        "rank_i(d))</code> con k=%d, pesi uguali per ogni lista.</p>"
        "<p>Riferimenti: Cormack et al. (SIGIR 2009); "
        "<a href=\"https://learn.microsoft.com/en-us/azure/search/"
        "hybrid-search-ranking\">Microsoft Learn</a>; "
        "<a href=\"https://www.elastic.co/docs/reference/elasticsearch/"
        "rest-apis/reciprocal-rank-fusion\">Elastic</a>; "
        "<a href=\"https://schema.org/\">Schema.org</a>.</p>"
        "</footer></div></body></html>" % (__version__, k))
    return "".join(parts)


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
.crossb{display:inline-block;font-size:.68rem;font-weight:700;
border-radius:4px;padding:1px 7px;margin-left:6px;
background:var(--accent);color:#fff}
.cit-actions{margin:6px 0 0 18px;padding:0}
.cit-actions li{margin:.4rem 0}
.qw{background:var(--good);color:#fff;text-transform:uppercase;
letter-spacing:.03em}
footer{color:var(--muted);font-size:.78rem;padding:0 4px}
footer a{color:var(--accent)}
footer .brand{color:var(--accent);font-weight:700;font-size:.88rem;
letter-spacing:.04em}
"""


def render_json(base: str, pages: List[Page],
                findings: List[Finding],
                scores: Dict[str, Optional[float]],
                results: List[QueryResult], mode: str,
                k: int = 60,
                competitive: Optional[Dict[str, object]] = None,
                market: str = DEFAULT_MARKET,
                judge: Optional[Dict[str, object]] = None,
                delta: Optional[Dict[str, object]] = None) -> str:
    """Referto JSON, adatto a essere versionato o messo in pipeline."""
    payload = {
        "tool": "seo_rrf_audit.py",
        "version": __version__,
        "site": base,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "vector_retriever": mode,
        "rrf": {"k": k, "formula": "score(d)=sum 1/(k+rank_i(d))"},
        "scores": {**scores, "overall": overall_score(scores)},
        "citability": citability_profiles(pages, scores, market),
        "citability_actions": citability_top_actions(
            findings, pages, scores, market),
        "judge": judge,
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
        "remediation": build_remediation(findings, pages, scores,
                                         market),
        "rrf_simulation": [asdict(r) for r in results],
        "competitive": competitive,
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


# --------------------------------------------------------------------
# Orchestrazione
# --------------------------------------------------------------------

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
            "eventuali concorrenti."))
    elif robots_mode == ROBOTS_FORCE:
        findings.append(Finding(
            AREA_TECH, SEV_INFO,
            "Disallow del robots.txt ignorati su richiesta esplicita",
            "Scansione oltre i Disallow attivata con --ignore-robots "
            "%s: la responsabilita' della scansione e' stata assunta "
            "esplicitamente dall'utente."
            % IGNORE_ROBOTS_ACK))

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
                   ", ".join(sorted(excluded)[:5]))))
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
                "risposta originale." % render))
        if n_failed:
            findings.append(Finding(
                AREA_TECH, SEV_WARNING,
                "Rendering non riuscito per %d pagina/e" % n_failed,
                "Per queste pagine e' stato analizzato l'HTML "
                "statico.",
                "Riprova, o aumenta il timeout se il sito e' lento."))

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
            weight=1.0,
            example="Redirect 301 /index.html https://esempio.it/\n"
                    "e sulla pagina canonica:\n<link rel=\"canonical\""
                    " href=\"https://esempio.it/\">"))

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
        pages, queries, k=k, model_name=model_name)
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
            corpora[host] = [c for p in cpages if p.ok
                             for c in p.chunks]
        own_chunks = [c for p in pages if p.ok for c in p.chunks]
        competitive, comp_findings = simulate_share_of_voice(
            base, own_chunks, corpora, queries, k=k,
            model_name=model_name)
        findings += comp_findings

    scores = {
        area: area_score(findings, area)
        for area in (AREA_TECH, AREA_LEX, AREA_SEM, AREA_SD, AREA_RRF)
    }
    return pages, findings, scores, results, mode, competitive


def build_parser() -> argparse.ArgumentParser:
    """Costruisce il parser degli argomenti da riga di comando."""
    parser = argparse.ArgumentParser(
        prog="seo_rrf_audit.py",
        description="Audit SEO e Reciprocal Rank Fusion di un sito.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Esempio:\n"
               "  python3 seo_rrf_audit.py https://example.com "
               "--format html --output report.html")
    parser.add_argument("url", help="URL di partenza del sito")
    parser.add_argument("--max-pages", type=int, default=25,
                        help="numero massimo di pagine (default 25)")
    parser.add_argument("--queries", metavar="FILE",
                        help="file con una query per riga; se omesso "
                             "le query sono generate dai temi del sito")
    parser.add_argument("--embeddings", metavar="MODELLO", default="",
                        help="modello sentence-transformers per il "
                             "recupero vettoriale reale. Se omesso e "
                             "la libreria e' installata viene usato "
                             "%s; 'none' forza il proxy char-tfidf"
                             % DEFAULT_EMBEDDINGS_MODEL)
    parser.add_argument("--rrf-k", type=int, default=60,
                        help="costante k della formula RRF "
                             "(default 60)")
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
    parser.add_argument("--format", choices=("text", "json", "html"),
                        default="text", help="formato del referto")
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
    parser.add_argument("--history", metavar="FILE",
                        help="storico JSONL delle esecuzioni: "
                             "legge l'ultima riga dello stesso "
                             "sito per riportare nei referti il "
                             "delta (punteggi per area, rilievi "
                             "nuovi/risolti) e accoda una riga "
                             "compatta per l'esecuzione corrente. "
                             "Trasforma l'audit in monitoraggio "
                             "anche da riga di comando/cron")
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
    parser.add_argument("--render", choices=RENDER_MODES,
                        default=RENDER_OFF,
                        help="rendering JavaScript con browser "
                             "headless (richiede Playwright): 'auto' "
                             "rende solo le pagine con contenuto "
                             "lato client, 'always' tutte; il "
                             "rendering e' seriale e rispetta "
                             "--delay fra le pagine (default off)")
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
    ram = available_ram_mb()
    if ram is not None and args.max_body > ram * 0.1:
        print("Avviso: --max-body %.0f MB e' alto per questa "
              "macchina (RAM disponibile ora: %.0f MB). "
              "Suggerito un valore <= %.0f MB."
              % (args.max_body, ram, max(1.0, ram * 0.1)),
              file=sys.stderr)

    queries: List[str] = []
    if args.queries:
        try:
            with open(args.queries, encoding="utf-8") as handle:
                queries = [ln.strip() for ln in handle if ln.strip()]
        except OSError as exc:
            print("Impossibile leggere %s: %s" % (args.queries, exc),
                  file=sys.stderr)
            return 2

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
                render=args.render)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\nInterrotto dall'utente.", file=sys.stderr)
        return 130

    judge_data = run_judge(results, pages, args.judge,
                           verbose=not args.quiet)

    delta = None
    current_row = history_payload(base, findings, scores)
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
                 "html": render_html}
    report = renderers[args.format](
        base, pages, findings, scores, results, mode, args.rrf_k,
        competitive, market=args.market, judge=judge_data,
        delta=delta)

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
    return 1 if critical else 0


if __name__ == "__main__":
    sys.exit(main())
