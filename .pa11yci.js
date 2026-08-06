/* Configurazione Pa11y (CI e locale).
   PA11Y_BASE   base URL della GUI (default http://127.0.0.1:8765)
   PA11Y_CHROME percorso di un Chrome/Chromium di sistema (opzionale;
                senza, Pa11y usa il Chromium impacchettato) */
"use strict";

const base = process.env.PA11Y_BASE || "http://127.0.0.1:8765";

const chromeLaunchConfig = {
  args: ["--no-sandbox", "--disable-dev-shm-usage"],
};
if (process.env.PA11Y_CHROME) {
  chromeLaunchConfig.executablePath = process.env.PA11Y_CHROME;
}

module.exports = {
  defaults: {
    standard: "WCAG2AA",
    timeout: 60000,
    wait: 500,
    chromeLaunchConfig: chromeLaunchConfig,
  },
  urls: [
    base + "/tos.html",
    base + "/accesso.html",
    base + "/accesso.html?embed=1",
    {
      /* Configurazione da autenticati: registrazione
         sull'accesso e redirect alla pagina dedicata (P5). */
      url: base + "/accesso.html?vista=autenticata",
      actions: [
        "set field #r-nome to Utente Test",
        "set field #r-email to a11y@esempio.it",
        "set field #r-password to passwordtest",
        "check field #r-tos",
        "click element #register-form button[type=submit]",
        "wait for element #audit-form to be visible",
      ],
    },
    {
      /* Scansione senza job: ogni URL Pa11y ha la sua sessione,
         quindi si registra un account dedicato e si naviga. */
      url: base + "/accesso.html?vista=scansione",
      actions: [
        "set field #r-nome to Utente Test",
        "set field #r-email to a11y-scan@esempio.it",
        "set field #r-password to passwordtest",
        "check field #r-tos",
        "click element #register-form button[type=submit]",
        "wait for element #audit-form to be visible",
        "navigate to " + base + "/scansione.html",
        "wait for element #no-job to be visible",
      ],
    },
  ],
};
