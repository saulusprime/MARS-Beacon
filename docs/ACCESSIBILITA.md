# Accessibilità della GUI — verifica automatica e manuale

Obiettivo: WCAG 2.2 AA per l'interfaccia di `mars_gui.py`.
La verifica ha due gambe: l'audit **automatico** (Pa11y in CI, su
pagine reali servite dalla GUI) e la verifica **manuale con screen
reader**, che gli strumenti automatici non possono sostituire
(ordine di lettura, annunci di stato, comprensibilità delle
etichette).

## 1. Audit automatico (CI)

Il workflow [`.github/workflows/ci.yml`](../.github/workflows/ci.yml)
esegue a ogni push su `main` e su ogni pull request:

- `flake8` + `pytest` su Python 3.10 e 3.12;
- **Pa11y** (standard `WCAG2AA`) sulle pagine servite da una GUI
  avviata nel runner: `tos.html`, la vista anonima (login e
  registrazione) e la **vista autenticata** (configurazione), che
  Pa11y raggiunge compilando davvero il form di registrazione con le
  sue azioni (config in [`.pa11yci.js`](../.pa11yci.js)).

Esecuzione locale:

```bash
# 1. avvia la GUI (usa un DB pulito: l'email di prova non deve esistere)
python3 mars_gui.py --no-browser --port 8765

# 2. in un altro terminale
PA11Y_CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  npx --yes pa11y-ci@3 --config .pa11yci.js
```

`PA11Y_BASE` cambia l'URL di base (default `http://127.0.0.1:8765`);
`PA11Y_CHROME` punta a un Chrome di sistema (senza, Pa11y usa il suo
Chromium impacchettato, che su macOS recenti può non avviarsi).

Ultimo esito locale: **3/3 pagine, 0 errori WCAG 2 AA**
(2026-08-03, Chrome 139, pa11y-ci 3).

## 1.1 Sessione strumentale del protocollo (albero di accessibilità)

Fra l'audit automatico e la sessione umana c'è una terza gamba:
[`tools/verifica_at.py`](../tools/verifica_at.py) esegue i **flussi
1–7 del protocollo** in un Chrome reale (GUI in-process, store
temporaneo, sito fixture) e verifica il **contratto ARIA** che
l'albero di accessibilità espone allo screen reader: gestione del
focus (skip link, avvio, fine audit), annunci delle regioni
`role="status"` (registrazione, fasi dell'audit), etichette e
obblighi dei campi, `aria-expanded`/`aria-describedby`,
`aria-disabled` con nota, gravità come testo, didascalie delle
tabelle, `aria-label` dei widget e — dalla GUI v2.19.0 — il
contratto delle **cinque sezioni risultati** (sintesi + quattro
tipologie MARS): visibilità, `aria-expanded`/`aria-controls` dei
toggle, apertura della sola sintesi a fine audit, click su un
punteggio d'area che espande la sezione di pertinenza e porta il
focus sulla fisarmonica giusta. Dal 2026-08-05 lo script verifica
anche le **viste Lighthouse** (GUI v2.24.0–v2.27.0): etichette dei
tre campi del form, chip di categoria e pannello Core Web Vitals
con verdetti testo + simbolo e nota "laboratorio", badge di
origine e di conferma sui rilievi — popolate da uno **stub di
`run_lighthouse`** (la verifica resta indipendente dalla macchina:
niente Node né fork richiesti). 31 controlli in tutto.

```bash
<venv>/bin/python tools/verifica_at.py   # richiede Chrome e playwright
```

**Non sostituisce la sessione umana**: verifica ciò che l'AT
*riceve*, non come lo *pronuncia* né se l'ordine di lettura è
comprensibile. Va rieseguita a ogni modifica di flusso, prima
della sessione umana.

Ultimo esito: **31/31 controlli superati** (2026-08-05, Chrome di
sistema via Playwright su Linux, GUI v2.27.0 / audit v1.55.0):
riesecuzione dopo l'integrazione Lighthouse, con i quattro
controlli nuovi sulle sue viste. I contrasti dei colori introdotti
(badge `.badge-lh`, chip `.lh-*`, pannello `.cwv-*`) sono stati
verificati a calcolo: tutti fra 6,48:1 e 10,24:1, sopra la soglia
AA di 4,5:1.

Esito precedente: 27/27 (2026-08-05, macOS, GUI v2.19.0 / audit
v1.43.0), dopo la separazione dei risultati in cinque sezioni. Lo
script individua il Chrome di sistema per piattaforma
(macOS/Linux/Windows), con ripiego sul Chromium di Playwright.

Esito precedente: 23/23 (2026-08-04, GUI v2.16.0 / audit v1.37.0).
Nessuna anomalia del contratto ARIA; tre falsi allarmi iniziali
erano artefatti dello script (audit troppo rapido per campionare
l'avanzamento → risolto con `--delay 1.5`; confronto di stringhe
senza normalizzare gli a-capo; id errato del bottone Annulla).

## 2. Verifica manuale con screen reader — protocollo

Da eseguire a ogni modifica sostanziale dell'interfaccia (nuove
sezioni, cambi di flusso), su almeno una combinazione per sistema:

