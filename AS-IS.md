# AS-IS — Stato di fatto del progetto

Il prodotto si chiama **MARS Beacon** (Meta-fusion, Accessibility,
Ranking & Security Audit) dal 2026-08-05, in vista dell'integrazione
di Lighthouse; dal 2026-08-04 al 2026-08-05 "MARS Audit", in
precedenza "Audit SEO & Reciprocal Rank Fusion". Anche il repository
GitHub è stato rinominato (`SEO-RRF` → `MARS-Beacon`, i vecchi URL
sono rediretti da GitHub). Dal 2026-08-05 anche i file sono
rinominati: `seo_rrf_audit.py` → `mars_audit.py`, `seo_rrf_gui.py` →
`mars_gui.py`, `seo_rrf_citations.py` → `mars_citations.py`,
`seo_rrf_audit.md` → `mars_audit.md`, unit systemd `seo-rrf-*` →
`mars-*`.

Fotografia di ciò che è **già realizzato e verificato** al 2026-08-05.
È il complemento di [TO-DO.md](TO-DO.md), che da qui in avanti elenca
solo ciò che resta da fare. Il quadro d'insieme e le istruzioni d'uso
sono nel [README.md](README.md).

## Strumento CLI — `mars_audit.py` v1.59.0 (+ package `marsbeacon/`)

- **Grafo dei link, motore evoluto** (v1.59.0, GUI v2.30.0,
  2026-08-05) — in vanilla JavaScript su entrambe le superfici
  (GUI e referto HTML): **simulazione a forze viva** (repulsione,
  molle sugli archi, richiamo al centro, smorzamento) seminata dal
  layout deterministico del core — il disegno iniziale resta
  identico e stampabile, la fisica **si sveglia al trascinamento**
  e si spegne da sola quando l'energia si esaurisce; **vista ad
  anelli di profondità** commutabile (un anello per click dalla
  home, soglia dei 3 click marcata, senza-percorso sull'anello
  esterno; transizione animata che preserva gli angoli);
  **frecce direzionali** sugli archi (marker SVG, archi accorciati
  al bordo del nodo, evidenziate col vicinato); **evidenziazione
  bloccabile col clic** (Esc o clic sullo sfondo la libera, stato
  annunciato nella regione di stato); dettagli con **link in
  ingresso e in uscita** (conteggio nel `<title>` lato server, già
  localizzato); in GUI anche la **ricerca per percorso** (le
  pagine corrispondenti restano evidenziate, esito annunciato);
  legenda testuale (mai solo colore) e bottoni-vista con
  `aria-pressed`. **`prefers-reduced-motion` spegne ogni
  animazione**: resta la resa statica, pienamente fruibile.
  Suite verde, AT 31/31, JS validato con `node --check` su
  entrambe le superfici.

- **Scomposizione in moduli** (v1.58.0, 2026-08-05, dal P3): le
  10.050 righe del file singolo vivono ora nel package
  **`marsbeacon/`** — `base` (costanti, regex, modelli dati),
  `crawler` (fetch, robots, scoperta, parsing, rendering JS,
  chunking, deduplica), `indexes` (BM25, vettoriale, RRF, grafo,
  treemap), `audits` (controlli per area, punteggi, citabilità,
  storico, giudizio, Lighthouse, ancora di realtà), `render`
  (cinque renderer, cataloghi i18n, CSS/JS del referto, brand) —
  con **`mars_audit.py` ridotto a facciata** (~1.100 righe):
  docstring, riesportazione esplicita di ogni nome (pubblici e
  `_privati`), `run_audit`, `build_parser`, `main`.
  **`python3 mars_audit.py URL`, la GUI (`import mars_audit`) e le
  unit systemd restano identici**; il deploy copia anche
  `marsbeacon/`. Metodo: split meccanico assistito da AST
  (segmenti contigui, import per modulo calcolati sui riferimenti
  reali, tre sole ricollocazioni imposte dai riferimenti in
  avanti: `build_remediation`, blocco Lighthouse, `dedupe_pages`);
  nei test l'helper `_patch` applica i monkeypatch sulla facciata
  **e** su ogni modulo che espone il nome — dopo lo split conta il
  namespace del consumatore. Percorsi da `__file__` (fork
  Lighthouse, brand) rebasati alla radice del repository. Suite
  completa verde e AT 31/31 sul codice scomposto; flake8 pulito su
  facciata e package (lint CI esteso a `marsbeacon/`).

- **Brand incorporato nel referto HTML** (v1.57.0, 2026-08-05, dal
  P2): il footer porta il **marchio SVG inline** (25,6 KB,
  vettoriale, `aria-label` preservata, tile con angoli
  arrotondati) e il `<style>` incorpora i font **Titillium Web
  regular e bold** come data URI woff2 (~47 KB in base64): la resa
  offline non dipende più dai font di sistema. Valutazione
  dichiarata: i pesi 600/800 usati dal CSS ripiegano sul 700 per
  la regola di font-matching CSS — incorporarli sarebbe costato
  altri ~25 KB per una resa quasi identica; il referto passa da
  ~62 a ~129 KB (example.com), accettabile per un deliverable di
  consulenza. **Fallback pulito e dichiarato**: senza gli asset
  accanto allo script (distribuito senza gli asset della GUI) restano
  firma testuale e font di sistema — mai incorpori parziali. Test
  dedicato su incorporo e fallback.

- **Ancora di realtà** (v1.56.0, 2026-08-05, dal P2):
  `--search-check auto|on|off` (default `auto`) — `run_search_check`,
  passo separato dopo `run_audit()` col pattern del giudizio LLM:
  interroga la **Brave Search API** (chiave solo da `BRAVE_API_KEY`,
  endpoint sovrascrivibile con `BRAVE_BASE_URL` per i test) sulle
  query della simulazione e cerca il sito nei **primi 20 risultati**
  (host normalizzato, `www.` incluso), affiancando al consenso RRF
  simulato la posizione reale o l'assenza. Max 10 query, una
  richiesta al secondo (rate limit Brave), errori per query che non
  fermano le altre, salto dichiarato senza chiave (`on` la pretende:
  errore d'uso). Sezione nei referti text/html/md (con la **nota di
  onestà sempre inclusa**: il ranking dipende anche da
  personalizzazione, località e freschezza — confronto direzionale,
  non validazione), blocco additivo `search_check` nel JSON. 6 test
  col **server Brave finto locale** (posizioni e confronto RRF,
  errori, salto, renderer, CLI) e chiavi rimosse dall'ambiente in
  conftest: suite offline per costruzione. Complementare a
  `--queries-gsc` (domande vere ↔ ranking vero). Dalla GUI v2.29.0
  l'opzione è anche nel form, con sezione nei risultati.

- **Delta Lighthouse fra esecuzioni** (v1.55.0, GUI v2.27.0,
  2026-08-05): `history_payload` accetta il blocco `lighthouse` e
  scrive nella riga compatta dello storico i **punteggi di
  categoria** (solo con Lighthouse eseguito); `compute_delta`
  restituisce la chiave additiva `lighthouse` — delta per
  categoria, per le categorie presenti in entrambe le esecuzioni —
  normalizzando le due forme (blocco del referto JSON completo e
  lista compatta dello storico). Il delta della **sesta area** era
  già automatico (confronto generico sulle chiavi di `scores`).
  Nella GUI il blocco "Rispetto all'esecuzione precedente" e il
  confronto fra due audit scelti mostrano i delta di categoria
  accanto a quelli d'area ("Lighthouse Prestazioni: ▲ +5", frecce
  testuali del meccanismo esistente); vale anche per il
  monitoraggio CLI con `--history`. 2 test dedicati (riga di
  storico con/senza Lighthouse; delta fra le due forme, categoria
  assente esclusa).
