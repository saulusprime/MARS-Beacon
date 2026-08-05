"""Rilevamento runtime, flag CLI e runner del fork Lighthouse.

Percorsi, versioni, binari e processi sono simulati con monkeypatch
(il runner usa un finto ``subprocess.Popen``, quindi non serve Node):
nessuna dipendenza dallo stato della macchina, suite offline per
costruzione. Strategia del fork in docs/LIGHTHOUSE-FORK.md.
"""

import json
import threading

import pytest

import mars_audit as sra


def _patch(monkeypatch, name, value):
    """Monkeypatch sulla facciata e su ogni modulo marsbeacon che
    espone il nome: dopo la scomposizione (v1.58.0) conta il
    namespace del consumatore, non solo quello pubblico."""
    import mars_audit
    import marsbeacon.audits
    import marsbeacon.base
    import marsbeacon.crawler
    import marsbeacon.indexes
    import marsbeacon.render
    for modulo in (mars_audit, marsbeacon.base, marsbeacon.crawler,
                   marsbeacon.indexes, marsbeacon.audits,
                   marsbeacon.render):
        if name in vars(modulo):
            monkeypatch.setattr(modulo, name, value)


def _cli_finta(tmp_path):
    """Crea una finta CLI del fork e ne restituisce la directory."""
    cli = tmp_path / "lighthouse" / "cli"
    cli.mkdir(parents=True)
    (cli / "index.js").write_text("// finta CLI Lighthouse")
    return tmp_path / "lighthouse"


def test_find_system_chrome_primo_esistente(tmp_path, monkeypatch):
    chrome = tmp_path / "chrome"
    chrome.write_text("")
    _patch(monkeypatch, "CHROME_PATHS",
                        (str(tmp_path / "assente"), str(chrome)))
    assert sra.find_system_chrome() == str(chrome)


def test_find_system_chrome_nessuno(tmp_path, monkeypatch):
    _patch(monkeypatch, "CHROME_PATHS",
                        (str(tmp_path / "assente"),))
    assert sra.find_system_chrome() is None


def test_node_version_assente(monkeypatch):
    monkeypatch.setattr(sra.shutil, "which", lambda cmd: None)
    assert sra.node_version() is None


def test_node_version_parsing(monkeypatch):
    class Esito:
        stdout = "v22.19.0\n"

    monkeypatch.setattr(sra.shutil, "which",
                        lambda cmd: "/usr/bin/node")
    monkeypatch.setattr(sra.subprocess, "run",
                        lambda *a, **kw: Esito())
    assert sra.node_version() == (22, 19, 0)


def test_node_version_output_malformato(monkeypatch):
    class Esito:
        stdout = "boh\n"

    monkeypatch.setattr(sra.shutil, "which",
                        lambda cmd: "/usr/bin/node")
    monkeypatch.setattr(sra.subprocess, "run",
                        lambda *a, **kw: Esito())
    assert sra.node_version() is None


def test_lighthouse_senza_fork(tmp_path, monkeypatch):
    _patch(
        monkeypatch, "LIGHTHOUSE_CLI",
        str(tmp_path / "lighthouse" / "cli" / "index.js"))
    motivo = sra.lighthouse_unavailable()
    assert motivo is not None and "update-lighthouse" in motivo


def test_lighthouse_senza_node(tmp_path, monkeypatch):
    lh = _cli_finta(tmp_path)
    _patch(monkeypatch, "LIGHTHOUSE_CLI",
                        str(lh / "cli" / "index.js"))
    _patch(monkeypatch, "node_version", lambda: None)
    motivo = sra.lighthouse_unavailable()
    assert motivo is not None and "Node non trovato" in motivo


def test_lighthouse_node_vecchio(tmp_path, monkeypatch):
    lh = _cli_finta(tmp_path)
    _patch(monkeypatch, "LIGHTHOUSE_CLI",
                        str(lh / "cli" / "index.js"))
    _patch(monkeypatch, "node_version", lambda: (20, 11, 0))
    motivo = sra.lighthouse_unavailable()
    assert motivo is not None
    assert "20.11.0" in motivo and "22.19" in motivo


def test_lighthouse_node_alla_soglia(tmp_path, monkeypatch):
    lh = _cli_finta(tmp_path)
    _patch(monkeypatch, "LIGHTHOUSE_CLI",
                        str(lh / "cli" / "index.js"))
    _patch(monkeypatch, "node_version", lambda: (22, 19, 0))
    _patch(monkeypatch, "find_system_chrome",
                        lambda: "/usr/bin/google-chrome")
    assert sra.lighthouse_unavailable() is None


def test_lighthouse_senza_chrome(tmp_path, monkeypatch):
    lh = _cli_finta(tmp_path)
    _patch(monkeypatch, "LIGHTHOUSE_CLI",
                        str(lh / "cli" / "index.js"))
    _patch(monkeypatch, "node_version", lambda: (22, 22, 1))
    _patch(monkeypatch, "find_system_chrome", lambda: None)
    motivo = sra.lighthouse_unavailable()
    assert motivo is not None and "Chrome" in motivo


