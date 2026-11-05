# Command-parser distillation on a local Kubernetes cloud

Teacher `phi3.5` (Ollama, temp 0, seed 42) → sequence-level distillation → `pythia-70m` student → FastAPI service on k3d.

## Prerequisites
docker, k3d, kubectl, Python 3.11, [Ollama](https://ollama.com), `pip install locust ruff pytest`.

## Order of work
```bash
# 0. build + deploy cluster, SeaweedFS (ns data), buckets, images, secrets
make up                                    # RELEASE_REPO defaults to the value in the Makefile (edit it); models are seeded from the Release if it exists
# 1. teacher labelling (Task 1)
ollama pull phi3.5 && OLLAMA_HOST=0.0.0.0 ollama serve &
kubectl apply -f k8s/teacher-job.yaml      # 2 parallel workers in ns pipeline
kubectl -n pipeline logs -f job/teacher-labelling
#   then (port-forward 8333 + export S3_ENDPOINT/AWS_* as in scripts/up.sh):
python scripts/check_shards.py             # every id in exactly one shard
python worker/clean.py                     # -> datasets/v1/train.jsonl + train.sha256, prints the counts table
# 2. training (Task 2)
python scripts/s3tool.py get datasets v1/train.jsonl data/train.jsonl   # = make fetch-train; then COMMIT data/train.jsonl (data, not weights)
make train SUBSET=50                       # smoke test (writes training/loss_subset.csv + models/subset, never touches loss.csv/models/v1)
make train && make train-v2                # -> models/v1, models/v2, training/loss*.csv
make package                               # -> models/model-v1.tar.gz + models/v1/model.sha256 (upload tarballs as Release assets)
python scripts/s3tool.py putdir models/v1 models v1 ; python scripts/s3tool.py putdir models/v2 models v2
python scripts/predict.py teacher --out results/teacher_predictions.jsonl
python scripts/predict.py hf --model EleutherAI/pythia-70m --out results/base_predictions.jsonl
python scripts/predict.py hf --model models/v1 --out results/student_predictions.jsonl
for n in teacher base student; do python tools/score.py results/${n}_predictions.jsonl data/validation.jsonl --out results/${n}_validation.json; done
# 3. container limits test (Task 3): make memtest   # -> results/task3_memory.txt (50 requests, 1 CPU / 1 GiB, peak memory)
# 4. experiments (Task 4/7)
for e in hpa rolling recovery coldstart balance; do bash scripts/task4_experiments.sh $e; done
python scripts/cost.py --replicas 2 --cpu 1 --mem-gib 1 --stats results/loadtest_stats.csv
make down
```
Tests: `make test`, lint: `make lint`, network: `python tools/nacl_sim.py network/nacl.json network/packets_sample.jsonl --check`.

## Notes
* S3 credentials are generated randomly by `scripts/make_secrets.sh` and live only in Kubernetes Secrets.
* The HPA (min 1) would shrink the 2 starting replicas to 1; the `balance` experiment removes it temporarily.
* **Limitation:** single-node k3d on one laptop: no node-level fault tolerance; a Pod restart ≠ a machine failure.
