# -*- coding: utf-8 -*-
"""Profili di citabilita' per assistente IA (lenti per modello).

Gli ancoraggi numerici sono calcolati a mano dai pesi dichiarati in
CITABILITY_PROFILES e MARKET_WEIGHTS: se un peso cambia, il valore
atteso va ricalcolato, non "aggiustato".
"""

import json

import pytest

import mars_audit as sra


def _pages():
    """Due pagine buone: 400+500 parole -> media 450, profondita' 50."""
    return [
        sra.Page(url="https://sito.test/a", status=200,
                 text="testo", word_count=400),
        sra.Page(url="https://sito.test/b", status=200,
                 text="altro", word_count=500),
    ]


def _scores():
    return {
        sra.AREA_TECH: 80.0,
        sra.AREA_LEX: 60.0,
        sra.AREA_SEM: 70.0,
        sra.AREA_SD: 50.0,
        sra.AREA_RRF: 42.0,
    }


# ---------------- coerenza dei pesi dichiarati ----------------

def test_pesi_profili_sommano_a_uno():
    for _key, _label, _focus, weights in sra.CITABILITY_PROFILES:
        assert abs(sum(weights.values()) - 1.0) < 1e-9


def test_pesi_mercato_coprono_tutti_i_profili():
    keys = {key for key, _l, _f, _w in sra.CITABILITY_PROFILES}
    for market, weights in sra.MARKET_WEIGHTS.items():
        assert set(weights) == keys, market
        assert abs(sum(weights.values()) - 1.0) < 1e-9, market
    assert sra.DEFAULT_MARKET in sra.MARKET_WEIGHTS


# ---------------- calcolo dei punteggi ----------------

def test_punteggi_profilo_calcolati_a_mano():
    cit = sra.citability_profiles(_pages(), _scores())
    by_key = {p["key"]: p for p in cit["profiles"]}
    # claude  = .40*70 + .25*60 + .20*80 + .15*50           = 66.5
    # chatgpt = .45*42 + .25*60 + .15*80 + .15*70           = 56.4
    # qwen    = .40*50 + .25*80 + .20*70 + .15*60           = 63.0
    # kimi    = .35*50(prof) + .30*70 + .20*50 + .15*60     = 57.5
    assert by_key["claude"]["score"] == 66.5
    assert by_key["chatgpt"]["score"] == 56.4
    assert by_key["qwen"]["score"] == 63.0
    assert by_key["kimi"]["score"] == 57.5
    # profondita': media 450 parole su target 900 -> 50.0
    depth = by_key["kimi"]["components"][sra.CITABILITY_DEPTH]
    assert depth == 50.0


def test_indice_composito_per_mercato():
    pages, scores = _pages(), _scores()
    occ = sra.citability_profiles(pages, scores, "occidentale")
    # .30*66.5 + .50*56.4 + .10*63.0 + .10*57.5 = 60.2
    assert abs(occ["index"] - 60.2) < 0.051
    ori = sra.citability_profiles(pages, scores, "orientale")
    # .10*66.5 + .20*56.4 + .35*63.0 + .35*57.5 = 60.105 -> 60.1
    assert abs(ori["index"] - 60.1) < 0.051
    assert occ["market"] == "occidentale"
    assert ori["market_weights"]["qwen"] == 0.35


def test_area_mancante_rinormalizza_i_pesi():
    scores = _scores()
    scores[sra.AREA_RRF] = None
    cit = sra.citability_profiles(_pages(), scores)
    by_key = {p["key"]: p for p in cit["profiles"]}
    # chatgpt senza RRF: (.25*60+.15*80+.15*70) / 0.55 = 68.2
    assert by_key["chatgpt"]["score"] == 68.2
    assert sra.AREA_RRF not in by_key["chatgpt"]["components"]


def test_mercato_sconosciuto_rifiutato():
    with pytest.raises(ValueError):
        sra.citability_profiles(_pages(), _scores(), "marziano")


def test_nessun_dato_restituisce_none():
    vuoti = {area: None for area in _scores()}
    assert sra.citability_profiles([], vuoti) is None


