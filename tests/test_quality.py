# -*- coding: utf-8 -*-
"""Qualita' dell'analisi: llms.txt, JSON-LD, E-E-A-T, grafo link."""

import datetime

import requests

import seo_rrf_audit as sra


def _fetcher():
    return sra.Fetcher(delay=0.0, verbose=False)


def _fake_response(url, html_text):
    resp = requests.Response()
    resp.status_code = 200
    resp.url = url
    resp._content = html_text.encode("utf-8")
    resp.encoding = "utf-8"
    resp.elapsed = datetime.timedelta(0)
    return resp


# ---------------- llms.txt ----------------

def test_llms_txt_presente(site):
    finding = sra.check_llms_txt(site, _fetcher())
    assert finding.severity == sra.SEV_OK
    assert "llms.txt" in finding.title


def test_llms_txt_assente(competitor_site):
    finding = sra.check_llms_txt(competitor_site, _fetcher())
    assert finding.severity == sra.SEV_INFO
    assert "assente" in finding.title


# ---------------- lista crawler IA ----------------

def test_ai_crawlers_senza_bingbot_e_claude_web():
    assert "Bingbot" not in sra.AI_CRAWLERS
    assert "Claude-Web" not in sra.AI_CRAWLERS
    for token in ("GPTBot", "Claude-SearchBot", "Perplexity-User",
                  "Meta-ExternalAgent", "Amazonbot",
                  "MistralAI-User"):
        assert token in sra.AI_CRAWLERS


# ---------------- validazione JSON-LD ----------------

def test_jsonld_incompleto_segnalato():
    page = sra.Page(url="https://x.it/", status=200)
    page.jsonld_raw = [{"@type": "LocalBusiness", "name": "X"}]
    findings = sra.validate_jsonld([page])
    warn = [f for f in findings if f.severity == sra.SEV_WARNING]
    assert warn and "LocalBusiness" in warn[0].detail
    assert "address" in warn[0].detail
    assert "telephone" in warn[0].detail


def test_jsonld_completo_da_ok():
    page = sra.Page(url="https://x.it/", status=200)
    page.jsonld_raw = [{"@type": "WebSite", "name": "X",
                        "url": "https://x.it/"}]
    findings = sra.validate_jsonld([page])
    assert len(findings) == 1
    assert findings[0].severity == sra.SEV_OK


def test_faqpage_con_domande_incomplete():
    page = sra.Page(url="https://x.it/", status=200)
    page.jsonld_raw = [{
        "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": "Quanto costa?"},
            {"@type": "Question", "name": "Come funziona?",
             "acceptedAnswer": {"@type": "Answer",
                                "text": "Cosi'."}},
        ],
    }]
    findings = sra.validate_jsonld([page])
    faq = [f for f in findings if "FAQPage" in f.title]
    assert faq and "1 domanda" in faq[0].title


# ---------------- E-E-A-T ----------------

def test_eeat_tutti_i_segnali_presenti():
    html_text = """<!DOCTYPE html>
    <html lang="it"><head><meta charset="utf-8">
    <title>Chi siamo</title>
    <meta name="author" content="Paola Rossi">
    <meta property="article:published_time" content="2026-05-01">
    </head><body>
    <h1>Chi siamo</h1>
    <p>Il nostro team di fisioterapisti opera dal 2010 con
    formazione certificata e aggiornamento continuo.</p>
    <p><a href="tel:+390521123456">Chiamaci</a></p>
    </body></html>"""
    page = sra.parse_page("https://x.it/chi-siamo/",
                          _fake_response("https://x.it/chi-siamo/",
                                         html_text))
    assert page.author == "Paola Rossi"
    assert page.published == "2026-05-01"
    assert page.contact_links == 1
    findings = sra.audit_eeat([page])
    assert len(findings) == 4
    assert all(f.severity == sra.SEV_OK for f in findings)


def test_eeat_segnali_assenti():
    page = sra.Page(url="https://x.it/servizi/", status=200,
                    text="Elenco dei servizi offerti dal centro.")
    findings = sra.audit_eeat([page])
    assert len(findings) == 4
    assert all(f.severity == sra.SEV_WARNING for f in findings)
    titoli = " | ".join(f.title for f in findings)
    assert "autore" in titoli
    assert "chi siamo" in titoli


