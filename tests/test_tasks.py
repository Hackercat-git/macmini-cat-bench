import re
import unittest

from catbench import scoring
from catbench.models import load_models
from catbench.tasks import TRACK_LABELS, TRACKS, all_tracks, build_long_prompt, task_prompt


class TaskFileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tracks = all_tracks()

    def test_every_track_has_a_file_and_a_label(self):
        self.assertEqual(set(self.tracks), set(TRACKS))
        self.assertEqual(set(TRACK_LABELS), set(TRACKS))

    def test_ids_are_unique_across_the_whole_suite(self):
        ids = [t["id"] for d in self.tracks.values() for t in d["tasks"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_every_task_is_well_formed(self):
        for track, d in self.tracks.items():
            self.assertTrue(d["description"].strip(), track)
            for t in d["tasks"]:
                self.assertTrue(task_prompt(t).strip(), t["id"])
                self.assertTrue(t["checks"], t["id"])
                for c in t["checks"]:
                    self.assertIn(c["type"], scoring.CHECKS, t["id"])
                self.assertIn("pass", t)
                self.assertIn("fail", t)
                self.assertGreater(int(t.get("num_predict", 0)), 0, t["id"])

    def test_the_scoring_accepts_the_good_example_and_rejects_the_bad_one(self):
        for d in self.tracks.values():
            for t in d["tasks"]:
                good, _ = scoring.score_task(t, t["pass"])
                bad, _ = scoring.score_task(t, t["fail"])
                self.assertGreaterEqual(good, 0.99, f"{t['id']}: passing example scores {good}")
                self.assertLess(bad, 0.99, f"{t['id']}: failing example scores {bad}")

    def test_enough_tasks_per_track(self):
        for track, d in self.tracks.items():
            self.assertGreaterEqual(len(d["tasks"]), 6, track)
        self.assertGreaterEqual(sum(len(d["tasks"]) for d in self.tracks.values()), 90)

    def test_long_context_prompts_have_the_requested_size_and_position(self):
        for t in self.tracks["longcontext"]["tasks"]:
            spec = t["long"]
            p = task_prompt(t)
            self.assertAlmostEqual(len(p), spec["approx_tokens"] * 4, delta=spec["approx_tokens"] * 4 * 0.1, msg=t["id"])
            where = p.index(spec["needle_sentence"]) / len(p)
            self.assertAlmostEqual(where, spec["position"], delta=0.08, msg=t["id"])
            self.assertEqual(p.count(spec["needle_sentence"]), 1)
            self.assertTrue(p.rstrip().endswith(spec["question"]))
            self.assertLessEqual(spec["approx_tokens"] * 1.25, int(t["num_ctx"]))      # room for tokenisers that need more tokens per word

    def test_long_prompts_are_deterministic(self):
        spec = self.tracks["longcontext"]["tasks"][0]["long"]
        self.assertEqual(build_long_prompt(spec), build_long_prompt(spec))

    def test_defaults_are_applied(self):
        for t in self.tracks["daily"]["tasks"]:
            self.assertIn("system", t)


class ModelListTests(unittest.TestCase):
    def test_models_toml(self):
        models = load_models()
        self.assertGreaterEqual(len(models), 15)
        for tag, m in models.items():
            self.assertTrue(m["status"] in ("planned", "wishlist") or re.fullmatch(r"round\d+", m["status"]), (tag, m["status"]))
            self.assertIn(m["tier"], ("small", "mid", "large", "huge"), tag)
            self.assertTrue(m["name"], tag)
        self.assertEqual(models["deepseek-r1:14b"]["predict_min"], 3000)
        self.assertTrue(any(re.fullmatch(r"round\d+", m["status"]) for m in models.values()))


if __name__ == "__main__":
    unittest.main()
