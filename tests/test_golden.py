# -*- coding: utf-8 -*-
"""Golden file completi dei cinque renderer (P3).

Un dataset sintetico e deterministico — nessun crawl: i tempi di
rete non sono riproducibili — attraversa tutte le sezioni dei
referti: rilievi nelle sei aree e quattro gravita' (con esempi,
chiavi e parametri come in produzione), profili di citabilita',
giudizio LLM, blocco Lighthouse, ancora di realta', delta rispetto
all'esecuzione precedente, confronto competitivo, simulazione RRF,
piano di remediation, treemap e grafo dei link. L'output di ogni
formato e' confrontato riga per riga col golden in tests/golden/,
normalizzando i soli campi volatili (versione dello strumento,
timestamp del JSON): ogni cambiamento di resa non intenzionale
diventa un diff visibile.

Rigenerazione intenzionale (poi revisione del diff in git):

    MARS_RIGENERA_GOLDEN=1 pytest tests/test_golden.py
"""

import difflib
import os
import re

import pytest

import mars_audit as sra

GOLDEN_DIR = os.path.join(os.path.dirname(__file__), "golden")

BASE = "https://esempio.test/"


def _pagina(url, **kw):
    p = sra.Page(url=url, status=kw.pop("status", 200))
    for nome, valore in kw.items():
        setattr(p, nome, valore)
    return p


def _chunk(url, heading, testo, index=0):
    return sra.Chunk(url=url, heading=heading, text=testo,
                     index=index)


def _pages():
    home = _pagina(
        BASE, title="Drenaggio linfatico a Parma | Centro Esempio",
        description="Centro specializzato in drenaggio linfatico "
                    "manuale: sedute, prezzi e percorsi "
                    "post-operatori a Parma.",
        lang="it", word_count=430, elapsed=0.21, html_bytes=18000,
        has_charset=True, has_viewport=True,
        headings=[(1, "Drenaggio linfatico manuale"),
                  (2, "Che cos'e' il drenaggio linfatico?"),
                  (2, "Quanto costa una seduta?")],
        internal_targets=[BASE + "servizi/", BASE + "faq/"],
        internal_links=2, images=3, images_with_alt=3,
        jsonld_types=["Organization"],
        chunks=[
            _chunk(BASE, "Drenaggio linfatico manuale",
                   "Il drenaggio linfatico manuale e' un "
                   "massaggio delicato che favorisce il deflusso "
                   "della linfa: una seduta dura 45 minuti."),
            _chunk(BASE, "Quanto costa una seduta?",
                   "Una seduta costa in media 40-80 euro secondo "
                   "durata e zona trattata.", index=1),
        ])
    servizi = _pagina(
        BASE + "servizi/",
        title="Servizi di drenaggio | Centro Esempio",
        description="Tutti i percorsi: post-operatorio, "
                    "linfedema, sportivo. Durate e modalita' "
                    "delle sedute nel centro di Parma.",
        lang="it", word_count=610, elapsed=0.34, html_bytes=22000,
        has_charset=True, has_viewport=True,
        headings=[(1, "I percorsi del centro"),
                  (2, "Percorso post-operatorio")],
        internal_targets=[BASE], internal_links=1,
        images=2, images_with_alt=1,
        jsonld_types=["Service"],
        chunks=[
            _chunk(BASE + "servizi/", "Percorso post-operatorio",
                   "Il percorso post-operatorio prevede cicli da "
                   "5 a 10 sedute con rivalutazione ogni tre "
                   "incontri."),
        ])
    faq = _pagina(
        BASE + "faq/", title="Domande frequenti | Centro Esempio",
        description="Risposte alle domande piu' comuni su "
                    "drenaggio linfatico, controindicazioni, "
                    "durata e costi delle sedute.",
        lang="it", word_count=280, elapsed=0.18, html_bytes=9000,
        has_charset=True, has_viewport=True,
        headings=[(1, "Domande frequenti"),
                  (2, "Il drenaggio e' doloroso?")],
        internal_targets=[BASE], internal_links=1,
        chunks=[
            _chunk(BASE + "faq/", "Il drenaggio e' doloroso?",
                   "No, il drenaggio linfatico non e' doloroso: "
                   "la pressione delle manovre e' leggera."),
        ])
    rotta = _pagina(BASE + "vecchia-pagina/", status=404)
    rotta.error = "HTTP 404"
    return [home, servizi, faq, rotta]


