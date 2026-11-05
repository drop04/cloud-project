"""Command-parser inference service.  POST /parse, GET /healthz, GET /readyz  (port 8000).

Env: MODEL_URI (s3://bucket/prefix/), MODEL_VERSION, S3_ENDPOINT, MAX_NEW_TOKENS,
     FAULT_INJECT (1 => replace model output with "not json" before validation).
Credentials (AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY) are injected from a Kubernetes Secret.
"""
import json
import os
import threading

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel

HERE = os.path.dirname(os.path.abspath(__file__))
SCHEMA = json.load(open(os.path.join(HERE, "schema.json"), encoding="utf-8"))
KEYS = SCHEMA["keys"]
INTENTS = set(SCHEMA["intents"])
MODEL_DIR = os.environ.get("MODEL_DIR", "/tmp/model")

app = FastAPI()
state = {"ready": False, "model": None, "tok": None}
gen_lock = threading.Lock()


def validate_output(raw):
    """Return the parsed 4-key object if `raw` satisfies schema.json, else None."""
    try:
        obj = json.loads(raw)
    except (ValueError, TypeError):
        return None
    if not isinstance(obj, dict) or set(obj) != set(KEYS):
        return None
    if obj["intent"] not in INTENTS:
        return None
    for k in ("date", "time", "place"):
        if obj[k] is not None and not isinstance(obj[k], str):
            return None
    return {k: obj[k] for k in KEYS}


def prompt_text(command):  # keep identical to training/prompt_format.py
    return f"Command: {command}\nJSON:"


def download_model(uri, endpoint, dest):
    import boto3
    assert uri.startswith("s3://"), "MODEL_URI must be s3://bucket/prefix/"
    bucket, _, prefix = uri[5:].partition("/")
    prefix = prefix.rstrip("/") + "/"
    s3 = boto3.client("s3", endpoint_url=endpoint, region_name="us-east-1",
                      aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
                      aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"])
    os.makedirs(dest, exist_ok=True)
    n = 0
    for o in s3.list_objects_v2(Bucket=bucket, Prefix=prefix).get("Contents", []):
        name = o["Key"][len(prefix):]
        if name and "/" not in name:
            print(f"downloading {o['Key']} ({o['Size']} bytes)", flush=True)
            s3.download_file(bucket, o["Key"], os.path.join(dest, name))
            n += 1
    if n == 0:
        raise RuntimeError(f"no objects under {uri}")


def load_model():
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    download_model(os.environ["MODEL_URI"], os.environ["S3_ENDPOINT"], MODEL_DIR)
    torch.set_num_threads(int(os.environ.get("TORCH_THREADS", "1")))
    state["tok"] = AutoTokenizer.from_pretrained(MODEL_DIR)
    state["model"] = AutoModelForCausalLM.from_pretrained(MODEL_DIR).eval()
    state["ready"] = True
    print("model loaded, ready", flush=True)


def generate(text):
    import torch
    tok, model = state["tok"], state["model"]
    ids = tok(prompt_text(text), return_tensors="pt")
    with gen_lock, torch.no_grad():
        out = model.generate(**ids, max_new_tokens=int(os.environ.get("MAX_NEW_TOKENS", "64")),
                             do_sample=False, pad_token_id=tok.eos_token_id)
    return tok.decode(out[0][ids["input_ids"].shape[1]:], skip_special_tokens=True).split("\n")[0].strip()


@app.on_event("startup")
def startup():
    if os.environ.get("SKIP_MODEL_LOAD") == "1":  # unit tests only
        return

    def run():
        try:
            load_model()
        except Exception as e:  # stay alive (healthz 200) but never ready; probes/logs show why
            print(f"MODEL LOAD FAILED: {e!r}", flush=True)
    threading.Thread(target=run, daemon=True).start()


class ParseRequest(BaseModel):
    text: str


@app.get("/healthz")
def healthz():
    return {"status": "alive"}


@app.get("/readyz")
def readyz():
    return JSONResponse({"ready": state["ready"]}, status_code=200 if state["ready"] else 503)


@app.post("/parse")
def parse(req: ParseRequest):
    if not state["ready"]:
        return JSONResponse({"error": "model_not_ready"}, status_code=503)
    raw = "not json" if os.environ.get("FAULT_INJECT") == "1" else generate(req.text)
    obj = validate_output(raw)
    if obj is None:
        return JSONResponse({"error": "invalid_model_output"}, status_code=500)
    return JSONResponse(obj, headers={"X-Model-Version": os.environ.get("MODEL_VERSION", "unknown"),
                                      "X-Served-By": os.environ.get("HOSTNAME", "local")})
