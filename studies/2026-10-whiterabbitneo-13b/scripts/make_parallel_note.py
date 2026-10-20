#!/usr/bin/env python3
"""make_parallel_note.py — one-page explainer: how much memory does a model use with 1 agent versus 5 agents (HTML and PDF, in English).

  python make_parallel_note.py            # writes docs/ram-with-multiple-agents.html and .pdf
Input: docs/bench-data/parallel.json (measured on the Mac mini). Every number in the text is computed from that file.
"""
import html
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "docs" / "bench-data" / "parallel.json"
OUT_HTML = ROOT / "docs" / "ram-with-multiple-agents.html"
OUT_PDF = ROOT / "docs" / "ram-with-multiple-agents.pdf"
BROWSERS = ["C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe", "C:/Program Files/Microsoft/Edge/Application/msedge.exe",
            "C:/Program Files/Google/Chrome/Application/chrome.exe", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"]
BLUE, GREY, INK, INK2, LINE = "#2a78d6", "#a9a8a2", "#0b0b0b", "#52514e", "#dcdbd5"


def numbers(d: dict) -> dict:
    s, p = d["sequential"], d["parallel"]
    agents, tokens = d["settings"]["agents"], d["settings"]["tokens_per_request"]
    weights = d["weights_gb"]
    slot = (s["memory_gb_one_agent"] - weights)                       # context memory per request slot
    total_tokens = agents * tokens
    return {"agents": agents, "weights": weights, "slot": slot, "seq_mem": s["memory_gb_five_agents"], "par_mem": p["memory_gb_five_agents"],
            "seq_s": s["seconds_for_five"], "par_s": p["seconds_for_five"], "seq_tps": total_tokens / s["seconds_for_five"],
            "par_tps": total_tokens / p["seconds_for_five"], "par_per_agent": tokens / p["seconds_for_five"], "single": d["single_agent_generation_tok_s"],
            "speedup": s["seconds_for_five"] / p["seconds_for_five"], "mem_ratio": p["memory_gb_five_agents"] / s["memory_gb_five_agents"],
            "ram": float(d["hardware"].split("GB")[0].split()[-1]), "tokens": tokens, "ctx": d["settings"]["num_ctx"]}


def chart(n: dict) -> str:
    rows = [("1 agent", n["seq_mem"], BLUE), (f"{n['agents']} agents, one request at a time (default)", n["seq_mem"], BLUE),
            (f"{n['agents']} agents in parallel (NUM_PARALLEL={n['agents']})", n["par_mem"], GREY)]
    w, left, h, gap = 720, 290, 28, 12
    out = [f'<svg viewBox="0 0 {w} {len(rows) * (h + gap) + 30}" class="chart" role="img" aria-label="Memory use by setting">']
    scale = (w - left - 90) / n["ram"]
    for i, (label, gb, color) in enumerate(rows):
        y = 4 + i * (h + gap)
        out.append(f'<text x="{left - 10}" y="{y + 19}" text-anchor="end" class="lbl">{html.escape(label)}</text>')
        out.append(f'<rect x="{left}" y="{y}" width="{gb * scale:.1f}" height="{h}" rx="4" fill="{color}"/>')
        out.append(f'<text x="{left + gb * scale + 8}" y="{y + 19}" class="val">{gb:.1f} GB</text>')
    base = len(rows) * (h + gap) + 4
    out.append(f'<line x1="{left + n["ram"] * scale:.1f}" y1="0" x2="{left + n["ram"] * scale:.1f}" y2="{base}" stroke="{INK2}" stroke-dasharray="4 3"/>')
    out.append(f'<text x="{left + n["ram"] * scale:.1f}" y="{base + 16}" text-anchor="end" class="sub">machine memory: {n["ram"]:.0f} GB</text>')
    out.append("</svg>")
    return "\n".join(out)


def render(d: dict) -> str:
    n = numbers(d)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Memory use with one agent versus five agents</title>
<style>
:root {{ --ink:{INK}; --ink2:{INK2}; --line:{LINE}; --blue:{BLUE}; }}
* {{ box-sizing:border-box; }}
body {{ font:14px/1.5 -apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; color:var(--ink); background:#fff; margin:0; }}
main {{ max-width:760px; margin:0 auto; padding:32px 28px 40px; }}
h1 {{ font-size:22px; line-height:1.25; margin:0 0 4px; }} .sub0 {{ color:var(--ink2); margin:0 0 16px; }}
h2 {{ font-size:15px; margin:20px 0 6px; }} p {{ margin:6px 0 8px; }}
.answer {{ background:#f3f7fd; border-left:4px solid var(--blue); padding:10px 14px; border-radius:4px; margin:12px 0; }}
table {{ border-collapse:collapse; width:100%; margin:8px 0; font-size:12.5px; }}
th,td {{ border-bottom:1px solid var(--line); padding:5px 8px; text-align:right; }} th {{ text-align:left; font-weight:600; }}
thead th {{ text-align:right; }} thead th:first-child {{ text-align:left; }}
.chart {{ width:100%; height:auto; display:block; margin:8px 0 2px; }} .chart .lbl {{ font-size:12.5px; fill:var(--ink); }}
.chart .val {{ font-size:12.5px; font-weight:600; fill:var(--ink); }} .chart .sub {{ font-size:11px; fill:var(--ink2); }}
ul {{ margin:6px 0 8px 18px; padding:0; }} li {{ margin:3px 0; }} .note {{ color:var(--ink2); font-size:12px; }}
code {{ background:#f4f3ef; padding:1px 5px; border-radius:3px; font-size:12px; }}
</style></head><body><main>
<h1>Does a model use the same memory with five agents as with one?</h1>
<p class="sub0">Measured with {html.escape(d['model'])} on {html.escape(d['hardware'])}.</p>

<div class="answer"><strong>Short answer.</strong> It depends on the Ollama setting. With the default (one request at a time) five agents that share a model use
<strong>the same {n['seq_mem']:.1f} GB</strong> as one agent, but they are served one after another. If you let Ollama serve the five agents in parallel,
memory grows to <strong>{n['par_mem']:.1f} GB</strong> ({n['mem_ratio']:.1f}x as much) and the five answers arrive about {n['speedup']:.1f}x as fast.</div>

{chart(n)}

<h2>What was measured</h2>
<table><thead><tr><th>Setting</th><th>Memory</th><th>Time for {n['agents']} answers of {n['tokens']} tokens</th><th>Total speed</th><th>Speed per agent</th></tr></thead><tbody>
<tr><th>One request at a time (default)</th><td>{n['seq_mem']:.1f} GB</td><td>{n['seq_s']:.1f} s</td><td>{n['seq_tps']:.0f} tok/s</td><td>{n['single']:.1f} tok/s while it is its turn</td></tr>
<tr><th>Parallel ({n['agents']} at once)</th><td>{n['par_mem']:.1f} GB</td><td>{n['par_s']:.1f} s</td><td>{n['par_tps']:.0f} tok/s</td><td>{n['par_per_agent']:.1f} tok/s each</td></tr>
</tbody></table>

<h2>Why it works this way</h2>
<ul>
<li><strong>The model weights are loaded once</strong> ({n['weights']:.1f} GB here) and shared by every agent that uses the same model. More agents do not copy the model.</li>
<li><strong>Each request slot needs its own context memory</strong> (the "KV cache"): about {n['slot']:.1f} GB per slot at a context of {n['ctx']:,} tokens. One slot gives {n['weights']:.1f} + {n['slot']:.1f} = {n['seq_mem']:.1f} GB;
{n['agents']} slots give {n['weights']:.1f} + {n['agents']} x {n['slot']:.1f} = {n['par_mem']:.1f} GB. Ollama reserves the slots when the model loads, whether or not they are busy.</li>
<li><strong>With one slot the agents queue.</strong> Memory stays low, but the fifth agent waits for the four before it.</li>
<li><strong>Different models add up.</strong> Five agents on five different models keep five models in memory (up to the limit set in Ollama; here 2 loaded at a time).</li>
</ul>

<h2>What to choose</h2>
<ul>
<li><strong>Agents that mostly wait on each other or on tools:</strong> keep one slot. Cheapest in memory.</li>
<li><strong>Agents that all answer at the same moment:</strong> use two or three slots as a compromise, or a smaller model. A {n['ram']:.0f} GB machine has only about {n['ram'] - n['par_mem']:.0f} GB left over at {n['par_mem']:.1f} GB.</li>
<li><strong>Shrink the cost per slot</strong> with a smaller context window, or pick a model with memory-efficient attention (newer 7B and 8B models need far less context memory than Llama 2 13B).</li>
</ul>
<p class="note">One measurement per setting, on one machine and one model, with flash attention on and an 8-bit KV cache. Numbers for other models and context lengths will differ. The parallel run used a temporary second Ollama instance with <code>OLLAMA_NUM_PARALLEL={n['agents']}</code>, stopped afterwards; the other run used the production service.</p>
</main></body></html>
"""


def pdf(html_path: Path, pdf_path: Path) -> bool:
    for b in BROWSERS:
        if Path(b).exists():
            try:
                subprocess.run([b, "--headless", "--disable-gpu", "--no-pdf-header-footer", f"--print-to-pdf={pdf_path}", html_path.resolve().as_uri()],
                               capture_output=True, timeout=120)
            except (OSError, subprocess.SubprocessError):
                continue
            if pdf_path.exists() and pdf_path.stat().st_size > 3000:
                return True
    return False


def main():
    d = json.loads(DATA.read_text(encoding="utf-8"))
    OUT_HTML.write_text(render(d), encoding="utf-8")
    print("written:", OUT_HTML, "| pdf:", "yes" if pdf(OUT_HTML, OUT_PDF) else "NO")


if __name__ == "__main__":
    main()
