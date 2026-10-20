#!/usr/bin/env python3
"""bench_perf.py — meet hoe snel Ollama-modellen draaien op deze machine (draai op de Mac, andere belasting uit).

  python3 bench_perf.py wrn13b qwen2.5-coder:14b qwen3:8b

Per model, uit de tellers die Ollama zelf teruggeeft (geen eigen klok voor tokens):
  koude laadtijd        model uit het geheugen halen en opnieuw laden
  promptverwerking      tokens per seconde bij een lange prompt (elke ronde een uniek begin, zodat de prefix-cache niets verbergt)
  generatie             tokens per seconde bij het schrijven van een antwoord (mediaan van RONDES)
  geheugen              grootte in RAM en hoeveel daarvan op de GPU (Apple unified memory) volgens /api/ps
Resultaat: tabel op stdout en ~/bench-perf.json (inclusief ruwe rondes).
"""
import json
import os
import statistics
import subprocess
import sys
import time

import requests

HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
CTX = 8192
RONDES = 3
GEN_TOKENS = 256
LOG_LINE = "Oct 12 03:{m:02d}:{s:02d} srv sshd[{p}]: Failed password for invalid user admin from 203.0.113.{h} port {q} ssh2\n"


def long_prompt(unique: int) -> str:
    regels = "".join(LOG_LINE.format(m=i % 60, s=(i * 7) % 60, p=8000 + i, h=(i * 3 + unique) % 250, q=40000 + i) for i in range(60))
    return f"[run {unique}-{time.time_ns()}]\nHere is an SSH auth log:\n{regels}\nSummarise the attack in one sentence."


def generate(model, prompt, num_predict, keep_alive="5m"):
    body = {"model": model, "prompt": prompt, "stream": False, "keep_alive": keep_alive, "raw": False,
            "options": {"num_ctx": CTX, "num_predict": num_predict, "temperature": 0.0, "seed": 7}}
    t = time.time()
    r = requests.post(f"{HOST}/api/generate", json=body, timeout=900)
    r.raise_for_status()
    d = r.json()
    d["wall_s"] = time.time() - t
    return d


def rate(count, duration_ns):
    return count / (duration_ns / 1e9) if duration_ns else 0.0


def unload(model):
    requests.post(f"{HOST}/api/generate", json={"model": model, "keep_alive": 0}, timeout=60)
    time.sleep(3)


def memory(model):
    for m in requests.get(f"{HOST}/api/ps", timeout=10).json().get("models", []):
        if m.get("name", "").startswith(model.split(":")[0]) or m.get("model") == model:
            return {"ram_gb": round(m.get("size", 0) / 1e9, 2), "gpu_gb": round(m.get("size_vram", 0) / 1e9, 2),
                    "context": m.get("context_length")}
    return {}


def bench(model):
    unload(model)
    cold = generate(model, "Say OK.", 4)
    laadtijd = cold.get("load_duration", 0) / 1e9
    mem = memory(model)
    pp = [generate(model, long_prompt(i), 1) for i in range(RONDES)]
    pp_rates = [rate(d["prompt_eval_count"], d["prompt_eval_duration"]) for d in pp]
    gen = [generate(model, f"Write a detailed explanation of how Kerberoasting works and how to defend against it. (variant {i})", GEN_TOKENS)
           for i in range(RONDES)]
    gen_rates = [rate(d["eval_count"], d["eval_duration"]) for d in gen]
    ttft = [(d["load_duration"] + d["prompt_eval_duration"]) / 1e9 for d in pp]
    unload(model)
    return {"model": model, "laadtijd_s": round(laadtijd, 1), **mem,
            "prompt_tokens": pp[0]["prompt_eval_count"], "prompt_tok_s": round(statistics.median(pp_rates), 1),
            "ttft_lange_prompt_s": round(statistics.median(ttft), 2),
            "gen_tok_s": round(statistics.median(gen_rates), 1), "gen_tok_s_min": round(min(gen_rates), 1), "gen_tok_s_max": round(max(gen_rates), 1),
            "gen_tokens": [d["eval_count"] for d in gen], "ruw_prompt_tok_s": [round(x, 1) for x in pp_rates],
            "ruw_gen_tok_s": [round(x, 1) for x in gen_rates]}


def hardware():
    def sh(cmd):
        try:
            return subprocess.run(cmd, capture_output=True, text=True, timeout=20).stdout.strip()
        except Exception:
            return ""
    return {"chip": sh(["sysctl", "-n", "machdep.cpu.brand_string"]), "ram_gb": round(int(sh(["sysctl", "-n", "hw.memsize"]) or 0) / 2**30),
            "macos": sh(["sw_vers", "-productVersion"]), "ollama": sh(["ollama", "--version"]).replace("ollama version is ", ""),
            "datum": time.strftime("%Y-%m-%d %H:%M")}


def main():
    models = sys.argv[1:]
    if not models:
        print(__doc__)
        return
    out = {"hardware": hardware(), "instellingen": {"num_ctx": CTX, "rondes": RONDES, "gen_tokens": GEN_TOKENS}, "modellen": {}}
    for m in models:
        try:
            out["modellen"][m] = r = bench(m)
        except Exception as e:
            print(f"{m}: FOUT {type(e).__name__}: {e}", flush=True)
            continue
        print(f"{m:24s} laden {r['laadtijd_s']:5.1f}s | prompt {r['prompt_tok_s']:7.1f} tok/s ({r['prompt_tokens']} tok) | "
              f"gen {r['gen_tok_s']:5.1f} tok/s ({r['gen_tok_s_min']}-{r['gen_tok_s_max']}) | RAM {r.get('ram_gb', '?')} GB", flush=True)
    path = os.path.expanduser("~/bench-perf.json")
    json.dump(out, open(path, "w"), indent=1, ensure_ascii=False)
    print("opgeslagen:", path)


if __name__ == "__main__":
    main()
