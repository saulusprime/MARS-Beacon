# TO-DO — sviluppi e idee di miglioramento

Elenco di ciò che **resta da fare** (codice alla v1.62.0 / GUI
v2.39.0 / API mars_api v0.2.0, contratto 1.4.0 / citations v1.2.0;
tutto su `main`, dove il programma P1 API-first è stato fuso il
2026-08-06). Quanto già realizzato — e quanto scartato
consapevolmente, per non rivalutarlo — è documentato in
[AS-IS.md](AS-IS.md): le voci completate vengono spostate lì, non
spuntate qui. Le voci marcate **[bug/rischio]** sono comportamenti
osservati nel codice; il resto sono proposte.

## P2 — Interfaccia grafica (mars_gui.py)

- [ ] **Modalità embed** (strada A dell'analisi del 2026-08-06): la
      sola applicazione, senza header e footer, dentro un iframe di
      pagine web già brandizzate (lymphatech.it o siti dei
      rivenditori). Il backend non si tocca: l'unica modifica server
      è l'header CSP.
      - [ ] Attivazione runtime con `?embed=1` in query string (in
            alternativa `MARS_EMBED` in config.js per un bundle
            dedicato): app.js mette una classe sul body; due regole
            CSS nascondono `.lt-header` e `.lt-footer` e riducono i
            margini del `main`. Nessuna pagina duplicata da tenere
            allineata.
      - [ ] `frame-ancestors` configurabile: oggi la CSP serve
            `frame-ancestors 'self'` e il framing da altra origine è
            bloccato dal browser. Opzione `--frame-ancestors` con
            origin espliciti (speculare a `--cors`) su mars_gui e
            mars_api; il default resta `'self'` — la sicurezza di chi
            non embedda non cambia.
      - [ ] Autenticazione nei tre assetti, da documentare: stesso
            sito (app.lymphatech.it dentro lymphatech.it: stesso
            eTLD+1, i cookie SameSite=Strict viaggiano — funziona
            già); reverse proxy sulla stessa origine (l'esempio
            nginx è già in deploy/ — non serve nemmeno toccare
            frame-ancestors); dominio terzo (cookie di terza parte
            bloccati: si usa l'accesso token Bearer già costruito
            in P1 — valutare la UX del token dentro l'iframe).
      - [ ] Altezza dell'iframe: prima versione ad altezza fissa con
            scroll interno (zero lavoro); auto-altezza con
            ResizeObserver + postMessage come estensione (~20 righe
            più il protocollo da documentare per la pagina ospite).
      - [ ] Accessibilità: in embed il documento resta senza h1
            (l'unico h1 vive nell'header nascosto — WCAG non lo
            impone e Pa11y non boccia, ma il `<title>` della pagina
            e il `title` dell'iframe lato ospite diventano
            l'etichetta principale: da documentare per l'ospite);
            skip-link mantenuto (dentro l'iframe ha ancora senso);
            tos.html si apre già in scheda nuova (`target=_blank`).
      - [ ] Verifiche e doc: URL `?embed=1` aggiunto a .pa11yci.js,
            controllo AT dedicato alla modalità, asserzioni
            strutturali nella suite; esempio iframe + nginx nel
            README (sezione embed accanto al white-label).

      La strada B — widget nativo montato nel DOM della pagina
      ospite — resta fuori ed è da ratificare come "scartato
      consapevolmente" in AS-IS: i reset globali di Bootstrap
      Italia collidono col CSS ospite in entrambe le direzioni
      (servirebbe Shadow DOM o prefissare tutti i selettori),
      app.js usa decine di id globali e assume il documento intero,
      e la doppia manutenzione sarebbe permanente a fronte dello
      stesso risultato visivo dell'iframe.

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
