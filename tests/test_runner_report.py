import tempfile
import unittest
from unittest import mock
from pathlib import Path

from catbench import energy, ollama, report, runner
from catbench.ollama import OllamaError
from catbench.tasks import all_tracks


class FakeClient:
    """Answers every task with its own passing example, except for models in `bad`, which get the failing example."""

    def __init__(self, bad=(), truncate=()):
        self.calls, self.bad, self.truncate, self.unloaded = [], set(bad), set(truncate), []
        self.answers = {}
        for d in all_tracks().values():
            for t in d["tasks"]:
                from catbench.tasks import task_prompt
                self.answers[task_prompt(t)] = (t["pass"], t["fail"])

    def chat(self, model, user, system="", num_predict=300, temperature=0.2, seed=7, num_ctx=8192, min_predict=0, keep_alive="10m"):
        self.calls.append((model, seed, min_predict))
        good, bad = self.answers[user]
        return {"text": bad if model in self.bad else good, "secs": 1.5, "eval_count": 20, "eval_s": 1.0, "load_s": 0, "prompt_count": 10, "prompt_s": 0.1,
                "truncated": model in self.truncate, "cut_in_thinking": False, "thought": False}

    def unload(self, model):
        self.unloaded.append(model)

    def tags(self):
        return [{"name": "m-good", "digest": "abcdef0123456789xyz", "size": 5_000_000_000, "details": {"quantization_level": "Q4_K_M"}}]

    def version(self):
        return "0.0-test"


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def test_stores_every_answer_and_skips_what_is_done(self):
        c = FakeClient()
        new = runner.run_model(c, "m-good", ["daily"], [1, 2], self.tmp, log=lambda *a: None)
        self.assertEqual(new["daily"], 24)                                              # 12 tasks x 2 seeds
        recs = runner.read_records(runner.result_path(self.tmp, "m-good", "daily"))
        self.assertEqual(len(recs), 24)
        self.assertTrue(all(r["score"] >= 0.99 for r in recs))
        self.assertEqual({r["seed"] for r in recs}, {1, 2})
        again = runner.run_model(c, "m-good", ["daily"], [1, 2, 3], self.tmp, log=lambda *a: None)
        self.assertEqual(again["daily"], 12)                                            # only the new seed
        self.assertEqual(c.unloaded, ["m-good", "m-good"])

    def test_passes_the_token_floor_for_thinking_models_and_flags_cut_off_answers(self):
        c = FakeClient(truncate=["m-slow"])
        runner.run_model(c, "m-slow", ["honesty"], [1], self.tmp, models_cfg={"m-slow": {"predict_min": 3000}}, log=lambda *a: None, limit=2)
        self.assertTrue(all(call[2] == 3000 for call in c.calls))
        recs = runner.read_records(runner.result_path(self.tmp, "m-slow", "honesty"))
        self.assertTrue(all(r["truncated"] for r in recs))
        self.assertEqual(len(recs), 2)

    def test_model_failure_is_recorded_as_zero_and_the_run_continues(self):
        from catbench.ollama import OllamaError

        class Looping(FakeClient):
            def chat(self, model, user, **kw):
                raise OllamaError('HTTP 500: {"error":"prediction aborted, token repeat limit reached"}')

        with mock.patch.object(runner.time, "sleep"):
            new = runner.run_model(Looping(), "m-loop", ["honesty"], [1], self.tmp, log=lambda *a: None, limit=3)
        self.assertEqual(new["honesty"], 3)
        recs = runner.read_records(runner.result_path(self.tmp, "m-loop", "honesty"))
        self.assertTrue(all(r["score"] == 0 and "repeat limit" in r["error"] for r in recs))

    def test_unreachable_server_still_stops_the_run(self):
        from catbench.ollama import OllamaError

        class Down(FakeClient):
            def chat(self, model, user, **kw):
                raise OllamaError("cannot reach Ollama at localhost:11434")

        with mock.patch.object(runner.time, "sleep"), self.assertRaises(OllamaError):
            runner.run_model(Down(), "m-down", ["honesty"], [1], self.tmp, log=lambda *a: None, limit=1)

    def test_tag_with_special_characters_becomes_a_safe_folder_name(self):
        self.assertEqual(runner.safe("hf.co/QuantFactory/Foundation-Sec-8B-GGUF:Q4_K_M"), "hf.co_QuantFactory_Foundation-Sec-8B-GGUF_Q4_K_M")

    def test_manifest_records_machine_version_and_digests(self):
        m = runner.write_manifest(self.tmp, "test-run", FakeClient(), ["m-good"], {"seeds": 3})
        self.assertEqual(m["ollama"], "0.0-test")
        self.assertEqual(m["models"]["m-good"]["digest"], "abcdef0123456789")
        self.assertEqual(m["settings"]["seeds"], 3)
        again = runner.write_manifest(self.tmp, "test-run", FakeClient(), ["m-good"], {"temperature": 0.2})
        self.assertEqual(again["settings"], {"seeds": 3, "temperature": 0.2})

    def test_corrupt_lines_are_ignored(self):
        p = self.tmp / "x.jsonl"
        p.write_text('{"a": 1}\nnot json\n{"b": 2}\n', encoding="utf-8")
        self.assertEqual(runner.read_records(p), [{"a": 1}, {"b": 2}])


class ReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.run_dir = cls.tmp / "runs" / "test-run"
        c = FakeClient(bad=["m-bad"])
        for model in ("m-good", "m-bad"):
            runner.run_model(c, model, ["honesty", "daily", "reasoning"], [1, 2, 3], cls.run_dir, log=lambda *a: None)
        runner.write_manifest(cls.run_dir, "test-run", c, ["m-good", "m-bad"], {"seeds": 3})
        cls.site = cls.tmp / "site"
        cls.out = report.build(cls.run_dir, cls.site)

    def test_site_files_exist(self):
        for f in ("index.html", "hairball.html", "vote.html", "results.json", "RESULTS.md"):
            self.assertTrue((self.site / f).exists(), f)
        self.assertEqual(self.out["models"], 2)
        self.assertEqual(self.out["tracks"], ["daily", "honesty", "reasoning"])

    def test_aggregation_mean_and_range_over_seeds(self):
        run = report.load_run(self.run_dir)
        agg = report.aggregate(run["data"])
        self.assertAlmostEqual(agg["m-good"]["daily"]["mean"], 1.0)
        self.assertLess(agg["m-bad"]["daily"]["mean"], 0.5)
        self.assertEqual(agg["m-good"]["daily"]["seeds"], 3)
        self.assertEqual((agg["m-good"]["daily"]["lo"], agg["m-good"]["daily"]["hi"]), (1.0, 1.0))
        self.assertEqual(report.noise(agg), 0.0)

    def test_track_average_ignores_missing_tracks(self):
        self.assertEqual(report.track_average({"daily": {"mean": 1.0}}, ["daily", "coding"]), 1.0)
        self.assertEqual(report.track_average({}, ["daily"]), 0.0)

    def test_hairball_shows_the_bad_model_and_not_the_good_one(self):
        run = report.load_run(self.run_dir)
        worst = report.hairball(run["data"])
        self.assertEqual(worst["m-good"], [])
        self.assertEqual(len(worst["m-bad"]), 3)
        self.assertEqual(worst["m-bad"][0]["track"], "honesty")                         # honesty failures come first
        text = (self.site / "hairball.html").read_text(encoding="utf-8")
        self.assertIn("m-bad", text)
        self.assertIn("Nothing to show here", text)

    def test_index_shows_models_tracks_and_limitations(self):
        text = (self.site / "index.html").read_text(encoding="utf-8")
        for needle in ("m-good", "m-bad", "Daily use", "Honesty and safety", "Limitations", "no single winner", "test-run"):
            self.assertIn(needle, text)
        self.assertNotIn("http://", text.replace("http://www.w3.org", ""))             # nothing external

    def test_blind_vote_pairs_hide_names_until_voting_and_differ(self):
        run = report.load_run(self.run_dir)
        pairs = report.vote_pairs(run, all_tracks(), {})
        self.assertTrue(pairs)
        for p in pairs:
            self.assertNotEqual(p["a"]["text"], p["b"]["text"])
            self.assertEqual({p["a"]["model"], p["b"]["model"]}, {"m-good", "m-bad"})
        html = (self.site / "vote.html").read_text(encoding="utf-8")
        self.assertIn("localStorage", html)
        self.assertEqual(html.count("</script>"), 2)

    def test_markdown_summary(self):
        md = (self.site / "RESULTS.md").read_text(encoding="utf-8")
        self.assertIn("| m-good | 1.00 |", md)

    def test_html_in_answers_is_escaped(self):
        d = self.tmp / "evil"
        c = FakeClient()
        evil = list(c.answers)[0]
        c.answers[evil] = ("<script>alert(1)</script>", "<script>alert(1)</script>")
        runner.run_model(c, "m-evil", ["cybersecurity"], [1], d / "r", log=lambda *a: None, limit=1)
        runner.write_manifest(d / "r", "r", c, ["m-evil"], {})
        report.build(d / "r", d / "site")
        text = (d / "site" / "hairball.html").read_text(encoding="utf-8")
        self.assertNotIn("<script>alert(1)</script>", text)
        self.assertIn("&lt;script&gt;", text)


class RadarAndEnergyTests(unittest.TestCase):
    def test_radar_has_a_polygon_per_value_set(self):
        svg = report.radar_svg({"daily": 1.0, "coding": 0.5}, ["daily", "coding", "tools"])
        self.assertIn("<svg", svg)
        self.assertEqual(svg.count("stroke-width=\"2\""), 1)

    def test_parse_powermetrics_output(self):
        text = "CPU Power: 1000 mW\nCombined Power (CPU + GPU + ANE): 12345 mW\nfoo\nCombined Power (CPU + GPU + ANE): 8000 mW\n"
        self.assertEqual(energy.parse_milliwatts(text), [12345.0, 8000.0])
        self.assertEqual(energy.parse_milliwatts("nothing"), [])
        self.assertAlmostEqual(energy.joules([10000, 20000]), 30.0)

    def test_ollama_helpers(self):
        self.assertEqual(ollama.normalize_host("localhost:11500"), "http://localhost:11500")
        self.assertEqual(ollama.normalize_host("http://x:1/"), "http://x:1")
        self.assertEqual(ollama.clean_answer("<think>hmm</think>Answer."), ("Answer.", False))
        self.assertEqual(ollama.clean_answer("<think>still thinking"), ("", True))
        self.assertEqual(ollama.clean_answer(""), ("", False))

    def test_unreachable_server_raises_a_clear_error(self):
        with self.assertRaises(OllamaError):
            ollama.Client("http://127.0.0.1:9", timeout=2).version()


if __name__ == "__main__":
    unittest.main()