# ---------------- grafo dei link interni ----------------

def _pagina(url, targets=(), generic=0):
    page = sra.Page(url=url, status=200)
    page.internal_targets = [sra.norm_url(t) for t in targets]
    page.generic_anchors = generic
    return page


def test_grafo_orfane_profonde_e_anchor_generiche():
    base = "https://x.it/"
    pages = [
        _pagina("https://x.it/", ["https://x.it/a"], generic=2),
        _pagina("https://x.it/a", ["https://x.it/b"]),
        _pagina("https://x.it/b", ["https://x.it/c"]),
        _pagina("https://x.it/c", ["https://x.it/d"]),
        _pagina("https://x.it/d"),
        _pagina("https://x.it/orfana"),
    ]
    findings = sra._audit_link_graph(pages, base)
    titoli = " | ".join(f.title for f in findings)
    assert "orfane" in titoli
    assert any("orfana" in f.detail for f in findings)
    assert "oltre 3 click" in titoli
    assert "anchor generiche" in titoli


def test_grafo_sano_da_ok():
    base = "https://x.it/"
    pages = [
        _pagina("https://x.it/", ["https://x.it/a", "https://x.it/b"]),
        _pagina("https://x.it/a", ["https://x.it/"]),
        _pagina("https://x.it/b", ["https://x.it/a"]),
    ]
    findings = sra._audit_link_graph(pages, base)
    assert [f.severity for f in findings] == [sra.SEV_OK]


def test_anchor_generiche_riconosciute():
    for testo in ("Clicca qui", "leggi di più", "Read more", "QUI"):
        assert sra.GENERIC_ANCHOR_RE.match(testo), testo
    for testo in ("Scopri il servizio", "Guida al drenaggio"):
        assert not sra.GENERIC_ANCHOR_RE.match(testo), testo


# ---------------- installazione embedding rotta ----------------

def test_installazione_rotta_ripiega_su_tfidf(monkeypatch, capsys):
    """Un import che esplode (torch/numpy incompatibili) non deve
    propagare: si ripiega sul proxy dichiarandolo."""
    import sys as _sys
    import types

    rotto = types.ModuleType("sentence_transformers")

    def _boom(name):
        raise RuntimeError("ambiente rotto")

    rotto.__getattr__ = _boom
    monkeypatch.setitem(_sys.modules, "sentence_transformers", rotto)

    index = sra.VectorIndex(["primo documento", "secondo documento"],
                            model_name="qualunque")
    err = capsys.readouterr().err
    assert index.mode == "char-tfidf"
    assert "non utilizzabile" in err
    assert index.search("primo")


# ---------------- qualita' Schema.org: prezzi, media, rating ----------------

def _pagina_jsonld(*blocchi):
    page = sra.Page(url="https://x.it/", status=200)
    page.jsonld_raw = list(blocchi)
    return page


def test_offerta_con_prezzo_sporco_e_valuta_mancante():
    page = _pagina_jsonld({
        "@type": "Product", "name": "Pressoterapia",
        "offers": {"@type": "Offer", "price": "€ 50,00"},
    })
    findings = sra.validate_jsonld([page])
    titoli = " | ".join(f.title for f in findings)
    assert "prezzi delle offerte" in titoli
    dettagli = " | ".join(f.detail for f in findings)
    assert "non numerico" in dettagli
    assert "ISO 4217" in dettagli


def test_offerta_corretta_non_segnalata():
    page = _pagina_jsonld({
        "@type": "Product", "name": "Pressoterapia",
        "offers": {"@type": "Offer", "price": "50.00",
                   "priceCurrency": "EUR"},
    })
    findings = sra.validate_jsonld([page])
    assert not any("prezzi" in f.title for f in findings)


def test_product_senza_offerte_ne_giudizi():
    page = _pagina_jsonld({"@type": "Product", "name": "Kit"})
    findings = sra.validate_jsonld([page])
    assert any("senza offerte" in f.title for f in findings)


def test_video_senza_uploaddate_e_thumbnail_relativa():
    page = _pagina_jsonld({
        "@type": "VideoObject", "name": "Demo",
        "thumbnailUrl": "/img/demo.jpg",
    })
    findings = sra.validate_jsonld([page])
    dettagli = " | ".join(f.detail for f in findings)
    assert "VideoObject senza uploadDate" in dettagli
    assert any("non assoluti" in f.title for f in findings)