- **Metriche CWV nel blocco `lighthouse`** (v1.54.0, 2026-08-05):
  `lighthouse_report_data` estrae LCP, CLS, TBT (proxy dell'INP),
  FCP e Speed Index dai LHR — **valore peggiore fra le pagine
  esaminate**, `displayValue` già localizzato, verdetto
  buono/da migliorare/scarso dalle **soglie ufficiali
  Lighthouse/web.dev** dichiarate in `LIGHTHOUSE_CWV`; metriche
  assenti dal LHR: nessuna voce, mai valori inventati. Campo
  `metrics` additivo (JSON e sintesi GUI); i referti non lo
  rendono — la decisione di accantonare la sezione metriche nei
  referti resta valida, il pannello vive in GUI.

- **JavaScript inline nel referto HTML: treemap e grafo
  interattivi** (v1.53.0, GUI v2.23.0, 2026-08-05 — decisione che
  **ribalta il vincolo "referto senza JavaScript"**): il referto
  resta un file unico senza origini esterne e il JS è progressive
  enhancement puro — legge il DOM (attributi `data-*`, `<title>`),
  nessun payload proprio; senza JavaScript o in stampa resta l'SVG
  statico (controlli nascosti dal CSS di stampa). **Treemap della
  superficie contenutistica**, widget nuovo: rettangoli = pagine,
  area ∝ parole indicizzabili, colore dalla gravità dei rilievi
  che citano la pagina; layout squarified deterministico calcolato
  nel core (`_squarify`, Bruls-Huizing-van Wijk; `treemap_data`,
  max 40 pagine), rettangoli focusabili da tastiera con dettagli
  in regione di stato e **tabella di fallback** in un `<details>`.
  **Grafo dei link interattivo anche nel referto**, in parità con
  la GUI: zoom con rotella o pulsanti, pan, trascinamento dei
  nodi, evidenziazione del vicinato al passaggio o al focus con
  dettagli in regione di stato. Catalogo `_HTML_I18N` esteso
  (`tm.*`, `lg.*`, it+en). La GUI serve il referto HTML con una
  **CSP dedicata** (`REPORT_CSP`: `script-src 'unsafe-inline'`
  solo su `/api/report/html`; le pagine della GUI restano sotto la
  CSP stretta). Test: squarify (area, limiti, proporzioni),
  gravità della treemap, markup del referto, CSP del referto
  contro quella standard; JS validato con `node --check` e referto
  reale multi-pagina verificato.
- **i18n dei rilievi Lighthouse: il catalogo è Lighthouse stesso**
  (v1.52.0, 2026-08-05 — decisione del bullet i18n P1): niente
  catalogo interno da ~160 voci. Nei referti EN i testi inglesi
  arrivano dai **file di locale del fork installato**
  (`shared/localization/locales/en-US.json`, caricato pigramente e
  una sola volta), risalendo per ogni audit al messaggio che ne ha
  prodotto titolo e description tramite `i18n.icuMessagePaths` del
  LHR (mappa inversa percorso → id messaggio). Il parser salva
  `title_en`/`fix_en`/`cat_title_en` nei params (additivi, con
  `display` ed `evidence` strutturati) e `finding_texts()` li
  ricompone per le chiavi `lh.*` con la cornice inglese
  (Pages/Evidence/Score). **Fallback dichiarato campo per campo**
  come per `_FINDINGS_EN`: senza file di locale, senza mappatura o
  con placeholder ICU residui resta l'italiano (oggi accade al
  titolo della categoria agentic-browsing, non ancora localizzato
  da upstream). Il canonico italiano resta intatto per storico e
  ancore. 4 test dedicati (traduzione, fallback, scarto ICU,
  OK/errori); verificato dal vivo su example.com — "Document does
  not have a main landmark", "Lighthouse Performance: no findings"
  nel referto EN.
- **Lighthouse nei referti di tutti i formati** (v1.51.0,
  2026-08-05): sezione "Audit Lighthouse" nella sintesi di text,
  html e md — quando eseguito: pagine, device, tag del fork e
  punteggi di categoria (tabella HTML con soglie 90/50, valore
  sempre testuale); quando saltato: **salto dichiarato col
  motivo** nel referto, pattern del giudizio LLM; quando spento:
  nessuna menzione. Il JSON porta il blocco additivo `lighthouse`
  (status, mode, device, fork, pagine, errori, categorie con
  medie 0–100) — `schema_version` invariato. Il CSV non cambia:
  l'origine è già dichiarata da area e chiavi `lh.*`. Le ancore
  `#r-…` restano stabili anche per i rilievi Lighthouse (conteggi
  normalizzati dal meccanismo esistente, verificato). Catalogo
  `_HTML_I18N` esteso con le chiavi `lh.*` in it e en (parità
  verificata dai test esistenti). 3 test in più ed estensioni
  agli e2e: blocco JSON in ok e in salto, dichiarazione nei tre
  formati di prosa, stabilità delle ancore.
- **Deduplica e sesta area pesata** (v1.50.0, 2026-08-05): i
  rilievi Lighthouse entrano nei referti. **Deduplica** con la
  tabella esplicita `LIGHTHOUSE_DEDUP` (15 audit: title, meta
  description, alt, lang, viewport, charset, HTTPS, hreflang,
  canonical, robots.txt, noindex, status code, link descrittivi,
  llms.txt): il rilievo MARS resta canonico e la conferma
  Lighthouse si aggiunge come **evidenza** al dettaglio
  ("Conferma Lighthouse: … (punteggio N/100)", `lh_confirm` nei
  params per il futuro badge GUI); se MARS non ha un rilievo
  corrispondente — o ha solo un OK: divergenza fra i due
  strumenti — il rilievo Lighthouse resta perché porta
  informazione nuova; gli audit fuori tabella (contrasto,
  landmark…) restano sempre (`merge_lighthouse_findings`).
  **Sesta area** `AREA_LIGHTHOUSE` con peso 1.0 in
  `overall_score()` (`lighthouse_area_score`: media semplice
  delle categorie, ognuna mediata sulle pagine); senza Lighthouse
  l'area non esiste e i pesi si rinormalizzano da soli — gli
  storici restano confrontabili. I quattro renderer iterano
  `ALL_AREAS` (aree vuote saltate): rilievi Lighthouse in tutti i
  formati, nel piano di remediation (sforzo classificato) e nel
  gate `--fail-under`/exit code. 8 test in piu' (merge,
  divergenza, fuori tabella, media area, rinormalizzazione del
  complessivo, e2e col referto JSON su sito fixture); verificato
  dal vivo su example.com — conferme su charset e meta
  description, divergenza conservata sui link non descrittivi.
