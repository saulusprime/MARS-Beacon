# TO-DO — sviluppi e idee di miglioramento

Elenco di ciò che **resta da fare** (codice alla v1.45.0 / GUI
v2.21.0 / citations v1.2.0). Quanto già realizzato — e quanto scartato
consapevolmente, per non rivalutarlo — è documentato in
[AS-IS.md](AS-IS.md): le voci completate vengono spostate lì, non
spuntate qui. Le voci marcate **[bug/rischio]** sono comportamenti
osservati nel codice; il resto sono proposte.

## P1 — Integrazione Lighthouse

Obiettivo: integrare il fork di Google Lighthouse
(<https://github.com/saulusprime/lighthouse.git>) per aggiungere gli
audit Performance / Accessibilità / SEO / Best Practices / PWA al
progetto. Vincolo di filosofia: Lighthouse richiede **Node.js +
Chrome/Chromium**, quindi va trattato come **dipendenza opzionale
dichiarata** — stesso pattern di Playwright per `--render`: senza
Node/Chrome l'audit resta interamente offline e il referto dichiara il
salto con il motivo. I rilievi Lighthouse **non aprono nuove sezioni**:
si smistano nelle quattro fisarmoniche pilastro esistenti
(Meta-fusion / Accessibility / Ranking / Security) tramite il campo
`pillar` già presente nello schema.

### Decisioni preliminari

- [ ] **Mappatura categorie → pilastri MARS** (proposta da confermare):
      Performance → Accessibility (la velocità è accesso: CWV, FCP,
      TBT, Speed Index, risorse render-blocking); Accessibilità →
      Accessibility; SEO → Ranking; Best Practices → Security (HTTPS,
      librerie vulnerabili CVE, `rel="noopener"`, errori in console);
      PWA → Accessibility (manifest, service worker, offline =
      fruibilità). Alternativa da valutare: Performance → Ranking
      (i CWV sono segnale di ranking Google).
- [ ] **Punteggi**: decidere se i 4 score di categoria Lighthouse
      (0–100) diventano una **sesta area** pesata in `overall_score()`
      o se confluiscono nei punteggi dei pilastri; definire i pesi e
      l'eventuale effetto sui profili di citabilità.
- [ ] **Pagine sottoposte a Lighthouse**: l'audit MARS scansiona fino a
      25+ pagine, Lighthouse è lento (~10–30 s a pagina). Proposta:
      home + N pagine rappresentative (`--lighthouse-pages`, default
      3), scelte per profondità/traffico.
- [ ] **Deduplica con i controlli esistenti**: Lighthouse duplica
      molti rilievi già nostri (title, meta description, viewport,
      status code, link descrittivi, dati strutturati, `alt`, `lang`,
      contrasto, font-size, HTTPS, hreflang, robots). Regola proposta:
      il rilievo MARS resta canonico, l'audit Lighthouse equivalente
      viene soppresso o usato solo come conferma/evidenza aggiuntiva;
      serve la tabella esplicita audit-id → rilievo MARS.

### Fork e toolchain

- [ ] Strategia di manutenzione del fork: pin a una release upstream,
      procedura di sync documentata, patch minime (niente telemetria,
      eventuale branding referto).
- [ ] Installazione/vendorizzazione: valutare `npm ci` in una dir
      dedicata vs tarball vendorizzato; script
      `tools/update-lighthouse.sh` sul modello di
      `tools/update-vendor.sh`. Alla vendorizzazione aggiungere al
      `NOTICE` l'attribuzione completa di Lighthouse (la licenza del
      progetto è già Apache 2.0 dal 2026-08-05, vedi AS-IS).
- [ ] Rilevamento runtime: verifica di Node (versione minima del fork)
      e riuso della logica di scoperta Chrome/Chromium già scritta per
      il rendering Playwright; esito esposto in `/api/env`.

### Core CLI (mars_audit.py)

- [ ] Flag `--lighthouse off|auto|always` (default `off`, coerente con
      `--render`; `auto` parte solo se Node+Chrome trovati, altrimenti
      salto dichiarato) + `--lighthouse-pages N` +
      `--lighthouse-device mobile|desktop` (emulazione e throttling).
- [ ] Runner: subprocess della CLI del fork con `--output=json`,
      timeout per pagina, rispetto di `--delay` e dell'annullamento
      cooperativo (kill del processo Node).
- [ ] Parser del LHR (Lighthouse Result JSON) → `Finding`: audit id →
      chiave di catalogo, gravità dallo score (soglie da definire, es.
      score < 0.5 critico se weight alto), evidenze dagli `items` dei
      details, `pillar` dalla mappatura decisa sopra.
- [ ] Metriche di laboratorio nella sintesi: LCP, FCP, TBT, CLS, Speed
      Index con le soglie verde/arancio/rosso di Lighthouse. **Nota di
      onestà obbligatoria**: sono dati *lab* (ambiente simulato), non
      dati *field* (CrUX); l'INP reale non è misurabile in lab (TBT è
      il proxy) — dichiararlo nei referti.
