"""Tiny S3 helper (SeaweedFS). Uses S3_ENDPOINT / AWS_* env vars.
  s3tool.py mkbuckets | put LOCAL BUCKET KEY | putdir LOCALDIR BUCKET PREFIX | get BUCKET KEY LOCAL | getdir BUCKET PREFIX LOCALDIR
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "worker"))
from common import s3_client

s3 = s3_client(); cmd, args = sys.argv[1], sys.argv[2:]
if cmd == "mkbuckets":
    have = {b["Name"] for b in s3.list_buckets()["Buckets"]}
    for b in ("datasets", "models"):
        if b not in have: s3.create_bucket(Bucket=b)
    print("buckets:", [b["Name"] for b in s3.list_buckets()["Buckets"]])
elif cmd == "put":
    s3.upload_file(args[0], args[1], args[2])
elif cmd == "putdir":
    for n in sorted(os.listdir(args[0])):
        p = os.path.join(args[0], n)
        if os.path.isfile(p): s3.upload_file(p, args[1], f"{args[2].rstrip('/')}/{n}"); print("uploaded", args[1], n)
elif cmd == "get":
    os.makedirs(os.path.dirname(args[2]) or ".", exist_ok=True); s3.download_file(args[0], args[1], args[2])
elif cmd == "getdir":
    os.makedirs(args[2], exist_ok=True)
    for o in s3.list_objects_v2(Bucket=args[0], Prefix=args[1]).get("Contents", []):
        if not o["Key"].endswith("/"): s3.download_file(args[0], o["Key"], os.path.join(args[2], os.path.basename(o["Key"])))