def test_lighthouse_version_assente_e_letta(tmp_path, monkeypatch):
    lh = _cli_finta(tmp_path)
    _patch(monkeypatch, "LIGHTHOUSE_DIR", str(lh))
    assert sra.lighthouse_version() is None
    (lh / "VERSIONE").write_text(
        "v13.4.1-mars.1 (lighthouse 13.4.1)\n")
    assert (sra.lighthouse_version()
            == "v13.4.1-mars.1 (lighthouse 13.4.1)")


# ---------------------- flag della CLI ----------------------------

def test_flag_lighthouse_default_e_scelte():
    args = sra.build_parser().parse_args(["https://x.it"])
    assert args.lighthouse == sra.LIGHTHOUSE_OFF
    assert args.lighthouse_pages == sra.DEFAULT_LIGHTHOUSE_PAGES
    assert args.lighthouse_device == sra.LIGHTHOUSE_DEVICE_MOBILE


def test_flag_lighthouse_scelte_invalide():
    with pytest.raises(SystemExit) as exc:
        sra.build_parser().parse_args(
            ["https://x.it", "--lighthouse", "forse"])
    assert exc.value.code == 2
    with pytest.raises(SystemExit) as exc:
        sra.build_parser().parse_args(
            ["https://x.it", "--lighthouse-device", "tablet"])
    assert exc.value.code == 2


def test_lighthouse_pages_fuori_intervallo(capsys):
    rc = sra.main(["https://x.invalid", "--lighthouse-pages", "99"])
    assert rc == 2
    assert "--lighthouse-pages" in capsys.readouterr().err
    rc = sra.main(["https://x.invalid", "--lighthouse-pages", "-1"])
    assert rc == 2


def test_lighthouse_always_richiede_requisiti(monkeypatch, capsys):
    _patch(monkeypatch, "lighthouse_unavailable",
                        lambda: "Node non trovato (finto)")
    rc = sra.main(["https://x.invalid", "--lighthouse", "always"])
    assert rc == 2
    err = capsys.readouterr().err
    assert "--lighthouse always" in err and "finto" in err


def test_lighthouse_auto_salto_dichiarato(site, tmp_path,
                                          monkeypatch, capsys):
    _patch(monkeypatch, "lighthouse_unavailable",
                        lambda: "Node non trovato (finto)")
    out = tmp_path / "referto.json"
    rc = sra.main([site, "--delay", "0", "--format", "json",
                   "--output", str(out), "--lighthouse", "auto"])
    assert rc in (0, 1)
    err = capsys.readouterr().err
    assert "Lighthouse" in err and "saltato" in err
    assert "finto" in err
    # Salto dichiarato anche nel referto, non solo nel log.
    dati = json.loads(out.read_text())
    assert dati["lighthouse"]["status"] == "skipped"
    assert "finto" in dati["lighthouse"]["reason"]


# ------------------------- runner ---------------------------------

_LHR_FINTO = json.dumps({
    "lighthouseVersion": "13.4.1",
    "categories": {"performance": {"score": 0.9},
                   "seo": {"score": 0.8}},
}).encode("utf-8")


class _ProcessoFinto:
    """Sostituto di subprocess.Popen per il runner Lighthouse."""

    def __init__(self, stdout=_LHR_FINTO, stderr=b"",
                 returncode=0, appeso=False):
        self.stdout_data = stdout
        self.stderr_data = stderr
        self.returncode = returncode
        self.appeso = appeso
        self.killed = False

    def communicate(self, timeout=None):
        if self.appeso and not self.killed:
            raise sra.subprocess.TimeoutExpired("node", timeout)
        return self.stdout_data, self.stderr_data

    def terminate(self):
        self.killed = True

    def kill(self):
        self.killed = True

    def wait(self, timeout=None):
        return self.returncode


def _requisiti_ok(monkeypatch):
    _patch(monkeypatch, "lighthouse_unavailable", lambda: None)
    monkeypatch.setattr(sra.shutil, "which",
                        lambda cmd: "/usr/bin/node")
    _patch(monkeypatch, "find_system_chrome",
                        lambda: "/usr/bin/google-chrome")


def _pagine():
    home = sra.Page(url="https://x.it/", status=200)
    home.internal_targets = [sra.norm_url("https://x.it/a"),
                             sra.norm_url("https://x.it/b")]
    a = sra.Page(url="https://x.it/a", status=200)
    a.internal_targets = [sra.norm_url("https://x.it/b")]
    b = sra.Page(url="https://x.it/b", status=200)
    rotta = sra.Page(url="https://x.it/404", status=404)
    return [home, a, b, rotta]


def test_selezione_home_piu_linkate():
    urls = sra.select_lighthouse_pages("https://x.it/", _pagine(), 1)
    # La home apre la lista; /b ha due link in ingresso e batte /a.
    assert urls == ["https://x.it/", "https://x.it/b"]
    tutti = sra.select_lighthouse_pages("https://x.it/", _pagine(), 9)
    assert tutti == ["https://x.it/", "https://x.it/b",
                     "https://x.it/a"]  # la 404 mai inclusa
    assert sra.select_lighthouse_pages("https://x.it/", [], 3) == []


def test_runner_off_restituisce_none(monkeypatch):
    assert sra.run_lighthouse("https://x.it/", _pagine(),
                              mode=sra.LIGHTHOUSE_OFF) is None


