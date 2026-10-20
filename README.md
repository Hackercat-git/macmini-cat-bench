# macmini-cat-bench

**Honest, reproducible AI benchmarks on the Mac mini.**

macmini-cat-bench measures how well local language models perform on a Mac mini, and what they cost to run. Every model is tested on the same
tasks, on the same machine, with the same settings. Every result is published together with the raw answers, the scripts and the hardware and
software versions used, so anyone can repeat a measurement and check it.

Why another benchmark? Most rankings give one headline number, hide the run-to-run noise, and rarely say what hardware they ran on. Here you get a
**profile per use case**, the **range between runs**, the **speed and memory on a real Mac mini**, and the **worst answers** of every model.

## What is measured

Eight tracks, each a set of public tasks with automatic scoring. A model gets one score (0 to 1) per track, not one number overall.

| Track | What it tests | Scoring |
|---|---|---|
| Cybersecurity | Spotting vulnerabilities in code, security knowledge, log analysis, CTF decoding | Keywords, JSON fields, executed code |
| Daily use | Facts, summaries, emails, rewriting, conversions, following format instructions | Keywords, numbers, word and bullet limits |
| Coding | Python functions, a bug fix | The code is run against tests |
| Dutch | Answering in Dutch, translation both ways, grammar, spelling, idioms | Language detection, keywords |
| Tools and JSON | Extracting fields into JSON, choosing a tool, filling a function call | JSON fields compared with the expected values |
| Honesty and safety | Admitting what it does not know, resisting injected instructions, not over-refusing | Admission phrases, forbidden outputs, refusal detection |
| Reasoning and maths | Word problems with one correct answer | The final number |
| Long context | Finding one fact in a document of about 2k, 6k and 12k tokens | Exact match |

Besides quality: **cold load time, prompt processing speed, generation speed, memory use** and behaviour with **several agents at once**.
Energy per answer is supported when the machine allows it (see below).

## Results

<!-- RESULTS -->
See [docs/RESULTS.md](docs/RESULTS.md) and the generated site in [docs/](docs/) (`index.html`, `hairball.html`, `vote.html`). The first complete round is
being filled in; the table appears here when it is done.
<!-- /RESULTS -->

The study that started this repository, a security-focused comparison including WhiteRabbitNeo 13B, is in
[studies/2026-10-whiterabbitneo-13b](studies/2026-10-whiterabbitneo-13b).

## How we keep it honest

- **At least three runs per model** with different sampling seeds, and the range is printed next to every score. Differences smaller than the
  noise are not presented as wins.
- **Prompts, scoring rules and raw answers are public.** Every task ships with an example answer that must pass and one that must fail, and the test
  suite checks both, so the scoring itself is tested.
- **Mistakes are published and corrected, not hidden.** For example, a first run gave a reasoning model a score of 0.19 because the token limit ran out
  before it answered; the fix and the reason are in the study. Answers that were cut off by the token limit are flagged in the results.
- **The Hairball page** shows the worst answers of every model, verbatim.
- **The blind vote** page lets you compare two answers without model names, as a check on what keyword scoring cannot see.
- **No model grades another model.** Scoring is rule-based.
- **Limitations are stated up front** (below).

## Quick start

You need a Mac mini (or any machine), [Ollama](https://ollama.com), and Python 3.11 or newer. There are no Python dependencies.

```bash
git clone https://github.com/Hackercat-git/macmini-cat-bench.git
cd macmini-cat-bench

ollama pull qwen3:8b
python3 -m catbench validate                         # check the task files
python3 -m catbench run --models qwen3:8b --seeds 3  # all tracks, three seeds
python3 -m catbench perf --models qwen3:8b           # speed and memory
python3 -m catbench report --run-id <run-id>         # build the site in docs/
```

Useful options: `--tracks daily coding` to run some tracks, `--limit 3` for a quick check, `--host` for a remote Ollama.
`python3 -m catbench list` shows the tracks and the model list ([models.toml](models.toml)). An interrupted run can be restarted: finished answers are skipped.

Several agents at once, with the server setting described in the note:

```bash
python3 -m catbench parallel --model qwen3:8b --agents 5 --note "OLLAMA_NUM_PARALLEL=5"
```

## Repository layout

```
catbench/       the benchmark (client, scoring, runner, perf, energy, report, CLI)
tasks/          the public tasks, one JSON file per track
models.toml     the model list with source, size and per-model settings
runs/<run>/     raw results: manifest.json (machine, versions), one JSONL file per model and track, perf.json
docs/           the generated site (GitHub Pages) and RESULTS.md
studies/        write-ups of individual studies
tests/          unit tests (python3 -m unittest discover -s tests -t .)
```

## Status

Implemented: the eight tracks (98 tasks), the runner with resume, speed, memory and parallel measurement, the Hairball page, the blind vote, the site
generator, the test suite and CI.

Planned, not done yet:
- A human review of a sample of answers per track, with the error rate of the automatic scoring published.
- A hidden, rotating subset of tasks and rewritten variants of public tasks, to detect models that have seen the test.
- Energy per answer on every machine: it needs `powermetrics`, which needs root. The code is there and only runs when passwordless sudo is allowed for it;
  otherwise energy is reported as not measured. It is never estimated.
- More Mac mini configurations (M-series chips, memory sizes) contributed by others.

## Limitations

- Each track has only 6 to 22 tasks and the scoring is automatic: a good answer phrased differently can lose points. Run-to-run noise is reported;
  differences below it mean nothing.
- One quantisation per model (usually Q4_K_M) and English prompts, except the Dutch track.
- Results depend on the Ollama version and its settings (context window, `OLLAMA_NUM_PARALLEL`, flash attention, KV cache type). They are recorded in each run.
- **The coding track runs model-written Python on your machine** in a separate interpreter with a time limit. It is not a sandbox. If you do not trust the
  models, run the benchmark in a container or a virtual machine.

## Contributing

Results from other Mac minis, new tasks, new models and corrections are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT, see [LICENSE](LICENSE). Model weights keep their own licences; check them before use.
