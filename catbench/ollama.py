"""Minimal Ollama HTTP client (standard library only)."""
import json
import os
import re
import time
import urllib.error
import urllib.request

THINK_BLOCK = re.compile(r"<think>.*?</think>", re.S)


class OllamaError(RuntimeError):
    pass


def normalize_host(host: str = None) -> str:
    h = host or os.environ.get("OLLAMA_HOST") or "http://localhost:11434"
    if "://" not in h:
        h = "http://" + h
    return h.rstrip("/")


def clean_answer(text: str) -> tuple:
    """Removes reasoning blocks from an answer. Returns (answer, cut_off_inside_thinking)."""
    text = THINK_BLOCK.sub("", text or "")
    if "<think>" in text:                                   # the limit ran out while the model was still thinking
        return text.split("<think>")[0].strip(), True
    return text.strip(), False


class Client:
    def __init__(self, host: str = None, timeout: int = 1800):
        self.host = normalize_host(host)
        self.timeout = timeout

    def _request(self, path: str, body: dict = None, method: str = "POST"):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.host + path, data=data, method=method, headers={"Content-Type": "application/json"})
        return urllib.request.urlopen(req, timeout=self.timeout)

    def _json(self, path: str, body: dict = None, method: str = "POST") -> dict:
        try:
            with self._request(path, body, method) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            raise OllamaError(f"HTTP {e.code}: {e.read().decode(errors='replace')[:300]}") from e
        except (urllib.error.URLError, OSError) as e:
            raise OllamaError(f"cannot reach Ollama at {self.host}: {e}") from e

    def version(self) -> str:
        return self._json("/api/version", method="GET").get("version", "?")

    def tags(self) -> list:
        return self._json("/api/tags", method="GET").get("models", [])

    def ps(self) -> list:
        return self._json("/api/ps", method="GET").get("models", [])

    def unload(self, model: str):
        try:
            self._json("/api/generate", {"model": model, "keep_alive": 0})
        except OllamaError:
            pass
        time.sleep(2)

    def chat(self, model: str, user: str, system: str = "", num_predict: int = 300, temperature: float = 0.2, seed: int = 7,
             num_ctx: int = 8192, min_predict: int = 0, keep_alive: str = "10m") -> dict:
        """One chat turn. Returns text, timings and flags. `min_predict` raises the token limit for models that think first."""
        msgs = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": user}]
        body = {"model": model, "messages": msgs, "stream": False, "think": False, "keep_alive": keep_alive,
                "options": {"num_ctx": num_ctx, "num_predict": max(num_predict, min_predict), "temperature": temperature, "seed": seed}}
        t = time.time()
        try:
            d = self._json("/api/chat", body)
        except OllamaError as e:
            if "think" in str(e).lower():                    # the model does not know the thinking switch
                body.pop("think")
                d = self._json("/api/chat", body)
            else:
                raise
        text, cut = clean_answer(d.get("message", {}).get("content", ""))
        return {"text": text, "secs": round(time.time() - t, 3), "eval_count": d.get("eval_count", 0),
                "eval_s": (d.get("eval_duration") or 0) / 1e9, "load_s": (d.get("load_duration") or 0) / 1e9,
                "prompt_count": d.get("prompt_eval_count", 0), "prompt_s": (d.get("prompt_eval_duration") or 0) / 1e9,
                "truncated": d.get("done_reason") == "length", "cut_in_thinking": cut,
                "thought": bool(d.get("message", {}).get("thinking"))}

    def generate_stream(self, model: str, prompt: str, num_predict: int = 220, num_ctx: int = 8192) -> dict:
        """Streams a completion and records when each piece arrived (seconds since sending)."""
        body = {"model": model, "prompt": prompt, "stream": True, "think": False, "keep_alive": "10m",
                "options": {"num_ctx": num_ctx, "num_predict": num_predict, "temperature": 0.0, "seed": 7}}
        t0 = time.perf_counter()
        pieces, final = [], {}
        try:
            with self._request("/api/generate", body) as r:
                for line in r:
                    line = line.strip()
                    if not line:
                        continue
                    d = json.loads(line)
                    if d.get("done"):
                        final = d
                        break
                    if d.get("response"):
                        pieces.append([round(time.perf_counter() - t0, 3), d["response"]])
        except (urllib.error.URLError, OSError) as e:
            raise OllamaError(str(e)) from e
        n = final.get("eval_count") or len(pieces)
        gen_s = (final.get("eval_duration") or 0) / 1e9
        return {"pieces": pieces, "ttft_s": pieces[0][0] if pieces else None, "total_s": round(time.perf_counter() - t0, 2),
                "tokens": n, "tok_s": round(n / gen_s, 1) if gen_s else None}