def test_runner_salto_dichiarato(monkeypatch, capsys):
    _patch(monkeypatch, "lighthouse_unavailable",
                        lambda: "requisiti assenti (finto)")
    data = sra.run_lighthouse("https://x.it/", _pagine(),
                              mode=sra.LIGHTHOUSE_AUTO, verbose=True)
    assert data["status"] == "skipped"
    assert "finto" in data["reason"]
    assert "saltato" in capsys.readouterr().err


def test_runner_ok_comando_e_ambiente(monkeypatch):
    chiamate = []

    def popen_finto(cmd, stdout=None, stderr=None, env=None):
        chiamate.append((cmd, env))
        return _ProcessoFinto()

    _requisiti_ok(monkeypatch)
    monkeypatch.setattr(sra.subprocess, "Popen", popen_finto)
    data = sra.run_lighthouse("https://x.it/", _pagine(),
                              mode=sra.LIGHTHOUSE_AUTO, n_pages=1,
                              delay=0)
    assert data["status"] == "ok"
    assert [r["url"] for r in data["results"]] \
        == ["https://x.it/", "https://x.it/b"]
    assert data["errors"] == []
    cmd, env = chiamate[0]
    assert cmd[0] == "/usr/bin/node" and cmd[1] == sra.LIGHTHOUSE_CLI
    assert "--output=json" in cmd and "--quiet" in cmd
    assert "--locale=it" in cmd  # referti canonici in italiano
    assert "--preset=desktop" not in cmd  # mobile e' il default
    assert env["CHROME_PATH"] == "/usr/bin/google-chrome"
    # Il runner allega i rilievi del parser: il LHR finto non ha
    # audit sotto soglia, quindi solo gli OK di categoria.
    assert all(f.severity == sra.SEV_OK for f in data["findings"])
    assert len(data["findings"]) == 2


def test_runner_preset_desktop(monkeypatch):
    chiamate = []

    def popen_finto(cmd, stdout=None, stderr=None, env=None):
        chiamate.append(cmd)
        return _ProcessoFinto()

    _requisiti_ok(monkeypatch)
    monkeypatch.setattr(sra.subprocess, "Popen", popen_finto)
    sra.run_lighthouse("https://x.it/", _pagine(),
                       mode=sra.LIGHTHOUSE_AUTO, n_pages=0, delay=0,
                       device=sra.LIGHTHOUSE_DEVICE_DESKTOP)
    assert "--preset=desktop" in chiamate[0]


def test_runner_timeout_ucciso_e_dichiarato(monkeypatch):
    processi = []

    def popen_finto(cmd, stdout=None, stderr=None, env=None):
        proc = _ProcessoFinto(appeso=True)
        processi.append(proc)
        return proc

    _requisiti_ok(monkeypatch)
    monkeypatch.setattr(sra.subprocess, "Popen", popen_finto)
    data = sra.run_lighthouse("https://x.it/", _pagine(),
                              mode=sra.LIGHTHOUSE_AUTO, n_pages=0,
                              delay=0, timeout_s=0)
    assert data["status"] == "ok" and data["results"] == []
    assert "tempo scaduto" in data["errors"][0]["error"]
    assert processi[0].killed


def test_runner_annullamento_uccide_il_processo(monkeypatch):
    processi = []

    def popen_finto(cmd, stdout=None, stderr=None, env=None):
        proc = _ProcessoFinto(appeso=True)
        processi.append(proc)
        return proc

    _requisiti_ok(monkeypatch)
    monkeypatch.setattr(sra.subprocess, "Popen", popen_finto)
    evento = threading.Event()
    evento.set()
    with pytest.raises(sra.AuditCancelled):
        sra.run_lighthouse("https://x.it/", _pagine(),
                           mode=sra.LIGHTHOUSE_AUTO, n_pages=0,
                           delay=0, stop_event=evento)
    assert processi[0].killed


def test_runner_errori_per_pagina_non_fermano(monkeypatch, capsys):
    esiti = iter([
        _ProcessoFinto(returncode=1, stdout=b"",
                       stderr=b"Errore: Chrome esploso"),
        _ProcessoFinto(stdout=b"non-json"),
        _ProcessoFinto(),
    ])
    _requisiti_ok(monkeypatch)
    monkeypatch.setattr(sra.subprocess, "Popen",
                        lambda *a, **kw: next(esiti))
    data = sra.run_lighthouse("https://x.it/", _pagine(),
                              mode=sra.LIGHTHOUSE_AUTO, n_pages=2,
                              delay=0, verbose=True)
    assert data["status"] == "ok"
    assert len(data["errors"]) == 2 and len(data["results"]) == 1
    assert "uscita 1" in data["errors"][0]["error"]
    assert "JSON" in data["errors"][1]["error"]
    err = capsys.readouterr().err
    assert "performance 90" in err  # sintesi della pagina riuscita


# ---------------------- parser LHR -> Finding ---------------------

def _dati_lhr(results, errors=()):
    return {"status": "ok", "mode": "auto", "device": "mobile",
            "results": list(results), "errors": list(errors)}


