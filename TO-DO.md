# TO-DO — sviluppi e idee di miglioramento

Elenco di ciò che **resta da fare** (codice alla v1.18.0). Quanto già
realizzato è documentato in [AS-IS.md](AS-IS.md): le voci completate
vengono spostate lì, non spuntate qui. Le voci marcate
**[bug/rischio]** sono comportamenti osservati nel codice; il resto
sono proposte.

## P1 — Robustezza del crawling

## P1 — Qualità dell'analisi

## P2 — Citabilità multi-modello (da Features.md)

L'idea portante di Features.md: oltre al punteggio per area, esporre
**profili di citabilità per assistente IA**. Attenzione: le
associazioni modello→backend del documento (Claude→Brave,
Kimi→Baidu, …) sono speculative e non verificate — le lenti vanno
presentate nel referto come euristiche dichiarate, non come
comportamento documentato dei vendor.

Le **lenti per modello** sono realizzate nella v1.15.0 (quattro
profili + indice composito con `--market`, nei tre referti), la
**vista** nella v1.16.0/GUI v2.6.0 (select del mercato nel form,
barre per profilo e top azioni prioritarie con guadagno stimato) e
i **problemi trasversali** nella v1.17.0/GUI v2.7.0 (piano di
remediation annotato e ordinato per guadagno di citabilità, badge
sui rilievi che deprimono più profili — vedi AS-IS) e il **giudizio
LLM** nella v1.18.0/GUI v2.8.0 (`--judge`, **attivo di default** in
`auto` per decisione di progetto del 2026-08-04: parte da solo con
la chiave presente, senza chiave l'audit resta offline). I nove
controlli del P1 sono stati innestati nelle aree previste
(estraibilità/densità → semantica/Claude, ciclo di
vita/riferimenti → semantica/Kimi, HTML semantico → dati
strutturati/Qwen): le lenti li assorbono senza ritocchi ai pesi.

- [ ] **Ancora di realtà facoltativa**: verifica del posizionamento
      sulle query dell'audit via un'API di ricerca esterna (es.
      Brave Search API) per confrontare la simulazione RRF con un
      ranking reale; complementare all'import GSC già in P2 —
      Simulazione RRF.

Scartato consapevolmente da Features.md (per non rivalutarlo): lo
stack SaaS (FastAPI/Celery/Redis/RabbitMQ/pgvector/AWS) è
incompatibile con la filosofia locale/offline a dipendenze minime;
la simulazione di User-Agent altrui (Bravebot, Baiduspider…) e i
pool di proxy anti-bot contraddicono l'UA trasparente e il rispetto
del robots di default (v1.13); le API a pagamento Ahrefs/Semrush; il
cross-check fattuale su Wikipedia/Wikidata (oneroso, online, in
parte coperto dal futuro LLM-as-judge); i Core Web Vitals
(territorio di Lighthouse); business model, pricing e KPI (materiale
commerciale, non di sviluppo — il white-label è già in P2 — GUI).

## P2 — Simulazione RRF più realistica

Sezione completata il 2026-08-04: query reali da Search Console
(`--queries-gsc`, v1.32.0), parametri esposti (`--top-n`,
`--rrf-weights`, `--chunk-words`, v1.31.0) e provider **openai**
nel monitor citazioni (v1.1.0) — vedi AS-IS. Restano qui le idee
"online" collegate: l'ancora di realtà (Brave Search API) è in
P2 — Citabilità multi-modello; l'import da API GSC (OAuth) è
volutamente fuori scope per la filosofia offline.

## P2 — Output e reportistica

- [ ] Nel deploy systemd, affiancare al timer delle citazioni un
      timer per l'audit periodico con `--history` (la CLI ha
      storico e delta dalla v1.19.0 — vedi AS-IS): unit di esempio
      in `deploy/` con notifica sulle regressioni via
      `--fail-under`-equivalente (oggi il gate è il codice di
      uscita sui critici).
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
      Top Issues di Ahrefs/Semrush. Dalla v1.17.0 il piano di
      remediation è già una vista trans-area ordinata per gravità e
      guadagno di citabilità (`index_gain` riusabile dal widget);
      resta la resa compatta da dashboard accanto agli altri widget
      di sintesi.
- [ ] **Pin-evento** sul grafico delle citazioni IA ("qui abbiamo
      pubblicato le FAQ"): il grafico per provider con tendenza è
      realizzato nella GUI v2.9.0 (sezione "Citazioni IA nel
      tempo"); restano le annotazioni-evento, che richiedono un
      posto dove registrarle (es. campo `events` nel JSONL o file a
      parte) — pattern: Visibility Index di Sistrix, Brand Radar di
      Ahrefs.

Widget che richiedono lo **storico degli audit** (in GUI c'è dalla
v2.10.0 con referto JSON in database; per la CLI vedi "Storico e
delta nella CLI" in P2 — Output e reportistica):

- [ ] Badge "nuovo"/"risolto" **sui singoli rilievi nella
      fisarmonica** e confronto fra **due audit scelti** dallo
      storico (oggi il confronto è solo con l'esecuzione
      precedente; le liste nuovi/risolti sono nei risultati dalla
      v2.10.0) — pattern: Compare Crawls di Semrush, colonne
      New/Fixed di Ahrefs.

Mockup interattivo dei nove widget con dati d'esempio (artefatto della
sessione di analisi, 2026-08-03): board "SEO-RRF · Concept widget
dashboard" su claude.ai. Idee ulteriori emerse e rimandate: mappa a
bolle del posizionamento competitivo (Semrush), grafo force-directed
dell'architettura (Screaming Frog, dipende dal grafo dei link interni
in P1), distribuzione della profondità di crawl.

## P2 — Interfaccia grafica (seo_rrf_gui.py)

- [ ] Eseguire (e registrare in docs/ACCESSIBILITA.md) la prima
      sessione di verifica manuale con screen reader: il protocollo
      VoiceOver/NVDA è documentato, serve una persona con l'AT attivo.
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
- [ ] Aggiungere alla suite i golden file completi dei tre renderer
      (la CI GitHub Actions con flake8 + pytest su Python 3.10/3.12 e
      audit Pa11y esiste dalla sessione del 2026-08-03).
- [ ] Immagine Docker per esecuzioni riproducibili (utile con Playwright).
- [ ] Modalità server/batch: audit schedulati di una lista di siti con
      notifica sulle regressioni (il codice di uscita 0/1 è già pronto per
      fungere da gate).
- [ ] File di configurazione TOML per soglie (title, description, conteggi
      parole) oggi hardcoded come costanti.
