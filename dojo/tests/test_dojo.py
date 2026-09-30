import copy
import datetime as dt
import io
import json
import os
import random
import re
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import dojo


ROOT = Path(__file__).resolve().parents[1]


class TerminalCapture(io.StringIO):
    def __init__(self, encoding="utf-8", tty=False):
        super().__init__()
        self._encoding = encoding
        self._tty = tty

    @property
    def encoding(self):
        return self._encoding

    def isatty(self):
        return self._tty


def regex_example(pattern):
    sample = pattern[1:] if pattern.startswith("^") else pattern
    sample = sample[:-1] if sample.endswith("$") else sample
    sample = sample.replace("['\"]", "'")
    return re.sub(r"\\(.)", r"\1", sample)


class GradingTests(unittest.TestCase):
    def test_exact_normalization_and_keyword_grading(self):
        item = {
            "answers": ['devin -p "prompt"'],
            "keywords": ["devin -p"],
        }
        self.assertTrue(dojo.grade_answer(item, '  DEVIN   -P "PROMPT" '))
        self.assertTrue(dojo.grade_answer(item, "Use devin -p here"))
        self.assertFalse(dojo.grade_answer(item, "devin -c"))

    def test_keyword_set_requires_all_keywords(self):
        item = {"answers": ["full answer"], "keywords": ["config.local.json", "gitignored"]}
        self.assertTrue(dojo.grade_answer(item, "config.local.json is gitignored"))
        self.assertFalse(dojo.grade_answer(item, "config.local.json"))

    def test_multiple_choice_letter_and_choice_text(self):
        item = {"answers": ["accept-edits"], "keywords": ["accept-edits"]}
        choices = ["auto", "accept-edits", "smart", "dangerous"]
        self.assertTrue(dojo.grade_answer(item, "b", choices))
        self.assertTrue(dojo.grade_answer(item, "accept-edits", choices))
        self.assertFalse(dojo.grade_answer(item, "a", choices))


class LeitnerTests(unittest.TestCase):
    def test_transitions_and_due_dates_with_injected_clock(self):
        now = dt.datetime(2026, 1, 2, 12, tzinfo=dt.timezone.utc)
        state = {"items": {}}
        progress = dojo.review_item(state, "one", True, now)
        self.assertEqual(progress["box"], 2)
        self.assertEqual(dojo.parse_time(progress["due"]), now + dt.timedelta(days=1))
        dojo.review_item(state, "one", False, now)
        self.assertEqual(progress["box"], 1)
        self.assertEqual(dojo.parse_time(progress["due"]), now)
        for _ in range(5):
            dojo.review_item(state, "one", True, now)
        self.assertEqual(progress["box"], 5)
        self.assertEqual(dojo.parse_time(progress["due"]), now + dt.timedelta(days=21))
        self.assertEqual(progress["seen"], 7)
        self.assertEqual(progress["correct"], 6)


class SelectionTests(unittest.TestCase):
    def test_due_first_new_cap_and_seed_determinism(self):
        now = dt.datetime(2026, 1, 2, tzinfo=dt.timezone.utc)
        items = [{"id": "due"}, {"id": "known"}, {"id": "new-a"}, {"id": "new-b"}]
        state = {
            "items": {
                "due": {"box": 4, "due": (now - dt.timedelta(days=3)).isoformat()},
                "known": {"box": 1, "due": (now + dt.timedelta(days=1)).isoformat()},
            }
        }
        self.assertEqual(
            dojo.select_item(items, state, set(), random.Random(10), now)["id"],
            "due",
        )
        cap_state = {
            "items": {
                "known": {"box": 1, "due": (now + dt.timedelta(days=1)).isoformat()},
            }
        }
        capped = {"one", "two", "three", "four", "five"}
        self.assertEqual(
            dojo.select_item(items, cap_state, capped, random.Random(10), now)["id"],
            "known",
        )
        self.assertEqual(
            dojo.select_item(
                items,
                cap_state,
                capped,
                random.Random(10),
                now,
                played={"due", "new-a", "new-b"},
            )["id"],
            "known",
        )
        first = dojo.select_item(items[2:], {}, set(), random.Random(9), now)["id"]
        second = dojo.select_item(items[2:], {}, set(), random.Random(9), now)["id"]
        self.assertEqual(first, second)


class FlashSessionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name)
        self.items = [
            {
                "id": "flash-%d" % index,
                "topic": "debug",
                "q": "Question %d" % index,
                "answers": ["correct"],
                "keywords": ["correct"],
                "hint": "hint",
                "explain": "Explanation.",
            }
            for index in range(7)
        ]
        now = dt.datetime.now().astimezone()
        state = {
            "items": {
                item["id"]: {
                    "box": 1,
                    "due": (now + dt.timedelta(days=1)).isoformat(),
                }
                for item in self.items
            }
        }
        self.game = dojo.Dojo(self.home, {
            "flash": self.items,
            "drill": [],
            "combo": [],
        })
        self.game.state = state
        self.game.begin_session(seed=4)

    def tearDown(self):
        self.temp.cleanup()

    def test_wrong_flash_item_requeues_once_after_other_items(self):
        served = []
        responses = iter(["wrong", "n"] * 13)
        with patch("builtins.input", side_effect=responses), redirect_stdout(io.StringIO()):
            for _ in range(13):
                item = self.game.choose_item("flash", self.items)
                self.assertIsNotNone(item)
                served.append(item["id"])
                self.game.new_seen.add(item["id"])
                self.assertFalse(self.game.play_flash(item))
        counts = {item_id: served.count(item_id) for item_id in set(served)}
        self.assertLessEqual(max(counts.values()), 2)
        self.assertTrue(all(first != second for first, second in zip(served, served[1:])))

    def test_skip_reveals_answer_without_self_grade_prompt(self):
        item = {
            "id": "skip-card",
            "topic": "debug",
            "q": "Question",
            "answers": ["the answer"],
            "keywords": ["answer"],
            "hint": "hint",
            "explain": "The explanation.",
        }
        output = io.StringIO()
        with patch("builtins.input", return_value="skip") as mocked_input:
            with redirect_stdout(output):
                self.assertFalse(self.game.play_flash(item))
        self.assertEqual(mocked_input.call_count, 1)
        self.assertIn("answer  the answer", output.getvalue())
        self.assertIn("The explanation.", output.getvalue())
        self.assertNotIn("Count it?", output.getvalue())

    def test_missed_reveal_suppresses_duplicate_explanation(self):
        item = {
            "id": "duplicate-reveal",
            "topic": "debug",
            "q": "Question",
            "answers": ["same text"],
            "keywords": ["same"],
            "hint": "hint",
            "explain": "same text",
        }
        output = io.StringIO()
        with patch("builtins.input", return_value="skip"):
            with redirect_stdout(output):
                self.assertFalse(self.game.play_flash(item))
        self.assertEqual(output.getvalue().count("same text"), 1)


