#!/usr/bin/env bash
# Aggiorna la vendorizzazione di Scalar API Reference in
# gui/vendor/scalar scaricando @scalar/api-reference da npm e
# POTANDO tutto tranne il bundle standalone (autonomo, nessun
# chunk dinamico): e' il lettore della spec OpenAPI su /api/docs
# (decisione P1 API-first: solo Scalar, Swagger UI scartato).
#
# Uso:
#   tools/update-scalar.sh            # riscarica la versione attuale
#   tools/update-scalar.sh 1.64.0     # aggiorna a una versione
#   tools/update-scalar.sh latest     # aggiorna all'ultima su npm
#
# Verifiche incorporate (filosofia offline del progetto):
#   - DENYLIST telemetria: sentry/analytics/posthog/segment/hotjar/
#     plausible nel bundle fermano l'aggiornamento;
#   - ORIGINI.txt elenca gli host esterni presenti nel bundle come
#     stringhe (esempi e documentazione, piu' fonts.scalar.com dei
#     font predefiniti): sono inerti — la pagina /api/docs li
#     disattiva con withDefaultFonts:false e la CSP della GUI
#     blocca comunque ogni caricamento esterno a runtime.
#
# Dopo l'esecuzione: rilanciare pytest (test_api_contract), aprire
# /api/docs a occhio e aggiornare la versione citata in AS-IS.md
# prima del commit. Lo script non committa nulla.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$ROOT/gui/vendor/scalar"
REGISTRY="https://registry.npmjs.org/@scalar/api-reference"
DENYLIST='sentry\.io|google-analytics|googletagmanager|posthog'
DENYLIST="$DENYLIST"'|segment\.(io|com)|hotjar|plausible\.io'

attuale=""
if [ -f "$DEST/VERSIONE" ]; then
  attuale="$(cat "$DEST/VERSIONE")"
fi

versione="${1:-$attuale}"
if [ -z "$versione" ]; then
  echo "Impossibile dedurre la versione attuale: indicala" >&2
  echo "esplicitamente, es. tools/update-scalar.sh 1.64.0" >&2
  exit 2
fi
if [ "$versione" = "latest" ]; then
  versione="$(curl -fsSL "$REGISTRY/latest" \
    | python3 -c 'import json,sys; print(json.load(sys.stdin)["version"])')"
fi

echo "Versione vendorizzata: ${attuale:-nessuna}"
echo "Versione richiesta:    $versione"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

echo "Scarico @scalar/api-reference@$versione da npm..."
curl -fsSL "$REGISTRY/-/api-reference-$versione.tgz" \
  -o "$tmp/pkg.tgz"
tar -xzf "$tmp/pkg.tgz" -C "$tmp"
BUNDLE="$tmp/package/dist/browser/standalone.js"
[ -f "$BUNDLE" ] || {
  echo "dist/browser/standalone.js assente nel pacchetto" >&2
  exit 1
}

# Il bundle deve restare autonomo: niente import di chunk.
if grep -q 'dist/browser/chunks\|from"\./chunks' "$BUNDLE"; then
  echo "Il bundle non e' piu' autonomo (chunk dinamici):" >&2
  echo "rivedere la potatura prima di aggiornare." >&2
  exit 1
fi

# Denylist di telemetria e analytics: se compare, non si aggiorna.
if grep -qE "$DENYLIST" "$BUNDLE"; then
  echo "TELEMETRIA NEL BUNDLE (denylist): aggiornamento" >&2
  echo "rifiutato. Ispezionare il pacchetto prima di procedere." >&2
  grep -oE "$DENYLIST" "$BUNDLE" | sort -u >&2
  exit 1
fi

licenza="$(python3 -c 'import json,sys
p = json.load(open(sys.argv[1]))
print(p.get("license", "?"), "-", p.get("author", "?"))' \
  "$tmp/package/package.json")"

nuovo="$tmp/vendor"
mkdir -p "$nuovo"
cp "$BUNDLE" "$nuovo/standalone.js"
echo "$versione" > "$nuovo/VERSIONE"
{
  echo "# Host esterni presenti nel bundle come STRINGHE (esempi,"
  echo "# documentazione, font predefiniti). Sono inerti: la pagina"
  echo "# /api/docs disattiva i font con withDefaultFonts:false e"
  echo "# la CSP della GUI blocca ogni caricamento esterno a"
  echo "# runtime. Denylist telemetria verificata dallo script."
  grep -oE 'https?://[a-zA-Z0-9.-]+' "$nuovo/standalone.js" \
    | sort -u
} > "$nuovo/ORIGINI.txt"
{
  echo "@scalar/api-reference $versione"
  echo "Licenza dichiarata nel package.json: $licenza"
  echo "Bundle standalone vendorizzato da npm; attribuzione nel"
  echo "NOTICE del repository. https://github.com/scalar/scalar"
} > "$nuovo/LICENZA.txt"

# Sostituzione atomica: prima si costruisce tutto, poi si scambia.
rm -rf "$DEST"
mkdir -p "$(dirname "$DEST")"
mv "$nuovo" "$DEST"

echo ""
echo "Vendorizzazione aggiornata a $versione:"
echo "  file:       $(find "$DEST" -type f | wc -l)"
echo "  dimensione: $(du -sh "$DEST" | cut -f1)"
echo "  licenza:    $licenza"
echo ""
echo "Prossimi passi (NON automatici):"
echo "  1. pytest tests/test_api_contract.py"
echo "  2. controllo visivo di /api/docs (python3 mars_gui.py)"
echo "  3. aggiornare la versione citata in AS-IS.md"
echo "  4. git add gui/vendor/scalar && commit"
