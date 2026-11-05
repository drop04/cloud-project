#!/usr/bin/env bash
# Task 3: 50 sequential requests against the container at 1 CPU / 1 GiB; reports peak memory.
# Needs: cluster up (make up) with models in s3://models/v1/, image parser-service:local built.
# Evidence -> results/task3_memory.txt
set -euo pipefail
cd "$(dirname "$0")/.."; mkdir -p results
OUT=results/task3_memory.txt; : > "$OUT"
kubectl -n data port-forward --address 0.0.0.0 svc/seaweedfs-s3 8333:8333 >/dev/null 2>&1 & PF=$!
cleanup() { kill $PF $SAMPLER 2>/dev/null || true; docker rm -f memtest >/dev/null 2>&1 || true; }
SAMPLER=0; trap cleanup EXIT
for _ in $(seq 30); do (echo > /dev/tcp/localhost/8333) 2>/dev/null && break; sleep 1; done
AK=$(kubectl -n data get secret s3-credentials -o jsonpath='{.data.AWS_ACCESS_KEY_ID}' | base64 -d)
SK=$(kubectl -n data get secret s3-credentials -o jsonpath='{.data.AWS_SECRET_ACCESS_KEY}' | base64 -d)
docker rm -f memtest >/dev/null 2>&1 || true
docker run -d --name memtest --cpus 1 --memory 1g --add-host=host.docker.internal:host-gateway -p 8000:8000 \
  -e MODEL_URI=s3://models/v1/ -e MODEL_VERSION=v1 -e MAX_NEW_TOKENS=64 \
  -e S3_ENDPOINT=http://host.docker.internal:8333 -e AWS_ACCESS_KEY_ID="$AK" -e AWS_SECRET_ACCESS_KEY="$SK" \
  parser-service:local >/dev/null
for _ in $(seq 120); do curl -sf localhost:8000/readyz >/dev/null && break; sleep 2; done
curl -sf localhost:8000/readyz >/dev/null || { docker logs memtest | tail -20; echo "service never became ready"; exit 1; }
# sample memory (MiB) every 0.5 s while the requests run; the peak is the max sample
( while true; do docker stats --no-stream --format '{{.MemUsage}}' memtest | awk '{print $1}'; sleep 0.5; done > /tmp/memsamples.txt ) & SAMPLER=$!
ok=0
for i in $(seq 50); do
  code=$(curl -s -o /dev/null -w '%{http_code}' -X POST localhost:8000/parse -H 'content-type: application/json' \
         -d '{"text":"what is the weather in london"}')
  [ "$code" = 200 ] && ok=$((ok+1))
done
kill $SAMPLER 2>/dev/null || true
PEAK=$(python3 - <<'PY'
import re
vals=[]
for l in open('/tmp/memsamples.txt'):
    m=re.match(r'([\d.]+)(KiB|MiB|GiB|B)',l.strip())
    if m: vals.append(float(m[1])*{'B':1/1048576,'KiB':1/1024,'MiB':1,'GiB':1024}[m[2]])
print(f"{max(vals):.1f} MiB" if vals else "no samples")
PY
)
{
  echo "limits: --cpus 1 --memory 1g"
  echo "requests ok: $ok / 50"
  echo "OOMKilled: $(docker inspect memtest --format '{{.State.OOMKilled}}')"
  echo "peak memory (max of docker stats samples): $PEAK"
  echo "--- docker stats (final) ---"; docker stats --no-stream memtest
  echo "--- FAULT_INJECT check: run separately with -e FAULT_INJECT=1 ---"
} | tee "$OUT"
