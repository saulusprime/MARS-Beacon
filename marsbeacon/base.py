# -*- coding: utf-8 -*-
"""Costanti, espressioni regolari e modelli dati di MARS Beacon.

Generato dalla scomposizione di mars_audit.py (v1.58.0): il
namespace pubblico resta mars_audit, questo modulo e' interno.
"""

from __future__ import annotations

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
import os
import re
import sys


try:
    import requests  # noqa: F401
except ImportError:  # pragma: no cover
    sys.exit("Manca 'requests'. Installa: pip install requests")


try:
    from bs4 import BeautifulSoup  # noqa: F401
except ImportError:  # pragma: no cover
    sys.exit("Manca 'beautifulsoup4'. Installa: pip install "
             "beautifulsoup4 lxml")


__version__ = "1.60.0"


# Versione dello SCHEMA del referto JSON (e delle righe dello
# storico --history), indipendente dalla versione dello strumento:
# si incrementa solo per cambi INCOMPATIBILI della struttura
# (campi rinominati/rimossi o semantica cambiata); le aggiunte di
# campi non la toccano. I consumatori possono fare il gate su
# questo intero invece di interpretare la versione del tool.
JSON_SCHEMA_VERSION = 1


# La pagina indicata nello user agent spiega chi e' il bot e come
# escluderlo; sovrascrivibile con --user-agent.
USER_AGENT = (
    "Mozilla/5.0 (compatible; SeoRrfAudit/%s; "
    "+https://github.com/saulusprime/MARS-Beacon)" % __version__
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


# Parametri della simulazione RRF esposti dalla v1.31.0: posti fusi
# considerati per query, pesi della variante RRF pesata (lessicale,
# vettoriale; 1,1 = RRF classico) e dimensione dei chunk.
DEFAULT_TOP_N = 5


TOP_N_MIN, TOP_N_MAX = 1, 20


DEFAULT_CHUNK_WORDS = 220


CHUNK_WORDS_MIN, CHUNK_WORDS_MAX = 80, 600


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


# Browser di sistema tentati se Playwright non ha un Chromium proprio
# (percorsi Linux, macOS e Windows: i non pertinenti non esistono e
# vengono semplicemente saltati).
CHROME_PATHS = (
    "/usr/bin/google-chrome",
    "/usr/bin/google-chrome-stable",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
    "/snap/bin/chromium",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
)


# Fork Lighthouse (docs/LIGHTHOUSE-FORK.md): installato accanto allo
# script da tools/update-lighthouse.sh, mai nel repository. Il
# rilevamento riusa CHROME_PATHS del rendering per il browser.
# Radice del repository: la directory sopra il package marsbeacon.
LIGHTHOUSE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "lighthouse")


LIGHTHOUSE_CLI = os.path.join(LIGHTHOUSE_DIR, "cli", "index.js")


LIGHTHOUSE_NODE_MIN = (22, 19)


LIGHTHOUSE_OFF = "off"


LIGHTHOUSE_AUTO = "auto"


LIGHTHOUSE_ALWAYS = "always"


LIGHTHOUSE_MODES = (LIGHTHOUSE_OFF, LIGHTHOUSE_AUTO,
                    LIGHTHOUSE_ALWAYS)


LIGHTHOUSE_DEVICE_MOBILE = "mobile"


LIGHTHOUSE_DEVICE_DESKTOP = "desktop"


LIGHTHOUSE_DEVICES = (LIGHTHOUSE_DEVICE_MOBILE,
                      LIGHTHOUSE_DEVICE_DESKTOP)


# Pagine rappresentative oltre la home (~10-30 s l'una in Lighthouse)
DEFAULT_LIGHTHOUSE_PAGES = 3


LIGHTHOUSE_PAGES_MIN = 0


LIGHTHOUSE_PAGES_MAX = 9


LIGHTHOUSE_TIMEOUT_S = 120  # tetto per pagina del processo Node


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


# Tipologie MARS (Meta-fusion, Accessibility, Ranking, Security):
# classificazione dei rilievi per pilastro di prodotto, usata dalla
# GUI per separare i risultati. Ogni area ha un pilastro di default;
# i singoli rilievi possono dichiararne uno diverso (campo
# ``pillar`` del Finding: oggi i controlli di sicurezza dell'area
# tecnica — HTTPS, http residuo, opt-out IA Microsoft).
PILLAR_META = "meta-fusion"


PILLAR_ACCESS = "accessibility"


PILLAR_RANK = "ranking"


PILLAR_SEC = "security"


AREA_PILLARS: Dict[str, str] = {
    AREA_TECH: PILLAR_ACCESS,
    AREA_LEX: PILLAR_RANK,
    AREA_SEM: PILLAR_RANK,
    AREA_SD: PILLAR_RANK,
    AREA_RRF: PILLAR_META,
}


# Sesta area (decisione P1): i rilievi del fork Lighthouse. La
# mappatura categorie -> pilastri e' la decisione di progetto del
# 2026-08-05 (TO-DO): la velocita' e' accesso, e l'accesso della
# categoria agentic-browsing e' quello degli agenti IA.
AREA_LIGHTHOUSE = "Performance (Lighthouse)"


