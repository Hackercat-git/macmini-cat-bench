"""Command line: python -m catbench <command>"""
import argparse
import sys
import time
from pathlib import Path

from . import perf, report, runner, system
from .models import load_models
from .ollama import Client, OllamaError
from .scoring import score_task
from .tasks import TRACKS, all_tracks, task_prompt

ROOT = Path(__file__).resolve().parent.parent


def default_run_id(info: dict) -> str:
    chip = (info.get("chip") or "machine").lower().replace("apple ", "").replace(" ", "")
    return f"{time.strftime('%Y-%m-%d')}-macmini-{chip}-{info.get('ram_gb') or 'x'}gb"


def cmd_run(a) -> int:
    client = Client(a.host)
    cfg = load_models()
    info = system.machine_info()
    run_id = a.run_id or default_run_id(info)
    run_dir = Path(a.out) / run_id
    tracks = a.tracks or TRACKS
    runner.write_manifest(run_dir, run_id, client, a.models, {"seeds": a.seeds, "temperature": a.temperature, "tracks": tracks})
    for model in a.models:
        print(f"== {model}", flush=True)
        try:
            runner.run_model(client, model, tracks, list(range(1, a.seeds + 1)), run_dir, cfg, temperature=a.temperature, limit=a.limit)
        except OllamaError as e:
            print(f"   stopped: {e}", flush=True)
            return 1
        runner.write_manifest(run_dir, run_id, client, a.models, {})
    print(f"results in {run_dir}")
    return 0


def cmd_perf(a) -> int:
    client = Client(a.host)
    run_dir = Path(a.out) / (a.run_id or default_run_id(system.machine_info()))
    result = {"models": {}}
    for model in a.models:
        r = perf.measure(client, model)
        result["models"][model] = r
        print(f"{model}: load {r['cold_load_s']} s | read {r['reading_tok_s']} tok/s | generate {r['generation_tok_s']} tok/s | memory {r.get('memory_gb')} GB", flush=True)
    perf.save(run_dir / "perf.json", result)
    return 0


def cmd_parallel(a) -> int:
    client = Client(a.host)
    run_dir = Path(a.out) / (a.run_id or default_run_id(system.machine_info()))
    r = perf.parallel(client, a.model, a.agents, note=a.note)
    print(r)
    path = run_dir / "parallel.json"
    old = []
    try:
        import json
        old = json.loads(path.read_text(encoding="utf-8"))
        old = old if isinstance(old, list) else [old]
    except (OSError, ValueError):
        pass
    perf.save(path, old + [r])
    return 0


def cmd_report(a) -> int:
    out = report.build(Path(a.out) / a.run_id, Path(a.site))
    print(f"site written to {a.site}: {out['models']} models, tracks {', '.join(out['tracks'])}, noise {out['noise']:.2f}")
    return 0


def cmd_validate(a) -> int:
    problems = []
    for track, data in all_tracks().items():
        ids = set()
        for t in data["tasks"]:
            if t["id"] in ids:
                problems.append(f"{track}: duplicate id {t['id']}")
            ids.add(t["id"])
            if not task_prompt(t).strip():
                problems.append(f"{t['id']}: empty prompt")
            ok, _ = score_task(t, t["pass"])
            bad, _ = score_task(t, t["fail"])
            if ok < 0.99:
                problems.append(f"{t['id']}: the passing example scores {ok}")
            if bad >= 0.99:
                problems.append(f"{t['id']}: the failing example scores {bad}")
    n = sum(len(d["tasks"]) for d in all_tracks().values())
    print(f"{n} tasks checked; {len(problems)} problem(s)")
    for p in problems:
        print("  -", p)
    return 1 if problems else 0


def cmd_list(a) -> int:
    for track, data in all_tracks().items():
        print(f"{track:14s} {len(data['tasks']):3d} tasks  {data['description']}")
    print()
    for tag, m in load_models().items():
        print(f"{tag:34s} {m['status']:9s} {m['tier']:8s} {m['name']}")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="catbench", description="Honest AI benchmarks on the Mac mini")
    sub = p.add_subparsers(dest="cmd", required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--host", default=None, help="Ollama host (default: OLLAMA_HOST or localhost:11434)")
    common.add_argument("--out", default=str(ROOT / "runs"))
    common.add_argument("--run-id", default=None)
    r = sub.add_parser("run", parents=[common], help="run models over tracks")
    r.add_argument("--models", nargs="+", required=True)
    r.add_argument("--tracks", nargs="+", choices=TRACKS)
    r.add_argument("--seeds", type=int, default=3)
    r.add_argument("--temperature", type=float, default=0.2)
    r.add_argument("--limit", type=int, default=None, help="only the first N tasks per track (for a quick check)")
    r.set_defaults(fn=cmd_run)
    pf = sub.add_parser("perf", parents=[common], help="speed and memory")
    pf.add_argument("--models", nargs="+", required=True)
    pf.set_defaults(fn=cmd_perf)
    pl = sub.add_parser("parallel", parents=[common], help="several agents at once")
    pl.add_argument("--model", required=True)
    pl.add_argument("--agents", type=int, default=5)
    pl.add_argument("--note", default="", help="describe the server setting, e.g. OLLAMA_NUM_PARALLEL=5")
    pl.set_defaults(fn=cmd_parallel)
    rp = sub.add_parser("report", help="build the site from a run")
    rp.add_argument("--run-id", required=True)
    rp.add_argument("--out", default=str(ROOT / "runs"))
    rp.add_argument("--site", default=str(ROOT / "docs"))
    rp.set_defaults(fn=cmd_report)
    sub.add_parser("validate", help="check the task files").set_defaults(fn=cmd_validate)
    sub.add_parser("list", help="list tracks and models").set_defaults(fn=cmd_list)
    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