# ---------------- top azioni prioritarie ----------------

def _findings():
    """Pesi scelti per un calcolo a mano dei guadagni.

    Dati strutturati: critico peso 3 su totale 4 -> risolverlo vale
    100*3/4 = 75 punti d'area. Tecnica: avvertenza peso 2 su totale
    4 -> 100*2*0.5/4 = 25 punti d'area.
    """
    return [
        sra.Finding(sra.AREA_SD, sra.SEV_CRITICAL,
                    "FAQPage assente", weight=3.0),
        sra.Finding(sra.AREA_SD, sra.SEV_OK, "WebSite presente",
                    weight=1.0),
        sra.Finding(sra.AREA_TECH, sra.SEV_WARNING,
                    "Sitemap XML assente o illeggibile",
                    weight=2.0),
        sra.Finding(sra.AREA_TECH, sra.SEV_OK, "HTTPS attivo",
                    weight=2.0),
    ]


def test_top_azioni_guadagni_calcolati_a_mano():
    azioni = sra.citability_top_actions(
        _findings(), _pages(), _scores())
    assert len(azioni) == 2
    prima, seconda = azioni

    # Critico prima dell'avvertenza, come nel piano di remediation.
    assert prima["priority"] == 1
    assert prima["title"] == "FAQPage assente"
    # Delta area 75; quote sui dati strutturati: qwen .40,
    # kimi .20, chatgpt 0 (tutte le componenti hanno punteggio,
    # quindi i pesi non vengono rinormalizzati).
    assert prima["gains"]["qwen"] == 30.0
    assert prima["gains"]["kimi"] == 15.0
    assert prima["gains"]["chatgpt"] == 0.0
    assert prima["best_profile"] == "qwen"
    assert prima["best_gain"] == 30.0
    assert prima["effort"] == sra.EFFORT_DAYS  # "faq" -> giorni
    assert prima["quick_win"] is False

    assert seconda["title"].startswith("Sitemap")
    assert seconda["best_profile"] == "qwen"  # tecnica pesa .25
    assert seconda["effort"] == sra.EFFORT_MINUTES
    assert seconda["quick_win"] is False  # avvertenza, non critico


def test_top_azioni_coerenti_col_piano_e_col_tetto():
    findings = _findings()
    piano = sra.build_remediation(findings)
    azioni = sra.citability_top_actions(
        findings, _pages(), _scores(), top=1)
    assert len(azioni) == 1
    assert azioni[0]["title"] == piano[0]["title"]
    assert azioni[0]["severity"] == piano[0]["severity"]


def test_top_azioni_senza_profili():
    vuoti = {area: None for area in _scores()}
    assert sra.citability_top_actions(_findings(), [], vuoti) == []


# ---------------- problemi trasversali nel piano ----------------

def test_piano_promuove_i_trasversali():
    """A parita' di gravita' e peso vince chi risolleva piu' profili.

    Due avvertenze di peso 3 su aree con totale 4: delta d'area 37.5
    per entrambe. La semantica alimenta tutti e quattro i profili
    (indice ~9.2), la simulazione RRF solo ChatGPT/Perplexity
    (indice ~8.5): senza dati di citabilita' vince l'ordine di
    inserimento, con i dati la semantica viene promossa.
    """
    findings = [
        sra.Finding(sra.AREA_RRF, sra.SEV_WARNING,
                    "Consenso basso", weight=3.0),
        sra.Finding(sra.AREA_RRF, sra.SEV_OK, "Query coperte",
                    weight=1.0),
        sra.Finding(sra.AREA_SEM, sra.SEV_WARNING,
                    "Poche definizioni", weight=3.0),
        sra.Finding(sra.AREA_SEM, sra.SEV_OK, "FAQ presenti",
                    weight=1.0),
    ]
    legacy = sra.build_remediation(findings)
    assert legacy[0]["area"] == sra.AREA_RRF
    assert "index_gain" not in legacy[0]

    piano = sra.build_remediation(findings, _pages(), _scores())
    assert piano[0]["area"] == sra.AREA_SEM
    assert piano[0]["cross"] is True
    assert len(piano[0]["profiles_hit"]) == 4
    assert piano[1]["area"] == sra.AREA_RRF
    assert piano[1]["cross"] is False
    assert piano[1]["profiles_hit"] == ["chatgpt"]
    assert [x["priority"] for x in piano] == [1, 2]
    assert piano[0]["index_gain"] > piano[1]["index_gain"]