- **Parser LHR → Finding** (v1.49.0, 2026-08-05):
  `lighthouse_findings()` converte i LHR del runner in rilievi
  MARS della **sesta area** `AREA_LIGHTHOUSE` ("Performance
  (Lighthouse)"). Un rilievo per audit, aggregato su tutte le
  pagine (punteggio peggiore, peso massimo, URL riuniti); gravità
  dai **bucket ufficiali Lighthouse**: sotto 0,9 il rilievo
  esiste, sotto 0,5 con peso ≥ 3 nel punteggio di categoria è
  critico, peso 0 è informativo; gli audit senza punteggio
  (informative/manual/notApplicable/error) non generano rilievi.
  `pillar` dalla mappatura di progetto `LIGHTHOUSE_PILLARS`
  (Performance/Accessibilità/Agentic → accessibility, SEO →
  ranking, Best Practices → security); chiave di catalogo
  `lh.<categoria>.<audit-id>` con `params` (audit, categoria,
  score, peso, URL) pronti per deduplica e i18n. Evidenze dagli
  `items` dei details (URL, selettore/snippet del nodo,
  etichetta), `displayValue` nel dettaglio, description del LHR
  senza i link Markdown come correzione. Il runner passa
  **`--locale=it`** alla CLI del fork: titoli e description
  arrivano già in italiano dal LHR (niente inglese nel referto
  canonico). Categorie senza audit sotto soglia → un solo rilievo
  OK con la media; errori del runner → rilievo informativo. I
  rilievi viaggiano in `run_lighthouse()["findings"]`; l'ingresso
  nei referti e nei punteggi è il prossimo passo (deduplica +
  sesta area pesata). 7 test dedicati con LHR finti; verificato
  end-to-end reale su example.com (rilievi in italiano, gravità e
  pilastri coerenti).
- **Runner Lighthouse** (v1.48.0, 2026-08-05): `run_lighthouse()`,
  passo separato dopo `run_audit()` col pattern del giudizio LLM
  (None con off; dict con status "ok" oppure "skipped" col motivo
  dichiarato). Selezione pagine `select_lighthouse_pages()`: home +
  N rappresentative con euristica dichiarata — link interni in
  ingresso, poi vicinanza alla home (riusa il grafo dei link
  dell'audit; i dati di traffico non esistono offline). Un processo
  Node per pagina (`--output=json --quiet`, `--preset=desktop` col
  device desktop, `CHROME_PATH` dal rilevamento runtime), attesa a
  piccoli passi con **timeout per pagina** (120 s: kill e
  fallimento dichiarato), pausa `--delay` fra le pagine e
  **annullamento cooperativo** che uccide il processo Node
  (terminate, poi kill); gli errori di una pagina — avvio, uscita
  non zero, LHR malformato — non fermano mai le altre né l'audit.
  Log con la sintesi dei punteggi per categoria. 8 test col
  processo finto al posto di `subprocess.Popen` (comando e
  ambiente, preset, timeout, annullamento, errori per pagina,
  selezione): la suite non richiede Node; verificato anche
  end-to-end reale su example.com. I LHR raccolti alimenteranno il
  parser LHR → `Finding` (prossimo passo P1).
- **Flag Lighthouse nella CLI** (v1.47.0, 2026-08-05):
  `--lighthouse off|auto|always` (default `off`; `auto` esegue solo
  se fork, Node ≥ 22.19 e Chrome ci sono, altrimenti **salto
  dichiarato** nel log; `always` li pretende — errore d'uso col
  motivo, pattern di `--judge on`), `--lighthouse-pages N` (pagine
  rappresentative oltre la home, 0–9, default 3) e
  `--lighthouse-device mobile|desktop` (emulazione e throttling,
  default mobile). Parametri validati in `main`; dalla v1.48.0 la
  risoluzione vive nel passo separato `run_lighthouse()`. Test CLI
  in `tests/test_lighthouse.py` (5 in più:
  default, scelte invalide, intervallo pagine, `always` senza
  requisiti, salto dichiarato end-to-end sul sito fixture).
- **Rilevamento runtime Lighthouse** (v1.46.0, GUI v2.22.0,
  2026-08-05): dettaglio nella sezione "Fork Lighthouse" più sotto.
- **File rinominati `mars_*`** (v1.45.0, GUI v2.21.0, citations
  v1.2.0, 2026-08-05): script, nota tecnica e unit systemd coerenti
  col nome MARS Beacon (`git mv`, riferimenti aggiornati in codice,
  test, CI, docs e deploy). Cookie di sessione ora `mars_session` e
  download rinominati `referto-mars`/`rilievi-mars`; la chiave
  localStorage dei preset resta `seo_rrf_presets` per non perdere le
  preimpostazioni già salvate, e il token robots.txt resta
  `SeoRrfAudit` (le regole già scritte dai siti restano valide).
- **Rename in MARS Beacon** (v1.44.0, GUI v2.20.0, 2026-08-05):
  nome prodotto aggiornato in referti (text/html/md), docstring,
  `--help`, GUI (header, titolo, condizioni di servizio), unit
  systemd e URL del progetto nello User-Agent; repository GitHub
  rinominato in `MARS-Beacon` con descrizione "MARS Beacon:
  Meta-fusion, Accessibility, Ranking & Security Audit". Il token
  robots.txt resta `SeoRrfAudit` per non invalidare le regole già
  scritte dai siti auditati.

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
- **Varietà degli anchor interni** (v1.30.0, da Features.md —
  ultimo dei nove controlli del concept, ora tutti realizzati):
  coppie (testo, destinazione) deduplicate sull'intero sito (il
  menu ripetuto conta una volta), varietà = testi unici / coppie
  uniche con soglia di prassi 80%; sotto, avvertenza con i testi
  ambigui come evidenza ("leggi tutto" → N destinazioni) ed
  esempio prima/dopo. Estende le anchor generiche nell'area
  tecnica.
- **Meta di base** (v1.29.0, da Features.md): charset, viewport e
  completezza Open Graph (gli `og:*`, estratti dalla v1.0, ora
  vengono valutati: assenti o senza la triade
  title/description/image → avvertenza con l'elenco di cosa manca
  per URL, sforzo "minuti"); tutto a posto → un solo OK.
- **HTML semantico e divitis** (v1.28.0, da Features.md): conteggio
  per pagina dei tag di sezionamento e del rapporto `<div>`/
  elementi (anche sul DOM renderizzato); avvertenze con soglie di
  prassi — meno di 2 tipi di tag semantici (scheletro
  `<main><article><section>` nel fix) e più di metà `<div>`
  (percentuale per URL come evidenza); pagine sotto i 30 elementi
  escluse. Nell'area dati strutturati (lente Qwen).
- **Freschezza dei contenuti** (v1.27.0, da Features.md): età
  dell'aggiornamento dichiarato più recente (meta article:*_time e
  date JSON-LD), soglie di prassi a un anno (avvertenza) e due
  anni (peso doppio), pagine più datate come evidenza e fix con
  meta datato a oggi; senza alcuna data nessun rilievo — la
  presenza è già coperta dall'E-E-A-T, niente doppia punizione.
- **Riferimenti bibliografici** (v1.26.0, da Features.md): sezione
  fonti negli heading (cinque lingue), citazioni accademiche nel
  testo (`[1]`, "(Autore, anno)") e link esterni come contesto
  dichiarato; OK con una sezione fonti o almeno 3 citazioni,
  altrimenti avvertenza con esempio di sezione Fonti pronto.
  Completa l'E-E-A-T nell'area semantica (lente Kimi).