LIGHTHOUSE_PILLARS: Dict[str, str] = {
    "performance": PILLAR_ACCESS,
    "accessibility": PILLAR_ACCESS,
    "seo": PILLAR_RANK,
    "best-practices": PILLAR_SEC,
    "agentic-browsing": PILLAR_ACCESS,
}


# Gravita' dai bucket ufficiali del punteggio Lighthouse (0.5/0.9):
# sotto 0.9 il rilievo esiste; sotto 0.5 e' critico se il peso
# dell'audit nel punteggio di categoria e' alto; peso 0 (audit che
# non concorrono al punteggio) e' informativo.
LIGHTHOUSE_PASS_SCORE = 0.9


LIGHTHOUSE_CRIT_SCORE = 0.5


LIGHTHOUSE_HIGH_WEIGHT = 3


LIGHTHOUSE_MAX_EVIDENCE = 3


# Metriche di laboratorio del pannello CWV in GUI: (audit LHR,
# etichetta, soglia "buono", soglia oltre cui e' "scarso") — soglie
# ufficiali Lighthouse/web.dev, in ms tranne il CLS (adimensionale).
# Sono dati lab, non field (CrUX); l'INP reale non e' misurabile in
# laboratorio e il TBT e' il suo proxy: la nota accompagna sempre
# il pannello.
LIGHTHOUSE_CWV = (
    ("largest-contentful-paint", "LCP", 2500.0, 4000.0),
    ("cumulative-layout-shift", "CLS", 0.1, 0.25),
    ("total-blocking-time", "TBT (proxy INP)", 200.0, 600.0),
    ("first-contentful-paint", "FCP", 1800.0, 3000.0),
    ("speed-index", "Speed Index", 3400.0, 5800.0),
)


# Tutte le aree nei referti: le cinque storiche piu' la sesta,
# presente solo quando Lighthouse e' stato eseguito (i renderer
# saltano le aree senza rilievi, overall_score le aree senza
# punteggio: la rinormalizzazione e' automatica).
ALL_AREAS = (AREA_TECH, AREA_LEX, AREA_SEM, AREA_SD, AREA_RRF,
             AREA_LIGHTHOUSE)


# Deduplica (decisione P1): audit Lighthouse -> prefisso della chiave
# del rilievo MARS equivalente. Il rilievo MARS resta canonico e la
# conferma Lighthouse diventa evidenza aggiuntiva sul rilievo; se
# MARS non ha rilevato il problema (nessun rilievo, o solo un OK) il
# rilievo Lighthouse resta: porta informazione nuova. Gli audit
# senza equivalente MARS (contrasto, font-size...) non sono in
# tabella e restano sempre.
LIGHTHOUSE_DEDUP: Dict[str, str] = {
    "document-title": "lex.title.",
    "meta-description": "lex.desc.",
    "image-alt": "lex.alt.",
    "html-has-lang": "tech.lang.",
    "html-lang-valid": "tech.lang.",
    "viewport": "tech.meta.viewport",
    "charset": "tech.meta.charset",
    "is-on-https": "tech.https.",
    "hreflang": "tech.hreflang.",
    "canonical": "tech.canonical.",
    "robots-txt": "tech.robots.",
    "is-crawlable": "tech.pages.noindex",
    "http-status-code": "tech.pages.broken",
    "link-text": "tech.links.generic_anchors",
    "llms-txt": "tech.llms.",
}


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


# Ancora di realta' (P2): posizionamento reale sulle query
# dell'audit via Brave Search API. Chiave SOLO dall'ambiente
# (pattern del giudizio LLM); BRAVE_BASE_URL sovrascrive
# l'endpoint (server finti nei test).
SEARCH_CHECK_AUTO = "auto"


SEARCH_CHECK_ON = "on"


SEARCH_CHECK_OFF = "off"


SEARCH_CHECK_MODES = (SEARCH_CHECK_AUTO, SEARCH_CHECK_ON,
                      SEARCH_CHECK_OFF)


SEARCH_CHECK_ENV = "BRAVE_API_KEY"


SEARCH_CHECK_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"


SEARCH_CHECK_MAX_QUERIES = 10  # tetto ai costi API per audit


SEARCH_CHECK_TOP_N = 20        # posizioni esaminate per query


SEARCH_CHECK_DELAY_S = 1.1     # rate limit Brave (1 richiesta/s)


SEARCH_CHECK_NOTE = (
    "Ranking reale del motore (Brave Search): dipende anche da "
    "personalizzazione, localita' e freschezza. Confronto "
    "direzionale con la simulazione RRF, non una validazione.")


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
    # Tipologia MARS: vuoto = pilastro di default dell'area
    # (AREA_PILLARS); valorizzato solo dai rilievi che deviano
    # (es. sicurezza dentro l'area tecnica).
    pillar: str = ""
    example: str = ""
    # Internazionalizzazione: i testi canonici restano in italiano;
    # ``key`` identifica il rilievo nel catalogo _FINDINGS_EN e
    # ``params`` porta i valori dinamici gia' interpolati nei testi,
    # cosi' i renderer possono riformattare i template tradotti.
    # Senza chiave (o senza voce in catalogo) resta l'italiano.
    key: str = ""
    params: Dict[str, object] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, object]:
        data = asdict(self)
        data["pillar"] = self.pillar \
            or AREA_PILLARS.get(self.area, "")
        return data


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
