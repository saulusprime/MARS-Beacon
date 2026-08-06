/* Percorso dei font per il fonts-loader di Bootstrap Italia.
   Deve essere valorizzato prima del caricamento del bundle. */
window.__PUBLIC_PATH__ = "vendor/bootstrap-italia/fonts";

/* Base dell'API (assetto separato, Fase 3 API-first). Vuota =
   stessa origine: il combinato mars_gui.py a zero configurazione.
   Quando il bundle statico e' servito da un'altra origine,
   indicare qui l'origine del server API (mars_api.py avviato con
   --cors su QUESTA origine), es. "https://api.esempio.it": la GUI
   passa all'accesso con token API personale (il cookie
   SameSite=Strict non viaggia tra origini). */
window.MARS_API_BASE = "";

/* Modalita' embed: true = la sola applicazione, senza header e
   footer, per un bundle dedicato all'iframe di una pagina gia'
   brandizzata. In alternativa (bundle unico) si attiva a runtime
   con ?embed=1 nella query string dell'iframe. */
window.MARS_EMBED = false;

