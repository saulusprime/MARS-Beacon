# -*- coding: utf-8 -*-
"""Test unitari delle funzioni di base (token, n-grammi, URL, RAM)."""

import seo_rrf_audit as sra


def test_tokenize_rimuove_stopword_e_minuscolizza():
    assert sra.tokenize("Il gatto NERO dorme") == \
        ["gatto", "nero", "dorme"]


def test_tokenize_scarta_token_corti():
    assert "re" not in sra.tokenize("il re di Roma")


def test_tokenize_keep_stopwords():
    assert sra.tokenize("Il gatto", keep_stopwords=True) == \
        ["il", "gatto"]


def test_char_ngrams_dimensione_e_normalizzazione():
    grams = sra.char_ngrams("Drenaggio  Linfatico")
    assert grams
    assert all(len(g) == 4 for g in grams)
    assert grams == sra.char_ngrams("drenaggio linfatico")


def test_char_ngrams_testo_corto():
    assert sra.char_ngrams("ab") == ["ab"]
    assert sra.char_ngrams("   ") == []


def test_norm_url():
    assert sra.norm_url("https://x.it/pagina/") == "https://x.it/pagina"
    assert sra.norm_url("https://x.it/") == "https://x.it/"
    assert sra.norm_url("https://x.it/p#sezione") == "https://x.it/p"
    assert sra.norm_url("https://x.it/p?a=1") == "https://x.it/p?a=1"


def test_available_ram_mb():
    ram = sra.available_ram_mb()
    assert ram is None or ram > 0


def test_is_question():
    assert sra.is_question("Cos'e' il drenaggio linfatico?")
    assert sra.is_question("come funziona una seduta")
    assert not sra.is_question("I nostri servizi principali")


# ---------------- auto-rilevamento sentence-transformers ----------------

def test_embeddings_auto_rilevati(monkeypatch):
    monkeypatch.setattr(sra, "embeddings_available", lambda: True)
    assert sra.resolve_model_name("") == sra.DEFAULT_EMBEDDINGS_MODEL
    assert sra.resolve_model_name("  ") == sra.DEFAULT_EMBEDDINGS_MODEL


def test_embeddings_modello_esplicito_vince(monkeypatch):
    monkeypatch.setattr(sra, "embeddings_available", lambda: True)
    assert sra.resolve_model_name("mio/modello") == "mio/modello"


def test_embeddings_none_forza_il_proxy(monkeypatch):
    monkeypatch.setattr(sra, "embeddings_available", lambda: True)
    for spento in ("none", "NONE", "off", "char-tfidf"):
        assert sra.resolve_model_name(spento) == ""


def test_embeddings_senza_libreria_resta_proxy(monkeypatch):
    monkeypatch.setattr(sra, "embeddings_available", lambda: False)
    assert sra.resolve_model_name("") == ""
    assert sra.resolve_model_name("mio/modello") == "mio/modello"
