# TO-DO — sviluppi e idee di miglioramento

Elenco di ciò che **resta da fare** (codice alla v1.5.0). Quanto già
realizzato è documentato in [AS-IS.md](AS-IS.md): le voci completate
vengono spostate lì, non spuntate qui. Le voci marcate
**[bug/rischio]** sono comportamenti osservati nel codice; il resto
sono proposte.

## P1 — Robustezza del crawling

- [ ] Valutare se rendere `--respect-robots` il comportamento predefinito
      quando l'host auditato non coincide con un dominio "proprio"
      dichiarato (oggi è opt-in, pensato per l'audit del proprio sito).
- [ ] Fetch concorrente con limite per host (`asyncio` + `httpx` o thread
      pool) mantenendo il rate limit: con `--max-pages 40` e delay 0.5s
      l'esecuzione è oggi interamente seriale.
- [ ] Opzione di **rendering JavaScript** (Playwright) per auditare davvero i
      siti client-side: oggi il contenuto solo-JS viene rilevato ma non
      analizzato.

## P1 — Qualità dell'analisi

- [ ] **Auto-rilevare sentence-transformers.** Oggi gli embedding reali si
      attivano solo passando `--embeddings MODELLO`; se la libreria è
      installata, usare un modello multilingue di default e lasciare
      `char-tfidf` solo come vero fallback.
- [ ] Validazione JSON-LD contro lo schema (proprietà obbligatorie di
      `LocalBusiness`, `FAQPage`, ecc.), non solo inventario dei tipi.
- [ ] Controllo del file **`llms.txt`** (standard emergente per gli agenti IA)
      accanto a robots.txt.
- [ ] Segnali E-E-A-T: autore, date di pubblicazione/aggiornamento, pagina
      "chi siamo", contatti verificabili.
- [ ] Grafo dei link interni: pagine orfane, profondità di click, anchor text
      (oggi i link si usano solo per la scoperta URL).
- [ ] Stopword e pattern linguistici oltre it/en (le regex di definizioni,
      anafore e domande coprono solo italiano e inglese).
- [ ] Rivedere la lista `AI_CRAWLERS`: Bingbot è un crawler di ricerca
      classico, non IA; valutare l'aggiunta di nuovi agenti (es.
      `Meta-ExternalAgent`, `Amazonbot`) con fonte documentata.

## P2 — Simulazione RRF più realistica

- [ ] Query reali da **Google Search Console** (import CSV/API) al posto dei
      soli bigrammi auto-generati.
- [ ] Parametri esposti: `top_n` (oggi fisso a 5), variante RRF pesata,
      chunking configurabile (`--chunk-words`).
- [ ] Provider **OpenAI** nel monitoraggio citazioni (Responses API con
      web_search) accanto ad anthropic e perplexity.
- [ ] Integrare il monitoraggio citazioni nella GUI (grafico dello
      storico JSONL, tendenza per provider).

## P2 — Output e reportistica

- [ ] **Colmare il divario fra referto generato e referto consegnato**: il
      referto di esempio ([audit_miaweb_rrf.html](audit_miaweb_rrf.html)) è
      stato curato a mano e contiene verdetto sintetico, tabella
      "matematica del problema" e piano d'azione per priorità che
      `render_html()` non produce. Generare automaticamente almeno il piano
      d'azione ordinato per (gravità × peso × sforzo stimato).
- [ ] Renderer **Markdown** (comodo per issue/PR) ed export **CSV** dei
      rilievi.
- [ ] **Storico e delta**: salvare il JSON di ogni esecuzione e riportare le
      variazioni rispetto alla precedente (punteggi, rilievi nuovi/risolti),
      per trasformare l'audit in monitoraggio.
- [ ] Versionare lo schema del JSON (`"schema_version"`) per compatibilità
      futura.
- [ ] Referto HTML: CSS di stampa/esport PDF, ancore per rilievo,
      internazionalizzazione (oggi solo italiano).

## P2 — Widget grafici (GUI e referto HTML)

Idee raccolte dall'analisi dei principali tool del settore (Semrush,
Ahrefs, Moz, Lighthouse/PageSpeed, GTmetrix, CrUX Vis, Sistrix,
SE Ranking, Screaming Frog; per l'AI visibility: Profound, Peec,
Otterly, Ahrefs Brand Radar). Tutti realizzabili in HTML+CSS+SVG puro,
senza librerie, coerenti col vincolo offline della GUI e riusabili nel
referto HTML autonomo.

Convenzioni trasversali da adottare in blocco:

- scala 0–100 con **soglie fisse e visibili** (50/90 alla Lighthouse):
  colore per il verdetto immediato, numero sempre accanto;
