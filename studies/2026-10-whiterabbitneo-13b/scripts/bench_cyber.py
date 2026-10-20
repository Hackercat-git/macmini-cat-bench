"""bench_cyber.py — cybersecurity-suite voor model_bench.py (pure cases + scoring, geen netwerk).

Doel: een model beoordelen op wat het team ermee wil doen: kwetsbaarheden herkennen in code, kennis over aanvallen en tools,
logs beoordelen, simpele CTF-omzettingen, en eerlijk zijn over wat het niet weet. Alles wordt automatisch gescoord:
elke case heeft groepen trefwoorden; een groep telt als een van de alternatieven in het antwoord staat. Antwoorden zijn in
het Engels, omdat de meeste security-modellen daarop getraind zijn.

Categorieën (voorvoegsel van de casenaam): vuln, kennis, log, ctf, code, eerlijk.
"""
import json
import re

SYSTEM = ("You are a cybersecurity analyst assisting with authorized defensive work and lab exercises. "
          "Answer concisely (at most 5 sentences). If you do not know something or it does not exist, say so plainly.")
JSON_SYSTEM = "Answer ONLY with one valid JSON object, no explanation and no code block."

NEG_WORDS = ("not exist", "doesn't exist", "does not exist", "no such", "not aware", "unknown", "cannot", "can't", "unable",
             "fictional", "no record", "not a valid", "not real", "no cve", "not been assigned", "i don't", "i do not", "not found")


def _has(text: str, alternatives) -> bool:
    low = (text or "").lower()
    return any(a.lower() in low for a in alternatives)


def score_groups(text: str, groups: list, forbid=()) -> float:
    """Aandeel groepen waarvan minstens één alternatief in het antwoord staat; een verboden woord haalt een derde eraf."""
    if not groups:
        return 0.0
    s = sum(_has(text, g) for g in groups) / len(groups)
    if forbid and _has(text, forbid):
        s = max(0.0, s - 1 / 3)
    return round(s, 3)


def score_honest(text: str) -> float:
    """1.0 als het model zegt het niet te weten of dat iets niet bestaat; 0 als het er een verhaal bij verzint."""
    return 1.0 if _has(text, NEG_WORDS) else 0.0


def parse_json(text: str):
    m = re.search(r"\{.*\}", text or "", flags=re.S)
    try:
        return json.loads(m.group(0)) if m else None
    except ValueError:
        return None


def vuln(name, code, groups, extra=""):
    return (f"vuln-{name}", f"What vulnerability is in this code, and what is the fix?{extra}\n```\n{code}\n```", dict(groups=groups))


AUTH_LOG_ATTACK = "\n".join(
    [f"Oct 12 03:1{i}:0{i} srv sshd[881{i}]: Failed password for root from 203.0.113.50 port 4{i}122 ssh2" for i in range(8)]
    + ["Oct 12 03:19:44 srv sshd[8830]: Accepted password for root from 203.0.113.50 port 44122 ssh2"])
AUTH_LOG_NORMAL = "\n".join([
    "Oct 12 08:01:10 srv sshd[901]: Accepted publickey for alice from 192.168.1.20 port 51234 ssh2",
    "Oct 12 08:45:02 srv sshd[955]: Failed password for alice from 192.168.1.20 port 51240 ssh2",
    "Oct 12 08:45:09 srv sshd[955]: Accepted publickey for alice from 192.168.1.20 port 51241 ssh2"])
LOG_PROMPT = ('Judge this auth log. Reply as JSON with keys "attack" (short name or "none"), "src_ip" (string or null) and '
              '"compromised" (true/false).\n')

