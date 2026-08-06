# Contribuire a MARS Beacon

Grazie dell'interesse per il progetto. MARS Beacon è open source
(licenza Apache 2.0) con una direzione ben precisa: **ideazione,
visione e roadmap sono di Paolo Pierno per Lympha Technologies
S.r.l.**, titolare del copyright, e le decisioni di progetto —
cosa entra, cosa no, e in quale forma — restano in capo al
maintainer. Dentro questa cornice i contributi sono benvenuti:
correzioni, segnalazioni circostanziate e proposte discusse prima
in una issue hanno la strada più breve.

In ogni spazio del progetto vale il
[Codice di condotta](CODE_OF_CONDUCT.md).

## Prima di proporre qualcosa

1. **Apri una issue prima di una pull request sostanziosa**: le
   idee si discutono lì, prima di investire lavoro. Le PR piccole e
   autoevidenti (refusi, fix puntuali con test) possono arrivare
   direttamente.
2. **Leggi la sezione "Scartato consapevolmente" di
   [AS-IS.md](AS-IS.md)**: elenca le strade valutate ed escluse
   (stack SaaS, simulazione di User-Agent altrui, API a pagamento,
   ecc.) proprio per non rivalutarle. Proposte in quelle direzioni
   non verranno accolte.
3. **Rispetta la filosofia del progetto**: esecuzione locale e
   offline, dipendenze minime e dichiarate, onestà metodologica
   (le stime si dichiarano come tali, le note di onestà non si
   rimuovono), robots.txt rispettato di default, User-Agent
   trasparente.

## Segnalare un bug

Apri una issue con: versione (`python3 mars_audit.py --version`),
comando completo eseguito, comportamento atteso e osservato, ed
estratti pertinenti di log o referto. Non allegare referti di siti
di clienti o dati personali: riproduci il problema su un sito
pubblico o su una fixture.

## Ambiente di sviluppo

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
pip install sentence-transformers numpy   # opzionale: embedding reali
pip install playwright                    # opzionale: rendering JS
tools/update-lighthouse.sh                # opzionale: audit Lighthouse
```

La suite e il lint devono essere verdi prima della PR (la CI li
riesegue su più versioni di Python):

```bash
flake8 mars_audit.py marsbeacon/ mars_gui.py mars_citations.py tests/
pytest
```

## Requisiti di qualità (la CI li verifica)

1. **Lint**: `flake8` pulito (PEP8, righe ≤ 79 caratteri).
2. **Test**: suite `pytest` verde. La suite è **offline per
   costruzione**: i test nuovi non toccano la rete — si usano siti
   fixture locali, server API finti e monkeypatch (helper `_patch`
   nei file di test: dopo la scomposizione in moduli conta il
   namespace del consumatore).
3. **i18n**: i testi canonici dei rilievi restano in **italiano**
   nei punti di creazione dei `Finding`, con `key` + `params`; ogni
   rilievo nuovo o modificato aggiorna i cataloghi di
   `marsbeacon/i18n.py` in **tutte** le lingue (en/fr/de/es) — i
   test di parità falliscono altrimenti. Le stringhe di cornice
   nuove nei renderer text/md passano da `T(it, en)` e vanno
   aggiunte a `_FRAME_I18N` (la copertura è verificata sull'AST).
4. **Accessibilità** (modifiche a GUI o referto HTML): obiettivo
   WCAG 2.2 AA — mai solo colore, etichette e regioni di stato,
   `prefers-reduced-motion` rispettato; `tools/verifica_at.py`
   deve restare a punteggio pieno e Pa11y gira in CI (vedi
   [docs/ACCESSIBILITA.md](docs/ACCESSIBILITA.md)).
5. **Onestà metodologica**: soglie e stime dichiarate come prassi o
   euristiche, mai come standard; le note di onestà nei referti
   sono parte del prodotto.
6. **Documentazione allineata nello stesso commit**: README,
   [AS-IS.md](AS-IS.md) (voce nuova per la modifica), TO-DO.md e
   [mars_audit.md](mars_audit.md); bump di `__version__` in
   `marsbeacon/base.py` (e del badge versione nel README) a ogni
   modifica degli script.
7. **Niente dipendenze nuove** senza discussione preventiva in
   issue: la filosofia è stdlib + poche dipendenze dichiarate, con
   gli opzionali sempre accompagnati da un fallback dichiarato.

## Stile

- Codice e commenti seguono lo stile del modulo che tocchi; i
  messaggi rivolti all'utente (CLI, GUI, referti) sono in italiano
  canonico.
- Commit chiari, in italiano, una modifica logica per commit.

## Licenza dei contributi

Inviando una pull request accetti che il tuo contributo sia
concesso al progetto alle condizioni della **Apache License 2.0**,
ai sensi dell'art. 5 della licenza, senza termini aggiuntivi. Il
copyright dei singoli contributi resta ai rispettivi autori;
l'attribuzione del progetto nel file [NOTICE](NOTICE) va conservata
e la licenza non concede diritti sui marchi (art. 6): «MARS Beacon»
e «Lympha Technologies», logo e identità visiva identificano il
progetto originale — i fork si presentano con un nome e un brand
propri (il re-brand è previsto: `gui/brand/`).
