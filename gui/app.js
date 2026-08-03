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

  let running = false;
  let lastPhase = "";

  el("audit-form").addEventListener("submit", onSubmit);
  loadEnv();

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
        el("report-frame").hidden = true;
        el("audit-error").hidden = true;
        el("log").textContent = "";
        el("announcer").textContent = "Audit avviato.";
        el("progress-anim").hidden = false;
        el("progress-section").hidden = false;
        el("progress-heading").focus();
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

    renderMeta(snap.summary);
    renderScores(snap.summary);
    renderFindings(snap.findings || []);
    renderRrf(snap.rrf || []);
    renderCompetitive(snap.competitive);

    const frame = el("report-frame");
    frame.src = "api/report/html?t=" + Date.now();
    frame.hidden = false;

    el("results-section").hidden = false;
    el("results-heading").focus();
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

  function renderScores(summary) {
    const wrap = el("scores");
    wrap.textContent = "";
    const rows = AREAS.map((area) => [area, summary.scores[area]]);
    rows.push(["Punteggio complessivo", summary.overall]);

    rows.forEach(([label, value], index) => {
      const row = document.createElement("div");
      row.className = "score-row" +
        (index === rows.length - 1 ? " score-overall" : "");

      const name = document.createElement("span");
      name.className = "score-label";
      name.textContent = label;
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
    el("competitive-intro").textContent =
      "Share of voice sui primi " + comp.top_n + " posti delle " +
      "liste fuse, sulle query dei temi del tuo sito.";

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
      bar.className = "progress";
      bar.setAttribute("aria-hidden", "true");
      const fill = document.createElement("div");
      fill.className = "progress-bar";
      fill.style.width = comp.share[host] + "%";
      if (!mine) { fill.style.backgroundColor = "#3c5054"; }
      bar.appendChild(fill);
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
      consensus.textContent = result.consensus + " su 5";
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
