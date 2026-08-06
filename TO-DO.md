# TO-DO — sviluppi e idee di miglioramento

Elenco di ciò che **resta da fare** (codice alla v1.62.0 / GUI
v2.37.0 / API mars_api v0.2.0, contratto 1.4.0 / citations v1.2.0;
tutto su `main`, dove il programma P1 API-first è stato fuso il
2026-08-06). Quanto già realizzato — e quanto scartato
consapevolmente, per non rivalutarlo — è documentato in
[AS-IS.md](AS-IS.md): le voci completate vengono spostate lì, non
spuntate qui. Le voci marcate **[bug/rischio]** sono comportamenti
osservati nel codice; il resto sono proposte.

## P2 — Interfaccia grafica (mars_gui.py)

- [ ] White-label per rivendita: pacchettizzare il re-brand (token CSS,
      logo, favicon, ragione sociale nel footer) in un unico file di
      configurazione (sinergia con P1: a separazione fatta, il
      pacchetto da brandizzare è il bundle statico di `gui/`; dalla
      v2.37.0 la superficie comprende anche il footer istituzionale
      replicato da lymphatech.it — colonne, anagrafica e badge in
      `gui/brand/` — da sostituire in blocco per un altro brand).

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
