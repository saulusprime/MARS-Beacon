# AS-IS — Stato di fatto del progetto

Fotografia di ciò che è **già realizzato e verificato** al 2026-08-04.
È il complemento di [TO-DO.md](TO-DO.md), che da qui in avanti elenca
solo ciò che resta da fare. Il quadro d'insieme e le istruzioni d'uso
sono nel [README.md](README.md).

## Strumento CLI — `seo_rrf_audit.py` v1.24.0

- **Audit su cinque aree** con rilievi a quattro gravità e punteggio
  0–100 per area, media complessiva pesata (tecnica 1.0, lessicale 1.5,
  semantica 1.5, dati strutturati 1.0, RRF 1.5): tecnica (HTTPS,
  robots.txt e permessi dei crawler IA, llms.txt, sitemap, errori,
  redirect interni, soft-404, grafo dei link interni, pagine
  segnaposto, noindex, canonical, contenuto solo-JS, hreflang,
  duplicati), lessicale BM25 (title, description, H1, conteggi, slug,
  alt), semantica (chunk, autoconsistenza, heading-domanda, FAQ,
  definizioni, esempi, vocabolario, segnali E-E-A-T), dati
  strutturati (inventario JSON-LD, entità, FAQPage, BreadcrumbList,
  WebSite, validazione delle proprietà minime per tipo).
- **Qualità dell'analisi** (v1.7.0): lista `AI_CRAWLERS` rivista su
  documentazione ufficiale dei vendor — 14 token fra training,
  ricerca/citazioni e fetch su richiesta utente; esclusi Bingbot
  (crawler di ricerca classico) e Claude-Web (deprecato) — con fonti
  citate nel codice; controllo di `/llms.txt` (rilievo informativo
  se assente); validazione delle proprietà minime dei tipi JSON-LD
  più comuni, incluse le coppie domanda/risposta di FAQPage; segnali
  E-E-A-T (meta author o author JSON-LD, article:published_time o
  datePublished, pagina "chi siamo", contatti tel:/mailto:/email);
  grafo dei link interni con pagine orfane, profondità oltre 3 click
  dalla home e anchor generiche ("clicca qui").
- **Piano di remediation** (v1.9.0), in tutti i referti e nella GUI:
  rilievi critici e avvertenze ordinati per gravità × peso, ciascuno
  con correzione ed **esempio concreto di fix** (campo `example` del
  rilievo: snippet JSON-LD, righe di robots.txt/.htaccess, testo
  prima/dopo). Rilievi arricchiti con evidenze: query verificate e
  consenso per query nell'area RRF, evidenze E-E-A-T (dove sono
  stati trovati autore, date, chi-siamo, contatti), URL coinvolti
  nei rilievi su canonical/description/H1/noindex, esempi testuali
  dei chunk anaforici e degli heading interrogativi. Dalla v1.14.0
  ogni intervento porta la **stima dello sforzo** (minuti/ore/giorni)
  incrociata con la priorità: i critici da minuti sono marcati
  **quick win** (badge in HTML/GUI, campi `effort`/`quick_win` nel
  JSON); e tutti i referti includono **"la matematica del problema"**
  — superficie attuale vs potenziale in chunk con proiezione
  dichiarata e moltiplicatore dell'effetto sull'RRF (`surface_math`
  nel JSON) — chiudendo il divario col referto consegnato a mano di
  miaweb.art.
