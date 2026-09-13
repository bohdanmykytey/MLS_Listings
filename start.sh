#!/usr/bin/env bash
#
# Start both services with one command.
#
# Installs dependencies if they are missing, starts the API, waits for it to
# answer, then starts the UI. Ctrl-C stops both.
#
# Shutdown is deliberate rather than incidental: `npm run dev` spawns vite as a
# child process, so killing npm alone would orphan vite and leave the port
# occupied. `kill_tree` walks the process tree depth-first so nothing survives.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
API_PORT=8000
UI_PORT=3000

# Pin "today" so relevance scores are identical between runs and demos.
export LISTING_SEARCH_REFERENCE_DATE="${LISTING_SEARCH_REFERENCE_DATE:-$(date +%F)}"

API_PID=""
UI_PID=""

# Kill a process and every descendant, children first.
kill_tree() {
  local pid=$1 child
  for child in $(pgrep -P "$pid" 2>/dev/null); do
    kill_tree "$child"
  done
  kill "$pid" 2>/dev/null || true
}

cleanup() {
  trap - EXIT INT TERM   # don't re-enter while shutting down
  echo ""
  echo "Shutting down..."
  [ -n "$UI_PID" ] && kill_tree "$UI_PID"
  [ -n "$API_PID" ] && kill_tree "$API_PID"
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

port_in_use() {
  lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1
}

for port in "$API_PORT" "$UI_PORT"; do
  if port_in_use "$port"; then
    echo "ERROR: port $port is already in use. Stop whatever is on it first." >&2
    exit 1
  fi
done

echo "==> Backend"
cd "$ROOT/backend"
if [ ! -d .venv ]; then
  echo "    creating virtualenv..."
  python3 -m venv .venv
  ./.venv/bin/pip install --quiet --upgrade pip
  ./.venv/bin/pip install --quiet -r requirements.txt
else
  echo "    virtualenv present"
fi

./.venv/bin/uvicorn app.main:app --port "$API_PORT" --log-level warning &
API_PID=$!

echo -n "    waiting for http://localhost:$API_PORT "
for _ in $(seq 1 60); do
  if curl -fsS "http://127.0.0.1:$API_PORT/api/health" >/dev/null 2>&1; then
    echo "ready"
    break
  fi
  echo -n "."
  sleep 0.5
done

if ! curl -fsS "http://127.0.0.1:$API_PORT/api/health" >/dev/null 2>&1; then
  echo ""
  echo "ERROR: the API did not start. See the output above." >&2
  exit 1
fi

echo "==> Frontend"
cd "$ROOT/frontend"
if [ ! -d node_modules ]; then
  echo "    installing packages (this takes a minute)..."
  npm install --silent
else
  echo "    packages present"
fi

npm run dev &
UI_PID=$!

cat <<BANNER

  UI      http://localhost:$UI_PORT
  API     http://localhost:$API_PORT
  Docs    http://localhost:$API_PORT/docs

  Relevance scores pinned to $LISTING_SEARCH_REFERENCE_DATE
  Ctrl-C stops both.

BANNER

# Exit as soon as either service dies, rather than hanging on a dead stack.
# A polling loop rather than `wait -n`, because macOS ships bash 3.2 and
# `wait -n` needs bash 4.3+.
while kill -0 "$API_PID" 2>/dev/null && kill -0 "$UI_PID" 2>/dev/null; do
  sleep 1
done
