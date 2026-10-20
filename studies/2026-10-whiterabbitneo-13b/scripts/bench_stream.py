#!/usr/bin/env python3
"""bench_stream.py — legt vast WANNEER elk stukje antwoord binnenkomt, zodat de snelheid van een model zichtbaar af te spelen is.

  python3 bench_stream.py wrn13b qwen3:8b qwen2.5-coder:14b          # schrijft ~/bench-stream.json

Elk model krijgt dezelfde vraag, het model staat al in het geheugen (warm), temperatuur 0. Per model komt er een lijst
[seconden sinds het versturen, tekststuk] uit Ollama's stroom, plus de tijd tot het eerste stuk en tokens per seconde.
make_speed_demo.py speelt dat daarna af op de echte tijden (HTML en GIF); er wordt niets gesimuleerd.
"""
import json
import os
import sys
import time

import requests

HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
PROMPT = ("Explain in five short sentences how Kerberoasting works and how a defender can detect it. "
          "Answer in plain English without lists or headings.")
NUM_PREDICT = 220
CTX = 8192


def warm(model):
    requests.post(f"{HOST}/api/generate", json={"model": model, "prompt": "Say OK.", "stream": False, "keep_alive": "5m",
                                                "options": {"num_ctx": CTX, "num_predict": 3, "temperature": 0}}, timeout=900)


def stream(model, prompt=PROMPT, num_predict=NUM_PREDICT):
    body = {"model": model, "prompt": prompt, "stream": True, "keep_alive": "5m", "think": False,
            "options": {"num_ctx": CTX, "num_predict": num_predict, "temperature": 0.0, "seed": 7}}
    t0 = time.perf_counter()
    r = requests.post(f"{HOST}/api/generate", json=body, stream=True, timeout=900)
    if r.status_code == 400 and "think" in r.text.lower():
        body.pop("think")
        r = requests.post(f"{HOST}/api/generate", json=body, stream=True, timeout=900)
    r.raise_for_status()
    stukjes, final = [], {}
    for line in r.iter_lines():
        if not line:
            continue
        d = json.loads(line)
        if d.get("done"):
            final = d
            break
        if d.get("response"):
            stukjes.append([round(time.perf_counter() - t0, 3), d["response"]])
    totaal = time.perf_counter() - t0
    n = final.get("eval_count") or len(stukjes)
    gen_s = (final.get("eval_duration") or 0) / 1e9
    return {"model": model, "stukjes": stukjes, "ttft_s": stukjes[0][0] if stukjes else None, "totaal_s": round(totaal, 2),
            "tokens": n, "tok_s": round(n / gen_s, 1) if gen_s else None}


def main():
    modellen = sys.argv[1:]
    if not modellen:
        print(__doc__)
        return
    out = {"vraag": PROMPT, "modellen": {}}
    for m in modellen:
        try:
            warm(m)
            out["modellen"][m] = r = stream(m)
        except Exception as e:
            print(f"{m}: FOUT {type(e).__name__}: {e}", flush=True)
            continue
        print(f"{m:34s} eerste stuk na {r['ttft_s']:.2f}s | {r['tok_s']} tok/s | {r['tokens']} tokens in {r['totaal_s']}s", flush=True)
        requests.post(f"{HOST}/api/generate", json={"model": m, "keep_alive": 0}, timeout=60)
    json.dump(out, open(os.path.expanduser("~/bench-stream.json"), "w"), ensure_ascii=False, indent=1)
    print("opgeslagen: ~/bench-stream.json")


if __name__ == "__main__":
    main()
