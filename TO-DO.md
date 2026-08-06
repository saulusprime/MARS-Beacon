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

Le **sei decisioni preliminari (Fase 0)** sono state ratificate il
2026-08-06 e spostate in AS-IS ("qui per memoria", come le quattro
decisioni della P1 Lighthouse): contratto auto-generato dal
registro delle rotte, autenticazione a doppio binario
(cookie + token Bearer, CORS spento di default), versionamento
`/api/v1` con alias legacy deprecati dichiaratamente, audit come
job con id, errori uniformi con chiave+parametri, documentazione
della spec con solo Scalar vendorizzato (Swagger UI scartato per
scelta — non rivalutare).

### Fase 1 — Il contratto (lo "swagger")

Registro, generatore, spec servita, golden, validazione runtime,
contract test e **parità CLI↔API** (lang, soglie, queries_gsc,
fail_under nel POST /api/audit) sono **fatti** — censimento
completo delle 17 rotte, `API_CONTRACT_VERSION` 1.1.0, vedi AS-IS
"API — contratto e registro". Resta:

- [ ] **Scalar vendorizzato** (decisione di Fase 0): script
      `tools/update-scalar.sh` sul modello di update-vendor che
      scarica `@scalar/api-reference` (MIT) da npm, pota ai soli
      file necessari, scrive il file `VERSIONE` e **verifica
      l'assenza di origini esterne** nel bundle; attribuzione nel
      NOTICE.
- [ ] Rotta `/api/docs`: Scalar in modalità markup (`data-url`
      verso la spec, niente JS inline: CSP stretta), con
      `withDefaultFonts: false` e `--scalar-font` sul Titillium
      Web del brand già vendorizzato; test che la pagina serve,
      punta alla spec e non contiene origini esterne (grep
      automatico, pattern anti-telemetria del fork Lighthouse).

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
