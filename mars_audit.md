# mars_audit.py — nota tecnica

Script Python 3 (PEP8, `flake8` pulito) per audit SEO + Reciprocal Rank Fusion
di un sito. Consegnato in chat il 2026-08-03. Versione 1.38.0, ~6420
righe (~6430), licenza MIT. Dal 2026-08-05 il prodotto si chiama
**MARS Beacon** (Meta-fusion, Accessibility, Ranking & Security
Audit); dal 2026-08-04 al 2026-08-05 si chiamava "MARS Audit".

Novità 1.1.0 (2026-08-03): tetto alla dimensione di ogni risposta HTTP
(default 10 MB, opzione `--max-body`): scarico a blocchi interrotto al
superamento, rifiuto immediato se il `Content-Length` dichiarato eccede,
esclusione riportata nel referto e avviso all'avvio se il valore scelto
supera un decimo della RAM disponibile.

Novità 1.2.0 (2026-08-03): opzione `--respect-robots` per rispettare i
`Disallow` del robots.txt rivolti all'agente `SeoRrfAudit`: gli URL
vietati non vengono scaricati (né dalla sitemap né in crawling) e sono
elencati nel referto come rilievo informativo. Predefinito spento.

Novità 1.2.1 (2026-08-03): referto HTML armonizzato al brand Lympha
Technologies (palette teal/arancio in chiaro e scuro, font Titillium
Web, firma aziendale nel footer).

Novità 1.3.0 (2026-08-03): retry con backoff esponenziale sugli errori
transitori (`--retries`, default 2): errori di rete e HTTP
429/500/502/503/504 ritentati con attese 0,5/1/2 s (tetto 8 s) e
rispetto di Retry-After; 404/403 e corpi oltre il limite mai ritentati.

Novità 1.4.0 (2026-08-03): confronto competitivo (`--competitor URL`,
ripetibile, max 3): corpora fusi negli stessi indici, share of voice
sui primi 5 posti fusi con soglie rispetto alla parità, elenco delle
query vinte dai concorrenti; sezione dedicata nei tre referti.

Novità 1.5.0 (2026-08-03): robustezza del crawling. Rilievi sulle
catene di redirect interne (301/302, http→https, www/non-www, catene
multiple); rilevamento euristico dei soft-404 (200 con contenuto
"pagina non trovata"); i Content-Type non analizzabili (PDF,
immagini, archivi) non vengono più scaricati — bastano stato e
header; sitemap compresse `.xml.gz` e prioritizzazione degli URL per
`lastmod` più recente quando `--max-pages` non copre tutto.

Novità 1.5.0, referto e GUI: widget grafici di sintesi in stile
Lympha (pattern mutuati da Lighthouse/Semrush/PSI): anello del
punteggio complessivo con verdetto testuale e soglie dichiarate
(40/70), tile Critici/Avvertenze/Informazioni, donut dello stato
pagine, meter del consenso RRF con tacche alle soglie 20%/45%,
tacca di parità sulle barre dello share of voice. Nella GUI i
punteggi-area sono cliccabili (aprono i rilievi dell'area) e i
risultati vengono ripristinati al ricaricamento della pagina.

Novità 1.6.0 (2026-08-03): auto-rilevamento di sentence-transformers.
Se la libreria è installata gli embedding reali si attivano da soli
con il modello multilingue predefinito
`paraphrase-multilingual-MiniLM-L12-v2`; `--embeddings MODELLO`
sceglie un modello diverso, `--embeddings none` forza il proxy
char-tfidf. Senza libreria il comportamento resta invariato.

Novità 1.7.0 (2026-08-03): qualità dell'analisi. Lista `AI_CRAWLERS`
rivista su documentazione ufficiale dei vendor (14 token; via Bingbot
— crawler di ricerca classico — e Claude-Web, deprecato; dentro
Claude-SearchBot, Claude-User, Perplexity-User, Meta-ExternalAgent,
Amazonbot, MistralAI-User); controllo di `/llms.txt`; validazione
delle proprietà minime dei tipi JSON-LD (incluse le coppie
domanda/risposta di FAQPage); segnali E-E-A-T (autore, date,
"chi siamo", contatti verificabili); grafo dei link interni con
pagine orfane, profondità oltre 3 click e anchor generiche.

Novità 1.7.1 (2026-08-03): ripiego robusto sugli ambienti embedding
rotti. Un'installazione incompatibile di sentence-transformers (es.
torch/numpy in conflitto, caso tipico su macOS Intel dove PyTorch si
ferma alla 2.2.2) sollevava errori diversi da ImportError durante
l'import: ora qualunque eccezione produce il ripiego pulito sul proxy
char-TFIDF, con il motivo dichiarato nel log. Nel README la
combinazione di versioni compatibile con macOS x86_64.

Novità GUI 1.7.0 (2026-08-03): interfaccia riorganizzata in tre
sezioni collassabili (accordion Bootstrap Italia, tema Lympha):
configurazione, avanzamento e "Risultati dell'audit e referto"
unificati — i download del referto vivono dentro i risultati. Le
sezioni si aprono e chiudono da sole seguendo il ciclo dell'audit.
Con la 1.7.1 l'anteprima incorporata (iframe) è stata rimossa:
faceva doppione con la pagina dei risultati, il referto HTML si
apre in una nuova scheda.

Novità 1.8.0 (2026-08-03): qualità del markup Schema.org. Proprietà
minime estese a 23 tipi (aggiunti Product, VideoObject, ImageObject,
Event, Recipe, HowTo, JobPosting, Review, AggregateRating,
NewsArticle, Course, MedicalBusiness/MedicalClinic) e controlli sui
valori: prezzi delle offerte numerici col punto e valuta ISO 4217
(accettato anche priceSpecification), Product senza offerte né
giudizi, ratingValue dentro la scala dichiarata con conteggio
recensioni, date in ISO 8601, URL di media assoluti in
image/logo/thumbnailUrl/contentUrl/embedUrl.

