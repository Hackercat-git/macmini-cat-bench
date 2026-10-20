#!/usr/bin/env python3
"""make_bench_package.py — puts the whole benchmark study in one folder and one zip, ready to send.

  python make_bench_package.py            # builds docs/benchmark-package/ and docs/benchmark-package.zip

First rebuilds the report and the speed demo from docs/bench-data/, makes a PDF of the report (with Edge or Chrome, if present), writes the
numbers as CSV and adds the raw measurements, the scripts and a README. No passwords or tokens go into the package.
"""
import csv
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DOCS = ROOT / "docs"
OUT = DOCS / "benchmark-package"
ZIP = DOCS / "benchmark-package.zip"
SCRIPTS = ["make_parallel_note.py", "bench_cyber.py", "model_bench.py", "bench_perf.py", "bench_stream.py", "make_bench_report.py", "make_speed_demo.py", "make_bench_package.py"]
BROWSERS = ["C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe", "C:/Program Files/Microsoft/Edge/Application/msedge.exe",
            "C:/Program Files/Google/Chrome/Application/chrome.exe", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"]
README = """BENCHMARK: WHITERABBITNEO 13B AND 11 OTHER LOCAL MODELS ON A MAC MINI
=======================================================================

What this is
  An evaluation of how well local language models handle security tasks, and how fast they run on an Apple Mac mini (M6, 32 GB, Ollama 0.40.5).
  The question: is WhiteRabbitNeo 13B a good cybersecurity model? Short answer: a competent source of security facts, but not the best choice.
  It fabricates answers about things that do not exist, is slow to answer and uses a lot of memory. Newer models are faster and smaller.

Contents
  1-report.pdf               the report (start here)
  2-speed-demo.gif           models writing the same answer side by side at the real measured timings (not sped up); plays inline in chat apps
  3-speed-demo.html          the same demo to play in a browser (with a half-speed option)
  4-report.html              the report as a web page
  5-memory-with-multiple-agents.pdf   one-page explainer: memory use with 1 agent versus 5 agents
  results-quality.csv       score per model and per category
  results-per-task.csv      score per model per task
  results-speed.csv         load time, reading speed, generation speed and memory per model
  data/                      the raw measurements (JSON), including when each piece of text arrived
  scripts/                   everything needed to repeat the study (Python 3 and Ollama)
  modelfiles/                Ollama Modelfiles for WhiteRabbitNeo 13B

Method
  Quality: 22 tasks in 6 categories (identifying vulnerabilities in code, security knowledge, CTF decoding, writing code, honesty about things that
  do not exist, log analysis). Scored automatically on keywords that a good answer must contain. WhiteRabbitNeo 13B, qwen2.5-coder 14B and
  qwen3.8 27B were run three times with different sampling seeds; the other models once. Run-to-run variation reaches about 0.13, so differences
  smaller than that are noise.
  Speed: the counters Ollama itself reports; median of 3 rounds, model freshly loaded, context 8192, Q4 quantisation. Reading = processing a log of
  about 3,000 tokens; generating = producing 256 tokens.
  deepseek-r1 always thinks aloud before answering; it was given a generous limit of 3,000 tokens instead of 260.

Limitations
  Small (22 tasks), keyword scoring (no human read the answers), English prompts only, one machine, one quantisation.

Reproducing (on a machine with Ollama)
  ollama create wrn13b -f modelfiles/Modelfile.wrn13b
  python3 scripts/model_bench.py --models wrn13b qwen2.5-coder:14b cyber        (quality; BENCH_SEED=1 for another seed)
  python3 scripts/bench_perf.py wrn13b qwen2.5-coder:14b                         (speed and memory)
  python3 scripts/bench_stream.py wrn13b qwen3:8b                                (records answer timing for the demo)
  Put the measurement files in docs/bench-data/ and run make_bench_report.py and make_speed_demo.py for a new report (Pillow is needed for the GIF).

Models and sources
  WhiteRabbitNeo 13B (Llama 2): TheBloke/WhiteRabbitNeo-13B-GGUF, Q4_K_M
  WhiteRabbitNeo 2.5 (Qwen) 7B: bartowski/WhiteRabbitNeo-2.5-Qwen-2.5-Coder-7B-GGUF, Q4_K_M
  WhiteRabbitNeo (Llama 3) 8B: mradermacher/Llama-3-WhiteRabbitNeo-8B-v2.0-GGUF, Q4_K_M
  DeepHat V1 7B: mradermacher/DeepHat-V1-7B-GGUF, Q4_K_M
  Ollama library: deepseek-r1:14b, qwen2.5-coder:14b and :32b, codestral:22b, dolphin-llama3:8b, qwen3:8b, qwen3.8:27b, phi4:14b, gemma3:12b,
  mistral-nemo
  Note: WhiteRabbitNeo is released under the Llama licence plus its own extension with usage restrictions; read the licence before serious use.
"""


def pdf_van(html: Path, pdf: Path) -> bool:
    for b in BROWSERS:
        if Path(b).exists():
            try:
                subprocess.run([b, "--headless", "--disable-gpu", "--no-pdf-header-footer", f"--print-to-pdf={pdf}", html.resolve().as_uri()],
                               capture_output=True, timeout=120)
            except (OSError, subprocess.SubprocessError):
                continue
            if pdf.exists() and pdf.stat().st_size > 5000:
                return True
    return False


def schrijf_csv(pad: Path, kop: list, rijen: list):
    with open(pad, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(kop)
        w.writerows(rijen)


def csvs(out: Path):
    sys.path.insert(0, str(ROOT))
    import make_bench_report as r
    perf, runs = r.laad()
    agg = r.aggregeer(runs)
    cats = [c for c, _ in r.CATS]
    ranking = sorted(agg, key=lambda m: -agg[m]["mean"])
    f2 = lambda x: "" if x is None else f"{x:.2f}"
    schrijf_csv(out / "results-quality.csv", ["model", "score_mean", "score_min", "score_max", "runs", *[l for _, l in r.CATS], "mean_seconds_per_question"],
                [[r.naam(m), f2(agg[m]["mean"]), f2(agg[m]["lo"]), f2(agg[m]["hi"]), agg[m]["n"], *[f2(agg[m]["cats"][c]) for c in cats],
                  f"{agg[m]['avg_s']:.1f}"] for m in ranking])
    schrijf_csv(out / "results-per-task.csv", ["task", *[r.naam(m) for m in ranking]],
                [[omschr, *[f2(agg[m]["cases"].get(k)) for m in ranking]] for k, omschr in r.CASES.items()])
    pm = perf["modellen"]
    schrijf_csv(out / "results-speed.csv", ["model", "cold_load_s", "reading_tok_per_s", "first_token_after_long_prompt_s", "generation_tok_per_s",
                                           "generation_min", "generation_max", "memory_gb"],
                [[r.naam(m), v["laadtijd_s"], v["prompt_tok_s"], v["ttft_lange_prompt_s"], v["gen_tok_s"], v["gen_tok_s_min"], v["gen_tok_s_max"], v["ram_gb"]]
                 for m, v in sorted(pm.items(), key=lambda kv: -kv[1]["gen_tok_s"])])


def main():
    sys.path.insert(0, str(ROOT))
    import make_bench_report
    import make_speed_demo
    import make_parallel_note
    make_parallel_note.main()
    make_bench_report.main()
    make_speed_demo.main()
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "data").mkdir(parents=True)
    (OUT / "scripts").mkdir()
    (OUT / "modelfiles").mkdir()
    html = DOCS / "benchmark-whiterabbitneo-13b.html"
    shutil.copy2(html, OUT / "4-report.html")
    shutil.copy2(DOCS / "speed-demo.html", OUT / "3-speed-demo.html")
    shutil.copy2(DOCS / "speed-demo.gif", OUT / "2-speed-demo.gif")
    heeft_pdf = pdf_van(html, OUT / "1-report.pdf")
    shutil.copy2(DOCS / "ram-with-multiple-agents.pdf", OUT / "5-memory-with-multiple-agents.pdf")
    csvs(OUT)
    for f in (DOCS / "bench-data").glob("*.json"):
        shutil.copy2(f, OUT / "data" / f.name)
    for s in SCRIPTS:
        shutil.copy2(ROOT / s, OUT / "scripts" / s)
    for f in (DOCS / "modelfiles").glob("Modelfile.wrn13b*"):
        shutil.copy2(f, OUT / "modelfiles" / f.name)
    (OUT / "README.txt").write_text(README, encoding="utf-8")
    if ZIP.exists():
        ZIP.unlink()
    with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(OUT.rglob("*")):
            if f.is_file():
                z.write(f, Path("benchmark-whiterabbitneo") / f.relative_to(OUT))
    print(f"package: {OUT} ({sum(1 for _ in OUT.rglob('*') if _.is_file())} files), zip {ZIP.stat().st_size / 1e6:.1f} MB, pdf: {'yes' if heeft_pdf else 'NO'}")


if __name__ == "__main__":
    main()
