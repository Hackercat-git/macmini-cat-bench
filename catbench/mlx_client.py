"""MLX client: wraps mlx_lm.server (OpenAI-compatible API on port 8080).

Drop-in replacement for ollama.Client for the `run` and `perf` commands.
mlx_lm.server does not expose Ollama-style timings, so perf metrics are
measured with wall-clock time and OpenAI usage counters instead.
"""
import json
import os
import time
import urllib.error
import urllib.request

from .ollama import THINK_BLOCK, OllamaError, clean_answer


def normalize_host(host: str = None) -> str:
    h = host or os.environ.get("MLX_HOST") or "http://localhost:8080"
    if "://" not in h:
        h = "http://" + h
    return h.rstrip("/")


class MLXClient:
    """OpenAI-compatible client for mlx_lm.server."""

    def __init__(self, host: str = None, timeout: int = 1800):
        self.host = normalize_host(host)
        self.timeout = timeout

    def _request(self, path: str, body: dict = None, method: str = "POST"):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(
            self.host + path, data=data, method=method,
            headers={"Content-Type": "application/json"},
        )
        return urllib.request.urlopen(req, timeout=self.timeout)

    def _json(self, path: str, body: dict = None, method: str = "POST") -> dict:
        if path == "/api/generate":
            return self._ollama_generate_compat(body or {})
        try:
            with self._request(path, body, method) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            raise OllamaError(f"HTTP {e.code}: {e.read().decode(errors='replace')[:300]}") from e
        except (urllib.error.URLError, OSError) as e:
            raise OllamaError(f"cannot reach mlx_lm.server at {self.host}: {e}") from e

    def _ollama_generate_compat(self, body: dict) -> dict:
        """Translate /api/generate (Ollama) to /v1/completions (OpenAI) for perf.py."""
        opts = body.get("options", {})
        comp_body = {
            "model": body["model"],
            "prompt": body.get("prompt", ""),
            "max_tokens": opts.get("num_predict", 256),
            "temperature": opts.get("temperature", 0.0),
            "seed": opts.get("seed", 7),
            "stream": False,
        }
        t0 = time.time()
        try:
            with self._request("/v1/completions", comp_body) as r:
                d = json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            raise OllamaError(f"HTTP {e.code}: {e.read().decode(errors='replace')[:300]}") from e
        except (urllib.error.URLError, OSError) as e:
            raise OllamaError(f"cannot reach mlx_lm.server at {self.host}: {e}") from e
        elapsed = time.time() - t0
        usage = d.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", 0)
        comp_tokens = usage.get("completion_tokens", 0)
        total = max(prompt_tokens + comp_tokens, 1)
        prompt_frac = prompt_tokens / total
        text = (d.get("choices") or [{}])[0].get("text", "")
        elapsed_ns = int(elapsed * 1e9)
        return {
            "model": body["model"],
            "response": text,
            "load_duration": 0,
            "prompt_eval_count": prompt_tokens,
            "prompt_eval_duration": int(elapsed_ns * prompt_frac),
            "eval_count": comp_tokens,
            "eval_duration": int(elapsed_ns * (1 - prompt_frac)),
        }

    def version(self) -> str:
        try:
            d = self._json("/v1/models", method="GET")
            return "mlx-lm"
        except OllamaError:
            return "mlx-lm"

    def tags(self) -> list:
        """Return models in Ollama tag format."""
        try:
            d = self._json("/v1/models", method="GET")
            return [{"name": m["id"], "model": m["id"], "digest": "", "size": 0, "details": {}}
                    for m in d.get("data", [])]
        except OllamaError:
            return []

    def ps(self) -> list:
        return self.tags()

    def unload(self, model: str):
        pass  # mlx_lm.server manages memory itself

    def chat(self, model: str, user: str, system: str = "", num_predict: int = 300,
             temperature: float = 0.2, seed: int = 7, num_ctx: int = 8192,
             min_predict: int = 0, keep_alive: str = "10m") -> dict:
        msgs = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": user}]
        body = {
            "model": model,
            "messages": msgs,
            "max_tokens": max(num_predict, min_predict),
            "temperature": temperature,
            "seed": seed,
            "stream": False,
        }
        t = time.time()
        d = self._json("/v1/chat/completions", body)
        elapsed = time.time() - t
        choice = (d.get("choices") or [{}])[0]
        raw = choice.get("message", {}).get("content", "")
        text, cut = clean_answer(raw)
        usage = d.get("usage", {})
        comp = usage.get("completion_tokens", 0)
        prompt = usage.get("prompt_tokens", 0)
        stop = choice.get("finish_reason", "")
        return {
            "text": text,
            "secs": round(elapsed, 3),
            "eval_count": comp,
            "eval_s": elapsed,
            "load_s": 0.0,
            "prompt_count": prompt,
            "prompt_s": 0.0,
            "truncated": stop == "length",
            "cut_in_thinking": cut,
            "thought": False,
        }

    def generate_stream(self, model: str, prompt: str, num_predict: int = 220,
                        num_ctx: int = 8192) -> dict:
        """Streaming via OpenAI /v1/completions."""
        body = {
            "model": model,
            "prompt": prompt,
            "max_tokens": num_predict,
            "temperature": 0.0,
            "seed": 7,
            "stream": True,
        }
        t0 = time.perf_counter()
        pieces = []
        total_tokens = 0
        try:
            with self._request("/v1/completions", body) as r:
                for line in r:
                    line = line.strip()
                    if not line or line == b"data: [DONE]":
                        continue
                    if line.startswith(b"data: "):
                        line = line[6:]
                    try:
                        d = json.loads(line)
                    except ValueError:
                        continue
                    text = (d.get("choices") or [{}])[0].get("text", "")
                    if text:
                        pieces.append([round(time.perf_counter() - t0, 3), text])
                    total_tokens += 1
                    if (d.get("choices") or [{}])[0].get("finish_reason"):
                        break
        except (urllib.error.URLError, OSError) as e:
            raise OllamaError(str(e)) from e
        total_s = round(time.perf_counter() - t0, 2)
        n = total_tokens or len(pieces)
        return {
            "pieces": pieces,
            "ttft_s": pieces[0][0] if pieces else None,
            "total_s": total_s,
            "tokens": n,
            "tok_s": round(n / total_s, 1) if total_s else None,
        }
