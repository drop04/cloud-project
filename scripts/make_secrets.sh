#!/usr/bin/env bash
# Generate random S3 credentials at deploy time and store them ONLY as Kubernetes Secrets (nothing in git).
set -euo pipefail
if kubectl -n data get secret seaweedfs-s3-config >/dev/null 2>&1; then echo "secrets exist"; exit 0; fi
AK="ak$(openssl rand -hex 8)"; SK="$(openssl rand -hex 24)"
CFG=$(printf '{"identities":[{"name":"admin","credentials":[{"accessKey":"%s","secretKey":"%s"}],"actions":["Admin","Read","Write","List","Tagging"]}]}' "$AK" "$SK")
kubectl -n data create secret generic seaweedfs-s3-config --from-literal=s3.json="$CFG"
for ns in data pipeline app; do
  kubectl -n "$ns" create secret generic s3-credentials --from-literal=AWS_ACCESS_KEY_ID="$AK" --from-literal=AWS_SECRET_ACCESS_KEY="$SK"
done
