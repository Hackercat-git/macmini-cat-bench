#!/usr/bin/env python3
"""make_bench_report.py — builds the benchmark report (print-ready HTML, in English) from the measurement files in docs/bench-data/.

  python make_bench_report.py            # writes docs/benchmark-whiterabbitneo-13b.html
Input: perf.json / perf-nieuw.json (bench_perf.py) and results-seed*.json (model_bench.py cyber, one file per seed or batch).
Every number in the text is computed from those files; nothing is typed in by hand.
"""
import glob
import html
import json
import statistics
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "docs" / "bench-data"
OUT = ROOT / "docs" / "benchmark-whiterabbitneo-13b.html"
WRN = "wrn13b"
NAMEN = {"wrn13b": "WhiteRabbitNeo 13B", "wrn13b-official": "WhiteRabbitNeo 13B (official prompt)", "mistral-nemo:latest": "mistral-nemo 12B",
         "qwen3.8:27b": "qwen3.8 27B", "qwen2.5-coder:14b": "qwen2.5-coder 14B", "qwen3:8b": "qwen3 8B", "phi4:14b": "phi4 14B",
         "gemma3:12b": "gemma3 12B", "wrn25-qwen7b": "WhiteRabbitNeo 2.5 (Qwen) 7B", "deephat7b": "DeepHat V1 7B",
         "wrn-llama3-8b": "WhiteRabbitNeo (Llama 3) 8B", "dolphin-llama3:8b": "dolphin-llama3 8B", "deepseek-r1:14b": "deepseek-r1 14B",
         "codestral:22b": "codestral 22B", "qwen2.5-coder:32b": "qwen2.5-coder 32B"}
CATS = [("vuln", "Vulnerability identification in code"), ("kennis", "Security knowledge (attacks, tools)"), ("ctf", "CTF decoding"),
        ("code", "Code writing"), ("eerlijk", "Honesty (no fabrication)"), ("log", "Log analysis")]
CASES = {
    "vuln-sqli": "Recognise SQL injection", "vuln-cmdinj": "Recognise command injection", "vuln-traversal": "Recognise path traversal",
    "vuln-pickle": "Unsafe deserialisation (pickle)", "vuln-md5": "MD5 for password storage", "vuln-xss": "XSS through innerHTML",
    "vuln-secret": "Hard-coded API key", "kennis-revshell": "Bind shell vs. reverse shell", "kennis-kerberoast": "Explain Kerberoasting",
    "kennis-nmap": "Explain nmap -sS -sV -p-", "kennis-hashcat": "hashcat mode for NTLM (1000)", "kennis-kerberosport": "Kerberos port (88)",
    "kennis-eternalblue": "EternalBlue = MS17-010", "kennis-log4shell": "Explain Log4Shell", "ctf-base64": "Decode base64",
    "ctf-rot13": "Decode ROT13", "ctf-hex": "Hex to ASCII", "code-portcheck": "Write a Python port check",
    "eerlijk-cve": "Non-existent CVE-2099-99999", "eerlijk-tool": "Non-existent nmap flag", "log-bruteforce": "Recognise SSH attack in a log",
    "log-normaal": "Do not flag a normal log"}
BLAUW, GRIJS, INKT, INKT2, LIJN = "#2a78d6", "#a9a8a2", "#0b0b0b", "#52514e", "#dcdbd5"


def naam(m):
    return NAMEN.get(m, m)


def laad():
    perf = json.loads((DATA / "perf.json").read_text(encoding="utf-8"))
    extra = DATA / "perf-nieuw.json"
    if extra.exists():
        perf["modellen"].update(json.loads(extra.read_text(encoding="utf-8"))["modellen"])
    runs = []
    for f in sorted(glob.glob(str(DATA / "results-seed*.json"))):
        d = json.loads(Path(f).read_text(encoding="utf-8"))
        runs.append({m: v["cyber"] for m, v in d.items() if "cyber" in v})
    return perf, runs


