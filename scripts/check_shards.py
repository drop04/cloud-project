"""Check every pool id appears in exactly one shard (no gaps, no repeats). Needs S3 env vars."""
import json, sys
sys.path.insert(0, "worker")
from common import read_text, s3_client
s3 = s3_client()
pool = [json.loads(l)["id"] for l in read_text(s3, "datasets", "commands_pool.jsonl").splitlines() if l.strip()]
seen = []
for o in s3.list_objects_v2(Bucket="datasets", Prefix="teacher/").get("Contents", []):
    if o["Key"].endswith(".jsonl"):
        ids = [json.loads(l)["id"] for l in read_text(s3, "datasets", o["Key"]).splitlines() if l.strip()]
        print(o["Key"], len(ids)); seen += ids
print("pool", len(pool), "seen", len(seen), "gaps", len(set(pool) - set(seen)), "repeats", len(seen) - len(set(seen)))
sys.exit(0 if sorted(seen) == sorted(pool) else 1)
