NOTE: this is the study that started the macmini-cat-bench repository. It is kept as it was published, with its own scripts, so that it can be
reproduced. The maintained benchmark is the `catbench` package in the repository root (more tracks, resume, reports).
Download the model file first and place it next to the Modelfile (FROM ./whiterabbitneo-13b.Q4_K_M.gguf).

BENCHMARK: WHITERABBITNEO 13B AND 11 OTHER LOCAL MODELS ON A MAC MINI
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