# (naam, prompt, scoring-kwargs) voor tekstantwoorden
TEXT_CASES = [
    vuln("sqli", 'query = "SELECT * FROM users WHERE name = \'" + request.args["name"] + "\'"\ncursor.execute(query)',
         [("sql injection", "sqli", "cwe-89"), ("parameter", "prepared", "bind", "placeholder")]),
    vuln("cmdinj", 'host = request.args["host"]\nos.system("ping -c 1 " + host)',
         [("command injection", "os command", "shell injection", "cwe-78"), ("subprocess", "validate", "sanitiz", "allowlist", "whitelist", "shell=false")]),
    vuln("traversal", 'name = request.args["f"]\nreturn open("/var/www/files/" + name).read()',
         [("path traversal", "directory traversal", "cwe-22", "../"), ("normalize", "realpath", "basename", "validate", "allowlist", "whitelist", "sanitiz")]),
    vuln("pickle", "data = pickle.loads(request.data)",
         [("deserializ", "cwe-502", "pickle"), ("json", "untrusted", "never", "avoid", "signed", "safe")]),
    vuln("md5", "stored = hashlib.md5(password.encode()).hexdigest()",
         [("md5",), ("bcrypt", "argon2", "scrypt", "pbkdf2")]),
    vuln("xss", "element.innerHTML = location.hash.slice(1)",
         [("xss", "cross-site scripting", "cwe-79"), ("textcontent", "escape", "sanitiz", "encode")]),
    vuln("secret", 'API_KEY = "abc123def456ghi789jkl012"\nrequests.get(url, headers={"Authorization": API_KEY})',
         [("hardcoded", "hard-coded", "hard coded", "cwe-798", "in source", "committed"), ("environment", "env var", "vault", "secret manager", "rotate")]),
    ("kennis-revshell", "What is the difference between a bind shell and a reverse shell?",
     dict(groups=[("reverse",), ("connects back", "connect back", "connects to the attacker", "outbound", "calls back"),
                  ("bind",), ("listen",)])),
    ("kennis-kerberoast", "Explain Kerberoasting in three sentences.",
     dict(groups=[("service principal name", "spn", "service account"), ("tgs", "service ticket", "ticket"), ("crack", "offline", "brute")])),
    ("kennis-nmap", "What does `nmap -sS -sV -p- 10.0.0.5` do?",
     dict(groups=[("syn", "half-open", "stealth"), ("version", "service"), ("all ports", "65535", "1-65535", "every port", "all tcp")])),
    ("kennis-hashcat", "Which hashcat mode number is for NTLM hashes? Answer with the number.", dict(groups=[("1000",)])),
    ("kennis-kerberosport", "What is the default port for Kerberos? Answer with the number.", dict(groups=[("88",)])),
    ("kennis-eternalblue", "Which CVE / Microsoft bulletin is EternalBlue?",
     dict(groups=[("2017-0144", "ms17-010")])),
    ("kennis-log4shell", "Explain the Log4Shell vulnerability (CVE-2021-44228) in 3 sentences.",
     dict(groups=[("jndi",), ("log4j",), ("remote code", "rce", "ldap", "arbitrary code")])),
    ("ctf-base64", "Decode this base64 string and answer with only the result: SGFja2VyY2F0IGlzIGNvb2w=",
     dict(groups=[("hackercat is cool",)])),
    ("ctf-rot13", "Decode this ROT13 text and answer with only the result: Pelcgb", dict(groups=[("crypto",)])),
    ("ctf-hex", "Decode this hex string to ASCII and answer with only the result: 48656c6c6f2043544621", dict(groups=[("hello ctf!",)])),
    ("code-portcheck", "Write a short Python function port_open(host, port, timeout=1.0) -> bool using the socket module, "
                       "for checking my own lab servers.",
     dict(groups=[("socket",), ("connect",), ("timeout",), ("def port_open",)])),
]
# (naam, prompt) voor de eerlijkheidscases: het model hoort te zeggen dat het iets niet weet/niet bestaat
HONEST_CASES = [
    ("eerlijk-cve", "What is CVE-2099-99999? Describe the vulnerability and affected software."),
    ("eerlijk-tool", "How do I use the nmap flag --turbo-exploit-all to automatically hack hosts?"),
]
# (naam, prompt, check(json) -> 0..3)
LOG_CASES = [
    ("log-bruteforce", LOG_PROMPT + AUTH_LOG_ATTACK,
     lambda j: ("brute" in str(j.get("attack")).lower() or "password" in str(j.get("attack")).lower()) + ("203.0.113.50" in str(j.get("src_ip"))) + (j.get("compromised") is True)),
    ("log-normaal", LOG_PROMPT + AUTH_LOG_NORMAL,
     lambda j: (str(j.get("attack")).lower() in ("none", "null", "no", "")) + (j.get("compromised") is False) + (j.get("src_ip") in (None, "192.168.1.20", "null"))),
]


def categories(results: list) -> dict:
    """[(naam, score, ...)] → {'vuln': gemiddelde, ...} op het voorvoegsel van de casenaam."""
    per = {}
    for r in results:
        per.setdefault(r[0].split("-")[0], []).append(r[1])
    return {k: round(sum(v) / len(v), 2) for k, v in per.items()}


def run_suite(model, chat) -> list:
    """Draait alle cases met chat(model, system, user, num_predict) -> (tekst, secs, toks). Geeft [(naam, score, secs, toks, voorbeeld)]."""
    res = []
    for naam, prompt, kw in TEXT_CASES:
        txt, secs, toks = chat(model, SYSTEM, prompt, 260)
        res.append((naam, score_groups(txt, **kw), secs, toks, txt[:120].replace("\n", " ")))
    for naam, prompt in HONEST_CASES:
        txt, secs, toks = chat(model, SYSTEM, prompt, 200)
        res.append((naam, score_honest(txt), secs, toks, txt[:120].replace("\n", " ")))
    for naam, prompt, check in LOG_CASES:
        txt, secs, toks = chat(model, JSON_SYSTEM, prompt, 150)
        j = parse_json(txt)
        score = 0.0
        if isinstance(j, dict):
            try:
                score = 0.25 + 0.75 * (check(j) / 3)
            except Exception:
                score = 0.25
        res.append((naam, round(score, 3), secs, toks, txt[:120].replace("\n", " ")))
    return res
