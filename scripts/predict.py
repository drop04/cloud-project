"""Produce a predictions.jsonl ({"id","prediction"}) for score.py.

  predict.py teacher --data data/validation.jsonl --out results/teacher_predictions.jsonl   (Ollama, same prompt/settings as Task 1)
  predict.py hf --model EleutherAI/pythia-70m|DIR --data ... --out ...                      (base or trained student)
Base and student use the same prompt and greedy decoding; the output is cut at the first newline.
"""
import argparse, json, os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "training"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "worker"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["teacher", "hf"])
    ap.add_argument("--model", default="EleutherAI/pythia-70m")
    ap.add_argument("--data", default="data/validation.jsonl")
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-new-tokens", type=int, default=64)
    ap.add_argument("--prompt", default="prompts/teacher_prompt.txt")
    a = ap.parse_args()
    rows = [json.loads(l) for l in open(a.data, encoding="utf-8") if l.strip()]
    if a.mode == "teacher":
        os.environ.setdefault("OLLAMA_URL", "http://localhost:11434")
        os.environ["PROMPT_FILE"] = a.prompt
        import worker as w  # reuses the exact Task 1 call (temperature 0, seed 42)
        tpl = open(a.prompt, encoding="utf-8").read()
        gen = lambda text: w.ask_teacher(w.build_prompt(tpl, text))
    else:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        from prompt_format import prompt_text
        torch.manual_seed(42)
        tok = AutoTokenizer.from_pretrained(a.model)
        model = AutoModelForCausalLM.from_pretrained(a.model).eval()

        def gen(text):
            ids = tok(prompt_text(text), return_tensors="pt")
            with torch.no_grad():
                out = model.generate(**ids, max_new_tokens=a.max_new_tokens, do_sample=False,
                                     pad_token_id=tok.eos_token_id)
            return tok.decode(out[0][ids["input_ids"].shape[1]:], skip_special_tokens=True).split("\n")[0].strip()
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps({"id": r["id"], "prediction": gen(r["text"])}, ensure_ascii=False) + "\n")
    print("wrote", a.out)


if __name__ == "__main__":
    main()
