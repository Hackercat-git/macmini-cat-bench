# Contributing

Thank you for helping to keep local-model benchmarks honest. The most useful contributions:

## 1. Results from your Mac mini

1. Install Ollama and Python 3.11 or newer. Close other heavy apps and keep the machine plugged in.
2. Pull the models you want to measure (see [models.toml](models.toml); the `round1` models are the ones to start with).
3. Run, with a run id that names your machine:
   ```bash
   python3 -m catbench run --models <tags> --seeds 3 --run-id 2026-11-02-macmini-m4pro-48gb
   python3 -m catbench perf --models <tags> --run-id 2026-11-02-macmini-m4pro-48gb
   ```
4. Check that the report builds: `python3 -m catbench report --run-id 2026-11-02-macmini-m4pro-48gb --site /tmp/site`.
5. Open a pull request that adds only the folder `runs/<run-id>/`. Do not edit other runs.

The run folder contains `manifest.json` (machine, versions, model digests), the raw answers and `perf.json`. Do not remove or edit answers.
If a model was cut off by the token limit, leave it in: the report flags it.

## 2. New tasks

Tasks are in `tasks/<track>.json`. A task needs an `id`, a `prompt`, a list of `checks` (see `catbench/scoring.py` for the check types), an example
answer in `pass` that scores 1 and an example in `fail` that does not. Run `python3 -m catbench validate`; the same check runs in CI.
Prefer tasks with an answer that can be scored without judgement. Do not add tasks that depend on facts that change.

## 3. New models

Add an entry to `models.toml` with the exact `tag`, the source, the download size and the status. Models that think before answering need
`predict_min = 3000` (or more), otherwise they score near zero for the wrong reason. Say in the pull request where the weights come from.

## 4. Corrections

If you find a scoring rule that marks a good answer wrong (or a wrong answer right), open an issue with the task id, the answer and what you expected.
Corrections are published, not hidden; we will say what changed and re-score the affected runs.

## Ground rules

- Be honest about what you measured, and on what. Report the machine, the macOS and Ollama versions, and any non-default setting.
- No cherry-picking: if you re-run, keep the first complete run unless there was a documented fault.
- Keep scripts free of external dependencies and secrets.
- Run the tests before a pull request: `python3 -m unittest discover -s tests -t .`
