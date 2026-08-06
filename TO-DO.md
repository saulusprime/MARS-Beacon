# TO-DO — sviluppi e idee di miglioramento

Elenco di ciò che **resta da fare** (codice alla v1.61.0 / GUI
v2.30.0 / citations v1.2.0). Quanto già realizzato — e quanto scartato
consapevolmente, per non rivalutarlo — è documentato in
[AS-IS.md](AS-IS.md): le voci completate vengono spostate lì, non
spuntate qui. Le voci marcate **[bug/rischio]** sono comportamenti
osservati nel codice; il resto sono proposte.

## P2 — Interfaccia grafica (mars_gui.py)

- [ ] White-label per rivendita: pacchettizzare il re-brand (token CSS,
      logo, favicon, ragione sociale nel footer) in un unico file di
      configurazione.

## P3 — Distribuzione ed ecosistema

- [ ] Packaging: `pyproject.toml`, entry point `mars-audit`,
      pubblicazione su PyPI (la scomposizione in moduli è fatta:
      package `marsbeacon/` + facciata dalla v1.58.0 — vedi AS-IS).
- [ ] Aggiungere alla suite i golden file completi dei renderer
      (la CI GitHub Actions con flake8 + pytest su Python 3.10/3.12 e
      audit Pa11y esiste dalla sessione del 2026-08-03).
- [ ] Immagine Docker per esecuzioni riproducibili (utile con Playwright).
- [ ] Modalità server/batch: audit schedulati di una lista di siti con
      notifica sulle regressioni (codice di uscita 0/1 e `--fail-under`
      già pronti per fungere da gate; per il sito singolo esistono le
      unit systemd in `deploy/`).
