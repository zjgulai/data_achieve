#!/usr/bin/env bash
# Deterministic test for scripts/check_dual_production_drift.sh.
# Mocks curl so the test does not touch production.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCRIPT="$ROOT/scripts/check_dual_production_drift.sh"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

mkdir -p "$TMP/bin"
cat >"$TMP/bin/curl" <<'SH'
#!/usr/bin/env bash
url=""
for arg in "$@"; do
  case "$arg" in
    http*) url="$arg" ;;
  esac
done
case "$url" in
  *a.example*)
    printf '%s' '{"status":"ok","database":"connected","schema":"current","schema_revision":"202610310068","schema_head":"202610310068"}'
    ;;
  *b.example*)
    if [[ "${FAKE_B_REV:-202610310068}" == "same" ]]; then
      printf '%s' '{"status":"ok","database":"connected","schema":"current","schema_revision":"202610310068","schema_head":"202610310068"}'
    else
      printf '%s' "{\"status\":\"ok\",\"database\":\"connected\",\"schema\":\"current\",\"schema_revision\":\"${FAKE_B_REV}\",\"schema_head\":\"${FAKE_B_REV}\"}"
    fi
    ;;
  *)
    exit 22
    ;;
esac
SH
chmod +x "$TMP/bin/curl"

run() {
  PATH="$TMP/bin:$PATH" \
    SCRAPY_PROD_A_URL="http://a.example" \
    SCRAPY_PROD_B_URL="http://b.example" \
    bash "$SCRIPT" "$@"
}

echo "case 1: matching revisions"
out="$(FAKE_B_REV=same run)"
grep -q "PASS  schema revisions match" <<<"$out" || {
  echo "FAIL: expected matching revisions to PASS"
  echo "$out"
  exit 1
}

echo "case 2: drift without --strict"
out="$(FAKE_B_REV=202610220056 run)"
grep -q "WARN  schema drift" <<<"$out" || {
  echo "FAIL: expected a drift warning"
  echo "$out"
  exit 1
}
grep -q "RESULT  PASS" <<<"$out" || {
  echo "FAIL: warn mode must exit PASS"
  echo "$out"
  exit 1
}

echo "case 3: drift with --strict"
set +e
out="$(FAKE_B_REV=202610220056 run --strict)"
code=$?
set -e
[[ "$code" == "1" ]] || {
  echo "FAIL: --strict must exit 1, got $code"
  echo "$out"
  exit 1
}
grep -q "RESULT  FAIL" <<<"$out" || {
  echo "FAIL: --strict must print FAIL"
  echo "$out"
  exit 1
}

echo "case 4: frozen_nonprod host is skipped, even under --strict"
cat >"$TMP/scope.json" <<'JSON'
{"hosts":{"a":{"role":"active"},"b":{"role":"frozen_nonprod"}}}
JSON
set +e
out="$(FAKE_B_REV=202610220056 SCRAPY_PRODUCTION_SCOPE="$TMP/scope.json" run --strict)"
code=$?
set -e
[[ "$code" == "0" ]] || {
  echo "FAIL: frozen host must not fail --strict, got $code"
  echo "$out"
  exit 1
}
grep -q "frozen_nonprod" <<<"$out" || {
  echo "FAIL: expected the frozen role in the table"
  echo "$out"
  exit 1
}
grep -q "SKIP  schema comparison" <<<"$out" || {
  echo "FAIL: expected schema comparison to be skipped"
  echo "$out"
  exit 1
}

echo "dual production drift test OK"