def _findings():
    F = sra.Finding
    return [
        F(sra.AREA_TECH, sra.SEV_CRITICAL, "Sito non in HTTPS",
          fix="Attiva un certificato TLS e reindirizza tutto su "
              "HTTPS.",
          weight=2.0, pillar=sra.PILLAR_SEC,
          key="tech.https.missing"),
        F(sra.AREA_TECH, sra.SEV_CRITICAL,
          "Crawler IA bloccati: GPTBot, ClaudeBot",
          "Questi agenti non possono accedere alla home. Se sono "
          "bloccati non entri in nessuna lista di recupero e "
          "l'RRF non ha nulla da fondere.",
          "Rimuovi i Disallow per gli agenti da cui vuoi essere "
          "citato.",
          weight=2.0, key="tech.robots.ai_blocked",
          params={"agents": "GPTBot, ClaudeBot"},
          example="# robots.txt - sblocca gli agenti IA\n"
                  "User-agent: GPTBot\nDisallow:\n\n"
                  "User-agent: ClaudeBot\nDisallow:"),
        F(sra.AREA_TECH, sra.SEV_WARNING,
          "1 pagina/e a piu' di 3 click dalla home",
          "%svecchia-pagina/." % BASE,
          "Accorcia i percorsi: le pagine profonde vengono "
          "scansionate e pesate meno.",
          key="tech.links.deep",
          params={"n": 1, "urls": BASE + "vecchia-pagina/."}),
        F(sra.AREA_TECH, sra.SEV_OK, "robots.txt presente",
          "12 righe.", key="tech.robots.present",
          params={"n": 12}),
        F(sra.AREA_LEX, sra.SEV_CRITICAL,
          "1 title non ottimizzati",
          "Esempi: 'Centro' (6 car.)",
          "Title unico, 30-65 caratteri, con i termini di "
          "ricerca reali; evita il nome dominio come titolo.",
          url=BASE + "faq/", weight=2.0, key="lex.title.bad",
          params={"n": 1, "min": 30, "max": 65,
                  "examples": "'Centro' (6 car.)"},
          example="<title>Drenaggio linfatico manuale a Parma | "
                  "Centro Esempio</title>\n"
                  "(52 caratteri: servizio + territorio + brand)"),
        F(sra.AREA_LEX, sra.SEV_CRITICAL,
          "1 pagina/e sotto 300 parole",
          "Media sito: 440 parole. Con cosi' poco testo i "
          "termini utili non raggiungono una frequenza "
          "sufficiente perche' BM25 li valorizzi.",
          "Porta le pagine chiave verso le 700+ parole con "
          "contenuto informativo, non promozionale.",
          url=BASE + "faq/", weight=2.0, key="lex.words.thin",
          params={"n": 1, "min": 300, "avg": 440, "target": 700},
          example="Struttura tipo per una pagina servizio:\n"
                  "<h2>Cos'e' ...?</h2> <h2>Come funziona una "
                  "seduta</h2>\n<h2>Quando serve</h2> <h2>Quanto "
                  "costa</h2> <h2>Domande frequenti</h2>"),
        F(sra.AREA_LEX, sra.SEV_OK,
          "Meta description presenti e di lunghezza adeguata",
          key="lex.desc.ok"),
        F(sra.AREA_SEM, sra.SEV_WARNING,
          "Pochi paragrafi a risposta diretta",
          "1 paragrafi su 12 aprono con una risposta esplicita "
          "in 20-120 parole (8% contro una soglia di prassi del "
          "20%): sono i passaggi citabili da un assistente cosi' "
          "come sono.",
          "Riscrivi i paragrafi chiave aprendo con la risposta "
          "(\"X e' ...\", \"Si', ...\", \"In sintesi ...\") e "
          "tienili fra 20 e 120 parole.",
          key="sem.extract.low",
          params={"direct": 1, "total": 12, "min": 20, "max": 120,
                  "pct": 8.0, "threshold": 20.0},
          example="Prima: \"Nel panorama del benessere di oggi, "
                  "molti si chiedono quale percorso...\"\n"
                  "Dopo:  \"Il drenaggio linfatico e' un "
                  "massaggio delicato che favorisce il deflusso "
                  "della linfa: una seduta dura 45 minuti e "
                  "costa 40-80 euro.\""),
        F(sra.AREA_SEM, sra.SEV_WARNING, "Nessuna sezione FAQ",
          "Le FAQ allineano un chunk a un intento preciso e "
          "alimentano entrambi gli assi insieme.",
          "Aggiungi FAQ per pagina, marcate con JSON-LD FAQPage.",
          key="sem.faq.missing"),
        F(sra.AREA_SEM, sra.SEV_OK,
          "E-E-A-T: contatti verificabili presenti",
          key="sem.eeat.contact.ok"),
        F(sra.AREA_SD, sra.SEV_WARNING,
          "Entita' principale non dichiarata",
          fix="Aggiungi Organization o LocalBusiness con nome, "
              "indirizzo, contatti e riferimenti fiscali.",
          key="sd.entity.missing"),
        F(sra.AREA_SD, sra.SEV_INFO,
          "1 data/e non in formato ISO 8601",
          "31/12/2025 (Service).",
          "Usa AAAA-MM-GG, con l'ora facoltativa dopo la T "
          "(es. 2026-08-03T09:30:00+02:00).",
          key="sd.check.dates",
          params={"n": 1, "list": "31/12/2025 (Service)"}),
        F(sra.AREA_RRF, sra.SEV_WARNING,
          "Consenso medio fra le liste: 1.5/5 (30%)",
          "Consenso parziale fra i due recuperatori. Nella "
          "formula RRF un documento presente in entrambe le "
          "liste somma due addendi 1/(k+rank) e batte chi domina "
          "una lista sola. Consenso per query: 'drenaggio "
          "linfatico costi' 3/5, 'controindicazioni drenaggio' "
          "0/5.",
          "Ottimizza gli stessi passaggi su entrambi gli assi: "
          "termini espliciti (BM25) e spiegazione completa "
          "(vettoriale).",
          key="rrf.consensus.mid",
          params={"avg": 1.5, "top_n": 5, "pct": 30.0,
                  "per_query": "'drenaggio linfatico costi' 3/5, "
                               "'controindicazioni drenaggio' "
                               "0/5"}),
        F(sra.AREA_RRF, sra.SEV_CRITICAL,
          "1 query senza alcun risultato",
          "Nessun chunk del sito risponde: 'controindicazioni "
          "drenaggio'.",
          "Crea contenuti dedicati a questi intenti.",
          weight=2.0, key="rrf.uncovered",
          params={"n": 1,
                  "queries": "'controindicazioni drenaggio'"},
          example="Per ogni query scoperta, una sezione con un "
                  "heading uguale alla domanda:\n"
                  "<h2>Quanto costa il drenaggio linfatico?</h2>"
                  "\n<p>Una seduta costa in media 40-80 euro, "
                  "secondo durata e zona trattata.</p>"),
        F(sra.AREA_LIGHTHOUSE, sra.SEV_WARNING,
          "Lighthouse: LCP lento",
          "4,1 s; Pagine: %s" % BASE,
          "Riduci il peso dell'immagine principale e servila "
          "con priorita' alta.",
          url=BASE, weight=2.0, pillar=sra.PILLAR_ACCESS,
          key="lh.performance.lcp",
          params={"audit": "lcp", "category": "performance",
                  "score": 0.42, "lh_weight": 25,
                  "urls": BASE, "display": "4,1 s",
                  "evidence": ["img.hero (1,8 MB)"],
                  "title_en": "Slow LCP",
                  "fix_en": "Reduce the hero image weight.",
                  "title_msg": "audit.js | lcpTitle",
                  "fix_msg": "audit.js | lcpDescription"}),
        F(sra.AREA_LIGHTHOUSE, sra.SEV_OK,
          "Lighthouse SEO: nessun rilievo",
          "Punteggio 88/100 sull'unica pagina esaminata.",
          pillar=sra.PILLAR_RANK, key="lh.seo.ok",
          params={"category": "seo", "score": 88, "pages": 1,
                  "cat_title_en": "SEO",
                  "cat_title_msg": "config.js | seoCategoryTitle"}),
    ]


