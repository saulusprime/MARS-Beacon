/* Logica della GUI di seo_rrf_audit.py.
   Vanilla JS, nessuna dipendenza oltre al bundle Bootstrap Italia.
   Tutto il contenuto dinamico è inserito con textContent: i dati
   provengono dal sito auditato e non vanno mai interpretati come HTML. */

"use strict";

(function () {
  const AREAS = [
    "Tecnica",
    "Lessicale (BM25)",
    "Semantica (vettoriale)",
    "Dati strutturati",
    "Simulazione RRF",
  ];

  const SEVERITIES = {
    critical: { label: "Critico", cls: "badge-sev-critical", mark: "✕" },
    warning: { label: "Avvertenza", cls: "badge-sev-warning", mark: "!" },
    info: { label: "Informazione", cls: "badge-sev-info", mark: "i" },
    ok: { label: "OK", cls: "badge-sev-ok", mark: "✓" },
  };
  const SEV_ORDER = { critical: 0, warning: 1, info: 2, ok: 3 };

  const NUMERIC_FIELDS = [
    ["f-max-pages", "e-max-pages"],
    ["f-delay", "e-delay"],
    ["f-max-body", "e-max-body"],
    ["f-retries", "e-retries"],
    ["f-rrf-k", "e-rrf-k"],
  ];

  const el = (id) => document.getElementById(id);

  /* Apre o chiude una sezione collassabile passando dal suo bottone,
     cosi' Bootstrap mantiene coerenti classi e aria-expanded. */
  function setOpen(collapseId, open) {
    const body = el(collapseId);
    const toggle = document.querySelector(
      '[data-bs-target="#' + collapseId + '"]');
    if (!body || !toggle) {
      return;
    }
    if (body.classList.contains("show") !== open) {
      toggle.click();
    }
  }

  let running = false;
  let lastPhase = "";

  el("audit-form").addEventListener("submit", onSubmit);
  loadEnv();
  restoreResults();

  /* Se un audit e' gia' concluso (es. pagina ricaricata), i
     risultati vengono ripristinati senza rilanciare nulla. */
  function restoreResults() {
    fetch("api/status")
      .then((r) => r.json())
      .then((snap) => {
        if (!running && snap.state === "done" &&
            snap.summary && snap.summary.site) {
          renderLog(snap.log || []);
          el("progress-anim").hidden = true;
          el("progress-section").hidden = false;
          setOpen("sec-config", false);
          showResults(snap);
        }
      })
      .catch(() => { /* nessun audit precedente */ });
  }

  /* ---------------- ambiente ---------------- */

  function loadEnv() {
    fetch("api/env")
      .then((r) => r.json())
      .then((env) => {
        if (env.suggested_max_body_mb && env.available_ram_mb) {
          el("h-max-body").textContent =
            "Tetto per ogni pagina scaricata (predefinito " +
            env.default_max_body_mb + " MB). Su questa macchina si " +
            "consiglia di non superare " + env.suggested_max_body_mb +
            " MB: la RAM disponibile ora è di circa " +
            Math.round(env.available_ram_mb) + " MB.";
        }
        if (!env.embeddings_available) {
          el("h-embeddings").textContent =
            "Libreria sentence-transformers non installata: il " +
            "recupero vettoriale userà il proxy char-TFIDF " +
            "(dichiarato nel referto), anche indicando un modello.";
        } else {
          el("h-embeddings").textContent =
            "sentence-transformers rilevato: se lasci vuoto viene " +
            "usato il modello predefinito " +
            env.default_embeddings_model + ". Scrivi «none» " +
            "per forzare il proxy char-TFIDF.";
        }
        el("footer-info").textContent +=
          " — seo_rrf_audit.py " + env.tool_version +
          " · interfaccia " + env.gui_version;
      })
      .catch(() => { /* la GUI resta usabile senza /api/env */ });
  }

  /* ---------------- invio del form ---------------- */

  function onSubmit(event) {
    event.preventDefault();
    if (running) {
      return;
    }
    clearErrors();
    const config = collectConfig();
    if (config) {
      startAudit(config);
    }
  }

  function clearErrors() {
    const summary = el("form-error");
    summary.hidden = true;
    summary.textContent = "";
    el("audit-error").hidden = true;
    document.querySelectorAll(".is-invalid").forEach((input) => {
      input.classList.remove("is-invalid");
      input.removeAttribute("aria-invalid");
    });
    document.querySelectorAll(".invalid-feedback").forEach((box) => {
      box.textContent = "";
      box.classList.remove("d-block");
    });
  }

  function markInvalid(input, feedbackId, message) {
    input.classList.add("is-invalid");
    input.setAttribute("aria-invalid", "true");
    const box = el(feedbackId);
    box.textContent = message;
    box.classList.add("d-block");
  }

  function collectConfig() {
    let firstInvalid = null;

    const url = el("f-url");
    if (!url.value.trim()) {
      markInvalid(url, "e-url", "Inserisci l'URL del sito da auditare.");
      firstInvalid = url;
    }

    const competitors = el("f-competitors");
    const compLines = competitors.value
      .split("\n").map((c) => c.trim()).filter(Boolean);
    if (compLines.length > 3) {
      markInvalid(competitors, "e-competitors",
        "Indica al massimo 3 siti concorrenti.");
      firstInvalid = firstInvalid || competitors;
    }

    NUMERIC_FIELDS.forEach(([inputId, feedbackId]) => {
      const input = el(inputId);
      if (!input.checkValidity()) {
        markInvalid(input, feedbackId, input.validationMessage);
        firstInvalid = firstInvalid || input;
      }
    });

    if (firstInvalid) {
      const summary = el("form-error");
      summary.textContent =
        "Il modulo contiene errori: correggi i campi evidenziati.";
      summary.hidden = false;
      firstInvalid.focus();
      return null;
    }

    return {
      url: url.value.trim(),
      max_pages: el("f-max-pages").valueAsNumber,
      delay: el("f-delay").valueAsNumber,
      max_body: el("f-max-body").valueAsNumber,
      retries: el("f-retries").valueAsNumber,
      rrf_k: el("f-rrf-k").valueAsNumber,
      queries: el("f-queries").value,
      embeddings: el("f-embeddings").value.trim(),
      respect_robots: el("f-respect-robots").checked,
      competitors: el("f-competitors").value,
    };
  }

  /* ---------------- ciclo dell'audit ---------------- */

  function startAudit(config) {
    fetch("api/audit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(config),
    })
      .then((r) => r.json().then((data) => ({ status: r.status, data })))
      .then(({ status, data }) => {
        if (status !== 202) {
          showFormError(data.error || "Avvio non riuscito.");
          return;
        }
        running = true;
        lastPhase = "";
        setSubmitState(true);
        el("results-section").hidden = true;
        setOpen("sec-results", false);
        el("audit-error").hidden = true;
        el("log").textContent = "";
        el("announcer").textContent = "Audit avviato.";
        el("progress-anim").hidden = false;
        el("progress-section").hidden = false;
        setOpen("sec-config", false);
        setOpen("sec-progress", true);
        el("progress-toggle").focus();
        window.setTimeout(poll, 800);
      })
      .catch(() => showFormError(
        "Impossibile contattare il server locale: verifica che " +
        "seo_rrf_gui.py sia in esecuzione."));
  }

  function showFormError(message) {
    const summary = el("form-error");
    summary.textContent = message;
    summary.hidden = false;
    summary.focus();
  }

  function setSubmitState(busy) {
    const button = el("submit-btn");
    button.disabled = busy;
    button.textContent = busy ? "Audit in corso…" : "Avvia audit";
  }

  function poll() {
    fetch("api/status")
      .then((r) => r.json())
      .then((snap) => {
        renderLog(snap.log || []);
        if (snap.state === "done") {
          finish(snap);
        } else if (snap.state === "error") {
          fail(snap.error || "Errore sconosciuto durante l'audit.");
        } else {
          window.setTimeout(poll, 1000);
        }
      })
      .catch(() => fail(
        "Connessione al server locale persa durante l'audit."));
  }

  function renderLog(lines) {
    el("log").textContent = lines.join("\n");
    const box = document.querySelector(".audit-log");
    box.scrollTop = box.scrollHeight;

    for (let i = lines.length - 1; i >= 0; i -= 1) {
      if (/^\[\d+\/\d+\]/.test(lines[i])) {
        if (lines[i] !== lastPhase) {
          lastPhase = lines[i];
          el("announcer").textContent = "Fase " + lines[i];
        }
        break;
      }
    }
  }

  function fail(message) {
    running = false;
    setSubmitState(false);
    el("progress-anim").hidden = true;
    el("announcer").textContent = "Audit interrotto da un errore.";
    const box = el("audit-error");
    box.textContent = "L'audit non è andato a buon fine. " + message;
    box.hidden = false;
    box.focus();
  }

  function finish(snap) {
    running = false;
    setSubmitState(false);
    el("progress-anim").hidden = true;
    el("announcer").textContent = "Audit completato: risultati pronti.";
    setOpen("sec-progress", false);
    showResults(snap);
    el("results-toggle").focus();
  }

  function showResults(snap) {
    renderMeta(snap.summary);
    renderHero(snap.summary);
    renderScores(snap.summary);
    renderFindings(snap.findings || []);
    renderRrf(snap.rrf || []);
    renderCompetitive(snap.competitive);

    el("results-section").hidden = false;
    setOpen("sec-results", true);
  }

  /* ---------------- rendering dei risultati ---------------- */

  function renderMeta(summary) {
    const parts = [
      "Sito: " + summary.site,
      "pagine analizzabili: " + summary.pages_ok + " su " +
        summary.pages_total,
      "chunk indicizzati: " + summary.chunks,
      "recuperatore vettoriale: " + summary.vector_retriever,
      "k = " + summary.rrf_k,
      "criticità: " + summary.critical,
      "avvertenze: " + summary.warning,
    ];
    el("results-meta").textContent = parts.join(" · ");
  }

  function scoreColor(value) {
    if (value >= 70) { return "#1c6b45"; }
    if (value >= 40) { return "#a8480f"; }
    return "#9e1b1b";
  }

  function scoreVerdict(value) {
    if (value >= 70) { return { label: "Buono", mark: "✓" }; }
    if (value >= 40) { return { label: "Da migliorare", mark: "!" }; }
    return { label: "Critico", mark: "✕" };
  }

  const SVG_NS = "http://www.w3.org/2000/svg";

  function svgNode(name, attrs) {
    const node = document.createElementNS(SVG_NS, name);
    Object.keys(attrs || {}).forEach((key) => {
      node.setAttribute(key, attrs[key]);
    });
    return node;
  }

  /* Anello del punteggio complessivo (r=52, C=2*pi*r). */
  function scoreRing(value) {
    const circ = 326.73;
    const box = document.createElement("div");
    box.className = "hero-ring";
    box.setAttribute("role", "img");
    box.setAttribute("aria-label",
      "Punteggio complessivo " + Math.round(value) + " su 100: " +
      scoreVerdict(value).label);

    const svg = svgNode("svg", {
      viewBox: "0 0 120 120", width: "124", height: "124",
      "aria-hidden": "true",
    });
    svg.appendChild(svgNode("circle", {
      class: "ring-track", cx: 60, cy: 60, r: 52,
    }));
    svg.appendChild(svgNode("circle", {
      class: "ring-fill", cx: 60, cy: 60, r: 52,
      stroke: scoreColor(value),
      "stroke-dasharray":
        (circ * value / 100).toFixed(2) + " " + circ,
      transform: "rotate(-90 60 60)",
    }));
    box.appendChild(svg);

    const num = document.createElement("div");
    num.className = "ring-num";
    num.setAttribute("aria-hidden", "true");
    const big = document.createElement("b");
    big.textContent = Math.round(value);
    const small = document.createElement("small");
    small.textContent = "su 100";
    num.appendChild(big);
    num.appendChild(small);
    box.appendChild(num);
    return box;
  }

  /* Donut dello stato pagine (r=44), con respiro fra i segmenti. */
  function pagesDonut(summary) {
    const total = summary.pages_total || 0;
    const segments = [
      [summary.pages_clean || 0, "#1c6b45", "senza rilievi"],
      [summary.pages_flagged || 0, "#a8480f", "con rilievi"],
      [summary.pages_error || 0, "#9e1b1b", "in errore"],
    ];
    const circ = 276.46;
    const box = document.createElement("div");
    box.className = "hero-donut";
    box.setAttribute("role", "img");
    box.setAttribute("aria-label",
      total + " pagine: " + segments
        .map(([count, , label]) => count + " " + label).join(", "));

    const wrap = document.createElement("div");
    wrap.className = "donut-wrap";
    const svg = svgNode("svg", {
      viewBox: "0 0 120 120", width: "112", height: "112",
      "aria-hidden": "true",
    });
    const group = svgNode("g", { transform: "rotate(-90 60 60)" });
    let offset = 0;
    segments.forEach(([count, color]) => {
      if (!count) { return; }
      const span = circ * count / total;
      const dash = span > 3 ? Math.max(span - 2, 1) : span;
      group.appendChild(svgNode("circle", {
        cx: 60, cy: 60, r: 44, fill: "none",
        stroke: color, "stroke-width": 14,
        "stroke-dasharray": dash.toFixed(2) + " " +
          (circ - dash).toFixed(2),
        "stroke-dashoffset": (-offset).toFixed(2),
      }));
      offset += span;
    });
    svg.appendChild(group);
    wrap.appendChild(svg);

    const num = document.createElement("div");
    num.className = "donut-num";
    num.setAttribute("aria-hidden", "true");
    const big = document.createElement("b");
    big.textContent = total;
    const small = document.createElement("small");
    small.textContent = total === 1 ? "pagina" : "pagine";
    num.appendChild(big);
    num.appendChild(small);
    wrap.appendChild(num);
    box.appendChild(wrap);

    const legend = document.createElement("ul");
    legend.className = "donut-legend";
    legend.setAttribute("aria-hidden", "true");
    segments.forEach(([count, color, label]) => {
      const li = document.createElement("li");
      const dot = document.createElement("span");
      dot.className = "sev-dot";
      dot.style.backgroundColor = color;
      li.appendChild(dot);
      li.appendChild(
        document.createTextNode(count + " " + label));
      legend.appendChild(li);
    });
    box.appendChild(legend);
    return box;
  }

  function severityTile(label, count, color) {
    const tile = document.createElement("div");
    tile.className = "sev-tile";
    const head = document.createElement("span");
    head.className = "sev-tile-label";
    const dot = document.createElement("span");
    dot.className = "sev-dot";
    dot.style.backgroundColor = color;
    head.appendChild(dot);
    head.appendChild(document.createTextNode(label));
    tile.appendChild(head);
    const num = document.createElement("b");
    num.textContent = count;
    tile.appendChild(num);
    return tile;
  }

  function renderHero(summary) {
    const hero = el("hero");
    hero.textContent = "";
    hero.appendChild(scoreRing(summary.overall));

    const side = document.createElement("div");
    side.className = "hero-side";

    const verdict = document.createElement("p");
    verdict.className = "hero-verdict";
    const info = scoreVerdict(summary.overall);
    const ico = document.createElement("span");
    ico.className = "verdict-ico";
    ico.style.backgroundColor = scoreColor(summary.overall);
    ico.setAttribute("aria-hidden", "true");
    ico.textContent = info.mark;
    verdict.appendChild(ico);
    verdict.appendChild(document.createTextNode(info.label));
    side.appendChild(verdict);

    const soglie = document.createElement("p");
    soglie.className = "hero-soglie";
    soglie.textContent =
      "buono ≥ 70 · da migliorare 40–69 · critico < 40";
    side.appendChild(soglie);

    const tiles = document.createElement("div");
    tiles.className = "sev-tiles";
    tiles.appendChild(
      severityTile("Critici", summary.critical || 0, "#9e1b1b"));
    tiles.appendChild(
      severityTile("Avvertenze", summary.warning || 0, "#a8480f"));
    tiles.appendChild(
      severityTile("Informazioni", summary.info || 0, "#0f4a5b"));
    side.appendChild(tiles);
    hero.appendChild(side);

    if (summary.pages_total) {
      hero.appendChild(pagesDonut(summary));
    }
  }

  function renderScores(summary) {
    const wrap = el("scores");
    wrap.textContent = "";
    const rows = AREAS.map((area) => [area, summary.scores[area]]);
    rows.push(["Punteggio complessivo", summary.overall]);

    rows.forEach(([label, value], index) => {
      const isArea = index < AREAS.length;
      const row = document.createElement("div");
      row.className = "score-row" +
        (index === rows.length - 1 ? " score-overall" : "");

      const name = document.createElement(isArea ? "button" : "span");
      name.className = "score-label";
      name.textContent = label;
      if (isArea) {
        name.type = "button";
        name.classList.add("score-link");
        name.setAttribute("aria-label",
          label + ": apri i rilievi di quest'area");
        name.addEventListener("click", () => openArea(index));
      }
      row.appendChild(name);

      const bar = document.createElement("div");
      bar.className = "progress";
      bar.setAttribute("aria-hidden", "true");
      const fill = document.createElement("div");
      fill.className = "progress-bar";
      if (value !== null && value !== undefined) {
        fill.style.width = value + "%";
        fill.style.backgroundColor = scoreColor(value);
      }
      bar.appendChild(fill);
      row.appendChild(bar);

      const num = document.createElement("span");
      num.className = "score-value";
      num.textContent = (value === null || value === undefined)
        ? "n/d" : Math.round(value) + "/100";
      row.appendChild(num);

      wrap.appendChild(row);
    });
  }

  function openArea(index) {
    const body = document.getElementById("acc-c-" + index);
    if (!body) { return; }
    const toggle = document.querySelector(
      "#acc-h-" + index + " button");
    if (toggle && toggle.classList.contains("collapsed")) {
      toggle.click();
    }
    const reduced = window.matchMedia(
      "(prefers-reduced-motion: reduce)").matches;
    body.closest(".accordion-item").scrollIntoView({
      behavior: reduced ? "auto" : "smooth", block: "start",
    });
    if (toggle) { toggle.focus({ preventScroll: true }); }
  }

  function severityBadge(severity) {
    const info = SEVERITIES[severity] || SEVERITIES.info;
    const badge = document.createElement("span");
    badge.className = "badge badge-sev " + info.cls;
    const mark = document.createElement("span");
    mark.setAttribute("aria-hidden", "true");
    mark.textContent = info.mark + " ";
    badge.appendChild(mark);
    badge.appendChild(document.createTextNode(info.label));
    return badge;
  }

  function findingNode(finding) {
    const box = document.createElement("div");
    box.className = "finding";

    const head = document.createElement("p");
    head.className = "mb-1";
    head.appendChild(severityBadge(finding.severity));
    const title = document.createElement("strong");
    title.className = "ms-2";
    title.textContent = finding.title;
    head.appendChild(title);
    box.appendChild(head);

    if (finding.detail) {
      const detail = document.createElement("p");
      detail.className = "mb-1 small";
      detail.textContent = finding.detail;
      box.appendChild(detail);
    }
    if (finding.fix) {
      const fix = document.createElement("p");
      fix.className = "mb-1 small fix";
      fix.textContent = "Correzione suggerita: " + finding.fix;
      box.appendChild(fix);
    }
    if (finding.url) {
      const where = document.createElement("p");
      where.className = "mb-0 small text-muted";
      where.textContent = "Riferimento: " + finding.url;
      box.appendChild(where);
    }
    return box;
  }

  function summarizeArea(findings) {
    const counts = { critical: 0, warning: 0, info: 0, ok: 0 };
    findings.forEach((f) => {
      if (counts[f.severity] !== undefined) { counts[f.severity] += 1; }
    });
    const parts = [];
    if (counts.critical) { parts.push(counts.critical + " critici"); }
    if (counts.warning) { parts.push(counts.warning + " avvertenze"); }
    if (counts.ok) { parts.push(counts.ok + " ok"); }
    if (counts.info) { parts.push(counts.info + " informazioni"); }
    return parts.length ? " — " + parts.join(", ") : "";
  }

  function renderFindings(findings) {
    const acc = el("findings-acc");
    acc.textContent = "";

    AREAS.forEach((area, index) => {
      const subset = findings
        .filter((f) => f.area === area)
        .sort((a, b) => SEV_ORDER[a.severity] - SEV_ORDER[b.severity]);
      if (!subset.length) {
        return;
      }

      const item = document.createElement("div");
      item.className = "accordion-item";

      const headId = "acc-h-" + index;
      const bodyId = "acc-c-" + index;

      const header = document.createElement("h4");
      header.className = "accordion-header";
      header.id = headId;

      const button = document.createElement("button");
      button.type = "button";
      button.className = "accordion-button collapsed";
      button.setAttribute("data-bs-toggle", "collapse");
      button.setAttribute("data-bs-target", "#" + bodyId);
      button.setAttribute("aria-expanded", "false");
      button.setAttribute("aria-controls", bodyId);
      button.textContent = area + summarizeArea(subset);
      header.appendChild(button);
      item.appendChild(header);

      const collapse = document.createElement("div");
      collapse.id = bodyId;
      collapse.className = "accordion-collapse collapse";
      collapse.setAttribute("aria-labelledby", headId);

      const body = document.createElement("div");
      body.className = "accordion-body";
      subset.forEach((f) => body.appendChild(findingNode(f)));
      collapse.appendChild(body);
      item.appendChild(collapse);

      acc.appendChild(item);
    });
  }

  function renderCompetitive(comp) {
    const block = el("competitive-block");
    if (!comp) {
      block.hidden = true;
      return;
    }
    const parity = 100 / Math.max(1, comp.sites.length);
    el("competitive-intro").textContent =
      "Share of voice sui primi " + comp.top_n + " posti delle " +
      "liste fuse, sulle query dei temi del tuo sito. La tacca " +
      "indica la parità (" + Math.round(parity) + "%): sopra la " +
      "tacca si è sopra la propria quota naturale.";

    const bars = el("share-bars");
    bars.textContent = "";
    comp.sites.forEach((host) => {
      const mine = host === comp.main;
      const row = document.createElement("div");
      row.className = "score-row";

      const name = document.createElement("span");
      name.className = "score-label";
      name.textContent = host + (mine ? " — tuo sito" : "");
      if (mine) { name.classList.add("fw-bold"); }
      row.appendChild(name);

      const bar = document.createElement("div");
      bar.className = "progress share-meter";
      bar.setAttribute("aria-hidden", "true");
      const fill = document.createElement("div");
      fill.className = "progress-bar";
      fill.style.width = comp.share[host] + "%";
      if (!mine) { fill.style.backgroundColor = "#3c5054"; }
      bar.appendChild(fill);
      const tick = document.createElement("span");
      tick.className = "meter-tick";
      tick.style.left = parity + "%";
      bar.appendChild(tick);
      row.appendChild(bar);

      const value = document.createElement("span");
      value.className = "score-value";
      value.textContent = comp.share[host] + "%";
      row.appendChild(value);

      bars.appendChild(row);
    });

    const tbody = el("sov-table").querySelector("tbody");
    tbody.textContent = "";
    comp.queries.forEach((row) => {
      const tr = document.createElement("tr");

      const query = document.createElement("th");
      query.scope = "row";
      query.className = "fw-normal";
      query.textContent = row.query;
      tr.appendChild(query);

      const mineCount = document.createElement("td");
      mineCount.textContent = row.mine_in_top + " su " + comp.top_n;
      tr.appendChild(mineCount);

      const best = document.createElement("td");
      best.textContent = row.best_rank_mine
        ? String(row.best_rank_mine) : "assente";
      tr.appendChild(best);

      tbody.appendChild(tr);
    });

    block.hidden = false;
  }

  function renderRrf(results) {
    const tbody = el("rrf-table").querySelector("tbody");
    tbody.textContent = "";

    results.forEach((result) => {
      const row = document.createElement("tr");

      const query = document.createElement("th");
      query.scope = "row";
      query.className = "fw-normal";
      query.textContent = result.query;
      row.appendChild(query);

      const consensus = document.createElement("td");
      consensus.className = "cons-cell";
      const num = document.createElement("span");
      num.className = "cons-num";
      num.textContent = result.consensus + " su 5";
      consensus.appendChild(num);
      const ratio = result.consensus / 5;
      const meter = document.createElement("div");
      meter.className = "cons-meter";
      meter.setAttribute("aria-hidden", "true");
      const fill = document.createElement("div");
      fill.className = "cons-fill";
      fill.style.width = (ratio * 100) + "%";
      fill.style.backgroundColor = ratio >= 0.45 ? "#1c6b45"
        : (ratio >= 0.2 ? "#a8480f" : "#9e1b1b");
      meter.appendChild(fill);
      [20, 45].forEach((pos) => {
        const tick = document.createElement("span");
        tick.className = "meter-tick";
        tick.style.left = pos + "%";
        meter.appendChild(tick);
      });
      consensus.appendChild(meter);
      row.appendChild(consensus);

      const covered = document.createElement("td");
      covered.textContent = result.covered ? "Sì" : "No";
      row.appendChild(covered);

      const top = document.createElement("td");
      if (result.fused_top && result.fused_top.length) {
        top.textContent = result.fused_top[0][0] +
          " (punteggio RRF " + result.fused_top[0][1] + ")";
      } else {
        top.textContent = "nessun passaggio recuperato";
      }
      row.appendChild(top);

      tbody.appendChild(row);
    });
  }
})();
