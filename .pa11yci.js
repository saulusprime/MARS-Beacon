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
    base + "/",
    base + "/?embed=1",
    {
      url: base + "/?vista=autenticata",
      actions: [
        "set field #r-nome to Utente Test",
        "set field #r-email to a11y@esempio.it",
        "set field #r-password to passwordtest",
        "check field #r-tos",
        "click element #register-form button[type=submit]",
        "wait for element #config-section to be visible",
      ],
    },
  ],
};