def _lhr_completo():
    return {
        "categories": {
            "performance": {
                "title": "Prestazioni", "score": 0.4,
                "auditRefs": [{"id": "lcp", "weight": 25},
                              {"id": "cls-info", "weight": 0},
                              {"id": "tbt-medio", "weight": 2},
                              {"id": "fcp-ok", "weight": 10}]},
            "seo": {
                "title": "SEO", "score": 1.0,
                "auditRefs": [{"id": "meta-ok", "weight": 1}]},
            "best-practices": {
                "title": "Best practice", "score": 0.7,
                "auditRefs": [{"id": "console-err", "weight": 5}]},
        },
        "audits": {
            "lcp": {"title": "LCP lento", "score": 0.2,
                    "description":
                        "Riduci il [LCP](https://web.dev/lcp).",
                    "displayValue": "5,0 s",
                    "details": {"items": [
                        {"url": "https://x.it/hero.jpg"},
                        {"node": {"selector": "img.hero"}}]}},
            "cls-info": {"title": "Informativo", "score": 0.0,
                         "description": "d"},
            "tbt-medio": {"title": "TBT medio", "score": 0.4,
                          "description": "d"},
            "fcp-ok": {"title": "FCP ok", "score": 0.95},
            "meta-ok": {"title": "Meta ok", "score": 1.0},
            "console-err": {"title": "Errori in console",
                            "score": 0, "description": "d"},
        },
    }


def test_parser_gravita_pilastri_e_chiavi():
    data = _dati_lhr([{"url": "https://x.it/",
                       "lhr": _lhr_completo()}])
    per_chiave = {f.key: f for f in sra.lighthouse_findings(data)}
    lcp = per_chiave["lh.performance.lcp"]
    assert lcp.severity == sra.SEV_CRITICAL   # 0.2 < 0.5, peso 25
    assert lcp.area == sra.AREA_LIGHTHOUSE
    assert lcp.pillar == sra.PILLAR_ACCESS
    assert lcp.title == "Lighthouse: LCP lento"
    assert "5,0 s" in lcp.detail and "img.hero" in lcp.detail
    assert "https://x.it/hero.jpg" in lcp.detail
    # description senza i link Markdown, come correzione
    assert "LCP" in lcp.fix and "web.dev" not in lcp.fix
    # peso 0 nel punteggio -> informativo anche se fallito
    assert per_chiave["lh.performance.cls-info"].severity \
        == sra.SEV_INFO
    # sotto 0.5 ma peso basso -> avvertenza
    assert per_chiave["lh.performance.tbt-medio"].severity \
        == sra.SEV_WARNING
    # 0.95 supera la soglia: nessun rilievo
    assert "lh.performance.fcp-ok" not in per_chiave
    console = per_chiave["lh.best-practices.console-err"]
    assert console.severity == sra.SEV_CRITICAL
    assert console.pillar == sra.PILLAR_SEC
    # SEO senza audit sotto soglia -> un solo OK, pilastro ranking
    ok_seo = per_chiave["lh.seo.ok"]
    assert ok_seo.severity == sra.SEV_OK
    assert ok_seo.pillar == sra.PILLAR_RANK
    assert "lh.performance.ok" not in per_chiave


def test_parser_aggrega_le_pagine():
    lhr_grave, lhr_lieve = _lhr_completo(), _lhr_completo()
    lhr_lieve["audits"]["lcp"]["score"] = 0.6
    data = _dati_lhr([{"url": "https://x.it/", "lhr": lhr_grave},
                      {"url": "https://x.it/a", "lhr": lhr_lieve}])
    trovati = [f for f in sra.lighthouse_findings(data)
               if f.key == "lh.performance.lcp"]
    assert len(trovati) == 1  # un rilievo per audit, non per pagina
    rilievo = trovati[0]
    assert "https://x.it/" in rilievo.detail
    assert "https://x.it/a" in rilievo.detail
    assert rilievo.params["score"] == 0.2  # punteggio peggiore


def test_parser_agentic_browsing_su_accessibility():
    lhr = {"categories": {
               "agentic-browsing": {
                   "title": "Agentic Browsing", "score": 0.5,
                   "auditRefs": [{"id": "llms-txt", "weight": 1}]}},
           "audits": {"llms-txt": {"title": "llms.txt",
                                   "score": 0.0,
                                   "description": "d"}}}
    data = _dati_lhr([{"url": "https://x.it/", "lhr": lhr}])
    rilievo = sra.lighthouse_findings(data)[0]
    assert rilievo.key == "lh.agentic-browsing.llms-txt"
    assert rilievo.pillar == sra.PILLAR_ACCESS
    assert rilievo.severity == sra.SEV_WARNING  # peso 1, non alto


def test_parser_errori_del_runner_dichiarati():
    data = _dati_lhr([], errors=[{"url": "https://x.it/",
                                  "error": "tempo scaduto (120 s)"}])
    rilievi = sra.lighthouse_findings(data)
    assert len(rilievi) == 1
    assert rilievi[0].severity == sra.SEV_INFO
    assert "1 pagina" in rilievi[0].title
    assert "tempo scaduto" in rilievi[0].detail


def test_parser_senza_dati():
    assert sra.lighthouse_findings(None) == []
    assert sra.lighthouse_findings(
        {"status": "skipped", "reason": "x"}) == []


# ------------------- deduplica e sesta area -----------------------