- **Profili di citabilità per assistente IA** (v1.15.0, "lenti per
  modello" da Features.md): quattro profili — Claude,
  ChatGPT/Perplexity, Qwen, Kimi — che ripesano i punteggi di area
  (più la profondità editoriale: parole medie per pagina sul target
  di 900 di `surface_math`) secondo ciò che ciascun assistente
  plausibilmente premia, con rinormalizzazione dei pesi se un'area
  non ha punteggio. Indice composito pesato per mercato (`--market
  occidentale|globale|orientale`, default occidentale). In tutti e
  tre i referti (chiave JSON `citability`, sezione testuale, tabella
  HTML con barre) con **nota di onestà sempre inclusa**: stime
  euristiche derivate dalle metriche dell'audit, non comportamento
  documentato dai vendor. Dalla v1.16.0 la sezione riporta le **top
  azioni prioritarie**: le prime voci del piano di remediation
  annotate con il profilo che guadagna di più dall'intervento
  (variazione esatta del punteggio d'area proiettata sui pesi
  rinormalizzati del profilo; `citability_actions` nel JSON).
  Dalla v1.17.0 l'intero piano di remediation è annotato con i
  guadagni (`index_gain`, `profiles_hit`, `cross`) e, a parità di
  gravità, ordina per guadagno sull'indice composito del mercato
  scelto: i **problemi trasversali** — che deprimono più profili
  insieme — salgono in testa e portano un badge dedicato in
  HTML/GUI; senza dati di citabilità l'ordinamento resta
  gravità+peso.
- **Densità informativa** (v1.24.0, da Features.md): pagine sature
  di filler di marketing ("leader di mercato", "scopri di più",
  cinque lingue) segnalate quando le formule sono almeno 3 *e*
  almeno una ogni 100 parole — doppio requisito per non punire le
  call-to-action legittime; evidenze con le formule trovate ed
  esempio prima/dopo. Nell'area semantica (lente Claude).
- **Titoli clickbait** (v1.23.0, da Features.md): title e H1–H3
  scanditi con pattern sensazionalistici nelle cinque lingue ("non
  crederai…", "il segreto di/del…", "N motivi per…", esclamazioni
  multiple); avvertenza con evidenze ed esempio prima/dopo, sforzo
  "minuti". Solo titoli e heading, non il corpo: falsi positivi
  contenuti per costruzione.
- **Estraibilità diretta** (v1.22.0, da Features.md): quota di
  paragrafi di 20–120 parole che aprono con una risposta esplicita
  (sì/no, "in sintesi", passo numerato, definizione in apertura —
  cinque lingue) sul totale dei paragrafi sostanziosi; sotto la
  soglia di prassi del 20% scatta un'avvertenza con esempio
  prima/dopo. Nell'area semantica: alimenta la lente Claude dei
  profili di citabilità.
- **Opt-out IA di Microsoft** (v1.21.0): l'area tecnica controlla i
  meta `noarchive`/`nocache` che governano Bing Chat/Copilot e il
  training Microsoft (non esiste un token robots.txt dedicato;
  semantiche verificate sulla fonte primaria e citate nel codice).
  `noarchive` → avvertenza (citabilità zero sul canale Microsoft),
  `nocache` → informativo (solo URL/titolo/snippet), assenti → OK
  con spiegazione dell'opt-out; il meta scoped a `bingbot` prevale
  su quello generico, come documentato da Microsoft.
- **Cinque lingue nell'analisi linguistica** (v1.20.0): stopword e
  pattern di definizioni, esempi, anafore, FAQ e heading-domanda
  coprono italiano, inglese, **francese, tedesco e spagnolo**
  (liste e regex curate a mano, nessuna dipendenza; il "¿" spagnolo
  è gestito; l'espletivo tedesco "Es gibt…" non conta come
  anafora). Le query auto-generate usano i template della lingua
  prevalente del sito (attributo `lang`; default italiano).
- **Storico e delta anche nella CLI** (v1.19.0): `--history FILE`
  legge l'ultima esecuzione dello stesso sito dal JSONL, riporta
  nei tre referti la sezione "Rispetto all'esecuzione precedente"
  (variazioni dei punteggi per area e complessivo, rilievi
  nuovi/risolti per tipo con i conteggi normalizzati) e accoda una
  riga compatta (`history_payload`: solo punteggi e rilievi
  azionabili). `compute_delta` vive nel core ed è riusato dalla
  GUI (v2.11.0), i cui referti scaricati includono la stessa
  sezione. Righe malformate o file assente non impediscono mai
  l'audit; con cron/systemd l'audit diventa monitoraggio headless.
- **Giudizio LLM sulla citabilità** (v1.18.0, "LLM as judge"),
  **attivo di default** in modalità `auto` per decisione di
  progetto: dopo l'audit un modello (SDK ufficiale Anthropic,
  `claude-opus-5` con fallback server-side, chiave solo da
  `ANTHROPIC_API_KEY`) valuta il primo passaggio fuso di ogni query
  (deduplicato, max 5, una sola richiesta API) con punteggio 0–100
  e motivazione. Nei tre referti: verdetti, media e **scarto
  giudice-euristica** rispetto all'indice composito, con nota di
  onestà. Senza chiave o SDK il giudizio si salta con motivo
  dichiarato e l'audit resta interamente offline; `--judge on` lo
  pretende (errore d'uso senza chiave), `off` lo spegne; errori
  API, refusal e risposte malformate non fermano mai il referto.
- **Qualità del markup Schema.org** (v1.8.0): proprietà minime per
  23 tipi (fra cui Product, VideoObject, ImageObject, Event, Recipe,
  HowTo, JobPosting, Review, AggregateRating, Course, i tipi medici)
  e controlli sui valori — prezzi delle offerte numerici con valuta
  ISO 4217 (o priceSpecification), Product senza offerte né giudizi,
  ratingValue dentro la scala dichiarata e conteggio recensioni,
  date ISO 8601, URL di media assoluti, coppie domanda/risposta
  complete nelle FAQPage.
- **Simulazione RRF**: chunking per heading (~220 parole), doppio
  indice BM25 (Okapi, k1=1.5, b=0.75) e vettoriale
  (sentence-transformers con **auto-rilevamento** dalla v1.6.0 —
  modello multilingue predefinito se la libreria è installata,
  `--embeddings none` per forzare il proxy — oppure fallback
  char-TFIDF di 4-grammi, sempre dichiarato nel referto), fusione `Σ 1/(k+rank)` con k
  configurabile (`--rrf-k`, propagato a tutti i renderer) e misura del
  consenso fra le liste con soglie 20%/45%.
- **Scoperta URL** da sitemap (anche sitemap-index e `.xml.gz`,
  ricorsione ≤ 3, priorità agli URL con `lastmod` più recente quando
  `--max-pages` non copre tutto) con ripiego sul crawling BFS
  interno; deduplica dei contenuti identici per impronta del testo
  (conservato l'URL più corto).
- **Rendering JavaScript facoltativo** (v1.12.0): `--render
  off|auto|always` con Playwright (Chromium proprio o Chrome di
  sistema come ripiego). `auto` rende solo le pagine classificate
  client-side dall'euristica; il DOM renderizzato sostituisce solo
  l'estrazione del contenuto, mentre stato/redirect/tempi restano
  della risposta HTTP reale; il rilievo critico sul contenuto
  invisibile ai crawler senza JS scatta comunque (`raw_js_heavy`).
  Rendering seriale (Playwright sync non è thread-safe), rispetta
  delay e annullamento, verifica di disponibilità all'avvio. Select
  dedicata nella GUI con disponibilità esposta da /api/env.
- **Scansione concorrente** (v1.11.0): `--workers` (default 4, max
  16, 1 = seriale) scarica le pagine — del sito e dei concorrenti —
  con un pool di thread **senza cambiare il ritmo verso il sito**: il
  throttle del Fetcher assegna atomicamente gli slot di partenza
  distanziati di `--delay` anche fra thread; sessione HTTP ed esito
  d'errore sono per-thread; l'annullamento interrompe anche i worker
  in attesa. Campo dedicato nella GUI, incluso nelle preimpostazioni.
- **Robustezza del crawling** (v1.5.0): rilievi sulle catene di
  redirect interne (http→https, www/non-www, URL spostati, catene a
  più passaggi, con `final_url` e conteggio nel referto JSON);
  rilevamento euristico dei **soft-404** (200 con contenuto "pagina
  non trovata" nel title/H1, o nel corpo se molto breve); i
  Content-Type non analizzabili (PDF, immagini, archivi) non vengono
  scaricati: stato e header bastano a classificarli nel referto.
- **Query di prova** da file (`--queries`) o auto-generate dai
  bigrammi tematici di heading e title, senza query degeneri.
- **Tre formati di referto** (`text`, `json`, `html` autonomo con tema
  chiaro/scuro) su stdout o file; codici di uscita `0/1/2/130` adatti
  all'uso come gate in CI.
- **Limite alla dimensione delle risposte** (v1.1.0): scarico a
  blocchi con tetto di 10 MB configurabile (`--max-body`), conteggio
  post-decompressione, rifiuto immediato se il `Content-Length`
  dichiarato eccede, esclusione riportata nel referto fra gli URL in
  errore e avviso all'avvio se il valore scelto supera un decimo
  della RAM disponibile della macchina.
- **Robots.txt rispettato di default** (v1.2.0 opt-in, ribaltato in
  default nella v1.13.0): i `Disallow` per l'agente `SeoRrfAudit`
  vengono rispettati — né dalla sitemap né in crawling BFS — con
  rilievo informativo sugli URL esclusi. `--own-site` dichiara la
  titolarità del sito e analizza tutto (i concorrenti restano sempre
  protetti); `--ignore-robots accetto` ignora i Disallow ovunque con
  **accettazione esplicita di responsabilità** (valore letterale
  obbligatorio, registrata nel referto); `--respect-robots` è
  deprecato e confligge con le altre due. GUI: select a tre modalità
  con default "titolarità dichiarata" (coperta dalle condizioni di
  servizio) e checkbox di responsabilità obbligatoria per "ignora",
  validata lato server.
- **Confronto competitivo** (v1.4.0): con `--competitor URL`
  (ripetibile, max 3) i siti concorrenti vengono scansionati con gli
  stessi limiti (senza generare rilievi propri), i corpora fusi negli
  stessi indici BM25+vettoriale e interrogati con le query del sito
  principale; il referto riporta la **share of voice** sui primi 5
  posti fusi (rilievi con soglie rispetto alla parità: sotto la metà
  della parità è critico) e le query vinte interamente dai
  concorrenti. Presente in tutti e tre i renderer e nella GUI (barre
  per sito + tabella per query).
- **Retry con backoff esponenziale** (v1.3.0): gli errori di rete e
  gli HTTP 429/500/502/503/504 vengono ritentati (`--retries`,
  default 2) con attese 0,5 s → 1 s → 2 s (tetto 8 s) e rispetto
  dell'header `Retry-After`; gli altri stati HTTP e i corpi oltre
  `--max-body` non vengono ritentati perché sono segnali diagnostici.
- Fetcher con user agent esplicito e configurabile (`--user-agent`;
  il predefinito identifica lo strumento e rimanda alla pagina del
  progetto su GitHub), throttle configurabile (`--delay`), timeout
  20 s; PEP8, `flake8` pulito, licenza MIT dichiarata nel modulo.

## Interfaccia grafica locale — `seo_rrf_gui.py` v2.11.0 + `gui/`

- **Storico e delta per utente e dominio** (v2.10.0): il referto
  JSON completo di ogni esecuzione è salvato nel database
  (`audits.report_json`, migrazione automatica dei DB precedenti)
  ed esportabile con `GET /api/history/report?id=N` (solo il
  proprietario, profilo completo — link "JSON" per riga nello
  storico). A fine audit il server calcola il **delta rispetto
  all'esecuzione precedente dello stesso utente e dominio**
  (`compute_delta`): differenze dei punteggi per area/complessivo e
  rilievi **nuovi/risolti** (critici e avvertenze confrontati per
  area + titolo con i conteggi normalizzati; euristica dichiarata).
  Blocco "Rispetto all'esecuzione precedente" nei risultati con
  frecce testuali e liste con badge di gravità: l'audit diventa
  monitoraggio.

- **Citazioni IA nel tempo** (v2.9.0): sezione dedicata che legge
  lo storico JSONL del monitor citazioni (`GET /api/citations`,
  accesso richiesto; percorso con `--citations-history`, default
  `citazioni.jsonl` accanto agli script) con sintesi e tendenza
  per provider (delta fra esecuzioni), grafico SVG multilinea del
  tasso di citazione (una linea per provider più il complessivo,
  tratteggi ed etichette di fine linea, mai solo colore), tabella
  accessibile con tutti i valori e selettore del sito se lo
  storico ne contiene più d'uno; righe malformate o file assente
  non rompono mai la GUI.

- **Giudizio LLM nella GUI** (v2.8.0): select nel form (auto
  predefinito / obbligatorio / spento; "obbligatorio" è validato
  lato server contro la disponibilità reale di SDK e chiave, con
  motivo nell'errore), disponibilità esposta da `/api/env` e
  suggerimento contestuale aggiornato quando manca la chiave;
  nei risultati blocco con modello, media, scarto
  giudice-euristica e tabella dei verdetti (query, punteggio,
  motivazione), nota di onestà nella caption.

- **Problemi trasversali nel piano** (v2.7.0): il piano di
  remediation mostrato in GUI usa l'ordinamento per gravità e
  guadagno di citabilità, con badge "trasversale: N profili ·
  +X,X indice" sui rilievi che deprimono più profili e intestazione
  che dichiara il criterio.

- **Profili di citabilità nella GUI** (v2.6.0): select "Mercato di
  riferimento" nel form (nelle preimpostazioni, validata lato
  server, propagata ai tre referti scaricabili); nei risultati
  blocco con barre per profilo (valore sempre testuale, mai solo
  colore), descrizione di cosa premia ciascun assistente, indice
  composito, pesi del mercato, nota di onestà e "Top azioni
  prioritarie" con badge sforzo/quick-win e guadagno stimato per
  profilo. `citability` e `citability_actions` nel summary di
  `/api/status`.

- **Storico degli audit** (v2.1.0), per utente su SQLite: sezione
  dedicata con tabella delle esecuzioni (data, sito, punteggio con
  colore-soglia, delta rispetto al run precedente dello stesso
  sito, critici/avvertenze) e grafico SVG dell'andamento del
  punteggio complessivo con soglie 40/70 — primo widget "richiede
  storico" del concept board realizzato.
- **Avanzamento push** (v2.1.0): Server-Sent Events su
  `GET /api/events` (snapshot inviato a ogni variazione, flusso
  chiuso allo stato terminale) con ripiego automatico sul polling.
- **Preimpostazioni di configurazione** (v2.1.0): l'intero form si
  salva con un nome in localStorage (salva/carica/elimina), per
  riusare le configurazioni per cliente o sito.

- **Account utente** (v2.0.0): registrazione rapida (nome, email,
  password, accettazione condizioni di servizio con dichiarazione di
  proprietà del sito — pagina `gui/tos.html`) o login; il check
  richiede l'accesso, con limite di **un check all'ora per utente**
  (l'annullamento libera lo slot); il download dei referti richiede
  la **registrazione completa** (azienda e telefono, completabili
  dal profilo in qualsiasi momento) — vincolo applicato lato server
  (403), non solo nella UI. Utenti e sessioni su SQLite locale
  (`seo_rrf_gui.db`, escluso dal repo), password PBKDF2-SHA256 con
  salt per utente, cookie di sessione HttpOnly SameSite=Strict con
  scadenza a 7 giorni.

- **Audit annullabile** (v1.9.0): bottone "Annulla audit"
  nell'avanzamento e `POST /api/cancel`; lo stop è cooperativo
  (`stop_event` propagato a `run_audit`/`Fetcher`, che interrompe
  richieste, attese di throttle/backoff e download a blocchi con
  `AuditCancelled`). Stato `cancelled` distinto da errore; il job
  accetta subito un nuovo audit.

- **Layout a sezioni collassabili** (v1.7.x): configurazione,
  avanzamento e "Risultati dell'audit e referto" (unificati: pulsanti
  di download del referto dentro i risultati; dalla v1.7.1 senza
  anteprima incorporata — il referto HTML si apre in una nuova
  scheda) sono voci
  di un accordion Bootstrap Italia col tema Lympha. Il ciclo audit
  guida le sezioni: all'avvio si chiude la configurazione e si apre
  l'avanzamento, alla fine l'avanzamento si richiude (log sempre
  consultabile) e si aprono i risultati; il ripristino dopo un
  ricaricamento riapre direttamente i risultati.

- **Widget grafici di sintesi** (v1.5.0, GUI e referto HTML, stile
  brand Lympha): anello del punteggio complessivo con verdetto
  testuale e soglie dichiarate (40/70, mai solo colore), tile
  Critici/Avvertenze/Informazioni, donut dello stato pagine (senza
  rilievi / con rilievi / in errore), meter del consenso RRF con
  tacche alle soglie 20%/45%, tacca di parità sulle barre dello
  share of voice (tuo sito a colori, concorrenti in grigio). Nella
  GUI i punteggi per area sono pulsanti che aprono i rilievi
  dell'area e i risultati vengono ripristinati se la pagina viene
  ricaricata dopo un audit concluso.

- **Server in sola libreria standard** (nessuna dipendenza nuova):
  importa lo script, esegue `run_audit()` in un thread e da un'unica
  scansione produce tutti e tre i referti. API: `GET /api/env`
  (versioni, RAM disponibile, `--max-body` suggerito, disponibilità
  embeddings), `POST /api/audit` (validazione in italiano, un audit
  alla volta con `409`), `GET /api/status` (stato, log, sintesi,
  rilievi, esiti RRF), `GET /api/report/{html,json,text}` con
  `?download=1`.
- **Frontend Bootstrap Italia 2.18.2 in vanilla JavaScript**, asset
  vendorizzati in `gui/vendor` (CSS, bundle JS, font woff/woff2,
  sprite icone, licenza): funziona offline, nessun CDN. Modulo con
  tutti i parametri della CLI e suggerimenti contestuali, avanzamento
  in tempo reale con log, risultati nella pagina (punteggi, rilievi in
  fisarmonica, tabella del consenso RRF) e scarico del referto nei
  tre formati, con apertura del referto HTML in una nuova scheda.
- **Accessibilità (obiettivo WCAG 2.2 AA)**: lingua, landmark e
  gerarchia heading corretti, skip link, label/hint su ogni campo,
  errori sul campo + riepilogo con focus gestito, stati via
  `role="status"` (annunci solo ai cambi di fase), aree scorrevoli
  focalizzabili, gravità con testo + simbolo e contrasti ≥ 4.5:1,
  `prefers-reduced-motion` rispettato, contenuti dinamici solo via
  `textContent`. Struttura verificata con lint automatico (id, label,
  riferimenti ARIA, heading).
- **Sicurezza**: ascolto su 127.0.0.1, CSP senza origini esterne,
  `X-Content-Type-Options: nosniff`, protezione dal path traversal
  (testata), un audit alla volta.
- **Brand Lympha Technologies** (GUI v1.2.0): look & feel allineato a
  lymphatech.it riusandone il layer di token (`gui/brand/
  lympha-brand.css`, palette `--lt-*` con contrasti AA documentati)
  più il tema applicativo `gui/theme.css` (header bianco con marchio,
  bottoni teal, footer teal-900, focus arancione); logo
  `lympha-mark.svg` e favicon vendorizzati. Anche il referto HTML
  (script v1.2.1) adotta la palette del brand, il font Titillium Web
  e la firma "Lympha Technologies S.r.l." nel footer.
- **Esecuzione come servizio**: unit systemd
  `deploy/seo-rrf-gui.service` con utente dinamico senza privilegi,
  filesystem in sola lettura e riavvio automatico, per le
  installazioni presso i clienti.

## Monitoraggio citazioni IA — `seo_rrf_citations.py` v1.0.0

- Interroga assistenti IA con ricerca web sulle query target del sito
  (da file o riusate dal referto JSON dell'audit con `--from-audit`) e
  verifica per ogni risposta se il sito è **citato** fra le fonti,
  **consultato**, o sostituito dai **concorrenti** (max 3).
- Provider: **anthropic** (SDK ufficiale, `claude-opus-5` con
  strumento `web_search`, gestione `pause_turn`/`refusal`, fallback
  server-side attivo di default) e **perplexity** (Sonar). Chiavi API
  solo via variabili d'ambiente.
- **Storico JSONL** con delta fra esecuzioni, soglia `--fail-under`
  con codice d'uscita 1 per l'alerting, referti text/JSON, limiti di
  costo (max 15 query, max 5 ricerche per risposta, pausa fra query).
  Dalla GUI v2.9.0 lo storico è consultabile anche nell'interfaccia
  (grafico per provider e tabella).
- **Esecuzione periodica**: unit systemd `deploy/
  seo-rrf-citations.service` + `.timer` (settimanale, hardening,
  chiavi in `/etc/seorrf/citations.env`).
- Testato senza chiamate reali: server API finti locali per entrambi i
  provider (8 test dedicati).

## Qualità e verifica

- **CI su GitHub Actions** (`.github/workflows/ci.yml`): a ogni push
  e pull request, `flake8` + `pytest` su Python 3.10 e 3.12 e
  **audit di accessibilità Pa11y** (WCAG 2 AA) su pagine reali
  servite dalla GUI nel runner — condizioni di servizio, vista
  anonima e vista autenticata (raggiunta compilando davvero il form
  di registrazione con le azioni di Pa11y, config `.pa11yci.js`).
  Esito locale alla creazione: 3/3 pagine, 0 errori.
- **Protocollo di verifica manuale con screen reader**
  (`docs/ACCESSIBILITA.md`): flussi da testare con VoiceOver/NVDA,
  comportamento atteso per ciascuno e registro degli esiti da
  compilare a ogni sessione (la prima esecuzione umana è in TO-DO).

- **Suite pytest: 206 test in ~15 secondi** (`tests/`), senza rete
  esterna: nucleo numerico fissato sui valori calcolati a mano (idf
  BM25, saturazione della frequenza, coseno in [0,1], addendi RRF con
  k=60, rango da 1), chunking, deduplica, `norm_url`, query
  automatiche, `extract_jsonld`, `parse_page`, limite `--max-body`
  (Content-Length e chunked), retry sui transitori (503→200 al terzo
  tentativo, 404 mai ritentato, esaurimento tentativi, oversize non
  ritentato), confronto competitivo (dominanza del concorrente,
  concorrente vuoto, e2e su due siti fixture con verifica dei tre
  renderer e dei limiti CLI/GUI), rispetto opzionale del robots.txt
  (esclusione da sitemap e da crawling, rilievo informativo,
  comportamento predefinito invariato), end-to-end su un **sito
  fixture locale con difetti piantati** (GPTBot bloccato, pagina
  segnaposto, duplicato `/`↔`/index.html`, noindex, sezione vietata
  dal robots, risposta oversize da 12 MB) tutti rilevati, coerenza
  dei tre renderer con `k` propagato, codici di uscita CLI, API della
  GUI (CSP, traversal, validazione, `409`, ciclo completo, referti).
- `flake8` pulito su script, server GUI e test.
- Difetti trovati e corretti in fase di consegna della v1.0.0:
  mappatura heading→paragrafi in ordine di documento, deduplica
  `/`↔`/index.html`, query auto-generate degeneri, propagazione di
  `--rrf-k` ai renderer (dettaglio in
  [seo_rrf_audit.md](seo_rrf_audit.md)).

## File di servizio e documentazione

- `requirements.txt` (esecuzione) e `requirements-dev.txt`
  (pytest + flake8 + SDK anthropic per i test), `pytest.ini`.
- File `LICENSE` (MIT) alla radice del repository, coerente con la
  licenza dichiarata nei moduli.
- **Repository git** inizializzato su branch `main` con `.gitignore`
  (esclusi bytecode, venv, referti e storici generati a runtime;
  vendorizzati Bootstrap Italia e asset brand inclusi nel
  versionamento perché necessari all'esecuzione offline).
- [README.md](README.md) con diagrammi dell'infrastruttura (pipeline
  CLI e architettura GUI), [seo_rrf_audit.md](seo_rrf_audit.md) (nota
  tecnica di consegna con changelog),
  [audit_miaweb_rrf.html](audit_miaweb_rrf.html) (esempio di referto
  di consulenza per www.miaweb.art, curato a mano a partire dai dati
  dello strumento).

## Limiti noti e accettati (dettaglio in TO-DO)

- Il bypass dei `Disallow` del robots.txt richiede una dichiarazione:
  `--own-site` (titolarità) o `--ignore-robots accetto`
  (responsabilità esplicita). Dalla v1.13.0 il rispetto è il
  **default**; nella GUI il default resta "sito di mia titolarità"
  perché coperto dalle condizioni di servizio della registrazione.
- Il rendering JavaScript è seriale (vincolo dell'API sync di
  Playwright) e opzionale: senza Playwright/browser i siti
  client-side restano rilevati ma non analizzati.
- La stima dello sforzo nel piano di remediation è un classificatore
  a parole chiave a tre livelli: indicativa, non un preventivo.
- I profili di citabilità per assistente IA sono euristiche
  dichiarate (i pesi non derivano da comportamento documentato dai
  vendor): utili come confronto relativo, non come previsione di
  citazione — quella la misura `seo_rrf_citations.py`.
- Il giudizio LLM è **attivo di default** (modalità `auto`): con la
  chiave nell'ambiente ogni audit fa una richiesta API con costi a
  carico della chiave; il verdetto è il parere di un modello su un
  campione, non riproducibile né garanzia di citazione (nota
  inclusa in ogni referto). Senza chiave l'audit resta offline.
- Lavorazione multi-macchina: il working tree locale può contenere
  lavoro non ancora pushato — verificare `git status` e `git fetch`
  prima di riprendere lo sviluppo da un'altra postazione.
