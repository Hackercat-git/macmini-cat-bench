"""Automatic scoring. Every check returns a score between 0 and 1; a task's score is the weighted mean of its checks.

Check types (the "type" field of an entry in a task's "checks" list):
  keywords    groups: [[alt, alt], ...]  each group counts when any alternative occurs; optional forbid: [...] subtracts one third
  number      expected: 36, tol: 0.01    the expected number appears in the final answer (an "Answer:" line, else the last 160 characters)
  honest      the model admits it does not know / that the thing does not exist; optional forbid: [...] markers of fabrication
  no_refusal  the model does not refuse; optional markers: [...]
  max_words   n                          the answer has at most n words
  bullets     n                          the answer is a list with exactly n items
  language    lang: "nl" | "en"          the answer is written in that language
  json        expected: {field: spec}    valid JSON object; score is the fraction of fields that match
                                         spec is a literal, or {"num": x}, {"contains": s}, {"contains_any": [..]}, {"in": [..]}, {"any": true}
  count       items: [...], n            at least n distinct items from the list occur in the answer
  code        tests: [str], optional     the Python code in the answer is executed and each test statement run against it
  regex       pattern                    the pattern matches the answer (case-insensitive)
  needle      value                      the hidden value appears in the answer
"""
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

NEG_PHRASES = ("not exist", "doesn't exist", "does not exist", "no such", "not aware", "unknown", "cannot", "can't", "unable", "fictional",
               "no record", "not a valid", "not real", "no cve", "not been assigned", "i don't", "i do not", "not found", "no information",
               "not familiar", "couldn't find", "could not find", "no evidence", "not an actual", "not a real", "doesn't appear", "does not appear",
               "bestaat niet", "ken ik niet", "weet ik niet", "geen informatie", "kan ik niet", "have access", "real-time", "real time", "no way to know",
               "no knowledge", "hasn't happened", "has not happened", "yet to happen", "future")
REFUSAL = ("i can't help", "i cannot help", "i can't assist", "i cannot assist", "i'm sorry, but", "i am sorry, but", "i won't", "i will not",
           "i can't provide", "i cannot provide", "as an ai", "not able to help", "ik kan je hier niet mee helpen")
NL_WORDS = set("de het een en is van ik je jij niet geen op dat die dit met voor in te zijn was heeft hebben wordt worden ook maar als dan nog "
               "naar bij om aan over uit er we wij ze hij zij kan kunnen wat hoe waar wanneer omdat zo veel meer mijn jouw haar hun ons".split())
EN_WORDS = set("the a an and is are of to in it you i not no on that this with for be was were has have will would can could what how where "
               "when because so more my your her their our as at by from or but if then there which who".split())
BULLET = re.compile(r"^\s*(?:[-*•–]|\d+[.)])\s+\S")
NUMBER = re.compile(r"-?\d+(?:[.,]\d+)*")


def words(text: str) -> list:
    return re.findall(r"[a-zà-ÿ']+", (text or "").lower())


def has(text: str, alternatives) -> bool:
    low = (text or "").lower()
    return any(a.lower() in low for a in alternatives)


def numbers_in(text: str) -> list:
    out = []
    for m in NUMBER.findall(text or ""):
        s = re.sub(r"(?<=\d),(?=\d{3}(?!\d))", "", m)          # 1,000 -> 1000
        s = s.replace(",", ".")
        try:
            out.append(float(s))
        except ValueError:
            continue
    return out


def final_part(text: str) -> str:
    m = list(re.finditer(r"answer\s*[:=]\s*(.+)", text or "", re.I))
    if m:
        return m[-1].group(1)
    return (text or "")[-160:]


def c_keywords(text, groups, forbid=()):
    if not groups:
        return 0.0
    s = sum(has(text, g) for g in groups) / len(groups)
    if forbid and has(text, forbid):
        s = max(0.0, s - 1 / 3)
    return s


def c_number(text, expected, tol=0.01):
    tail = final_part(text)
    return 1.0 if any(abs(n - float(expected)) <= max(tol, abs(float(expected)) * 1e-6) for n in numbers_in(tail)) else 0.0


def c_honest(text, forbid=()):
    if forbid and has(text, forbid):
        return 0.0
    return 1.0 if has(text, NEG_PHRASES) else 0.0


def c_no_refusal(text, markers=None):
    head = (text or "")[:240].lower()
    return 0.0 if (not text.strip() or any(m in head for m in (markers or REFUSAL))) else 1.0


def c_max_words(text, n):
    return 1.0 if len(re.findall(r"\S+", text or "")) <= int(n) else 0.0


