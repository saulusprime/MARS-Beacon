# -*- coding: utf-8 -*-
"""i18n dei referti: cataloghi per lingua, resolver, renderer.

Dalla v1.60.0 le lingue del referto sono it/en/fr/de/es: una
tabella per lingua per i rilievi (_FINDINGS_*), per la cornice
HTML (_HTML_I18N) e per la cornice text/md (_FRAME_I18N, chiave =
testo italiano canonico delle chiamate T()).
"""

import ast
import re

import mars_audit as sra

_LINGUE = ("en", "fr", "de", "es")


class _Zero(dict):
    """Dict che risponde 0 a ogni chiave: valida i template."""

    def __missing__(self, key):
        return 0


def _chiavi_T_da_render():
    """Testi italiani delle chiamate T(it, en) in render.py."""
    with open(sra.render_text.__code__.co_filename,
              encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    chiavi = set()
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "T" and len(node.args) == 2
                and all(isinstance(a, ast.Constant)
                        for a in node.args)):
            chiavi.add(node.args[0].value)
    return chiavi


def test_template_formattabili_in_tutte_le_lingue():
    """Ogni template di ogni catalogo formatta senza errori."""
    for lingua in _LINGUE:
        for key, entry in sra._FINDINGS_BY_LANG[lingua].items():
            for field, template in entry.items():
                try:
                    template % _Zero()
                except (ValueError, TypeError) as exc:
                    raise AssertionError(
                        "template %s %s.%s malformato: %s"
                        % (lingua, key, field, exc))


def test_cataloghi_rilievi_stesse_chiavi_e_campi():
    """FR/DE/ES coprono le stesse voci e campi di EN."""
    en = sra._FINDINGS_EN
    for lingua in ("fr", "de", "es"):
        cat = sra._FINDINGS_BY_LANG[lingua]
        assert set(cat) == set(en), \
            "%s: chiavi diverse: %r" % (lingua, set(cat) ^ set(en))
        for key in en:
            assert set(cat[key]) == set(en[key]), \
                "%s.%s: campi diversi" % (lingua, key)


def test_cornice_frame_copre_le_chiamate_T():
    """_FRAME_I18N copre ogni T(it, en) di render.py, senza voci
    orfane e con gli stessi segnaposto posizionali."""
    chiavi = _chiavi_T_da_render()
    assert chiavi, "nessuna chiamata T() trovata"
    spec = re.compile(r"%(?:[-+ #0]*\d*(?:\.\d+)?[sdif]|%)")
    for lingua in ("fr", "de", "es"):
        tabella = sra._FRAME_I18N[lingua]
        assert not chiavi - set(tabella), \
            "%s: chiavi mancanti: %r" % (lingua,
                                         chiavi - set(tabella))
        assert not set(tabella) - chiavi, \
            "%s: voci orfane: %r" % (lingua,
                                     set(tabella) - chiavi)
        for k, v in tabella.items():
            sk = [s for s in spec.findall(k) if s != "%%"]
            sv = [s for s in spec.findall(v) if s != "%%"]
            assert sk == sv, \
                "%s: segnaposto diversi per %r" % (lingua, k)


def test_fallback_su_chiave_o_parametri_mancanti():
    senza_chiave = sra.Finding(sra.AREA_LEX, sra.SEV_OK, "Titolo it")
    assert sra.finding_texts(senza_chiave, "en")["title"] == \
        "Titolo it"
    chiave_ignota = sra.Finding(sra.AREA_LEX, sra.SEV_OK,
                                "Titolo it", key="non.esiste")
    assert sra.finding_texts(chiave_ignota, "en")["title"] == \
        "Titolo it"
    # parametri incoerenti col template: resta l'italiano, campo
    # per campo, senza eccezioni — in ogni lingua
    rotto = sra.Finding(sra.AREA_LEX, sra.SEV_WARNING,
                        "2 title duplicati fra pagine",
                        key="lex.title.dup", params={})
    for lingua in _LINGUE:
        testi = sra.finding_texts(rotto, lingua)
        assert testi["title"] == "2 title duplicati fra pagine"


def test_resolver_su_voci_del_piano():
    item = {"title": "Sito non in HTTPS", "fix": "f", "example": "",
            "key": "tech.https.missing", "params": {}}
    assert sra.finding_texts(item, "en")["title"] == \
        "Site not on HTTPS"
    assert sra.finding_texts(item, "fr")["title"] == \
        "Site sans HTTPS"
    assert sra.finding_texts(item, "de")["title"] == \
        "Website nicht auf HTTPS"
    assert sra.finding_texts(item, "es")["title"] == \
        "Sitio sin HTTPS"
    assert sra.finding_texts(item, "it")["title"] == \
        "Sito non in HTTPS"


def test_audit_reale_tutto_tradotto(site):
    """Sul sito fixture ogni rilievo ha chiave e traduzione
    effettiva (template applicato, nessun fallback) in ognuna
    delle quattro lingue."""
    pages, findings, scores, results, mode, _ = sra.run_audit(
        base=site, max_pages=10, queries=[], model_name="none",
        delay=0.0, k=60, verbose=False)
    assert findings
    for f in findings:
        assert f.key, "rilievo senza chiave i18n: %r" % f.title
        for lingua in _LINGUE:
            catalogo = sra._FINDINGS_BY_LANG[lingua]
            assert f.key in catalogo, \
                "%s: chiave scoperta: %r" % (lingua, f.key)
            atteso = catalogo[f.key]["title"] % f.params
            assert sra.finding_texts(f, lingua)["title"] == \
                atteso, "%s: fallback su %r" % (lingua, f.key)

    marcatori = {"it": "piano di remediation",
                 "en": "remediation plan",
                 "fr": "plan de rem",
                 "de": "behebungsplan",
                 "es": "plan de correc"}
    for render in (sra.render_text, sra.render_markdown,
                   sra.render_html):
        esiti = {lingua: render(site, pages, findings, scores,
                                results, mode, 60,
                                lang=lingua).lower()
                 for lingua in ("it",) + _LINGUE}
        for lingua, out in esiti.items():
            for altra, marcatore in marcatori.items():
                if altra == lingua:
                    assert marcatore in out, (lingua, marcatore)
                else:
                    assert marcatore not in out, \
                        (lingua, altra, marcatore)


def test_csv_intestazioni_per_lingua():
    intestazioni = {
        "en": "site;area;severity;weight;title",
        "fr": "site;domaine;gravité;poids;titre",
        "de": "website;bereich;schweregrad;gewicht;titel",
        "es": "sitio;área;gravedad;peso;título",
    }
    for lingua, atteso in intestazioni.items():
        out = sra.render_csv("https://x.it", [], [], {}, [], "x",
                             60, lang=lingua)
        assert out.lstrip("﻿").startswith(atteso), lingua
    out_it = sra.render_csv("https://x.it", [], [], {}, [], "x", 60)
    assert out_it.lstrip("﻿").startswith("sito;area;gravita")


def test_nota_evidenze_nelle_lingue():
    for lingua in _LINGUE:
        out = sra.render_text("https://x.it", [], [], {}, [], "x",
                              60, lang=lingua)
        assert sra.evidence_note(lingua) in out
    assert sra.evidence_note("it") == ""
