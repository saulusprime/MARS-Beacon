# TO-DO — sviluppi e idee di miglioramento

Elenco di ciò che **resta da fare** (codice alla v1.61.0 / GUI
v2.30.0 / citations v1.2.0). Quanto già realizzato — e quanto scartato
consapevolmente, per non rivalutarlo — è documentato in
[AS-IS.md](AS-IS.md): le voci completate vengono spostate lì, non
spuntate qui. Le voci marcate **[bug/rischio]** sono comportamenti
osservati nel codice; il resto sono proposte.

## P1 — API-first: apizzazione completa e separazione frontend/backend

Rendere il progetto "totalmente apizzato" significa tre cose, in
quest'ordine: un **contratto formale** (la spec OpenAPI — lo
"swagger" — come unica fonte di verità su endpoint, schemi, errori e
autenticazione), la **parità funzionale** (tutto ciò che fanno CLI e
GUI dev'essere possibile via API, da qualunque client), e la
**separazione fisica** (backend che serve solo JSON+SSE, frontend
statico servibile da qualunque web server, anche su un'altra
origine). Oggi la GUI è già un frontend vanilla JS che parla
JSON+SSE con 17 endpoint: l'accoppiamento non è nel protocollo ma
nel processo unico, nel contratto implicito, nel cookie same-origin
come unica autenticazione e nell'audit come singleton globale (409)
invece che risorsa con identità.

**Vincoli non negoziabili** (coerenti con "Scartato
consapevolmente" in AS-IS): API-first **non** significa SaaS — lo
stack FastAPI/Celery/Redis resta escluso; server in sola libreria
standard, spec **auto-generata dal codice** e verificata dai test,
lettore della spec (Scalar) vendorizzato (pattern Bootstrap Italia:
funziona offline, mai CDN), default di binding su 127.0.0.1 e
sicurezza dichiarata. Il referto
JSON con `schema_version` resta il cuore del contratto dati.
Sinergie: il frontend separato è il pacchetto da brandizzare del
white-label (P2); il modello a job è il prerequisito della modalità
batch (P3).

### Fase 0 — Decisioni preliminari (da ratificare prima di iniziare)

- [ ] **Contratto auto-generato dal codice** (decisione corretta
      il 2026-08-06: la prima stesura prevedeva la spec scritta a
      mano — ribaltata, una spec mantenuta a mano deriva sempre
      dal codice). Unica fonte di verità: un **registro
      dichiarativo delle rotte** in `marsbeacon/api.py` —
      percorso, metodo, schemi di richiesta e risposta, errori,
      autenticazione per ogni endpoint — da cui derivano **sia il
      dispatch del server sia la spec** (OpenAPI 3.1): spec e
      codice non possono divergere per costruzione, senza
      adottare un framework esterno (il vincolo stdlib resta; il
      generatore è nostro, come il layout del grafo o lo
      squarify). `GET /api/v1/openapi.json` genera al volo dal
      registro; lo **snapshot `docs/openapi.json` è versionato
      col pattern golden** (un test verifica che il file
      committato coincida col generato; rigenerazione
      intenzionale e diff in revisione). Il registro alimenta
      anche la **validazione delle richieste** a runtime (stessi
      schemi: niente doppia scrittura) e i **contract test**
      (ogni risposta reale validata contro gli schemi;
      `jsonschema` in requirements-dev, come tomli: solo per la
      suite).
- [ ] **Autenticazione a doppio binario**: cookie di sessione
      HttpOnly per il frontend same-origin (com'è oggi) + **token
      Bearer per utente** per i client macchina e il cross-origin
      (generazione/revoca dal profilo, hash in SQLite, rate limit
      per token). CORS **spento di default**, attivabile solo con
      elenco esplicito di origini in configurazione.
- [ ] **Versionamento**: prefisso `/api/v1`; gli attuali `/api/*`
      restano come alias durante la migrazione della GUI e la loro
      deprecazione viene dichiarata (data e sostituto nella spec).
- [ ] **Modello a risorse**: l'audit diventa un **job con id**
      (`POST /api/v1/audits` → 202 + id; stato, referti e
      annullamento per id), con coda a concorrenza configurabile
      (default 1: comportamento attuale invariato). Lo slot orario
      per utente resta.
- [ ] **Errori uniformi**: oggetto unico `{code, key, params,
      message}` con chiave+parametri — lo stesso meccanismo i18n
      dei rilievi, così anche gli errori API sono traducibili e il
      messaggio italiano resta canonico.
- [ ] **Documentazione della spec con Scalar, unico lettore**
      (decisione del 2026-08-06; la coesistenza Swagger UI +
      Scalar era stata analizzata e giudicata fattibile, ma è
      stata **scartata per scelta**: un solo lettore da
      vendorizzare e mantenere — non rivalutare). Scalar (MIT,
      uso commerciale libero) renderizza `openapi.json` con
      lettura moderna, client di prova integrato e snippet di
      codice generati (curl/Python/JS); gli integratori
      abituati a Swagger UI hanno comunque la spec grezza su
      `/api/v1/openapi.json`, importabile in qualunque
      strumento. Condizioni non negoziabili: bundle
      **vendorizzato** e offline — attenzione dichiarata: Scalar
      di default carica Inter e JetBrains Mono da
      fonts.scalar.com, va spento con `withDefaultFonts: false`
      e font locali via `--scalar-font` (occasione: puntarlo al
      Titillium Web già vendorizzato del brand) — attribuzione
      MIT nel NOTICE, verifica automatica "nessuna origine
      esterna" nella suite.

### Fase 1 — Il contratto (lo "swagger")

- [ ] **Registro dichiarativo delle rotte e generatore OpenAPI**
      (decisione di Fase 0): il censimento della superficie
      attuale entra nel registro — GET `/api/env`, `/api/me`,
      `/api/status`, `/api/history`, `/api/history/report`,
      `/api/history/compare`, `/api/citations`, `/api/events`
      (SSE), `/api/report/{html,json,text,md,csv}`; POST
      `/api/register`, `/api/login`, `/api/logout`,
      `/api/profile`, `/api/citations/events`, `/api/cancel`,
      `/api/audit` — con schemi di richiesta/risposta, codici
      (401/403/409/422), cookie e limiti; il generatore emette la
      spec dal registro e lo snapshot `docs/openapi.json` è il
      golden verificato dalla suite.
- [ ] **Gap di parità CLI↔API da colmare e specificare**: lingua
      del referto (`lang` sui download, oggi solo it), soglie di
      prassi (blocco `soglie` nel POST, validato dal registro
      `CONFIG_THRESHOLDS` — equivalente di `--config`), query
      reali da Search Console (upload CSV), `fail_under`
      echeggiato nell'esito del job.
- [ ] Schemi riusati, non duplicati: il referto JSON
      (`schema_version`), le righe dello storico, il blocco
      citazioni; l'SSE documentato come `text/event-stream` con lo
      schema dello snapshot.
- [ ] La spec servita dal backend: `GET /api/v1/openapi.json`,
      generata al volo dal registro (mai letta da file: il file è
      solo lo snapshot golden).
- [ ] **Scalar vendorizzato** (decisione di Fase 0): script
      `tools/update-scalar.sh` sul modello di update-vendor che
      scarica `@scalar/api-reference` (MIT) da npm, pota ai soli
      file necessari, scrive il file `VERSIONE` e **verifica
      l'assenza di origini esterne** nel bundle; attribuzione nel
      NOTICE.
- [ ] Rotta `/api/docs`: Scalar in modalità markup (`data-url`
      verso la spec, niente JS inline: CSP stretta), con
      `withDefaultFonts: false` e `--scalar-font` sul Titillium
      Web del brand già vendorizzato.
- [ ] Suite: la spec si carica, i riferimenti si risolvono, ogni
      esempio valida contro il proprio schema; contract test per
      endpoint (pattern golden: le risposte non derivano in
      silenzio); la pagina di documentazione serve, punta alla
      spec e non contiene origini esterne (grep automatico,
      pattern anti-telemetria del fork Lighthouse).

### Fase 2 — Backend puro

- [ ] Estrazione degli handler API da `mars_gui.py` nel modulo
      **`marsbeacon/api.py`** (stesso metodo della scomposizione
      v1.58.0: spostamento meccanico, facciata invariata);
      `mars_gui.py` resta il combinato statici+API a zero
      configurazione, il nuovo entry **`mars_api.py`** serve solo
      l'API (niente filesystem statico, niente pagine).
- [ ] Job di audit: `POST /api/v1/audits` (202 + id), `GET
      /api/v1/audits/{id}` (stato+sintesi), `DELETE` (annullamento
      cooperativo per id), `GET /api/v1/audits/{id}/report?format=
      …&lang=…`; l'SSE diventa per-job (`/api/v1/audits/{id}/
      events`) col ripiego sul polling com'è oggi.
- [ ] Token Bearer: emissione/revoca dal profilo, hash in DB
      (pattern PBKDF2 esistente), stesso perimetro del cookie
      (slot orario, gating del profilo completo sui download).
- [ ] CORS opzionale esplicito (preflight, credenziali solo se
      necessario), binding configurabile con default 127.0.0.1 e
      nota reverse proxy; paginazione dello storico; validazioni
      già in italiano riusate con le chiavi d'errore uniformi.

### Fase 3 — Frontend statico separato

- [ ] `gui/` diventa un bundle autonomo: **base URL dell'API
      configurabile** (default: stessa origine — il combinato
      resta a zero configurazione), usata da fetch, SSE e link di
      download.
- [ ] Cross-origin: login via token quando l'origine è diversa
      (il cookie SameSite=Strict non viaggia), stessa UI.
- [ ] Servibile da qualunque static server: esempio nginx in
      `deploy/` (statici + proxy verso mars_api) e nota sul
      white-label P2 (il bundle è il pacchetto da brandizzare).
- [ ] Accessibilità riconfermata: verifica strumentale AT sui due
      assetti (combinato e separato), annunci e focus invariati.

### Fase 4 — Qualità, deploy, documentazione

- [ ] E2E a origini separate nella suite: API su una porta,
      frontend statico su un'altra, CORS attivo, ciclo completo
      audit→referti via token.
- [ ] Job CI dedicato (contract test + e2e separato); Pa11y
      invariato sul frontend.
- [ ] `docs/API.md` con esempi curl (audit, polling, referto in
      un'altra lingua, soglie personalizzate); README aggiornato;
      unit systemd `deploy/mars-api.service` (hardening delle unit
      esistenti).
- [ ] A migrazione della GUI completata: deprecazione dichiarata
      degli alias `/api/*` legacy (mai rimozione silenziosa).

## P2 — Interfaccia grafica (mars_gui.py)

- [ ] White-label per rivendita: pacchettizzare il re-brand (token CSS,
      logo, favicon, ragione sociale nel footer) in un unico file di
      configurazione (sinergia con P1: a separazione fatta, il
      pacchetto da brandizzare è il bundle statico di `gui/`).

## P3 — Distribuzione ed ecosistema

- [ ] Packaging: `pyproject.toml`, entry point `mars-audit`,
      pubblicazione su PyPI (la scomposizione in moduli è fatta:
      package `marsbeacon/` + facciata dalla v1.58.0 — vedi AS-IS).
- [ ] Immagine Docker per esecuzioni riproducibili (utile con Playwright).
- [ ] Modalità server/batch: audit schedulati di una lista di siti con
      notifica sulle regressioni (codice di uscita 0/1 e `--fail-under`
      già pronti per fungere da gate; per il sito singolo esistono le
      unit systemd in `deploy/`; il modello a job della P1 API-first
      è il prerequisito naturale di questa voce).