def test_rating_fuori_scala_e_senza_conteggio():
    page = _pagina_jsonld({
        "@type": "AggregateRating", "ratingValue": "6.2",
    })
    findings = sra.validate_jsonld([page])
    warn = [f for f in findings if "valutazion" in f.title]
    assert warn
    assert "fuori scala" in warn[0].detail
    assert "reviewCount" in warn[0].detail


def test_data_non_iso_segnalata():
    page = _pagina_jsonld({
        "@type": "Article", "headline": "T", "author": "A",
        "datePublished": "03/08/2026",
    })
    findings = sra.validate_jsonld([page])
    assert any("ISO 8601" in f.title for f in findings)


def test_evento_completo_e_coerente_da_ok():
    page = _pagina_jsonld({
        "@type": "Event", "name": "Open day",
        "startDate": "2026-09-12T10:00:00+02:00",
        "location": {"@type": "Place", "name": "Centro Linfa"},
        "image": "https://x.it/open-day.jpg",
    })
    findings = sra.validate_jsonld([page])
    assert len(findings) == 1
    assert findings[0].severity == sra.SEV_OK
    assert "coerente" in findings[0].title


# ---------------- piano di remediation ----------------

def test_build_remediation_ordina_per_gravita_e_peso():
    findings = [
        sra.Finding(sra.AREA_LEX, sra.SEV_WARNING, "w1", weight=1.0),
        sra.Finding(sra.AREA_TECH, sra.SEV_CRITICAL, "c1",
                    weight=1.0),
        sra.Finding(sra.AREA_SEM, sra.SEV_OK, "tutto bene"),
        sra.Finding(sra.AREA_SD, sra.SEV_CRITICAL, "c2", weight=3.0,
                    example="snippet"),
        sra.Finding(sra.AREA_RRF, sra.SEV_INFO, "nota"),
        sra.Finding(sra.AREA_LEX, sra.SEV_WARNING, "w2", weight=2.0),
    ]
    plan = sra.build_remediation(findings)
    assert [x["title"] for x in plan] == ["c2", "c1", "w2", "w1"]
    assert [x["priority"] for x in plan] == [1, 2, 3, 4]
    assert plan[0]["example"] == "snippet"


def test_quiet_huggingface(monkeypatch):
    import logging as pylog
    monkeypatch.delenv("HF_HUB_DISABLE_PROGRESS_BARS", raising=False)
    monkeypatch.setenv("TRANSFORMERS_VERBOSITY", "debug")
    sra._quiet_huggingface()
    import os
    assert os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] == "1"
    assert os.environ["TRANSFORMERS_VERBOSITY"] == "debug", \
        "le scelte esplicite dell'utente non vanno toccate"
    assert pylog.getLogger("huggingface_hub").level == pylog.ERROR


def test_stima_sforzo_per_intervento():
    minuti = sra.Finding(sra.AREA_TECH, sra.SEV_CRITICAL,
                         "1 pagina/e segnaposto indicizzabili",
                         fix="Cancellala o imposta noindex.")
    giorni = sra.Finding(sra.AREA_TECH, sra.SEV_CRITICAL,
                         "2 pagina/e con testo scarso e molto "
                         "JavaScript",
                         fix="Attiva rendering server-side.")
    ore = sra.Finding(sra.AREA_SD, sra.SEV_WARNING,
                      "JSON-LD senza entita' principale",
                      fix="Aggiungi Organization.")
    assert sra.estimate_effort(minuti) == sra.EFFORT_MINUTES
    assert sra.estimate_effort(giorni) == sra.EFFORT_DAYS
    assert sra.estimate_effort(ore) == sra.EFFORT_HOURS