Novità 1.9.0 (2026-08-03): piano di remediation e rilievi più
dettagliati. Ogni rilievo può portare un esempio concreto di fix
(campo `example`: snippet JSON-LD, righe di robots.txt, testo
prima/dopo) e i tre referti più la GUI espongono un **piano di
remediation**: i rilievi critici e le avvertenze ordinati per
gravità × peso, ciascuno con correzione ed esempio. Dettagli
arricchiti: query verificate elencate nei rilievi RRF e nel
confronto competitivo, consenso per query, evidenze E-E-A-T (dove è
stato trovato autore/data/chi-siamo/contatti), URL nei rilievi su
canonical/description/H1, esempi di chunk anaforici e di heading
interrogativi.

Novità 1.10.0 (2026-08-03): audit annullabile. `run_audit()` e
`Fetcher` accettano uno `stop_event` (`threading.Event`): quando
scatta viene sollevata `AuditCancelled` alla prima occasione utile
(richieste HTTP, attese di throttle/backoff interrotte, download a
blocchi, confini di fase). Nella GUI (v1.9.0): endpoint
`POST /api/cancel`, stato `cancelled` e bottone "Annulla audit"
nella sezione Avanzamento; dopo l'annullamento il job accetta
subito un nuovo audit.

Novità GUI 2.0.0 (2026-08-03): account utente. Registrazione rapida
(nome, email, password e accettazione delle condizioni di servizio
con dichiarazione di proprietà del sito, pagina `tos.html`) o login;
solo gli utenti autenticati avviano il check, con limite di **un
check all'ora per utente** (un annullamento non consuma lo slot); il
download dei referti richiede la **registrazione completa** (azienda
e telefono nel profilo, completabili anche dopo). Utenti e sessioni
su SQLite locale (`mars_gui.db`, nel `.gitignore`), password con
PBKDF2-SHA256 e salt per utente, sessioni con cookie HttpOnly
SameSite=Strict. Nuovi endpoint: `/api/register`, `/api/login`,
`/api/logout`, `/api/me`, `/api/profile`; `/api/audit`, `/api/status`
e `/api/report/*` ora richiedono la sessione (i referti anche il
profilo completo).

Novità GUI 2.1.0 (2026-08-03): avanzamento push con Server-Sent
Events (`GET /api/events`, con ripiego automatico sul polling);
**storico degli audit per utente** su SQLite con nuova sezione nella
pagina — tabella delle esecuzioni con delta del punteggio rispetto
al run precedente dello stesso sito e grafico dell'andamento del
punteggio complessivo con soglie 40/70 (il widget "trend salute"
del concept board); **preimpostazioni di configurazione** salvabili
per cliente/sito in localStorage (salva/carica/elimina).

Novità 1.11.0 (2026-08-04): scansione concorrente con rate limit
preservato (`--workers`, default 4, max 16, 1 = seriale). Il
`Fetcher` è thread-safe: throttle che assegna atomicamente gli slot
di partenza (gli avvii restano distanziati di `--delay` anche fra
thread), sessione HTTP ed esito d'errore per-thread. Il download
delle pagine (sito e concorrenti) usa un pool di worker che si
limita a sovrapporre le attese di rete: a parità di ritmo verso il
sito, il tempo di scansione si avvicina a max(delay, latenza) per
pagina invece di delay + latenza. Annullamento funzionante anche coi
worker in attesa. Nella GUI (v2.2.0): campo "Richieste in parallelo"
nel form, incluso nelle preimpostazioni.

Novità 1.12.0 (2026-08-04): rendering JavaScript facoltativo
(`--render off|auto|always`, richiede Playwright; usa il Chromium di
Playwright o il Chrome/Chromium di sistema come ripiego). In `auto`
vengono rese solo le pagine che l'euristica classifica come
client-side; in `always` tutte. I metadati HTTP (stato, redirect,
tempi, dimensioni) restano quelli della risposta reale: il browser
sostituisce solo l'estrazione del contenuto (`extract_content`
separata da `parse_page`). Il rilievo critico "testo scarso e molto
JavaScript" continua a scattare anche sulle pagine renderizzate
(`raw_js_heavy`): i crawler IA senza JavaScript non vedono comunque
il contenuto. Il rendering è seriale (l'API sync di Playwright non è
thread-safe), rispetta `--delay` e l'annullamento; verifica di
disponibilità all'avvio (errore d'uso se Playwright/browser
mancano); rilievi informativi sul numero di pagine rese e avviso su
quelle non riuscite (analizzate in statico). Nella GUI (v2.3.0):
select "Rendering JavaScript" nel form, nelle preimpostazioni;
`render_available` in /api/env.

Novità 1.13.0 (2026-08-04) — CAMBIO DI COMPORTAMENTO: i Disallow del
robots.txt per l'agente SeoRrfAudit sono ora **rispettati di
default** (prima erano ignorati). `--own-site` dichiara la
titolarità del sito e ripristina l'audit completo (i concorrenti di
--competitor restano sempre protetti); `--ignore-robots accetto`
ignora i Disallow ovunque con accettazione esplicita di
responsabilità (valore letterale obbligatorio, registrata come
rilievo informativo nel referto); `--respect-robots` è deprecato
(ora è il default) e confligge con le altre due. Nella GUI (v2.4.0):
select a tre modalità con default "sito di mia titolarità" (coperta
dalla dichiarazione nelle condizioni di servizio accettate alla
registrazione) e, per "ignora", checkbox di assunzione di
responsabilità obbligatoria validata lato server.

Novità 1.14.0 (2026-08-04): colmato il divario col referto consegnato
a mano. **"La matematica del problema"** in tutti i referti e nella
GUI: superficie attuale (pagine, chunk, parole medie) contro
superficie potenziale con proiezione prudente e dichiarata (ogni
pagina esistente ad almeno ~900 parole, 4 chunk, più una FAQ; nessuna
pagina nuova) e moltiplicatore dell'effetto sull'RRF. **Stima dello
sforzo per intervento** nel piano di remediation (minuti/ore/giorni,
classificatore per parole chiave su titolo e fix) incrociata con la
priorità: i critici risolvibili in minuti sono marcati **quick win**
(badge nei referti HTML/GUI, marcatore nel testuale, campi `effort` e
`quick_win` nel JSON insieme a `surface_math`). GUI v2.5.0.

