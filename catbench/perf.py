"""Speed and memory: cold load time, prompt processing, generation speed, memory, and behaviour with several agents at once.
Everything comes from the counters Ollama itself reports; nothing is estimated."""
import json
import statistics
import threading
import time
from pathlib import Path

from .ollama import Client

LOG_LINE = "Oct 12 03:{m:02d}:{s:02d} srv sshd[{p}]: Failed password for invalid user admin from 203.0.113.{h} port {q} ssh2\n"
ROUNDS = 3
GEN_TOKENS = 256


def long_prompt(unique: int) -> str:
    """A log of a few thousand tokens with a unique first line, so Ollama's prompt cache cannot hide the processing time."""
    lines = "".join(LOG_LINE.format(m=i % 60, s=(i * 7) % 60, p=8000 + i, h=(i * 3 + unique) % 250, q=40000 + i) for i in range(60))
    return f"[run {unique}-{time.time_ns()}]\nHere is an SSH auth log:\n{lines}\nSummarise the attack in one sentence."


def _rate(count: int, seconds: float) -> float:
    return count / seconds if seconds else 0.0


def _generate(client: Client, model: str, prompt: str, num_predict: int, num_ctx: int = 8192) -> dict:
    body = {"model": model, "prompt": prompt, "stream": False, "keep_alive": "10m", "think": False,
            "options": {"num_ctx": num_ctx, "num_predict": num_predict, "temperature": 0.0, "seed": 7}}
    t = time.time()
    d = client._json("/api/generate", body)
    d["wall_s"] = time.time() - t
    return d


def memory_of(client: Client, model: str) -> dict:
    for m in client.ps():
        if m.get("name") == model or m.get("model") == model:
            return {"memory_gb": round(m.get("size", 0) / 1e9, 2), "gpu_gb": round(m.get("size_vram", 0) / 1e9, 2), "context": m.get("context_length")}
    return {}


def measure(client: Client, model: str, rounds: int = ROUNDS) -> dict:
    client.unload(model)
    cold = _generate(client, model, "Say OK.", 4)
    mem = memory_of(client, model)
    reading = [_generate(client, model, long_prompt(i), 1) for i in range(rounds)]
    writing = [_generate(client, model, f"Write a detailed explanation of how Kerberoasting works and how to defend against it. (variant {i})", GEN_TOKENS)
               for i in range(rounds)]
    read_rates = [_rate(d["prompt_eval_count"], d["prompt_eval_duration"] / 1e9) for d in reading]
    write_rates = [_rate(d["eval_count"], d["eval_duration"] / 1e9) for d in writing]
    out = {"model": model, "cold_load_s": round(cold.get("load_duration", 0) / 1e9, 1), **mem,
           "prompt_tokens": reading[0]["prompt_eval_count"], "reading_tok_s": round(statistics.median(read_rates), 1),
           "first_token_long_prompt_s": round(statistics.median([(d["load_duration"] + d["prompt_eval_duration"]) / 1e9 for d in reading]), 2),
           "generation_tok_s": round(statistics.median(write_rates), 1), "generation_min": round(min(write_rates), 1),
           "generation_max": round(max(write_rates), 1), "generated_tokens": [d["eval_count"] for d in writing]}
    client.unload(model)
    return out


def parallel(client: Client, model: str, agents: int = 5, tokens: int = 120, note: str = "") -> dict:
    """Sends `agents` requests at the same moment and records memory and total time. What it shows depends on how the server is
    configured (OLLAMA_NUM_PARALLEL); pass a note describing that setting."""
    client.unload(model)
    _generate(client, model, "Explain topic 0 of network security in detail.", 40)
    solo_mem = memory_of(client, model)
    threads = [threading.Thread(target=_generate, args=(client, model, f"Explain topic {i} of network security in detail.", tokens)) for i in range(agents)]
    t = time.time()
    for th in threads:
        th.start()
    time.sleep(6)
    during = memory_of(client, model)
    for th in threads:
        th.join()
    total = time.time() - t
    client.unload(model)
    return {"model": model, "agents": agents, "tokens_per_request": tokens, "memory_one_request_gb": solo_mem.get("memory_gb"),
            "memory_during_parallel_gb": during.get("memory_gb"), "seconds_for_all": round(total, 1),
            "total_tok_s": round(agents * tokens / total, 1), "per_agent_tok_s": round(tokens / total, 1), "note": note}


def save(path: Path, data: dict):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
