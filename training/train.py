"""Sequence-level distillation: fine-tune pythia-70m on the teacher's replies (CPU, PyTorch + Transformers).

  python training/train.py --config training/config.yaml [--subset 50]
Reads ONLY the config file (plus --subset, used for the smoke test). Loss is computed on the JSON part only.
"""
import argparse
import csv
import os
import random
import sys

import numpy as np
import torch
import yaml
from transformers import AutoModelForCausalLM, AutoTokenizer

sys.path.insert(0, os.path.dirname(__file__))
from prompt_format import prompt_text, target_text  # noqa: E402


def set_seed(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.use_deterministic_algorithms(True, warn_only=True)


def encode(tok, rec, max_len):
    p = tok(prompt_text(rec["text"]), add_special_tokens=False)["input_ids"]
    t = tok(target_text(rec["teacher_raw"]), add_special_tokens=False)["input_ids"] + [tok.eos_token_id]
    ids = (p + t)[:max_len]
    labels = ([-100] * len(p) + t)[:max_len]
    return ids, labels


def collate(batch, pad_id):
    n = max(len(i) for i, _ in batch)
    ids = torch.tensor([i + [pad_id] * (n - len(i)) for i, _ in batch])
    lab = torch.tensor([l + [-100] * (n - len(l)) for _, l in batch])
    att = torch.tensor([[1] * len(i) + [0] * (n - len(i)) for i, _ in batch])
    return ids, att, lab


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="training/config.yaml")
    ap.add_argument("--subset", type=int, default=0)
    a = ap.parse_args()
    cfg = yaml.safe_load(open(a.config))
    set_seed(cfg["seed"])
    import json
    recs = [json.loads(l) for l in open(cfg["train_file"], encoding="utf-8") if l.strip()]
    recs = recs[: cfg["max_records"]]          # first 1,500 records, never more
    if a.subset:
        recs = recs[: a.subset]
    # smoke-test runs must never overwrite the real loss file or models/v1
    loss_path = "training/loss_subset.csv" if a.subset else cfg["loss_csv"]
    out_dir = "models/subset" if a.subset else cfg["output_dir"]
    print(f"training on {len(recs)} records; torch {torch.__version__}", flush=True)

    tok = AutoTokenizer.from_pretrained(cfg["model_name"])
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    model = AutoModelForCausalLM.from_pretrained(cfg["model_name"])
    model.train()
    data = [encode(tok, r, cfg["max_seq_len"]) for r in recs]
    opt = torch.optim.AdamW(model.parameters(), lr=float(cfg["learning_rate"]))
    gen = torch.Generator().manual_seed(cfg["seed"])
    bs = cfg["batch_size"]
    os.makedirs(os.path.dirname(loss_path) or ".", exist_ok=True)
    with open(loss_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["epoch", "train_loss"])
        for ep in range(1, cfg["epochs"] + 1):
            order = torch.randperm(len(data), generator=gen).tolist()
            total, tokens = 0.0, 0
            for s in range(0, len(order), bs):
                ids, att, lab = collate([data[i] for i in order[s:s + bs]], tok.pad_token_id)
                out = model(input_ids=ids, attention_mask=att, labels=lab)
                out.loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                opt.step()
                opt.zero_grad()
                n = int((lab[:, 1:] != -100).sum())
                total += out.loss.item() * n
                tokens += n
            loss = total / max(tokens, 1)
            w.writerow([ep, f"{loss:.6f}"])
            f.flush()
            print(f"epoch {ep}/{cfg['epochs']} loss {loss:.4f}", flush=True)
    os.makedirs(out_dir, exist_ok=True)
    model.save_pretrained(out_dir)
    tok.save_pretrained(out_dir)
    print("saved to", out_dir)


if __name__ == "__main__":
    main()
