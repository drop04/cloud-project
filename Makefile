SUBSET ?= 0
CONFIG ?= training/config.yaml
RELEASE_REPO ?= drop04/cloud-project   # CHANGE to your GitHub user/repo
export RELEASE_REPO

.PHONY: up down train train-v2 test lint package fetch-train loadtest cost memtest

up:            ## build + deploy the whole system (cluster, storage, images, app)
	bash scripts/up.sh

down:          ## delete the cluster
	k3d cluster delete cloudproj

train:         ## make train [SUBSET=50] [CONFIG=training/config_v2.yaml] - reads only the config file
	python training/train.py --config $(CONFIG) $(if $(filter-out 0,$(SUBSET)),--subset $(SUBSET),)

train-v2:
	$(MAKE) train CONFIG=training/config_v2.yaml

fetch-train:   ## fallback: pull data/train.jsonl from SeaweedFS (needs port-forward 8333 + S3_ENDPOINT/AWS_* env, see README)
	python scripts/s3tool.py get datasets v1/train.jsonl data/train.jsonl

memtest:       ## Task 3: 50 sequential requests at 1 CPU / 1 GiB, peak memory -> results/
	bash scripts/memtest.sh

package:       ## deterministic release assets + model.sha256
	python scripts/package_model.py models/v1 v1
	python scripts/package_model.py models/v2 v2

test:
	python -m pytest -q

lint:
	ruff check .

loadtest:
	mkdir -p results && locust -f tools/locustfile.py --headless --users 4 --spawn-rate 4 --run-time 2m \
	  --host http://localhost:8080 --csv results/loadtest
