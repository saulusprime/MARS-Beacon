Progetto di integrazione di Lighthouse in MARS Audit
Nuovo nome di progetto MARS Beacon

https://github.com/saulusprime/lighthouse.git

Poiché Lighthouse esegue centinaia di micro-controlli (audit) specifici, la tabella è organizzata per **Macro-Categorie** e **Funzionalità dello Strumento**, elencando i controlli e le capacità più importanti che il tool offre.

### 📊 Tabella delle Funzionalità di Google Lighthouse

| Area / Categoria | Funzionalità / Audit Principali | Descrizione e Obiettivo |
| :--- | :--- | :--- |
| **🚀 Performance** | **Core Web Vitals (LCP, INP, CLS)** | Misura le metriche vitali di Google: caricamento dell'elemento più grande (LCP), reattività agli input (INP) e stabilità visiva (CLS). |
| | **First Contentful Paint (FCP)** | Misura il tempo impiegato dal browser per renderizzare il primo elemento di contenuto (testo o immagine). |
| | **Total Blocking Time (TBT)** | Misura il tempo totale in cui il thread principale è stato bloccato, impedendo l'interattività della pagina. |
| | **Speed Index** | Misura la velocità con cui i contenuti di una pagina vengono popolati visivamente durante il caricamento. |
| | **Ottimizzazione Risorse** | Identifica immagini non compresse, CSS/JS inutilizzati, e risorse che bloccano il rendering (render-blocking). |
| | **Ottimizzazione Server** | Suggerisce riduzioni del tempo di risposta del server (TTFB), caching efficiente e uso di CDN. |
| | **Animazioni e Transizioni** | Rileva animazioni non ottimizzate che causano un uso eccessivo della CPU o del layout. |
| **♿ Accessibilità** | **Contrasto dei Colori** | Verifica che il contrasto tra testo e sfondo sia sufficiente per utenti con disabilità visive. |
| | **Attributi ARIA** | Controlla che i ruoli, gli stati e le proprietà ARIA siano validi e utilizzati correttamente per gli screen reader. |
| | **Testi Alternativi (Alt)** | Assicura che tutte le immagini informative abbiano un attributo `alt` descrittivo. |
| | **Etichette per i Form** | Verifica che ogni elemento dei form (input, select) sia associato a un'etichetta (`<label>`) per l'accessibilità. |
| | **Ordine dei Titoli (Heading)** | Controlla che i tag di intestazione (`<h1>`, `<h2>`, ecc.) seguano un ordine gerarchico logico e non saltino livelli. |
| | **Attributo `lang`** | Verifica che il tag `<html>` abbia un attributo `lang` valido per aiutare gli screen reader con la pronuncia. |
| **🔍 SEO** | **Meta Description e Title** | Verifica che ogni pagina abbia un tag `<title>` unico e una `<meta name="description">` per i risultati di ricerca. |
| | **Mobile-Friendly (Viewport)** | Controlla la presenza del tag `<meta name="viewport">` per garantire l'adattabilità ai dispositivi mobili. |
| | **Link Descrittivi** | Evita link con testo generico come "clicca qui", suggerendo testi descrittivi per i crawler. |
| | **Link Crawlabili** | Verifica che i link non siano bloccati da `robots.txt` o `nofollow` in modo errato, permettendo l'indicizzazione. |
| | **Status Code HTTP** | Assicura che le pagine non restituiscano errori (es. 404, 500) o redirect a catena che danneggiano la SEO. |
| | **Dati Strutturati** | Verifica la validità dei dati strutturati (Schema.org) per l'ottenimento dei "rich snippet" su Google. |
| | **Dimensione Font Leggibili** | Controlla che la dimensione del testo sia almeno 12px per essere leggibile da mobile senza zoom. |
| **🛡️ Best Practices** | **Errori in Console** | Rileva errori JavaScript, avvisi di deprecazione o problemi di rete segnalati nella console del browser. |
| | **Utilizzo di HTTPS** | Verifica che l'intero sito sia servito tramite protocollo sicuro HTTPS. |
| | **Librerie Vulnerabili** | Scansiona le librerie JavaScript di terze parti cercando vulnerabilità di sicurezza note (CVE). |
| | **Aspect Ratio Immagini** | Controlla che le immagini abbiano attributi `width` e `height` per evitare scatti di layout (CLS). |
| | **Link Esterni Sicuri** | Verifica che i link a domini esterni usino `rel="noopener"` per prevenire vulnerabilità di sicurezza. |
| | **Doctype HTML** | Assicura che la pagina inizi con `<!DOCTYPE html>` per evitare la modalità "quirks" del browser. |
| **📱 PWA (Progressive Web App)** | **Manifest (`manifest.json`)** | Verifica la presenza e la correttezza del file manifest per permettere l'installazione dell'app. |
| | **Service Worker** | Controlla che un Service Worker sia registrato per abilitare funzionalità offline e push notification. |
| | **Funzionalità Offline** | Testa se la pagina fornisce una risposta (es. pagina offline personalizzata) quando la rete non è disponibile. |
| | **Icona e Theme Color** | Verifica la presenza di icone valide per la "Add to Home Screen" e la coerenza del colore del tema. |
| **⚙️ Funzionalità dello Strumento** | **Ambienti di Esecuzione** | Può essere eseguito tramite Chrome DevTools, CLI (riga di comando), modulo Node.js o come estensione. |
| | **Emulazione Mobile/Desktop** | Simula il caricamento della pagina su dispositivi mobili (con throttling di rete e CPU) o desktop. |
| | **Throttling (Limitazione)** | Simula reti lente (es. 3G/4G) e CPU rallentate per testare le performance in condizioni reali avverse. |
| | **Generazione Report** | Esporta i risultati in formati leggibili e integrabili: HTML, JSON, CSV. |
| | **Integrazione CI/CD** | Tramite CLI e moduli Node, può essere integrato in pipeline di sviluppo (es. GitHub Actions) per bloccare deploy con scarse performance. |
| | **Treemap Audit** | Fornisce una visualizzazione ad albero (Treemap) per analizzare il peso dei file JavaScript e delle risorse. |

### 💡 Note Importanti:
1. **Metriche in Evoluzione**: Google aggiorna costantemente Lighthouse. Ad esempio, nel 2024 il **FID** (First Input Delay) è stato ufficialmente sostituito dall'**INP** (Interaction to Next Paint) come metrica principale per la reattività.
2. **Punteggi (Scores)**: Per ogni categoria (Performance, Accessibilità, SEO, Best Practices), Lighthouse calcola un punteggio da **0 a 100**. Un punteggio di 90-100 è considerato "buono" (verde), 50-89 "da migliorare" (arancione) e 0-49 "scarso" (rosso).
3. **PWA**: Sebbene le PWA siano una categoria storica di Lighthouse, Google sta progressivamente spostando alcuni di questi controlli in tool dedicati, ma rimangono fondamentali per lo sviluppo di Web App moderne.