def _lh_finding(audit, key, severity=None):
    return sra.Finding(
        sra.AREA_LIGHTHOUSE, severity or sra.SEV_WARNING,
        "Lighthouse: rilievo %s" % audit, key=key,
        params={"audit": audit, "score": 0.0})


def test_merge_conferma_sul_rilievo_mars():
    mars = sra.Finding(sra.AREA_LEX, sra.SEV_WARNING,
                       "Meta description mancante", "Su 3 pagine.",
                       key="lex.desc.missing")
    lh = _lh_finding("meta-description", "lh.seo.meta-description")
    merged = sra.merge_lighthouse_findings(
        [mars], {"status": "ok", "findings": [lh]})
    assert len(merged) == 1  # niente doppione: MARS resta canonico
    assert "Conferma Lighthouse" in merged[0].detail
    assert "0/100" in merged[0].detail
    assert merged[0].params["lh_confirm"] == "meta-description"


def test_merge_divergenza_mars_ok_tiene_lighthouse():
    mars_ok = sra.Finding(sra.AREA_LEX, sra.SEV_OK,
                          "Description a posto", key="lex.desc.ok")
    lh = _lh_finding("meta-description", "lh.seo.meta-description")
    merged = sra.merge_lighthouse_findings(
        [mars_ok], {"status": "ok", "findings": [lh]})
    assert len(merged) == 2  # divergenza dichiarata: restano entrambi
    assert "Conferma" not in merged[0].detail


def test_merge_audit_fuori_tabella_resta():
    lh = _lh_finding("color-contrast",
                     "lh.accessibility.color-contrast")
    merged = sra.merge_lighthouse_findings(
        [], {"status": "ok", "findings": [lh]})
    assert merged == [lh]


def test_merge_senza_dati_lighthouse():
    mars = sra.Finding(sra.AREA_LEX, sra.SEV_WARNING, "x",
                       key="lex.desc.missing")
    assert sra.merge_lighthouse_findings([mars], None) == [mars]
    assert sra.merge_lighthouse_findings(
        [mars], {"status": "skipped"}) == [mars]


def test_sesta_area_media_delle_categorie():
    data = _dati_lhr([
        {"url": "https://x.it/", "lhr": {"categories": {
            "performance": {"score": 1.0},
            "seo": {"score": 0.5}}, "audits": {}}},
        {"url": "https://x.it/a", "lhr": {"categories": {
            "performance": {"score": 0.5},
            "seo": {"score": 0.5}}, "audits": {}}},
    ])
    # performance media 0.75, seo 0.5 -> (0.75 + 0.5) / 2 = 62.5
    assert sra.lighthouse_area_score(data) == 62.5
    assert sra.lighthouse_area_score(None) is None
    assert sra.lighthouse_area_score({"status": "skipped"}) is None


def test_overall_score_con_sesta_area_rinormalizzata():
    base = {sra.AREA_TECH: 50.0, sra.AREA_LEX: 50.0,
            sra.AREA_SEM: 50.0, sra.AREA_SD: 50.0,
            sra.AREA_RRF: 50.0}
    assert sra.overall_score(base) == 50.0  # senza Lighthouse
    con_lh = dict(base, **{sra.AREA_LIGHTHOUSE: 100.0})
    # pesi 6.5 + 1.0: (6.5*50 + 100) / 7.5 = 56.7
    assert sra.overall_score(con_lh) == 56.7


def test_e2e_sesta_area_nel_referto_json(site, tmp_path,
                                         monkeypatch):
    _requisiti_ok(monkeypatch)
    lhr_bytes = json.dumps(_lhr_completo()).encode("utf-8")
    monkeypatch.setattr(
        sra.subprocess, "Popen",
        lambda *a, **kw: _ProcessoFinto(stdout=lhr_bytes))
    out = tmp_path / "r.json"
    rc = sra.main([site, "--quiet", "--delay", "0",
                   "--lighthouse", "auto", "--format", "json",
                   "--output", str(out)])
    assert rc in (0, 1)
    dati = json.loads(out.read_text())
    # sesta area nei punteggi: (0.4 + 1.0 + 0.7) / 3 -> 70.0
    assert dati["scores"][sra.AREA_LIGHTHOUSE] == 70.0
    assert "overall" in dati["scores"]
    per_chiave = {f["key"]: f for f in dati["findings"] if f["key"]}
    assert "lh.performance.lcp" in per_chiave
    assert per_chiave["lh.performance.lcp"]["area"] \
        == sra.AREA_LIGHTHOUSE
    assert per_chiave["lh.performance.lcp"]["pillar"] \
        == sra.PILLAR_ACCESS
    # Blocco additivo "lighthouse" nel JSON (schema invariato).
    blocco = dati["lighthouse"]
    assert blocco["status"] == "ok"
    assert blocco["device"] == "mobile"
    assert {c["id"] for c in blocco["categories"]} \
        == {"performance", "seo", "best-practices"}


# ------------------ dichiarazione nei referti ---------------------

_RIASSUNTO_OK = {
    "status": "ok", "mode": "auto", "device": "mobile",
    "fork": "v13.4.1-mars.1", "pages": ["https://x.it/"],
    "errors": [],
    "categories": [{"id": "performance", "title": "Prestazioni",
                    "score": 97}]}