| SO | Screen reader | Browser |
|---|---|---|
| macOS | VoiceOver (Cmd+F5) | Safari |
| Windows | NVDA (gratuito, nvaccess.org) | Firefox o Chrome |

Comandi essenziali: VoiceOver — `Ctrl+Opt+→` per scorrere,
`Ctrl+Opt+Cmd+H` per i titoli, `Ctrl+Opt+Spazio` per attivare;
NVDA — `↓` per scorrere, `H` per i titoli, `B` per i pulsanti,
`F` per i campi, `Invio`/`Spazio` per attivare.

### Flussi da verificare e comportamento atteso

1. **Orientamento iniziale** — dal caricamento, il titolo della
   pagina è annunciato; con la navigazione per titoli si
   raggiungono "Accesso" e le altre sezioni; lo skip link "Vai al
   contenuto principale" è il primo elemento raggiungibile con Tab.
2. **Registrazione** — ogni campo annuncia etichetta e obbligo
   (asterisco nel testo dell'etichetta); il checkbox delle
   condizioni annuncia il proprio stato; inviando il form con un
   errore, il focus va sull'avviso e il testo dell'errore viene
   letto; a registrazione riuscita viene annunciato "Registrazione
   completata: puoi avviare il check" (regione di stato).
3. **Configurazione** — le sezioni collassabili annunciano
   espanso/compresso (`aria-expanded` dei bottoni accordion); i
   suggerimenti sotto i campi sono letti insieme al campo
   (`aria-describedby`); i tre campi del gruppo Lighthouse
   (attivazione, dispositivo, pagine) annunciano etichetta e
   suggerimento — che dichiara il motivo quando i requisiti
   mancano sul server ("Non disponibile sul server: …").
4. **Avvio e avanzamento** — premuto "Avvia audit", il focus va
   sull'intestazione "Avanzamento"; le fasi ("Fase [1/5]...") sono
   annunciate dalla regione `role="status"` senza rubare il focus;
   il bottone "Annulla audit" è raggiungibile e, annullando, viene
   annunciato l'esito.
5. **Risultati** — il focus arriva su "Risultati dell'audit:
   sintesi e referto"; con la navigazione per titoli si
   raggiungono le altre quattro sezioni ("Risultati dell'audit:
   Meta-fusion / Accessibility / Ranking / Security"), annunciate
   come compresse; i punteggi per area sono pulsanti con etichetta
   esplicita ("...apri i rilievi di quest'area") e attivandoli si
   viene portati alla sezione MARS di pertinenza, che si espande;
   le gravità dei rilievi sono lette come testo
   (Critico/Avvertenza/...), mai solo colore; le tabelle (RRF,
   storico) hanno intestazioni e didascalie annunciate. Con
   Lighthouse eseguito: i badge "Lighthouse" e "confermato da
   Lighthouse" sui rilievi sono testo leggibile; nella sintesi le
   chip di categoria e le tile Core Web Vitals annunciano
   punteggio e verdetto come testo con simbolo (✓/!/✕), e la nota
   sui dati di laboratorio è leggibile subito dopo il pannello;
   i delta ("Lighthouse Prestazioni: ▲ +5") usano le frecce
   testuali del confronto.
6. **Download negato** — con profilo incompleto, i pulsanti di
   scarico annunciano lo stato disabilitato (`aria-disabled`) e la
   nota esplicativa è leggibile subito dopo.
7. **Widget grafici** — anello, donut e trend hanno un
   `aria-label` con il dato completo ("Punteggio complessivo 66 su
   100: da migliorare"); i dettagli decorativi sono `aria-hidden`.
   Il grafo dei link (motore evoluto, v2.30.0): i nodi annunciano
   etichetta, link in ingresso/uscita e profondità; i bottoni
   "Vista a forza"/"Anelli di profondità" annunciano lo stato
   (`aria-pressed`); il clic su un nodo blocca l'evidenziazione e
   la regione di stato lo dichiara ("Esc per liberarla"); la
   ricerca annuncia quante pagine corrispondono; con
   `prefers-reduced-motion` nessuna animazione.
8. **Referto HTML interattivo** (aperto in una nuova scheda) — la
   treemap della superficie contenutistica ha rettangoli
   raggiungibili con Tab che annunciano pagina, parole, chunk e
   gravità; i dettagli compaiono anche in una regione
   `role="status"` e la **tabella di fallback** (in un `<details>`)
   contiene tutti i dati; il grafo dei link ha nodi focusabili con
   `<title>` parlante (link in ingresso e in uscita compresi),
   pulsanti etichettati per zoom e cambio vista (forza/anelli, con
   `aria-pressed`), evidenziazione bloccabile col clic (Esc la
   libera) e dettagli in regione di stato; senza JavaScript, in
   stampa o con `prefers-reduced-motion` resta la resa statica
   completa.

### Registro degli esiti

Compilare una riga per sessione di verifica (l'esecuzione richiede
una persona con lo screen reader attivo: non è automatizzabile).

| Data | AT + browser | Versioni | Flussi | Esito | Note / anomalie |
|---|---|---|---|---|---|
| 2026-08-04 | *(strumentale, non AT)* albero di accessibilità via Chrome+Playwright | GUI 2.16.0, audit 1.37.0 | 1–7 | 23/23 OK | Verifica del contratto ARIA, **non** sostituisce la sessione umana; dettagli in §1.1 |
| 2026-08-05 | *(strumentale, non AT)* albero di accessibilità via Chrome+Playwright (macOS) | GUI 2.19.0, audit 1.43.0 | 1–7 | 27/27 OK | Riesecuzione dopo le cinque sezioni risultati (v2.19.0), con 4 controlli nuovi sul loro contratto; dettagli in §1.1 |
| 2026-08-05 | *(strumentale, non AT)* albero di accessibilità via Chrome+Playwright (Linux) | GUI 2.27.0, audit 1.55.0 | 1–7 | 31/31 OK | Riesecuzione dopo l'integrazione Lighthouse, con 4 controlli nuovi sulle sue viste (stub di run_lighthouse); contrasti nuovi verificati a calcolo (≥ 6,48:1); dettagli in §1.1 |
| _da compilare_ | VoiceOver + Safari | | 1–8 | | |
| _da compilare_ | NVDA + Firefox | | 1–8 | | |

Anomalie rilevate → aprire una voce in [TO-DO.md](../TO-DO.md) con
il flusso, il comando AT usato e il comportamento atteso/ottenuto.