- **Ciclo di vita dell'argomento** (v1.25.0, da Features.md):
  copertura in title e heading H1–H4 delle sei sezioni canoniche —
  definizione, storia, casi d'uso, limiti, FAQ, prospettive
  (cinque lingue) — valutata sull'intero sito; 5+/6 OK con
  evidenze, sotto scatta l'avvertenza (peso 2 se coperte ≤ 2) con
  l'elenco delle mancanti e un canovaccio di heading nel fix.
  Nell'area semantica (lente Kimi), sforzo "giorni".
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
- **Gate di regressione e audit periodico come servizio** (v1.40.0):
  `--fail-under PUNTI` esce con codice 1 anche quando il punteggio
  complessivo scende sotto la soglia (0–100, validata; motivo
  dichiarato su stderr), in aggiunta all'uscita 1 sui critici — il
  "`--fail-under`-equivalente" già in uso nel monitor citazioni. Lo
  sfruttano le unit `deploy/mars-audit.service` + `.timer`
  (settimanale il mercoledì, stesso hardening delle altre unit,
  `--history` su `/var/lib/seorrf/audit.jsonl`, referto HTML
  persistito, giudizio LLM opzionale via `citations.env`): il
  fallimento del servizio è la notifica di regressione, e la unit
  modello `deploy/mars-notify@.service` la trasforma in webhook
  attivo (ntfy/Slack/Teams) agganciabile con `OnFailure=` anche al
  monitoraggio citazioni.
- **Chrome di sistema multipiattaforma** (v1.43.1): `CHROME_PATHS`
  ora copre anche macOS e Windows (prima solo Linux), quindi il
  ripiego del rendering JavaScript sul browser di sistema funziona
  ovunque; su macOS il test di integrazione col browser reale non
  viene più saltato (suite 285/285 senza skip con Chrome
  presente).
- **i18n completa dei referti** (v1.43.0): `--lang it|en` traduce
  cornice **e rilievi** nei formati html, text, md e csv.
  Architettura: i ~125 punti di creazione dei `Finding` mantengono
  i testi italiani canonici (output italiano identico per
  costruzione, storico e ancore intatti) e portano `key` +
  `params`; il catalogo `_FINDINGS_EN` (solo inglese, ~120 voci
  con template `%(nome)s` per title/detail/fix/example) viene
  applicato al rendering da `finding_texts()`, con fallback
  campo per campo sull'italiano se chiave o parametri non
  combaciano — un template rotto non interrompe mai il referto.
  Il piano di remediation e le top azioni propagano chiave e
  parametri; le evidenze citate dal sito (URL, estratti, titoli
  del confronto storico) restano nella lingua del sito, con nota
  dichiarata in testa al referto EN. Il JSON resta canonico in
  italiano ed espone `key`/`params` per rilievo (campi additivi,
  schema invariato) cosi' le integrazioni traducono da sole.
  Test in `tests/test_i18n.py`: validazione di tutti i template,
  fallback, audit reale sul sito fixture con verifica che ogni
  rilievo abbia chiave e traduzione effettiva, nessuna stringa di
  cornice italiana nei referti EN (e viceversa), intestazioni CSV.
- **Tipologie MARS sui rilievi** (v1.42.0): ogni `Finding` porta il
  campo `pillar` (`meta-fusion` / `accessibility` / `ranking` /
  `security`) — di default derivato dall'area (`AREA_PILLARS`:
  Tecnica→accessibility, Lessicale/Semantica/Dati
  strutturati→ranking, RRF→meta-fusion), con override esplicito sui
  controlli di sicurezza dell'area tecnica (HTTPS, URL ancora in
  http, opt-out IA Microsoft noarchive/nocache). Esposto in
  `as_dict`/JSON come campo additivo (schema_version invariato);
  la GUI lo usa per separare i risultati. Test in
  `tests/test_pillars.py`.
