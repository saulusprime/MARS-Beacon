# seo_rrf_audit.py — nota tecnica

Script Python 3 (PEP8, `flake8` pulito) per audit SEO + Reciprocal Rank Fusion
di un sito. Consegnato in chat il 2026-08-03. Versione 1.7.1, ~3070 righe,
licenza MIT.

Novità 1.1.0 (2026-08-03): tetto alla dimensione di ogni risposta HTTP
(default 10 MB, opzione `--max-body`): scarico a blocchi interrotto al
superamento, rifiuto immediato se il `Content-Length` dichiarato eccede,
esclusione riportata nel referto e avviso all'avvio se il valore scelto
supera un decimo della RAM disponibile.

Novità 1.2.0 (2026-08-03): opzione `--respect-robots` per rispettare i
`Disallow` del robots.txt rivolti all'agente `SeoRrfAudit`: gli URL
vietati non vengono scaricati (né dalla sitemap né in crawling) e sono
elencati nel referto come rilievo informativo. Predefinito spento.

Novità 1.2.1 (2026-08-03): referto HTML armonizzato al brand Lympha
Technologies (palette teal/arancio in chiaro e scuro, font Titillium
Web, firma aziendale nel footer).

Novità 1.3.0 (2026-08-03): retry con backoff esponenziale sugli errori
transitori (`--retries`, default 2): errori di rete e HTTP
429/500/502/503/504 ritentati con attese 0,5/1/2 s (tetto 8 s) e
rispetto di Retry-After; 404/403 e corpi oltre il limite mai ritentati.

Novità 1.4.0 (2026-08-03): confronto competitivo (`--competitor URL`,
ripetibile, max 3): corpora fusi negli stessi indici, share of voice
sui primi 5 posti fusi con soglie rispetto alla parità, elenco delle
query vinte dai concorrenti; sezione dedicata nei tre referti.

Novità 1.5.0 (2026-08-03): robustezza del crawling. Rilievi sulle
catene di redirect interne (301/302, http→https, www/non-www, catene
multiple); rilevamento euristico dei soft-404 (200 con contenuto
"pagina non trovata"); i Content-Type non analizzabili (PDF,
immagini, archivi) non vengono più scaricati — bastano stato e
header; sitemap compresse `.xml.gz` e prioritizzazione degli URL per
`lastmod` più recente quando `--max-pages` non copre tutto.

Novità 1.5.0, referto e GUI: widget grafici di sintesi in stile
Lympha (pattern mutuati da Lighthouse/Semrush/PSI): anello del
punteggio complessivo con verdetto testuale e soglie dichiarate
(40/70), tile Critici/Avvertenze/Informazioni, donut dello stato
pagine, meter del consenso RRF con tacche alle soglie 20%/45%,
tacca di parità sulle barre dello share of voice. Nella GUI i
punteggi-area sono cliccabili (aprono i rilievi dell'area) e i
risultati vengono ripristinati al ricaricamento della pagina.

Novità 1.6.0 (2026-08-03): auto-rilevamento di sentence-transformers.
Se la libreria è installata gli embedding reali si attivano da soli
con il modello multilingue predefinito
`paraphrase-multilingual-MiniLM-L12-v2`; `--embeddings MODELLO`
sceglie un modello diverso, `--embeddings none` forza il proxy
char-tfidf. Senza libreria il comportamento resta invariato.

Novità 1.7.0 (2026-08-03): qualità dell'analisi. Lista `AI_CRAWLERS`
rivista su documentazione ufficiale dei vendor (14 token; via Bingbot
— crawler di ricerca classico — e Claude-Web, deprecato; dentro
Claude-SearchBot, Claude-User, Perplexity-User, Meta-ExternalAgent,
Amazonbot, MistralAI-User); controllo di `/llms.txt`; validazione
delle proprietà minime dei tipi JSON-LD (incluse le coppie
domanda/risposta di FAQPage); segnali E-E-A-T (autore, date,
"chi siamo", contatti verificabili); grafo dei link interni con
pagine orfane, profondità oltre 3 click e anchor generiche.

Novità 1.7.1 (2026-08-03): ripiego robusto sugli ambienti embedding
rotti. Un'installazione incompatibile di sentence-transformers (es.
torch/numpy in conflitto, caso tipico su macOS Intel dove PyTorch si
ferma alla 2.2.2) sollevava errori diversi da ImportError durante
l'import: ora qualunque eccezione produce il ripiego pulito sul proxy
char-TFIDF, con il motivo dichiarato nel log. Nel README la
combinazione di versioni compatibile con macOS x86_64.

Novità GUI 1.7.0 (2026-08-03): interfaccia riorganizzata in tre
sezioni collassabili (accordion Bootstrap Italia, tema Lympha):
configurazione, avanzamento e "Risultati dell'audit e referto"
unificati — i download del referto vivono dentro i risultati. Le
sezioni si aprono e chiudono da sole seguendo il ciclo dell'audit.
Con la 1.7.1 l'anteprima incorporata (iframe) è stata rimossa:
faceva doppione con la pagina dei risultati, il referto HTML si
apre in una nuova scheda.

## Uso

```
pip install requests beautifulsoup4 lxml
# opzionale, per il recupero vettoriale reale:
pip install sentence-transformers numpy

python3 seo_rrf_audit.py https://esempio.it --format html --output report.html
python3 seo_rrf_audit.py https://esempio.it --max-pages 40 --queries query.txt
python3 seo_rrf_audit.py https://esempio.it --embeddings paraphrase-multilingual-MiniLM-L12-v2
```

