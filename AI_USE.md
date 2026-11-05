# AI use

## Tools
- **Claude (Anthropic)** — used to scaffold and review the repository: the teacher worker and `clean.py`,
  the training script, the FastAPI service and Dockerfile, the Kubernetes manifests, the Makefile and helper
  scripts, the GitHub Actions workflow, and a first draft of the subnet table and NACL.

## What I did myself
<!-- TODO: edit to match reality. Examples: wrote the teacher prompt, chose hyper-parameters, ran every experiment. -->
- Ran every command and experiment on my own machine; all numbers in `results/` and the report come from those runs.
- <!-- TODO: e.g. "Tuned the teacher prompt after inspecting N bad outputs" -->

## How I checked what the AI produced
- Subnets: recomputed by hand and with Python `ipaddress`; covered by `tests/test_network.py`.
- NACL: `python tools/nacl_sim.py network/nacl.json network/packets_sample.jsonl --check` (6/6), plus my own extra packets.
- `clean.py` and sharding: unit tests (`tests/`), and the count identity is asserted in code; I re-ran `clean.py`
  twice and compared the SHA-256.
- Service: unit tests for validation and `FAULT_INJECT`; manual `curl` tests for headers and status codes.
- Training/Docker/Kubernetes behaviour: verified by running them (`make train SUBSET=50`, `docker run --cpus 1 --memory 1g`,
  `kubectl` experiments), not by trusting the generated code.
- <!-- TODO: anything the AI got wrong that I caught and fixed -->

## Not done by AI
- No results, measurements or report numbers were typed in or estimated by AI.