class SummaryTests(unittest.TestCase):
    def test_weakest_topics_only_lists_incomplete_topics(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            game = dojo.Dojo(home, dojo.load_content(home))
            game.topic_totals = {
                "perfect": [2, 2],
                "weak": [0, 1],
                "partial": [1, 2],
            }
            output = io.StringIO()
            with redirect_stdout(output):
                game.print_summary()
            summary = output.getvalue()
            self.assertIn("weakest topics  weak, partial", summary)
            self.assertNotIn("perfect", summary.split("weakest topics", 1)[1])

            game.topic_totals = {"perfect": [1, 1]}
            output = io.StringIO()
            with redirect_stdout(output):
                game.print_summary()
            self.assertIn("weakest topics  none", output.getvalue())

    def test_missed_summary_deduplicates_and_suppresses_duplicate_explanation(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            game = dojo.Dojo(home, dojo.load_content(home))
            item = {
                "id": "duplicate-summary",
                "topic": "debug",
                "q": "Question",
                "answers": ["same text"],
                "keywords": ["same"],
                "hint": "hint",
                "explain": "same text",
            }
            game.session_missed = [item, dict(item)]
            output = io.StringIO()
            with redirect_stdout(output):
                game.print_summary()
        summary = output.getvalue()
        self.assertEqual(summary.count("Question"), 1)
        self.assertEqual(summary.count("same text"), 1)


class ScenarioTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name)
        self.content = dojo.load_content(self.home)
        self.game = dojo.Dojo(self.home, self.content)

    def tearDown(self):
        self.temp.cleanup()

    def test_matching_unknown_turn_cost_and_repeat_evidence(self):
        scenario = next(item for item in self.content["combo"] if item["id"] == "s1-hooks-wrapper")
        engine = {
            "turns_used": 0,
            "run_ids": set(),
            "evidence_ids": set(),
            "evidence_streak": 0,
            "best_combo": 1,
        }
        output, evidence = self.game.run_combo_command(
            scenario, "cat .devin/hooks.v1.json", engine
        )
        self.assertIn('"hooks"', output)
        self.assertTrue(evidence)
        output, evidence = self.game.run_combo_command(
            scenario, "cat .devin/hooks.v1.json", engine
        )
        self.assertFalse(evidence)
        self.assertIn("hooks", output)
        output, evidence = self.game.run_combo_command(scenario, "nonsense", engine)
        self.assertEqual(output, "bash: nonsense: command not found")
        self.assertFalse(evidence)
        self.assertEqual(engine["turns_used"], 3)
        self.assertEqual(len(engine["evidence_ids"]), 1)

    def test_combo_build_reset_and_cap(self):
        scenario = next(item for item in self.content["combo"] if item["id"] == "s2-path-alias")
        engine = {
            "turns_used": 0,
            "run_ids": set(),
            "evidence_ids": set(),
            "evidence_streak": 0,
            "best_combo": 1,
        }
        for command in (
            "type node",
            "bash -lic 'echo $PATH'",
            "grep node ~/.bashrc",
            "bash -lic 'command -v node'",
        ):
            self.game.run_combo_command(scenario, command, engine)
        self.assertEqual(engine["evidence_streak"], 3)
        self.assertEqual(engine["best_combo"], 3)
        self.game.run_combo_command(scenario, "devin --version", engine)
        self.assertEqual(engine["evidence_streak"], 0)
        self.assertEqual(engine["best_combo"], 3)

    def test_powershell_commands_preserve_patterns_and_unknown_errors(self):
        scenario = next(item for item in self.content["combo"] if item["id"] == "sup-s-win-bash")

        def engine():
            return {
                "turns_used": 0,
                "run_ids": set(),
                "evidence_ids": set(),
                "evidence_streak": 0,
                "best_combo": 1,
            }

        output, _ = self.game.run_combo_command(scenario, "WHERE.EXE BASH", engine())
        self.assertIn("MKS Toolkit", output)
        output, _ = self.game.run_combo_command(scenario, "$env:PATH", engine())
        self.assertIn("MKS Toolkit", output)
        output, _ = self.game.run_combo_command(scenario, "echo %path%", engine())
        self.assertIn("MKS Toolkit", output)
        output, _ = self.game.run_combo_command(scenario, "Get-ChildItem foo", engine())
        self.assertEqual(output, scenario["unknown_output"])
        output, _ = self.game.run_combo_command(scenario, "Bogus-Command", engine())
        self.assertEqual(
            output,
            "Bogus-Command : The term 'Bogus-Command' is not recognized as the name of a "
            "cmdlet, function, script file, or operable program.",
        )

    def test_combo_end_explain_displays_confidence(self):
        scenario = next(item for item in self.content["combo"] if item["id"] == "sup-s-win-bash")
        output = io.StringIO()
        with patch.object(dojo, "use_color", return_value=False):
            with patch("builtins.input", side_effect=["solve", "1", "1"]):
                with redirect_stdout(output):
                    self.game.play_combo(scenario)
        self.assertIn("confidence  hypothesis", output.getvalue())

    def test_combo_scoring_math(self):
        self.assertEqual(dojo.combo_score(3, 5, 3, True, True), 390)
        self.assertEqual(dojo.combo_score(0, 0, 1, False, True), 55)
        self.assertEqual(dojo.levelled_xp(40, 1.5), 60)


class ContentTests(unittest.TestCase):
    def test_content_schema_regexes_and_optimal_reachability(self):
        with tempfile.TemporaryDirectory() as directory:
            content = dojo.load_content(Path(directory))
        self.assertTrue(dojo.validate_content(content))
        self.assertEqual(len(content["flash"]), 91)
        self.assertEqual(sum("choices" in item for item in content["flash"]), 11)
        source_rows = [
            line.split("\t", 1)
            for line in (ROOT.parent / "cards.tsv").read_text(encoding="utf-8").splitlines()
        ]
        plain_cards = [
            item for item in content["flash"]
            if "choices" not in item
            and item["id"] not in ("devin-shadow-function", "card-66")
            and not item["id"].startswith("sup-")
        ]
        source_cards = {
            (item["q"], item["explain"])
            for item in plain_cards
        }
        self.assertEqual(len(source_rows), 66)
        self.assertEqual(len(plain_cards), 65)
        policy = next(item for item in content["flash"] if item["id"] == "card-66")
        self.assertTrue(all(
            tuple(row) in source_cards
            for row in source_rows
            if row[0] != policy["q"]
        ))
        self.assertIn("Managed policy file found via strace", policy["explain"])
        self.assertEqual(policy["source"], "S-MASTER")
        self.assertEqual(policy["confidence"], "confirmed (strace)")
        shadow = next(item for item in content["flash"] if item["id"] == "devin-shadow-function")
        self.assertEqual(shadow["topic"], "debug")
        self.assertEqual(shadow["answers"], ["type -a devin"])
        self.assertEqual(shadow["keywords"], ["type", "function"])
        self.assertEqual(shadow["hint"], "type -a")
        topics = {
            "launch", "sessions", "auth", "config", "permissions", "modes", "slash",
            "cloud", "hooks", "rules", "skills", "mcp", "logs", "debug", "acp",
            "general-cli",
        }
        self.assertTrue(
            all(
                item["topic"] in topics
                for key in ("flash", "drill", "combo")
                for item in content[key]
            )
        )
        for scenario in content["combo"]:
            patterns = []
            for entry in scenario["commands"]:
                self.assertTrue(entry["match"])
                entry_patterns = [
                    re.compile(pattern, re.IGNORECASE) for pattern in entry["match"]
                ]
                patterns.extend(entry_patterns)
                if entry["evidence"]:
                    self.assertTrue(any(
                        pattern.fullmatch(regex_example(source))
                        for pattern, source in zip(entry_patterns, entry["match"])
                    ))
                for pattern, source in zip(entry_patterns, entry["match"]):
                    self.assertTrue(pattern.fullmatch(regex_example(source)))
            for command in scenario["optimal"]:
                self.assertTrue(any(
                    pattern.fullmatch(dojo.normalize_whitespace(command)) for pattern in patterns
                ))

    def test_support_glob_loading_and_source_key_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            content = dojo.load_content(Path(directory))
        expected_flash = [
            item["id"]
            for path in sorted((ROOT / "content").glob("cards*.json"))
            for item in json.loads(path.read_text(encoding="utf-8"))
        ]
        expected_combos = [
            item["id"]
            for path in sorted((ROOT / "content").glob("scenarios*.json"))
            for item in json.loads(path.read_text(encoding="utf-8"))
        ]
        self.assertEqual([item["id"] for item in content["flash"]], expected_flash)
        self.assertEqual([item["id"] for item in content["combo"]], expected_combos)
        self.assertNotIn("sup-policy-file", [item["id"] for item in content["flash"]])
        self.assertIn("S-MASTER", dojo.support_source_keys())

        for category, identifier in (("flash", "sup-acp-is-cli"), ("combo", "sup-s-win-bash")):
            invalid = copy.deepcopy(content)
            item = next(entry for entry in invalid[category] if entry["id"] == identifier)
            item["source"] = "NOT-A-SOURCE"
            with self.subTest(category=category):
                with self.assertRaisesRegex(ValueError, "invalid source keys"):
                    dojo.validate_content(invalid)

        optional = copy.deepcopy(content)
        for category in ("flash", "combo", "commands"):
            for item in optional[category]:
                item.pop("tags", None)
                item.pop("source", None)
                item.pop("confidence", None)
        self.assertTrue(dojo.validate_content(optional))

    def test_flash_hypothesis_confidence_is_shown_on_reveal(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            content = dojo.load_content(home)
            item = next(card for card in content["flash"] if card["id"] == "sup-conn-banner-quota")
            game = dojo.Dojo(home, content)
            output = io.StringIO()
            with patch.object(dojo, "use_color", return_value=False):
                with patch("builtins.input", return_value="skip"):
                    with redirect_stdout(output):
                        game.play_flash(item)
        self.assertIn("confidence  hypothesis", output.getvalue())


class EndToEndTests(unittest.TestCase):
    def test_piped_session_saves_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            env = {
                **os.environ,
                "DOJO_HOME": str(root / "dojo-home"),
                "HOME": str(root / "home"),
                "NO_COLOR": "1",
            }
            Path(env["HOME"]).mkdir()
            command = [
                sys.executable,
                str(ROOT / "dojo.py"),
                "play",
                "--seed",
                "1",
                "--rounds",
                "3",
                "--no-live",
            ]
            result = subprocess.run(
                command,
                input="skip\nskip\nskip\n",
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env=env,
                timeout=20,
            )
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertIn("round 1/3", result.stdout)
            self.assertNotIn("[L1 Intern", result.stdout)
            state_path = Path(env["DOJO_HOME"]) / "state.json"
            self.assertTrue(state_path.exists())
            state = json.loads(state_path.read_text())
            self.assertEqual(state["sessions"], 1)
            self.assertEqual(sum(row["seen"] for row in state["items"].values()), 3)


class PresentationTests(unittest.TestCase):
    def make_game(self, home, item):
        return dojo.Dojo(Path(home), {
            "flash": [item],
            "drill": [],
            "combo": [],
        })

    @staticmethod
    def answer_with_prompt(responses):
        def answer(prompt=""):
            print(prompt, end="")
            return next(responses)
        return answer

    def test_no_color_full_session_has_plain_danger_labels(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "home"
            home.mkdir()
            env = {
                **os.environ,
                "DOJO_HOME": str(root / "dojo-home"),
                "HOME": str(home),
                "NO_COLOR": "1",
            }
            env.pop("DEVIN_DESKTOP_AUTH_TOKEN", None)
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "dojo.py"),
                    "play",
                    "--seed",
                    "1",
                    "--no-live",
                ],
                input="skip\n" * 40,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env=env,
                timeout=20,
            )
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("\x1b", result.stdout)
        self.assertIn("[missed]", result.stdout)
        self.assertIn("devin dojo", result.stdout)
        self.assertRegex(result.stdout, r"round \d+/\d+")

    def test_color_wrong_flash_uses_inverse_danger_and_accent_marker_only(self):
        item = {
            "id": "path-card",
            "topic": "debug",
            "q": "Where is the PATH?",
            "answers": ["the answer"],
            "keywords": ["answer"],
            "hint": "hint",
            "explain": "The explanation.",
        }
        output = TerminalCapture(tty=True)
        with tempfile.TemporaryDirectory() as directory:
            game = self.make_game(directory, item)
            responses = iter(["wrong", "n"])
            with patch.dict(os.environ, {"DOJO_ACCENT": "208"}):
                with patch.object(dojo, "use_color", return_value=True):
                    with redirect_stdout(output):
                        with patch(
                            "builtins.input",
                            side_effect=self.answer_with_prompt(responses),
                        ):
                            game.play_flash(item)
        text = output.getvalue()
        self.assertIn("\x1b[1;7mmissed\x1b[0m", text)
        self.assertIn("Where is the PATH?", text)
        self.assertNotIn("\x1b[31m", text)
        self.assertNotIn("\x1b[32m", text)
        self.assertNotIn("\x1b[36m", text)
        accent_sequence = "\x1b[%sm" % dojo.accent_code()
        accent_positions = [
            match.end() for match in re.finditer(re.escape(accent_sequence), text)
        ]
        self.assertTrue(accent_positions)
        self.assertTrue(all(text[position:].startswith("☞") for position in accent_positions))
        self.assertEqual(dojo.chrome("Session summary"), "session summary")

    def test_accent_code_parsing_and_default(self):
        with patch.dict(os.environ, {"DOJO_ACCENT": "33"}):
            self.assertEqual(dojo.accent_code(), "38;5;33")
        with patch.dict(os.environ, {"DOJO_ACCENT": "#ff6a00"}):
            self.assertEqual(dojo.accent_code(), "38;2;255;106;0")
        with patch.dict(os.environ, {"DOJO_ACCENT": "junk"}):
            self.assertEqual(dojo.accent_code(), "38;5;208")

    def test_ascii_fallback_omits_all_unicode_glyphs(self):
        output = TerminalCapture(encoding="ascii")
        names = ("prompt", "found", "empty", "separator", "quit", "strong_rule", "hairline")
        with patch.object(dojo, "use_color", return_value=False):
            with redirect_stdout(output):
                print("".join(dojo.glyph(name) for name in names))
                print(dojo.dots(1, 2))
                print(dojo.score_bar(0.5))
                print(dojo.rule(), dojo.rule(is_strong=True))
        text = output.getvalue()
        for character in "☞●○·✕━─":
            self.assertNotIn(character, text)

    def test_source_has_no_non_accent_foreground_sgr_literals(self):
        source = Path(dojo.__file__).read_text(encoding="utf-8")
        self.assertNotRegex(source, r"\\(?:033|x1b)\[3[0-9]")


if __name__ == "__main__":
    unittest.main()
