import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in ("worker", "service", "training"):
    sys.path.insert(0, os.path.join(ROOT, p))
os.environ["SKIP_MODEL_LOAD"] = "1"