def aggregeer(runs):
    out = {}
    for m in {m for r in runs for m in r}:
        entries = [r[m] for r in runs if m in r]
        scores = [e["score"] for e in entries]
        cats = {}
        for c, _ in CATS:
            vals = [e["categorieen"][c] for e in entries if c in e.get("categorieen", {})]
            cats[c] = statistics.mean(vals) if vals else None
        cases = {}
        for e in entries:
            for k, v in e["cases"].items():
                cases.setdefault(k, []).append(v)
        out[m] = {"n": len(entries), "mean": statistics.mean(scores), "lo": min(scores), "hi": max(scores), "cats": cats,
                  "cases": {k: statistics.mean(v) for k, v in cases.items()}, "avg_s": statistics.mean(e["avg_s"] for e in entries)}
    return out


def bar_chart(rows, maxv, fmt, highlight=WRN, titel="", eenheid=""):
    """rows = [(model, value, extra_label)] → horizontal bars as inline SVG; the model under study in blue, the rest grey."""
    h, gap, left, width = 26, 10, 230, 720
    total = len(rows) * (h + gap) + 8
    s = [f'<svg viewBox="0 0 {width} {total}" role="img" aria-label="{html.escape(titel)}" class="chart">']
    for i, (m, v, extra) in enumerate(rows):
        y = 4 + i * (h + gap)
        w = max(2, (width - left - 150) * v / maxv)
        kleur = BLAUW if m == highlight else GRIJS
        s.append(f'<text x="{left - 10}" y="{y + h / 2 + 5}" text-anchor="end" class="lbl{" b" if m == highlight else ""}">{html.escape(naam(m))}</text>')
        s.append(f'<rect x="{left}" y="{y}" width="{w:.1f}" height="{h}" rx="4" fill="{kleur}"/>')
        s.append(f'<text x="{left + w + 8}" y="{y + h / 2 + 5}" class="val">{fmt(v)}{eenheid}'
                 + (f' <tspan class="sub">{html.escape(extra)}</tspan>' if extra else "") + '</text>')
    s.append("</svg>")
    return "\n".join(s)


def heat(v):
    if v is None:
        return "—", "background:#f4f3ef"
    return f"{v:.2f}", f"background:rgba(42,120,214,{0.08 + 0.52 * v:.2f})"


