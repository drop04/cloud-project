#!/usr/bin/env bash
# Task 4 experiments. Usage: bash scripts/task4_experiments.sh <rolling|recovery|coldstart|balance|hpa>
# Evidence is written to results/. Load test uses a longer run-time where a change happens during load.
set -euo pipefail
cd "$(dirname "$0")/.."; mkdir -p results
case "$1" in
rolling)
  # NB: LOADTEST_HEADERS_OUT is read by locustfile; set it per run so files are not overwritten.
  export LOADTEST_HEADERS_OUT=results/rolling_headers.json
  (locust -f tools/locustfile.py --headless --users 4 --spawn-rate 4 --run-time 5m --host http://localhost:8080 --csv results/rolling > results/rolling.log 2>&1 || true) &
  LP=$!; sleep 30
  kubectl -n app set env deploy/parser MODEL_VERSION=v2 MODEL_URI=s3://models/v2/
  kubectl -n app rollout status deploy/parser --timeout=300s | tee results/rolling_update_status.txt
  sleep 60
  kubectl -n app rollout undo deploy/parser
  kubectl -n app rollout status deploy/parser --timeout=300s | tee -a results/rolling_update_status.txt
  wait $LP
  curl -si -X POST localhost:8080/parse -H 'content-type: application/json' -d '{"text":"what is the weather in london"}' | tee results/after_rollback.txt
  kubectl -n app get deploy parser -o jsonpath='{.spec.template.spec.containers[0].env}' | tee results/after_rollback_env.json ;;
recovery)
  export LOADTEST_HEADERS_OUT=results/recovery_headers.json
  (locust -f tools/locustfile.py --headless --users 4 --spawn-rate 4 --run-time 3m --host http://localhost:8080 --csv results/recovery > results/recovery.log 2>&1 || true) &
  LP=$!; sleep 30
  kubectl -n app get pods | tee results/recovery_before.txt
  kubectl -n app delete pod "$(kubectl -n app get pods -o name | head -1 | cut -d/ -f2)"
  for i in $(seq 1 24); do kubectl -n app get deploy parser --no-headers; sleep 5; done | tee results/recovery_replicas.txt
  wait $LP ;;
coldstart)
  : > results/coldstart_times.txt
  for run in 1 2 3; do
    kubectl -n app delete pods -l app=parser --wait=true
    sleep 3; kubectl -n app wait --for=condition=Ready pod -l app=parser --timeout=300s
    kubectl -n app get pods -l app=parser -o json | python3 -c '
import sys, json, datetime as d
p = lambda s: d.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ")
for pod in json.load(sys.stdin)["items"]:
    c = pod["metadata"]["creationTimestamp"]
    r = next(x["lastTransitionTime"] for x in pod["status"]["conditions"] if x["type"] == "Ready")
    print((p(r) - p(c)).total_seconds())' | tee -a results/coldstart_times.txt
  done
  kubectl -n app logs -l app=parser --tail=20 | tee results/coldstart_logs.txt
  python3 -c "import statistics as s;v=[float(x) for x in open('results/coldstart_times.txt')];print('median',s.median(v),'n',len(v))" | tee results/coldstart_median.txt ;;
balance)
  kubectl -n app delete hpa parser --ignore-not-found   # HPA would scale 2 -> 1; we need exactly two Ready replicas
  kubectl -n app scale deploy/parser --replicas=2; kubectl -n app rollout status deploy/parser
  export LOADTEST_HEADERS_OUT=results/loadtest_headers.json
  locust -f tools/locustfile.py --headless --users 4 --spawn-rate 4 --run-time 2m --host http://localhost:8080 --csv results/loadtest | tee results/loadtest.log || true
  kubectl -n app top pods | tee results/loadtest_top_pods.txt
  kubectl apply -f k8s/app.yaml >/dev/null ;;   # restore HPA
hpa)
  kubectl -n app scale deploy/parser --replicas=1
  export LOADTEST_HEADERS_OUT=results/hpa_headers.json
  (locust -f tools/locustfile.py --headless --users 8 --spawn-rate 8 --run-time 6m --host http://localhost:8080 --csv results/hpa > results/hpa.log 2>&1 || true) &
  LP=$!
  for i in $(seq 1 60); do date +%T; kubectl -n app get hpa parser --no-headers; sleep 8; done | tee results/hpa_timeline.txt
  wait $LP ;;
esac