def _results():
    coperta = sra.QueryResult(
        query="drenaggio linfatico costi",
        lexical_top=["/  ·  Quanto costa una seduta?",
                     "/servizi/  ·  Percorso post-operatorio"],
        vector_top=["/  ·  Quanto costa una seduta?",
                    "/faq/  ·  Il drenaggio e' doloroso?"],
        fused_top=[("/  ·  Quanto costa una seduta?", 0.03252),
                   ("/servizi/  ·  Percorso post-operatorio",
                    0.01639),
                   ("/faq/  ·  Il drenaggio e' doloroso?",
                    0.01613)],
        consensus=3, covered=True)
    scoperta = sra.QueryResult(query="controindicazioni drenaggio")
    return [coperta, scoperta]


def _dataset():
    return {
        "pages": _pages(),
        "findings": _findings(),
        "scores": {sra.AREA_TECH: 52.5, sra.AREA_LEX: 61.0,
                   sra.AREA_SEM: 58.5, sra.AREA_SD: 30.0,
                   sra.AREA_RRF: 66.7,
                   sra.AREA_LIGHTHOUSE: 74.0},
        "results": _results(),
        "competitive": {
            "top_n": 5, "main": "esempio.test",
            "sites": ["esempio.test", "concorrente.test"],
            "share": {"esempio.test": 40.0,
                      "concorrente.test": 60.0},
            "presence": {"esempio.test": 1,
                         "concorrente.test": 2},
            "chunks": {"esempio.test": 4, "concorrente.test": 9},
            "queries_total": 2,
            "queries": [
                {"query": "drenaggio linfatico costi",
                 "mine_in_top": 2, "best_rank_mine": 2},
                {"query": "controindicazioni drenaggio",
                 "mine_in_top": 0, "best_rank_mine": 0},
            ]},
        "judge": {
            "status": "ok", "model": "claude-esempio",
            "sampled": 2, "average": 71.5,
            "note": "Parere di un modello su un campione: non "
                    "e' una misura riproducibile.",
            "verdicts": [
                {"query": "drenaggio linfatico costi",
                 "score": 78.0,
                 "reason": "Risposta diretta con durata e "
                           "prezzo."},
                {"query": "controindicazioni drenaggio",
                 "score": 65.0,
                 "reason": "Passaggio pertinente ma senza "
                           "elenco esplicito."},
            ]},
        "delta": {
            "previous_generated_at": "2026-07-30T10:00:00+0200",
            "scores": {sra.AREA_TECH: 2.5, sra.AREA_LEX: 0.0,
                       "Complessivo": 1.8},
            "resolved": [{"severity": sra.SEV_CRITICAL,
                          "title": "n pagina/e senza <title>"}],
            "new": [{"severity": sra.SEV_WARNING,
                     "title": "Nessuna sezione FAQ"}]},
        "lighthouse": {
            "status": "ok", "mode": "auto", "device": "mobile",
            "fork": "v13.4.1-mars.1", "pages": [BASE],
            "categories": [
                {"id": "performance", "title": "Prestazioni",
                 "score": 74},
                {"id": "seo", "title": "SEO", "score": 88}],
            "errors": []},
        "search_check": {
            "status": "ok", "engine": "brave",
            "site": "esempio.test", "top_n": 20, "found": 1,
            "note": "Il ranking reale dipende anche da "
                    "personalizzazione, localita' e freschezza: "
                    "confronto direzionale, non una validazione.",
            "queries": [
                {"query": "drenaggio linfatico costi",
                 "rrf_covered": True, "rrf_consensus": 3,
                 "position": 4, "url": BASE},
                {"query": "controindicazioni drenaggio",
                 "rrf_covered": False, "rrf_consensus": 0,
                 "position": None, "url": ""},
            ]},
    }