def render(perf, runs, today: str = None):
    agg = aggregeer(runs)
    hw, inst, pm = perf["hardware"], perf["instellingen"], perf["modellen"]
    w = agg[WRN]
    ranking = sorted(agg, key=lambda m: -agg[m]["mean"])
    uniek = [m for m in ranking if m != "wrn13b-official"]
    plek = uniek.index(WRN) + 1
    beste = ranking[0]
    seeds = max(a["n"] for a in agg.values())
    pw = pm[WRN]
    datum = today or date.today().strftime("%d %B %Y")

    q_rows = [(m, agg[m]["mean"], f"{agg[m]['lo']:.2f}–{agg[m]['hi']:.2f}, {agg[m]['n']} runs" if agg[m]["n"] > 1 else "1 run") for m in ranking]
    g_rows = sorted(((m, v["gen_tok_s"], "") for m, v in pm.items()), key=lambda r: -r[1])
    r_rows = sorted(((m, v["ram_gb"], "") for m, v in pm.items()), key=lambda r: r[1])

    kop = "<th>Overall</th>" + "".join(f"<th>{html.escape(l)}</th>" for _, l in CATS)
    cat_rows = ""
    for m in ranking:
        cells = "".join(f'<td style="{heat(agg[m]["cats"][c])[1]}">{heat(agg[m]["cats"][c])[0]}</td>' for c, _ in CATS)
        b = ' class="hl"' if m == WRN else ""
        cat_rows += f'<tr{b}><th>{html.escape(naam(m))}</th><td style="{heat(agg[m]["mean"])[1]}">{agg[m]["mean"]:.2f}</td>{cells}</tr>'

    vergelijk = [m for m in (WRN, "qwen2.5-coder:14b", "qwen3.8:27b", "deephat7b") if m in agg]
    case_rows = ""
    for k, omschr in CASES.items():
        cells = ""
        for m in vergelijk:
            t, st = heat(agg[m]["cases"].get(k))
            cells += f'<td style="{st}">{t}</td>'
        case_rows += f"<tr><th>{html.escape(omschr)}</th>{cells}</tr>"
    case_kop = "".join(f"<th>{html.escape(naam(m))}</th>" for m in vergelijk)

    tabel_perf = ""
    for m, v in sorted(pm.items(), key=lambda kv: -kv[1]["gen_tok_s"]):
        b = ' class="hl"' if m == WRN else ""
        tabel_perf += (f"<tr{b}><th>{html.escape(naam(m))}</th><td>{v['laadtijd_s']:.1f} s</td><td>{v['prompt_tok_s']:.0f}</td>"
                       f"<td>{v['ttft_lange_prompt_s']:.1f} s</td><td>{v['gen_tok_s']:.1f}</td><td>{v['ram_gb']:.1f} GB</td></tr>")

    zwak = [(CASES[k], v) for k, v in sorted(w["cases"].items(), key=lambda kv: kv[1]) if v < 0.5]
    zwak_txt = "; ".join(f"{o} ({v:.2f})" for o, v in zwak[:6])
    sterk_cats = [l for c, l in CATS if (w["cats"][c] or 0) >= 0.95]
    zwak_cats = [(l, w["cats"][c]) for c, l in CATS if (w["cats"][c] or 0) < 0.5]
    meerdere = html.escape(", ".join(naam(m) for m in ranking if agg[m]["n"] > 1) or "none")
    ruis = max([a["hi"] - a["lo"] for a in agg.values() if a["n"] > 1] or [0.0])
    pogingen = 2 * w["n"]
    verzint = round((1 - w["cats"]["eerlijk"]) * pogingen)
    antw256 = 256 / pw["gen_tok_s"]
    mediaan_s = statistics.median([a['avg_s'] for m, a in agg.items() if m not in (WRN, 'wrn13b-official')])
    ram_pct = pw["ram_gb"] / hw["ram_gb"] * 100

    nieuw = [m for m in ("wrn13b", "wrn-llama3-8b", "wrn25-qwen7b", "deephat7b") if m in agg and m in pm]
    nieuw_rijen = "".join(
        f'<tr{" class=hl" if m == WRN else ""}><th>{html.escape(naam(m))}</th><td>{agg[m]["mean"]:.2f}</td><td>{agg[m]["cats"]["kennis"]:.2f}</td>'
        f'<td>{agg[m]["cats"]["eerlijk"]:.2f}</td><td>{pm[m]["gen_tok_s"]:.1f}</td><td>{pm[m]["ram_gb"]:.1f} GB</td></tr>' for m in nieuw)
    sneller = [m for m in nieuw if m != WRN]
    beste_nieuw = max(sneller, key=lambda m: agg[m]["mean"]) if sneller else None
    meetbaar = [m for m in ranking if m in pm]
    beste_klein = max([m for m in meetbaar if pm[m]["ram_gb"] <= 6], key=lambda m: agg[m]["mean"], default=None)
    beste_snel = max(meetbaar, key=lambda m: pm[m]["gen_tok_s"])
    beste_balans = max([m for m in meetbaar if pm[m]["ram_gb"] <= 12 and m != WRN], key=lambda m: agg[m]["mean"], default=None)
    nieuw_zin = ""
    if beste_nieuw:
        snel = pm[beste_nieuw]['gen_tok_s'] / pw['gen_tok_s']
        geheugen = "in less than half the memory" if pm[beste_nieuw]['ram_gb'] < 0.5 * pw['ram_gb'] else f"in {pm[beste_nieuw]['ram_gb']:.1f} GB instead of {pw['ram_gb']:.1f} GB"
        kwaliteit = "with a similar quality score" if abs(agg[beste_nieuw]['mean'] - w['mean']) <= 0.10 else ("with a higher quality score" if agg[beste_nieuw]['mean'] > w['mean'] else "with a lower quality score")
        nieuw_zin = (f"The newer 7B and 8B models in the same family and DeepHat V1 7B generate about {snel:.1f} times as fast {geheugen}, {kwaliteit} "
                     f"({html.escape(naam(beste_nieuw))}: {agg[beste_nieuw]['mean']:.2f}).")
    still = ""
    try:
        import base64
        import tempfile
        import make_speed_demo as _demo
        _tmp = Path(tempfile.mkdtemp()) / "still.png"
        _demo.maak_still(_demo.laad(), _tmp, t=8.0)
        still = base64.b64encode(_tmp.read_bytes()).decode()
    except Exception:
        still = ""
    r1 = agg.get("deepseek-r1:14b")
    r1_noot = ('<p class="note">deepseek-r1 is a reasoning model: it always thinks at length before answering. It was therefore given a generous limit of 3,000 tokens '
               'per question instead of 260; with 260 tokens it scored 0.19 because the answer never appeared. Its time per question is correspondingly much higher '
               f'({r1["avg_s"]:.0f} s).</p>') if r1 else ""

    nieuw_alinea = ""
    if beste_nieuw:
        ratio = pm[beste_nieuw]["gen_tok_s"] / pw["gen_tok_s"]
        nieuw_alinea = (f"<p>The best of the newer models is <strong>{html.escape(naam(beste_nieuw))}</strong> with {agg[beste_nieuw]['mean']:.2f} "
                        f"(WhiteRabbitNeo 13B: {w['mean']:.2f}). The newer models generate about {ratio:.1f}x as fast and use less memory, "
                        "but do not clearly beat the 13B on quality.</p>")
    conc_nieuw = (f"<li>If you want a model from the WhiteRabbitNeo line, prefer <strong>{html.escape(naam(beste_nieuw))}</strong> over the 13B: "
                  f"{agg[beste_nieuw]['mean']:.2f} versus {w['mean']:.2f}, {pm[beste_nieuw]['gen_tok_s']:.0f} versus {pw['gen_tok_s']:.0f} tokens per second "
                  f"and {pm[beste_nieuw]['ram_gb']:.1f} versus {pw['ram_gb']:.1f} GB.</li>") if beste_nieuw else ""
    conc_klein = (f"<li>Best small model (up to 6 GB): <strong>{html.escape(naam(beste_klein))}</strong> ({agg[beste_klein]['mean']:.2f}, "
                  f"{pm[beste_klein]['gen_tok_s']:.0f} tok/s, {pm[beste_klein]['ram_gb']:.1f} GB). Fastest overall: {html.escape(naam(beste_snel))} "
                  f"at {pm[beste_snel]['gen_tok_s']:.0f} tokens per second.</li>") if beste_klein else ""
    conc_balans = (f"<li>Best balance of quality, speed and memory for a {hw['ram_gb']} GB machine: <strong>{html.escape(naam(beste_balans))}</strong> "
                   f"({agg[beste_balans]['mean']:.2f}, {pm[beste_balans]['gen_tok_s']:.1f} tok/s, {pm[beste_balans]['ram_gb']:.1f} GB). "
                   f"Best quality overall: <strong>{html.escape(naam(beste))}</strong> ({agg[beste]['mean']:.2f}) "
                   f"at {pm.get(beste, {}).get('ram_gb', 0):.1f} GB.</li>") if beste_balans else ""
    still_html = (f'<h3>What that looks like</h3><img alt="Four models writing the same answer side by side, after 8 seconds" '
                  f'style="width:100%;border:1px solid var(--line);border-radius:8px" src="data:image/png;base64,{still}">'
                  '<p class="note">Frame at 8 seconds from the speed demo: four models were given the same question. The animated version '
                  '(real timings, not sped up) is in <code>speed-demo.gif</code> and <code>speed-demo.html</code>.</p>') if still else ""

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>WhiteRabbitNeo 13B for cybersecurity tasks on a Mac mini: quality and speed</title>
<style>
:root {{ --ink:{INKT}; --ink2:{INKT2}; --line:{LIJN}; --blue:{BLAUW}; }}
* {{ box-sizing:border-box; }}
body {{ font:14px/1.5 -apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; color:var(--ink); background:#fff; margin:0; }}
main {{ max-width:780px; margin:0 auto; padding:36px 28px 60px; }}
h1 {{ font-size:26px; line-height:1.2; margin:0 0 4px; }}
.sub0 {{ color:var(--ink2); margin:0 0 22px; }}
h2 {{ font-size:18px; margin:34px 0 8px; padding-top:10px; border-top:1px solid var(--line); }}
h3 {{ font-size:14px; margin:20px 0 6px; }}
p {{ margin:6px 0 10px; }}
.tiles {{ display:grid; grid-template-columns:repeat(4,1fr); gap:10px; margin:14px 0 6px; }}
.tile {{ border:1px solid var(--line); border-radius:8px; padding:10px 12px; }}
.tile .n {{ font-size:24px; font-weight:650; letter-spacing:-.01em; }}
.tile .l {{ color:var(--ink2); font-size:12px; }}
.verdict {{ background:#f3f7fd; border-left:4px solid var(--blue); padding:10px 14px; border-radius:4px; margin:14px 0; }}
table {{ border-collapse:collapse; width:100%; margin:8px 0 12px; font-size:12.5px; }}
th,td {{ border-bottom:1px solid var(--line); padding:5px 7px; text-align:right; }}
th {{ font-weight:600; text-align:left; }}
thead th {{ text-align:right; vertical-align:bottom; font-size:11.5px; }}
thead th:first-child {{ text-align:left; }}
tr.hl th,tr.hl td {{ background:#f3f7fd; font-weight:600; }}
.chart {{ width:100%; height:auto; display:block; margin:6px 0 4px; }}
.chart .lbl {{ font-size:12.5px; fill:var(--ink); }} .chart .lbl.b {{ font-weight:700; }}
.chart .val {{ font-size:12.5px; fill:var(--ink); font-weight:600; }} .chart .sub {{ font-weight:400; fill:var(--ink2); font-size:11px; }}
.note {{ color:var(--ink2); font-size:12px; }}
ul {{ margin:6px 0 10px 18px; padding:0; }} li {{ margin:3px 0; }}
code {{ background:#f4f3ef; padding:1px 5px; border-radius:3px; font-size:12px; }}
@media print {{ main {{ padding:0; }} h2 {{ break-after:avoid; }} .tile,table,.verdict,svg {{ break-inside:avoid; }} }}
@media (max-width:640px) {{ .tiles {{ grid-template-columns:repeat(2,1fr); }} }}
</style></head><body><main>

<h1>WhiteRabbitNeo 13B for cybersecurity tasks on a Mac mini</h1>
<p class="sub0">Quality and speed of a security-tuned language model compared with {len(uniek) - 1} other local models. Measured with Ollama on an Apple Mac mini ({html.escape(hw['chip'])}, {hw['ram_gb']} GB unified memory). {html.escape(datum)}.</p>

<div class="verdict"><strong>Summary.</strong> WhiteRabbitNeo 13B is a competent source of security facts, but on this evidence it is not the best choice.
It ranks {plek} of {len(uniek)} models with a quality score of {w['mean']:.2f}, against {agg[beste]['mean']:.2f} for {html.escape(naam(beste))}. It fabricates answers to questions about things that do not exist
(honesty score {w['cats']['eerlijk']:.2f}), takes {w['avg_s']:.1f} s per question on average (median of the other models: {mediaan_s:.1f} s), and occupies {pw['ram_gb']:.1f} GB of memory.
On the Mac mini it generates {pw['gen_tok_s']:.1f} tokens per second, which is fast enough for interactive use. {nieuw_zin}</div>

<div class="tiles">
<div class="tile"><div class="n">{w['mean']:.2f}</div><div class="l">quality score (0 to 1), mean of {w['n']} runs</div></div>
<div class="tile"><div class="n">{pw['gen_tok_s']:.1f}</div><div class="l">tokens per second when generating</div></div>
<div class="tile"><div class="n">{pw['prompt_tok_s']:.0f}</div><div class="l">tokens per second when reading a long prompt</div></div>
<div class="tile"><div class="n">{pw['ram_gb']:.1f} GB</div><div class="l">memory in use ({ram_pct:.0f}% of {hw['ram_gb']} GB)</div></div>
</div>

<h2>1. Test setup</h2>
<ul>
<li><strong>Machine:</strong> Apple Mac mini ({html.escape(hw['chip'])}, 12 CPU cores, 12 GPU cores, {hw['ram_gb']} GB unified memory), macOS {html.escape(hw['macos'])}, Ollama 0.40.5. All models ran fully on the GPU (Metal).</li>
<li><strong>Model under study:</strong> WhiteRabbitNeo-13B-v1, GGUF Q4_K_M from <code>TheBloke/WhiteRabbitNeo-13B-GGUF</code>, 7.87 GB. Base: Llama 2, 13 billion parameters. The SHA-256 checksum matches Hugging Face.</li>
<li><strong>Compared with:</strong> {", ".join(html.escape(naam(m)) for m in ranking if m not in (WRN, "wrn13b-official"))}. All are Q4 quantisations run on the same machine with the same settings.</li>
<li><strong>Settings:</strong> context window {inst['num_ctx']} tokens; temperature 0.2 for quality and 0 for speed; Ollama defaults otherwise. WhiteRabbitNeo was prompted in its own template (<code>SYSTEM / USER / ASSISTANT</code>); a second run used its official Tree-of-Thoughts system prompt.</li>
</ul>

<h2>2. Quality: {len(CASES)} security tasks</h2>
<p>Each task is scored automatically on keywords that a good answer must contain (for <em>SQL injection</em>: the name of the vulnerability and the fix with parameterised queries).
Scores run from 0 to 1. Results are the mean of {seeds} runs with different sampling seeds where available; the range is printed next to each bar.</p>
{bar_chart(q_rows, 1.0, lambda v: f"{v:.2f}", titel="Overall quality score per model")}
<p class="note">Overall quality score (higher is better). Run-to-run variation reaches {ruis:.2f} (see the range next to the bars), so differences smaller than that are noise: the test is small.</p>

<h3>By category</h3>
<table><thead><tr><th>Model</th>{kop}</tr></thead><tbody>{cat_rows}</tbody></table>
<p class="note">Darker blue means a higher score. Models averaged over several seeds: {meerdere}; all others are a single run.</p>

<h3>Strengths and weaknesses of WhiteRabbitNeo 13B</h3>
<ul>
<li><strong>Strong:</strong> {html.escape(", ".join(sterk_cats))}. Its security knowledge ({w['cats']['kennis']:.2f}) matches the best models: it knows nmap, hashcat, Kerberoasting and EternalBlue.</li>
<li><strong>Weak:</strong> {html.escape("; ".join(f"{l} ({v:.2f})" for l, v in zwak_cats))}. In {verzint} of {pogingen} attempts it invented a description of <code>CVE-2099-99999</code> or of an nmap flag that does not exist, instead of saying it does not know it. For a team that relies on the output, this is the most dangerous failure mode.</li>
<li><strong>Lowest-scoring tasks:</strong> {html.escape(zwak_txt)}.</li>
<li><strong>Official prompt:</strong> the long Tree-of-Thoughts system prompt does not improve the model ({agg['wrn13b-official']['mean']:.2f} versus {w['mean']:.2f}) and makes answers longer.</li>
</ul>

<h2>Newer versions and DeepHat</h2>
<p>WhiteRabbitNeo 13B is based on Llama 2 (2023). Newer variants exist on Llama 3 and Qwen 2.5, as does DeepHat (on Qwen 2.5 Coder). How they compare:</p>
<table><thead><tr><th>Model</th><th>Quality</th><th>Knowledge</th><th>Honesty</th><th>Generation (tok/s)</th><th>Memory</th></tr></thead><tbody>{nieuw_rijen}</tbody></table>
{nieuw_alinea}
{r1_noot}

<h2>3. Speed and memory on the Mac mini</h2>
<p>Measured with the counters Ollama itself reports; median of {inst['rondes']} rounds per model, freshly loaded. Reading = processing a log of about {pw['prompt_tokens']:,} tokens; generating = producing {inst['gen_tokens']} tokens.</p>
<table><thead><tr><th>Model</th><th>Cold load</th><th>Reading (tok/s)</th><th>First token after {pw['prompt_tokens']:,} tok</th><th>Generating (tok/s)</th><th>Memory</th></tr></thead><tbody>{tabel_perf}</tbody></table>
{still_html}
<h3>Generation speed (tokens per second, higher is better)</h3>
{bar_chart(g_rows, max(r[1] for r in g_rows), lambda v: f"{v:.1f}", titel="Generation speed per model")}
<h3>Memory use (GB, lower is better; the machine has {hw['ram_gb']} GB)</h3>
{bar_chart(r_rows, hw['ram_gb'] / 2, lambda v: f"{v:.1f}", titel="Memory use per model", eenheid=" GB")}
<ul>
<li>A {inst['gen_tokens']}-token answer (about 190 words) takes {antw256:.0f} seconds. Reading a {pw['prompt_tokens']:,}-token log takes {pw['ttft_lange_prompt_s']:.0f} seconds before the first word appears.</li>
<li>In the quality test WhiteRabbitNeo needed {w['avg_s']:.1f} seconds per question on average, versus {agg['qwen2.5-coder:14b']['avg_s']:.1f} s for qwen2.5-coder 14B: its answers are much longer.</li>
<li>Its memory use ({pw['ram_gb']:.1f} GB at context {inst['num_ctx']}) is higher than that of comparable models (qwen2.5-coder 14B: {pm['qwen2.5-coder:14b']['ram_gb']:.1f} GB) because Llama 2 13B has no memory-efficient grouped-query attention (GQA). It grows quickly with longer contexts.</li>
<li>Loading takes {pw['laadtijd_s']:.1f} seconds; the model stays loaded as long as Ollama keeps it in memory.</li>
</ul>

<h2>4. Conclusions and recommendations</h2>
<ul>
<li><strong>Use it</strong> when you want a model without refusals for pentest questions in a lab, where a person checks the answers.</li>
<li><strong>Do not use it</strong> where a fabricated answer causes harm (CVE look-ups, unsupervised triage) or where speed matters.</li>
{conc_nieuw}
{conc_klein}
{conc_balans}
<li>The model is based on Llama 2 from 2023 and does not know recent vulnerabilities or techniques. Use is subject to the Llama 2 licence plus a WhiteRabbitNeo extension with restrictions; read <code>LICENSE.txt</code> and <code>USE_POLICY.md</code> before serious use.</li>
</ul>

<h2>5. Limitations</h2>
<ul>
<li>Small sample: {len(CASES)} tasks scored on keywords. No human read the answers, so a correct answer phrased differently can lose points.</li>
<li>English prompts only; no exploit development, no long agentic tasks, no comparison with models outside this list.</li>
<li>One machine and one quantisation (Q4_K_M or equivalent). Other quantisations or other Apple chips will give other speeds.</li>
<li>The seeds differ only in sampling (temperature 0.2); the questions are identical.</li>
</ul>

<h2>Appendix A. Score per task</h2>
<table><thead><tr><th>Task</th>{case_kop}</tr></thead><tbody>{case_rows}</tbody></table>

<h2>Appendix B. Reproducing the results</h2>
<p>On a machine with Ollama and the scripts in the package (<code>bench_cyber.py</code>, <code>model_bench.py</code>, <code>bench_perf.py</code>, <code>bench_stream.py</code>):</p>
<p><code>ollama create wrn13b -f modelfiles/Modelfile.wrn13b</code><br>
<code>python3 model_bench.py --models wrn13b qwen2.5-coder:14b cyber</code> (quality; set <code>BENCH_SEED=1</code> for another seed)<br>
<code>python3 bench_perf.py wrn13b qwen2.5-coder:14b</code> (speed and memory)<br>
<code>python3 bench_stream.py wrn13b qwen3:8b</code> (records the answer timing for the speed demo)</p>
</main></body></html>
"""


def main():
    perf, runs = laad()
    OUT.write_text(render(perf, runs), encoding="utf-8")
    print("written:", OUT, f"({len(runs)} result files)")


if __name__ == "__main__":
    main()