def test_guadagni_sotto_soglia_non_trasversali():
    findings = [
        sra.Finding(sra.AREA_SD, sra.SEV_WARNING,
                    "Una proprieta' minore", weight=1.0),
        sra.Finding(sra.AREA_SD, sra.SEV_OK, "Resto a posto",
                    weight=39.0),
    ]
    piano = sra.build_remediation(findings, _pages(), _scores())
    # Delta d'area 1.25: nessun profilo arriva a CROSS_GAIN_MIN.
    assert piano[0]["profiles_hit"] == []
    assert piano[0]["cross"] is False
    assert "index_gain" in piano[0]


def test_top_azioni_stesse_priorita_del_piano():
    findings = [
        sra.Finding(sra.AREA_RRF, sra.SEV_WARNING,
                    "Consenso basso", weight=3.0),
        sra.Finding(sra.AREA_SEM, sra.SEV_WARNING,
                    "Poche definizioni", weight=3.0),
        sra.Finding(sra.AREA_SEM, sra.SEV_OK, "FAQ presenti",
                    weight=1.0),
        sra.Finding(sra.AREA_RRF, sra.SEV_OK, "Query coperte",
                    weight=1.0),
    ]
    piano = sra.build_remediation(findings, _pages(), _scores())
    azioni = sra.citability_top_actions(
        findings, _pages(), _scores(), top=2)
    assert [a["title"] for a in azioni] == \
        [i["title"] for i in piano[:2]]


# ---------------- referti ----------------

def test_referto_json_include_citability():
    payload = json.loads(sra.render_json(
        "https://sito.test", _pages(), _findings(), _scores(), [],
        "char-tfidf", 60, None, market="orientale"))
    cit = payload["citability"]
    assert cit["market"] == "orientale"
    assert len(cit["profiles"]) == 4
    assert cit["note"] == sra.CITABILITY_NOTE
    assert 0.0 <= cit["index"] <= 100.0
    azioni = payload["citability_actions"]
    assert len(azioni) == 2
    assert azioni[0]["best_profile"] == "qwen"


def test_referto_testo_include_profili():
    testo = sra.render_text(
        "https://sito.test", _pages(), _findings(), _scores(), [],
        "char-tfidf")
    assert "PROFILI DI CITABILITA' PER ASSISTENTE IA" in testo
    assert "INDICE COMPOSITO" in testo
    assert "mercato %s" % sra.DEFAULT_MARKET in testo
    assert "Azioni con maggior guadagno di profilo" in testo
    assert "+30.0 punti profilo" in testo
    assert "gravita' e guadagno di citabilita'" in testo
    assert "Trasversale: deprime 3 profili" in testo


def test_referto_html_include_profili():
    pagina = sra.render_html(
        "https://sito.test", _pages(), _findings(), _scores(), [],
        "char-tfidf")
    assert "Profili di citabilita' per assistente IA" in pagina
    assert "Indice composito" in pagina
    assert sra.CITABILITY_NOTE in pagina
    assert "Top 2 azioni prioritarie" in pagina
    assert "guadagna di piu'" in pagina
    assert "trasversale: 3 profili" in pagina  # badge nel piano


# ---------------- CLI ----------------

def test_cli_accetta_mercati_noti():
    args = sra.build_parser().parse_args(
        ["https://sito.test", "--market", "globale"])
    assert args.market == "globale"


def test_cli_default_e_rifiuto_mercato_ignoto():
    args = sra.build_parser().parse_args(["https://sito.test"])
    assert args.market == sra.DEFAULT_MARKET
    with pytest.raises(SystemExit):
        sra.build_parser().parse_args(
            ["https://sito.test", "--market", "lunare"])