def test_remediation_quick_win():
    findings = [
        sra.Finding(sra.AREA_TECH, sra.SEV_CRITICAL,
                    "1 pagina/e segnaposto indicizzabili",
                    weight=2.0),
        sra.Finding(sra.AREA_SEM, sra.SEV_CRITICAL,
                    "Poche pagine indicizzabili", weight=3.0),
        sra.Finding(sra.AREA_SD, sra.SEV_WARNING,
                    "Nessun titolo descrittivo title", weight=1.0),
    ]
    plan = sra.build_remediation(findings)
    per_titolo = {i["title"]: i for i in plan}
    segnaposto = per_titolo["1 pagina/e segnaposto indicizzabili"]
    assert segnaposto["effort"] == sra.EFFORT_MINUTES
    assert segnaposto["quick_win"] is True
    assert per_titolo["Poche pagine indicizzabili"]["quick_win"] \
        is False, "critico ma da giorni: non e' un quick win"
    assert per_titolo["Nessun titolo descrittivo title"][
        "quick_win"] is False, "minuti ma solo avvertenza"


def test_surface_math():
    ricca = sra.Page(url="https://x.it/", status=200)
    ricca.word_count = 900
    ricca.chunks = [sra.Chunk("https://x.it/", "H", "t", i)
                    for i in range(6)]
    povera = sra.Page(url="https://x.it/p", status=200)
    povera.word_count = 100
    povera.chunks = [sra.Chunk("https://x.it/p", "H", "t", 0)]
    rotta = sra.Page(url="https://x.it/err", error="fallita")

    math = sra.surface_math([ricca, povera, rotta])
    assert math["pages"] == 2
    assert math["chunks_now"] == 7
    assert math["words_avg"] == 500
    # ricca: max(6,4)+1 = 7; povera: max(1,4)+1 = 5
    assert math["chunks_potential"] == 12
    assert math["multiplier"] == round(12 / 7, 1)

    vuota = sra.Page(url="https://x.it/v", status=200)
    vuota.word_count = 0
    math0 = sra.surface_math([vuota])
    assert math0["chunks_now"] == 0 and math0["multiplier"] is None
    assert sra.surface_math([rotta]) is None


def test_rilievi_critici_portano_esempi():
    """I rilievi piu' comuni devono avere un esempio di fix."""
    page = sra.Page(url="https://x.it/pagina", status=200,
                    text="poco testo")
    findings = sra.audit_lexical([page])
    critici = [f for f in findings
               if f.severity == sra.SEV_CRITICAL and f.example]
    assert critici, "attesi esempi sui rilievi lessicali critici"


def test_eeat_warning_con_esempio():
    page = sra.Page(url="https://x.it/servizi/", status=200,
                    text="Elenco servizi.")
    findings = sra.audit_eeat([page])
    assert all(f.example for f in findings
               if f.severity == sra.SEV_WARNING)


# ---------------- opt-out IA di Microsoft ----------------

def _pagina_con_meta(url, extra_head=""):
    html_text = ("<!DOCTYPE html><html lang=\"it\"><head>"
                 "<title>Pagina</title>%s</head><body><h1>Testo"
                 "</h1><p>Contenuto della pagina di prova con "
                 "abbastanza parole utili.</p></body></html>"
                 % extra_head)
    return sra.parse_page(url, _fake_response(url, html_text))


def test_msft_optout_noarchive_avvertenza():
    page = _pagina_con_meta(
        "https://mio.it/a",
        "<meta name=\"robots\" content=\"noarchive\">")
    findings = sra._audit_msft_ai_optout([page])
    assert len(findings) == 1
    assert findings[0].severity == sra.SEV_WARNING
    assert "noarchive" in findings[0].title
    assert "Copilot" in findings[0].title
    assert sra.estimate_effort(findings[0]) == sra.EFFORT_MINUTES


def test_msft_optout_nocache_informativo():
    page = _pagina_con_meta(
        "https://mio.it/b",
        "<meta name=\"bingbot\" content=\"nocache\">")
    findings = sra._audit_msft_ai_optout([page])
    assert len(findings) == 1
    assert findings[0].severity == sra.SEV_INFO
    assert "nocache" in findings[0].title


def test_msft_optout_bingbot_prevale_su_robots():
    """L'esempio documentato da Microsoft: bingbot vince per Bing."""
    page = _pagina_con_meta(
        "https://mio.it/c",
        "<meta name=\"robots\" content=\"noarchive\">"
        "<meta name=\"bingbot\" content=\"nocache\">")
    findings = sra._audit_msft_ai_optout([page])
    assert len(findings) == 1
    assert findings[0].severity == sra.SEV_INFO, \
        "il meta scoped a bingbot prevale su quello generico"


