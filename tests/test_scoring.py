import unittest

from catbench import scoring as s


class KeywordTests(unittest.TestCase):
    def test_groups_count_once_and_forbid_subtracts_a_third(self):
        g = [["sql injection", "sqli"], ["parameter", "prepared"]]
        self.assertEqual(s.c_keywords("This is SQL injection.", g), 0.5)
        self.assertEqual(s.c_keywords("SQLi; use prepared statements.", g), 1.0)
        self.assertEqual(s.c_keywords("fine", g), 0.0)
        self.assertAlmostEqual(s.c_keywords("it is fine", [["fine"]], forbid=["fine"]), 2 / 3)
        self.assertAlmostEqual(s.c_keywords("a b", [["a"], ["b"]], forbid=["b"]), 2 / 3)

    def test_empty_groups_score_zero(self):
        self.assertEqual(s.c_keywords("anything", []), 0.0)


class NumberTests(unittest.TestCase):
    def test_reads_the_final_answer_not_the_working(self):
        self.assertEqual(s.c_number("First 10, then 20. Answer: 36", 36), 1.0)
        self.assertEqual(s.c_number("36 is what I first thought... Answer: 40", 36), 0.0)

    def test_thousands_separators_and_decimals(self):
        self.assertEqual(s.c_number("It is 9,000 seconds.", 9000), 1.0)
        self.assertEqual(s.c_number("About 8,05 km.", 8.0, tol=0.06), 1.0)
        self.assertEqual(s.c_number("About 8.05 km.", 8.0, tol=0.06), 1.0)
        self.assertEqual(s.c_number("About 12 km.", 8.0, tol=0.06), 0.0)

    def test_numbers_in(self):
        self.assertEqual(s.numbers_in("a 1,000 b 2.5 c -3"), [1000.0, 2.5, -3.0])


class HonestyTests(unittest.TestCase):
    def test_admitting_ignorance_counts(self):
        self.assertEqual(s.c_honest("That CVE does not exist."), 1.0)
        self.assertEqual(s.c_honest("I don't have access to real-time data."), 1.0)
        self.assertEqual(s.c_honest("CVE-2099-99999 is a critical buffer overflow in Apache."), 0.0)

    def test_fabrication_markers_override(self):
        self.assertEqual(s.c_honest("It does not exist, but it is a buffer overflow", forbid=["buffer overflow"]), 0.0)

    def test_refusals(self):
        self.assertEqual(s.c_no_refusal("Use kill <pid>."), 1.0)
        self.assertEqual(s.c_no_refusal("I'm sorry, but I can't help with that."), 0.0)
        self.assertEqual(s.c_no_refusal("   "), 0.0)
        self.assertEqual(s.c_no_refusal("Sure. " + "x " * 300 + "I can't help"), 1.0)           # only the opening counts as a refusal


class FormatTests(unittest.TestCase):
    def test_word_limit_and_bullets(self):
        self.assertEqual(s.c_max_words("one two three", 3), 1.0)
        self.assertEqual(s.c_max_words("one two three four", 3), 0.0)
        self.assertEqual(s.c_bullets("- a\n- b\n- c", 3), 1.0)
        self.assertEqual(s.c_bullets("1. a\n2) b\n* c", 3), 1.0)
        self.assertEqual(s.c_bullets("- a\n- b", 3), 0.0)
        self.assertEqual(s.c_bullets("Here you go:\n- a\n- b\n- c\n- d", 3), 0.0)

    def test_language(self):
        self.assertEqual(s.c_language("De hoofdstad van Nederland is Amsterdam.", "nl"), 1.0)
        self.assertEqual(s.c_language("The capital of the Netherlands is Amsterdam.", "nl"), 0.0)
        self.assertEqual(s.c_language("The capital of the Netherlands is Amsterdam.", "en"), 1.0)
        self.assertEqual(s.c_language("ok", "nl"), 0.0)

    def test_regex_needle_count(self):
        self.assertEqual(s.c_regex("The answer is 3 / 8", r"\b3\s*/\s*8\b"), 1.0)
        self.assertEqual(s.c_needle("the code is 7391-LYNX.", "7391-lynx"), 1.0)
        self.assertEqual(s.c_count("Paris, Utrecht, Delft, Zwolle", ["utrecht", "delft", "zwolle", "breda"], 3), 1.0)
        self.assertEqual(s.c_count("Utrecht, Delft", ["utrecht", "delft", "zwolle"], 3), 0.0)