Opzioni: `--max-pages` (default 25), `--queries FILE` (una per riga; se omesso
le query sono generate dai bigrammi tematici del sito), `--embeddings MODELLO`
(auto-rilevato se la libreria è installata; `none` forza il proxy),
`--rrf-k` (default 60), `--delay`, `--max-body MB` (default 10; tetto al corpo
di ogni risposta, da dimensionare sulla RAM della macchina),
`--retries N` (default 2; ritenta errori di rete e HTTP 429/5xx con backoff
esponenziale), `--respect-robots` (rispetta i Disallow del robots.txt per
l'agente dello strumento; predefinito spento), `--competitor URL`
(ripetibile, max 3; confronto competitivo con share of voice),
`--format text|json|html`, `--output`, `--quiet`, `--version`.

Codici di uscita: `0` nessuna criticità, `1` almeno una criticità, `2` errore
d'uso, `130` interruzione.

## Cosa misura

Cinque aree con punteggio 0–100 e punteggio complessivo pesato (tecnica 1.0,
lessicale 1.5, semantica 1.5, dati strutturati 1.0, simulazione RRF 1.5):

1. **Tecnica** — HTTPS, `robots.txt` e permessi per i crawler IA (GPTBot,
   OAI-SearchBot, ClaudeBot, PerplexityBot, Google-Extended, CCBot,
   Applebot-Extended…), sitemap, URL in errore, pagine segnaposto del CMS,
   `noindex`, canonical, contenuto solo-JavaScript, hreflang, duplicati.
2. **Lessicale (BM25)** — title, meta description, struttura H1, conteggio
   parole, slug, attributi `alt`.
3. **Semantica (vettoriale)** — numero di chunk, autoconsistenza dei passaggi
   (anafore), heading in forma di domanda, FAQ, definizioni, esempi, ampiezza
   del vocabolario.
4. **Dati strutturati** — inventario dei tipi JSON-LD, entità principale,
   FAQPage, BreadcrumbList, WebSite.
5. **Simulazione RRF** — indicizza i chunk in BM25 e in un indice vettoriale,
   esegue le query, fonde le liste con `score(d) = Σ 1/(k + rank_i(d))` e
   misura la **sovrapposizione fra le due liste** (il "consenso"), che è il
   segnale operativo vero.

## Avvertenze di onestà incorporate nello script

- Senza `sentence-transformers` il recupero "semantico" ripiega su un coseno
  TF-IDF di 4-grammi di caratteri: è un **proxy morfologico, non una vera
  rappresentazione semantica**. Lo script dichiara sempre la modalità usata
  (`char-tfidf` o il nome del modello) in tutti e tre i formati di referto.
- La simulazione RRF riproduce la formula pubblicata, non l'implementazione
  interna di un motore specifico: pesi, `k` e re-ranking li decide il motore.
  Il valore diagnostico sta nel confronto fra le due liste, non nel punteggio
  assoluto.

## Verifiche eseguite prima della consegna

- `flake8` senza rilievi.
- Esecuzione end-to-end su un sito di prova servito in locale (robots.txt con
  `Disallow: GPTBot`, sitemap, pagina segnaposto WordPress, JSON-LD parziale):
  lo script ha rilevato indipendentemente tutti i difetti piantati.
- Verifica numerica del nucleo contro valori calcolati a mano: RRF con k=60
  (2° lessicale + 3° semantico = 1/62 + 1/63 = 0,032002 batte 1° in una sola
  lista = 1/61 = 0,016393), idf BM25 = ln(1 + (N−n+0,5)/(n+0,5)), saturazione
  della frequenza, coseno entro [0,1].
- Testati i tre formati di output, il file di query esterno, `--rrf-k`, i
  codici di uscita e i percorsi d'errore (host irraggiungibile, file mancante).

## Difetti trovati e corretti durante la verifica

- Mappatura heading→paragrafi basata su una divisione aritmetica: sostituita
  con la scansione nel vero ordine del documento.
- `/` e `/index.html` contati come pagine distinte, con raddoppio dei chunk e
  falso allarme sui title duplicati: aggiunta la deduplica per impronta del
  testo, con segnalazione dei duplicati come rilievo a sé.
- Query auto-generate degeneri ("come funziona funziona"): ora si usano
  bigrammi tematici, escludendo i termini già presenti nei template.
- Il referto JSON e quello HTML dichiaravano `k=60` fisso anche con `--rrf-k`
  diverso: parametro ora propagato a tutti i renderer.

## Fonti

- Cormack, Clarke, Buettcher — *Reciprocal Rank Fusion Outperforms Condorcet
  and Individual Rank Learning Methods*, SIGIR 2009.
- Microsoft Learn — Hybrid search scoring (RRF):
  https://learn.microsoft.com/en-us/azure/search/hybrid-search-ranking
- Elastic — Reciprocal Rank Fusion:
  https://www.elastic.co/docs/reference/elasticsearch/rest-apis/reciprocal-rank-fusion
- OpenSearch — Introducing RRF for hybrid search:
  https://opensearch.org/blog/introducing-reciprocal-rank-fusion-hybrid-search/
- Robertson & Zaragoza — *The Probabilistic Relevance Framework: BM25 and
  Beyond*, 2009.
- Schema.org: https://schema.org/