- [ ] Applicare la deduplica decisa sopra (tabella di soppressione) e
      il calcolo punteggi deciso sopra.

### Referti (tutti i formati)

- [ ] text/json/md/csv/html: rilievi Lighthouse dentro le aree e i
      pilastri esistenti con origine dichiarata; sezione metriche
      performance nella sintesi. JSON solo additivo
      (`schema_version` invariato); ancore `#r-…` stabili anche per i
      nuovi rilievi.
- [ ] i18n it/en: valutare il riuso delle stringhe localizzate che il
      LHR già fornisce (Lighthouse è internazionalizzato) contro il
      catalogo interno chiave+parametri; in ogni caso niente inglese
      hardcoded nel referto italiano.
- [ ] Referto HTML: resta **senza JavaScript** — niente treemap
      interattiva nel referto statico (eventuale treemap solo in GUI);
      metriche e score con testo + simbolo, mai solo colore.

### GUI (mars_gui.py + gui/)

- [ ] Form: gruppo di opzioni Lighthouse (attivazione, device,
      pagine) con avviso se Node/Chrome mancano (da `/api/env`),
      pattern dell'avviso sentence-transformers.
- [ ] Risultati: smistamento dei rilievi Lighthouse nelle quattro
      fisarmoniche pilastro esistenti (`findings-acc-*`) via campo
      `pillar`, con badge di origine "Lighthouse" sul singolo rilievo;
      nessun accordion di primo livello nuovo.
- [ ] Sintesi: score delle categorie Lighthouse accanto ai punteggi di
      area e pannello Core Web Vitals con soglie (accessibile: testo +
      simbolo).
- [ ] Avanzamento: fase "Lighthouse" nel log e negli eventi SSE;
      "Annulla audit" interrompe anche il processo Node.
- [ ] Storico: delta degli score Lighthouse fra esecuzioni nel
      confronto "Rispetto all'esecuzione precedente".
- [ ] Accessibilità WCAG 2.2 AA delle nuove viste + aggiornamento del
      lint struttura e di docs/ACCESSIBILITA.md.

### Test e CI

- [ ] Fixture LHR JSON finti + stub dell'eseguibile Lighthouse: la
      suite resta **offline per costruzione** (pattern del server API
      finto del giudizio LLM).
- [ ] Unit test di mappatura audit→pillar/gravità, deduplica,
      soglie metriche, coerenza dei renderer, API GUI.
- [ ] Test d'integrazione con Lighthouse vero, saltato se Node/Chrome
      assenti (pattern del test di rendering Playwright); job CI
      dedicato con Node + Chrome.

### Documentazione e deploy

- [ ] README (nuova capacità, requisiti opzionali Node/Chrome,
      tabella opzioni), AS-IS.md a lavoro fatto, nota tecnica.
- [ ] Unit systemd: PATH per Node, revisione dell'hardening (Chrome
      headless dentro `DynamicUser` richiede aggiustamenti al
      sandboxing) nelle unit audit/GUI.

## P2 — Citabilità multi-modello

- [ ] **Ancora di realtà facoltativa**: verifica del posizionamento
      sulle query dell'audit via un'API di ricerca esterna (es.
      Brave Search API) per confrontare la simulazione RRF con un
      ranking reale; complementare all'import GSC già realizzato
      (`--queries-gsc`, v1.32.0).

## P2 — Interfaccia grafica (mars_gui.py)

- [ ] Incorporare il logo nel referto HTML autonomo (oggi la firma è
      testuale per contenere il peso del file) e valutare i font
      Titillium Web incorporati nel referto per la resa offline.
- [ ] White-label per rivendita: pacchettizzare il re-brand (token CSS,
      logo, favicon, ragione sociale nel footer) in un unico file di
      configurazione.

## P3 — Distribuzione ed ecosistema

- [ ] Packaging: `pyproject.toml`, entry point `mars-audit`, pubblicazione
      su PyPI; valutare la scomposizione del file singolo in moduli
      (`crawler`, `indexes`, `audits`, `render`) mantenendo l'installazione
      monocomando.
- [ ] Aggiungere alla suite i golden file completi dei renderer
      (la CI GitHub Actions con flake8 + pytest su Python 3.10/3.12 e
      audit Pa11y esiste dalla sessione del 2026-08-03).
- [ ] Immagine Docker per esecuzioni riproducibili (utile con Playwright).
- [ ] Modalità server/batch: audit schedulati di una lista di siti con
      notifica sulle regressioni (codice di uscita 0/1 e `--fail-under`
      già pronti per fungere da gate; per il sito singolo esistono le
      unit systemd in `deploy/`).
- [ ] File di configurazione TOML per soglie (title, description, conteggi
      parole) oggi hardcoded come costanti.
- [ ] Altre lingue del referto oltre it/en: il catalogo `_FINDINGS_EN`
      della v1.43.0 è la struttura su cui aggiungerle (una tabella per
      lingua, stesso meccanismo chiave+parametri).
