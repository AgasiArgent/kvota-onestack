#!/usr/bin/env bash
# test_ci_stale_check.sh — verify that the stale-manifest CI guard works.
#
# Task 7 Requirement 1.3 — "CI workflow SHALL regenerate the manifest and compare
# it against the committed file; IF they differ, THEN CI SHALL fail."
#
# What this script does:
#   1. Copy the test fixture to a scratch directory.
#   2. Build the manifest from the scratch fixture via `vitest`-free runner (ts-node
#      would be ideal, but we stick to `node --experimental-strip-types` only if
#      Node >= 22.6 is available; otherwise this script falls back to `npx tsx`).
#   3. Stash the generated manifest.
#   4. Modify one fixture file (a route's title).
#   5. Re-build the manifest.
#   6. Assert the two manifests differ on the modified node's title.
#
# Exit codes:
#   0 — all assertions passed
#   1 — assertion failed or tooling error
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_ROOT="$(cd "${HERE}/../../.." && pwd)"
FIXTURE_ROOT="${HERE}/fixtures/manifest"

SCRATCH="$(mktemp -d -t journey-stale-XXXXXX)"
trap 'rm -rf "${SCRATCH}"' EXIT

echo "[stale-check] scratch dir: ${SCRATCH}"

# Clone the fixture into the scratch directory.
cp -R "${FIXTURE_ROOT}/." "${SCRATCH}/"

# Use tsx so we don't depend on Node's native TS stripping version.
RUNNER="npx --yes tsx"

# Absolute paths fed to the runner.
APP_ROOT="${SCRATCH}/app"
SPECS_ROOT="${SCRATCH}/specs"
ACCESS_CONTROL="${SCRATCH}/steering/access-control.md"
OUT_JSON="${SCRATCH}/journey-manifest.json"

build_manifest() {
  (
    cd "${FRONTEND_ROOT}"
    ${RUNNER} scripts/journey/__tests__/_stale-check-runner.ts \
      "${APP_ROOT}" "${SPECS_ROOT}" "${ACCESS_CONTROL}" "${SCRATCH}" "${OUT_JSON}"
  )
}

echo "[stale-check] first build"
build_manifest
BEFORE="$(cat "${OUT_JSON}")"

echo "[stale-check] mutating fixture title"
TARGET="${SCRATCH}/app/(app)/quotes/page.tsx"
cat > "${TARGET}" <<'EOF'
export const metadata = { title: "Quotes (mutated)" };

export default function QuotesPage() {
  return <div>mutated</div>;
}
EOF

echo "[stale-check] second build"
build_manifest
AFTER="$(cat "${OUT_JSON}")"

if [ "${BEFORE}" = "${AFTER}" ]; then
  echo "[stale-check] FAIL: manifest did not change after editing a route title"
  exit 1
fi

# Specifically check the title moved from "Quotes" to "Quotes (mutated)".
if ! echo "${AFTER}" | grep -q '"title": "Quotes (mutated)"'; then
  echo "[stale-check] FAIL: new title not present in regenerated manifest"
  echo "${AFTER}" | head -60
  exit 1
fi

if echo "${BEFORE}" | grep -q '"title": "Quotes (mutated)"'; then
  echo "[stale-check] FAIL: mutated title unexpectedly present in pre-edit manifest"
  exit 1
fi

echo "[stale-check] OK — regenerated manifest reflects fixture edit"
