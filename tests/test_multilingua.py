# -*- coding: utf-8 -*-
"""Pattern linguistici oltre it/en: francese, tedesco, spagnolo."""

import seo_rrf_audit as sra


# ---------------- stopword e tokenizzazione ----------------

def test_stopword_filtrate_nelle_tre_lingue():
    assert sra.tokenize("dans les meilleures conditions pour vous") \
        == ["meilleures", "conditions"]
    assert sra.tokenize("durch diese sehr wichtige Entscheidung") \
        == ["wichtige", "entscheidung"]
    assert sra.tokenize("desde nuestra experiencia sobre el tema") \
        == ["experiencia", "tema"]


# ---------------- definizioni ----------------

def test_definizioni_riconosciute():
    frasi = (
        "Le drainage lymphatique est une technique de massage.",
        "Il s'agit de la méthode la plus documentata.",
        "Die Lymphdrainage ist eine sanfte Massagetechnik.",
        "Unter Lymphdrainage versteht man eine Therapie.",
        "El drenaje linfático es una técnica manual.",
        "Se trata de un masaje suave y ritmico.",
    )
    for frase in frasi:
        assert sra.DEFINITION_RE.search(frase), frase


# ---------------- esempi ----------------

def test_esempi_riconosciuti():
    frasi = (
        "Par exemple après une opération.",
        "Zum Beispiel nach einer Operation.",
        "Diese Methode hilft beispielsweise beim Abschwellen.",
        "Por ejemplo después de una cirugía.",
    )
    for frase in frasi:
        assert sra.EXAMPLE_RE.search(frase), frase


# ---------------- anafore ----------------

def test_anafore_in_apertura():
    anaforici = ("Cela permet de réduire l'œdème.",
                 "Diese Methode wirkt schnell.",
                 "Esto permite reducir el edema.",
                 "Dicha técnica es muy eficaz.")
    for frase in anaforici:
        assert sra.ANAPHORA_RE.search(frase), frase
    autonomi = ("Es gibt viele Anwendungen.",  # espletivo, non anafora
                "Le drainage lymphatique est doux.",
                "Die Lymphdrainage wirkt entstauend.")
    for frase in autonomi:
        assert not sra.ANAPHORA_RE.search(frase), frase


# ---------------- FAQ e domande ----------------

def test_faq_riconosciute():
    for testo in ("Foire aux questions", "Questions fréquentes",
                  "Häufig gestellte Fragen",
                  "Preguntas frecuentes"):
        assert sra.FAQ_HINT_RE.search(testo), testo


def test_heading_interrogativi():
    domande = ("Comment fonctionne le drainage lymphatique",
               "Combien coûte une séance",
               "Wie funktioniert die Lymphdrainage",
               "Warum ist das wichtig",
               "¿Cuánto cuesta una sesión",
               "Qué es el drenaje linfático")
    for testo in domande:
        assert sra.is_question(testo), testo
    assert not sra.is_question("Le nostre tariffe")
    assert not sra.is_question("Der Behandlungsablauf")


# ---------------- lingua prevalente e query ----------------

def _pagina(lang, title, headings):
    page = sra.Page(url="https://sito.test/%s" % lang, status=200,
                    text="testo", word_count=300, lang=lang,
                    title=title)
    page.headings = [(2, h) for h in headings]
    return page


def test_lingua_prevalente():
    pages = [_pagina("fr-FR", "Drainage", []),
             _pagina("fr", "Tarifs", []),
             _pagina("it", "Home", [])]
    assert sra.dominant_language(pages) == "fr"
    assert sra.dominant_language([]) == "it"
    assert sra.dominant_language(
        [_pagina("ru", "Страница", [])]) == "it", \
        "lingua non supportata: ripiego sull'italiano"


def test_query_auto_nella_lingua_del_sito():
    pages = [_pagina("de", "Manuelle Lymphdrainage",
                     ["Manuelle Lymphdrainage Therapie",
                      "Lymphdrainage Behandlung Ablauf"])]
    queries = sra.auto_queries(pages, limit=6)
    assert queries and all(
        q.startswith(("was ist", "wie funktioniert", "was kostet"))
        for q in queries), queries

    pages_it = [_pagina("", "Drenaggio linfatico manuale",
                        ["Drenaggio linfatico gambe"])]
    queries_it = sra.auto_queries(pages_it, limit=3)
    assert queries_it and queries_it[0].startswith("cos'e'"), \
        "senza lang dichiarato il default resta l'italiano"


# ---------------- parametri RRF esposti (v1.31.0) ----------------

def test_rrf_pesata_calcolata_a_mano():
    """Liste [A,B] e [B,A]: alla pari, pesata vince chi domina la
    lista col peso maggiore. Addendi: w/(k+rank), k=60."""
    lista1 = [(0, 1.0), (1, 0.9)]   # A primo
    lista2 = [(1, 1.0), (0, 0.9)]   # B primo
    classico = sra.reciprocal_rank_fusion([lista1, lista2], k=60)
    assert classico[0][1] == classico[1][1]  # perfetta parita'
    pesata = sra.reciprocal_rank_fusion(
        [lista1, lista2], k=60, weights=(2.0, 1.0))
    # score(A) = 2/61 + 1/62; score(B) = 2/62 + 1/61
    assert pesata[0][0] == 0
    atteso_a = 2.0 / 61 + 1.0 / 62
    assert abs(pesata[0][1] - atteso_a) < 1e-12


def test_top_n_limita_le_liste():
    pages = [_pagina("it", "Drenaggio linfatico",
                     ["Drenaggio linfatico gambe",
                      "Costo drenaggio linfatico"])]
    pages[0].text = ("Il drenaggio linfatico e' una tecnica. "
                     * 40)
    pages[0].chunks = sra.build_chunks(sra.Page(
        url="https://sito.test/x", status=200,
        text=pages[0].text,
        paragraphs=[pages[0].text]))
    results, _, _ = sra.simulate_rrf(
        pages, ["drenaggio linfatico"], top_n=2)
    assert len(results[0].fused_top) <= 2
    assert len(results[0].lexical_top) <= 2


def test_chunk_words_cambia_il_taglio():
    paragrafi = [("parola " * 30).strip() for _ in range(30)]
    page = sra.Page(url="https://sito.test/", status=200,
                    text=" ".join(paragrafi),
                    paragraphs=paragrafi)
    fini = sra.build_chunks(page, target_words=100)
    grossi = sra.build_chunks(page, target_words=450)
    assert len(fini) > len(grossi) >= 1


def test_cli_valida_i_nuovi_parametri():
    assert sra.main(["https://x.it", "--top-n", "0",
                     "--quiet"]) == 2
    assert sra.main(["https://x.it", "--chunk-words", "10",
                     "--quiet"]) == 2
    assert sra.main(["https://x.it", "--rrf-weights", "1",
                     "--quiet"]) == 2
    assert sra.main(["https://x.it", "--rrf-weights", "0,-1",
                     "--quiet"]) == 2
