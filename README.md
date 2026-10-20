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

Mac mini (Apple M6, 32 GB), Ollama 0.40.5, 2026-10-20.

| Model | Track average | Cybersecurity | Daily use | Coding | Dutch | Tools and JSON | Honesty and safety | Reasoning and maths | Long context |
|---|---|---|---|---|---|---|---|---|---|
| gemma4 12B | 0.97 | 0.95 (0.95–0.95) | 1.00 (1.00–1.00) | 0.94 (0.94–0.94) | 0.96 (0.96–0.96) | 1.00 (1.00–1.00) | 0.92 (0.92–0.92) | 1.00 (1.00–1.00) | 1.00 (1.00–1.00) |
| qwen3.8 27B | 0.95 | 0.94 (0.94–0.95) | 0.92 (0.92–0.92) | 1.00 (1.00–1.00) | 0.92 (0.92–0.92) | 0.89 (0.83–0.92) | 1.00 (1.00–1.00) | 0.97 (0.92–1.00) | 1.00 (1.00–1.00) |
| qwen3.5 9B | 0.94 | 0.95 (0.93–0.95) | 0.92 (0.92–0.92) | 1.00 (1.00–1.00) | 0.79 (0.79–0.79) | 1.00 (1.00–1.00) | 0.85 (0.79–0.92) | 1.00 (1.00–1.00) | 1.00 (1.00–1.00) |
| gpt-oss 20B | 0.94 | 0.89 (0.87–0.91) | 0.99 (0.99–0.99) | 1.00 (1.00–1.00) | 0.90 (0.85–0.92) | 1.00 (1.00–1.00) | 0.72 (0.58–0.83) | 1.00 (1.00–1.00) | 1.00 (1.00–1.00) |
| phi4 14B | 0.93 | 0.85 (0.84–0.86) | 0.99 (0.96–1.00) | 1.00 (1.00–1.00) | 0.95 (0.93–0.96) | 1.00 (1.00–1.00) | 0.75 (0.75–0.75) | 0.92 (0.92–0.92) | 1.00 (1.00–1.00) |
| qwen2.5-coder 14B | 0.93 | 0.84 (0.80–0.87) | 0.98 (0.96–1.00) | 1.00 (1.00–1.00) | 0.86 (0.85–0.88) | 1.00 (1.00–1.00) | 0.78 (0.67–0.83) | 0.94 (0.92–1.00) | 1.00 (1.00–1.00) |
| Llama 3.1 8B | 0.92 | 0.76 (0.75–0.77) | 0.94 (0.92–0.96) | 0.93 (0.85–1.00) | 0.87 (0.85–0.88) | 0.97 (0.97–0.97) | 0.92 (0.92–0.92) | 1.00 (1.00–1.00) | 1.00 (1.00–1.00) |
| gemma3 12B | 0.91 | 0.80 (0.79–0.81) | 0.92 (0.92–0.92) | 1.00 (1.00–1.00) | 0.83 (0.83–0.83) | 1.00 (1.00–1.00) | 0.75 (0.75–0.75) | 1.00 (1.00–1.00) | 1.00 (1.00–1.00) |
| granite4 | 0.91 | 0.76 (0.73–0.78) | 0.97 (0.92–1.00) | 0.90 (0.85–0.93) | 0.88 (0.88–0.88) | 1.00 (1.00–1.00) | 0.75 (0.75–0.75) | 1.00 (1.00–1.00) | 1.00 (1.00–1.00) |
| qwen3 8B | 0.91 | 0.84 (0.83–0.85) | 0.88 (0.88–0.88) | 0.95 (0.95–0.95) | 0.89 (0.88–0.92) | 1.00 (1.00–1.00) | 0.69 (0.67–0.75) | 1.00 (1.00–1.00) | 1.00 (1.00–1.00) |
| WhiteRabbitNeo 2.5 (Qwen) 7B | 0.89 | 0.84 (0.81–0.87) | 0.96 (0.96–0.96) | 1.00 (0.99–1.00) | 0.78 (0.75–0.83) | 1.00 (1.00–1.00) | 0.61 (0.50–0.67) | 0.89 (0.83–1.00) | 1.00 (1.00–1.00) |
| DeepHat V1 7B | 0.88 | 0.78 (0.73–0.81) | 0.92 (0.92–0.92) | 0.98 (0.95–1.00) | 0.87 (0.85–0.89) | 1.00 (1.00–1.00) | 0.50 (0.38–0.67) | 1.00 (1.00–1.00) | 1.00 (1.00–1.00) |
| deepseek-r1 14B | 0.88 | 0.74 (0.70–0.80) | 0.89 (0.88–0.92) | 0.88 (0.85–0.90) | 0.87 (0.75–0.94) | 1.00 (1.00–1.00) | 0.64 (0.58–0.75) | 1.00 (1.00–1.00) | 1.00 (1.00–1.00) |
| codestral 22B | 0.85 | 0.84 (0.81–0.88) | 0.88 (0.88–0.88) | 0.92 (0.90–0.95) | 0.79 (0.75–0.82) | 1.00 (1.00–1.00) | 0.72 (0.67–0.75) | 0.69 (0.67–0.75) | 1.00 (1.00–1.00) |
| gemma3 4B | 0.85 | 0.66 (0.66–0.67) | 0.74 (0.74–0.74) | 0.87 (0.82–0.95) | 0.92 (0.92–0.92) | 1.00 (1.00–1.00) | 0.58 (0.58–0.58) | 1.00 (1.00–1.00) | 1.00 (1.00–1.00) |
| WhiteRabbitNeo 13B (Llama 2) | 0.71 | 0.78 (0.70–0.84) | 0.47 (0.31–0.64) | 0.89 (0.83–0.95) | 0.84 (0.82–0.85) | 0.86 (0.75–0.92) | 0.56 (0.50–0.58) | 0.31 (0.17–0.42) | 1.00 (1.00–1.00) |
| WhiteRabbitNeo (Llama 3) 8B | 0.69 | 0.78 (0.70–0.82) | 0.64 (0.60–0.71) | 0.79 (0.72–0.89) | 0.84 (0.78–0.93) | 0.68 (0.62–0.72) | 0.50 (0.42–0.58) | 0.58 (0.58–0.58) | 0.72 (0.50–0.83) |
| Foundation-Sec 8B | 0.28 | 0.49 (0.45–0.58) | 0.38 (0.29–0.47) | 0.12 (0.07–0.20) | 0.50 (0.44–0.54) | 0.00 (0.00–0.00) | 0.50 (0.42–0.58) | 0.11 (0.00–0.33) | 0.11 (0.00–0.33) |

