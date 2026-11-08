# AI use

## Tools

- **Claude (Anthropic)**, used through the claude.ai chat interface. It was used for:
  - **Repository scaffolding and review:** the teacher worker and `clean.py`, the training script, the FastAPI
    service and Dockerfile, the Kubernetes manifests, the Makefile and helper scripts, the GitHub Actions
    workflow, and a first draft of the subnet table and NACL.
  - **Debugging and guidance while running the project:** step-by-step commands, reading error messages and
    logs I pasted, and explaining results.
  - **The report:** the structure of `report/report.pdf`, a script that collected my result files into one
    text file, copying the measured values from my pasted output into the report draft, and drafts of the
    written explanations (sequence-level versus logit-based distillation, why NACL replies need rules, the
    limitations and improvements in the review table, and this AI-use section).
  - **Formatting:** converting the finished report to PDF.

## What I did myself

- Ran the teacher labelling, training (v1 and v2), prediction and scoring, container tests, Kubernetes
  experiments, load test, cost calculation, unit tests and network simulation on my own machine, and saved the
  outputs in `results/`.
- Fixed the environment problems that came up while running (Python version, missing `pip` in the virtual
  environment, Ollama listening only on localhost, port clashes, restarting the cluster) and re-ran the
  affected steps.
- Chose to report the rolling-update result as measured (2.17% failures against the 0.5% target) and to
  explain its causes in the report, instead of changing the deployment and re-running the experiment.

## How I checked what the AI produced

- **Unit tests:** `make test` runs the 11 tests in `tests/` (cleaning, sharding, network, service); all pass.
- **Subnets:** covered by `tests/test_network.py`.
- **NACL:** `python tools/nacl_sim.py network/nacl.json network/packets_sample.jsonl --check` gives 6 of 6.
- **`clean.py` and sharding:** the counts add up (3,000 = 1,551 + 85 + 2 + 34 + 16 + 1,312), and running
  `clean.py` twice gave the same SHA-256, which also matches `sha256sum data/train.jsonl`.
- **Service:** unit tests for validation and `FAULT_INJECT`; manual `curl` requests for headers, status codes
  and `/readyz`, saved in `results/`.
- **Training, Docker and Kubernetes behaviour:** verified by running them (`make train SUBSET=50`,
  `docker run --cpus 1 --memory 1g`, the `kubectl` experiments), not by trusting the generated code.

## Where the AI was wrong

- **Environment:** it gave install steps that failed on my Python 3.14. The pinned packages need a Python
  3.11 virtual environment, and `make up` also needed `pip` inside it. `make test` additionally needed
  `fastapi` and `httpx`, which `training/requirements.txt` does not list.
- **Teacher score:** it expected the teacher to score well above the student once its trailing "Note:" text
  was cut. Measured full-frame accuracy was 40% for the teacher and 41% for the student.
- **Cleaning:** it guessed that cleaning would discard about two thirds of the teacher labels. The counts show
  1,551 of 3,000 (51.7%) removed, and the training set therefore has 1,312 records, below the 1,500 limit.

## Not done by AI

- Claude did not run any command on my machine. Every measurement in `results/` and in the report comes from
  my own runs.
- Claude did not estimate or invent any measured value. It copied values from the output files I pasted into
  the report draft, and worked out derived figures (percentages, differences) from those values.