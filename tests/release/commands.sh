#!/bin/sh
# Real test of the release tool's `published` and `marker-claims` commands
# through the built binary, against the npm registry.
#
# `published` must answer `published VERSION PATH` for packages npm certainly
# serves (an unscoped and a scoped name) and `absent NAME` for a name nobody
# published, and the old `baseline --probe` spelling must be gone. Then
# `marker-claims` must read the committed baseline's marker and answer whether
# its tier claims a registry, agreeing with what npm says about the package:
# `registry` only when npm serves it. Every command, its exit status and
# output go to the run's report.txt.
#
# Usage: tests/release/commands.sh   (RELEASE selects the binary, default
#   release/target/debug/wisent-node-release)
set -eu
cd "$(dirname "$0")/../.."
BIN=${RELEASE:-release/target/debug/wisent-node-release}
RUN="$(date -u +%Y%m%dT%H%M%SZ)-$$"
ROOT="$PWD/release/target/real-tests/release/$RUN"
REPORT="$ROOT/report.txt"
mkdir -p "$ROOT"
echo "revision: $(git rev-parse HEAD)$(git diff --quiet || echo ' (dirty)')" >"$REPORT"
echo "binary: $BIN" >>"$REPORT"

run() {
  expected=$1
  shift
  set +e
  out=$("$BIN" "$@" 2>"$ROOT/stderr" </dev/null)
  status=$?
  set -e
  err=$(cat "$ROOT/stderr")
  printf '$ wisent-node-release %s\nexit: %s\nstdout: %s\nstderr: %s\n\n' "$*" "$status" "$out" "$err" >>"$REPORT"
  if [ "$status" -ne "$expected" ]; then
    echo "FAIL: $* exited $status, expected $expected: $err" | tee -a "$REPORT" >&2
    exit 1
  fi
}
check() {
  case "$2" in
    $3) echo "ok: $1 = $2" >>"$REPORT" ;;
    *) echo "FAIL: $1: got '$2', expected '$3'" | tee -a "$REPORT" >&2; exit 1 ;;
  esac
}

run 0 published express
check "npm serves express" "$out" "published * express/-/express-*.tgz"
run 0 published @types/node
check "npm serves a scoped package" "$out" "published * @types/node/-/node-*.tgz"
run 0 published "wisent-release-test-nobody-published-$RUN"
check "a name nobody published is absent" "$out" "absent wisent-release-test-nobody-published-$RUN"
run 2 baseline --probe express

name=$(jq -r .name package.json)
marker=$(jq -r '.source | split(" ") | first' released-surface.json)
run 0 marker-claims "$marker"
claims=$out
run 0 published "$name"
case "$out" in
  "published "*) check "a registry marker for a package npm serves" "$claims" "registry" ;;
  *) check "a marker that claims no registry for a package npm does not serve" "$claims" "*" ;;
esac

touch "$ROOT/passed"
echo "PASS" >>"$REPORT"
echo "PASS: $REPORT"