Run-to-run noise in this run reaches 0.33; smaller differences are not meaningful.

### Speed and memory (single request)

| Model | Load (s) | Reading (tok/s) | Writing (tok/s) | Memory (GB) |
|---|---|---|---|---|
| `qwen3:8b` | 0.8 | 647.1 | 28.3 | 5.24 |
| `hf.co/mradermacher/DeepHat-V1-7B-GGUF:Q4_K_M` | 0.5 | 686.5 | 32.1 | 4.48 |
| `llama3.1:8b` | 2.1 | 605.3 | 30.3 | 5.45 |
| `qwen3.5:9b` | 1.7 | 908.6 | 36.0 | 7.74 |
| `gemma4:12b` | 1.7 | 568.6 | 34.7 | 7.75 |
| `qwen2.5-coder:14b` | 3.1 | 313.1 | 16.6 | 9.67 |
| `hf.co/QuantFactory/Foundation-Sec-8B-GGUF:Q4_K_M` | 1.8 | 606.3 | 30.8 | 5.02 |
| `qwen3.8:27b` | 6.4 | 172.8 | 15.6 | 16.46 |
| `phi4:14b` | 2.8 | 331.8 | 16.5 | 9.55 |
| `gemma3:12b` | 3.3 | 481.6 | 19.2 | 7.22 |
| `gpt-oss:20b` | 4.9 | 1088.7 | 39.3 | 12.85 |
| `deepseek-r1:14b` | 3.1 | 333.8 | 16.4 | 9.03 |
| `codestral:22b` | 4.3 | 219.8 | 11.3 | 13.77 |
| `granite4` | 0.8 | 1513.1 | 61.7 | n/a |
| `gemma3:4b` | 1.1 | 1612.9 | 51.4 | 2.38 |
| `wrn13b` | 2.8 | 343.0 | 18.2 | n/a |
| `hf.co/mradermacher/Llama-3-WhiteRabbitNeo-8B-v2.0-GGUF:Q4_K_M` | 1.8 | 609.1 | 30.2 | 5.45 |
| `hf.co/bartowski/WhiteRabbitNeo-2.5-Qwen-2.5-Coder-7B-GGUF:Q4_K_M` | 1.6 | 692.1 | 32.2 | 4.93 |

### Reading these results honestly

- **Foundation-Sec 8B scores 0.28 because of how this GGUF is packaged, not necessarily the model.** The community GGUF has no chat template in Ollama:
  its answers leak `<|im_start|>` tokens and loop. Treat it as "as shipped through Ollama".
- **The WhiteRabbitNeo models are the weakest on general tracks** (0.69 to 0.89) but not on cybersecurity (0.78 to 0.84, about the level of general 8B to 14B models).
  They are tuned for offensive security and lose ground on reasoning, honesty and safety.
- **Several tracks are at the ceiling (1.00 for most models).** Long context, tools and reasoning do not separate the stronger models yet; a harder round is planned.
- **Thinking models** (gpt-oss, deepseek-r1) run with a token floor of 3000, otherwise they score near zero for the wrong reason.
- **Parallel agents:** with the default server setting only one request runs at a time (5 agents: 28.7 tok/s in total, 5.7 each, memory unchanged).
  The `OLLAMA_NUM_PARALLEL=5` comparison is planned.
- "n/a" memory: the model was not listed by `ollama ps` under the requested name at measurement time.
- Three seeds per task at temperature 0.2; ranges are min–max over seeds. Differences below the stated noise are not meaningful.
- Full data, raw answers and the blind vote: see the [site](docs/index.html) and `runs/2026-10-20-macmini-m6-32gb/`.

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
