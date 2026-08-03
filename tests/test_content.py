# -*- coding: utf-8 -*-
"""Estrazione dei contenuti: parsing, chunking, deduplica, query."""

import seo_rrf_audit as sra


def _page_with_blocks(blocks):
    page = sra.Page(url="https://x.it/servizi", status=200)
    page.blocks = blocks
    return page


def test_build_chunks_segue_ordine_documento():
    page = _page_with_blocks([
        ("h", "Primo argomento"),
        ("p", "parole utili " * 10),
        ("h", "Secondo argomento"),
        ("p", "altre parole interessanti " * 10),
    ])
    chunks = sra.build_chunks(page)
    assert [c.heading for c in chunks] == \
        ["Primo argomento", "Secondo argomento"]


def test_build_chunks_scarta_sezioni_povere():
    page = _page_with_blocks([
        ("h", "Sezione ricca"),
        ("p", "contenuto informativo rilevante " * 8),
        ("h", "Sezione povera"),
        ("p", "poche parole qui"),
    ])
    chunks = sra.build_chunks(page)
    assert all(c.heading == "Sezione ricca" for c in chunks)


def test_build_chunks_divide_sezioni_lunghe():
    page = _page_with_blocks([
        ("h", "Guida completa"),
        ("p", "paragrafo denso di informazioni " * 60),
        ("p", "seguito della guida con esempi " * 60),
    ])
    chunks = sra.build_chunks(page, target_words=220)
    assert len(chunks) >= 2
    assert all(c.heading == "Guida completa" for c in chunks)


def test_extract_jsonld_tipi_e_blocchi_invalidi():
    html = """
    <script type="application/ld+json">
    {"@type": "Organization", "name": "X",
     "address": {"@type": "PostalAddress"}}
    </script>
    <script type="application/ld+json">non e' JSON</script>
    <script type="application/ld+json">
    [{"@type": "FAQPage"}]
    </script>
    """
    types, blocks = sra.extract_jsonld(html)
    assert types == ["FAQPage", "Organization", "PostalAddress"]
    assert len(blocks) == 2


def test_dedupe_pages_conserva_url_corto():
    testo = "contenuto identico servito da due indirizzi diversi"
    lunga = sra.Page(url="http://x.it/index.html", status=200)
    corta = sra.Page(url="http://x.it/", status=200)
    lunga.text = corta.text = testo
    rotta = sra.Page(url="http://x.it/errore", error="fallita")
    pagine, duplicati = sra.dedupe_pages([lunga, corta, rotta])
    assert duplicati == ["http://x.it/index.html"]
    assert {p.url for p in pagine} == \
        {"http://x.it/", "http://x.it/errore"}


def test_auto_queries_bigrammi_senza_degeneri():
    page = sra.Page(url="https://x.it/", status=200)
    page.title = "Drenaggio linfatico manuale | Centro Linfa"
    page.headings = [(2, "Drenaggio linfatico manuale"),
                     (2, "Come funziona il drenaggio linfatico")]
    queries = sra.auto_queries([page])
    assert any("drenaggio linfatico" in q for q in queries)
    assert all("funziona funziona" not in q for q in queries)
    assert all("cosa costa" not in q for q in queries)


def test_parse_page_dal_sito_di_prova(site):
    fetcher = sra.Fetcher(delay=0.0, verbose=False)
    url = site + "/servizio-drenaggio/"
    page = sra.parse_page(url, fetcher.get(url))
    assert page.ok
    assert page.lang == "it"
    assert "cos'e' e come funziona" in page.title
    assert page.description
    assert page.headings[0] == (1, "Il drenaggio linfatico manuale")
    assert [k for k, _ in page.blocks[:3]] == ["h", "h", "p"]
    assert page.word_count > 100
    assert page.chunks


def test_parse_page_estrae_jsonld_dalla_home(site):
    fetcher = sra.Fetcher(delay=0.0, verbose=False)
    page = sra.parse_page(site + "/", fetcher.get(site + "/"))
    assert page.jsonld_types == ["Organization"]
