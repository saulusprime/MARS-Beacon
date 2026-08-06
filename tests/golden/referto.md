# MARS Beacon — https://esempio.test/

*Meta-fusion, Accessibility, Ranking & Security Audit*

Pagine analizzate: 3 · chunk indicizzati: 4 · recuperatore vettoriale: `char-tfidf`

## Punteggi

| Area | Punteggio |
|---|---:|
| Tecnica | 52.5/100 |
| Lessicale (BM25) | 61.0/100 |
| Semantica (vettoriale) | 58.5/100 |
| Dati strutturati | 30.0/100 |
| Simulazione RRF | 66.7/100 |
| Performance (Lighthouse) | 74.0/100 |
| **Complessivo** | **58.1/100** |

## Profili di citabilita' per assistente IA

| Profilo | Cosa premia | Punteggio |
|---|---|---:|
| Claude (Anthropic) | contenuto estraibile, strutturato e autoconsistente | 53.7/100 |
| ChatGPT / Perplexity | consenso fra piu' indici (RRF) e segnali lessicali | 61.9/100 |
| Qwen (Alibaba) | markup semantico e dati strutturati | 46.0/100 |
| Kimi (Moonshot AI) | profondita' editoriale e completezza dell'argomento | 49.8/100 |
| **Indice composito (occidentale)** | | **56.6/100** |

> Stime euristiche ricavate dalle metriche di questo audit: le preferenze attribuite a ciascun assistente non sono comportamento documentato dai vendor.

## Rispetto all'esecuzione precedente (2026-07-30T10:00:00+0200)

Tecnica **+2.5** · Lessicale (BM25) = · Complessivo **+1.8**

**Risolti (1):**
- **[CRITICO]** n pagina/e senza <title>

**Nuovi (1):**
- [AVVISO] Nessuna sezione FAQ

## Giudizio LLM sulla citabilita'

Modello `claude-esempio` su 2 passaggio/i · media **71.5/100**.

| Query | Punteggio | Motivazione |
|---|---:|---|
| drenaggio linfatico costi | 78.0 | Risposta diretta con durata e prezzo. |
| controindicazioni drenaggio | 65.0 | Passaggio pertinente ma senza elenco esplicito. |

> Parere di un modello su un campione: non e' una misura riproducibile.

## Audit Lighthouse

Eseguito su 1 pagina/e (mobile), fork v13.4.1-mars.1.

- Prestazioni: **74/100**
- SEO: **88/100**

## Ancora di realta' (Brave Search)

Sito trovato per 1 query su 2 (primi 20 risultati).

- drenaggio linfatico costi — posizione **#4** (consenso RRF 3)
- controindicazioni drenaggio — assente dai primi 20 (consenso RRF 0)

> Il ranking reale dipende anche da personalizzazione, localita' e freschezza: confronto direzionale, non una validazione.

## Piano di remediation

- [ ] **1.** 1 query senza alcun risultato _(CRITICO · Simulazione RRF · sforzo: giorni)_
- [ ] **2.** 1 title non ottimizzati _(CRITICO · Lessicale (BM25) · sforzo: minuti · QUICK WIN · trasversale: 4 profili)_
- [ ] **3.** 1 pagina/e sotto 300 parole _(CRITICO · Lessicale (BM25) · sforzo: giorni · trasversale: 4 profili)_
- [ ] **4.** Sito non in HTTPS _(CRITICO · Tecnica · sforzo: ore · trasversale: 3 profili)_
- [ ] **5.** Crawler IA bloccati: GPTBot, ClaudeBot _(CRITICO · Tecnica · sforzo: minuti · QUICK WIN · trasversale: 3 profili)_
- [ ] **6.** Entita' principale non dichiarata _(AVVISO · Dati strutturati · sforzo: ore · trasversale: 3 profili)_
- [ ] **7.** Pochi paragrafi a risposta diretta _(AVVISO · Semantica (vettoriale) · sforzo: ore · trasversale: 4 profili)_
- [ ] **8.** Nessuna sezione FAQ _(AVVISO · Semantica (vettoriale) · sforzo: giorni · trasversale: 4 profili)_
- [ ] **9.** Consenso medio fra le liste: 1.5/5 (30%) _(AVVISO · Simulazione RRF · sforzo: giorni)_
- [ ] **10.** 1 pagina/e a piu' di 3 click dalla home _(AVVISO · Tecnica · sforzo: ore · trasversale: 3 profili)_
- [ ] **11.** Lighthouse: LCP lento _(AVVISO · Performance (Lighthouse) · sforzo: ore)_

