"""Turns the stored answers of a run into a static website (index, hairball, blind vote) and a markdown summary. No server, no external files."""
import html
import json
import math
import random
import statistics
from pathlib import Path

from .models import display_name, load_models
from .runner import read_records
from .system import describe
from .tasks import TRACK_LABELS, TRACKS, all_tracks

BLUE, GREY, INK, INK2, LINE = "#2a78d6", "#a9a8a2", "#0b0b0b", "#52514e", "#dcdbd5"
HAIRBALL_PRIORITY = {"honesty": 0, "cybersecurity": 1, "tools": 2, "dutch": 3, "daily": 4, "reasoning": 5, "coding": 6, "longcontext": 7, "hard": 8}


def load_run(run_dir: Path) -> dict:
    run_dir = Path(run_dir)
    try:
        manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        manifest = {}
    data = {}
    for mdir in sorted(p for p in run_dir.iterdir() if p.is_dir()):
        recs = {}
        for f in mdir.glob("*.jsonl"):
            rs = read_records(f)
            if rs:
                recs[f.stem] = rs
        if recs:
            tag = next(iter(recs.values()))[0]["model"]
            data[tag] = recs
    extra = {}
    for name in ("perf", "parallel"):
        try:
            extra[name] = json.loads((run_dir / f"{name}.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
    return {"manifest": manifest, "data": data, **extra}


def aggregate(data: dict) -> dict:
    """{model: {track: {mean, lo, hi, seeds, n_tasks, tasks: {id: mean}, truncated}}} — the mean of per-seed means, with the range over seeds."""
    out = {}
    for model, tracks in data.items():
        out[model] = {}
        for track, recs in tracks.items():
            by_seed = {}
            for r in recs:
                by_seed.setdefault(r["seed"], []).append(r["score"])
            seed_means = [statistics.mean(v) for v in by_seed.values()]
            tasks = {}
            for r in recs:
                tasks.setdefault(r["task"], []).append(r["score"])
            out[model][track] = {"mean": statistics.mean(seed_means), "lo": min(seed_means), "hi": max(seed_means), "seeds": len(by_seed),
                                 "n_tasks": len(tasks), "tasks": {k: statistics.mean(v) for k, v in tasks.items()},
                                 "truncated": sum(1 for r in recs if r.get("truncated") or r.get("cut_in_thinking")), "answers": len(recs),
                                 "secs": statistics.mean(r["secs"] for r in recs)}
    return out


def track_average(agg_model: dict, tracks: list) -> float:
    vals = [agg_model[t]["mean"] for t in tracks if t in agg_model]
    return statistics.mean(vals) if vals else 0.0


def noise(agg: dict) -> float:
    """The largest spread between seeds of any model on any track: differences below this are not meaningful."""
    spreads = [t["hi"] - t["lo"] for m in agg.values() for t in m.values() if t["seeds"] > 1]
    return max(spreads) if spreads else 0.0


def heat(v):
    return f"background:rgba(42,120,214,{0.06 + 0.54 * v:.2f})"


def radar_svg(values: dict, tracks: list, size: int = 200) -> str:
    cx = cy = size / 2
    r = size / 2 - 34
    n = len(tracks)
    pts, labels = [], []
    for i, t in enumerate(tracks):
        a = -math.pi / 2 + 2 * math.pi * i / n
        v = max(0.0, min(1.0, values.get(t, 0.0)))
        pts.append(f"{cx + r * v * math.cos(a):.1f},{cy + r * v * math.sin(a):.1f}")
        lx, ly = cx + (r + 14) * math.cos(a), cy + (r + 14) * math.sin(a)
        anchor = "middle" if abs(math.cos(a)) < 0.3 else ("start" if math.cos(a) > 0 else "end")
        labels.append(f'<text x="{lx:.1f}" y="{ly + 3:.1f}" text-anchor="{anchor}" class="rl">{html.escape(TRACK_LABELS[t].split(" ")[0])}</text>')
    rings = "".join('<polygon points="' + " ".join(f"{cx + r * k * math.cos(-math.pi / 2 + 2 * math.pi * i / n):.1f},{cy + r * k * math.sin(-math.pi / 2 + 2 * math.pi * i / n):.1f}"
                                                  for i in range(n)) + f'" fill="none" stroke="{LINE}"/>' for k in (0.5, 1.0))
    return (f'<svg viewBox="0 0 {size} {size}" class="radar" role="img">{rings}<polygon points="{" ".join(pts)}" fill="{BLUE}" fill-opacity="0.25" '
            f'stroke="{BLUE}" stroke-width="2"/>{"".join(labels)}</svg>')


def hairball(data: dict, per_model: int = 3) -> dict:
    """The worst answers of each model: lowest mean score per task, honesty failures first. Returns {model: [records]}."""
    out = {}
    for model, tracks in data.items():
        by_task = {}
        for track, recs in tracks.items():
            for r in recs:
                by_task.setdefault((track, r["task"]), []).append(r)
        ranked = sorted(by_task.items(), key=lambda kv: (statistics.mean(x["score"] for x in kv[1]), HAIRBALL_PRIORITY.get(kv[0][0], 9)))
        picked = []
        for (track, task), recs in ranked:
            if statistics.mean(x["score"] for x in recs) > 0.34 or len(picked) >= per_model:
                break
            worst = min(recs, key=lambda x: x["score"])
            picked.append(worst)
        out[model] = picked
    return out


CSS = f"""
:root {{ --ink:{INK}; --ink2:{INK2}; --line:{LINE}; --blue:{BLUE}; --bg:#fff; --panel:#fafaf8; }}
@media (prefers-color-scheme: dark) {{ :root {{ --ink:#f0efec; --ink2:#c3c2b7; --line:#3a3a37; --blue:#3987e5; --bg:#1a1a19; --panel:#222220; }} }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--ink); font:15px/1.5 -apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; }}
main {{ max-width:1100px; margin:0 auto; padding:28px 18px 60px; }}
h1 {{ font-size:28px; margin:0 0 4px; }} h2 {{ font-size:19px; margin:30px 0 8px; padding-top:10px; border-top:1px solid var(--line); }}
p {{ margin:6px 0 10px; }} .sub {{ color:var(--ink2); }} a {{ color:var(--blue); }}
nav a {{ margin-right:14px; font-weight:600; }}
table {{ border-collapse:collapse; width:100%; font-size:13px; margin:8px 0; }}
th,td {{ border-bottom:1px solid var(--line); padding:6px 8px; text-align:right; }} th {{ text-align:left; font-weight:600; }}
thead th {{ text-align:right; vertical-align:bottom; font-size:12px; }} thead th:first-child {{ text-align:left; }}
td small {{ display:block; color:var(--ink2); font-size:10.5px; }}
.cards {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(210px,1fr)); gap:12px; }}
.card {{ border:1px solid var(--line); border-radius:10px; background:var(--panel); padding:8px 10px; }} .card b {{ font-size:14px; }}
.radar {{ width:100%; height:auto; }} .rl {{ font-size:9.5px; fill:var(--ink2); }}
.note {{ color:var(--ink2); font-size:12.5px; }} .warn {{ color:#b45309; }}
pre {{ white-space:pre-wrap; background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:8px 10px; font-size:12.5px; }}
.balls {{ display:grid; gap:14px; }} .ball {{ border:1px solid var(--line); border-radius:10px; padding:10px 12px; background:var(--panel); }}
button {{ font:inherit; padding:8px 14px; border:1px solid var(--line); background:var(--panel); color:var(--ink); border-radius:8px; cursor:pointer; }}
button.go {{ background:var(--blue); border-color:var(--blue); color:#fff; font-weight:600; }}
"""


def page(title: str, body: str, extra_head: str = "") -> str:
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f"<title>{html.escape(title)}</title><style>{CSS}</style>{extra_head}</head><body><main>{body}</main></body></html>")


def nav(active: str) -> str:
    items = [("index", "Results"), ("hairball", "Hairball"), ("vote", "Blind vote")]
    parts = []
    for page_name, label in items:
        style = ' style="text-decoration:underline"' if page_name == active else ""
        parts.append(f'<a href="{page_name}.html"{style}>{label}</a>')
    return "<nav>" + "".join(parts) + "</nav>"


def render_index(run: dict, agg: dict, models_cfg: dict, tracks: list) -> str:
    m = run["manifest"]
    mach = m.get("machine", {})
    order = sorted(agg, key=lambda k: -track_average(agg[k], tracks))
    head = "".join(f"<th>{html.escape(TRACK_LABELS[t])}</th>" for t in tracks)
    rows = ""
    for model in order:
        cells = ""
        for t in tracks:
            a = agg[model].get(t)
            if not a:
                cells += "<td>—</td>"
                continue
            rng = f"{a['lo']:.2f}–{a['hi']:.2f}" if a["seeds"] > 1 else "1 run"
            cut = f' <span class="warn" title="answers cut off by the token limit">⚠{a["truncated"]}</span>' if a["truncated"] else ""
            cells += f'<td style="{heat(a["mean"])}">{a["mean"]:.2f}{cut}<small>{rng}</small></td>'
        rows += f"<tr><th>{html.escape(display_name(model, models_cfg))}</th><td>{track_average(agg[model], tracks):.2f}</td>{cells}</tr>"
    cards = "".join(f'<div class="card"><b>{html.escape(display_name(k, models_cfg))}</b>{radar_svg({t: agg[k][t]["mean"] for t in tracks if t in agg[k]}, tracks)}</div>' for k in order)
    perf = ""
    if "perf" in run:
        pm = run["perf"].get("models", run["perf"])
        prow = "".join(f"<tr><th>{html.escape(display_name(k, models_cfg))}</th><td>{v['cold_load_s']} s</td><td>{v['reading_tok_s']:.0f}</td>"
                       f"<td>{v['first_token_long_prompt_s']} s</td><td>{v['generation_tok_s']}</td><td>{v.get('memory_gb', '—')} GB</td></tr>"
                       for k, v in sorted(pm.items(), key=lambda kv: -kv[1]["generation_tok_s"]))
        perf = ("<h2>Speed and memory</h2><p class='sub'>Counters reported by Ollama; median of 3 rounds, model freshly loaded, context 8192. Reading = a log of about "
                "3,000 tokens; generating = 256 tokens.</p><table><thead><tr><th>Model</th><th>Cold load</th><th>Reading (tok/s)</th><th>First token after long prompt</th>"
                f"<th>Generating (tok/s)</th><th>Memory</th></tr></thead><tbody>{prow}</tbody></table>")
    par = ""
    if "parallel" in run:
        rows_p = "".join(f"<tr><th>{html.escape(display_name(p['model'], models_cfg))}</th><td>{p['agents']}</td><td>{p['memory_one_request_gb']} GB</td>"
                         f"<td>{p['memory_during_parallel_gb']} GB</td><td>{p['seconds_for_all']} s</td><td>{p['total_tok_s']}</td><td>{html.escape(p.get('note', ''))}</td></tr>"
                         for p in (run["parallel"] if isinstance(run["parallel"], list) else [run["parallel"]]))
        par = ("<h2>Several agents at once</h2><table><thead><tr><th>Model</th><th>Agents</th><th>Memory, one request</th><th>Memory, all at once</th><th>Time for all</th>"
               f"<th>Total tok/s</th><th>Setting</th></tr></thead><tbody>{rows_p}</tbody></table>")
    body = (f"<h1>macmini-cat-bench</h1><p class='sub'>Honest AI benchmarks on the Mac mini. Run <code>{html.escape(m.get('run_id', '?'))}</code> on "
            f"{html.escape(describe(mach))}, macOS {html.escape(str(mach.get('macos', '?')))}, Ollama {html.escape(str(m.get('ollama', '?')))}, {html.escape(str(m.get('date', '')))}.</p>"
            f"{nav('index')}<h2>Profile per track</h2><p>Score from 0 to 1 per track: mean over seeds, with the range between seeds underneath. There is no single winner: "
            f"look at the tracks that matter to you. The second column is the plain average of the tracks, for sorting only. "
            f"Run-to-run noise in this run reaches {noise(agg):.2f}: differences smaller than that are not meaningful. "
            f"<span class='warn'>⚠n</span> means n answers were cut off by the token limit.</p>"
            f"<table><thead><tr><th>Model</th><th>Track average</th>{head}</tr></thead><tbody>{rows}</tbody></table>"
            f"<h2>Profiles</h2><div class='cards'>{cards}</div>{perf}{par}"
            "<h2>Limitations</h2><ul><li>Small task sets per track and automatic scoring on keywords, numbers, JSON and executed code; a human check of a sample is planned.</li>"
            "<li>One machine, one quantisation per model, English prompts except the Dutch track.</li>"
            "<li>Model-written code is executed on the benchmark machine.</li></ul>"
            "<p class='note'>Prompts, scoring rules, raw answers and scripts are in the repository. See the Hairball page for the worst answers.</p>")
    return page("macmini-cat-bench", body)


def render_hairball(run: dict, models_cfg: dict, tasks: dict) -> str:
    worst = hairball(run["data"])
    prompts = {(t, x["id"]): x.get("prompt", "") for t, d in tasks.items() for x in d["tasks"]}
    blocks = ""
    for model, recs in sorted(worst.items(), key=lambda kv: display_name(kv[0], models_cfg).lower()):
        if not recs:
            blocks += f"<div class='ball'><b>{html.escape(display_name(model, models_cfg))}</b><p class='note'>No answers scored below 0.34. Nothing to show here.</p></div>"
            continue
        items = ""
        for r in recs:
            p = prompts.get((r["track"], r["task"]), "")
            note = " <span class='warn'>(cut off by the token limit)</span>" if r.get("truncated") or r.get("cut_in_thinking") else ""
            items += (f"<p><b>{html.escape(TRACK_LABELS.get(r['track'], r['track']))} / {html.escape(r['task'])}</b> (score {r['score']:.2f}, seed {r['seed']}){note}</p>"
                      f"<pre>Q: {html.escape(p[:500])}</pre><pre>A: {html.escape(r['answer'][:700]) or '(empty answer)'}</pre>")
        blocks += f"<div class='ball'><h3 style='margin:0 0 6px'>{html.escape(display_name(model, models_cfg))}</h3>{items}</div>"
    body = (f"<h1>Hairball</h1><p class='sub'>The worst answers of every model, verbatim: where it invented things, ignored the format or simply got it wrong. "
            f"Shown only when the mean score of that task is below 0.34.</p>{nav('hairball')}<div class='balls'>{blocks}</div>")
    return page("Hairball: macmini-cat-bench", body)


def vote_pairs(run: dict, tasks: dict, models_cfg: dict, n: int = 40, seed: int = 7) -> list:
    """Pairs of answers from two models to the same prompt, for the blind vote. Picks tasks where the answers differ."""
    rng = random.Random(seed)
    prompts = {(t, x["id"]): x.get("prompt", "") for t, d in tasks.items() for x in d["tasks"] if "long" not in x}
    index = {}
    for model, tracks in run["data"].items():
        for track, recs in tracks.items():
            for r in recs:
                if r["seed"] == min(x["seed"] for x in recs) and (track, r["task"]) in prompts and r["answer"].strip():
                    index.setdefault((track, r["task"]), {})[model] = r
    pairs = []
    for key, by_model in index.items():
        ms = sorted(by_model)
        for i in range(len(ms)):
            for j in range(i + 1, len(ms)):
                if by_model[ms[i]]["answer"].strip() != by_model[ms[j]]["answer"].strip():
                    pairs.append((key, ms[i], ms[j]))
    rng.shuffle(pairs)
    out = []
    for key, a, b in pairs[:n]:
        if rng.random() < 0.5:
            a, b = b, a
        out.append({"track": key[0], "task": key[1], "prompt": prompts[key][:900], "a": {"model": a, "name": display_name(a, models_cfg), "text": index[key][a]["answer"][:1200]},
                    "b": {"model": b, "name": display_name(b, models_cfg), "text": index[key][b]["answer"][:1200]}})
    return out


VOTE_JS = """
const P = DATA.pairs; let i = 0; const votes = JSON.parse(localStorage.getItem('catbench-votes') || '[]');
const $ = id => document.getElementById(id);
function elo() { const r = {}; votes.forEach(v => { if (v.w === 'tie' || v.w === 'bad') return; const a = r[v.a] ?? 1000, b = r[v.b] ?? 1000;
  const ea = 1 / (1 + Math.pow(10, (b - a) / 400)), sa = v.w === 'a' ? 1 : 0; r[v.a] = a + 24 * (sa - ea); r[v.b] = b + 24 * ((1 - sa) - (1 - ea)); });
  return Object.entries(r).sort((x, y) => y[1] - x[1]); }
function show() { if (i >= P.length) { $('card').innerHTML = '<p>No more pairs. Thank you!</p>'; return; } const p = P[i];
  $('prompt').textContent = p.prompt; $('a').textContent = p.a.text; $('b').textContent = p.b.text; $('reveal').textContent = ''; $('count').textContent = (i + 1) + ' / ' + P.length; }
function vote(w) { const p = P[i]; votes.push({ task: p.task, a: p.a.model, b: p.b.model, w }); localStorage.setItem('catbench-votes', JSON.stringify(votes));
  $('reveal').textContent = 'A was ' + p.a.name + ', B was ' + p.b.name; i++; setTimeout(show, 1400); table(); }
function table() { $('elo').innerHTML = elo().map(([m, r]) => '<tr><th>' + m + '</th><td>' + Math.round(r) + '</td></tr>').join(''); $('n').textContent = votes.length; }
function dl() { const csv = 'task,a,b,winner\\n' + votes.map(v => [v.task, v.a, v.b, v.w].join(',')).join('\\n'); const l = document.createElement('a');
  l.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv' })); l.download = 'catbench-votes.csv'; l.click(); }
document.querySelectorAll('[data-w]').forEach(b => b.onclick = () => vote(b.dataset.w)); $('dl').onclick = dl; show(); table();
"""


def render_vote(run: dict, models_cfg: dict, tasks: dict) -> str:
    pairs = vote_pairs(run, tasks, models_cfg)
    data = json.dumps({"pairs": pairs}, ensure_ascii=False).replace("</", "<\\/")
    body = (f"<h1>Blind vote</h1><p class='sub'>Two answers to the same question, without model names. Pick the better one. Votes stay in your browser (nothing is sent anywhere); "
            f"download them as CSV to share. This complements the automatic scores, which cannot judge style.</p>{nav('vote')}"
            "<div id='card'><p id='count' class='note'></p><h3>Question</h3><pre id='prompt'></pre><div style='display:grid;grid-template-columns:1fr 1fr;gap:12px'>"
            "<div><h3>Answer A</h3><pre id='a'></pre></div><div><h3>Answer B</h3><pre id='b'></pre></div></div>"
            "<p><button class='go' data-w='a'>A is better</button> <button class='go' data-w='b'>B is better</button> <button data-w='tie'>Tie</button> "
            "<button data-w='bad'>Both bad</button></p><p id='reveal' class='note'></p></div>"
            "<h2>Your ranking so far (<span id='n'>0</span> votes)</h2><table><tbody id='elo'></tbody></table><p><button id='dl'>Download votes (CSV)</button></p>")
    return page("Blind vote: macmini-cat-bench", body, f"<script>const DATA = {data};</script>") .replace("</main>", f"<script>{VOTE_JS}</script></main>")


def markdown_summary(run: dict, agg: dict, models_cfg: dict, tracks: list) -> str:
    m = run["manifest"]
    lines = [f"# Results: {m.get('run_id', '')}", "", f"{describe(m.get('machine', {}))}, Ollama {m.get('ollama', '?')}, {m.get('date', '')}.", "",
             "| Model | Track average | " + " | ".join(TRACK_LABELS[t] for t in tracks) + " |", "|---|---|" + "---|" * len(tracks)]
    for model in sorted(agg, key=lambda k: -track_average(agg[k], tracks)):
        cells = [(f"{agg[model][t]['mean']:.2f} ({agg[model][t]['lo']:.2f}–{agg[model][t]['hi']:.2f})" if t in agg[model] else "—") for t in tracks]
        lines.append(f"| {display_name(model, models_cfg)} | {track_average(agg[model], tracks):.2f} | " + " | ".join(cells) + " |")
    lines += ["", f"Run-to-run noise in this run reaches {noise(agg):.2f}; smaller differences are not meaningful."]
    return "\n".join(lines) + "\n"


def build(run_dir: Path, site_dir: Path, models_path: Path = None) -> dict:
    run = load_run(run_dir)
    if not run["data"]:
        raise SystemExit(f"no results found in {run_dir}")
    models_cfg = load_models(models_path)
    tasks = all_tracks()
    tracks = [t for t in TRACKS if any(t in tr for tr in run["data"].values())]
    agg = aggregate(run["data"])
    site_dir = Path(site_dir)
    site_dir.mkdir(parents=True, exist_ok=True)
    (site_dir / "index.html").write_text(render_index(run, agg, models_cfg, tracks), encoding="utf-8")
    (site_dir / "hairball.html").write_text(render_hairball(run, models_cfg, tasks), encoding="utf-8")
    (site_dir / "vote.html").write_text(render_vote(run, models_cfg, tasks), encoding="utf-8")
    (site_dir / "results.json").write_text(json.dumps({"run": run["manifest"].get("run_id"), "tracks": tracks,
                                                     "models": {m: {t: {k: v for k, v in a.items() if k != "tasks"} for t, a in tr.items()} for m, tr in agg.items()}},
                                                    indent=1, ensure_ascii=False), encoding="utf-8")
    (site_dir / "RESULTS.md").write_text(markdown_summary(run, agg, models_cfg, tracks), encoding="utf-8")
    return {"models": len(agg), "tracks": tracks, "noise": noise(agg)}
