"""Energy per answer, measured with macOS powermetrics.

powermetrics needs root. This module only works when passwordless sudo is allowed for it (for example a sudoers line for the user running the
benchmark: `youruser ALL=(root) NOPASSWD: /usr/bin/powermetrics`). Without that, `available()` is False and energy is reported as "not measured";
nothing is ever estimated.
"""
import re
import subprocess
import threading
import time

POWER_LINE = re.compile(r"Combined Power \(CPU \+ GPU \+ ANE\):\s*([\d.]+)\s*mW")
CMD = ["sudo", "-n", "/usr/bin/powermetrics", "--samplers", "cpu_power", "-i", "1000"]


def parse_milliwatts(text: str) -> list:
    return [float(x) for x in POWER_LINE.findall(text or "")]


def available() -> bool:
    try:
        r = subprocess.run(CMD + ["-n", "1"], capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return False
    return r.returncode == 0 and bool(parse_milliwatts(r.stdout))


def joules(samples_mw: list, seconds_per_sample: float = 1.0) -> float:
    """Energy in joules from power samples in milliwatts taken every `seconds_per_sample`."""
    return sum(samples_mw) / 1000.0 * seconds_per_sample


class Meter:
    """Context manager: samples power for as long as the block runs. `result()` gives {'joules', 'avg_watts', 'seconds'}."""

    def __init__(self):
        self._proc = None
        self._t0 = 0.0
        self._out = ""

    def __enter__(self):
        self._t0 = time.time()
        self._proc = subprocess.Popen(CMD, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        self._reader = threading.Thread(target=self._read, daemon=True)
        self._reader.start()
        return self

    def _read(self):
        for line in self._proc.stdout:
            self._out += line

    def __exit__(self, *exc):
        self._proc.terminate()
        self._reader.join(timeout=3)
        self.seconds = time.time() - self._t0
        return False

    def result(self) -> dict:
        s = parse_milliwatts(self._out)
        if not s:
            return {"joules": None, "avg_watts": None, "seconds": round(self.seconds, 1)}
        return {"joules": round(joules(s), 1), "avg_watts": round(sum(s) / len(s) / 1000, 1), "seconds": round(self.seconds, 1)}
