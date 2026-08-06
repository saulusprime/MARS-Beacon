# -*- coding: utf-8 -*-
"""Soglie configurabili da file TOML (--config, v1.61.0).

Il registro CONFIG_THRESHOLDS espone le sole soglie "di prassi" i
cui rilievi dichiarano il valore nei params; load_thresholds valida
il file (errore d'uso, mai audit fallito) e apply_thresholds
riassegna le costanti in ogni modulo che le espone — stesso motivo
dell'helper _patch: dopo la scomposizione conta il namespace del
consumatore.
"""

import json

import pytest

import mars_audit as sra


def _scrivi(tmp_path, testo):
    percorso = tmp_path / "soglie.toml"
    percorso.write_text(testo, encoding="utf-8")
    return str(percorso)


def test_esempio_documentato_carica_i_default():
    """docs/soglie.esempio.toml copre tutte le soglie coi default."""
    soglie = sra.load_thresholds("docs/soglie.esempio.toml")
    assert set(soglie) == set(sra.CONFIG_THRESHOLDS)
    for chiave, valore in soglie.items():
        costante = sra.CONFIG_THRESHOLDS[chiave][0]
        assert valore == getattr(sra, costante), chiave


def test_file_parziale_e_tipi(tmp_path):
    percorso = _scrivi(tmp_path,
                       "[soglie]\ntitle_min = 25\n"
                       "estraibilita_minima = 0.5\n")
    assert sra.load_thresholds(percorso) == {
        "title_min": 25, "estraibilita_minima": 0.5}


def test_validazione_respinta_con_messaggi(tmp_path):
    casi = (
        ("[soglie]\ninventata = 1\n", "Soglia sconosciuta"),
        ("[altra]\ntitle_min = 25\n", "Tabella sconosciuta"),
        ("[soglie]\ntitle_min = \"trenta\"\n", "vuole un numero"),
        ("[soglie]\ntitle_min = true\n", "vuole un numero"),
        ("[soglie]\ntitle_min = 25.5\n", "numero intero"),
        ("[soglie]\ntitle_min = 0\n", "deve stare fra"),
        ("[soglie]\nestraibilita_minima = 1.5\n", "deve stare fra"),
        ("[soglie]\ntitle_min = 70\n", "deve restare minore"),
        ("[soglie]\ntitle_min = 60\ntitle_max = 50\n",
         "deve restare minore"),
        ("title_min = \n", "TOML non valido"),
    )
    for testo, atteso in casi:
        with pytest.raises(ValueError) as exc:
            sra.load_thresholds(_scrivi(tmp_path, testo))
        assert atteso in str(exc.value), testo


def test_file_assente_e_errore_duso(tmp_path):
    with pytest.raises(ValueError) as exc:
        sra.load_thresholds(str(tmp_path / "non-esiste.toml"))
    assert "Impossibile leggere" in str(exc.value)


def test_apply_su_tutti_i_moduli_e_ripristino():
    import marsbeacon.audits
    import marsbeacon.base
    precedenti = sra.apply_thresholds(
        {"title_min": 40, "parole_scarse": 500})
    try:
        for modulo in (sra, marsbeacon.base, marsbeacon.audits):
            assert modulo.TITLE_MIN == 40
            assert modulo.THIN_CONTENT_WORDS == 500
        assert precedenti == {"title_min": 30, "parole_scarse": 300}
    finally:
        sra.apply_thresholds(precedenti)
    for modulo in (sra, marsbeacon.base, marsbeacon.audits):
        assert modulo.TITLE_MIN == 30
        assert modulo.THIN_CONTENT_WORDS == 300


def test_soglie_applicate_cambiano_i_rilievi(site):
    """Con title_min alzato il rilievo dichiara la soglia usata,
    in italiano e nei cataloghi (params min/max)."""
    precedenti = sra.apply_thresholds(
        {"title_min": 190, "title_max": 195})
    try:
        pages, findings, scores, results, mode, _ = sra.run_audit(
            base=site, max_pages=5, queries=[], model_name="none",
            delay=0.0, k=60, verbose=False)
    finally:
        sra.apply_thresholds(precedenti)
    per_chiave = {f.key: f for f in findings}
    rilievo = per_chiave["lex.title.bad"]
    assert rilievo.params["min"] == 190
    assert "190-195 caratteri" in rilievo.fix
    assert "190-195 characters" \
        in sra.finding_texts(rilievo, "en")["fix"]
    assert "de 190 à 195 caractères" \
        in sra.finding_texts(rilievo, "fr")["fix"]


def test_cli_config_invalida_esce_con_2(tmp_path, capsys):
    percorso = _scrivi(tmp_path, "[soglie]\ninventata = 1\n")
    rc = sra.main(["https://x.invalid", "--config", percorso])
    assert rc == 2
    assert "Soglia sconosciuta" in capsys.readouterr().err


def test_cli_e2e_con_eco_nel_json(site, tmp_path, capsys):
    percorso = _scrivi(tmp_path,
                       "[soglie]\ndescription_min = 90\n")
    uscita = tmp_path / "referto.json"
    rc = sra.main([site, "--max-pages", "3", "--delay", "0",
                   "--config", percorso, "--format", "json",
                   "--output", str(uscita)])
    assert rc in (0, 1)
    payload = json.loads(uscita.read_text(encoding="utf-8"))
    assert payload["thresholds"] == {"description_min": 90}
    # ripristino: la CLI e' usa-e-getta ma la suite no
    sra.apply_thresholds({"description_min": 110})
    assert "Soglie personalizzate" in capsys.readouterr().err
