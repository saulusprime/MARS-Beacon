# -*- coding: utf-8 -*-
"""Tipologie MARS: campo pillar dei rilievi e propagazione."""

import json

import mars_audit as sra


def test_pilastro_default_per_area():
    attesi = {
        sra.AREA_TECH: sra.PILLAR_ACCESS,
        sra.AREA_LEX: sra.PILLAR_RANK,
        sra.AREA_SEM: sra.PILLAR_RANK,
        sra.AREA_SD: sra.PILLAR_RANK,
        sra.AREA_RRF: sra.PILLAR_META,
    }
    for area, pillar in attesi.items():
        f = sra.Finding(area, sra.SEV_OK, "x")
        assert f.as_dict()["pillar"] == pillar


def test_override_esplicito_vince_sul_default():
    f = sra.Finding(sra.AREA_TECH, sra.SEV_OK, "HTTPS attivo",
                    pillar=sra.PILLAR_SEC)
    assert f.as_dict()["pillar"] == sra.PILLAR_SEC


def test_optout_microsoft_e_sicurezza():
    pagina = sra.Page(url="https://x.it/", status=200,
                      meta_robots="noarchive")
    findings = sra._audit_msft_ai_optout([pagina])
    assert findings, "atteso il rilievo noarchive"
    assert all(f.pillar == sra.PILLAR_SEC for f in findings)

    pulita = sra.Page(url="https://x.it/", status=200)
    ok = sra._audit_msft_ai_optout([pulita])
    assert ok and ok[0].pillar == sra.PILLAR_SEC


def test_http_residuo_e_sicurezza():
    p = sra.Page(url="http://x.it/a", status=200,
                 final_url="https://x.it/a")
    findings = sra._audit_redirects([p])
    http = [f for f in findings if "ancora in http" in f.title]
    assert http and http[0].pillar == sra.PILLAR_SEC


def test_pillar_nel_referto_json(site):
    pages, findings, scores, results, mode, _ = sra.run_audit(
        base=site, max_pages=10, queries=[], model_name="none",
        delay=0.0, k=60, verbose=False)
    payload = json.loads(sra.render_json(
        site, pages, findings, scores, results, mode, 60))
    pillars = {f["pillar"] for f in payload["findings"]}
    # il sito fixture e' in http: il rilievo HTTPS e' security
    assert sra.PILLAR_SEC in pillars
    assert pillars <= {sra.PILLAR_META, sra.PILLAR_ACCESS,
                       sra.PILLAR_RANK, sra.PILLAR_SEC}