## Rilievi per area

### Tecnica

- **[CRITICO]** Sito non in HTTPS
  _Fix: Attiva un certificato TLS e reindirizza tutto su HTTPS._
- **[CRITICO]** Crawler IA bloccati: GPTBot, ClaudeBot
  Questi agenti non possono accedere alla home. Se sono bloccati non entri in nessuna lista di recupero e l'RRF non ha nulla da fondere.
  _Fix: Rimuovi i Disallow per gli agenti da cui vuoi essere citato._
- [AVVISO] 1 pagina/e a piu' di 3 click dalla home
  https://esempio.test/vecchia-pagina/.
  _Fix: Accorcia i percorsi: le pagine profonde vengono scansionate e pesate meno._
- [ok] robots.txt presente
  12 righe.

### Lessicale (BM25)

- **[CRITICO]** 1 title non ottimizzati
  Esempi: 'Centro' (6 car.)
  _Fix: Title unico, 30-65 caratteri, con i termini di ricerca reali; evita il nome dominio come titolo._
- **[CRITICO]** 1 pagina/e sotto 300 parole
  Media sito: 440 parole. Con cosi' poco testo i termini utili non raggiungono una frequenza sufficiente perche' BM25 li valorizzi.
  _Fix: Porta le pagine chiave verso le 700+ parole con contenuto informativo, non promozionale._
- [ok] Meta description presenti e di lunghezza adeguata

### Semantica (vettoriale)

- [AVVISO] Pochi paragrafi a risposta diretta
  1 paragrafi su 12 aprono con una risposta esplicita in 20-120 parole (8% contro una soglia di prassi del 20%): sono i passaggi citabili da un assistente cosi' come sono.
  _Fix: Riscrivi i paragrafi chiave aprendo con la risposta ("X e' ...", "Si', ...", "In sintesi ...") e tienili fra 20 e 120 parole._
- [AVVISO] Nessuna sezione FAQ
  Le FAQ allineano un chunk a un intento preciso e alimentano entrambi gli assi insieme.
  _Fix: Aggiungi FAQ per pagina, marcate con JSON-LD FAQPage._
- [ok] E-E-A-T: contatti verificabili presenti

### Dati strutturati

- [AVVISO] Entita' principale non dichiarata
  _Fix: Aggiungi Organization o LocalBusiness con nome, indirizzo, contatti e riferimenti fiscali._
- [info] 1 data/e non in formato ISO 8601
  31/12/2025 (Service).
  _Fix: Usa AAAA-MM-GG, con l'ora facoltativa dopo la T (es. 2026-08-03T09:30:00+02:00)._

### Simulazione RRF

- **[CRITICO]** 1 query senza alcun risultato
  Nessun chunk del sito risponde: 'controindicazioni drenaggio'.
  _Fix: Crea contenuti dedicati a questi intenti._
- [AVVISO] Consenso medio fra le liste: 1.5/5 (30%)
  Consenso parziale fra i due recuperatori. Nella formula RRF un documento presente in entrambe le liste somma due addendi 1/(k+rank) e batte chi domina una lista sola. Consenso per query: 'drenaggio linfatico costi' 3/5, 'controindicazioni drenaggio' 0/5.
  _Fix: Ottimizza gli stessi passaggi su entrambi gli assi: termini espliciti (BM25) e spiegazione completa (vettoriale)._

### Performance (Lighthouse)

- [AVVISO] Lighthouse: LCP lento
  4,1 s; Pagine: https://esempio.test/
  _Fix: Riduci il peso dell'immagine principale e servila con priorita' alta._
- [ok] Lighthouse SEO: nessun rilievo
  Punteggio 88/100 sull'unica pagina esaminata.

## Simulazione RRF per query

| Query | Consenso | Primo passaggio fuso |
|---|---:|---|
| drenaggio linfatico costi | 3 | /  ·  Quanto costa una seduta? |
| controindicazioni drenaggio | 0 | (nessuno) |

## Share of voice (primi 5 posti fusi)

| Sito | Quota |
|---|---:|
| esempio.test ← tuo sito | 40.0% |
| concorrente.test | 60.0% |