def test_msft_optout_assente_ok_informativo():
    page = _pagina_con_meta("https://mio.it/d")
    findings = sra._audit_msft_ai_optout([page])
    assert len(findings) == 1
    assert findings[0].severity == sra.SEV_OK
    assert "opt-out" in findings[0].title


# ---------------- estraibilita' diretta ----------------

_PAR_DIRETTO = ("Il drenaggio linfatico è una tecnica di massaggio "
                "dolce che favorisce il deflusso della linfa verso "
                "le stazioni linfonodali: una seduta tipica dura "
                "quarantacinque minuti e costa fra i quaranta e "
                "gli ottanta euro.")
_PAR_SI_SECCO = ("Sì, il trattamento è indicato anche dopo un "
                 "intervento chirurgico: il protocollo prevede in "
                 "genere da cinque a dieci sedute distribuite su "
                 "un ciclo di poche settimane, secondo il parere "
                 "del medico curante.")
_PAR_VAGO = ("Nel panorama attuale del benessere e della cura "
             "della persona, molte persone si chiedono quale "
             "percorso possa essere il più adatto alle proprie "
             "esigenze quotidiane e ai propri ritmi di vita "
             "sempre più frenetici e complessi.")


def _pagina_con_paragrafi(paragrafi):
    page = sra.Page(url="https://mio.it/", status=200,
                    text=" ".join(paragrafi), word_count=300)
    page.paragraphs = list(paragrafi)
    return page


def test_estraibilita_buona():
    page = _pagina_con_paragrafi(
        [_PAR_DIRETTO, _PAR_SI_SECCO, _PAR_VAGO])
    findings = sra._audit_extractability([page])
    assert len(findings) == 1
    assert findings[0].severity == sra.SEV_OK
    assert "2 paragrafi su 3" in findings[0].detail


def test_estraibilita_scarsa_con_fix():
    page = _pagina_con_paragrafi([_PAR_VAGO, _PAR_VAGO, _PAR_VAGO,
                                  _PAR_VAGO, _PAR_VAGO])
    findings = sra._audit_extractability([page])
    assert len(findings) == 1
    assert findings[0].severity == sra.SEV_WARNING
    assert "0 paragrafi su 5" in findings[0].detail
    assert findings[0].fix and findings[0].example


def test_estraibilita_esclude_paragrafi_fuori_misura():
    troppo_lungo = "%s %s" % (_PAR_DIRETTO,
                              (_PAR_VAGO + " ") * 3)
    assert len(troppo_lungo.split()) > sra.EXTRACT_MAX_WORDS
    corto = "Il drenaggio è utile."  # apre bene ma < 20 parole
    page = _pagina_con_paragrafi([troppo_lungo,
                                  corto + " " + "parola " * 7])
    findings = sra._audit_extractability([page])
    assert findings[0].severity == sra.SEV_WARNING
    assert "0 paragrafi su 2" in findings[0].detail


def test_estraibilita_multilingua():
    frasi = [
        "Oui, la séance dure quarante-cinq minutes et le drainage "
        "lymphatique manuel reste une méthode douce adaptée aussi "
        "aux personnes âgées comme aux sportifs après une "
        "opération du genou.",
        "Kurz gesagt ist die manuelle Lymphdrainage eine sanfte "
        "Massagetechnik, die den Abfluss der Lymphe fördert und "
        "nach Operationen sowie bei geschwollenen Beinen sehr "
        "häufig verordnet wird.",
        "En resumen, el drenaje linfático manual es un masaje "
        "suave que favorece la salida de la linfa y se recomienda "
        "después de una cirugía o cuando las piernas se hinchan "
        "con frecuencia.",
    ]
    page = _pagina_con_paragrafi(frasi)
    findings = sra._audit_extractability([page])
    assert findings[0].severity == sra.SEV_OK
    assert "3 paragrafi su 3" in findings[0].detail


def test_estraibilita_senza_paragrafi_sostanziosi():
    page = _pagina_con_paragrafi(["Poche parole qui."])
    assert sra._audit_extractability([page]) == []


# ---------------- titoli clickbait ----------------

def _pagina_con_titoli(title, headings):
    page = sra.Page(url="https://mio.it/", status=200,
                    text="testo", word_count=300, title=title)
    page.headings = headings
    return page