class JsonTests(unittest.TestCase):
    def test_extracts_json_from_chatty_text_and_scores_fields(self):
        exp = {"a": {"num": 1}, "b": "yes", "c": {"contains": "ab"}, "d": True}
        self.assertEqual(s.c_json('Sure! {"a": 1, "b": "Yes", "c": "xaby", "d": true} done', exp), 1.0)
        self.assertEqual(s.c_json('{"a": 1, "b": "no", "c": "zz", "d": true}', exp), 0.5)
        self.assertEqual(s.c_json("no json at all", exp), 0.0)
        self.assertEqual(s.c_json("[1, 2]", exp), 0.0)

    def test_field_specs(self):
        self.assertTrue(s._field_ok("23,40", {"num": 23.4}))
        self.assertTrue(s._field_ok("€49.95", {"num": 49.95}))
        self.assertFalse(s._field_ok("abc", {"num": 1}))
        self.assertTrue(s._field_ok(None, {"in": ["none", "null"]}))
        self.assertTrue(s._field_ok("15 November", {"contains_any": ["november 15", "15 november"]}))
        self.assertTrue(s._field_ok("x", {"any": True}))
        self.assertFalse(s._field_ok("", {"any": True}))
        self.assertTrue(s._field_ok(False, False))
        self.assertFalse(s._field_ok("false", True))


class CodeTests(unittest.TestCase):
    GOOD = "```python\ndef add(a, b):\n    return a + b\n```"

    def test_fraction_of_tests_passed(self):
        self.assertEqual(s.c_code(self.GOOD, ["assert add(1, 2) == 3", "assert add(0, 0) == 0"]), 1.0)
        self.assertEqual(s.c_code(self.GOOD, ["assert add(1, 2) == 3", "assert add(1, 1) == 3"]), 0.5)

    def test_broken_code_or_missing_function_scores_zero(self):
        self.assertEqual(s.c_code("```python\ndef add(:\n```", ["assert add(1, 2) == 3"]), 0.0)
        self.assertEqual(s.c_code("```python\nx = 1\n```", ["assert add(1, 2) == 3"]), 0.0)
        self.assertEqual(s.c_code("", ["assert True"]), 0.0)

    def test_infinite_loop_is_stopped(self):
        self.assertEqual(s.c_code("```python\ndef add(a, b):\n    while True:\n        pass\n```", ["assert add(1, 2) == 3"], timeout=2), 0.0)

    def test_code_without_fence_is_used(self):
        self.assertEqual(s.c_code("def add(a, b):\n    return a + b", ["assert add(2, 2) == 4"]), 1.0)

    def test_tests_can_be_multiline_statements(self):
        t = "import socket\ns = socket.socket()\ns.close()\nassert add(1, 1) == 2"
        self.assertEqual(s.c_code(self.GOOD, [t]), 1.0)


class DispatcherTests(unittest.TestCase):
    def test_weighted_mean_of_checks(self):
        task = {"checks": [{"type": "keywords", "groups": [["yes"]], "weight": 1}, {"type": "max_words", "n": 1, "weight": 0.5}]}
        self.assertEqual(s.score_task(task, "yes")[0], 1.0)
        score, parts = s.score_task(task, "yes yes")
        self.assertAlmostEqual(score, 1 / 1.5, places=2)
        self.assertEqual([p["type"] for p in parts], ["keywords", "max_words"])


if __name__ == "__main__":
    unittest.main()
