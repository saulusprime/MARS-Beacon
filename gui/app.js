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

  const PRESETS_KEY = "seo_rrf_presets";
  const PRESET_FIELDS = [
    "f-url", "f-max-pages", "f-delay", "f-max-body", "f-retries",
    "f-workers", "f-render", "f-market", "f-judge",
    "f-competitors", "f-robots", "f-robots-ack", "f-queries",
    "f-embeddings", "f-rrf-k", "f-top-n", "f-chunk-words",
    "f-w-lex", "f-w-vec",
  ];

  const NUMERIC_FIELDS = [
    ["f-max-pages", "e-max-pages"],
    ["f-delay", "e-delay"],
    ["f-max-body", "e-max-body"],
    ["f-retries", "e-retries"],
    ["f-workers", "e-workers"],
    ["f-rrf-k", "e-rrf-k"],
    ["f-top-n", "e-top-n"],
    ["f-chunk-words", "e-chunk-words"],
    ["f-w-lex", "e-w-lex"],
    ["f-w-vec", "e-w-vec"],
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

  let me = null;

  el("audit-form").addEventListener("submit", onSubmit);
  el("f-robots").addEventListener("change", syncRobotsAck);
  el("btn-compare").addEventListener("click", runCompare);
  el("btn-add-event").addEventListener("click", () => {
    const feedback = el("event-feedback");
    feedback.textContent = "";
    fetch("api/citations/events", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        date: el("f-ev-date").value,
        label: el("f-ev-label").value.trim(),
        site: el("f-ev-site").value.trim(),
      }),
    })
      .then((r) => r.json().then(
        (data) => ({ status: r.status, data })))
      .then(({ status, data }) => {
        if (status !== 201) {
          feedback.textContent = data.error ||
            "Evento non salvato.";
          return;
        }
        feedback.textContent = "Evento salvato.";
        el("f-ev-label").value = "";
        loadCitations();
      })
      .catch(() => {
        feedback.textContent = "Errore di rete.";
      });
  });
  el("f-cit-site").addEventListener("change", (event) => {
    const entry = citSites[Number(event.target.value)];
    if (entry) {
      renderCitationsSite(entry);
    }
  });
  el("cancel-btn").addEventListener("click", cancelAudit);
  el("login-form").addEventListener("submit", onLogin);
  el("register-form").addEventListener("submit", onRegister);
  el("profile-form").addEventListener("submit", onProfile);
  el("logout-btn").addEventListener("click", onLogout);
  ["dl-html", "dl-json", "dl-text", "open-report"].forEach((id) => {
    el(id).addEventListener("click", (event) => {
      if (!me || !me.profile_complete) {
        event.preventDefault();
      }
    });
  });
  el("preset-save").addEventListener("click", savePreset);
  el("preset-load").addEventListener("click", loadPreset);
  el("preset-delete").addEventListener("click", deletePreset);
  refreshPresetSelect();
  loadEnv();
  refreshAuth();

  /* ---------------- accesso e profilo ---------------- */

  function showAuthError(message) {
    const box = el("auth-error");
    box.textContent = message;
    box.hidden = false;
    box.focus();
  }

  function postJson(path, payload) {
    return fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }).then((r) => r.json().then(
      (data) => ({ status: r.status, data })));
  }

  function refreshAuth() {
    fetch("api/me")
      .then((r) => r.json())
      .then((info) => {
        applyAuth(info.authenticated ? info.user : null);
        if (me) {
          restoreResults();
        }
      })
      .catch(() => applyAuth(null));
  }

  function applyAuth(user) {
    me = user;
    el("auth-error").hidden = true;
    if (me) {
      el("auth-out").hidden = true;
      el("auth-in").hidden = false;
      el("auth-name").textContent = me.nome;
      el("auth-email").textContent = me.email;
      el("profile-block").hidden = !!me.profile_complete;
      el("profile-ok").hidden = !me.profile_complete;
      el("config-section").hidden = false;
      setOpen("sec-auth", false);
      setOpen("sec-config", true);
      loadHistory();
      loadCitations();
    } else {
      el("auth-out").hidden = false;
      el("auth-in").hidden = true;
      el("config-section").hidden = true;
      el("progress-section").hidden = true;
      el("results-section").hidden = true;
      el("history-section").hidden = true;
      el("citations-section").hidden = true;
      setOpen("sec-auth", true);
    }
    updateDownloadGate();
  }

  function updateDownloadGate() {
    const locked = !me || !me.profile_complete;
    ["dl-html", "dl-json", "dl-text", "dl-md", "dl-csv",
     "open-report"].forEach((id) => {
      const link = el(id);
      link.classList.toggle("disabled", locked);
      link.setAttribute("aria-disabled", locked ? "true" : "false");
    });
    el("download-note").hidden = !locked;
  }

  function onLogin(event) {
    event.preventDefault();
    postJson("api/login", {
      email: el("l-email").value.trim(),
      password: el("l-password").value,
    })
      .then(({ status, data }) => {
        if (status !== 200) {
          showAuthError(data.error || "Accesso non riuscito.");
          return;
        }
        applyAuth(data.user);
        restoreResults();
      })
      .catch(() => showAuthError("Server locale non raggiungibile."));
  }

  function onRegister(event) {
    event.preventDefault();
    postJson("api/register", {
      nome: el("r-nome").value.trim(),
      email: el("r-email").value.trim(),
      password: el("r-password").value,
      azienda: el("r-azienda").value.trim(),
      telefono: el("r-telefono").value.trim(),
      tos: el("r-tos").checked,
    })
      .then(({ status, data }) => {
        if (status !== 201) {
          showAuthError(data.error || "Registrazione non riuscita.");
          return;
        }
        applyAuth(data.user);
        el("announcer").textContent =
          "Registrazione completata: puoi avviare il check.";
      })
      .catch(() => showAuthError("Server locale non raggiungibile."));
  }

  function onProfile(event) {
    event.preventDefault();
    postJson("api/profile", {
      azienda: el("p-azienda").value.trim(),
      telefono: el("p-telefono").value.trim(),
    })
      .then(({ status, data }) => {
        if (status !== 200) {
          showAuthError(data.error || "Aggiornamento non riuscito.");
          return;
        }
        applyAuth(data.user);
      })
      .catch(() => showAuthError("Server locale non raggiungibile."));
  }

  function onLogout() {
    postJson("api/logout", {}).finally(() => applyAuth(null));
  }

  /* ---------------- storico degli audit ---------------- */

  function loadHistory() {
    if (!me) {
      return;
    }
    fetch("api/history")
      .then((r) => r.json())
      .then((data) => renderHistory(data.runs || []))
      .catch(() => { /* lo storico non blocca il resto */ });
  }

  function deltaNode(delta) {
    const span = document.createElement("span");
    if (delta === null) {
      span.className = "text-muted";
      span.textContent = "—";
    } else if (delta > 0) {
      span.className = "delta-up";
      span.textContent = "▲ +" + delta;
    } else if (delta < 0) {
      span.className = "delta-down";
      span.textContent = "▼ " + delta;
    } else {
      span.className = "text-muted";
      span.textContent = "=";
    }
    return span;
  }

  function renderHistory(runs) {
    const section = el("history-section");
    if (!runs.length) {
      section.hidden = true;
      return;
    }
    const tbody = el("history-table").querySelector("tbody");
    tbody.textContent = "";
    runs.forEach((run, index) => {
      const prev = runs.slice(index + 1)
        .find((r) => r.site === run.site);
      const delta = prev
        ? Math.round(run.overall) - Math.round(prev.overall) : null;

      const tr = document.createElement("tr");
      const when = document.createElement("td");
      when.textContent = new Date(run.created_at * 1000)
        .toLocaleString("it-IT", {
          day: "2-digit", month: "2-digit", year: "2-digit",
          hour: "2-digit", minute: "2-digit",
        });
      tr.appendChild(when);

      const site = document.createElement("th");
      site.scope = "row";
      site.className = "fw-normal";
      site.textContent = run.site;
      tr.appendChild(site);

      const score = document.createElement("td");
      const dot = document.createElement("span");
      dot.className = "sev-dot me-1";
      dot.style.backgroundColor = scoreColor(run.overall);
      score.appendChild(dot);
      score.appendChild(document.createTextNode(
        Math.round(run.overall) + "/100"));
      tr.appendChild(score);

      const deltaCell = document.createElement("td");
      deltaCell.appendChild(deltaNode(delta));
      tr.appendChild(deltaCell);

      const critical = document.createElement("td");
      critical.textContent = run.critical;
      tr.appendChild(critical);
      const warning = document.createElement("td");
      warning.textContent = run.warning;
      tr.appendChild(warning);

      const report = document.createElement("td");
      if (run.has_report) {
        const link = document.createElement("a");
        link.href = "api/history/report?id=" + run.id +
          "&download=1";
        link.textContent = "JSON";
        link.setAttribute("aria-label",
          "Scarica il referto JSON dell'audit di " + run.site +
          " del " + when.textContent);
        if (!me || !me.profile_complete) {
          link.classList.add("disabled");
          link.setAttribute("aria-disabled", "true");
        }
        report.appendChild(link);
      } else {
        report.className = "text-muted";
        report.textContent = "—";
      }
      tr.appendChild(report);

      tbody.appendChild(tr);
    });

    renderTrend(runs.filter((r) => r.site === runs[0].site)
      .slice(0, 12).reverse());
    renderCompareBox(runs);
    section.hidden = false;
  }

  function renderCompareBox(runs) {
    const box = el("compare-box");
    const confrontabili = runs.filter((r) => r.has_report);
    if (confrontabili.length < 2) {
      box.hidden = true;
      return;
    }
    ["f-cmp-a", "f-cmp-b"].forEach((id, position) => {
      const select = el(id);
      select.textContent = "";
      confrontabili.forEach((run, index) => {
        const option = document.createElement("option");
        option.value = String(run.id);
        option.textContent =
          new Date(run.created_at * 1000).toLocaleString("it-IT", {
            day: "2-digit", month: "2-digit", year: "2-digit",
            hour: "2-digit", minute: "2-digit",
          }) + " — " + run.site + " (" +
          Math.round(run.overall) + "/100)";
        // Preselezione: penultima vs ultima esecuzione.
        if ((position === 0 && index === 1) ||
            (position === 1 && index === 0)) {
          option.selected = true;
        }
        select.appendChild(option);
      });
    });
    el("compare-error").textContent = "";
    el("compare-result").hidden = true;
    box.hidden = false;
  }

  function runCompare() {
    const a = el("f-cmp-a").value;
    const b = el("f-cmp-b").value;
    el("compare-error").textContent = "";
    fetch("api/history/compare?a=" + a + "&b=" + b)
      .then((r) => r.json().then(
        (data) => ({ status: r.status, data })))
      .then(({ status, data }) => {
        if (status !== 200) {
          el("compare-error").textContent =
            data.error || "Confronto non riuscito.";
          el("compare-result").hidden = true;
          return;
        }
        renderCompareResult(data);
      })
      .catch(() => {
        el("compare-error").textContent = "Errore di rete.";
      });
  }

  function renderCompareResult(data) {
    const delta = data.delta;
    const quando = (ts) =>
      new Date(ts * 1000).toLocaleString("it-IT", {
        day: "2-digit", month: "2-digit", year: "2-digit",
        hour: "2-digit", minute: "2-digit",
      });
    el("cmp-intro").textContent =
      data.site + ": confronto fra l'audit del " +
      quando(data.older_at) + " e quello del " +
      quando(data.newer_at) + ". Rilievi confrontati per tipo.";

    const scores = el("cmp-scores");
    scores.textContent = "";
    Object.entries(delta.scores || {}).forEach(
      ([area, value], index) => {
        if (index) {
          scores.appendChild(document.createTextNode(" · "));
        }
        const label = document.createElement("strong");
        label.textContent = area + ": ";
        scores.appendChild(label);
        scores.appendChild(deltaNode(value));
      });

    const fill = (listId, titleId, items, titolo, vuoto) => {
      const list = el(listId);
      list.textContent = "";
      el(titleId).textContent = titolo + " (" + items.length + ")";
      if (!items.length) {
        const item = document.createElement("li");
        item.className = "text-muted small";
        item.textContent = vuoto;
        list.appendChild(item);
        return;
      }
      items.forEach((f) => {
        const item = document.createElement("li");
        item.className = "mb-1";
        item.appendChild(severityBadge(f.severity));
        const text = document.createElement("span");
        text.className = "ms-2";
        text.textContent = f.title;
        item.appendChild(text);
        list.appendChild(item);
      });
    };
    fill("cmp-resolved", "cmp-resolved-title",
      delta.resolved || [], "Rilievi risolti",
      "Nessun rilievo risolto.");
    fill("cmp-new", "cmp-new-title", delta.new || [],
      "Rilievi nuovi", "Nessun rilievo nuovo.");
    el("compare-result").hidden = false;
  }

  /* Trend del punteggio complessivo (stile CrUX Vis: linea con
     soglie 40/70 tratteggiate come hairline). */
  function renderTrend(points) {
    const box = el("history-trend");
    box.textContent = "";
    if (points.length < 2) {
      return;
    }
    const width = 560;
    const x0 = 40;
    const x1 = 540;
    const yOf = (value) => 150 - value * 1.3;
    const xOf = (index) =>
      x0 + (x1 - x0) * index / (points.length - 1);

    const svg = svgNode("svg", {
      viewBox: "0 0 " + width + " 175",
      class: "history-trend-svg",
      role: "img",
      "aria-label": "Andamento del punteggio complessivo di " +
        points[points.length - 1].site + " negli ultimi " +
        points.length + " audit",
    });
    [[0, "#c3c2b7"], [40, "#e5e5e5"], [70, "#e5e5e5"]]
      .forEach(([value, color]) => {
        svg.appendChild(svgNode("line", {
          x1: x0, x2: x1, y1: yOf(value), y2: yOf(value),
          stroke: color, "stroke-width": 1,
        }));
      });
    [[40, "40"], [70, "70"], [0, "0"]].forEach(([value, label]) => {
      const text = svgNode("text", {
        x: x0 - 6, y: yOf(value) + 4, "font-size": 10,
        "text-anchor": "end", fill: "#6b7f83",
      });
      text.textContent = label;
      svg.appendChild(text);
    });

    const coords = points.map((p, i) =>
      xOf(i).toFixed(1) + "," + yOf(p.overall).toFixed(1));
    svg.appendChild(svgNode("polyline", {
      points: coords.join(" "),
      fill: "none", stroke: "#186078", "stroke-width": 2,
      "stroke-linejoin": "round", "stroke-linecap": "round",
    }));
    const last = points[points.length - 1];
    svg.appendChild(svgNode("circle", {
      cx: x1, cy: yOf(last.overall), r: 6, fill: "#fff",
    }));
    svg.appendChild(svgNode("circle", {
      cx: x1, cy: yOf(last.overall), r: 4, fill: "#186078",
    }));
    const endLabel = svgNode("text", {
      x: x1 - 10, y: yOf(last.overall) - 10, "font-size": 11,
      "font-weight": 600, "text-anchor": "end", fill: "#14272b",
    });
    endLabel.textContent = Math.round(last.overall);
    svg.appendChild(endLabel);
    box.appendChild(svg);
  }

  /* ---------------- citazioni IA nel tempo ---------------- */

  const CIT_STYLES = [
    { stroke: "#186078", dash: "" },
    { stroke: "#7a2e8d", dash: "7,4" },
    { stroke: "#9c5400", dash: "2,4" },
  ];
  let citSites = [];
  let citEvents = [];

  function loadCitations() {
    if (!me) {
      return;
    }
    fetch("api/citations")
      .then((r) => r.json())
      .then((data) => {
        citEvents = data.events || [];
        renderCitations(data.sites || []);
      })
      .catch(() => { /* lo storico citazioni non blocca il resto */ });
  }

  function eventsForSite(site) {
    return citEvents.filter(
      (e) => !e.site || site.indexOf(e.site) !== -1);
  }

  function renderCitations(sites) {
    const section = el("citations-section");
    citSites = sites;
    if (!sites.length) {
      section.hidden = true;
      return;
    }
    const select = el("f-cit-site");
    select.textContent = "";
    sites.forEach((entry, index) => {
      const option = document.createElement("option");
      option.value = String(index);
      option.textContent = entry.site;
      select.appendChild(option);
    });
    el("cit-site-box").hidden = sites.length < 2;
    renderCitationsSite(sites[0]);
    section.hidden = false;
  }

  function citProviders(runs) {
    const names = [];
    runs.forEach((run) => {
      Object.keys(run.providers || {}).forEach((name) => {
        if (names.indexOf(name) === -1) {
          names.push(name);
        }
      });
    });
    return names;
  }

  function fmtRate(value) {
    return (value === null || value === undefined)
      ? "n/d" : value.toFixed(1).replace(".", ",") + "%";
  }

  function renderCitationsSite(entry) {
    const runs = entry.runs;
    const providers = citProviders(runs);
    renderCitSummary(runs, providers);
    renderCitChart(entry.site, runs, providers);
    renderCitEvents(entry.site);
    renderCitTable(runs, providers);
  }

  function renderCitEvents(site) {
    const box = el("cit-events-box");
    const list = el("cit-events");
    list.textContent = "";
    const eventi = eventsForSite(site);
    if (!eventi.length) {
      box.hidden = true;
      return;
    }
    eventi.forEach((event) => {
      const item = document.createElement("li");
      item.textContent = event.date + " — " + event.label;
      list.appendChild(item);
    });
    box.hidden = false;
  }

  function renderCitSummary(runs, providers) {
    const box = el("cit-trend-summary");
    box.textContent = "";
    const last = runs[runs.length - 1];
    const prev = runs.length > 1 ? runs[runs.length - 2] : null;
    const parts = [["Complessivo", last.overall_rate,
                    prev ? prev.overall_rate : null]];
    providers.forEach((name) => {
      parts.push([
        name,
        (last.providers[name] || {}).rate,
        prev ? (prev.providers[name] || {}).rate : null,
      ]);
    });
    parts.forEach(([label, now, before], index) => {
      if (index) {
        box.appendChild(document.createTextNode(" · "));
      }
      const strong = document.createElement("strong");
      strong.textContent = label + ": ";
      box.appendChild(strong);
      box.appendChild(document.createTextNode(fmtRate(now) + " "));
      const delta = (now === null || now === undefined
        || before === null || before === undefined)
        ? null : Math.round((now - before) * 10) / 10;
      box.appendChild(deltaNode(delta));
    });
  }

  function renderCitChart(site, runs, providers) {
    const box = el("cit-chart");
    box.textContent = "";
    if (runs.length < 2) {
      return;
    }
    const width = 620;
    const x0 = 46;
    const x1 = 500;
    const yOf = (value) => 150 - value * 1.3;
    const xOf = (index) =>
      x0 + (x1 - x0) * index / (runs.length - 1);
    const svg = svgNode("svg", {
      viewBox: "0 0 " + width + " 175",
      class: "history-trend-svg",
      role: "img",
      "aria-label": "Andamento del tasso di citazione IA di " +
        site + " nelle ultime " + runs.length +
        " esecuzioni; i valori sono nella tabella seguente",
    });
    [[0, "0%"], [50, "50%"], [100, "100%"]].forEach(
      ([value, label]) => {
        svg.appendChild(svgNode("line", {
          x1: x0, x2: x1, y1: yOf(value), y2: yOf(value),
          stroke: value ? "#e5e5e5" : "#c3c2b7",
          "stroke-width": 1,
        }));
        const text = svgNode("text", {
          x: x0 - 6, y: yOf(value) + 4, "font-size": 10,
          "text-anchor": "end", fill: "#6b7f83",
        });
        text.textContent = label;
        svg.appendChild(text);
      });

    const series = [{
      name: "complessivo", stroke: "#14272b", dash: "",
      width: 2.5, values: runs.map((r) => r.overall_rate),
    }];
    providers.forEach((name, index) => {
      const style = CIT_STYLES[index % CIT_STYLES.length];
      series.push({
        name: name, stroke: style.stroke, dash: style.dash,
        width: 2,
        values: runs.map((r) => (r.providers[name] || {}).rate),
      });
    });

    const labels = [];
    series.forEach((serie) => {
      const coords = [];
      let lastValue = null;
      let lastX = null;
      serie.values.forEach((value, index) => {
        if (value === null || value === undefined) {
          return;
        }
        coords.push(xOf(index).toFixed(1) + "," +
          yOf(value).toFixed(1));
        lastValue = value;
        lastX = xOf(index);
      });
      if (coords.length < 2) {
        return;
      }
      const attrs = {
        points: coords.join(" "), fill: "none",
        stroke: serie.stroke, "stroke-width": serie.width,
        "stroke-linejoin": "round", "stroke-linecap": "round",
      };
      if (serie.dash) {
        attrs["stroke-dasharray"] = serie.dash;
      }
      svg.appendChild(svgNode("polyline", attrs));
      svg.appendChild(svgNode("circle", {
        cx: lastX, cy: yOf(lastValue), r: 3.5,
        fill: serie.stroke,
      }));
      labels.push({ y: yOf(lastValue), serie: serie });
    });

    // Pin-evento: linea verticale tratteggiata sull'esecuzione
    // successiva all'evento ("qui abbiamo pubblicato le FAQ").
    const dates = runs.map((r) =>
      String(r.generated_at || "").slice(0, 10));
    eventsForSite(site).forEach((event) => {
      let index = dates.findIndex((d) => d >= event.date);
      if (index === -1) {
        return; // evento successivo all'ultima esecuzione
      }
      const x = xOf(index);
      svg.appendChild(svgNode("line", {
        x1: x, x2: x, y1: yOf(100) - 8, y2: yOf(0),
        stroke: "#9a6a00", "stroke-width": 1.5,
        "stroke-dasharray": "3,3",
      }));
      svg.appendChild(svgNode("circle", {
        cx: x, cy: yOf(100) - 10, r: 3.5, fill: "#9a6a00",
      }));
    });

    // Etichette di fine linea (nome + valore): mai solo colore.
    labels.sort((a, b) => a.y - b.y);
    let prevY = -100;
    labels.forEach((item) => {
      const y = Math.max(item.y, prevY + 13);
      prevY = y;
      const text = svgNode("text", {
        x: x1 + 8, y: y + 4, "font-size": 11,
        "font-weight": 600, fill: item.serie.stroke,
      });
      text.textContent = item.serie.name;
      svg.appendChild(text);
    });
    box.appendChild(svg);
  }

  function renderCitTable(runs, providers) {
    const table = el("cit-table");
    const thead = table.querySelector("thead");
    const tbody = table.querySelector("tbody");
    thead.textContent = "";
    tbody.textContent = "";

    const headRow = document.createElement("tr");
    ["Data", "Complessivo"].concat(providers).forEach((label) => {
      const th = document.createElement("th");
      th.scope = "col";
      th.textContent = label;
      headRow.appendChild(th);
    });
    thead.appendChild(headRow);

    runs.slice().reverse().forEach((run) => {
      const tr = document.createElement("tr");
      const when = document.createElement("th");
      when.scope = "row";
      when.className = "fw-normal";
      when.textContent = String(run.generated_at || "")
        .slice(0, 16).replace("T", " ");
      tr.appendChild(when);
      const overall = document.createElement("td");
      overall.textContent = fmtRate(run.overall_rate);
      tr.appendChild(overall);
      providers.forEach((name) => {
        const stats = run.providers[name];
        const cell = document.createElement("td");
        cell.textContent = stats
          ? fmtRate(stats.rate) + " (" + stats.site_cited +
            " su " + stats.answered + ")"
          : "n/d";
        tr.appendChild(cell);
      });
      tbody.appendChild(tr);
    });
  }

  /* ---------------- preimpostazioni ---------------- */

  function readPresets() {
    try {
      return JSON.parse(
        window.localStorage.getItem(PRESETS_KEY)) || {};
    } catch (err) {
      return {};
    }
  }

  function writePresets(presets) {
    window.localStorage.setItem(PRESETS_KEY,
      JSON.stringify(presets));
  }

  function refreshPresetSelect() {
    const select = el("preset-select");
    const current = select.value;
    select.textContent = "";
    const none = document.createElement("option");
    none.value = "";
    none.textContent = "— nessuna —";
    select.appendChild(none);
    Object.keys(readPresets()).sort().forEach((name) => {
      const option = document.createElement("option");
      option.value = name;
      option.textContent = name;
      select.appendChild(option);
    });
    select.value = current;
  }

  function savePreset() {
    const name = el("preset-name").value.trim();
    if (!name) {
      showFormError("Dai un nome alla preimpostazione da salvare.");
      return;
    }
    const presets = readPresets();
    const data = {};
    PRESET_FIELDS.forEach((id) => {
      const field = el(id);
      data[id] = field.type === "checkbox"
        ? field.checked : field.value;
    });
    presets[name] = data;
    writePresets(presets);
    el("preset-name").value = "";
    refreshPresetSelect();
    el("preset-select").value = name;
    el("announcer").textContent =
      "Preimpostazione \"" + name + "\" salvata.";
  }

  function loadPreset() {
    const name = el("preset-select").value;
    const data = readPresets()[name];
    if (!data) {
      return;
    }
    PRESET_FIELDS.forEach((id) => {
      const field = el(id);
      if (field.type === "checkbox") {
        field.checked = !!data[id];
      } else if (data[id] !== undefined) {
        field.value = data[id];
      }
    });
    el("announcer").textContent =
      "Preimpostazione \"" + name + "\" caricata.";
    syncRobotsAck();
  }

  /* Mostra la conferma di responsabilita' solo quando si sceglie di
     ignorare i Disallow; cambiando modalita' la spunta si azzera. */
  function syncRobotsAck() {
    const force = el("f-robots").value === "force";
    el("robots-ack-box").hidden = !force;
    if (!force) {
      el("f-robots-ack").checked = false;
    }
  }

  function deletePreset() {
    const name = el("preset-select").value;
    if (!name) {
      return;
    }
    const presets = readPresets();
    delete presets[name];
    writePresets(presets);
    refreshPresetSelect();
    el("announcer").textContent =
      "Preimpostazione \"" + name + "\" eliminata.";
  }

  function cancelAudit() {
    const btn = el("cancel-btn");
    btn.disabled = true;
    btn.textContent = "Annullamento…";
    el("announcer").textContent = "Annullamento richiesto…";
    fetch("api/cancel", { method: "POST" }).catch(() => {
      btn.disabled = false;
      btn.textContent = "Annulla audit";
    });
  }

  function hideCancel() {
    const btn = el("cancel-btn");
    btn.hidden = true;
    btn.disabled = false;
    btn.textContent = "Annulla audit";
  }

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
        if (env.judge_available === false) {
          el("h-judge").textContent =
            "Non disponibile sul server: " + env.judge_reason +
            ". In auto il giudizio viene semplicemente saltato.";
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

    const robotsAck = el("f-robots-ack");
    if (el("f-robots").value === "force" && !robotsAck.checked) {
      markInvalid(robotsAck, "e-robots-ack",
        "Per ignorare i Disallow devi assumerti esplicitamente " +
        "la responsabilità della scansione.");
      firstInvalid = firstInvalid || robotsAck;
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
      workers: el("f-workers").valueAsNumber,
      render: el("f-render").value,
      market: el("f-market").value,
      judge: el("f-judge").value,
      rrf_k: el("f-rrf-k").valueAsNumber,
      top_n: el("f-top-n").valueAsNumber,
      chunk_words: el("f-chunk-words").valueAsNumber,
      w_lex: el("f-w-lex").valueAsNumber,
      w_vec: el("f-w-vec").valueAsNumber,
      queries: el("f-queries").value,
      embeddings: el("f-embeddings").value.trim(),
      robots: el("f-robots").value,
      robots_ack: el("f-robots-ack").checked,
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
        el("cancel-btn").hidden = false;
        el("progress-section").hidden = false;
        setOpen("sec-config", false);
        setOpen("sec-progress", true);
        el("progress-toggle").focus();
        window.setTimeout(watchProgress, 300);
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

  /* Avanzamento push (SSE) con ripiego sul polling. */

  let events = null;

  function stopEvents() {
    if (events) {
      events.close();
      events = null;
    }
  }

  function watchProgress() {
    stopEvents();
    if (window.EventSource) {
      try {
        events = new EventSource("api/events");
        events.onmessage = (msg) => {
          handleSnapshot(JSON.parse(msg.data));
        };
        events.onerror = () => {
          stopEvents();
          if (running) {
            window.setTimeout(poll, 500);
          }
        };
        return;
      } catch (err) { /* ripiego sul polling */ }
    }
    poll();
  }

  function handleSnapshot(snap) {
    if (!snap.state) {
      stopEvents();
      fail(snap.error || "Sessione scaduta: accedi di nuovo.");
      return;
    }
    renderLog(snap.log || []);
    if (snap.state === "done") {
      stopEvents();
      finish(snap);
    } else if (snap.state === "cancelled") {
      stopEvents();
      cancelled();
    } else if (snap.state === "error") {
      stopEvents();
      fail(snap.error || "Errore sconosciuto durante l'audit.");
    }
  }

  function poll() {
    fetch("api/status")
      .then((r) => r.json())
      .then((snap) => {
        handleSnapshot(snap);
        if (snap.state === "running") {
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

  function cancelled() {
    running = false;
    setSubmitState(false);
    hideCancel();
    el("progress-anim").hidden = true;
    el("announcer").textContent =
      "Audit annullato: nessun risultato prodotto. Puoi avviarne " +
      "un altro dalla configurazione.";
    setOpen("sec-config", true);
  }

  function fail(message) {
    running = false;
    setSubmitState(false);
    hideCancel();
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
    hideCancel();
    el("progress-anim").hidden = true;
    el("announcer").textContent = "Audit completato: risultati pronti.";
    setOpen("sec-progress", false);
    showResults(snap);
    loadHistory();
    el("results-toggle").focus();
  }

  function showResults(snap) {
    renderMeta(snap.summary);
    renderHero(snap.summary);
    renderDelta((snap.summary || {}).delta);
    renderScores(snap.summary);
    renderTopRilievi(snap.remediation || []);
    renderCitability(snap.summary || {});
    renderJudge((snap.summary || {}).judge,
      (snap.summary || {}).citability);
    renderFindings(snap.findings || [],
      (snap.summary || {}).delta);
    renderSurfaceMath((snap.summary || {}).surface_math);
    renderDepth((snap.summary || {}).depth_distribution);
    renderRemediation(snap.remediation || []);
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

  function renderTopRilievi(plan) {
    const block = el("toplist-block");
    const list = el("toplist");
    list.textContent = "";
    if (!plan.length) {
      block.hidden = true;
      return;
    }
    plan.slice(0, 5).forEach((item) => {
      const row = document.createElement("li");
      row.className = "mb-1";
      const dot = document.createElement("span");
      dot.className = "sev-dot me-1";
      dot.style.backgroundColor =
        item.severity === "critical" ? "#9c2f26" : "#9a6a00";
      row.appendChild(dot);
      const sev = document.createElement("span");
      sev.className = "small text-muted me-1";
      sev.textContent =
        (item.severity === "critical" ? "CRITICO" : "AVVISO") +
        " · " + item.area + " — ";
      row.appendChild(sev);
      const title = document.createElement("strong");
      title.textContent = item.title;
      row.appendChild(title);
      if (item.index_gain) {
        const gain = document.createElement("span");
        gain.className = "badge badge-effort ms-2";
        gain.textContent = "+" +
          item.index_gain.toFixed(1).replace(".", ",") + " indice";
        row.appendChild(gain);
      }
      list.appendChild(row);
    });
    block.hidden = false;
  }

  function normFindingKey(finding) {
    return finding.area + "|" +
      String(finding.title).replace(/\d+/g, "N");
  }

  function renderDelta(delta) {
    const block = el("delta-block");
    if (!delta) {
      block.hidden = true;
      return;
    }
    const quando = new Date(delta.previous_at * 1000)
      .toLocaleString("it-IT", {
        day: "2-digit", month: "2-digit", year: "2-digit",
        hour: "2-digit", minute: "2-digit",
      });
    el("delta-intro").textContent =
      "Confronto con l'audit del " + quando + " sullo stesso " +
      "sito: l'audit diventa monitoraggio. I rilievi sono " +
      "confrontati per tipo (i conteggi nei titoli possono " +
      "variare).";

    const scores = el("delta-scores");
    scores.textContent = "";
    Object.entries(delta.scores || {}).forEach(
      ([area, value], index) => {
        if (index) {
          scores.appendChild(document.createTextNode(" · "));
        }
        const label = document.createElement("strong");
        label.textContent = area + ": ";
        scores.appendChild(label);
        scores.appendChild(deltaNode(value));
      });

    const fill = (listId, titleId, items, titolo, vuoto) => {
      const list = el(listId);
      list.textContent = "";
      el(titleId).textContent = titolo + " (" + items.length + ")";
      if (!items.length) {
        const item = document.createElement("li");
        item.className = "text-muted small";
        item.textContent = vuoto;
        list.appendChild(item);
        return;
      }
      items.forEach((f) => {
        const item = document.createElement("li");
        item.className = "mb-1";
        item.appendChild(severityBadge(f.severity));
        const text = document.createElement("span");
        text.className = "ms-2";
        text.textContent = f.title;
        item.appendChild(text);
        list.appendChild(item);
      });
    };
    fill("delta-resolved", "delta-resolved-title",
      delta.resolved || [], "Rilievi risolti",
      "Nessun rilievo risolto.");
    fill("delta-new", "delta-new-title", delta.new || [],
      "Rilievi nuovi", "Nessun rilievo nuovo: bene.");
    block.hidden = false;
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

  function renderCitability(summary) {
    const block = el("citability-block");
    const cit = summary.citability;
    if (!cit || !cit.profiles) {
      block.hidden = true;
      return;
    }
    const pesi = Object.entries(cit.market_weights || {})
      .map(([key, w]) => key + " " + Math.round(w * 100) + "%")
      .join(", ");
    el("citability-intro").textContent =
      cit.note + " Mercato di riferimento: " + cit.market +
      " (pesi: " + pesi + ").";

    const wrap = el("citability-bars");
    wrap.textContent = "";
    const rows = cit.profiles
      .filter((p) => p.score !== null && p.score !== undefined)
      .map((p) => [p.label, p.focus, p.score, false]);
    if (cit.index !== null && cit.index !== undefined) {
      rows.push(["Indice composito", "", cit.index, true]);
    }
    rows.forEach(([label, focus, value, isTotal]) => {
      const row = document.createElement("div");
      row.className = "score-row" + (isTotal ? " score-overall" : "");

      const name = document.createElement("span");
      name.className = "score-label";
      name.appendChild(document.createTextNode(label));
      if (focus) {
        const detail = document.createElement("small");
        detail.className = "d-block text-muted";
        detail.textContent = focus;
        name.appendChild(detail);
      }
      row.appendChild(name);

      const bar = document.createElement("div");
      bar.className = "progress";
      bar.setAttribute("aria-hidden", "true");
      const fill = document.createElement("div");
      fill.className = "progress-bar";
      fill.style.width = value + "%";
      fill.style.backgroundColor = scoreColor(value);
      bar.appendChild(fill);
      row.appendChild(bar);

      const num = document.createElement("span");
      num.className = "score-value";
      num.textContent = Math.round(value) + "/100";
      row.appendChild(num);

      wrap.appendChild(row);
    });

    renderCitabilityActions(summary.citability_actions || []);
    block.hidden = false;
  }

  function renderCitabilityActions(actions) {
    const box = el("citability-actions-box");
    const list = el("citability-actions");
    list.textContent = "";
    if (!actions.length) {
      box.hidden = true;
      return;
    }
    actions.forEach((act) => {
      const item = document.createElement("li");
      item.className = "mb-1";

      const title = document.createElement("strong");
      title.textContent = act.title;
      item.appendChild(title);

      if (act.effort) {
        const effort = document.createElement("span");
        effort.className = "badge badge-effort ms-2";
        effort.textContent = "sforzo: " + act.effort;
        item.appendChild(effort);
      }
      if (act.quick_win) {
        const win = document.createElement("span");
        win.className = "badge badge-quickwin ms-2";
        win.textContent = "quick win";
        item.appendChild(win);
      }
      if (act.best_profile) {
        const gain = document.createElement("span");
        gain.className = "d-block small text-muted";
        gain.textContent = "Guadagna di più: " + act.best_label +
          " (+" + act.best_gain.toFixed(1).replace(".", ",") +
          " punti profilo)";
        item.appendChild(gain);
      }
      list.appendChild(item);
    });
    box.hidden = false;
  }

  function renderJudge(judge, cit) {
    const block = el("judge-block");
    if (!judge) {
      block.hidden = true;
      return;
    }
    const intro = el("judge-intro");
    const tableBox = el("judge-table-box");
    const tbody = el("judge-table").querySelector("tbody");
    tbody.textContent = "";
    if (judge.status !== "ok") {
      intro.textContent = "Non eseguito: " + (judge.reason || "");
      tableBox.hidden = true;
      block.hidden = false;
      return;
    }
    let confronto = "";
    if (cit && cit.index !== null && cit.index !== undefined) {
      const scarto = judge.average - cit.index;
      confronto = " Indice euristico: " +
        cit.index.toFixed(1).replace(".", ",") +
        " — scarto giudice-euristica: " +
        (scarto >= 0 ? "+" : "") +
        scarto.toFixed(1).replace(".", ",") + ".";
    }
    intro.textContent = "Modello " + judge.model + " su " +
      judge.sampled + " passaggio/i · media " +
      judge.average.toFixed(1).replace(".", ",") + "/100." +
      confronto;
    el("judge-note").textContent = judge.note || "";
    judge.verdicts.forEach((v) => {
      const row = document.createElement("tr");
      const query = document.createElement("td");
      query.textContent = v.query;
      row.appendChild(query);
      const score = document.createElement("td");
      score.textContent =
        Math.round(v.score) + "/100";
      score.style.color = scoreColor(v.score);
      score.style.fontWeight = "600";
      row.appendChild(score);
      const reason = document.createElement("td");
      reason.textContent = v.reason;
      row.appendChild(reason);
      tbody.appendChild(row);
    });
    tableBox.hidden = false;
    block.hidden = false;
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

  function findingNode(finding, isNew) {
    const box = document.createElement("div");
    box.className = "finding";

    const head = document.createElement("p");
    head.className = "mb-1";
    head.appendChild(severityBadge(finding.severity));
    const title = document.createElement("strong");
    title.className = "ms-2";
    title.textContent = finding.title;
    head.appendChild(title);
    if (isNew) {
      const nuovo = document.createElement("span");
      nuovo.className = "badge badge-new ms-2";
      nuovo.textContent = "NUOVO";
      head.appendChild(nuovo);
    }
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

  function renderFindings(findings, delta) {
    const acc = el("findings-acc");
    acc.textContent = "";
    const newKeys = new Set(
      ((delta || {}).new || []).map(normFindingKey));

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
      subset.forEach((f) => body.appendChild(
        findingNode(f, newKeys.has(normFindingKey(f)))));
      collapse.appendChild(body);
      item.appendChild(collapse);

      acc.appendChild(item);
    });
  }

  function renderSurfaceMath(math) {
    const block = el("surface-math-block");
    const list = el("surface-math-list");
    list.textContent = "";
    if (!math) {
      block.hidden = true;
      return;
    }
    const effetto = math.multiplier !== null
      ? "circa " + math.multiplier + "× occasioni di comparire " +
        "nelle liste fuse"
      : "da 0 addendi a circa " + math.chunks_potential +
        " occasioni di comparire nelle liste";
    const righe = [
      ["Superficie attuale", math.pages + " pagine, " +
        math.chunks_now + " chunk (~" + math.words_avg +
        " parole/pagina)"],
      ["Superficie potenziale", "~" + math.chunks_potential +
        " chunk (" + math.assumption + ")"],
      ["Effetto sull'RRF", effetto],
    ];
    righe.forEach(([nome, valore]) => {
      const dt = document.createElement("dt");
      dt.textContent = nome;
      const dd = document.createElement("dd");
      dd.textContent = valore;
      list.appendChild(dt);
      list.appendChild(dd);
    });
    block.hidden = false;
  }

  function renderDepth(depths) {
    const block = el("depth-block");
    const wrap = el("depth-bars");
    wrap.textContent = "";
    if (!depths || !depths.buckets) {
      block.hidden = true;
      return;
    }
    const massimo = Math.max(1,
      ...depths.buckets.map((b) => b.count));
    depths.buckets.forEach((bucket) => {
      const row = document.createElement("div");
      row.className = "score-row";
      const name = document.createElement("span");
      name.className = "score-label";
      name.textContent = bucket.label;
      row.appendChild(name);
      const bar = document.createElement("div");
      bar.className = "progress";
      bar.setAttribute("aria-hidden", "true");
      const fill = document.createElement("div");
      fill.className = "progress-bar";
      fill.style.width = (100 * bucket.count / massimo) + "%";
      const critico = bucket.label.indexOf("4+") !== -1 ||
        bucket.label.indexOf("sitemap") !== -1;
      fill.style.backgroundColor = critico ? "#9a6a00" : "#1c6b45";
      bar.appendChild(fill);
      row.appendChild(bar);
      const num = document.createElement("span");
      num.className = "score-value";
      num.textContent = String(bucket.count);
      row.appendChild(num);
      wrap.appendChild(row);
    });
    block.hidden = false;
  }

  function renderRemediation(plan) {
    const block = el("remediation-block");
    const list = el("remediation-list");
    list.textContent = "";
    if (!plan.length) {
      block.hidden = true;
      return;
    }
    const quickWins = plan.filter((i) => i.quick_win).length;
    const annotato = plan[0].index_gain !== undefined;
    el("remediation-intro").textContent =
      plan.length + (annotato
        ? " interventi ordinati per gravità e guadagno di " +
          "citabilità: in testa i problemi trasversali, che " +
          "deprimono più profili insieme."
        : " interventi ordinati per gravità e peso: si parte da " +
          "ciò che rende di più sul punteggio.") +
      (quickWins ? " Quick win (critici risolvibili in minuti): " +
        quickWins + "." : "");

    plan.forEach((item) => {
      const box = document.createElement("div");
      box.className = "finding";

      const head = document.createElement("p");
      head.className = "mb-1";
      head.appendChild(severityBadge(item.severity));
      const title = document.createElement("strong");
      title.className = "ms-2";
      title.textContent = item.priority + ". " + item.title;
      head.appendChild(title);
      if (item.effort) {
        const effort = document.createElement("span");
        effort.className = "badge badge-effort ms-2";
        effort.textContent = "sforzo: " + item.effort;
        head.appendChild(effort);
      }
      if (item.quick_win) {
        const win = document.createElement("span");
        win.className = "badge badge-quickwin ms-2";
        win.textContent = "quick win";
        head.appendChild(win);
      }
      if (item.cross) {
        const cross = document.createElement("span");
        cross.className = "badge badge-cross ms-2";
        cross.textContent = "trasversale: " +
          item.profiles_hit.length + " profili · +" +
          item.index_gain.toFixed(1).replace(".", ",") + " indice";
        head.appendChild(cross);
      }
      box.appendChild(head);

      if (item.fix) {
        const fix = document.createElement("p");
        fix.className = "mb-1 small";
        fix.textContent = item.fix;
        box.appendChild(fix);
      }
      if (item.example) {
        const example = document.createElement("pre");
        example.className = "remediation-ex";
        example.textContent = item.example;
        box.appendChild(example);
      }
      if (item.url) {
        const where = document.createElement("p");
        where.className = "mb-0 small text-muted";
        where.textContent = "Riferimento: " + item.url;
        box.appendChild(where);
      }
      list.appendChild(box);
    });
    block.hidden = false;
  }

  function renderSovBubble(comp) {
    const box = el("sov-bubble");
    box.textContent = "";
    const presence = comp.presence || {};
    const chunks = comp.chunks || {};
    const totale = comp.queries_total || 0;
    if (!totale || !Object.keys(presence).length) {
      return;
    }
    const svg = svgNode("svg", {
      viewBox: "0 0 420 190",
      class: "history-trend-svg",
      role: "img",
      "aria-label": "Mappa a bolle del posizionamento " +
        "competitivo: share of voice in orizzontale, query " +
        "coperte in verticale, corpus come ampiezza; i valori " +
        "sono nelle tabelle",
    });
    svg.appendChild(svgNode("line", {
      x1: 40, y1: 160, x2: 400, y2: 160,
      stroke: "#c3c2b7", "stroke-width": 1,
    }));
    svg.appendChild(svgNode("line", {
      x1: 40, y1: 20, x2: 40, y2: 160,
      stroke: "#c3c2b7", "stroke-width": 1,
    }));
    const massimo = Math.max(1,
      ...Object.values(chunks));
    comp.sites.forEach((host) => {
      const mine = host === comp.main;
      const x = 40 + 360 * (comp.share[host] || 0) / 100;
      const y = 160 - 140 * (presence[host] || 0) / totale;
      const r = 5 + 14 * Math.sqrt(
        (chunks[host] || 0) / massimo);
      const hue = mine ? "#186078" : "#6b7f83";
      svg.appendChild(svgNode("circle", {
        cx: x, cy: y, r: r, fill: hue, "fill-opacity": "0.55",
        stroke: hue,
      }));
      const text = svgNode("text", {
        x: x + r + 3, y: y + 3, "font-size": 10,
        fill: "#14272b",
      });
      text.textContent = host + (mine ? " (tuo)" : "");
      svg.appendChild(text);
    });
    box.appendChild(svg);
  }

  function renderCompetitive(comp) {
    const block = el("competitive-block");
    if (!comp) {
      block.hidden = true;
      return;
    }
    renderSovBubble(comp);
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