def test_clickbait_rilevato_in_title_e_heading():
    page = _pagina_con_titoli(
        "Non crederai a cosa fa il drenaggio!!",
        [(2, "Il segreto del drenaggio linfatico"),
         (2, "Quanto costa una seduta"),
         (4, "Incredibile offerta")])  # h4: fuori dal controllo
    findings = sra._audit_clickbait([page])
    assert len(findings) == 1
    assert findings[0].severity == sra.SEV_WARNING
    assert "2 titoli o heading" in findings[0].title
    assert findings[0].example
    assert sra.estimate_effort(findings[0]) == sra.EFFORT_MINUTES


def test_clickbait_multilingua():
    casi = ("You won't believe these results",
            "Vous ne croirez jamais ce résultat",
            "Du wirst nicht glauben, was dann geschah",
            "No creerás lo que pasó después",
            "10 motivi per scegliere il drenaggio",
            "Offerta speciale!!!")
    for testo in casi:
        page = _pagina_con_titoli(testo, [])
        findings = sra._audit_clickbait([page])
        assert findings[0].severity == sra.SEV_WARNING, testo


def test_titoli_informativi_ok():
    page = _pagina_con_titoli(
        "Drenaggio linfatico manuale a Parma | Centro Esempio",
        [(2, "Cos'è il drenaggio linfatico"),
         (2, "Quanto costa una seduta"),
         (3, "Il trattamento è doloroso?")])
    findings = sra._audit_clickbait([page])
    assert len(findings) == 1
    assert findings[0].severity == sra.SEV_OK


# ---------------- densita' informativa (filler) ----------------

def _pagina_con_testo(testo):
    page = sra.Page(url="https://mio.it/", status=200, text=testo,
                    word_count=len(testo.split()))
    return page


def test_filler_pagina_satura():
    testo = ("Siamo leader di mercato con soluzioni innovative a "
             "360 gradi. Scopri di più sui nostri servizi e "
             "contattaci per un preventivo: qualità e "
             "professionalità al tuo servizio. " + "parola " * 60)
    findings = sra._audit_filler([_pagina_con_testo(testo)])
    assert len(findings) == 1
    assert findings[0].severity == sra.SEV_WARNING
    assert "sature di formule di marketing" in findings[0].title
    assert "7 formule" in findings[0].detail
    assert "a 360 gradi" in findings[0].detail
    assert findings[0].fix and findings[0].example


def test_filler_sotto_controllo():
    testo = ("Il drenaggio linfatico e' una tecnica di massaggio "
             "che favorisce il deflusso della linfa. Una seduta "
             "dura 45 minuti e costa dai 40 agli 80 euro. Scopri "
             "di più nella pagina dei servizi. " + "parola " * 200)
    findings = sra._audit_filler([_pagina_con_testo(testo)])
    assert len(findings) == 1
    assert findings[0].severity == sra.SEV_OK
    assert "1 formule" in findings[0].detail


def test_filler_serve_sia_conteggio_che_densita():
    # 3 formule ma diluite in 600 parole: densita' sotto soglia.
    testo = ("Scopri di più. Clicca qui. Seguici su Instagram. "
             + "parola " * 600)
    findings = sra._audit_filler([_pagina_con_testo(testo)])
    assert findings[0].severity == sra.SEV_OK


def test_filler_multilingua():
    casi = (
        "We are the market leader with cutting-edge solutions. "
        "Learn more and contact us for a quote. " + "word " * 50,
        "Leader du marché, cliquez ici pour en savoir plus et "
        "contactez-nous sans attendre. " + "mot " * 50,
        "Wir sind Marktführer: erfahren Sie mehr und "
        "kontaktieren Sie uns, jetzt anfragen. " + "wort " * 50,
        "Líder del mercado: descubre más, haz clic aquí y "
        "contáctanos hoy. " + "palabra " * 50,
    )
    for testo in casi:
        findings = sra._audit_filler([_pagina_con_testo(testo)])
        assert findings[0].severity == sra.SEV_WARNING, testo[:40]


def test_filler_ignora_pagine_brevissime():
    findings = sra._audit_filler(
        [_pagina_con_testo("Clicca qui. Scopri di più. Seguici "
                           "su Facebook.")])
    assert findings == []


# ---------------- ciclo di vita dell'argomento ----------------

