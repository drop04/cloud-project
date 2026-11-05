"""Package a model dir deterministically and write checksums.

  python scripts/package_model.py models/v1 v1
-> models/v1.tar.gz  (release asset, reproducible: sorted, mtime 0, no owner)
-> models/v1/model.sha256        sha256 of the release asset  ("<hash>  model-v1.tar.gz")
-> models/v1/model.files.sha256  per-file sha256
"""
import gzip, hashlib, io, os, sys, tarfile

src, ver = sys.argv[1], sys.argv[2]
skip = {"model.sha256", "model.files.sha256"}
files = sorted(f for f in os.listdir(src) if f not in skip and os.path.isfile(os.path.join(src, f)))
sha = lambda b: hashlib.sha256(b).hexdigest()
with open(os.path.join(src, "model.files.sha256"), "w") as f:
    for n in files:
        f.write(f"{sha(open(os.path.join(src, n), 'rb').read())}  {n}\n")
buf = io.BytesIO()
with tarfile.open(fileobj=buf, mode="w") as tar:
    for n in files:
        ti = tarfile.TarInfo(n)
        data = open(os.path.join(src, n), "rb").read()
        ti.size, ti.mtime, ti.uid, ti.gid, ti.uname, ti.gname, ti.mode = len(data), 0, 0, 0, "", "", 0o644
        tar.addfile(ti, io.BytesIO(data))
asset = os.path.join(os.path.dirname(src.rstrip("/")) or ".", f"model-{ver}.tar.gz")
with open(asset, "wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", mtime=0, filename="") as gz:
    gz.write(buf.getvalue())
digest = sha(open(asset, "rb").read())
open(os.path.join(src, "model.sha256"), "w").write(f"{digest}  model-{ver}.tar.gz\n")
print(asset, digest)
