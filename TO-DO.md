# TO-DO — sviluppi e idee di miglioramento

Elenco di ciò che **resta da fare** (codice alla v1.62.0 / GUI
v2.35.0 / API mars_api v0.2.0, contratto 1.3.0 / citations v1.2.0;
lo sviluppo API-first vive sul branch **`devapi`**, non ancora fuso
in `main`). Quanto già realizzato — e quanto scartato
consapevolmente, per non rivalutarlo — è documentato in
[AS-IS.md](AS-IS.md): le voci completate vengono spostate lì, non
spuntate qui. Le voci marcate **[bug/rischio]** sono comportamenti
osservati nel codice; il resto sono proposte.

## P1 — API-first (programma CONCLUSO il 2026-08-06; voce residua)

Il programma — contratto OpenAPI auto-generato dal registro delle
rotte, parità CLI↔API, backend puro con job a id e token Bearer,
frontend statico separato, e2e/CI/docs/deploy — è **completo**:
storia, decisioni ratificate e dettagli nella sezione "API —
contratto e registro" di AS-IS. Resta una sola voce, condizionale:

- [ ] Migrazione della GUI dalle rotte legacy `/api/*` alle
      `/api/v1` (job con id) e, a migrazione completata,
      **deprecazione dichiarata degli alias legacy** nella spec
      (data e sostituto per rotta — mai rimozione silenziosa).

- [ ] **Merge di `devapi` in `main`** quando il titolare decide:
      il branch è verde (suite completa, CI, AT 31/31) e
      documentato; da quel momento le release ripartono da `main`.

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
