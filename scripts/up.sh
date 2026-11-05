#!/usr/bin/env bash
# Build and deploy everything from a fresh clone. Needs: docker, k3d, kubectl, python3 (+pip), curl.
set -euo pipefail
cd "$(dirname "$0")/.."
RELEASE_REPO="${RELEASE_REPO:-}"            # e.g. youruser/cloud-project (set in Makefile/env)
RELEASE_TAG="${RELEASE_TAG:-models-v1}"
k3d cluster list | grep -q cloudproj || k3d cluster create --config cluster/k3d.yaml
kubectl apply -f k8s/00-namespaces.yaml
bash scripts/make_secrets.sh
kubectl apply -f k8s/seaweedfs.yaml
kubectl -n data rollout status deploy/seaweedfs --timeout=180s
docker build -t parser-service:local -f service/Dockerfile .
docker build -t teacher-worker:local -f worker/Dockerfile .
k3d image import parser-service:local teacher-worker:local -c cloudproj
python3 -m pip install -q --break-system-packages boto3==1.35.76 2>/dev/null || python3 -m pip install -q boto3==1.35.76
# host-side access to S3 for seeding
kubectl -n data port-forward svc/seaweedfs-s3 8333:8333 >/dev/null 2>&1 & PF=$!
trap 'kill $PF 2>/dev/null || true' EXIT
for _ in $(seq 30); do (echo > /dev/tcp/localhost/8333) 2>/dev/null && break; sleep 1; done
export S3_ENDPOINT=http://localhost:8333
export AWS_ACCESS_KEY_ID=$(kubectl -n data get secret s3-credentials -o jsonpath='{.data.AWS_ACCESS_KEY_ID}' | base64 -d)
export AWS_SECRET_ACCESS_KEY=$(kubectl -n data get secret s3-credentials -o jsonpath='{.data.AWS_SECRET_ACCESS_KEY}' | base64 -d)
python3 scripts/s3tool.py mkbuckets
python3 scripts/s3tool.py put data/commands_pool.jsonl datasets commands_pool.jsonl
# models: from the GitHub Release assets (model-v1.tar.gz / model-v2.tar.gz) -> s3://models/vN/
if [ -n "$RELEASE_REPO" ]; then
  for v in v1 v2; do
    mkdir -p "models/$v"
    if ! curl -fsSL -o "models/model-$v.tar.gz" "https://github.com/$RELEASE_REPO/releases/download/$RELEASE_TAG/model-$v.tar.gz"; then
      echo "WARN: no release asset model-$v.tar.gz yet (tag $RELEASE_TAG) - skipping; pods stay NotReady until models exist"; continue
    fi
    tar -xzf "models/model-$v.tar.gz" -C "models/$v"
    python3 scripts/s3tool.py putdir "models/$v" models "$v"
  done
fi
kubectl apply -f k8s/app.yaml
kubectl -n app rollout status deploy/parser --timeout=300s || echo "WARN: parser not Ready - are models v1/v2 in s3://models/ ? (check: kubectl -n app logs deploy/parser)"
echo "up. try: curl -s -X POST localhost:8080/parse -H 'content-type: application/json' -d '{\"text\":\"what is the weather in london\"}'"
