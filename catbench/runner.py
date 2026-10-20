"""Runs models over the tracks and stores every answer. Re-running skips what is already stored, so an interrupted run can simply be restarted."""
import json
import re
import time
from pathlib import Path

from . import system
from .ollama import Client, OllamaError
from .scoring import score_task
from .tasks import TRACKS, load_track, task_prompt

MAX_ANSWER_CHARS = 6000


def safe(tag: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", tag)


def result_path(run_dir: Path, model: str, track: str) -> Path:
    return Path(run_dir) / safe(model) / f"{track}.jsonl"


def read_records(path: Path) -> list:
    out = []
    try:
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
    except OSError:
        pass
    return out


def write_manifest(run_dir: Path, run_id: str, client, models: list, settings: dict):
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "manifest.json"
    try:
        old = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        old = {}
    digests = old.get("models", {})
    try:
        for m in client.tags():
            if m.get("name") in models or m.get("model") in models:
                digests[m.get("name")] = {"digest": (m.get("digest") or "")[:16], "size_gb": round(m.get("size", 0) / 1e9, 2),
                                          "details": m.get("details", {})}
        version = client.version()
    except OllamaError:
        version = old.get("ollama", "?")
    manifest = {"run_id": run_id, "date": old.get("date") or system.stamp(), "machine": old.get("machine") or system.machine_info(),
                "ollama": version, "settings": {**old.get("settings", {}), **settings}, "models": digests}
    path.write_text(json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8")
    return manifest


def run_model(client: Client, model: str, tracks: list, seeds: list, run_dir: Path, models_cfg: dict = None, task_dir: Path = None,
              temperature: float = 0.2, log=print, limit: int = None) -> dict:
    """Returns {track: number of new answers}. Stops cleanly on an unreachable server."""
    cfg = (models_cfg or {}).get(model, {})
    new = {}
    for track in tracks:
        tasks = load_track(track, task_dir)["tasks"]
        if limit:
            tasks = tasks[:limit]
        path = result_path(run_dir, model, track)
        path.parent.mkdir(parents=True, exist_ok=True)
        done = {(r["task"], r["seed"]) for r in read_records(path)}
        count = 0
        for seed in seeds:
            for task in tasks:
                if (task["id"], seed) in done:
                    continue
                prompt = task_prompt(task)
                try:
                    res = client.chat(model, prompt, system=task.get("system", ""), num_predict=int(task.get("num_predict", 300)),
                                      temperature=temperature, seed=seed, num_ctx=int(task.get("num_ctx", 8192)),
                                      min_predict=int(cfg.get("predict_min", 0)))
                except OllamaError as e:
                    log(f"  ! {model} {task['id']} seed {seed}: {e}")
                    time.sleep(3)
                    res = client.chat(model, prompt, system=task.get("system", ""), num_predict=int(task.get("num_predict", 300)),
                                      temperature=temperature, seed=seed, num_ctx=int(task.get("num_ctx", 8192)),
                                      min_predict=int(cfg.get("predict_min", 0)))
                score, checks = score_task(task, res["text"])
                rec = {"model": model, "track": track, "task": task["id"], "seed": seed, "score": score, "checks": checks, "secs": res["secs"],
                       "eval_count": res["eval_count"], "truncated": res["truncated"], "cut_in_thinking": res["cut_in_thinking"],
                       "answer": res["text"][:MAX_ANSWER_CHARS]}
                with open(path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                count += 1
            log(f"  {model} {track} seed {seed}: done")
        new[track] = count
    client.unload(model)
    return new
