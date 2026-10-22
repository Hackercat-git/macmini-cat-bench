import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from catbench import cli, runner
from tests.test_runner_report import FakeClient


class CliTests(unittest.TestCase):
    def run_cli(self, *args):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = cli.main(list(args))
        return code, buf.getvalue()

    def test_validate_passes_on_the_shipped_tasks(self):
        code, out = self.run_cli("validate")
        self.assertEqual(code, 0, out)
        self.assertIn("0 problem(s)", out)

    def test_perf_adds_to_earlier_measurements_instead_of_replacing_them(self):
        from unittest import mock
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp) / "r1"
            run.mkdir()
            (run / "perf.json").write_text(json.dumps({"models": {"old-model": {"generation_tok_s": 30}}}), encoding="utf-8")
            fake = {"cold_load_s": 1, "reading_tok_s": 2, "generation_tok_s": 3, "first_token_long_prompt_s": 1, "memory_gb": 4}
            with mock.patch.object(cli.perf, "measure", return_value=fake):
                self.run_cli("perf", "--models", "new-model", "--out", tmp, "--run-id", "r1")
            saved = json.loads((run / "perf.json").read_text(encoding="utf-8"))["models"]
            self.assertEqual(set(saved), {"old-model", "new-model"})

    def test_list_shows_tracks_and_models(self):
        code, out = self.run_cli("list")
        self.assertEqual(code, 0)
        self.assertIn("cybersecurity", out)
        self.assertIn("qwen3:8b", out)

    def test_report_command_builds_a_site(self):
        tmp = Path(tempfile.mkdtemp())
        c = FakeClient()
        runner.run_model(c, "m-good", ["daily"], [1], tmp / "runs" / "r1", log=lambda *a: None)
        runner.write_manifest(tmp / "runs" / "r1", "r1", c, ["m-good"], {})
        code, out = self.run_cli("report", "--run-id", "r1", "--out", str(tmp / "runs"), "--site", str(tmp / "site"))
        self.assertEqual(code, 0, out)
        self.assertTrue((tmp / "site" / "index.html").exists())
        data = json.loads((tmp / "site" / "results.json").read_text(encoding="utf-8"))
        self.assertEqual(data["tracks"], ["daily"])

    def test_default_run_id_names_the_machine(self):
        self.assertEqual(cli.default_run_id({"chip": "Apple M6", "ram_gb": 32}).split("-", 3)[3], "macmini-m6-32gb")

    def test_run_without_server_stops_cleanly(self):
        tmp = Path(tempfile.mkdtemp())
        code, out = self.run_cli("run", "--models", "x", "--tracks", "daily", "--seeds", "1", "--out", str(tmp), "--run-id", "r", "--host", "127.0.0.1:9")
        self.assertEqual(code, 1)
        self.assertIn("stopped", out)


if __name__ == "__main__":
    unittest.main()