- **Referto HTML: stampa, ancore e cornice bilingue** (v1.41.0):
  CSS `@media print` (palette chiara forzata, interruzioni di
  pagina che non spezzano rilievi/righe/tile, URL delle fonti
  esplicitati nel footer, `print-color-adjust` per i colori di
  verdetto) — la stampa del browser produce un PDF pulito senza
  dipendenze; **ancore stabili per rilievo** (`#r-…` derivate
  dalla chiave storica: i conteggi nei titoli diventano "n", il
  link resta valido fra esecuzioni; duplicati con suffisso), con
  permalink "#" su ogni rilievo, link dai Top rilievi e dal piano
  di remediation al rilievo esteso ed evidenziazione `:target`;
  **`--lang it|en`** per la cornice del referto HTML (catalogo
  `_HTML_I18N` con ~90 chiavi per lingua: sezioni, tabelle,
  legende, aria-label, footer) — i rilievi e i testi generati
  dall'audit restano in italiano e con `en` il referto lo dichiara
  in testa; gli altri formati non sono toccati. Test dedicati in
  `tests/test_report_html.py` (stabilità delle ancore, CSS di
  stampa, parità di chiavi fra i cataloghi, cornice en con nota).
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
  (parametri esposti dalla v1.31.0: `--top-n` per i posti fusi,
  `--rrf-weights` per la variante pesata `Σ wᵢ/(k+rankᵢ)`,
  `--chunk-words` per il taglio dei chunk — tutti anche in GUI e
  echeggiati nel JSON per la riproducibilità;
  sentence-transformers con **auto-rilevamento** dalla v1.6.0 —
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
- **Query di prova** da file (`--queries`), **reali da Google
  Search Console** (`--queries-gsc`, v1.32.0: export CSV del
  rapporto Rendimento, intestazioni it/en, prime 15 per clic e
  impressioni deduplicate) o auto-generate dai bigrammi tematici
  di heading e title, senza query degeneri.
- **Cinque formati di referto** (`text`, `json`, `html` autonomo con
  tema chiaro/scuro, e dalla v1.34.0 `md` — Markdown per issue/PR
  col piano di remediation come task list spuntabile — e `csv` —
  rilievi una riga ciascuno per Excel/Sheets, `;` e BOM) su stdout
  o file; codici di uscita `0/1/2/130` adatti all'uso come gate in
  CI. Dalla v1.33.0 il JSON (e le righe dello
  storico `--history`) dichiara **`schema_version`** (oggi `1`),
  incrementato solo per cambi incompatibili della struttura: è il
  numero su cui le integrazioni fanno il gate.
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
  20 s; PEP8, `flake8` pulito, licenza dichiarata nel modulo.

## Interfaccia grafica locale — `mars_gui.py` v2.30.0 + `gui/`

- **Grafo dei link, motore evoluto** (v2.30.0, 2026-08-05): vedi
  la voce v1.59.0 dello strumento CLI — fisica viva, anelli di
  profondità, frecce, pin col clic, ricerca per percorso.

- **Ancora di realtà nella GUI** (v2.29.0, 2026-08-05): select nel
  form (Auto / Obbligatoria / Spenta, quarta colonna della riga
  Lighthouse) con **avviso di disponibilità da `/api/env`**
  (`search_check_available`/`search_check_reason`, pattern del
  giudizio LLM: senza chiave il suggerimento dichiara il motivo e
  in auto il passo si salta); `on` validata lato server contro la
  disponibilità reale; campo nelle preimpostazioni. Il job esegue
  `run_search_check` dopo il giudizio (log in streaming), il blocco
  va in sintesi e ai cinque referti scaricabili. Nei risultati la
  sezione "Ancora di realtà (Brave Search)" **subito dopo la
  tabella del consenso RRF**: intro col conteggio, tabella query →
  posizione reale (o assenza dai primi 20, o errore) → consenso
  RRF, nota di onestà nella caption, area scorrevole focalizzabile
  come le altre tabelle. 3 test nuovi (validazione, e2e col passo
  finto fino ai referti, chiavi in `/api/env`); AT 31/31
  riconfermata col campo nuovo, `app.js` validato con
  `node --check`.

- **Unit systemd riviste per Lighthouse** (v2.28.0, 2026-08-05,
  chiude "Documentazione e deploy" della P1): `mars-audit.service`
  ora esegue l'audit periodico con `--lighthouse auto` (senza
  requisiti: salto dichiarato, il servizio non fallisce per
  questo) e documenta i prerequisiti — Node ≥ 22.19 **di sistema**
  (il PATH di systemd non vede nvm e `ProtectHome` blocca /home;
  `Environment=PATH` di esempio commentato), Chrome/Chromium,
  `tools/update-lighthouse.sh` da `/opt/seorrf` (il checkout resta
  in sola lettura), sysctl per gli user namespace su Debian.
  Entrambe le unit hanno `Environment=HOME=%S/seorrf` (Chrome
  headless con l'utente dinamico non ha una home) e la **nota di
  hardening motivata**: mai `MemoryDenyWriteExecute` (JIT di
  Node/V8) né `RestrictNamespaces` (la sandbox di Chrome richiede
  user/pid/net namespace; `--no-sandbox` sarebbe un hardening
  peggiore). Sistemato anche un **difetto latente**: il database
  della GUI era fisso accanto allo script, illeggibile in
  scrittura sotto `ReadOnlyPaths=/opt/seorrf` — ora `MARS_GUI_DB`
  lo sposta (unit: `StateDirectory=seorrf` +
  `MARS_GUI_DB=%S/seorrf/mars_gui.db`), con test dedicato. Unit
  validate con `systemd-analyze verify` (unico rilievo: i percorsi
  `/opt/seorrf` assenti sulla macchina di sviluppo, atteso).
- **Accessibilità delle viste Lighthouse verificata**
  (2026-08-05, chiude la sezione GUI della P1): il lint di
  struttura/contratto ARIA (`tools/verifica_at.py`) copre le viste
  nuove — etichette dei tre campi del form, chip di categoria e
  pannello CWV con verdetti testo + simbolo e nota "laboratorio",
  badge di origine e di conferma — popolate da uno **stub di
  `run_lighthouse`** (nessuna dipendenza da Node/fork: verifica
  indipendente dalla macchina). **31/31 controlli superati**;
  contrasti dei colori nuovi verificati a calcolo (6,48–10,24:1,
  soglia AA 4,5:1). `docs/ACCESSIBILITA.md` aggiornato: §1.1,
  flussi 3 e 5 estesi, nuovo flusso 8 per il referto HTML
  interattivo (treemap e grafo: focus da tastiera, regioni di
  stato, tabella di fallback, resa statica senza JS), registro
  degli esiti.
- **Delta Lighthouse nello storico** (v2.27.0, 2026-08-05): vedi
  la voce v1.55.0 dello strumento CLI — il job passa il blocco
  `lighthouse` a `history_payload` e i due confronti della GUI
  (esecuzione precedente e audit scelti) mostrano i delta di
  categoria.

- **Fase Lighthouse annunciata** (v2.26.1, 2026-08-05): la regione
  di stato dell'avanzamento annuncia anche le righe di testa di
  Lighthouse — avvio ("Lighthouse: N pagine (mobile), timeout…"),
  salto dichiarato ed esito — oltre alle fasi numerate `[N/5]`; le
  righe per pagina sono indentate e non generano annunci (annunci
  solo ai cambi di fase, come da protocollo). Con questo il bullet
  "Avanzamento" della P1 è completo: le righe di log arrivavano
  già via SSE e "Annulla audit" uccide già il processo Node
  (`stop_event` propagato dalla v2.24.0). AT 27/27.
- **Sintesi Lighthouse: categorie e pannello Core Web Vitals**
  (v2.26.0, 2026-08-05): sotto i punteggi per area il blocco
  "Audit Lighthouse" mostra le **chip delle categorie** (titolo +
  punteggio con simbolo ✓/!/✕ alle soglie 90/50 — mai solo
  colore) e il **pannello CWV**: una tile per metrica (LCP, CLS,
  TBT proxy INP, FCP, Speed Index) con valore `displayValue`,
  verdetto testuale dalle soglie ufficiali e **nota di onestà
  sempre visibile** (valore peggiore fra le pagine; dati lab, non
  CrUX; l'INP reale non è misurabile in laboratorio). Con salto
  dichiarato la sintesi mostra "Non eseguito: <motivo>"; con
  Lighthouse spento nessuna menzione, e la riga "n/d" spuria
  della sesta area sparisce dai punteggi (le aree assenti non
  generano righe; l'indice d'area per l'apertura dei rilievi
  resta corretto). Verifica strumentale AT 27/27; `app.js`
  validato con `node --check`.
- **Gruppo Lighthouse nel form** (v2.25.0, 2026-08-05): riga
  dedicata nel modulo con select di attivazione (Spento / Auto: se
  Node e Chrome ci sono / Obbligatorio), select del dispositivo
  (mobile/desktop) e campo numerico delle pagine oltre la home
  (0–9, default 3, validato client e server). **Avviso di
  disponibilità da `/api/env`** col pattern sentence-transformers:
  senza i requisiti il suggerimento diventa "Non disponibile sul
  server: <motivo>. In auto l'audit viene semplicemente saltato";
  coi requisiti mostra il tag del fork installato. Campi nelle
  preimpostazioni (`PRESET_FIELDS`) e nella validazione numerica
  client (`NUMERIC_FIELDS`); label, hint `aria-describedby` e
  `invalid-feedback` come gli altri campi. Verifica strumentale AT
  27/27 con Chrome reale, `app.js` validato con `node --check`.
- **Lighthouse nei risultati** (v2.24.0, 2026-08-05): il server
  accetta e valida `lighthouse`, `lighthouse_pages` e
  `lighthouse_device` in `POST /api/audit` (messaggi in italiano;
  `always` validato contro la disponibilità reale, pattern del
  giudizio obbligatorio) ed esegue `run_lighthouse` nel job — le
  righe di log arrivano in streaming nella GUI via redirect dello
  stderr e **"Annulla audit" uccide anche il processo Node**
  (`stop_event` propagato) — poi fonde i rilievi (deduplica del
  core) e la sesta area nei punteggi; il blocco `lighthouse` va ai
  cinque referti scaricabili e nella sintesi di `/api/status`.
  Frontend: sesta area nelle fisarmoniche, rilievi smistati nei
  quattro pilastri via campo `pillar` (meccanismo esistente,
  nessun accordion di primo livello nuovo), **badge di origine
  "Lighthouse"** sui rilievi del fork (chiavi `lh.*`) e badge
  **"confermato da Lighthouse"** sui rilievi MARS arricchiti dalla
  deduplica (`lh_confirm` nei params); contrasto AA
  (`.badge-lh`). Il form non espone ancora le opzioni (prossimo
  passo del TO-DO): via API sono già utilizzabili. 2 test nuovi
  (validazione dei tre campi e di `always` non disponibile; e2e
  con `run_lighthouse` finto: pillar, area, sesta area nei
  punteggi e blocco in sintesi); `app.js` validato con
  `node --check`.

- **Risultati separati per tipologia MARS** (v2.19.0): la sezione
  unica "Risultati dell'audit e referto" è diventata cinque
  sezioni della fisarmonica — **"Sintesi e referto"** (meta,
  scarico referti, hero col verdetto, top rilievi, confronto con
  l'esecuzione precedente, punteggi per area, piano di
  remediation) più **Meta-fusion** (rilievi RRF, profili di
  citabilità, giudizio LLM, matematica del problema, simulazione
  per query, confronto competitivo), **Accessibility** (rilievi di
  accesso/crawling, profondità di crawl, grafo dei link),
  **Ranking** (rilievi lessicali/semantici/dati strutturati) e
  **Security** (HTTPS, http residuo, opt-out IA). Il riparto usa
  il campo `pillar` dei rilievi (core v1.42.0, ripiego sull'area
  in JS); i punteggi per area restano in sintesi e il click su
  un'area apre i suoi rilievi nella sezione di pertinenza; a fine
  audit si apre la sola sintesi, le altre sezioni sono chiuse ma
  visibili. Le sezioni senza rilievi mostrano "Nessun rilievo per
  questa tipologia".
- **Grafo dei link interattivo** (v2.18.0, su feedback: la resa
  statica non era leggibile): zoom con rotella o pulsanti, pan
  trascinando lo sfondo, trascinamento dei nodi per districare,
  evidenziazione del vicinato al passaggio o al **focus da
  tastiera** (nodi focusabili con `aria-label`) e dettagli nella
  regione di stato. Nel referto HTML il grafo resta statico ma
  ridisegnato leggibile: canvas 780×540, etichette con alone,
  tutte visibili fino a 20 nodi.

- **Grafo dell'architettura dei link** (v2.16.0, ultimo widget):
  layout force-directed Fruchterman-Reingold **deterministico,
  calcolato in Python nel core** (`_force_layout`; stesso input →
  stesso disegno, home ancorata al centro) e disegnato identico
  nella GUI e nel referto HTML, che resta senza JavaScript. Max 60
  nodi (i più linkati), etichette sui primi 10, ambra per pagine
  oltre 3 click o solo-da-sitemap, `<title>` con i dettagli su
  ogni nodo; `link_graph` nel JSON. La sezione widget del concept
  board è conclusa per intero.

- **Widget rimandati realizzati** (v2.15.0): **profondità di
  crawl** (bucket di click dalla home più "solo da sitemap", barre
  in GUI e referto HTML, `depth_distribution` nel JSON); **mappa a
  bolle** del posizionamento competitivo (share × query coperte ×
  corpus, `presence`/`queries_total` nello share of voice;
  decorativa, i numeri restano nelle tabelle); **form eventi**
  nella sezione citazioni (`POST /api/citations/events`, data
  validata, etichetta ≤ 120 caratteri) che aggiorna subito grafico
  e lista. Resta rimandato solo il grafo force-directed.

- **Widget completati** (v2.14.0, chiusa la sezione del concept
  board): **Top rilievi** (primi 5 interventi con pallino +
  etichetta + guadagno sull'indice, anche nel referto HTML sotto
  l'hero); **pin-evento** sul grafico citazioni da `eventi.jsonl`
  accanto allo storico (linea tratteggiata + lista testuale
  "Eventi annotati"); **badge NUOVO** sui rilievi comparsi
  rispetto all'esecuzione precedente (match per area + titolo
  normalizzato); **confronto fra due audit scelti** dallo storico
  (`GET /api/history/compare`, stesso sito, ordinamento per data
  lato server) con delta completo nella pagina.

- **Referti Markdown e CSV scaricabili** (v2.13.0): due pulsanti in
  più nei risultati ("Scarica Markdown", "Scarica CSV rilievi"),
  generati dalla stessa scansione e col medesimo gating del
  profilo completo.

- **Parametri RRF nel form** (v2.12.0): posti fusi per query,
  parole per chunk e pesi delle due liste (variante pesata) nel
  fieldset "Recupero e fusione", validati lato server e inclusi
  nelle preimpostazioni.

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
  (`mars_gui.db`, escluso dal repo), password PBKDF2-SHA256 con
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
- **Frontend Bootstrap Italia 2.18.3 in vanilla JavaScript**
  (aggiornata dalla 2.18.2 il 2026-08-04 con
  `tools/update-vendor.sh`, che scarica da npm e pota i formati
  legacy — ttf/eot/map e non minificati; file `VERSIONE` nel
  vendor), asset
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
  `deploy/mars-gui.service` con utente dinamico senza privilegi,
  filesystem in sola lettura e riavvio automatico, per le
  installazioni presso i clienti.

## Monitoraggio citazioni IA — `mars_citations.py` v1.2.0

- Interroga assistenti IA con ricerca web sulle query target del sito
  (da file o riusate dal referto JSON dell'audit con `--from-audit`) e
  verifica per ogni risposta se il sito è **citato** fra le fonti,
  **consultato**, o sostituito dai **concorrenti** (max 3).
- Provider: **anthropic** (SDK ufficiale, `claude-opus-5` con
  strumento `web_search`, gestione `pause_turn`/`refusal`, fallback
  server-side attivo di default), **perplexity** (Sonar) e
  **openai** (v1.1.0: ChatGPT via Responses API con `web_search`,
  citazioni dalle annotation `url_citation`, fonti consultate dal
  campo `sources`; modello `gpt-5.6` configurabile con
  `--openai-model`). Chiavi API solo via variabili d'ambiente.
- **Storico JSONL** con delta fra esecuzioni, soglia `--fail-under`
  con codice d'uscita 1 per l'alerting, referti text/JSON, limiti di
  costo (max 15 query, max 5 ricerche per risposta, pausa fra query).
  Dalla GUI v2.9.0 lo storico è consultabile anche nell'interfaccia
  (grafico per provider e tabella).
- **Esecuzione periodica**: unit systemd `deploy/
  mars-citations.service` + `.timer` (settimanale, hardening,
  chiavi in `/etc/seorrf/citations.env`).
- Testato senza chiamate reali: server API finti locali per entrambi i
  provider (8 test dedicati).

## Fork Lighthouse — strategia di manutenzione (P1, 2026-08-05)

- **P1 — Integrazione Lighthouse: COMPLETATA** (2026-08-05, in
  un'unica giornata di lavoro, v1.46.0→v1.55.0 / GUI
  v2.22.0→v2.28.0): fork (pin, patch anti-telemetria,
  installazione), core (rilevamento runtime, flag, runner, parser,
  deduplica, sesta area, referti nei cinque formati, i18n dai
  locale del fork), GUI (form, risultati coi badge, sintesi con
  CWV, fase annunciata, storico, accessibilità 31/31), test/CI
  (offline per costruzione + integrazione reale) e deploy (unit
  systemd riviste). Le **quattro decisioni preliminari** del
  2026-08-05, qui per memoria: *mappatura*
  Performance/Accessibilità/Agentic Browsing → Accessibility, SEO
  → Ranking, Best Practices → Security (PWA non esiste più nella
  13.x; l'alternativa Performance → Ranking è scartata per ora,
  rivalutabile a integrazione rodata); *punteggi* come sesta area
  a peso 1.0 con rinormalizzazione quando assente; *pagine* home +
  3 rappresentative; *deduplica* col rilievo MARS canonico e la
  conferma Lighthouse come evidenza aggiuntiva.

- Primo passo dell'integrazione Lighthouse (P1 del TO-DO): strategia
  di manutenzione del fork
  <https://github.com/saulusprime/lighthouse> impostata e documentata
  in [docs/LIGHTHOUSE-FORK.md](docs/LIGHTHOUSE-FORK.md). **Pin alla
  release upstream v13.4.1** (verificato che il fork fosse uno
  specchio esatto di upstream `main`, senza patch proprie né tag);
  modello di branch: `main` specchio di upstream, `mars` = release
  pinnata + patch-set, tag `vX.Y.Z-mars.N` come unico riferimento di
  installazione per MARS.
- **Patch-set versionato in questo repo**
  (`tools/lighthouse-patches/`, col file `PIN` macchina-leggibile
  della release corrente): una sola patch, che disattiva del tutto
  l'error reporting Sentry — niente prompt interattivo, niente
  consenso memorizzato in Configstore (un "sì" dato una volta a mano
  resterebbe attivo per sempre, anche nei run lanciati da MARS),
  niente traffico verso sentry.io, per ogni punto d'ingresso (CLI e
  API Node). L'`update-notifier` non esiste più nelle 13.x: nessuna
  patch necessaria. Il branch `mars` è ricostruibile da zero con
  `git am` (procedura nel doc); branch e tag `v13.4.1-mars.1` sono
  pubblicati sul fork (push del 2026-08-05, dopo la concessione
  dell'accesso in scrittura alla chiave LymphaTechnologies).
- **Verificato con smoke test end-to-end** su questa macchina (Node
  22.22.1, Chrome 151): branch `mars` costruito, dipendenze con
  yarn/corepack, `yarn build-report` (necessario: `dist/report` è
  importato anche con output solo JSON), audit reale su example.com →
  exit 0, LHR `13.4.1`, 160 audit, punteggi per categoria, nessun
  prompt né telemetria.
- Scoperte recepite nelle decisioni P1 del TO-DO: la categoria **PWA
  non esiste più** nella 13.x; la nuova categoria
  **`agentic-browsing`** (albero di accessibilità per gli agenti IA,
  WebMCP, CLS, llms.txt — dichiarata in sviluppo da upstream) è
  mappata sul pilastro **Accessibility**, e il suo audit `llms-txt`
  andrà in tabella di deduplica col controllo MARS esistente.
- **Rilevamento runtime nel core e in `/api/env`** (v1.46.0, GUI
  v2.22.0, 2026-08-05): `lighthouse_unavailable()` nel core verifica
  fork installato (`lighthouse/cli/index.js`), Node ≥ 22.19
  (`node_version()`) e browser (`find_system_chrome()`, che riusa i
  `CHROME_PATHS` del rendering JavaScript), con motivo dichiarato in
  italiano per ogni requisito mancante; `lighthouse_version()` legge
  il tag installato da `lighthouse/VERSIONE`. La GUI espone l'esito
  in `GET /api/env` (`lighthouse_available`, `lighthouse_reason`,
  `lighthouse_version`), stesso pattern di embeddings, rendering e
  giudizio LLM. Test dedicati in `tests/test_lighthouse.py` (11,
  tutto simulato con monkeypatch: la suite resta offline e
  indipendente dalla macchina) più le asserzioni in
  `test_gui.test_env`.
- **Installazione in directory dedicata** (2026-08-05, scelta di
  progetto: "`npm ci` in una dir dedicata", niente tarball nel
  repo): script `tools/update-lighthouse.sh` sul modello di
  `update-vendor.sh`. Il fork usa yarn (nessun `package-lock.json`),
  quindi l'equivalente di `npm ci` è clone shallow del tag del PIN
  + `yarn install --frozen-lockfile` via corepack; lo script
  costruisce `dist/report`, pota le devDependencies, **rifiuta i
  tag privi della patch anti-telemetria**, sostituisce `lighthouse/`
  in modo atomico e scrive `lighthouse/VERSIONE`. La directory
  (343 MB, 12.281 file) è in `.gitignore`; il `PIN` dichiara ora il
  tag del fork (`v13.4.1-mars.1`); attribuzione completa di
  Lighthouse nel `NOTICE`. Verificato end-to-end: installazione
  reale da GitHub e audit su example.com eseguito dall'artefatto
  installato (LHR 13.4.1, 160 audit, cinque categorie).

## Qualità e verifica

- **Test d'integrazione con Lighthouse vero e job CI dedicato**
  (2026-08-05, ultimo bullet della P1):
  `test_integrazione_lighthouse_reale` esegue il runner vero —
  processo Node, fork installato — contro il sito fixture locale
  (nessuna rete oltre 127.0.0.1) e verifica l'intera catena: LHR
  13.x, rilievi dal parser, punteggi di categoria, metriche CWV e
  punteggio della sesta area; **saltato con motivo** se
  fork/Node/Chrome mancano (pattern del test di rendering con
  browser reale). In CI il job **"Integrazione Lighthouse (Node +
  Chrome)"**: setup-node 22, `tools/update-lighthouse.sh`
  (installazione reale del fork al tag del PIN, con build) e
  `pytest tests/test_lighthouse.py` — sui runner ubuntu Chrome è
  preinstallato, quindi l'integrazione gira sempre.
- **Copertura di test dell'integrazione Lighthouse** (2026-08-05,
  chiude i primi due bullet "Test e CI" della P1): 48 test in
  `tests/test_lighthouse.py` — rilevamento runtime, flag CLI,
  runner (comando/ambiente, preset, timeout, annullamento, errori
  per pagina, selezione pagine), parser (mappatura
  audit→pillar/gravità con le **soglie esatte dei bucket** 0.5 e
  0.9, aggregazione multi-pagina, evidenze), deduplica (conferma,
  divergenza, fuori tabella), sesta area e rinormalizzazione,
  metriche CWV, i18n dai locale del fork, storico/delta, ancore,
  **coerenza dei cinque renderer** su uno stesso dataset (rilievo,
  sesta area, sezione di sintesi e salto dichiarato in
  text/json/html/md/csv) — più i test GUI (validazione API, e2e
  col runner finto, CSP del referto) e del referto HTML. La suite
  resta **offline per costruzione**: LHR JSON finti e un
  `subprocess.Popen` finto al posto dell'eseguibile (niente Node
  richiesto, nessun file su disco), pattern del server API finto
  del giudizio LLM.

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
  Dalla sessione del 2026-08-04 esiste anche la **verifica
  strumentale del protocollo** (`tools/verifica_at.py`): i flussi
  1–7 eseguiti in un Chrome reale (individuato per piattaforma,
  con ripiego sul Chromium di Playwright) con 31 controlli sul
  contratto ARIA (focus, regioni di stato, etichette, aria-*, il
  contratto delle cinque sezioni risultati dalla GUI v2.19.0 e le
  viste Lighthouse dalla v2.27.0, popolate da uno stub di
  run_lighthouse); ultimo esito 31/31 il 2026-08-05 —
  dichiaratamente non sostitutiva della sessione umana.

