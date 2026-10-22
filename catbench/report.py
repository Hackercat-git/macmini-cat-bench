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
HAIRBALL_PRIORITY = {"honesty": 0, "cybersecurity": 1, "tools": 2, "dutch": 3, "daily": 4, "reasoning": 5, "coding": 6, "longcontext": 7, "hard": 8, "pentest": 1, "standard": 9}


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


CSS = """
:root { --ink:#14161a; --ink2:#5b616b; --line:#e3e5e9; --blue:#2a78d6; --bg:#f6f7f9; --panel:#ffffff; --soft:#eef3fb; --good:#1a7f4b; --warn:#b45309; --shadow:0 1px 2px rgba(20,22,26,.06),0 4px 14px rgba(20,22,26,.05); }
@media (prefers-color-scheme: dark) { :root { --ink:#eceef2; --ink2:#a3a9b4; --line:#2b2f36; --blue:#4d94ec; --bg:#101216; --panel:#171a1f; --soft:#1b2433; --good:#46c07f; --warn:#e0a24a; --shadow:none; } }
* { box-sizing:border-box; }
html { scroll-behavior:smooth; }
body { margin:0; background:var(--bg); color:var(--ink); font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; -webkit-font-smoothing:antialiased; }
a { color:var(--blue); text-decoration:none; } a:hover { text-decoration:underline; }
code { background:var(--soft); padding:1px 6px; border-radius:5px; font-size:.9em; }
.top { position:sticky; top:0; z-index:5; background:color-mix(in srgb,var(--bg) 88%,transparent); backdrop-filter:blur(10px); border-bottom:1px solid var(--line); }
.top .in { max-width:1180px; margin:0 auto; padding:10px 20px; display:flex; align-items:center; gap:22px; }
.brand { font-weight:700; letter-spacing:-.01em; color:var(--ink); display:flex; align-items:center; gap:8px; } .brand:hover { text-decoration:none; }
.brand i { width:22px; height:22px; border-radius:7px; background:var(--blue); display:inline-block; position:relative; }
.brand i:after { content:""; position:absolute; inset:6px; border-radius:50%; background:#fff; opacity:.9; }
nav { display:flex; gap:4px; margin-left:auto; } nav a { color:var(--ink2); font-weight:600; font-size:14px; padding:6px 12px; border-radius:8px; } nav a:hover { background:var(--soft); text-decoration:none; color:var(--ink); }
nav a.on { background:var(--soft); color:var(--blue); }
main { max-width:1180px; margin:0 auto; padding:34px 20px 70px; }
.hero h1 { font-size:clamp(30px,5vw,46px); line-height:1.08; letter-spacing:-.025em; margin:0 0 12px; }
.hero p { font-size:17px; color:var(--ink2); max-width:760px; margin:0 0 6px; }
.chips { display:flex; flex-wrap:wrap; gap:8px; margin:16px 0 4px; } .chip { font-size:12.5px; color:var(--ink2); background:var(--panel); border:1px solid var(--line); border-radius:999px; padding:3px 11px; }
.stats { display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:12px; margin:26px 0 8px; }
.stat { background:var(--panel); border:1px solid var(--line); border-radius:14px; padding:14px 16px; box-shadow:var(--shadow); }
.stat b { display:block; font-size:30px; line-height:1.1; letter-spacing:-.02em; } .stat span { color:var(--ink2); font-size:13px; }
h2 { font-size:22px; letter-spacing:-.015em; margin:46px 0 6px; } h3 { font-size:16px; margin:14px 0 6px; }
.lead { color:var(--ink2); margin:0 0 16px; max-width:820px; }
.finds { display:grid; grid-template-columns:repeat(auto-fit,minmax(240px,1fr)); gap:12px; }
.find { background:var(--panel); border:1px solid var(--line); border-radius:14px; padding:16px; box-shadow:var(--shadow); }
.find small { color:var(--ink2); text-transform:uppercase; letter-spacing:.06em; font-size:11px; font-weight:700; }
.find b { display:block; font-size:19px; margin:4px 0 2px; letter-spacing:-.01em; } .find span { color:var(--ink2); font-size:13.5px; }
.panel { background:var(--panel); border:1px solid var(--line); border-radius:14px; box-shadow:var(--shadow); }
.scroll { overflow-x:auto; }
table { border-collapse:collapse; width:100%; font-size:13.5px; }
th,td { padding:9px 10px; text-align:right; white-space:nowrap; border-bottom:1px solid var(--line); }
tbody tr:last-child th, tbody tr:last-child td { border-bottom:0; }
th { font-weight:600; } thead th { position:sticky; top:0; background:var(--panel); color:var(--ink2); font-size:12px; vertical-align:bottom; white-space:normal; line-height:1.25; cursor:pointer; user-select:none; }
thead th:hover { color:var(--blue); } th.l, td.l { text-align:left; }
tbody tr:hover td, tbody tr:hover th { background:var(--soft); }
.rank { color:var(--ink2); width:34px; text-align:left; font-variant-numeric:tabular-nums; }
.mname { font-weight:650; } .mname small { display:block; color:var(--ink2); font-weight:400; font-size:11.5px; }
.avg { display:flex; align-items:center; gap:8px; justify-content:flex-end; min-width:130px; font-weight:700; font-variant-numeric:tabular-nums; }
.avg i { display:block; height:7px; border-radius:4px; background:var(--blue); min-width:2px; } .avg s { display:block; width:70px; height:7px; border-radius:4px; background:var(--line); text-decoration:none; }
.cell { font-variant-numeric:tabular-nums; border-radius:6px; } .cell small { display:block; color:var(--ink2); font-size:10.5px; }
.warn { color:var(--warn); }
.muted { color:var(--ink2); }
.cards { display:grid; grid-template-columns:repeat(auto-fill,minmax(210px,1fr)); gap:12px; }
.card { border:1px solid var(--line); border-radius:12px; background:var(--panel); padding:10px 12px; } .card b { font-size:14px; }
.radar { width:100%; height:auto; } .rl { font-size:9.5px; fill:var(--ink2); }
.note { color:var(--ink2); font-size:13px; }
details { margin:10px 0; } summary { cursor:pointer; font-weight:600; color:var(--blue); }
pre { white-space:pre-wrap; background:var(--soft); border:1px solid var(--line); border-radius:10px; padding:10px 12px; font-size:12.5px; }
.balls { display:grid; gap:14px; } .ball { border:1px solid var(--line); border-radius:14px; padding:12px 16px; background:var(--panel); box-shadow:var(--shadow); }
button { font:inherit; font-weight:600; padding:9px 16px; border:1px solid var(--line); background:var(--panel); color:var(--ink); border-radius:10px; cursor:pointer; }
button:hover { border-color:var(--blue); } button.go { background:var(--blue); border-color:var(--blue); color:#fff; }
.legend { display:flex; gap:16px; flex-wrap:wrap; font-size:12.5px; color:var(--ink2); padding:12px 16px 0; }
svg.scatter { width:100%; height:auto; display:block; } .scatter text { font:11px -apple-system,Segoe UI,sans-serif; fill:var(--ink2); } .scatter .pl { fill:var(--ink); font-weight:600; }
.scatter circle { fill:var(--blue); stroke:var(--panel); stroke-width:2; } .scatter circle:hover { fill:var(--ink); } .scatter .grid { stroke:var(--line); }
.pars { display:grid; grid-template-columns:repeat(auto-fit,minmax(260px,1fr)); gap:12px; }
.par { background:var(--panel); border:1px solid var(--line); border-radius:14px; padding:16px; box-shadow:var(--shadow); } .par b { font-size:15px; } .par .big { font-size:30px; font-weight:700; letter-spacing:-.02em; margin:6px 0 0; } .par ul { margin:8px 0 0; padding-left:18px; color:var(--ink2); font-size:13.5px; }
footer { margin-top:50px; padding-top:18px; border-top:1px solid var(--line); color:var(--ink2); font-size:13px; }
@media (max-width:640px) { .top .in { gap:10px; padding:8px 14px; } .brand span { display:none; } main { padding:22px 14px 50px; } nav a { padding:6px 9px; } }
"""