_RIASSUNTO_SALTO = {
    "status": "skipped", "mode": "auto", "device": "mobile",
    "reason": "Node assente (finto)"}


def test_lighthouse_report_data(monkeypatch):
    _patch(
        monkeypatch, "lighthouse_version",
        lambda: "v13.4.1-mars.1 (lighthouse 13.4.1)")
    data = _dati_lhr([
        {"url": "https://x.it/", "lhr": {"categories": {
            "performance": {"title": "Prestazioni", "score": 1.0}},
            "audits": {}}},
        {"url": "https://x.it/a", "lhr": {"categories": {
            "performance": {"title": "Prestazioni", "score": 0.5}},
            "audits": {}}}])
    blocco = sra.lighthouse_report_data(data)
    assert blocco["status"] == "ok"
    assert blocco["pages"] == ["https://x.it/", "https://x.it/a"]
    assert blocco["fork"].startswith("v13.4.1-mars.1")
    assert blocco["categories"] == [
        {"id": "performance", "title": "Prestazioni", "score": 75}]
    salto = sra.lighthouse_report_data(_RIASSUNTO_SALTO | {})
    assert salto["status"] == "skipped"
    assert salto["reason"] == "Node assente (finto)"
    assert sra.lighthouse_report_data(None) is None


def test_report_data_metriche_cwv():
    def lhr(lcp, cls_value):
        return {"categories": {}, "audits": {
            "largest-contentful-paint": {
                "numericValue": lcp,
                "displayValue": "%.1f s" % (lcp / 1000)},
            "cumulative-layout-shift": {
                "numericValue": cls_value,
                "displayValue": str(cls_value)},
        }}

    data = _dati_lhr([
        {"url": "https://x.it/", "lhr": lhr(2000.0, 0.05)},
        {"url": "https://x.it/a", "lhr": lhr(3000.0, 0.3)},
    ])
    per_id = {m["id"]: m
              for m in sra.lighthouse_report_data(data)["metrics"]}
    # vale la pagina peggiore; soglie ufficiali 2500/4000 e 0.1/0.25
    lcp = per_id["largest-contentful-paint"]
    assert lcp["value"] == 3000.0
    assert lcp["verdict"] == "da migliorare"
    assert lcp["display"] == "3.0 s"
    cls_metrica = per_id["cumulative-layout-shift"]
    assert cls_metrica["verdict"] == "scarso"
    # metriche assenti dal LHR: nessuna voce, mai valori inventati
    assert "total-blocking-time" not in per_id


def test_referti_dichiarano_lighthouse():
    txt = sra.render_text("https://x.it/", [], [], {}, [],
                          "char-tfidf",
                          lighthouse=_RIASSUNTO_OK)
    assert "AUDIT LIGHTHOUSE" in txt
    assert "Prestazioni 97/100" in txt
    assert "v13.4.1-mars.1" in txt
    txt_salto = sra.render_text("https://x.it/", [], [], {}, [],
                                "char-tfidf",
                                lighthouse=_RIASSUNTO_SALTO)
    assert "AUDIT LIGHTHOUSE" in txt_salto
    assert "Node assente (finto)" in txt_salto
    html = sra.render_html("https://x.it/", [], [], {}, [],
                           "char-tfidf",
                           lighthouse=_RIASSUNTO_OK)
    assert "Audit Lighthouse" in html and "Prestazioni" in html
    assert "v13.4.1-mars.1" in html
    html_salto = sra.render_html("https://x.it/", [], [], {}, [],
                                 "char-tfidf",
                                 lighthouse=_RIASSUNTO_SALTO)
    assert "Node assente (finto)" in html_salto
    md = sra.render_markdown("https://x.it/", [], [], {}, [],
                             "char-tfidf",
                             lighthouse=_RIASSUNTO_OK)
    assert "## Audit Lighthouse" in md and "**97/100**" in md
    # Senza Lighthouse i referti non ne parlano.
    txt_off = sra.render_text("https://x.it/", [], [], {}, [],
                              "char-tfidf", lighthouse=None)
    assert "LIGHTHOUSE" not in txt_off.replace(
        "Performance (Lighthouse)", "")


# ---------------- i18n EN dai locale del fork ---------------------

_CATALOGO_EN = {
    "audit.js | failureTitle": "Document has no meta description",
    "audit.js | description":
        "Write a [meta description](https://web.dev/meta).",
    "config.js | seoCategoryTitle": "SEO",
}


def _lhr_i18n(score=0.0):
    return {
        "categories": {"seo": {
            "title": "SEO (it)", "score": 0.5,
            "auditRefs": [{"id": "meta-description",
                           "weight": 1}]}},
        "audits": {"meta-description": {
            "title": "Il documento non ha una meta descrizione",
            "score": score,
            "description":
                "Scrivi la [meta](https://web.dev/meta).",
        }},
        "i18n": {"icuMessagePaths": {
            "audit.js | failureTitle":
                ["audits[meta-description].title"],
            "audit.js | description":
                ["audits[meta-description].description"],
            "config.js | seoCategoryTitle":
                ["categories.seo.title"],
        }},
    }