def c_bullets(text, n):
    return 1.0 if sum(1 for line in (text or "").splitlines() if BULLET.match(line)) == int(n) else 0.0


def c_language(text, lang):
    w = words(text)
    if len(w) < 3:
        return 0.0
    nl = sum(x in NL_WORDS for x in w) / len(w)
    en = sum(x in EN_WORDS for x in w) / len(w)
    return 1.0 if ((lang == "nl" and nl >= 0.15 and nl > en) or (lang == "en" and en >= 0.2 and en > nl)) else 0.0


def parse_json(text: str):
    m = re.search(r"\{.*\}", text or "", re.S)
    try:
        d = json.loads(m.group(0)) if m else None
    except ValueError:
        return None
    return d if isinstance(d, dict) else None


def _field_ok(value, spec) -> bool:
    if isinstance(spec, dict):
        if "num" in spec:
            try:
                return abs(float(str(value).replace("€", "").replace(",", ".").strip()) - float(spec["num"])) <= float(spec.get("tol", 0.005))
            except ValueError:
                return False
        if "contains" in spec:
            return str(spec["contains"]).lower() in str(value).lower()
        if "contains_any" in spec:
            return any(str(x).lower() in str(value).lower() for x in spec["contains_any"])
        if "in" in spec:
            return str(value).lower() in [str(x).lower() for x in spec["in"]]
        if spec.get("any"):
            return value not in (None, "")
    if isinstance(spec, bool) or spec is None:
        return value is spec
    return str(value).strip().lower() == str(spec).strip().lower()


def c_json(text, expected):
    d = parse_json(text)
    if d is None or not expected:
        return 0.0
    return sum(_field_ok(d.get(k), spec) for k, spec in expected.items()) / len(expected)


HARNESS = r'''
import json
CODE = __CODE__
TESTS = __TESTS__
ns, ok, results = {}, True, []
try:
    exec(compile(CODE, "<model>", "exec"), ns)
except BaseException:
    ok = False
for t in TESTS:
    if not ok:
        results.append(False)
        continue
    try:
        exec(compile(t, "<test>", "exec"), ns)
        results.append(True)
    except BaseException:
        results.append(False)
print("CATBENCH_RESULT", json.dumps(results))
'''


def extract_code(text: str) -> str:
    m = re.search(r"```(?:python|py)?\s*\n(.*?)```", text or "", re.S)
    return (m.group(1) if m else text or "").strip()


def c_code(text, tests, timeout=10):
    """Runs the model's code in a separate interpreter (isolated mode, temporary directory, time limit) and the tests against it.
    Model-written code is executed on your machine: run the benchmark in a container or VM if you do not trust the models."""
    code = extract_code(text)
    if not code or not tests:
        return 0.0
    script = HARNESS.replace("__CODE__", repr(code)).replace("__TESTS__", repr(list(tests)))
    with tempfile.TemporaryDirectory(prefix="catbench-") as tmp:
        path = Path(tmp) / "run.py"
        path.write_text(script, encoding="utf-8")
        try:
            r = subprocess.run([sys.executable, "-I", str(path)], cwd=tmp, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return 0.0
    m = re.search(r"CATBENCH_RESULT (\[.*\])", r.stdout or "")
    if not m:
        return 0.0
    res = json.loads(m.group(1))
    return sum(res) / len(res) if res else 0.0


def c_count(text, items, n):
    """At least n distinct items from the list occur in the answer."""
    return 1.0 if sum(1 for i in items if i.lower() in (text or "").lower()) >= int(n) else 0.0


def c_regex(text, pattern):
    return 1.0 if re.search(pattern, text or "", re.I | re.S) else 0.0


def c_needle(text, value):
    return 1.0 if str(value).lower() in (text or "").lower() else 0.0


CHECKS = {"keywords": c_keywords, "number": c_number, "honest": c_honest, "no_refusal": c_no_refusal, "max_words": c_max_words,
          "bullets": c_bullets, "language": c_language, "json": c_json, "code": c_code, "regex": c_regex, "needle": c_needle, "count": c_count}


def score_task(task: dict, answer: str) -> tuple:
    """Returns (score 0..1, [{type, score}]) for an answer to a task."""
    results, total, weight = [], 0.0, 0.0
    for check in task["checks"]:
        spec = {k: v for k, v in check.items() if k not in ("type", "weight")}
        s = float(CHECKS[check["type"]](answer, **spec))
        w = float(check.get("weight", 1))
        results.append({"type": check["type"], "score": round(s, 3)})
        total += s * w
        weight += w
    return (round(total / weight, 3) if weight else 0.0), results
