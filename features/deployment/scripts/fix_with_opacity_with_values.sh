#!/usr/bin/env bash
set -euo pipefail

DRY_RUN=0
if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN=1
fi

ROOT="${MELOS_ROOT_PATH:-$(pwd)}"

PATTERN='\.withOpacity\('

count_matches() {
  rg -n --no-heading -S "$PATTERN" "$ROOT/apps" "$ROOT/packages" 2>/dev/null | wc -l | tr -d ' '
}

MATCHES_BEFORE="$(count_matches)"

if [[ "$MATCHES_BEFORE" == "0" ]]; then
  echo "No .withOpacity(...) usages found under apps/ and packages/."
  exit 0
fi

echo "Found $MATCHES_BEFORE .withOpacity(...) usage(s)."

if [[ "$DRY_RUN" == "1" ]]; then
  echo "Dry run: showing first 50 matches."
  rg -n -S "$PATTERN" "$ROOT/apps" "$ROOT/packages" | head -n 50
  exit 2
fi

echo "Applying replacement: .withOpacity(  ->  .withValues(alpha: "
perl -0pi -e 's/\.withOpacity\(/.withValues(alpha: /g' $(rg --files -g'*.dart' "$ROOT/apps" "$ROOT/packages")

MATCHES_AFTER="$(count_matches)"
echo "Done. Remaining .withOpacity(...) usage(s): $MATCHES_AFTER"