def test_i18n_en_dai_locale_del_fork(monkeypatch):
    _patch(monkeypatch, "_LH_EN_CATALOG", dict(_CATALOGO_EN))
    data = _dati_lhr([{"url": "https://x.it/", "lhr": _lhr_i18n()}])
    rilievo = sra.lighthouse_findings(data)[0]
    assert rilievo.params["title_en"] \
        == "Document has no meta description"
    testi = sra.finding_texts(rilievo, "en")
    assert testi["title"] \
        == "Lighthouse: Document has no meta description"
    assert testi["fix"] == "Write a meta description."
    assert "Pages: https://x.it/" in testi["detail"]
    # Il canonico italiano resta intatto (storico e ancore).
    assert sra.finding_texts(rilievo, "it")["title"] \
        == "Lighthouse: Il documento non ha una meta descrizione"


def test_i18n_en_fallback_italiano(monkeypatch):
    _patch(monkeypatch, "_LH_EN_CATALOG", {})
    data = _dati_lhr([{"url": "https://x.it/", "lhr": _lhr_i18n()}])
    rilievo = sra.lighthouse_findings(data)[0]
    assert rilievo.params["title_en"] == ""
    testi = sra.finding_texts(rilievo, "en")
    assert "meta descrizione" in testi["title"]  # fallback dichiarato


def test_i18n_en_placeholder_icu_scartati(monkeypatch):
    catalogo = dict(_CATALOGO_EN)
    catalogo["audit.js | failureTitle"] = "Wasted {timeInMs} ms"
    _patch(monkeypatch, "_LH_EN_CATALOG", catalogo)
    data = _dati_lhr([{"url": "https://x.it/", "lhr": _lhr_i18n()}])
    rilievo = sra.lighthouse_findings(data)[0]
    assert rilievo.params["title_en"] == ""  # niente ICU parziale


def test_i18n_en_ok_e_errori(monkeypatch):
    _patch(monkeypatch, "_LH_EN_CATALOG", dict(_CATALOGO_EN))
    data = _dati_lhr([{"url": "https://x.it/",
                       "lhr": _lhr_i18n(score=1.0)}],
                     errors=[{"url": "https://x.it/a",
                              "error": "tempo scaduto"}])
    per_chiave = {f.key: f for f in sra.lighthouse_findings(data)}
    ok = sra.finding_texts(per_chiave["lh.seo.ok"], "en")
    assert ok["title"] == "Lighthouse SEO: no findings"
    assert ok["detail"] == "Score 50/100 on 1 page examined."
    errori = sra.finding_texts(per_chiave["lh.run.errors"], "en")
    assert errori["title"] \
        == "Lighthouse did not complete on 1 page"


def test_parser_soglie_esatte_dei_bucket():
    lhr = {"categories": {"performance": {
               "title": "P", "score": 0.5,
               "auditRefs": [{"id": "a-mezzo", "weight": 25},
                             {"id": "a-novanta", "weight": 25},
                             {"id": "a-quasi", "weight": 25}]}},
           "audits": {
               "a-mezzo": {"title": "t", "score": 0.5},
               "a-novanta": {"title": "t", "score": 0.9},
               "a-quasi": {"title": "t", "score": 0.89}}}
    data = _dati_lhr([{"url": "https://x.it/", "lhr": lhr}])
    per_chiave = {f.key: f for f in sra.lighthouse_findings(data)}
    # 0.5 esatto non e' critico: la soglia e' "sotto 0.5".
    assert per_chiave["lh.performance.a-mezzo"].severity \
        == sra.SEV_WARNING
    # 0.9 esatto passa (bucket ufficiale): nessun rilievo.
    assert "lh.performance.a-novanta" not in per_chiave
    assert per_chiave["lh.performance.a-quasi"].severity \
        == sra.SEV_WARNING


def test_coerenza_dei_cinque_renderer_su_lighthouse():
    lh_data = _dati_lhr([{"url": "https://x.it/",
                          "lhr": _lhr_completo()}])
    lh_data["findings"] = sra.lighthouse_findings(lh_data)
    findings = sra.merge_lighthouse_findings([], lh_data)
    scores = {sra.AREA_TECH: 50.0,
              sra.AREA_LIGHTHOUSE:
                  sra.lighthouse_area_score(lh_data)}
    blocco = sra.lighthouse_report_data(lh_data)

    testo = sra.render_text("https://x.it/", [], findings, scores,
                            [], "char-tfidf", lighthouse=blocco)
    html_out = sra.render_html("https://x.it/", [], findings,
                               scores, [], "char-tfidf",
                               lighthouse=blocco)
    md = sra.render_markdown("https://x.it/", [], findings, scores,
                             [], "char-tfidf", lighthouse=blocco)
    csv_out = sra.render_csv("https://x.it/", [], findings, scores,
                             [], "char-tfidf", lighthouse=blocco)
    dati = json.loads(sra.render_json(
        "https://x.it/", [], findings, scores, [], "char-tfidf",
        lighthouse=blocco))

    # Lo stesso rilievo Lighthouse in tutti e cinque i formati.
    for referto in (testo, html_out, md, csv_out):
        assert "LCP lento" in referto
    per_chiave = {f["key"]: f for f in dati["findings"]
                  if f["key"]}
    assert "lh.performance.lcp" in per_chiave
    # La sesta area in tutti i formati.
    assert sra.AREA_LIGHTHOUSE.upper() in testo
    assert sra.AREA_LIGHTHOUSE in md and sra.AREA_LIGHTHOUSE \
        in csv_out
    assert dati["scores"][sra.AREA_LIGHTHOUSE] \
        == scores[sra.AREA_LIGHTHOUSE]
    # La sezione di sintesi nei formati di prosa, il blocco nel JSON.
    assert "AUDIT LIGHTHOUSE" in testo
    assert "Audit Lighthouse" in html_out
    assert "## Audit Lighthouse" in md
    assert dati["lighthouse"]["status"] == "ok"
    # Il salto dichiarato e' coerente in tutti i formati di prosa.
    salto = {"status": "skipped", "mode": "auto",
             "device": "mobile", "reason": "Node assente (finto)"}
    for render in (sra.render_text, sra.render_markdown,
                   sra.render_html):
        out = render("https://x.it/", [], [], {}, [],
                     "char-tfidf", lighthouse=salto)
        assert "Node assente (finto)" in out


