# -*- coding: utf-8 -*-
"""Nucleo numerico: BM25, indice vettoriale di ripiego, fusione RRF.

I valori attesi sono quelli verificati a mano e documentati nella
nota tecnica: idf = ln(1 + (N-n+0.5)/(n+0.5)); con k=60 un documento
2° in una lista e 3° nell'altra (1/62 + 1/63) batte un documento 1°
in una sola lista (1/61).
"""

import math

import seo_rrf_audit as sra


def test_bm25_idf_formula():
    idx = sra.BM25Index(["gatto dorme", "cane corre", "gatto salta"])
    atteso = math.log(1 + (3 - 1 + 0.5) / (1 + 0.5))
    assert abs(idx.idf["cane"] - atteso) < 1e-9


def test_bm25_saturazione_frequenza():
    filler = "alfa beta gamma delta epsilon zeta eta theta iota"
    docs = ["ricerca " + filler, "ricerca " * 9 + "ricerca"]
    idx = sra.BM25Index(docs)
    scores = dict(idx.search("ricerca"))
    assert scores[1] > scores[0]
    assert scores[1] < 10 * scores[0]


def test_bm25_ordina_per_pertinenza():
    docs = ["il drenaggio linfatico manuale spiegato in dettaglio",
            "ricetta della torta di mele con cannella profumata",
            "drenaggio dei terreni agricoli in pianura padana"]
    idx = sra.BM25Index(docs)
    risultati = idx.search("drenaggio linfatico")
    assert risultati[0][0] == 0
    assert 1 not in {i for i, _ in risultati}


def test_vector_index_fallback_e_coseno():
    docs = ["il drenaggio linfatico manuale favorisce la circolazione",
            "ricetta della torta di mele con cannella",
            "massaggio e drenaggio dei tessuti linfatici"]
    vi = sra.VectorIndex(docs)
    assert vi.mode == "char-tfidf"
    risultati = vi.search(docs[0])
    assert risultati[0][0] == 0
    assert abs(risultati[0][1] - 1.0) < 1e-9
    assert all(0.0 < s <= 1.0 + 1e-9 for _, s in risultati)


def test_vector_index_modello_mancante_ripiega():
    vi = sra.VectorIndex(["un documento qualunque di prova"],
                         model_name="modello-inesistente")
    assert vi.mode == "char-tfidf"


def test_rrf_consenso_batte_primato_singolo():
    lista1 = [(0, 5.0), (1, 4.0)]            # doc 0 primo, doc 1 secondo
    lista2 = [(2, 9.0), (3, 8.0), (1, 7.0)]  # doc 1 terzo
    fusi = sra.reciprocal_rank_fusion([lista1, lista2], k=60)
    atteso = 1 / 62 + 1 / 63
    assert fusi[0][0] == 1
    assert abs(fusi[0][1] - atteso) < 1e-9
    assert abs(atteso - 0.032002) < 1e-6


def test_rrf_rango_parte_da_uno():
    fusi = sra.reciprocal_rank_fusion([[(7, 3.0)]], k=60)
    assert fusi == [(7, 1 / 61)]


def test_rrf_top_n():
    liste = [[(i, float(10 - i)) for i in range(10)]]
    assert len(sra.reciprocal_rank_fusion(liste, top_n=3)) == 3


def test_area_score_pesato():
    findings = [
        sra.Finding("Tecnica", sra.SEV_OK, "ok", weight=1.0),
        sra.Finding("Tecnica", sra.SEV_CRITICAL, "male", weight=2.0),
    ]
    assert sra.area_score(findings, "Tecnica") == 33.3


def test_area_score_solo_info_e_nessuna():
    findings = [sra.Finding("Tecnica", sra.SEV_INFO, "nota")]
    assert sra.area_score(findings, "Tecnica") is None
    assert sra.area_score([], "Tecnica") is None


def test_overall_score_media_pesata():
    scores = {sra.AREA_TECH: 100.0, sra.AREA_LEX: 0.0,
              sra.AREA_SEM: None, sra.AREA_SD: None,
              sra.AREA_RRF: None}
    assert sra.overall_score(scores) == 40.0