- **mai solo colore**: forma geometrica (cerchio/quadrato/triangolo) o
  etichetta accanto al semaforo; gli informativi in blu, non in verde;
- **delta** rispetto all'esecuzione precedente accanto a ogni numero;
- liste di problemi ordinate per **severità × diffusione**, mai
  alfabetiche;
- trend con **annotazioni-evento** ("qui abbiamo pubblicato le FAQ").

Widget realizzabili **oggi** (dati già nel referto JSON; i primi sei
della lista originale — anello del punteggio, meter per area con
drill-down, tripletta di severità, barre del consenso con soglie,
share of voice con tacca di parità, donut stato pagine — sono stati
realizzati nella v1.5.0, vedi AS-IS):

- [ ] Top rilievi ordinati per impatto con pallino di severità
      (`findings`), come vista trasversale alle aree — pattern:
      Top Issues di Ahrefs/Semrush (oggi i rilievi sono ordinati per
      gravità solo dentro ogni area).
- [ ] Grafico del tasso di citazione IA nel tempo con pin-evento e linea
      per provider: lo storico JSONL di `seo_rrf_citations.py` esiste già
      (si aggancia alla voce "monitoraggio citazioni nella GUI" in P2 —
      Simulazione RRF) — pattern: Visibility Index di Sistrix, Brand
      Radar di Ahrefs.

Widget che richiedono lo **storico degli audit** (prerequisito: la voce
"Storico e delta" in P2 — Output e reportistica; basta un `--history
FILE` che appende una riga JSONL compatta come già fa il monitor
citazioni):

- [ ] Delta (freccia verde/rossa vs audit precedente) su punteggi, aree
      e conteggi di severità.
- [ ] Trend del punteggio complessivo per esecuzione con bande di soglia
      50/90 — pattern: CrUX Vis, tab Progress di Semrush.
- [ ] Badge "nuovo"/"risolto" sui rilievi, confronto fra due audit —
      pattern: Compare Crawls di Semrush, colonne New/Fixed di Ahrefs.

Mockup interattivo dei nove widget con dati d'esempio (artefatto della
sessione di analisi, 2026-08-03): board "SEO-RRF · Concept widget
dashboard" su claude.ai. Idee ulteriori emerse e rimandate: mappa a
bolle del posizionamento competitivo (Semrush), grafo force-directed
dell'architettura (Screaming Frog, dipende dal grafo dei link interni
in P1), distribuzione della profondità di crawl.

## P2 — Interfaccia grafica (seo_rrf_gui.py)

- [ ] **Annullamento dell'audit in corso.** L'audit gira in-process in un
      thread e non è interrompibile; per un vero "Annulla" serve eseguire
      lo script come sottoprocesso (con `--format json`) o introdurre un
      flag cooperativo di stop nel `Fetcher`.
- [ ] Avanzamento push (Server-Sent Events) al posto del polling a 1s.
- [ ] Storico degli audit nella GUI: elenco delle esecuzioni con confronto
      dei punteggi (si aggancia all'idea "storico e delta" dei referti).
- [ ] Audit di accessibilità automatizzato in CI (axe-core / Pa11y) e
      verifica manuale con screen reader (NVDA/VoiceOver) documentata:
      oggi la struttura è lintata staticamente ma non testata con AT reali.
- [ ] Salvataggio/caricamento di preimpostazioni di configurazione
      (per cliente/sito) in localStorage o file.
- [ ] Aggiornare la vendorizzazione di Bootstrap Italia con uno script
      dedicato (`update-vendor.sh`) che scarichi e potri i formati legacy.
- [ ] Incorporare il logo nel referto HTML autonomo (oggi la firma è
      testuale per contenere il peso del file) e valutare i font
      Titillium Web incorporati nel referto per la resa offline.
- [ ] White-label per rivendita: pacchettizzare il re-brand (token CSS,
      logo, favicon, ragione sociale nel footer) in un unico file di
      configurazione.

## P3 — Distribuzione ed ecosistema

- [ ] Packaging: `pyproject.toml`, entry point `seo-rrf-audit`, pubblicazione
      su PyPI; valutare la scomposizione del file singolo in moduli
      (`crawler`, `indexes`, `audits`, `render`) mantenendo l'installazione
      monocomando.
- [ ] CI (GitHub Actions): flake8 + pytest su più versioni di Python;
      aggiungere alla suite i golden file completi dei tre renderer.
- [ ] Immagine Docker per esecuzioni riproducibili (utile con Playwright).
- [ ] Modalità server/batch: audit schedulati di una lista di siti con
      notifica sulle regressioni (il codice di uscita 0/1 è già pronto per
      fungere da gate).
- [ ] File di configurazione TOML per soglie (title, description, conteggi
      parole) oggi hardcoded come costanti.
