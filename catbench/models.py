"""models.toml: the list of models, with the settings that differ per model."""
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_models(path: Path = None) -> dict:
    """{tag: {name, family, params_b, size_gb, source, tier, predict_min, status, notes}}"""
    data = tomllib.loads((path or ROOT / "models.toml").read_text(encoding="utf-8"))
    out = {}
    for m in data.get("model", []):
        out[m["tag"]] = {"name": m.get("name", m["tag"]), "family": m.get("family", ""), "params_b": m.get("params_b"), "size_gb": m.get("size_gb"),
                         "source": m.get("source", ""), "tier": m.get("tier", ""), "predict_min": int(m.get("predict_min", 0)),
                         "status": m.get("status", "planned"), "notes": m.get("notes", "")}
    return out


def display_name(tag: str, models: dict) -> str:
    return (models.get(tag) or {}).get("name", tag)
