#!/usr/bin/env bash
# Aggiorna la vendorizzazione di Bootstrap Italia in
# gui/vendor/bootstrap-italia scaricando il pacchetto ufficiale da
# npm e POTANDO i formati legacy: restano solo i file che la GUI
# usa davvero (CSS minificato, bundle JS minificato, font
# woff/woff2 con le loro licenze, sprite SVG, LICENSE).
#
# Uso:
#   tools/update-vendor.sh            # riscarica la versione attuale
#   tools/update-vendor.sh 2.19.0     # aggiorna a una versione
#   tools/update-vendor.sh latest     # aggiorna all'ultima su npm
#
# Dopo l'esecuzione: rilanciare pytest, Pa11y (.pa11yci.js) e
# tools/verifica_at.py, controllare la GUI a occhio e aggiornare i
# riferimenti alla versione in README.md e AS-IS.md prima del
# commit. Lo script non committa nulla.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$ROOT/gui/vendor/bootstrap-italia"
REGISTRY="https://registry.npmjs.org/bootstrap-italia"

attuale=""
if [ -f "$DEST/VERSIONE" ]; then
  attuale="$(cat "$DEST/VERSIONE")"
elif [ -f "$DEST/js/bootstrap-italia.bundle.min.js" ]; then
  attuale="$(grep -oE \
    'BOOTSTRAP_ITALIA_VERSION="[0-9]+\.[0-9]+\.[0-9]+"' \
    "$DEST/js/bootstrap-italia.bundle.min.js" | head -1 \
    | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || true)"
fi

versione="${1:-$attuale}"
if [ -z "$versione" ]; then
  echo "Impossibile dedurre la versione attuale: indicala" >&2
  echo "esplicitamente, es. tools/update-vendor.sh 2.18.2" >&2
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

echo "Scarico bootstrap-italia@$versione da npm..."
curl -fsSL "$REGISTRY/-/bootstrap-italia-$versione.tgz" \
  -o "$tmp/pkg.tgz"
tar -xzf "$tmp/pkg.tgz" -C "$tmp"
DIST="$tmp/package/dist"
[ -d "$DIST" ] || { echo "dist/ assente nel pacchetto" >&2; exit 1; }

nuovo="$tmp/vendor"
mkdir -p "$nuovo/css" "$nuovo/js" "$nuovo/svg"

# Solo cio' che la GUI usa: niente sorgenti non minificati,
# niente source map, niente formati font legacy (ttf/eot/svg).
cp "$DIST/css/bootstrap-italia.min.css" "$nuovo/css/"
cp "$DIST/js/bootstrap-italia.bundle.min.js" "$nuovo/js/"
cp "$DIST/svg/sprites.svg" "$nuovo/svg/"
cp "$tmp/package/LICENSE" "$nuovo/LICENSE"

potati=0
while IFS= read -r -d '' file; do
  rel="${file#"$DIST"/fonts/}"
  case "$file" in
    *.woff|*.woff2|*OFL.txt|*LICENSE.txt)
      mkdir -p "$nuovo/fonts/$(dirname "$rel")"
      cp "$file" "$nuovo/fonts/$rel"
      ;;
    *)
      potati=$((potati + 1))
      ;;
  esac
done < <(find "$DIST/fonts" -type f -print0)

echo "$versione" > "$nuovo/VERSIONE"

# Sostituzione atomica: prima si costruisce tutto, poi si scambia.
rm -rf "$DEST"
mkdir -p "$(dirname "$DEST")"
mv "$nuovo" "$DEST"

echo ""
echo "Vendorizzazione aggiornata a $versione:"
echo "  file:            $(find "$DEST" -type f | wc -l)"
echo "  dimensione:      $(du -sh "$DEST" | cut -f1)"
echo "  legacy potati:   $potati (ttf/eot/svg/map e non minificati)"
echo ""
echo "Prossimi passi (NON automatici):"
echo "  1. pytest e npx pa11y-ci --config .pa11yci.js"
echo "  2. tools/verifica_at.py e controllo visivo della GUI"
echo "  3. aggiornare la versione citata in README.md e AS-IS.md"
echo "  4. git add gui/vendor && commit"
