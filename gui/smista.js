/* Smistatore della GUI a pagine (P5).

   index.html non è più l'applicazione: verifica lo stato di
   accesso su /api/me e reindirizza alla pagina giusta —
   accesso.html da anonimi, configurazione.html da autenticati.
   La modalità embed (?embed=1) viene propagata. Stessa base API
   configurabile del bundle (config.js, MARS_API_BASE) e stesso
   token dell'accesso cross-origin (localStorage). */
(function () {
  "use strict";

  var base = (window.MARS_API_BASE || "").replace(/\/+$/, "");
  var embed = window.MARS_EMBED === true ||
    /(?:^|[?&])embed=1(?:&|$)/.test(window.location.search);
  if (embed) { document.body.classList.add("mars-embed"); }
  var coda = embed ? "?embed=1" : "";

  function vai(pagina) {
    window.location.replace(pagina + coda);
  }

  var token = "";
  try {
    token = window.localStorage.getItem("mars_api_token") || "";
  } catch (err) { /* niente persistenza */ }

  var opzioni = { credentials: "include" };
  if (token) {
    opzioni.headers = { Authorization: "Bearer " + token };
  }
  window.fetch((base ? base + "/" : "") + "api/me", opzioni)
    .then(function (r) { return r.json(); })
    .then(function (info) {
      vai(info.authenticated
        ? "configurazione.html" : "accesso.html");
    })
    .catch(function () { vai("accesso.html"); });
})();
