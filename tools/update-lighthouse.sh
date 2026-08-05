#!/usr/bin/env bash
# Installa il fork di Google Lighthouse nella directory dedicata e
# NON versionata lighthouse/ alla radice del repository. E'
# l'equivalente per un repo yarn di "npm ci in una dir dedicata":
# checkout shallow di un tag esatto, dipendenze deterministiche dal
# lockfile (yarn install --frozen-lockfile via corepack), directory
# ricostruita da zero a ogni esecuzione, nessuno stato residuo.
#
# Il tag da installare e' dichiarato in tools/lighthouse-patches/PIN
# (es. v13.4.1-mars.1 = upstream v13.4.1 + patch-set MARS); la
# strategia di manutenzione del fork e' in docs/LIGHTHOUSE-FORK.md.
#
# Uso:
#   tools/update-lighthouse.sh                  # installa il tag del PIN
#   tools/update-lighthouse.sh v13.5.0-mars.1   # tag esplicito (poi
#                                               # allineare il PIN)
#
# Requisiti: git, Node >= 22.19 con corepack, rete verso GitHub.
# Lo script non committa nulla; lighthouse/ e' nel .gitignore e
# l'attribuzione e' nel NOTICE.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$ROOT/lighthouse"
REPO="https://github.com/saulusprime/lighthouse.git"
PIN_FILE="$ROOT/tools/lighthouse-patches/PIN"

tag="${1:-}"
if [ -z "$tag" ]; then
  if [ ! -f "$PIN_FILE" ]; then
    echo "PIN assente ($PIN_FILE): indica il tag esplicitamente," >&2
    echo "es. tools/update-lighthouse.sh v13.4.1-mars.1" >&2
    exit 2
  fi
  tag="$(tr -d '[:space:]' < "$PIN_FILE")"
fi

command -v git >/dev/null || { echo "git non trovato" >&2; exit 2; }
command -v node >/dev/null || {
  echo "Node non trovato: il fork richiede Node >= 22.19" >&2; exit 2; }
command -v corepack >/dev/null || {
  echo "corepack non trovato (e' incluso in Node dalla 16.9)" >&2; exit 2; }
node -e 'const [maj, min] = process.versions.node.split(".").map(Number);
process.exit(maj > 22 || (maj === 22 && min >= 19) ? 0 : 1)' || {
  echo "Node $(node --version) troppo vecchio: il fork richiede >= 22.19" >&2
  exit 2
}

attuale="nessuna"
[ -f "$DEST/VERSIONE" ] && attuale="$(cat "$DEST/VERSIONE")"
echo "Versione installata: $attuale"
echo "Tag richiesto:       $tag"

# Si costruisce accanto alla destinazione (stesso filesystem) per
# poter scambiare con un solo mv finale.
work="$DEST.nuovo.$$"
trap 'rm -rf "$work"' EXIT
rm -rf "$work"

echo "Clono $REPO al tag $tag (shallow)..."
git clone --quiet --branch "$tag" --depth 1 "$REPO" "$work"

# Guardia: mai installare un tag privo del patch-set MARS (la
# telemetria Sentry tornerebbe attiva). Vedi docs/LIGHTHOUSE-FORK.md.
grep -q 'MARS Beacon fork' "$work/cli/bin.js" || {
  echo "Il tag $tag non contiene la patch anti-telemetria MARS:" >&2
  echo "tag errato o branch mars non ricostruito dopo un sync" >&2
  exit 1
}

export PUPPETEER_SKIP_DOWNLOAD=1 COREPACK_ENABLE_DOWNLOAD_PROMPT=0
echo "Installo le dipendenze (deterministiche dal lockfile)..."
(cd "$work" && corepack yarn install --frozen-lockfile \
  --ignore-scripts --non-interactive --silent)
echo "Costruisco dist/report (richiesto anche per l'output JSON)..."
(cd "$work" && corepack yarn build-report >/dev/null)
echo "Poto le dipendenze di sviluppo..."
(cd "$work" && corepack yarn install --production --frozen-lockfile \
  --ignore-scripts --non-interactive --silent)
rm -rf "$work/.git"

versione_cli="$(node "$work/cli/index.js" --version)"
echo "$tag (lighthouse $versione_cli)" > "$work/VERSIONE"

# Sostituzione atomica: prima si costruisce tutto, poi si scambia.
rm -rf "$DEST"
mv "$work" "$DEST"
trap - EXIT

echo ""
echo "Fork Lighthouse installato in lighthouse/:"
echo "  tag:         $tag"
echo "  lighthouse:  $versione_cli"
echo "  file:        $(find "$DEST" -type f | wc -l)"
echo "  dimensione:  $(du -sh "$DEST" | cut -f1)"
echo ""
echo "Directory non versionata (.gitignore): niente da committare."
echo "Se hai installato un tag diverso dal PIN, allinea"
echo "tools/lighthouse-patches/PIN e docs/LIGHTHOUSE-FORK.md."
