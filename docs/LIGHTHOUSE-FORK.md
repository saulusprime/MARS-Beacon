# Fork Lighthouse — strategia di manutenzione

Il fork <https://github.com/saulusprime/lighthouse> fornisce a MARS
Beacon gli audit Performance / Accessibilità / SEO / Best Practices
(vedi TO-DO, P1). Questa nota fissa **come il fork viene mantenuto**:
pin a una release upstream, patch minime versionate in questo
repository, procedura di sync documentata.

## Principi

1. **Pin a una release, mai a `main`.** MARS usa esclusivamente un
   tag `vX.Y.Z-mars.N` del fork, costruito su una release upstream
   (`vX.Y.Z`) — mai su `main`, che upstream muove di continuo.
2. **Patch minime, versionate qui.** Il patch-set vive in
   [tools/lighthouse-patches/](../tools/lighthouse-patches/) come file
   `git format-patch` numerati: è revisionabile con il prodotto e
   rende il branch del fork **riproducibile da zero** in qualsiasi
   momento. Il file [PIN](../tools/lighthouse-patches/PIN) dichiara il
   **tag del fork** correntemente installato da MARS (es.
   `v13.4.1-mars.1`, da cui si legge anche la release upstream): è la
   sola fonte di verità per `tools/update-lighthouse.sh`.
3. **Niente telemetria.** Il fork non deve generare traffico di rete
   oltre a quello dell'audit stesso.

## Stato attuale (2026-08-05)

- **Pin**: upstream **v13.4.1** (ultima release; il `main` del fork
  ne dista 4 commit di solo sync dei test e-2-e).
- **Patch-set** (1 patch):
  `0001-mars-disable-sentry-error-reporting.patch` — disattiva del
  tutto l'error reporting Sentry: niente prompt interattivo, niente
  consenso memorizzato in Configstore (un "sì" dato una volta a mano
  resterebbe attivo per sempre, anche nei run lanciati da MARS),
  niente traffico verso sentry.io, per ogni punto d'ingresso (CLI e
  API Node). L'`update-notifier` non esiste più nelle 13.x: nessuna
  patch necessaria.
- **Branding del referto Lighthouse: scartato.** MARS consuma solo il
  LHR (`--output=json`) e presenta i rilievi nei propri referti; il
  referto HTML di Lighthouse non arriva mai al cliente. Meno patch =
  sync più semplici.
- Requisiti runtime del fork: **Node ≥ 22.19** e un Chrome/Chromium.

## Modello di branch del fork

| Ref | Contenuto |
|---|---|
| `main` | specchio di upstream `main`, senza modifiche (serve solo al sync) |
| `mars` | release upstream pinnata + patch-set applicato |
| `vX.Y.Z-mars.N` | tag annotato su `mars`: è ciò che MARS installa; `N` cresce se cambia il patch-set a parità di release |

## Costruzione del branch `mars` (riproducibile)

```bash
git clone git@github.com:saulusprime/lighthouse.git && cd lighthouse
git checkout -b mars v13.4.1
git am /percorso/a/MARS-Beacon/tools/lighthouse-patches/*.patch
git tag -a v13.4.1-mars.1 -m "MARS Beacon pin: upstream v13.4.1 + telemetria Sentry disattivata"
git push origin mars v13.4.1-mars.1
```

## Procedura di sync a una nuova release upstream

1. `git remote add upstream https://github.com/GoogleChrome/lighthouse.git`
   (una tantum), poi `git fetch upstream --tags`.
2. Aggiornare lo specchio: `git checkout main && git merge --ff-only
   upstream/main && git push origin main`.
3. Ricostruire `mars` sulla nuova release: `git checkout -B mars
   vX.Y.Z && git am .../tools/lighthouse-patches/*.patch`. Se una
   patch non applica, correggerla, rigenerarla con `git format-patch`
   e aggiornarla in `tools/lighthouse-patches/`.
4. Build e smoke test (sotto). Verificare nel changelog upstream le
   categorie e gli audit-id usati dalla mappatura MARS (la tabella
   audit-id → rilievo, quando esisterà).
5. Taggare `vX.Y.Z-mars.1` e push (`git push origin mars
   vX.Y.Z-mars.1 --force-with-lease` per il branch riallineato).
6. Aggiornare [PIN](../tools/lighthouse-patches/PIN) col nuovo tag,
   rieseguire `tools/update-lighthouse.sh` sulle installazioni e
   aggiornare questa nota.

## Build: il fork non si usa "as-is"

Dal sorgente il CLI **richiede una build** (`dist/report/*.js`,
importati dal generatore di referti anche con output solo JSON):

```bash
corepack yarn install --production --ignore-scripts --non-interactive   # deps runtime (~16 s)
corepack yarn install --ignore-scripts --non-interactive                # + devDeps per la build
corepack yarn build-report                                              # genera dist/report (~1 s)
```

`PUPPETEER_SKIP_DOWNLOAD=1` evita il download del Chromium di
puppeteer (serve solo ai test upstream). È lo stesso passo che il
`prepack` upstream esegue alla pubblicazione su npm.

## Installazione in MARS Beacon

Lo script [tools/update-lighthouse.sh](../tools/update-lighthouse.sh)
installa il fork nella directory dedicata e **non versionata**
`lighthouse/` alla radice del repository (scelta di progetto del
2026-08-05: installazione a setup-time, niente tarball nel repo). Il
fork usa yarn — `package-lock.json` non esiste — quindi l'equivalente
di `npm ci` è: clone shallow del tag del PIN + `yarn install
--frozen-lockfile` via corepack. Lo script poi costruisce
`dist/report`, pota le dipendenze di sviluppo, **verifica la presenza
della patch anti-telemetria** (si rifiuta di installare un tag che
non la contiene), sostituisce la directory in modo atomico e scrive
`lighthouse/VERSIONE` (tag + versione CLI). Requisiti: git, Node ≥
22.19 con corepack, rete verso GitHub. L'attribuzione completa di
Lighthouse è nel [NOTICE](../NOTICE).

## Verifica eseguita (2026-08-05)

Smoke test end-to-end del branch `mars` (v13.4.1 + patch) su questa
macchina (Node 22.22.1, Chrome 151):

```bash
CHROME_PATH=/usr/bin/google-chrome node cli/index.js https://example.com \
    --output=json --output-path=lhr.json --chrome-flags="--headless=new" --quiet
```

Esito: exit 0, LHR `lighthouseVersion: 13.4.1`, 160 audit, punteggi
per categoria presenti, nessun prompt e nessun traffico di telemetria.

## Categorie nella 13.x — differenze dal piano

- La categoria **PWA non esiste più** (rimossa da upstream): la voce
  "PWA → Accessibility" della mappatura è senza oggetto.
- Esiste la nuova categoria **`agentic-browsing`** ("browsable
  websites for AI agents", dichiarata *under development and subject
  to change*): albero di accessibilità ben formato per gli agenti,
  copertura e validità WebMCP, CLS, e un audit **`llms.txt`** che
  duplica il controllo MARS esistente (da tabella di deduplica). Il
  pilastro di destinazione è registrato nelle decisioni preliminari
  del [TO-DO](../TO-DO.md).
