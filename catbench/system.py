"""Facts about the machine and the software, recorded with every run so results can be compared and checked."""
import platform
import subprocess
import time

from . import __version__


def _sh(cmd: list) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=20).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def machine_info() -> dict:
    info = {"os": platform.platform(), "python": platform.python_version(), "catbench": __version__}
    if platform.system() == "Darwin":
        info["chip"] = _sh(["sysctl", "-n", "machdep.cpu.brand_string"])
        mem = _sh(["sysctl", "-n", "hw.memsize"])
        info["ram_gb"] = round(int(mem) / 2**30) if mem.isdigit() else None
        info["macos"] = _sh(["sw_vers", "-productVersion"])
        for line in _sh(["system_profiler", "SPHardwareDataType"]).splitlines():
            line = line.strip()
            if line.startswith("Model Name:"):
                info["model"] = line.split(":", 1)[1].strip()
            elif line.startswith("Model Identifier:"):
                info["identifier"] = line.split(":", 1)[1].strip()
            elif line.startswith("Total Number of Cores:"):
                info["cores"] = line.split(":", 1)[1].strip()
    return info


def stamp() -> str:
    return time.strftime("%Y-%m-%d")


def describe(info: dict) -> str:
    bits = [info.get("model") or "Computer", f"({info.get('chip') or 'unknown chip'}, {info.get('ram_gb') or '?'} GB)"]
    return " ".join(bits)
