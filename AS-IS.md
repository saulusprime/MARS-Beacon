# AS-IS — Stato di fatto del progetto

Fotografia di ciò che è **già realizzato e verificato** al 2026-08-03.
È il complemento di [TO-DO.md](TO-DO.md), che da qui in avanti elenca
solo ciò che resta da fare. Il quadro d'insieme e le istruzioni d'uso
sono nel [README.md](README.md).

## Strumento CLI — `seo_rrf_audit.py` v1.7.0

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
- **Rispetto opzionale del robots.txt** (v1.2.0): con
  `--respect-robots` gli URL vietati all'agente `SeoRrfAudit` non
  vengono scaricati, né dalla lista sitemap né durante il crawling
  BFS, e sono elencati nel referto come rilievo informativo.
  Predefinito spento: un audit del proprio sito ispeziona tutto.
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

## Interfaccia grafica locale — `seo_rrf_gui.py` v1.7.0 + `gui/`

- **Layout a sezioni collassabili** (v1.7.0): configurazione,
  avanzamento e "Risultati dell'audit e referto" (unificati: pulsanti
  di download e anteprima del referto dentro i risultati) sono voci
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
  fisarmonica, tabella del consenso RRF), anteprima del referto HTML
  in iframe sandbox e scarico nei tre formati.
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
- **Esecuzione periodica**: unit systemd `deploy/
  seo-rrf-citations.service` + `.timer` (settimanale, hardening,
  chiavi in `/etc/seorrf/citations.env`).
- Testato senza chiamate reali: server API finti locali per entrambi i
  provider (8 test dedicati).

## Qualità e verifica

- **Suite pytest: 69 test in ~5 secondi** (`tests/`), senza rete
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

- Il rispetto dei `Disallow` del robots.txt è **opzionale e spento di
  default** (`--respect-robots`): la scelta è deliberata per l'audit
  del proprio sito, ma va ricordata quando si analizzano siti altrui.
- L'audit avviato dalla GUI non è annullabile (esecuzione in-process).
- Nessuna CI.