def page(title: str, body: str, extra_head: str = "", active: str = "index") -> str:
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<meta name="color-scheme" content="light dark"><title>{html.escape(title)}</title><style>{CSS}</style>{extra_head}</head><body>'
            f'<header class="top"><div class="in"><a class="brand" href="index.html"><i></i><span>macmini-cat-bench</span></a>{nav(active)}</div></header>'
            f"<main>{body}</main></body></html>")


def nav(active: str) -> str:
    items = [("index", "Results"), ("hairball", "Hairball"), ("vote", "Blind vote")]
    links = "".join(f'<a href="{n}.html"' + (' class="on"' if n == active else "") + f">{label}</a>" for n, label in items)
    return links.join(["<nav>", '<a href="https://github.com/Hackercat-git/macmini-cat-bench">GitHub</a></nav>'])


def _scatter(points: list) -> str:
    """points: [(label, x tok/s, y score)]. Direct labels placed greedily so they do not overlap; every point has a tooltip."""
    W, H, L, R, T, B = 900, 460, 54, 24, 16, 46
    xmax = max(p[1] for p in points) * 1.08
    ymin = max(0.0, math.floor((min(p[2] for p in points) - 0.05) * 10) / 10)

    def X(v):
        return L + (W - L - R) * v / xmax

    def Y(v):
        return T + (H - T - B) * (1 - (v - ymin) / (1 - ymin + 0.02))
    out = [f'<svg class="scatter" viewBox="0 0 {W} {H}" role="img" aria-label="Quality against speed">']
    step = 0.1
    v = math.ceil(ymin / step) * step
    while v <= 1.0001:
        out.append(f'<line class="grid" x1="{L}" x2="{W - R}" y1="{Y(v):.1f}" y2="{Y(v):.1f}"/><text x="{L - 8}" y="{Y(v) + 4:.1f}" text-anchor="end">{v:.1f}</text>')
        v += step
    tick = 10 if xmax <= 100 else 20
    for k in range(0, int(xmax) + 1, tick):
        out.append(f'<line class="grid" x1="{X(k):.1f}" x2="{X(k):.1f}" y1="{T}" y2="{H - B}"/><text x="{X(k):.1f}" y="{H - B + 18}" text-anchor="middle">{k}</text>')
    out.append(f'<text x="{(L + W - R) / 2}" y="{H - 8}" text-anchor="middle">writing speed (tokens per second) → faster</text>')
    out.append(f'<text transform="translate(14 {(T + H - B) / 2}) rotate(-90)" text-anchor="middle">average score → better</text>')
    placed = [(X(x) - 8, Y(y) - 8, X(x) + 8, Y(y) + 8) for _, x, y in points]            # the dots themselves are obstacles too
    for label, x, y in sorted(points, key=lambda p: -p[2]):
        cx, cy = X(x), Y(y)
        w = 6.2 * len(label)
        for dx, dy in ((9, 0), (9, -13), (9, 13), (9, -26), (9, 26), (-9 - w, 0), (-9 - w, -13), (-9 - w, 13), (9, -39), (9, 39)):
            box = (cx + dx, cy + dy - 9, cx + dx + w, cy + dy + 3)
            if all(box[2] < b[0] or box[0] > b[2] or box[3] < b[1] or box[1] > b[3] for b in placed) and box[2] < W:
                placed.append(box)
                out.append(f'<text class="pl" x="{cx + dx + 1:.1f}" y="{cy + dy:.1f}">{html.escape(label)}</text>')
                break
        out.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="6"><title>{html.escape(label)}: score {y:.2f}, {x:.1f} tok/s</title></circle>')
    out.append("</svg>")
    return "".join(out)


