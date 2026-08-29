#!/usr/bin/env bash
# Start the backend, run end-to-end API verification, then stop it.
set -uo pipefail
cd "$(dirname "$0")/.."

pkill -9 -f "uvicorn app.main" 2>/dev/null
sleep 1
cd backend
rm -f skillbridge.db
SKILLBRIDGE_DB="$PWD/skillbridge.db" ../.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 > /tmp/sb-server.log 2>&1 &
SERVER_PID=$!

echo "Waiting for server to seed and start..."
for i in $(seq 1 40); do
  if curl -s -o /dev/null http://127.0.0.1:8000/api/skills; then
    break
  fi
  if ! kill -0 "$SERVER_PID" 2>/dev/null; then
    echo "SERVER DIED — log:"
    cat /tmp/sb-server.log
    exit 1
  fi
  sleep 1
done

echo "=== Health ==="
curl -s http://127.0.0.1:8000/api/skills | head -c 200; echo
echo "=== Login as Student ==="
curl -s -X POST http://127.0.0.1:8000/api/login -H "Content-Type: application/json" -d '{"email":"aisha@student.edu","password":"demo1234"}' | head -c 200; echo
echo "=== University stats ==="
curl -s http://127.0.0.1:8000/api/university/stats | head -c 400; echo
echo "=== Student analysis (Aisha) ==="
SID=$(curl -s -X POST http://127.0.0.1:8000/api/login -H "Content-Type: application/json" -d '{"email":"aisha@student.edu","password":"demo1234"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['entity_id'])")
curl -s "http://127.0.0.1:8000/api/students/$SID/analysis" | python3 -m json.tool | head -40

echo "=== Frontend served at root (should be HTML) ==="
curl -s http://127.0.0.1:8000/ | head -c 120; echo
echo "=== Assets ==="
curl -s -o /dev/null -w "assets http %{http_code}\n" http://127.0.0.1:8000/assets/$(ls ../frontend/dist/assets | grep js | head -1)

echo "=== Server log tail ==="
tail -6 /tmp/sb-server.log

kill "$SERVER_PID" 2>/dev/null
wait "$SERVER_PID" 2>/dev/null
echo "Done."