# --------------------- storico e delta ----------------------------

def test_history_payload_con_lighthouse():
    riga = sra.history_payload("https://x.it/", [], {},
                               lighthouse=_RIASSUNTO_OK)
    assert riga["lighthouse"] == [
        {"id": "performance", "title": "Prestazioni", "score": 97}]
    senza = sra.history_payload("https://x.it/", [], {})
    assert "lighthouse" not in senza
    salto = sra.history_payload("https://x.it/", [], {},
                                lighthouse=_RIASSUNTO_SALTO)
    assert "lighthouse" not in salto


def test_delta_categorie_lighthouse():
    # Prima esecuzione: referto JSON completo (blocco con
    # "categories"); seconda: riga compatta dello storico (lista).
    prima = {"site": "https://x.it/", "generated_at": "g",
             "scores": {"Tecnica": 50.0}, "findings": [],
             "lighthouse": {"status": "ok", "categories": [
                 {"id": "performance", "title": "Prestazioni",
                  "score": 90},
                 {"id": "seo", "title": "SEO", "score": 70},
                 {"id": "best-practices",
                  "title": "Best practice", "score": 80}]}}
    dopo = {"site": "https://x.it/", "generated_at": "g2",
            "scores": {"Tecnica": 60.0}, "findings": [],
            "lighthouse": [
                {"id": "performance", "title": "Prestazioni",
                 "score": 95},
                {"id": "seo", "title": "SEO", "score": 65}]}
    delta = sra.compute_delta(prima, dopo, 1000.0)
    per_id = {c["id"]: c for c in delta["lighthouse"]}
    assert per_id["performance"]["delta"] == 5.0
    assert per_id["performance"]["title"] == "Prestazioni"
    assert per_id["seo"]["delta"] == -5.0
    # Categoria assente da una delle due esecuzioni: nessun delta.
    assert "best-practices" not in per_id
    # E il delta dei punteggi d'area resta quello di sempre.
    assert delta["scores"]["Tecnica"] == 10.0
    vuoto = sra.compute_delta({"scores": {}, "findings": []},
                              {"scores": {}, "findings": []}, 0.0)
    assert vuoto["lighthouse"] == []


def test_ancore_stabili_per_rilievi_lighthouse():
    # I conteggi nei titoli non cambiano l'ancora (#r-... stabile).
    a1 = sra._finding_anchor(
        sra.AREA_LIGHTHOUSE,
        "Lighthouse non completato su 2 pagine", {})
    a2 = sra._finding_anchor(
        sra.AREA_LIGHTHOUSE,
        "Lighthouse non completato su 5 pagine", {})
    assert a1 == a2 and a1.startswith("r-")


# ---------------- integrazione con Lighthouse vero ----------------

LIGHTHOUSE_DISPONIBILE = sra.lighthouse_unavailable() is None


@pytest.mark.skipif(not LIGHTHOUSE_DISPONIBILE,
                    reason="fork Lighthouse, Node o Chrome assenti")
def test_integrazione_lighthouse_reale(site):
    """Il runner vero (processo Node, fork installato) contro il
    sito fixture locale: nessuna rete oltre 127.0.0.1. Pattern del
    test di rendering con browser reale; ~20-30 s per la sola home.
    """
    pages = [sra.Page(url=site, status=200)]
    data = sra.run_lighthouse(site, pages,
                              mode=sra.LIGHTHOUSE_AUTO,
                              n_pages=0, delay=0, verbose=False)
    assert data["status"] == "ok"
    assert data["errors"] == []
    assert len(data["results"]) == 1
    lhr = data["results"][0]["lhr"]
    assert str(lhr.get("lighthouseVersion", "")).startswith("13.")
    categorie = lhr.get("categories") or {}
    assert "performance" in categorie and "seo" in categorie
    # Dal LHR reale escono rilievi (o OK di categoria), punteggi
    # e metriche CWV: l'intera catena parser -> blocco referti.
    assert data["findings"]
    blocco = sra.lighthouse_report_data(data)
    assert blocco["categories"]
    assert blocco["metrics"]
    assert sra.lighthouse_area_score(data) is not None