- **Suite pytest: 342 test in ~30 secondi** (inclusa
  l'integrazione con Lighthouse vero, dove disponibile), senza rete
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
  [mars_audit.md](mars_audit.md)).

## File di servizio e documentazione

- `requirements.txt` (esecuzione) e `requirements-dev.txt`
  (pytest + flake8 + SDK anthropic per i test), `pytest.ini`.
- File `LICENSE` (**Apache License 2.0** dal 2026-08-05, prima MIT)
  e `NOTICE` alla radice del repository, coerenti con la licenza
  dichiarata nei moduli. Il cambio — deciso dal titolare del
  copyright, Lympha Technologies S.r.l. — allinea il progetto alla
  licenza del fork di Lighthouse in corso di integrazione e serve
  l'uso B2B enterprise (concessione esplicita di brevetti e clausola
  di ritorsione dell'art. 3, assenti nella MIT). Il NOTICE elenca i
  componenti di terze parti (Bootstrap Italia vendorizzato; alla
  vendorizzazione del fork Lighthouse andrà aggiunta la sua
  attribuzione completa).
- **Repository git** inizializzato su branch `main` con `.gitignore`
  (esclusi bytecode, venv, referti e storici generati a runtime;
  vendorizzati Bootstrap Italia e asset brand inclusi nel
  versionamento perché necessari all'esecuzione offline).
- **Documentazione dell'integrazione Lighthouse completata**
  (2026-08-05): README con la nuova capacità — riga di
  installazione opzionale con la nota sui requisiti Node ≥
  22.19/Chrome (dipendenza opzionale dichiarata, pattern
  Playwright), le tre opzioni `--lighthouse*` nella tabella, la
  sesta area in "Le aree misurate", il bullet GUI, il flusso
  aggiornato e le righe di `tools/update-lighthouse.sh` e
  `docs/LIGHTHOUSE-FORK.md` nella tabella del repository; nota
  tecnica [mars_audit.md](mars_audit.md) aggiornata (uso, sesta
  area, avvertenza di onestà su dipendenza opzionale/lab vs
  field/fork pinnato, fonti Lighthouse e web.dev — corretto anche
  l'elenco dei formati fermo a tre). AS-IS mantenuto passo-passo a
  ogni versione durante tutta la P1.
- [README.md](README.md) con diagrammi dell'infrastruttura (pipeline
  CLI e architettura GUI), [mars_audit.md](mars_audit.md) (nota
  tecnica di consegna con changelog). L'esempio di referto di
  consulenza `audit_miaweb_rrf.html` (miaweb.art, 2026-08-03) e il
  concept `Features2.md` sono stati rimossi il 2026-08-05 a piano
  recepito (l'integrazione Lighthouse è tracciata nel TO-DO).

## Convenzioni grafiche adottate (widget GUI e referto HTML)

Dall'analisi dei principali tool del settore (Semrush, Ahrefs, Moz,
Lighthouse/PageSpeed, GTmetrix, CrUX Vis, Sistrix, SE Ranking,
Screaming Frog; per l'AI visibility: Profound, Peec, Otterly,
Ahrefs Brand Radar), adottate in blocco nei widget v1.35.0–v1.37.0
/ GUI v2.14.0–v2.16.0 — tutto in HTML+CSS+SVG puro, senza librerie,
coerente col vincolo offline (dal 2026-08-05 il referto HTML ammette
**JavaScript inline autonomo** come progressive enhancement — mai
librerie o origini esterne, e senza JS resta la resa statica):

- scala 0–100 con **soglie fisse e visibili** (40/70): colore per il
  verdetto immediato, numero sempre accanto;
- **mai solo colore**: forma geometrica o etichetta accanto al
  semaforo; gli informativi in blu, non in verde;
- **delta** rispetto all'esecuzione precedente accanto a ogni numero;
- liste di problemi ordinate per **severità × diffusione**, mai
  alfabetiche;
- trend con **annotazioni-evento** ("qui abbiamo pubblicato le FAQ").

Mockup interattivo dei nove widget con dati d'esempio: board
"SEO-RRF · Concept widget dashboard" su claude.ai (sessione di
analisi del 2026-08-03).

## Scartato consapevolmente (per non rivalutarlo)

- Lo **stack SaaS** di Features.md
  (FastAPI/Celery/Redis/RabbitMQ/pgvector/AWS): incompatibile con la
  filosofia locale/offline a dipendenze minime.
- La **simulazione di User-Agent altrui** (Bravebot, Baiduspider…) e
  i pool di proxy anti-bot: contraddicono l'UA trasparente e il
  rispetto del robots.txt di default (v1.13.0).
- Le **API a pagamento** Ahrefs/Semrush.
- Il **cross-check fattuale** su Wikipedia/Wikidata: oneroso, online,
  in parte coperto dal giudizio LLM (v1.18.0).
- I **Core Web Vitals**: territorio di Lighthouse.
- **Business model, pricing e KPI**: materiale commerciale, non di
  sviluppo (il white-label resta in TO-DO).
- Le **associazioni modello→backend** di Features.md (Claude→Brave,
  Kimi→Baidu, …): speculative e non verificate — i profili di
  citabilità sono presentati come euristiche dichiarate, mai come
  comportamento documentato dei vendor.
- L'**import da API Google Search Console** (OAuth): fuori scope per
  la filosofia offline; resta l'import dall'export CSV
  (`--queries-gsc`).
- La **traduzione delle evidenze citate dal sito** nei referti
  bilingui (v1.43.0): sono contenuti del sito, non dello strumento —
  restano nella lingua del sito, con nota dichiarata nel referto.
- Il **branding del referto HTML di Lighthouse** (2026-08-05): MARS
  consuma solo il LHR JSON e presenta i rilievi nei propri referti —
  il referto HTML di Lighthouse non arriva mai al cliente; meno
  patch sul fork, sync più semplici.
- Le **metriche di laboratorio nei referti** (LCP, FCP, TBT, CLS,
  Speed Index con le soglie Lighthouse) — accantonate il
  2026-08-05 **per i soli referti**: lì i punteggi di categoria
  nella sezione "Audit Lighthouse" e i singoli rilievi coprono già
  il segnale utile. Il pannello CWV vive invece nella **sintesi
  della GUI** (v2.26.0), con la nota di onestà obbligatoria lab vs
  field (dati simulati, non CrUX; l'INP reale non è misurabile in
  lab, TBT è il proxy); l'eventuale sezione nei referti si
  rivaluta a integrazione rodata.

## Limiti noti e accettati

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
  citazione — quella la misura `mars_citations.py`.
- Il giudizio LLM è **attivo di default** (modalità `auto`): con la
  chiave nell'ambiente ogni audit fa una richiesta API con costi a
  carico della chiave; il verdetto è il parere di un modello su un
  campione, non riproducibile né garanzia di citazione (nota
  inclusa in ogni referto). Senza chiave l'audit resta offline.
- Lavorazione multi-macchina: il working tree locale può contenere
  lavoro non ancora pushato — verificare `git status` e `git fetch`
  prima di riprendere lo sviluppo da un'altra postazione.
