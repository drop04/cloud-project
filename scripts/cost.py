"""Cost + SLO worksheet from rate_card.json and a Locust stats CSV.
  python scripts/cost.py --replicas 2 --cpu 1 --mem-gib 1 --stats results/loadtest_stats.csv --slo 99
"""
import argparse, csv, json

ap = argparse.ArgumentParser()
ap.add_argument("--replicas", type=float, required=True)
ap.add_argument("--cpu", type=float, default=1.0)
ap.add_argument("--mem-gib", type=float, default=1.0)
ap.add_argument("--stats", default="results/loadtest_stats.csv")
ap.add_argument("--rate-card", default="data/rate_card.json")
ap.add_argument("--slo", type=float, default=99.0, help="target success %% per load-test run")
a = ap.parse_args()
rc = json.load(open(a.rate_card))
row = next(r for r in csv.DictReader(open(a.stats)) if r["Name"] == "Aggregated")
reqs, fails, rps = int(row["Request Count"]), int(row["Failure Count"]), float(row["Requests/s"])
hourly = a.replicas * (a.cpu * rc["vcpu_hour"] + a.mem_gib * rc["gib_memory_hour"])
per_hour = rps * 3600
print(f"hourly cost = {a.replicas} x ({a.cpu} x {rc['vcpu_hour']} + {a.mem_gib} x {rc['gib_memory_hour']}) = {hourly:.4f} {rc['currency']}")
print(f"requests/hour = {rps:.3f} rps x 3600 = {per_hour:.1f}")
print(f"cost per 1000 requests = {hourly:.4f} / {per_hour:.1f} x 1000 = {hourly / per_hour * 1000:.4f} {rc['currency']}")
budget = reqs * (100 - a.slo) / 100
print(f"SLO {a.slo}% success over one run of {reqs} requests: error budget = {budget:.2f} requests; used {fails} ({(fails / budget * 100) if budget else 0:.1f}% of budget)")