SORT_JS = """
document.querySelectorAll('table.sortable').forEach(t => { const body = t.tBodies[0];
  t.tHead.querySelectorAll('th').forEach((th, c) => th.addEventListener('click', () => { const dir = th.dataset.dir === 'desc' ? 'asc' : 'desc';
    t.tHead.querySelectorAll('th').forEach(x => delete x.dataset.dir); th.dataset.dir = dir;
    const val = r => { const v = r.cells[c].dataset.v; return v === undefined ? r.cells[c].textContent : parseFloat(v); };
    [...body.rows].sort((a, b) => { const x = val(a), y = val(b); const r = typeof x === 'number' ? x - y : String(x).localeCompare(String(y)); return dir === 'desc' ? -r : r; })
      .forEach((r, i) => { body.appendChild(r); r.cells[0].textContent = i + 1; }); })); });
"""


def render_index(run: dict, agg: dict, models_cfg: dict, tracks: list) -> str:
    m = run["manifest"]
    mach = m.get("machine", {})
    esc = html.escape
    order = sorted(agg, key=lambda k: -track_average(agg[k], tracks))
    pm = {}
    if "perf" in run:
        pm = run["perf"].get("models", run["perf"])
    name = lambda k: display_name(k, models_cfg)                                  # noqa: E731
    avg = {k: track_average(agg[k], tracks) for k in agg}
    n_tasks = max(sum(a["n_tasks"] for a in agg[k].values()) for k in agg)
    n_answers = sum(a["answers"] for k in agg for a in agg[k].values())
    seeds = max((a["seeds"] for k in agg for a in agg[k].values()), default=1)

    # --- findings, all computed from the data
    finds = []
    best = order[0]
    finds.append(("Best overall", name(best), f"{avg[best]:.2f} average over {len(tracks)} tracks"))
    cyber = [k for k in agg if "cybersecurity" in agg[k]]
    if cyber:
        c = max(cyber, key=lambda k: agg[k]["cybersecurity"]["mean"])
        finds.append(("Best at cybersecurity", name(c), f"{agg[c]['cybersecurity']['mean']:.2f} on the cybersecurity track"))
    good = [k for k in agg if avg[k] >= 0.9 and k in pm]
    if good:
        f = max(good, key=lambda k: pm[k]["generation_tok_s"])
        finds.append(("Fastest model that is still good", name(f), f"{pm[f]['generation_tok_s']:.0f} tok/s with an average of {avg[f]:.2f}"))
        mem = [k for k in good if pm[k].get("memory_gb")]
        if mem:
            s = min(mem, key=lambda k: pm[k]["memory_gb"])
            finds.append(("Smallest model that is still good", name(s), f"{pm[s]['memory_gb']} GB of memory with an average of {avg[s]:.2f}"))
    finds_html = "".join(f'<div class="find"><small>{esc(a)}</small><b>{esc(b)}</b><span>{esc(c)}</span></div>' for a, b, c in finds)

    # --- leaderboard
    head = "".join(f"<th>{esc(TRACK_LABELS[t])}</th>" for t in tracks)
    rows = ""
    for i, model in enumerate(order, 1):
        cells = ""
        for t in tracks:
            a = agg[model].get(t)
            if not a:
                cells += '<td data-v="-1">—</td>'
                continue
            rng = f"{a['lo']:.2f}–{a['hi']:.2f}" if a["seeds"] > 1 else "1 run"
            cut = f' <span class="warn" title="answers cut off by the token limit">⚠{a["truncated"]}</span>' if a["truncated"] else ""
            cells += (f'<td data-v="{a["mean"]:.3f}"><div class="cell" style="background:rgba(42,120,214,{0.05 + 0.5 * a["mean"] ** 2:.2f})">{a["mean"]:.2f}{cut}'
                      f"<small>{rng}</small></div></td>")
        p = pm.get(model, {})
        speed = f'<td data-v="{p.get("generation_tok_s", -1)}">{p["generation_tok_s"]:.0f}</td>' if p else '<td data-v="-1">—</td>'
        mem = f'<td data-v="{p.get("memory_gb") or -1}">{p["memory_gb"]} GB</td>' if p.get("memory_gb") else '<td data-v="-1">—</td>'
        fam = (models_cfg.get(model) or {}).get("family", "")
        rows += (f'<tr><td class="rank">{i}</td><th class="l mname">{esc(name(model))}<small>{esc(fam)}</small></th>'
                 f'<td data-v="{avg[model]:.3f}"><div class="avg"><s><i style="width:{avg[model] * 100:.0f}%"></i></s>{avg[model]:.2f}</div></td>{cells}{speed}{mem}</tr>')
    table = (f'<div class="panel scroll"><table class="sortable"><thead><tr><th class="l">#</th><th class="l">Model</th><th>Average</th>{head}'
             f"<th>Speed<br>(tok/s)</th><th>Memory</th></tr></thead><tbody>{rows}</tbody></table></div>")

    # --- quality against speed
    pts = [(name(k), pm[k]["generation_tok_s"], avg[k]) for k in agg if k in pm]
    scatter = ""
    if pts:
        scatter = ("<h2>Quality against speed</h2><p class='lead'>Top left is what you want: a high score <i>and</i> fast writing. "
                   "Hover a dot for the numbers.</p><div class='panel' style='padding:8px 10px 4px'>" + _scatter(pts) + "</div>")

    # --- speed table
    perf = ""
    if pm:
        top = max(v["generation_tok_s"] for v in pm.values())
        prow = "".join(f"<tr><th class='l'>{esc(name(k))}</th><td>{v['cold_load_s']} s</td><td>{v['reading_tok_s']:.0f}</td>"
                       f"<td>{v['first_token_long_prompt_s']} s</td><td><div class='avg'><s><i style='width:{v['generation_tok_s'] / top * 100:.0f}%'></i></s>"
                       f"{v['generation_tok_s']}</div></td><td>{v.get('memory_gb') or '—'}{' GB' if v.get('memory_gb') else ''}</td></tr>"
                       for k, v in sorted(pm.items(), key=lambda kv: -kv[1]["generation_tok_s"]))
        perf = ("<h2>Speed and memory</h2><p class='lead'>Counters reported by Ollama; median of 3 rounds, model freshly loaded, context 8192. "
                "Reading = a log of about 3,000 tokens; generating = 256 tokens.</p><div class='panel scroll'><table><thead><tr><th class='l'>Model</th><th>Cold load</th>"
                "<th>Reading (tok/s)</th><th>First token after long prompt</th><th>Generating (tok/s)</th><th>Memory</th></tr></thead>"
                f"<tbody>{prow}</tbody></table></div>")

    # --- parallel
    par = ""
    if "parallel" in run:
        items = ""
        for p in (run["parallel"] if isinstance(run["parallel"], list) else [run["parallel"]]):
            items += (f"<div class='par'><b>{esc(name(p['model']))}</b> <span class='muted'>· {p['agents']} agents</span><div class='big'>{p['total_tok_s']} <span class='muted' style='font-size:14px'>tok/s in total</span></div>"
                      f"<ul><li>{p['per_agent_tok_s']} tok/s per agent, all done in {p['seconds_for_all']} s</li>"
                      f"<li>Memory: {p['memory_one_request_gb']} GB with one request, {p['memory_during_parallel_gb']} GB with all agents</li>"
                      f"<li>{esc(p.get('note', ''))}</li></ul></div>")
        par = ("<h2>Several agents at once</h2><p class='lead'>What happens when five agents talk to the same Ollama server. The server setting decides: "
               f"one slot makes them queue, several slots cost memory but share the work.</p><div class='pars'>{items}</div>")

    cards = "".join(f'<div class="card"><b>{esc(name(k))}</b>{radar_svg({t: agg[k][t]["mean"] for t in tracks if t in agg[k]}, tracks)}</div>' for k in order)
    body = (f"<section class='hero'><h1>Honest AI benchmarks on the Mac mini</h1>"
            f"<p>Local language models, measured the same way on the same machine: quality over {len(tracks)} tracks (cybersecurity, daily use, coding, Dutch and more), "
            f"speed, memory and what happens when several agents share one server.</p>"
            f"<div class='chips'><span class='chip'>{esc(describe(mach))}</span><span class='chip'>macOS {esc(str(mach.get('macos', '?')))}</span>"
            f"<span class='chip'>Ollama {esc(str(m.get('ollama', '?')))}</span><span class='chip'>{esc(str(m.get('date', '')))}</span>"
            f"<span class='chip'>run {esc(m.get('run_id', '?'))}</span></div></section>"
            f"<div class='stats'><div class='stat'><b>{len(agg)}</b><span>models</span></div><div class='stat'><b>{len(tracks)}</b><span>tracks</span></div>"
            f"<div class='stat'><b>{n_tasks}</b><span>tasks per model</span></div><div class='stat'><b>{n_answers:,}</b><span>answers scored</span></div>"
            f"<div class='stat'><b>{seeds}</b><span>seeds per task</span></div></div>"
            f"<h2>The short version</h2><div class='finds'>{finds_html}</div>"
            f"<h2>Profile per track</h2><p class='lead'>Score from 0 to 1 per track: mean over seeds, with the range between seeds underneath. There is no single winner: "
            f"look at the tracks that matter to you. The average is for sorting only. Click a column heading to sort. "
            f"Run-to-run noise in this run reaches {noise(agg):.2f}: differences smaller than that are not meaningful. "
            f"<span class='warn'>⚠n</span> means n answers were cut off by the token limit.</p>{table}"
            f"{scatter}{perf}{par}"
            f"<h2>Profiles</h2><details><summary>Show a radar chart per model</summary><div class='cards' style='margin-top:12px'>{cards}</div></details>"
            "<h2>Limitations</h2><ul class='lead'><li>Small task sets per track and automatic scoring on keywords, numbers, JSON and executed code; a human check of a sample is planned.</li>"
            "<li>One machine, one quantisation per model, English prompts except the Dutch track.</li>"
            "<li>Model-written code is executed on the benchmark machine.</li></ul>"
            "<footer>Prompts, scoring rules, raw answers and scripts are in the <a href='https://github.com/Hackercat-git/macmini-cat-bench'>repository</a> (MIT licence). "
            "Run it on your own Mac mini and send a pull request. See the Hairball page for the worst answers and the Blind vote page to judge answers yourself.</footer>"
            f"<script>{SORT_JS}</script>")
    return page("macmini-cat-bench", body, active="index")


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
            f"Shown only when the mean score of that task is below 0.34.</p><div class='balls'>{blocks}</div>")
    return page("Hairball: macmini-cat-bench", body, active="hairball")


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
    body = ("<h1>Blind vote</h1><p class='sub'>Two answers to the same question, without model names. Pick the better one. Votes stay in your browser (nothing is sent anywhere); "
            "download them as CSV to share. This complements the automatic scores, which cannot judge style.</p>"
            "<div id='card'><p id='count' class='note'></p><h3>Question</h3><pre id='prompt'></pre><div style='display:grid;grid-template-columns:1fr 1fr;gap:12px'>"
            "<div><h3>Answer A</h3><pre id='a'></pre></div><div><h3>Answer B</h3><pre id='b'></pre></div></div>"
            "<p><button class='go' data-w='a'>A is better</button> <button class='go' data-w='b'>B is better</button> <button data-w='tie'>Tie</button> "
            "<button data-w='bad'>Both bad</button></p><p id='reveal' class='note'></p></div>"
            "<h2>Your ranking so far (<span id='n'>0</span> votes)</h2><table><tbody id='elo'></tbody></table><p><button id='dl'>Download votes (CSV)</button></p>")
    return page("Blind vote: macmini-cat-bench", body, f"<script>const DATA = {data};</script>", active="vote").replace("</main>", f"<script>{VOTE_JS}</script></main>")


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