def _render_tutti():
    d = _dataset()
    comuni = dict(competitive=d["competitive"], judge=d["judge"],
                  delta=d["delta"], lighthouse=d["lighthouse"],
                  search_check=d["search_check"])
    argomenti = (BASE, d["pages"], d["findings"], d["scores"],
                 d["results"], "char-tfidf", 60)
    return {
        "txt": sra.render_text(*argomenti, **comuni),
        "json": sra.render_json(
            *argomenti, **comuni,
            rrf_params={"top_n": 5, "weights": [1.0, 1.0],
                        "chunk_words": 220}),
        "html": sra.render_html(*argomenti, **comuni),
        "md": sra.render_markdown(*argomenti, **comuni),
        "csv": sra.render_csv(*argomenti, **comuni),
    }


def _normalizza(testo):
    """Neutralizza i soli campi volatili: versione e timestamp."""
    testo = testo.replace(sra.__version__, "X.Y.Z")
    return re.sub(r'"generated_at": "[^"]*"',
                  '"generated_at": "NORMALIZZATO"', testo)


@pytest.mark.parametrize("formato", ("txt", "json", "html", "md",
                                     "csv"))
def test_golden(formato):
    reso = _normalizza(_render_tutti()[formato])
    percorso = os.path.join(GOLDEN_DIR, "referto.%s" % formato)
    if os.environ.get("MARS_RIGENERA_GOLDEN"):
        os.makedirs(GOLDEN_DIR, exist_ok=True)
        with open(percorso, "w", encoding="utf-8") as handle:
            handle.write(reso)
        pytest.skip("golden %s rigenerato: rivedere il diff in "
                    "git prima del commit" % formato)
    with open(percorso, encoding="utf-8") as handle:
        atteso = handle.read()
    if reso != atteso:
        diff = "\n".join(list(difflib.unified_diff(
            atteso.splitlines(), reso.splitlines(),
            fromfile="golden/referto.%s" % formato,
            tofile="reso", lineterm=""))[:60])
        raise AssertionError(
            "Il referto %s non coincide col golden. Se il "
            "cambiamento e' voluto: MARS_RIGENERA_GOLDEN=1 "
            "pytest tests/test_golden.py e revisione del diff.\n%s"
            % (formato, diff))


def test_render_deterministico_nello_stesso_processo():
    prima = _render_tutti()
    seconda = _render_tutti()
    for formato, testo in prima.items():
        assert _normalizza(testo) == _normalizza(seconda[formato]), \
            formato
