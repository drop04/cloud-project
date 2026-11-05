"""Teacher-labelling worker.

Env: SHARD_INDEX (from 0), SHARD_COUNT, S3_ENDPOINT, AWS_* (Secret), OLLAMA_URL, TEACHER_MODEL, PROMPT_FILE.
Takes the commands whose 0-based line number n satisfies n % SHARD_COUNT == SHARD_INDEX, asks the teacher
(phi3.5, temperature 0, seed 42) and writes {"id","text","teacher_raw"} lines to datasets/teacher/shard-<i>.jsonl.
Progress is flushed to S3 every FLUSH_EVERY records, and an existing partial shard is resumed, so a crashed
Pod does not restart from zero (the output stays exactly what the teacher produced).
"""
import json
import os
import time
import urllib.request

from common import read_text, s3_client, write_text

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://host.k3d.internal:11434")
MODEL = os.environ.get("TEACHER_MODEL", "phi3.5")
PROMPT_FILE = os.environ.get("PROMPT_FILE", "/app/prompts/teacher_prompt.txt")
FLUSH_EVERY = int(os.environ.get("FLUSH_EVERY", "25"))


def shard_lines(lines, index, count):
    """Pure sharding rule: line number n (from 0) belongs to shard n % count."""
    return [ln for n, ln in enumerate(lines) if n % count == index]


def build_prompt(template, command):
    # str.replace, not str.format: the template contains literal JSON braces.
    return template.replace("{command}", command)


def ask_teacher(prompt, retries=5):
    body = json.dumps({
        "model": MODEL, "prompt": prompt, "stream": False,
        "options": {"temperature": 0, "seed": 42, "num_predict": 128},
    }).encode()
    for attempt in range(retries):
        try:
            req = urllib.request.Request(f"{OLLAMA_URL}/api/generate", data=body,
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=600) as r:
                return json.loads(r.read())["response"]
        except Exception as e:  # network hiccup / Ollama busy
            print(f"teacher call failed ({e}); retry {attempt + 1}/{retries}", flush=True)
            time.sleep(5 * (attempt + 1))
    raise RuntimeError("teacher unreachable")


def main():
    index, count = int(os.environ["SHARD_INDEX"]), int(os.environ["SHARD_COUNT"])
    s3 = s3_client()
    template = open(PROMPT_FILE, encoding="utf-8").read()
    pool = [l for l in read_text(s3, "datasets", "commands_pool.jsonl").splitlines() if l.strip()]
    mine = [json.loads(l) for l in shard_lines(pool, index, count)]
    key = f"teacher/shard-{index}.jsonl"
    done = []
    try:
        done = [l for l in read_text(s3, "datasets", key).splitlines() if l.strip()]
    except Exception:
        pass
    done = done[: len(mine)]
    print(f"shard {index}/{count}: {len(mine)} commands, {len(done)} already done", flush=True)
    for rec in mine[len(done):]:
        raw = ask_teacher(build_prompt(template, rec["text"]))
        done.append(json.dumps({"id": rec["id"], "text": rec["text"], "teacher_raw": raw}, ensure_ascii=False))
        if len(done) % FLUSH_EVERY == 0:
            write_text(s3, "datasets", key, "\n".join(done) + "\n")
            print(f"  {len(done)}/{len(mine)}", flush=True)
    write_text(s3, "datasets", key, "\n".join(done) + "\n")
    print("done", flush=True)


if __name__ == "__main__":
    main()