def _sito_con_heading(*heading_per_pagina):
    pages = []
    for i, headings in enumerate(heading_per_pagina):
        page = sra.Page(url="https://mio.it/p%d" % i, status=200,
                        text="testo", word_count=300)
        page.headings = [(2, h) for h in headings]
        pages.append(page)
    return pages


def test_ciclo_di_vita_completo_anche_su_piu_pagine():
    pages = _sito_con_heading(
        ["Cos'è il drenaggio linfatico",
         "Storia e origini della tecnica"],
        ["Quando serve: casi d'uso",
         "Limiti e controindicazioni"],
        ["Domande frequenti",
         "Prospettive e tendenze della riabilitazione"])
    findings = sra._audit_lifecycle(pages)
    assert len(findings) == 1
    assert findings[0].severity == sra.SEV_OK
    assert "6 su 6" in findings[0].title


def test_ciclo_di_vita_scoperto_pesa_di_piu():
    pages = _sito_con_heading(["I nostri servizi", "Contatti"])
    findings = sra._audit_lifecycle(pages)
    assert findings[0].severity == sra.SEV_WARNING
    assert "0 su 6" in findings[0].title
    assert findings[0].weight == 2.0
    assert "definizione" in findings[0].detail
    assert "<h2>Domande frequenti</h2>" in findings[0].example
    assert sra.estimate_effort(findings[0]) == sra.EFFORT_DAYS


def test_ciclo_di_vita_incompleto_elenca_le_mancanti():
    pages = _sito_con_heading(
        ["Cos'è il drenaggio", "A cosa serve: applicazioni",
         "Domande frequenti", "Rischi e controindicazioni"])
    findings = sra._audit_lifecycle(pages)
    assert findings[0].severity == sra.SEV_WARNING
    assert "4 su 6" in findings[0].title
    assert findings[0].weight == 1.0
    assert "storia" in findings[0].detail
    assert "prospettive" in findings[0].detail


def test_ciclo_di_vita_multilingua():
    pages = _sito_con_heading(
        ["Was ist Lymphdrainage", "Geschichte der Methode",
         "Anwendungen und Einsatz", "Grenzen und Risiken",
         "Häufig gestellte Fragen", "Zukunft und Trends"])
    findings = sra._audit_lifecycle(pages)
    assert findings[0].severity == sra.SEV_OK
    assert "6 su 6" in findings[0].title


# ---------------- riferimenti bibliografici ----------------

def _pagina_fonti(headings=(), testo="testo normale",
                  external=0):
    page = sra.Page(url="https://mio.it/", status=200, text=testo,
                    word_count=len(testo.split()),
                    external_links=external)
    page.headings = [(2, h) for h in headings]
    return page


def test_riferimenti_sezione_fonti_ok():
    page = _pagina_fonti(headings=["Fonti e riferimenti"],
                         external=4)
    findings = sra._audit_references([page])
    assert len(findings) == 1
    assert findings[0].severity == sra.SEV_OK
    assert "Fonti e riferimenti" in findings[0].detail


def test_riferimenti_citazioni_nel_testo_ok():
    testo = ("Lo studio dimostra l'efficacia [1] e la revisione "
             "sistematica lo conferma [2]; vedi anche "
             "(Rossi, 2023) per il protocollo completo.")
    findings = sra._audit_references([_pagina_fonti(testo=testo)])
    assert findings[0].severity == sra.SEV_OK
    assert "3 citazioni" in findings[0].detail


def test_riferimenti_assenti_avvertenza():
    findings = sra._audit_references(
        [_pagina_fonti(headings=["I nostri servizi"],
                       testo="Offriamo massaggi e terapie.",
                       external=2)])
    assert findings[0].severity == sra.SEV_WARNING
    assert "2 link esterni" in findings[0].detail
    assert findings[0].fix and "Fonti" in findings[0].example


def test_riferimenti_quellen_tedesco():
    page = _pagina_fonti(headings=["Quellen und Literatur"])
    findings = sra._audit_references([page])
    assert findings[0].severity == sra.SEV_OK


def test_riferimenti_due_citazioni_non_bastano():
    testo = "Efficace [1] e sicuro [2] secondo la letteratura."
    findings = sra._audit_references([_pagina_fonti(testo=testo)])
    assert findings[0].severity == sra.SEV_WARNING
