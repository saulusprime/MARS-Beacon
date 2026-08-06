# API di MARS Beacon — guida rapida

Il contratto completo è **generato dal registro delle rotte**
(`marsbeacon/api.py`) e servito da `GET /api/v1/openapi.json`
(snapshot golden in [openapi.json](openapi.json)); la
documentazione navigabile, con client di prova e snippet di
codice, è su **`GET /api/docs`** (Scalar vendorizzato, funziona
offline). Questa pagina è il percorso minimo con `curl`.

Due server, stesso motore (`marsbeacon/api.py`):

- **`mars_gui.py`** — il combinato statici+API a zero
  configurazione (porta 8765);
- **`mars_api.py`** — solo API (porta 8766; `--cors ORIGINE`
  ripetibile e `--max-audit N` per la concorrenza).

Autenticazione a doppio binario: **cookie di sessione** (HttpOnly,
SameSite=Strict — per il frontend sulla stessa origine) oppure
**token Bearer** (per client macchina e cross-origin, stesso
perimetro: slot orario di un audit per utente e download dei
referti riservato alla registrazione completa).

## 1. Account e token

```bash
BASE=http://127.0.0.1:8766

# registrazione (apre la sessione: cookie nel jar)
curl -s -c cookie.txt "$BASE/api/register" \
  -H 'Content-Type: application/json' \
  -d '{"nome": "Paola Rossi", "email": "paola@esempio.it",
       "password": "segretissima", "tos": true,
       "azienda": "Centro Esempio", "telefono": "0521 123456"}'

# token API personale (valore visibile SOLO in questa risposta;
# la gestione dei token richiede la sessione cookie)
curl -s -b cookie.txt "$BASE/api/v1/tokens" \
  -H 'Content-Type: application/json' \
  -d '{"label": "script di monitoraggio"}'
# -> {"ok": true, "id": 1, "label": "...", "token": "mars_..."}

TOKEN=mars_...   # da qui in poi basta il Bearer

# elenco (solo metadati) e revoca
curl -s -b cookie.txt "$BASE/api/v1/tokens"
curl -s -b cookie.txt -X DELETE "$BASE/api/v1/tokens/1"
```

## 2. Audit come job (modello a risorse)

```bash
# avvio: 202 con l'id del job. "soglie" e "lang" sono la parita'
# con --config e --lang della CLI; fail_under echeggia il gate
# nella sintesi (gate_passed).
curl -s "$BASE/api/v1/audits" \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"url": "https://esempio.it", "max_pages": 25,
       "lang": "en",
       "soglie": {"title_min": 25, "title_max": 70},
       "fail_under": 60}'
# -> {"ok": true, "id": "a1b2c3d4e5f6a7b8"}
ID=a1b2c3d4e5f6a7b8

# polling dello stato (snapshot: state, log, sintesi a fine audit)
curl -s "$BASE/api/v1/audits/$ID" \
  -H "Authorization: Bearer $TOKEN"

# oppure push via Server-Sent Events (chiuso allo stato terminale;
# con curl serve -N per disattivare il buffering)
curl -sN "$BASE/api/v1/audits/$ID/events" \
  -H "Authorization: Bearer $TOKEN"

# annullamento cooperativo (non consuma lo slot orario)
curl -s -X DELETE "$BASE/api/v1/audits/$ID" \
  -H "Authorization: Bearer $TOKEN"
```

## 3. Referti: ogni formato, ogni lingua, una sola scansione

```bash
# formato: html | json | text | md | csv — lingua: it | en | fr |
# de | es. La lingua diversa da quella dell'audit e' resa
# on-demand dal contesto del job (nessuna nuova scansione); il
# JSON resta canonico in italiano (schema_version, con "key" e
# "params" per rilievo). "download" aggiunge Content-Disposition.
curl -s "$BASE/api/v1/audits/$ID/report?format=text&lang=fr" \
  -H "Authorization: Bearer $TOKEN"

curl -s -o referto.html \
  "$BASE/api/v1/audits/$ID/report?format=html&download=1" \
  -H "Authorization: Bearer $TOKEN"
```

## 4. Storico e citazioni

```bash
# storico paginato dell'utente
curl -s "$BASE/api/history?limit=20&offset=0" \
  -H "Authorization: Bearer $TOKEN"

# referto JSON completo di un'esecuzione salvata
curl -s "$BASE/api/history/report?id=3" \
  -H "Authorization: Bearer $TOKEN"

# confronto fra due esecuzioni dello stesso sito
curl -s "$BASE/api/history/compare?a=3&b=5" \
  -H "Authorization: Bearer $TOKEN"
```

## Errori

Le rotte `/api/v1` usano l'oggetto uniforme — chiave i18n con lo
stesso meccanismo chiave+parametri dei rilievi, messaggio italiano
canonico:

```json
{"error": {"code": "hourly_slot", "key": "api.err.hourly_slot",
           "message": "Hai gia' effettuato un check nell'ultima
                       ora: ...", "params": {"retry_in_s": 1800}}}
```

Le rotte legacy (`/api/*`) conservano `{"error": "messaggio"}`.

## Assetto separato e CORS

CORS è **spento di default**: si attiva solo dichiarando le
origini (`mars_api.py --cors https://gui.esempio.it`), senza
credenziali — cross-origin ci si autentica col token, il cookie
SameSite=Strict non viaggia. Esempio completo di deploy (statici
+ proxy oppure origini separate) in
[../deploy/nginx-mars.conf.example](../deploy/nginx-mars.conf.example);
unit systemd del server API in
[../deploy/mars-api.service](../deploy/mars-api.service).
