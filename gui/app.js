/* Logica della GUI di mars_audit.py.
   Vanilla JS, nessuna dipendenza oltre al bundle Bootstrap Italia.
   Tutto il contenuto dinamico è inserito con textContent: i dati
   provengono dal sito auditato e non vanno mai interpretati come HTML. */

"use strict";

(function () {
  /* ------- assetto separato (Fase 3 API-first) -------
     API_BASE vuota = stessa origine (combinato mars_gui.py);
     valorizzata in config.js quando il bundle statico vive su
     un'altra origine. Cross-origin il cookie SameSite=Strict non
     viaggia: ci si autentica con un token API personale
     (Authorization: Bearer), l'avanzamento usa il polling (l'SSE
     non porta header) e i download passano da fetch+blob. */
  const API_BASE = (window.MARS_API_BASE || "")
    .replace(/\/+$/, "");
  const REMOTE_API = API_BASE !== "";
  let apiToken = "";
  try {
    apiToken = window.localStorage.getItem("mars_api_token") || "";
  } catch (err) { /* storage non disponibile */ }

  function apiUrl(path) {
    return REMOTE_API ? API_BASE + "/" + path : path;
  }

  function apiFetch(path, options) {
    const opts = options || {};
    if (apiToken) {
      opts.headers = opts.headers || {};
      opts.headers.Authorization = "Bearer " + apiToken;
    }
    return fetch(apiUrl(path), opts);
  }

  /* Anno corrente nella barra del footer (stesso comportamento
     del sito istituzionale, che aggiorna [data-year] via JS). */
  document.querySelectorAll("[data-year]").forEach(function (n) {
    n.textContent = String(new Date().getFullYear());
  });

  /* Il ciclo audit usa il modello a risorse (/api/v1/audits, job
     con id): l'id dell'ultimo job vive in localStorage cosi' il
     ricaricamento della pagina ripristina i risultati. Gli alias
     legacy /api/audit-status-cancel-events-report restano attivi
     sul server ma la GUI non li usa piu' (deprecazione dichiarata
     nella spec). */
  let jobId = "";
  try {
    jobId = window.localStorage.getItem("mars_job_id") || "";
  } catch (err) { /* niente persistenza */ }

  function setJobId(nuovo) {
    jobId = nuovo || "";
    try {
      if (jobId) {
        window.localStorage.setItem("mars_job_id", jobId);
      } else {
        window.localStorage.removeItem("mars_job_id");
      }
    } catch (err) { /* ignora */ }
  }

  /* Le rotte /api/v1 usano l'oggetto d'errore uniforme
     {code, key, message, params}; le legacy la stringa. */
  function messaggioErrore(data, fallback) {
    if (data && data.error) {
      if (typeof data.error === "string") { return data.error; }
      if (data.error.message) { return data.error.message; }
    }
    return fallback;
  }

  /* Nome di download suggerito per i link API (nell'assetto
     remoto il server non puo' imporlo: il blob e' anonimo). */
  function apiFileName(path) {
    if (path.indexOf("api/history/report") === 0) {
      const match = path.match(/id=(\d+)/);
      return "audit-" + (match ? match[1] : "n") + ".json";
    }
    const fmt = (path.match(/api\/report\/(\w+)/) || [])[1] || "";
    const ext = { html: "html", json: "json", text: "txt",
                  md: "md", csv: "csv" }[fmt] || "bin";
    return (fmt === "csv" ? "rilievi-mars." : "referto-mars.") +
      ext;
  }

  /* Link a un endpoint API: href normale in stessa origine; con
     token il download passa da fetch+blob (il Bearer non viaggia
     negli href). */
  function bindApiLink(link, path) {
    link.href = apiUrl(path);
    if (link._marsClick) {
      link.removeEventListener("click", link._marsClick);
      link._marsClick = null;
    }
    if (!apiToken) { return; }
    const gestore = (ev) => {
      if (link.classList.contains("disabled")) { return; }
      ev.preventDefault();
      apiFetch(path)
        .then((r) => (r.ok ? r.blob() : Promise.reject(r.status)))
        .then((blob) => {
          const url = URL.createObjectURL(blob);
          if (link.target === "_blank") {
            window.open(url, "_blank", "noopener");
          } else {
            const ancora = document.createElement("a");
            ancora.href = url;
            ancora.download = apiFileName(path);
            document.body.appendChild(ancora);
            ancora.click();
            ancora.remove();
          }
          window.setTimeout(
            () => URL.revokeObjectURL(url), 60000);
        })
        .catch(() => {});
    };
    link._marsClick = gestore;
    link.addEventListener("click", gestore);
  }

  function adaptStaticApiLinks() {
    if (!apiToken && !REMOTE_API) { return; }
    document.querySelectorAll('a[href^="api/"]').forEach((a) => {
      bindApiLink(a, a.getAttribute("href"));
    });
  }
  const AREAS = [
    "Tecnica",
    "Lessicale (BM25)",
    "Semantica (vettoriale)",
    "Dati strutturati",
    "Simulazione RRF",
    "Performance (Lighthouse)",
  ];

  const SEVERITIES = {
    critical: { label: "Critico", cls: "badge-sev-critical", mark: "✕" },
    warning: { label: "Avvertenza", cls: "badge-sev-warning", mark: "!" },
    info: { label: "Informazione", cls: "badge-sev-info", mark: "i" },
    ok: { label: "OK", cls: "badge-sev-ok", mark: "✓" },
  };
  const SEV_ORDER = { critical: 0, warning: 1, info: 2, ok: 3 };

  /* Tipologie MARS: chiave = valore del campo "pillar" dei rilievi
     (dal core), suffisso = parte finale degli id delle sezioni e
     dei contenitori findings-acc-*. AREA_PILLAR e' il pilastro di
     default dell'area (il core puo' deviare i singoli rilievi,
     es. sicurezza dentro l'area tecnica). */
  const PILLARS = [
    { key: "meta-fusion", suffix: "meta" },
    { key: "accessibility", suffix: "access" },
    { key: "ranking", suffix: "rank" },
    { key: "security", suffix: "sec" },
  ];
  const AREA_PILLAR = {
    "Tecnica": "accessibility",
    "Lessicale (BM25)": "ranking",
    "Semantica (vettoriale)": "ranking",
    "Dati strutturati": "ranking",
    "Simulazione RRF": "meta-fusion",
  };
  const RESULT_SECTIONS = [
    "results-section", "pillar-meta-section",
    "pillar-access-section", "pillar-rank-section",
    "pillar-sec-section",
  ];

  function pillarOf(finding) {
    return finding.pillar || AREA_PILLAR[finding.area] || "ranking";
  }

  function setResultsHidden(hidden) {
    RESULT_SECTIONS.forEach((id) => { el(id).hidden = hidden; });
  }

  const PRESETS_KEY = "seo_rrf_presets";  /* chiave storica: conserva i preset salvati prima del rename */
  const PRESET_FIELDS = [
    "f-url", "f-max-pages", "f-delay", "f-max-body", "f-retries",
    "f-workers", "f-render", "f-market", "f-judge",
    "f-search-check",
    "f-lighthouse", "f-lighthouse-device", "f-lighthouse-pages",
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
    ["f-lighthouse-pages", "e-lighthouse-pages"],
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
    apiFetch("api/citations/events", {
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
  ["dl-html", "dl-json", "dl-text", "dl-md", "dl-csv",
   "open-report"].forEach((id) => {
    el(id).addEventListener("click", (event) => {
      if (!jobId || !me || !me.profile_complete) {
        event.preventDefault();
      }
    });
  });
  el("preset-save").addEventListener("click", savePreset);
  el("preset-load").addEventListener("click", loadPreset);
  el("preset-delete").addEventListener("click", deletePreset);
  refreshPresetSelect();
  bindTokenLogin();
  adaptStaticApiLinks();
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
    return apiFetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }).then((r) => r.json().then(
      (data) => ({ status: r.status, data })));
  }

  function bindTokenLogin() {
    if (REMOTE_API) {
      el("token-login").hidden = false;
      el("password-login").hidden = true;
    }
    el("token-form").addEventListener("submit", (ev) => {
      ev.preventDefault();
      const valore = el("t-token").value.trim();
      if (!valore) {
        showAuthError("Inserisci un token API.");
        return;
      }
      apiToken = valore;
      try {
        window.localStorage.setItem("mars_api_token", valore);
      } catch (err) { /* niente persistenza */ }
      apiFetch("api/me")
        .then((r) => r.json())
        .then((info) => {
          if (info.authenticated) {
            el("t-token").value = "";
            adaptStaticApiLinks();
            applyAuth(info.user);
          } else {
            apiToken = "";
            try {
              window.localStorage.removeItem("mars_api_token");
            } catch (err) { /* ignora */ }
            showAuthError("Token non valido o revocato.");
          }
        })
        .catch(() => showAuthError(
          "Server API non raggiungibile."));
    });
  }

  function refreshAuth() {
    apiFetch("api/me")
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
      setResultsHidden(true);
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
    if (apiToken) {
      apiToken = "";
      try {
        window.localStorage.removeItem("mars_api_token");
      } catch (err) { /* ignora */ }
    }
    postJson("api/logout", {}).finally(() => applyAuth(null));
  }

  /* ---------------- storico degli audit ---------------- */

  function loadHistory() {
    if (!me) {
      return;
    }
    apiFetch("api/history")
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
        bindApiLink(link, "api/history/report?id=" + run.id +
          "&download=1");
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
    apiFetch("api/history/compare?a=" + a + "&b=" + b)
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
    const voci = Object.entries(delta.scores || {});
    (delta.lighthouse || []).forEach((c) => {
      voci.push(["Lighthouse " + c.title, c.delta]);
    });
    voci.forEach(([area, value], index) => {
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
    apiFetch("api/citations")
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
    apiFetch("api/v1/audits/" + jobId,
             { method: "DELETE" }).catch(() => {
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
    if (!jobId) {
      return;
    }
    apiFetch("api/v1/audits/" + jobId)
      .then((r) => r.json())
      .then((snap) => {
        if (!running && snap.state === "done" &&
            snap.summary && snap.summary.site) {
          renderLog(snap.log || []);
          el("progress-anim").hidden = true;
          el("progress-section").hidden = false;
          setOpen("sec-config", false);
          showResults(snap);
        } else if (!snap.state) {
          setJobId("");  // job sparito o di un altro utente
        }
      })
      .catch(() => { /* nessun audit precedente */ });
  }

  /* ---------------- ambiente ---------------- */

  function loadEnv() {
    apiFetch("api/env")
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
        if (env.search_check_available === false) {
          el("h-search-check").textContent =
            "Non disponibile sul server: " +
            env.search_check_reason + ". In auto l'ancora di " +
            "realtà viene semplicemente saltata.";
        }
        if (env.lighthouse_available === false) {
          el("h-lighthouse").textContent =
            "Non disponibile sul server: " +
            env.lighthouse_reason + ". In auto l'audit " +
            "Lighthouse viene semplicemente saltato.";
        } else if (env.lighthouse_version) {
          el("h-lighthouse").textContent =
            "Fork installato: " + env.lighthouse_version +
            ". Performance, accessibilità, SEO e best practice " +
            "nelle sezioni MARS.";
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
          " — mars_audit.py " + env.tool_version +
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
      lighthouse: el("f-lighthouse").value,
      lighthouse_device: el("f-lighthouse-device").value,
      lighthouse_pages: el("f-lighthouse-pages").valueAsNumber,
      search_check: el("f-search-check").value,
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
    apiFetch("api/v1/audits", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(config),
    })
      .then((r) => r.json().then((data) => ({ status: r.status, data })))
      .then(({ status, data }) => {
        if (status !== 202) {
          showFormError(messaggioErrore(
            data, "Avvio non riuscito."));
          return;
        }
        setJobId(data.id);
        running = true;
        lastPhase = "";
        setSubmitState(true);
        setResultsHidden(true);
        setOpen("sec-results", false);
        PILLARS.forEach((p) => {
          setOpen("sec-pillar-" + p.suffix, false);
        });
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
        "mars_gui.py sia in esecuzione."));
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
    if (window.EventSource && !apiToken) {
      /* con token Bearer l'SSE non puo' autenticarsi (niente
         header sugli EventSource): si va di polling, il ripiego
         gia' previsto dal protocollo. */
      try {
        events = new EventSource(
          apiUrl("api/v1/audits/" + jobId + "/events"));
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
      fail(messaggioErrore(
        snap, "Sessione scaduta: accedi di nuovo."));
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
    apiFetch("api/v1/audits/" + jobId)
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
      const riga = lines[i];
      /* Fasi numerate dell'audit piu' le righe di testa di
         Lighthouse (avvio, salto dichiarato, esito): quelle
         per pagina sono indentate e non vengono annunciate. */
      if (/^(\[\d+\/\d+\]|Lighthouse: )/.test(riga)) {
        if (riga !== lastPhase) {
          lastPhase = riga;
          el("announcer").textContent =
            riga.charAt(0) === "[" ? "Fase " + riga : riga;
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

  const REPORT_LINKS = {
    "dl-html": ["html", true], "dl-json": ["json", true],
    "dl-text": ["text", true], "dl-md": ["md", true],
    "dl-csv": ["csv", true], "open-report": ["html", false],
  };

  function setReportLinks() {
    Object.keys(REPORT_LINKS).forEach((id) => {
      const fmt = REPORT_LINKS[id][0];
      const scarica = REPORT_LINKS[id][1];
      bindApiLink(el(id), "api/v1/audits/" + jobId +
        "/report?format=" + fmt + (scarica ? "&download=1" : ""));
    });
  }

  function showResults(snap) {
    setReportLinks();
    renderMeta(snap.summary);
    renderHero(snap.summary);
    renderDelta((snap.summary || {}).delta);
    renderScores(snap.summary);
    renderLighthouseSummary(snap.summary);
    renderTopRilievi(snap.remediation || []);
    renderCitability(snap.summary || {});
    renderJudge((snap.summary || {}).judge,
      (snap.summary || {}).citability);
    renderFindings(snap.findings || [],
      (snap.summary || {}).delta);
    renderSurfaceMath((snap.summary || {}).surface_math);
    renderDepth((snap.summary || {}).depth_distribution);
    renderLinkGraph((snap.summary || {}).link_graph);
    renderRemediation(snap.remediation || []);
    renderRrf(snap.rrf || []);
    renderSearchCheck(snap.summary);
    renderCompetitive(snap.competitive);

    setResultsHidden(false);
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
    const voci = Object.entries(delta.scores || {});
    (delta.lighthouse || []).forEach((c) => {
      voci.push(["Lighthouse " + c.title, c.delta]);
    });
    voci.forEach(([area, value], index) => {
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
    /* Le aree assenti dai punteggi (es. Lighthouse spento) non
       generano righe: "n/d" resta per le aree analizzate senza
       punteggio. */
    const rows = AREAS
      .map((area, areaIndex) =>
        [area, summary.scores[area], areaIndex])
      .filter((riga) => riga[1] !== undefined);
    rows.push(["Punteggio complessivo", summary.overall, -1]);

    rows.forEach(([label, value, areaIndex], index) => {
      const isArea = areaIndex >= 0;
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
        name.addEventListener("click", () => openArea(areaIndex));
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

  /* Sintesi Lighthouse: categorie accanto ai punteggi di area e
     pannello Core Web Vitals con soglie — sempre testo + simbolo,
     mai solo colore; la nota dichiara che sono dati di
     laboratorio, non dati reali degli utenti. */
  function renderLighthouseSummary(summary) {
    const box = el("lighthouse-summary");
    box.textContent = "";
    const lh = summary.lighthouse;
    if (!lh) { return; }

    const head = document.createElement("h4");
    head.className = "h6";
    head.textContent = "Audit Lighthouse";
    box.appendChild(head);

    if (lh.status !== "ok") {
      const skip = document.createElement("p");
      skip.className = "small text-muted mb-0";
      skip.textContent = "Non eseguito: " + (lh.reason || "");
      box.appendChild(skip);
      return;
    }

    const meta = document.createElement("p");
    meta.className = "small text-muted mb-2";
    meta.textContent = "Eseguito su " +
      (lh.pages || []).length + " pagina/e (" + lh.device + ")" +
      (lh.fork ? ", fork " + lh.fork : "") + ".";
    box.appendChild(meta);

    const cats = document.createElement("ul");
    cats.className = "lh-cats";
    (lh.categories || []).forEach((c) => {
      const tono = c.score >= 90 ? "good"
        : (c.score >= 50 ? "mid" : "bad");
      const mark = c.score >= 90 ? "✓"
        : (c.score >= 50 ? "!" : "✕");
      const li = document.createElement("li");
      li.className = "lh-cat lh-" + tono;
      li.textContent = mark + " " + c.title + " " +
        c.score + "/100";
      cats.appendChild(li);
    });
    box.appendChild(cats);

    if ((lh.metrics || []).length) {
      const panel = document.createElement("div");
      panel.className = "cwv-panel";
      lh.metrics.forEach((m) => {
        const tono = m.verdict === "buono" ? "good"
          : (m.verdict === "scarso" ? "bad" : "mid");
        const mark = m.verdict === "buono" ? "✓"
          : (m.verdict === "scarso" ? "✕" : "!");
        const tile = document.createElement("div");
        tile.className = "cwv-tile cwv-" + tono;
        const label = document.createElement("span");
        label.className = "cwv-label";
        label.textContent = m.label;
        tile.appendChild(label);
        const value = document.createElement("b");
        value.textContent = m.display || String(m.value);
        tile.appendChild(value);
        const verdict = document.createElement("span");
        verdict.className = "cwv-verdict";
        verdict.textContent = mark + " " + m.verdict;
        tile.appendChild(verdict);
        panel.appendChild(tile);
      });
      box.appendChild(panel);

      const nota = document.createElement("p");
      nota.className = "small text-muted mb-0";
      nota.textContent = "Valore peggiore fra le pagine " +
        "esaminate. Dati di laboratorio (ambiente simulato), " +
        "non dati reali degli utenti (CrUX); l'INP reale non è " +
        "misurabile in laboratorio: il TBT è il suo proxy.";
      box.appendChild(nota);
    }
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
    /* Apre i rilievi dell'area nella sezione MARS di pertinenza
       (il pilastro di default dell'area). */
    const pillar = PILLARS.find(
      (p) => p.key === AREA_PILLAR[AREAS[index]]);
    if (!pillar) { return; }
    const body = document.getElementById(
      "acc-c-" + pillar.suffix + "-" + index);
    if (!body) { return; }
    setOpen("sec-pillar-" + pillar.suffix, true);
    const toggle = document.querySelector(
      "#acc-h-" + pillar.suffix + "-" + index + " button");
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
    /* Origine dichiarata: i rilievi del fork Lighthouse portano il
       badge; i rilievi MARS confermati dalla deduplica (params
       lh_confirm) portano la conferma incrociata. */
    if ((finding.key || "").indexOf("lh.") === 0) {
      const origine = document.createElement("span");
      origine.className = "badge badge-lh ms-2";
      origine.textContent = "Lighthouse";
      head.appendChild(origine);
    } else if ((finding.params || {}).lh_confirm) {
      const conferma = document.createElement("span");
      conferma.className = "badge badge-lh ms-2";
      conferma.textContent = "confermato da Lighthouse";
      head.appendChild(conferma);
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
    /* Distribuisce i rilievi nelle quattro sezioni MARS (campo
       "pillar" del core, con ripiego sul pilastro dell'area) e,
       dentro ciascuna, li raggruppa per area in una fisarmonica. */
    const newKeys = new Set(
      ((delta || {}).new || []).map(normFindingKey));

    PILLARS.forEach((pillar) => {
      const acc = el("findings-acc-" + pillar.suffix);
      acc.textContent = "";
      let empty = true;

      AREAS.forEach((area, index) => {
        const subset = findings
          .filter((f) => f.area === area
            && pillarOf(f) === pillar.key)
          .sort((a, b) =>
            SEV_ORDER[a.severity] - SEV_ORDER[b.severity]);
        if (!subset.length) {
          return;
        }
        empty = false;

        const item = document.createElement("div");
        item.className = "accordion-item";

        const headId = "acc-h-" + pillar.suffix + "-" + index;
        const bodyId = "acc-c-" + pillar.suffix + "-" + index;

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

      if (empty) {
        const none = document.createElement("p");
        none.className = "small text-muted";
        none.textContent =
          "Nessun rilievo per questa tipologia.";
        acc.appendChild(none);
      }
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

  /* Grafo dei link interattivo: zoom (rotella o pulsanti), pan
     (trascina lo sfondo), trascinamento dei nodi per districare,
     evidenziazione del vicinato al passaggio/focus con dettagli
     nella regione di stato. Layout iniziale calcolato dal core. */
  const graphView = { vb: null, base: null };

  function graphApplyView(svg) {
    svg.setAttribute("viewBox", graphView.vb.join(" "));
  }

  function graphZoom(svg, factor, cx, cy) {
    const [x, y, w, h] = graphView.vb;
    const nw = Math.max(60, Math.min(graphView.base[2] * 3,
      w * factor));
    const nh = nw * graphView.base[3] / graphView.base[2];
    const fx = cx === undefined ? x + w / 2 : cx;
    const fy = cy === undefined ? y + h / 2 : cy;
    graphView.vb = [fx - (fx - x) * nw / w,
      fy - (fy - y) * nh / h, nw, nh];
    graphApplyView(svg);
  }

  function renderLinkGraph(graph) {
    /* Motore evoluto (v2.30.0): simulazione a forze viva che si
       sveglia al trascinamento, vista ad anelli di profondita',
       frecce direzionali, evidenziazione bloccabile col clic
       (Esc libera), ricerca per percorso. prefers-reduced-motion
       spegne ogni animazione. */
    const block = el("graph-block");
    const box = el("graph-svg");
    box.textContent = "";
    if (!graph || !graph.links || !graph.links.length) {
      block.hidden = true;
      return;
    }
    el("graph-intro").textContent =
      "Ogni cerchio è una pagina; mostrate " +
      graph.nodes.length + " pagine su " + graph.total + ".";

    const ridotto = window.matchMedia && window.matchMedia(
      "(prefers-reduced-motion: reduce)").matches;
    graphView.base = [0, 0, graph.width, graph.height];
    graphView.vb = graphView.base.slice();
    const svg = svgNode("svg", {
      viewBox: graphView.vb.join(" "),
      class: "history-trend-svg graph-canvas",
      role: "img",
      "aria-label": "Grafo interattivo dei link interni: " +
        "orfane e profondità sono nei rilievi dell'area tecnica",
    });

    const defs = document.createElementNS(
      "http://www.w3.org/2000/svg", "defs");
    defs.innerHTML =
      '<marker id="g-arr" viewBox="0 0 8 8" refX="7" refY="4"' +
      ' markerWidth="5.5" markerHeight="5.5"' +
      ' orient="auto-start-reverse">' +
      '<path d="M0 0L8 4L0 8z" fill="#d8d8d2"/></marker>' +
      '<marker id="g-arr-hi" viewBox="0 0 8 8" refX="7"' +
      ' refY="4" markerWidth="5.5" markerHeight="5.5"' +
      ' orient="auto-start-reverse">' +
      '<path d="M0 0L8 4L0 8z" fill="#186078"/></marker>';
    svg.appendChild(defs);

    const N = graph.nodes.length;
    const pos = graph.nodes.map((n) => [n.x, n.y]);
    const vel = graph.nodes.map(() => [0, 0]);
    const raggi = graph.nodes.map((n) =>
      Math.min(15, 5 + 1.8 * Math.sqrt(n.incoming)));
    const lati = graph.links.map((l) => [l.source, l.target]);
    const vicini = graph.nodes.map(() => []);
    const uscita = graph.nodes.map(() => 0);
    lati.forEach((st) => {
      vicini[st[0]].push(st[1]);
      vicini[st[1]].push(st[0]);
      uscita[st[0]] += 1;
    });

    const edgeEls = lati.map(() => {
      const line = svgNode("line", {
        stroke: "#d8d8d2", "stroke-width": 1,
        "marker-end": "url(#g-arr)",
      });
      svg.appendChild(line);
      return line;
    });
    const mostraTutte = graph.nodes.length <= 20;
    const top = graph.nodes.slice()
      .sort((m, n) => (n.home - m.home) ||
        (n.incoming - m.incoming))
      .slice(0, 12).map((n) => n.url);

    const nodeEls = [];
    const labelEls = [];
    graph.nodes.forEach((node, i) => {
      const problematico = node.depth === null || node.depth > 3;
      const hue = node.home ? "#186078"
        : problematico ? "#9a6a00" : "#1c6b45";
      const circle = svgNode("circle", {
        r: raggi[i], fill: hue, "fill-opacity": "0.8",
        stroke: hue, tabindex: "0", role: "img",
        "aria-label": node.label + ": " + node.incoming +
          " link in ingresso, " + uscita[i] + " in uscita, " +
          (node.depth === null
            ? "solo da sitemap" : node.depth + " click"),
        class: "graph-node",
      });
      svg.appendChild(circle);
      nodeEls.push(circle);
      const text = svgNode("text", {
        "font-size": 12, fill: "#14272b", stroke: "#ffffff",
        "stroke-width": 3, "paint-order": "stroke",
        "pointer-events": "none",
      });
      text.textContent = node.label.slice(0, 30);
      if (!mostraTutte && top.indexOf(node.url) === -1) {
        text.setAttribute("visibility", "hidden");
      }
      svg.appendChild(text);
      labelEls.push(text);
    });

    function ridisegna() {
      for (let i = 0; i < N; i += 1) {
        nodeEls[i].setAttribute("cx", pos[i][0]);
        nodeEls[i].setAttribute("cy", pos[i][1]);
        labelEls[i].setAttribute("x", pos[i][0] + raggi[i] + 3);
        labelEls[i].setAttribute("y", pos[i][1] + 4);
      }
      lati.forEach((st, k) => {
        const dx = pos[st[1]][0] - pos[st[0]][0];
        const dy = pos[st[1]][1] - pos[st[0]][1];
        const lun = Math.sqrt(dx * dx + dy * dy) || 1;
        const acc = (raggi[st[1]] + 3) / lun;
        edgeEls[k].setAttribute("x1", pos[st[0]][0]);
        edgeEls[k].setAttribute("y1", pos[st[0]][1]);
        edgeEls[k].setAttribute("x2", pos[st[1]][0] - dx * acc);
        edgeEls[k].setAttribute("y2", pos[st[1]][1] - dy * acc);
      });
    }
    ridisegna();

    let vista = "forza";
    let blocco = null;
    let caldo = 0;
    let anim = null;
    function passo() {
      let energia = 0;
      for (let i = 0; i < N; i += 1) {
        for (let j = i + 1; j < N; j += 1) {
          const dx = pos[j][0] - pos[i][0];
          const dy = pos[j][1] - pos[i][1];
          const d2 = dx * dx + dy * dy + 0.01;
          const d = Math.sqrt(d2);
          const f = 900 / d2;
          vel[i][0] -= f * dx / d;
          vel[i][1] -= f * dy / d;
          vel[j][0] += f * dx / d;
          vel[j][1] += f * dy / d;
        }
      }
      lati.forEach((st) => {
        const ex = pos[st[1]][0] - pos[st[0]][0];
        const ey = pos[st[1]][1] - pos[st[0]][1];
        const lun = Math.sqrt(ex * ex + ey * ey) || 1;
        const tira = (lun - 70) * 0.02;
        vel[st[0]][0] += tira * ex / lun;
        vel[st[0]][1] += tira * ey / lun;
        vel[st[1]][0] -= tira * ex / lun;
        vel[st[1]][1] -= tira * ey / lun;
      });
      for (let i = 0; i < N; i += 1) {
        if (i === blocco) { vel[i] = [0, 0]; continue; }
        vel[i][0] += (graph.width / 2 - pos[i][0]) * 0.002;
        vel[i][1] += (graph.height / 2 - pos[i][1]) * 0.002;
        vel[i][0] *= 0.82;
        vel[i][1] *= 0.82;
        pos[i][0] += vel[i][0];
        pos[i][1] += vel[i][1];
        energia += vel[i][0] * vel[i][0] +
          vel[i][1] * vel[i][1];
      }
      ridisegna();
      caldo -= 1;
      if (vista === "forza" && !ridotto &&
          (energia > 0.4 || caldo > 0)) {
        anim = requestAnimationFrame(passo);
      } else {
        anim = null;
      }
    }
    function scalda(giri) {
      caldo = Math.max(caldo, giri || 30);
      if (vista !== "forza" || ridotto) { return; }
      if (anim === null) { anim = requestAnimationFrame(passo); }
    }

    let guide = [];
    function togliGuide() {
      guide.forEach((g) => g.remove());
      guide = [];
    }
    function transizione(dest) {
      if (ridotto) {
        dest.forEach((p, i) => { pos[i] = p; });
        ridisegna();
        return;
      }
      const da = pos.map((p) => p.slice());
      let t0 = null;
      const quadro = (ts) => {
        if (t0 === null) { t0 = ts; }
        const q = Math.min(1, (ts - t0) / 350);
        const morbo = q * (2 - q);
        for (let i = 0; i < N; i += 1) {
          pos[i][0] = da[i][0] + (dest[i][0] - da[i][0]) * morbo;
          pos[i][1] = da[i][1] + (dest[i][1] - da[i][1]) * morbo;
        }
        ridisegna();
        if (q < 1) { requestAnimationFrame(quadro); }
      };
      requestAnimationFrame(quadro);
    }
    function versoAnelli() {
      let maxD = 0;
      graph.nodes.forEach((n) => {
        if (n.depth !== null && n.depth > maxD) {
          maxD = n.depth;
        }
      });
      const esterno = maxD + 1;
      const cx = graph.width / 2;
      const cy = graph.height / 2;
      const rmax = Math.min(graph.width, graph.height) / 2 - 24;
      const raggio = (d) => d / (esterno + 0.5) * rmax;
      const perAnello = {};
      graph.nodes.forEach((n, i) => {
        const d = n.depth === null ? esterno : n.depth;
        (perAnello[d] = perAnello[d] || []).push(i);
      });
      const dest = new Array(N);
      Object.keys(perAnello).forEach((chiave) => {
        const anello = +chiave;
        const gruppo = perAnello[chiave];
        gruppo.sort((a, b) =>
          Math.atan2(pos[a][1] - cy, pos[a][0] - cx) -
          Math.atan2(pos[b][1] - cy, pos[b][0] - cx));
        gruppo.forEach((n, idx) => {
          if (anello === 0) { dest[n] = [cx, cy]; return; }
          const ang = -Math.PI / 2 +
            idx * 2 * Math.PI / gruppo.length;
          dest[n] = [cx + raggio(anello) * Math.cos(ang),
            cy + raggio(anello) * Math.sin(ang)];
        });
      });
      togliGuide();
      const primo = svg.querySelector("line");
      for (let g = 1; g <= esterno; g += 1) {
        const cerchio = svgNode("circle", {
          cx: cx, cy: cy, r: raggio(g), fill: "none",
          stroke: g === 3 ? "#9a6a00" : "#d8d8d2",
          "stroke-width": g === 3 ? 1.4 : 0.7,
          "stroke-dasharray": "4 5",
          "pointer-events": "none",
        });
        svg.insertBefore(cerchio, primo);
        guide.push(cerchio);
      }
      transizione(dest);
    }
    function impostaVista(nome) {
      if (vista === nome) { return; }
      vista = nome;
      el("graph-vforza").setAttribute("aria-pressed",
        nome === "forza" ? "true" : "false");
      el("graph-vanelli").setAttribute("aria-pressed",
        nome === "anelli" ? "true" : "false");
      if (nome === "anelli") {
        if (anim !== null) {
          cancelAnimationFrame(anim);
          anim = null;
        }
        versoAnelli();
      } else {
        togliGuide();
        scalda(80);
        if (ridotto) { ridisegna(); }
      }
    }
    el("graph-vforza").onclick = () => impostaVista("forza");
    el("graph-vanelli").onclick = () => impostaVista("anelli");

    let fisso = null;
    function evidenzia(i) {
      nodeEls.forEach((c, j) => c.setAttribute("fill-opacity",
        j === i || vicini[i].indexOf(j) !== -1
          ? "0.95" : "0.25"));
      lati.forEach((st, k) => {
        const suo = st[0] === i || st[1] === i;
        edgeEls[k].setAttribute("stroke",
          suo ? "#186078" : "#e8e8e4");
        edgeEls[k].setAttribute("stroke-width", suo ? 2 : 1);
        edgeEls[k].setAttribute("marker-end",
          suo ? "url(#g-arr-hi)" : "url(#g-arr)");
      });
      labelEls[i].setAttribute("visibility", "visible");
      const node = graph.nodes[i];
      el("graph-info").textContent = node.label + " — " +
        node.incoming + " link in ingresso, " + uscita[i] +
        " in uscita, " +
        (node.depth === null ? "raggiungibile solo da sitemap"
          : node.depth + " click dalla home") + "." +
        (fisso === i
          ? " Evidenziazione bloccata: Esc per liberarla." : "");
    }
    function spegni() {
      if (fisso !== null) { evidenzia(fisso); return; }
      nodeEls.forEach((c) =>
        c.setAttribute("fill-opacity", "0.8"));
      lati.forEach((_st, k) => {
        edgeEls[k].setAttribute("stroke", "#d8d8d2");
        edgeEls[k].setAttribute("stroke-width", 1);
        edgeEls[k].setAttribute("marker-end", "url(#g-arr)");
      });
      labelEls.forEach((t, j) => {
        if (!mostraTutte &&
            top.indexOf(graph.nodes[j].url) === -1) {
          t.setAttribute("visibility", "hidden");
        }
      });
      el("graph-info").textContent =
        "Seleziona un nodo (mouse o Tab) per i dettagli.";
    }
    box.onkeydown = (event) => {
      if (event.key === "Escape" && fisso !== null) {
        fisso = null;
        spegni();
      }
    };
    const ricerca = el("graph-search");
    ricerca.value = "";
    ricerca.oninput = () => {
      const testo = ricerca.value.trim().toLowerCase();
      if (!testo) { spegni(); return; }
      let trovate = 0;
      nodeEls.forEach((c, i) => {
        const bene = graph.nodes[i].label
          .toLowerCase().indexOf(testo) !== -1;
        if (bene) { trovate += 1; }
        c.setAttribute("fill-opacity", bene ? "0.95" : "0.15");
        labelEls[i].setAttribute("visibility",
          bene ? "visible" : "hidden");
      });
      el("graph-info").textContent = trovate +
        " pagina/e corrispondono a «" +
        ricerca.value.trim() + "».";
    };

    function svgPoint(event) {
      const rect = svg.getBoundingClientRect();
      const [x, y, w, h] = graphView.vb;
      return [x + (event.clientX - rect.left) / rect.width * w,
        y + (event.clientY - rect.top) / rect.height * h];
    }

    let dragNode = null;
    let panFrom = null;
    let mosso = false;
    nodeEls.forEach((circle, i) => {
      circle.addEventListener("pointerenter", () => {
        if (dragNode === null && fisso === null) {
          evidenzia(i);
        }
      });
      circle.addEventListener("focus", () => {
        if (fisso === null) { evidenzia(i); }
      });
      circle.addEventListener("pointerleave", () => {
        if (dragNode === null) { spegni(); }
      });
      circle.addEventListener("blur", () => spegni());
      circle.addEventListener("click", (event) => {
        event.stopPropagation();
        if (mosso) { mosso = false; return; }
        fisso = fisso === i ? null : i;
        if (fisso === null) { spegni(); } else { evidenzia(i); }
      });
      circle.addEventListener("pointerdown", (event) => {
        dragNode = i;
        blocco = i;
        mosso = false;
        circle.setPointerCapture(event.pointerId);
        event.preventDefault();
        event.stopPropagation();
      });
      circle.addEventListener("pointermove", (event) => {
        if (dragNode !== i) { return; }
        const [px, py] = svgPoint(event);
        pos[i][0] = px;
        pos[i][1] = py;
        mosso = true;
        if (vista === "forza") { scalda(20); }
        ridisegna();
      });
      circle.addEventListener("pointerup", () => {
        dragNode = null;
        blocco = null;
        if (vista === "forza" && mosso) { scalda(50); }
      });
    });
    svg.addEventListener("click", (event) => {
      if (event.target === svg && fisso !== null) {
        fisso = null;
        spegni();
      }
    });
    svg.addEventListener("pointerdown", (event) => {
      if (event.target === svg) {
        panFrom = [event.clientX, event.clientY,
          graphView.vb.slice()];
        svg.setPointerCapture(event.pointerId);
      }
    });
    svg.addEventListener("pointermove", (event) => {
      if (!panFrom) { return; }
      const rect = svg.getBoundingClientRect();
      const scala = graphView.vb[2] / rect.width;
      graphView.vb = [
        panFrom[2][0] - (event.clientX - panFrom[0]) * scala,
        panFrom[2][1] - (event.clientY - panFrom[1]) * scala,
        panFrom[2][2], panFrom[2][3]];
      graphApplyView(svg);
    });
    svg.addEventListener("pointerup", () => { panFrom = null; });
    svg.addEventListener("wheel", (event) => {
      event.preventDefault();
      const [cx, cy] = svgPoint(event);
      graphZoom(svg, event.deltaY > 0 ? 1.2 : 1 / 1.2, cx, cy);
    }, { passive: false });

    el("graph-zoom-in").onclick = () => graphZoom(svg, 1 / 1.4);
    el("graph-zoom-out").onclick = () => graphZoom(svg, 1.4);
    el("graph-reset").onclick = () => {
      graphView.vb = graphView.base.slice();
      graphApplyView(svg);
    };

    box.appendChild(svg);
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

  /* Ancora di realta' (Brave Search): posizione reale del sito
     sulle query dell'audit, accanto al consenso RRF simulato.
     Con salto dichiarato mostra il motivo; senza dati (spenta)
     il blocco resta nascosto. */
  function renderSearchCheck(summary) {
    const block = el("search-check-block");
    const sc = (summary || {}).search_check;
    if (!sc) {
      block.hidden = true;
      return;
    }
    block.hidden = false;
    const intro = el("search-check-intro");
    const tbody = el("search-check-table").querySelector("tbody");
    tbody.textContent = "";
    el("search-check-note").textContent = sc.note || "";
    if (sc.status !== "ok") {
      intro.textContent = "Non eseguita: " + (sc.reason || "");
      return;
    }
    const interrogate = sc.queries || [];
    intro.textContent = "Sito trovato per " + (sc.found || 0) +
      " query su " + interrogate.length + ": posizione reale nei " +
      "primi " + sc.top_n + " risultati, accanto al consenso " +
      "della simulazione RRF.";
    interrogate.forEach((q) => {
      const tr = document.createElement("tr");
      const th = document.createElement("th");
      th.scope = "row";
      th.className = "fw-normal";
      th.textContent = q.query;
      tr.appendChild(th);
      const pos = document.createElement("td");
      if (q.error) {
        pos.textContent = "errore: " + q.error;
      } else if (q.position) {
        const forte = document.createElement("b");
        forte.textContent = "#" + q.position;
        pos.appendChild(forte);
      } else {
        pos.textContent = "assente dai primi " + sc.top_n;
      }
      tr.appendChild(pos);
      const rrf = document.createElement("td");
      rrf.textContent = String(q.rrf_consensus) +
        (q.rrf_covered ? "" : " (query non coperta)");
      tr.appendChild(rrf);
      tbody.appendChild(tr);
    });
  }
})();
