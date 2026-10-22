"""Task files: tasks/<track>.json. Public by design; every task carries a passing and a failing example answer so the scoring is itself tested."""
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TASK_DIR = ROOT / "tasks"
TRACKS = ["cybersecurity", "daily", "coding", "dutch", "tools", "honesty", "reasoning", "longcontext", "hard", "standard", "pentest", "scenario"]
TRACK_LABELS = {"cybersecurity": "Cybersecurity", "daily": "Daily use", "coding": "Coding", "dutch": "Dutch", "tools": "Tools and JSON",
                "honesty": "Honesty and safety", "reasoning": "Reasoning and maths", "longcontext": "Long context", "hard": "Hard mixed", "standard": "Standard topics", "pentest": "Pentesting", "scenario": "Triage under noise"}
FILLER_SENTENCES = [
    "The committee reviewed the quarterly figures and noted a modest change in the regional totals.",
    "Several departments reported that routine maintenance had been completed on schedule.",
    "A short memo reminded staff that the archive room closes at five o'clock on weekdays.",
    "The supplier confirmed that the next delivery of office supplies would arrive early in the following week.",
    "Weather conditions along the coast were described as unremarkable for the time of year.",
    "The training session covered general safety procedures and was attended by most of the team.",
    "An internal survey found that employees generally appreciated the new lighting in the corridors.",
    "The library added a small number of reference books to its collection this month.",
    "Parking arrangements near the east entrance were adjusted to ease morning congestion.",
    "The newsletter included a recipe for vegetable soup submitted by the catering staff.",
]


def build_long_prompt(spec: dict) -> str:
    """Deterministic long text with one hidden fact at a relative position; the question comes last."""
    rng = random.Random(int(spec.get("filler_seed", 1)))
    target_chars = int(spec["approx_tokens"]) * 4
    pieces, size = [], 0
    while size < target_chars:
        s = rng.choice(FILLER_SENTENCES) + f" (note {rng.randint(100, 999)})"
        pieces.append(s)
        size += len(s) + 1
    pos = max(0, min(len(pieces) - 1, int(len(pieces) * float(spec["position"]))))
    pieces.insert(pos, spec["needle_sentence"])
    return "Read the following document carefully.\n\n" + " ".join(pieces) + "\n\n" + spec["question"]


def task_prompt(task: dict) -> str:
    return build_long_prompt(task["long"]) if "long" in task else task["prompt"]


def load_track(track: str, task_dir: Path = None) -> dict:
    path = (task_dir or TASK_DIR) / f"{track}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    defaults = data.get("defaults", {})
    for t in data["tasks"]:
        for k, v in defaults.items():
            t.setdefault(k, v)
        t["track"] = track
    return data


def all_tracks(task_dir: Path = None) -> dict:
    return {t: load_track(t, task_dir) for t in TRACKS if ((task_dir or TASK_DIR) / f"{t}.json").exists()}