Novità 1.14.1 (2026-08-04): log di avanzamento pulito con gli
embedding attivi. Il caricamento del modello contatta l'HF Hub e
senza token stampava su stderr l'avviso inglese sui rate limit (piu'
eventuali barre di download), che finiva nel log della GUI: ora
l'ecosistema Hugging Face viene zittito prima dell'import (variabili
d'ambiente non gia' impostate dall'utente + logger a livello error).
L'avviso era innocuo; chi vuole limiti piu' alti puo' esportare
HF_TOKEN, letto automaticamente dalle librerie.

Novità 1.15.0 (2026-08-04): profili di citabilità per assistente IA
("lenti per modello", da Features.md). `citability_profiles()` ripesa
i punteggi di area — più la "profondità editoriale" (parole medie per
pagina rapportate al target di 900 di `surface_math`) — secondo ciò
che ciascun assistente plausibilmente premia: Claude
(semantica/lessicale/tecnica/dati 40/25/20/15), ChatGPT-Perplexity
(RRF/lessicale/tecnica/semantica 45/25/15/15), Qwen
(dati/tecnica/semantica/lessicale 40/25/20/15), Kimi
(profondità/semantica/dati/lessicale 35/30/20/15). Indice composito
pesato per mercato (`--market occidentale|globale|orientale`, default
occidentale: chatgpt 50, claude 30, qwen/kimi 10). Le componenti
senza punteggio vengono escluse rinormalizzando i pesi. Presente nei
tre referti (chiave JSON `citability`, sezione testuale, tabella
HTML) sempre accompagnato dalla nota di onestà: stime euristiche
ricavate dalle metriche dell'audit, non comportamento documentato dai
vendor. 12 test dedicati con ancoraggi calcolati a mano.

Novità 1.16.0 (2026-08-04): vista dei profili di citabilità.
`citability_top_actions()` annota le prime voci del piano di
remediation con il profilo che guadagna di più da ciascun intervento:
la variazione d'area alla risoluzione del rilievo è esatta rispetto
al modello di punteggio (peso × (1 − fattore di gravità) / somma dei
pesi dell'area) e viene proiettata sui pesi rinormalizzati di ogni
profilo; l'ordinamento coincide con quello del piano. Nei referti:
blocco "Azioni con maggior guadagno di profilo" nel testo, "Top N
azioni prioritarie" con badge sforzo/quick-win nell'HTML (dove i
profili hanno ora anche le barre), chiave `citability_actions` nel
JSON.

Novità GUI 2.6.0 (2026-08-04): profili di citabilità nella GUI.
Select "Mercato di riferimento" nel form (occidentale/globale/
orientale, inclusa nelle preimpostazioni, validata lato server e
propagata ai tre referti scaricabili); nei risultati il blocco
"Profili di citabilità per assistente IA" con barre per profilo
(stesso pattern accessibile dei punteggi per area: valore sempre
testuale), cosa premia ciascun profilo, indice composito, pesi del
mercato, nota di onestà e "Top azioni prioritarie" con badge
sforzo/quick-win e guadagno stimato. Il summary di `/api/status`
espone `citability` e `citability_actions`. Verifica visiva con
Chrome reale su un audit end-to-end (form, blocco risultati,
referto) e lint di accessibilità sull'HTML della GUI.

Novità 1.17.0 (2026-08-04): problemi trasversali nel piano di
remediation. `build_remediation()` accetta ora anche pages/scores/
market: quando li riceve (sempre, nei tre referti e nella GUI)
annota ogni intervento con i guadagni per profilo di citabilità
(refactoring in `_citability_gains`), il guadagno sull'indice
composito (`index_gain`), i profili colpiti con almeno
`CROSS_GAIN_MIN`=1.0 punti (`profiles_hit`) e il flag `cross`
(≥2 profili = trasversale). A parità di gravità l'ordinamento
promuove il maggior guadagno sull'indice del mercato scelto: i
problemi trasversali salgono in testa perché sommano guadagni su
più profili, ma un rilievo a profilo singolo con guadagno maggiore
li supera — l'ordine misura la resa complessiva, il badge la
trasversalità. Senza dati di citabilità il comportamento resta
gravità+peso (retrocompatibile, test invariati).
`citability_top_actions()` ora è la testa del piano annotato:
stesse priorità per costruzione. Nei referti: riga "Trasversale:
deprime N profili (+X.X sull'indice)" nel testo, badge nel piano
HTML; GUI 2.7.0: badge "trasversale: N profili · +X,X indice" e
intestazione del piano aggiornata. Verifica visiva su audit reale.

Novità 1.18.0 (2026-08-04): giudizio LLM sulla citabilità ("LLM as
judge"), **attivo di default** in modalità `auto` per decisione di
progetto: parte da solo se l'SDK `anthropic` e la chiave
`ANTHROPIC_API_KEY` sono presenti, altrimenti viene saltato con
motivo dichiarato nel referto — l'audit resta interamente offline.
`run_judge()` è un passo separato dopo `run_audit()` (che non
contatta mai l'API): campiona il primo passaggio fuso di ogni query
(deduplicato, max 5), una sola richiesta all'API Anthropic (SDK
ufficiale, `claude-opus-5`, fallback server-side come nel monitor
citazioni, `ANTHROPIC_BASE_URL` per i test), risposta solo-JSON con
punteggio 0–100 e motivazione per passaggio. `--judge auto|on|off`
(`on` pretende la chiave: errore d'uso senza). Errori API, refusal
e JSON malformato non fermano mai il referto (status `error` con
motivo). Nei referti: sezione dedicata con media, **scarto
giudice-euristica** rispetto all'indice composito (la "taratura"
delle stime) e nota di onestà. GUI 2.8.0: select nel form (auto
default; "obbligatorio" validato lato server contro la
disponibilità), disponibilità esposta da `/api/env`, blocco
risultati con tabella dei verdetti. 10 test dedicati con server
API finto (`tests/test_judge.py`) e fixture autouse in conftest
che rimuove le chiavi dall'ambiente: la suite resta offline per
costruzione.

Novità GUI 2.9.0 (2026-08-04): citazioni IA nel tempo. La GUI legge
lo storico JSONL del monitor citazioni (`GET /api/citations`,
accesso richiesto; percorso configurabile con
`--citations-history`, default `citazioni.jsonl` accanto agli
script, nel deploy `/var/lib/seorrf/citazioni.jsonl`) e lo mostra
in una sezione dedicata: sintesi con tendenza per provider (delta
rispetto all'esecuzione precedente), grafico SVG multilinea del
tasso di citazione (una linea per provider più il complessivo,
tratteggi diversi ed etichette di fine linea — mai solo colore) e
tabella accessibile con tutti i valori; selettore del sito quando
lo storico ne contiene più d'uno. Il parser
(`read_citations_history`) raggruppa per sito, ignora le righe
malformate e non rompe mai la GUI se il file manca. 3 test
dedicati; verifica visiva con Chrome reale su uno storico di
esempio.

Novità GUI 2.10.0 (2026-08-04): storico e delta per utente e
dominio — l'audit diventa monitoraggio. Il referto JSON completo di
ogni esecuzione viene salvato nel database SQLite (colonna
`report_json` nella tabella `audits`, con migrazione automatica dei
DB creati prima) ed è esportabile da `GET /api/history/report?id=N`
(riservato al proprietario, profilo completo richiesto; link "JSON"
per riga nella tabella dello storico). A fine audit il server
confronta il referto con il precedente dello stesso utente e
dominio (`compute_delta`): differenze dei punteggi per area e
complessivo, e rilievi **nuovi/risolti** confrontando critici e
avvertenze per (area, titolo normalizzato — i conteggi nei titoli
diventano N, così "5 title non ottimizzati" → "2 title non
ottimizzati" è lo stesso problema che migliora, non un rilievo
nuovo+risolto; euristica dichiarata nella GUI). Il blocco
"Rispetto all'esecuzione precedente" nei risultati mostra i delta
con frecce testuali e le due liste con badge di gravità. 5 test
dedicati (delta calcolato a mano, migrazione dello schema, export
con proprietà e gating, doppio audit end-to-end); verifica visiva
con sito modificato fra le due esecuzioni (FAQ aggiunta → 2 critici
risolti, semantica +22,7).

Novità 1.19.0 (2026-08-04): storico e delta nella CLI. Il confronto
fra esecuzioni è migrato nel core (`compute_delta`, `_finding_key`;
la GUI 2.11.0 lo riusa via alias) e la CLI guadagna `--history
FILE`: legge l'ultima riga JSONL dello stesso sito, riporta il
delta nei **tre referti** (sezione "Rispetto all'esecuzione
precedente": variazioni dei punteggi per area, rilievi
nuovi/risolti con gravità, chiave `delta` nel JSON) e accoda una
riga compatta per l'esecuzione corrente (`history_payload`: solo
punteggi e rilievi azionabili — abbastanza per il delta, abbastanza
poco da tenere lo storico leggero; `read_history_last` ignora righe
malformate e file assente, `append_history` fallisce con un avviso
senza rompere l'audit). Stesso pattern JSONL del monitor citazioni:
audit schedulato da cron + storico = monitoraggio headless. GUI
2.11.0: il delta è calcolato prima dei render, così anche i tre
referti scaricati includono la sezione. 4 test nuovi (181 totali)
con doppia esecuzione CLI end-to-end.

Novità 1.20.0 (2026-08-04): stopword e pattern linguistici oltre
it/en — aggiunti **francese, tedesco e spagnolo**. Estesi:
STOPWORDS (liste compatte curate a mano, nessuna dipendenza),
DEFINITION_RE ("est une", "il s'agit de", "ist eine", "versteht
man", "es una", "se trata de"…), EXAMPLE_RE ("par exemple", "zum
Beispiel", "beispielsweise", "por ejemplo"…), ANAPHORA_RE ("cela",
"diese", "esto", "dicha"… — i pronomi nudi tedeschi es/er/sie
restano fuori apposta: "Es gibt…" è un espletivo, non un'anafora),
FAQ_HINT_RE ("foire aux questions", "häufig gestellte Fragen",
"preguntas frecuentes"…), QUESTION_STARTERS (con gestione del "¿"
spagnolo in is_question). Le query auto-generate ora usano i
template della **lingua prevalente del sito** (`dominant_language`
dagli attributi lang; QUERY_TEMPLATES it/en/fr/de/es, default
italiano invariato — anche per le lingue non supportate). 8 test
nuovi (189 totali) con frasi campione nelle tre lingue.

Novità 1.21.0 (2026-08-04): opt-out IA di Microsoft. Microsoft non
ha un token robots.txt dedicato all'IA (Bingbot è ricerca
classica): l'uso dei contenuti in Bing Chat/Copilot e nel training
si governa coi meta robots, e l'area tecnica ora li controlla
(`_audit_msft_ai_optout`, semantiche verificate sulla fonte
primaria e citate nel codice — Bing Blogs, settembre 2023).
`noarchive` → avvertenza (esclusione totale dalle risposte Copilot
e dal training: citabilità zero sul canale Microsoft; la ricerca
classica non cambia); `nocache` → informativo (presenza parziale:
solo URL, titolo e snippet, anche per il training); assenti → OK
informativo che spiega il default e come attivare l'opt-out. Il
meta scoped `<meta name="bingbot">` prevale su quello generico,
come documentato da Microsoft. Nuovo campo `Page.bingbot_meta`;
sforzo classificato "minuti". 4 test nuovi (193 totali).

Novità 1.22.0 (2026-08-04): estraibilità diretta (primo dei
controlli distillati da Features.md). L'area semantica misura la
quota di paragrafi di 20–120 parole che aprono con una risposta
esplicita — sì/no secco, "in sintesi", passo numerato
(`DIRECT_ANSWER_RE`, nelle cinque lingue della v1.20) o una
definizione nelle prime battute (riuso di `DEFINITION_RE`, come
previsto dal TO-DO). Denominatore: i paragrafi sostanziosi (≥ 10
parole), per non farsi gonfiare il conto dal boilerplate. Sotto la
soglia di prassi del 20% (dichiarata nel referto) scatta
un'avvertenza con esempio prima/dopo; sopra, un OK con i conteggi.
Il rilievo vive nell'area semantica, quindi alimenta la lente
Claude dei profili di citabilità senza ritocchi ai pesi. 5 test
nuovi (198 totali), incluso il caso multilingue.

Novità 1.23.0 (2026-08-04): titoli clickbait (da Features.md).
L'area lessicale scandisce title e H1–H3 (non il corpo, per
contenere i falsi positivi) con `CLICKBAIT_RE` nelle cinque
lingue: "non crederai…", "il segreto di/del…", "la verità su…",
"N motivi per…", esclamazioni multiple e gli equivalenti
en/fr/de/es. Formule trovate → avvertenza (peso 1.5, sforzo
"minuti") con evidenze (URL, origine e testo) ed esempio
prima/dopo; nessuna → OK. Razionale dichiarato come euristica: un
titolo sensazionalistico non risponde a niente, e i motori
generativi selezionano titoli informativi. 3 test nuovi (201
totali); trappola incontrata: le preposizioni articolate ("il
segreto DEL…") vanno coperte esplicitamente nella regex.

Novità 1.24.0 (2026-08-04): densità informativa (da Features.md).
L'area semantica rileva il **filler di marketing** ("leader di
mercato", "scopri di più", "contattaci per…", "qualità e
professionalità" e gli equivalenti en/fr/de/es in `FILLER_RE`) e
segnala le pagine **sature**: almeno 3 formule *e* almeno una ogni
100 parole (entrambe le soglie, di prassi e dichiarate nel referto
— il doppio requisito evita di punire una pagina lunga con tre
call-to-action legittime). Avvertenza con evidenze (URL, conteggio
e le formule trovate) ed esempio prima/dopo che sostituisce il
filler con fatti verificabili; sotto soglia, OK con il conteggio
totale. Pagine sotto le 50 parole escluse (il rumore dei
segnaposto è già coperto altrove). 5 test nuovi (206 totali).

Novità 1.25.0 (2026-08-04): ciclo di vita dell'argomento (da
Features.md). L'area semantica verifica in title e heading H1–H4
dell'intero sito la copertura delle **sei sezioni canoniche** di
una trattazione completa: definizione, storia, casi d'uso, limiti,
FAQ, prospettive (`LIFECYCLE_SECTIONS`, cinque lingue). Soglie di
prassi dichiarate: 5+/6 → OK con gli heading trovati come
evidenza; 3–4 → avvertenza (peso 1) con l'elenco delle mancanti;
0–2 → avvertenza pesante (peso 2). Il fix genera un **canovaccio
di heading** per le sole sezioni mancanti (`LIFECYCLE_HINTS`),
pronto per il piano di remediation; sforzo "giorni" (è lavoro di
contenuto). La copertura può essere distribuita su più pagine: si
valuta il sito, non la singola pagina. Alimenta la lente Kimi dei
profili di citabilità. 4 test nuovi (210 totali), incluso il caso
tedesco completo.

Novità 1.26.0 (2026-08-04): riferimenti bibliografici (da
Features.md). Tre segnali sull'intero sito, a completamento
dell'E-E-A-T: una **sezione fonti** negli heading H2–H4
(`REFERENCES_HEADING_RE`: fonti, bibliografia, sitografia,
references, Quellen, fuentes…), le **citazioni accademiche** nel
testo (`CITATION_RE`: `[1]` o "(Autore, anno)") e i link esterni
riportati come contesto — "fonti primarie" non è verificabile
offline, quindi i link sono un indizio dichiarato, non un
giudizio. Basta una sezione fonti *o* almeno 3 citazioni per l'OK
(soglia di prassi); altrimenti avvertenza con esempio di sezione
Fonti pronto (ISS, PubMed). Sforzo "ore". 5 test nuovi (215
totali). Trappola: `.capitalize()` minuscolizza il resto della
stringa — mai usarlo su testo che contiene evidenze citate.

Novità 1.27.0 (2026-08-04): freschezza dei contenuti (da
Features.md). La *presenza* delle date era già un segnale E-E-A-T:
ora se ne valuta l'**età**. `_page_last_update` raccoglie la data
più recente dichiarata da ogni pagina (meta
article:published/modified_time e datePublished/dateModified nel
JSON-LD, formati non ISO ignorati); `_audit_freshness` giudica
l'aggiornamento più recente dell'intero sito con soglie di prassi
a **un anno** (avvertenza) e **due anni** (peso doppio), elencando
le pagine più datate come evidenza. Senza alcuna data non c'è
rilievo: il difetto è già coperto dall'E-E-A-T, e non si punisce
due volte. Fix con meta `article:modified_time` pronto datato a
oggi; sforzo "giorni". Il parametro `today` iniettabile rende i
test deterministici. 5 test nuovi (220 totali).

Novità 1.28.0 (2026-08-04): HTML semantico e "divitis" (da
Features.md). `extract_content` conta per ogni pagina i tipi di
tag di sezionamento presenti (`SEMANTIC_TAGS`: article, section,
main, aside, details, figure…), i `<div>` e gli elementi totali
(nuovi campi `Page.semantic_tag_types`/`div_count`/
`element_count` — sul DOM renderizzato quando `--render` è
attivo). `_audit_semantic_html`, nell'area dati strutturati (il
focus della lente Qwen recita già "markup semantico e dati
strutturati"), emette due avvertenze con soglie di prassi
dichiarate: pagine con meno di 2 tipi di tag semantici (con
scheletro `<main><article><section>` nel fix) e pagine con più
della metà degli elementi `<div>` (divitis, con la percentuale
per URL come evidenza); entrambe a posto → OK. Le pagine sotto i
30 elementi sono fuori dal conto. Razionale: i chunker dei motori
generativi segmentano sui tag di sezionamento. 4 test nuovi (224
totali) su pagine HTML reali passate da parse_page.

Novità 1.29.0 (2026-08-04): meta di base (da Features.md).
L'area tecnica valuta charset e viewport (nuovi campi
`Page.has_charset`/`has_viewport`) e — finalmente — la
**completezza Open Graph**: gli `og:*` erano estratti fin dalla
v1.0 senza mai essere giudicati. Quattro avvertenze possibili,
tutte "minuti": pagine senza charset, senza viewport, senza alcun
og:* (con la triade og:title/og:description/og:image pronta
nell'esempio — le anteprime nei link condivisi e in molte
risposte degli assistenti si costruiscono da lì), e Open Graph
incompleto con l'elenco di cosa manca per URL. Tutto a posto →
un solo OK cumulativo per non fare rumore. 3 test nuovi (227
totali) su pagine HTML reali.

Novità 1.30.0 (2026-08-04): varietà degli anchor interni — ultimo
dei **nove controlli distillati da Features.md, ora tutti
realizzati** (v1.22.0→v1.30.0). `extract_content` raccoglie le
coppie (testo, destinazione) dei link interni (nuovo campo
`Page.internal_anchors`, testi ≥ 3 caratteri, minuscoli). Il
controllo deduplica le coppie sull'intero sito — **il menu
identico su ogni pagina conta una volta**, evitando il falso
positivo strutturale — e misura testi unici / coppie uniche: sotto
l'80% (soglia di prassi) lo stesso testo punta a destinazioni
diverse ("leggi tutto" → 8 pagine) e chi legge, umano o modello,
non può prevedere dove porta il link. Avvertenza con i testi
ambigui come evidenza ed esempio prima/dopo; sotto le 10 coppie
non si giudica. Nell'area tecnica, accanto alle anchor generiche
che estende. 5 test nuovi (232 totali).

Novità 1.31.0 (2026-08-04): parametri della simulazione RRF
esposti. `--top-n` (1–20, default 5: posti fusi per query, governa
consenso e share of voice — le soglie 20%/45% si adattano perché
sono percentuali di top_n); `--rrf-weights LES,VET` (**variante
RRF pesata**: `score(d)=Σ w_i/(k+rank_i)`, "1,1" è l'RRF classico;
`reciprocal_rank_fusion` accetta ora `weights`, usata anche dallo
share of voice); `--chunk-words` (80–600, default 220: il taglio
segue comunque gli heading; i chunk vengono ricostruiti dopo il
crawl anche per i concorrenti). Il JSON echeggia i parametri nel
blocco `rrf` (top_n, weights, chunk_words) per la riproducibilità.
GUI 2.12.0: quattro campi nel fieldset "Recupero e fusione" (posti
fusi, parole per chunk, pesi delle due liste), validati lato
server e inclusi nelle preimpostazioni. 5 test nuovi (237 totali)
con la fusione pesata ancorata a mano (2/61+1/62). Nota di
architettura: il chunking di default resta in extract_content; con
un target diverso i chunk si ricostruiscono dai blocchi conservati.

Novità 1.32.0 (2026-08-04): query reali da Google Search Console.
`--queries-gsc CSV` legge l'export "Query" del rapporto Rendimento
(`load_gsc_queries`: intestazioni italiane o inglesi, virgola o
punto e virgola, BOM tollerato, separatori delle migliaia
ignorati — clic e impressioni sono interi), ordina per clic poi
impressioni, deduplica e usa le prime 15 come query della
simulazione: le domande vere degli utenti al posto dei bigrammi
auto-generati. Non combinabile con `--queries` (errore d'uso
esplicito); righe illeggibili ignorate senza fermare l'import.
Chiude "Simulazione RRF più realistica" insieme al provider
OpenAI del monitor citazioni (v1.1.0): Responses API con
`web_search` — citazioni dalle annotation `url_citation`, fonti
consultate dal campo `sources` dell'item `web_search_call`
(semantiche verificate su developers.openai.com e citate nel
codice), chiave solo da `OPENAI_API_KEY`, modello `gpt-5.6`
configurabile con `--openai-model`, server finto nei test come
per gli altri provider. La GUI mostra il terzo provider nello
storico citazioni senza modifiche (colonne e linee sono
dinamiche). 8 test nuovi (245 totali).

Novità 1.33.0 (2026-08-04): `schema_version` nel JSON.
`JSON_SCHEMA_VERSION = 1` compare nel referto JSON e nelle righe
dello storico `--history` (i due formati persistiti a lungo).
Contratto dichiarato nel codice: l'intero si incrementa **solo per
cambi incompatibili** della struttura (campi rinominati/rimossi o
semantica cambiata); le aggiunte di campi non lo toccano. I
consumatori (pipeline, integrazioni, la stessa GUI) possono fare
il gate su questo numero invece di interpretare la versione dello
strumento, che cambia a ogni feature. 1 test nuovo (246 totali).

Novità 1.34.0 (2026-08-04): renderer **Markdown** ed export **CSV**
(`--format md|csv`, quinta e sesta uscita accanto a text/json/
html). Il Markdown è GitHub-flavored, pensato per issue e PR: il
**piano di remediation è una task list `- [ ]`** che incollata in
una issue diventa una checklist spuntabile; punteggi, profili di
citabilità, giudizio LLM, delta, rilievi per area, RRF per query e
share of voice in tabelle, gravità come marcatori testuali, pipe
escapate nelle celle. Il CSV è **una riga per rilievo** (sito,
area, gravità, peso, titolo, dettaglio, correzione, URL, sforzo,
quick win — gli ultimi due solo per i rilievi azionabili), con
delimitatore `;` e **BOM UTF-8** in testa per l'apertura diretta
in Excel/Sheets. GUI 2.13.0: entrambi scaricabili dai risultati
("Scarica Markdown", "Scarica CSV rilievi"), stesso gating del
profilo completo. 3 test nuovi (249 totali), incluso il quoting
CSV con `;` e `|` nei dettagli.

Novità 1.35.0 (2026-08-04): completata la sezione widget del TO-DO
(GUI 2.14.0). Quattro consegne: **Top rilievi** — la testa del
piano di remediation come vista compatta trasversale alle aree
(pallino + etichetta testuale + guadagno sull'indice), nel referto
HTML sotto l'hero e nella GUI sopra i punteggi; **pin-evento** sul
grafico delle citazioni — gli eventi vivono in `eventi.jsonl`
accanto allo storico citazioni (una riga JSON per evento: date,
label, site opzionale; `read_citations_events` ignora righe rotte
e file assente) e la GUI disegna la linea tratteggiata
sull'esecuzione successiva all'evento più la lista testuale
"Eventi annotati" (mai solo grafica); **badge NUOVO** sui singoli
rilievi in fisarmonica, abbinando i rilievi correnti alle voci
`new` del delta per (area, titolo normalizzato); **confronto fra
due audit scelti** dallo storico — `GET /api/history/compare?a=&b=`
carica i due referti salvati dello stesso sito (400 se siti
diversi, ordina per data da solo) e la GUI offre due select con
"Confronta" e il risultato in stile delta. Pa11y locale rieseguito
prima del push (3/3), heading senza salti. 4 test nuovi (252
totali).

Novità 1.36.0 (2026-08-04): le idee-widget rimandate (GUI 2.15.0).
**Distribuzione della profondità di crawl**: `depth_distribution`
riusa il BFS del grafo dei link (refactoring in `_build_link_edges`
e `_bfs_depths`) e produce i bucket 0/1/2/3/4+ click più "solo da
sitemap"; barre nel referto HTML e nella GUI, chiave
`depth_distribution` nel JSON. **Mappa a bolle del posizionamento
competitivo** (pattern Semrush): lo share of voice ora espone anche
`presence` (in quante query il sito compare) e `queries_total`;
bolla per sito con x = share, y = query coperte, raggio ∝ √chunk,
in GUI e referto HTML — decorativa (aria-label che rimanda alle
tabelle), i numeri restano nelle tabelle. **Form eventi nella
GUI**: `POST /api/citations/events` (accesso richiesto, data
AAAA-MM-GG validata, etichetta ≤ 120) accoda a `eventi.jsonl`; il
form nella sezione citazioni aggiorna subito grafico e lista.
Resta rimandato il solo grafo force-directed dell'architettura.
Pa11y locale 3/3 prima del push. 3 test nuovi (255 totali).

Novità 1.37.0 (2026-08-04): grafo force-directed dell'architettura
dei link interni — l'ultimo widget (GUI 2.16.0). Scelta
architetturale migliorativa rispetto alla nota del TO-DO: il
layout force (Fruchterman-Reingold, `_force_layout`) è calcolato
**in Python nel core**, deterministico (inizializzazione su
cerchio, niente casualità: stesso input → stesso disegno,
testabile) con la home ancorata al centro; così il **referto HTML
resta senza JavaScript** e la GUI disegna le stesse posizioni
precalcolate. `link_graph_data` limita i nodi a 60 (home per
prima, poi i più linkati), etichetta i primi 10, colora per stato
(home accent, oltre 3 click o solo-da-sitemap in ambra) e dà a
ogni cerchio un `<title>` con URL, link in ingresso e profondità;
chiave `link_graph` nel JSON. Con questo la sezione widget è
davvero conclusa. Pa11y 3/3; 3 test nuovi (258 totali), incluso
il determinismo del layout e il tetto ai nodi.

Novità 1.38.0 (2026-08-04): il prodotto si chiama **MARS Audit**
(Meta-fusion, Accessibility, Ranking & Security Audit) — era
"Audit SEO & Reciprocal Rank Fusion". Rinominate tutte le
superfici visibili: header e title della GUI (2.17.0, con
l'espansione come sottotitolo), tos.html, intestazioni dei
referti text/html/markdown, descrizione della CLI, unit systemd,
README e docstring. Nomi dei file, del repo e il campo `tool` del
JSON restano invariati (nessun cambio di schema); i test e la
verifica AT sono stati allineati al nuovo titolo.

Novità 1.39.0 (2026-08-04): grafo dei link **interattivo** in GUI
(2.18.0) e più leggibile nel referto — feedback dell'utente: la
resa statica non era leggibile. Nel referto HTML (che resta senza
JavaScript): canvas 780×540, layout con più iterazioni, nodi più
grandi, etichette a 11px con **alone di sfondo**
(`paint-order:stroke`, leggibili anche sopra gli archi), tutte
visibili fino a 20 nodi. Nella GUI il grafo diventa uno strumento:
**zoom** (rotella o pulsanti Ingrandisci/Riduci/Reimposta),
**pan** trascinando lo sfondo, **trascinamento dei nodi** per
districare le matasse, **evidenziazione del vicinato** al
passaggio o al focus da tastiera (i nodi sono focusabili, con
`aria-label` completa) e dettagli nella regione di stato
`role="status"` — niente informazione solo-hover. Layout iniziale
sempre dal core (deterministico); Pa11y 3/3.

## Uso

```
pip install requests beautifulsoup4 lxml
# opzionale, per il recupero vettoriale reale:
pip install sentence-transformers numpy

python3 mars_audit.py https://esempio.it --format html --output report.html
python3 mars_audit.py https://esempio.it --max-pages 40 --queries query.txt
python3 mars_audit.py https://esempio.it --embeddings paraphrase-multilingual-MiniLM-L12-v2
```

Opzioni: `--max-pages` (default 25), `--queries FILE` (una per riga; se omesso
le query sono generate dai bigrammi tematici del sito), `--embeddings MODELLO`
(auto-rilevato se la libreria è installata; `none` forza il proxy),
`--rrf-k` (default 60), `--delay`, `--max-body MB` (default 10; tetto al corpo
di ogni risposta, da dimensionare sulla RAM della macchina),
`--retries N` (default 2; ritenta errori di rete e HTTP 429/5xx con backoff
esponenziale), `--workers N` (default 4, max 16; scansione concorrente senza
cambiare il ritmo verso il sito), `--render off|auto|always` (rendering
JavaScript con Playwright/Chrome), `--own-site` / `--ignore-robots accetto`
(il rispetto dei Disallow è il default dalla 1.13.0), `--user-agent UA`,
`--competitor URL` (ripetibile, max 3; confronto competitivo con share of
voice), `--market occidentale|globale|orientale` (pesi dell'indice di
citabilità composito), `--judge auto|on|off` (giudizio LLM sui passaggi
migliori via API Anthropic; `auto`, il default, parte solo con
ANTHROPIC_API_KEY presente), `--history FILE` (storico JSONL: delta nei
referti e riga compatta accodata a ogni esecuzione), `--format
text|json|html`, `--output`, `--quiet`, `--version`.

Codici di uscita: `0` nessuna criticità, `1` almeno una criticità, `2` errore
d'uso, `130` interruzione.

## Cosa misura

Cinque aree con punteggio 0–100 e punteggio complessivo pesato (tecnica 1.0,
lessicale 1.5, semantica 1.5, dati strutturati 1.0, simulazione RRF 1.5):

1. **Tecnica** — HTTPS, `robots.txt` e permessi per i crawler IA (GPTBot,
   OAI-SearchBot, ClaudeBot, PerplexityBot, Google-Extended, CCBot,
   Applebot-Extended…), sitemap, URL in errore, pagine segnaposto del CMS,
   `noindex`, canonical, contenuto solo-JavaScript, hreflang, duplicati.
2. **Lessicale (BM25)** — title, meta description, struttura H1, conteggio
   parole, slug, attributi `alt`.
3. **Semantica (vettoriale)** — numero di chunk, autoconsistenza dei passaggi
   (anafore), heading in forma di domanda, FAQ, definizioni, esempi, ampiezza
   del vocabolario.
4. **Dati strutturati** — inventario dei tipi JSON-LD, entità principale,
   FAQPage, BreadcrumbList, WebSite.
5. **Simulazione RRF** — indicizza i chunk in BM25 e in un indice vettoriale,
   esegue le query, fonde le liste con `score(d) = Σ 1/(k + rank_i(d))` e
   misura la **sovrapposizione fra le due liste** (il "consenso"), che è il
   segnale operativo vero.

## Avvertenze di onestà incorporate nello script

- Senza `sentence-transformers` il recupero "semantico" ripiega su un coseno
  TF-IDF di 4-grammi di caratteri: è un **proxy morfologico, non una vera
  rappresentazione semantica**. Lo script dichiara sempre la modalità usata
  (`char-tfidf` o il nome del modello) in tutti e tre i formati di referto.
- La simulazione RRF riproduce la formula pubblicata, non l'implementazione
  interna di un motore specifico: pesi, `k` e re-ranking li decide il motore.
  Il valore diagnostico sta nel confronto fra le due liste, non nel punteggio
  assoluto.

## Verifiche eseguite prima della consegna

- `flake8` senza rilievi.
- Esecuzione end-to-end su un sito di prova servito in locale (robots.txt con
  `Disallow: GPTBot`, sitemap, pagina segnaposto WordPress, JSON-LD parziale):
  lo script ha rilevato indipendentemente tutti i difetti piantati.
- Verifica numerica del nucleo contro valori calcolati a mano: RRF con k=60
  (2° lessicale + 3° semantico = 1/62 + 1/63 = 0,032002 batte 1° in una sola
  lista = 1/61 = 0,016393), idf BM25 = ln(1 + (N−n+0,5)/(n+0,5)), saturazione
  della frequenza, coseno entro [0,1].
- Testati i tre formati di output, il file di query esterno, `--rrf-k`, i
  codici di uscita e i percorsi d'errore (host irraggiungibile, file mancante).

## Difetti trovati e corretti durante la verifica

- Mappatura heading→paragrafi basata su una divisione aritmetica: sostituita
  con la scansione nel vero ordine del documento.
- `/` e `/index.html` contati come pagine distinte, con raddoppio dei chunk e
  falso allarme sui title duplicati: aggiunta la deduplica per impronta del
  testo, con segnalazione dei duplicati come rilievo a sé.
- Query auto-generate degeneri ("come funziona funziona"): ora si usano
  bigrammi tematici, escludendo i termini già presenti nei template.
- Il referto JSON e quello HTML dichiaravano `k=60` fisso anche con `--rrf-k`
  diverso: parametro ora propagato a tutti i renderer.

## Fonti

- Cormack, Clarke, Buettcher — *Reciprocal Rank Fusion Outperforms Condorcet
  and Individual Rank Learning Methods*, SIGIR 2009.
- Microsoft Learn — Hybrid search scoring (RRF):
  https://learn.microsoft.com/en-us/azure/search/hybrid-search-ranking
- Elastic — Reciprocal Rank Fusion:
  https://www.elastic.co/docs/reference/elasticsearch/rest-apis/reciprocal-rank-fusion
- OpenSearch — Introducing RRF for hybrid search:
  https://opensearch.org/blog/introducing-reciprocal-rank-fusion-hybrid-search/
- Robertson & Zaragoza — *The Probabilistic Relevance Framework: BM25 and
  Beyond*, 2009.
- Schema.org: https://schema.org/