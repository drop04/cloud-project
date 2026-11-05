"""Clean teacher shards -> datasets/v1/train.jsonl (+ .sha256) and print the counts table.

Usage:
  python worker/clean.py                        # reads datasets/teacher/shard-*.jsonl from S3 (S3_ENDPOINT, AWS_*)
  python worker/clean.py --local DIR --out DIR  # reads DIR/shard-*.jsonl, writes OUT/train.jsonl, train.sha256
Order of rules: (a) invalid JSON, (b) key set, (c) intent, (d) slot value, then (e) duplicate commands
(on records that survived a-d, smallest id kept), so input = a+b+c+d+dup+kept always holds.
The output is deterministic (sorted by id, fixed serialisation), so re-running gives the same checksum.
"""
import argparse
import glob
import hashlib
import json
import os
import re

KEYS = {"intent", "date", "time", "place"}
INTENTS = {"alarm_set", "alarm_query", "calendar_set", "calendar_query", "calendar_remove",
           "weather_query", "datetime_query", "recommendation_events"}


def _norm(s):
    return re.sub(r"\s+", " ", s.strip().lower())


def check(rec):
    """Return None if the record is good, else the reason code 'a'|'b'|'c'|'d'."""
    try:
        obj = json.loads(rec["teacher_raw"].strip())
    except (ValueError, AttributeError):
        return "a"
    if not isinstance(obj, dict):
        return "a"
    if set(obj) != KEYS:
        return "b"
    if obj["intent"] not in INTENTS:
        return "c"
    text = _norm(rec["text"])
    for slot in ("date", "time", "place"):
        v = obj[slot]
        if v is None:
            continue
        if not isinstance(v, str) or not _norm(v) or _norm(v) not in text:
            return "d"
    return None


def clean(records):
    counts = {"input": len(records), "a": 0, "b": 0, "c": 0, "d": 0, "duplicates": 0, "kept": 0}
    good = []
    for rec in sorted(records, key=lambda r: r["id"]):
        reason = check(rec)
        if reason:
            counts[reason] += 1
        else:
            good.append(rec)
    seen, kept = set(), []
    for rec in good:
        k = _norm(rec["text"])
        if k in seen:
            counts["duplicates"] += 1
        else:
            seen.add(k)
            kept.append(rec)
    counts["kept"] = len(kept)
    assert counts["input"] == sum(counts[k] for k in ("a", "b", "c", "d", "duplicates", "kept"))
    return kept, counts


def serialise(kept):
    return "".join(json.dumps({"id": r["id"], "text": r["text"], "teacher_raw": r["teacher_raw"]},
                              ensure_ascii=False) + "\n" for r in kept)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--local", help="directory holding shard-*.jsonl instead of S3")
    ap.add_argument("--out", help="output directory (local mode)")
    a = ap.parse_args()
    records = []
    if a.local:
        for f in sorted(glob.glob(os.path.join(a.local, "shard-*.jsonl"))):
            records += [json.loads(l) for l in open(f, encoding="utf-8") if l.strip()]
    else:
        from common import read_text, s3_client
        s3 = s3_client()
        keys = [o["Key"] for o in s3.list_objects_v2(Bucket="datasets", Prefix="teacher/").get("Contents", [])
                if o["Key"].endswith(".jsonl")]
        for k in sorted(keys):
            records += [json.loads(l) for l in read_text(s3, "datasets", k).splitlines() if l.strip()]
    kept, counts = clean(records)
    body = serialise(kept)
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    sha_line = f"{digest}  train.jsonl\n"
    if a.local:
        os.makedirs(a.out, exist_ok=True)
        open(os.path.join(a.out, "train.jsonl"), "w", encoding="utf-8").write(body)
        open(os.path.join(a.out, "train.sha256"), "w").write(sha_line)
    else:
        from common import write_text
        write_text(s3, "datasets", "v1/train.jsonl", body)
        write_text(s3, "datasets", "v1/train.sha256", sha_line)
    print(json.dumps(counts, indent=2))
    print("sha256", digest)


if __name__ == "__main__":
    main()
