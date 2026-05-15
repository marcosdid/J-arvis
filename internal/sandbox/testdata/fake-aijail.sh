#!/usr/bin/env bash
# fake-aijail.sh — integration-test fixture for AijailRuntime (build tag: integration).
#
# Sleeps until SIGTERM. On SIGTERM, explicitly kills the sleep child before
# exiting so the test does not leak a 10-minute orphan process per run.
# The echo is for human debugging only; tests do not assert on stdout.

echo "fake-aijail: spawned in $(pwd)" >&2

SLEEP_PID=
cleanup() {
  if [ -n "$SLEEP_PID" ]; then
    kill -TERM "$SLEEP_PID" 2>/dev/null
    wait "$SLEEP_PID" 2>/dev/null
  fi
  exit 0
}
trap cleanup TERM INT

sleep 600 &
SLEEP_PID=$!
wait "$SLEEP_PID"
