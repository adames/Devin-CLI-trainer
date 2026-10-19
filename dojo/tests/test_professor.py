import io
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
import unittest
from collections import Counter
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import dojo


ROOT = Path(__file__).resolve().parents[1]
COVERAGE_EXEMPT = ()


class DevinCommandParserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.content = dojo.load_content(Path(cls.temp.name))
        cls.cards = cls.content["commands"]

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def card(self, identifier):
        return next(card for card in self.cards if card["id"] == identifier)

    def test_aliases_equals_option_order_and_placeholders(self):
        list_card = self.card("cmd-sessions-list")
        self.assertTrue(dojo.command_answer_matches("devin ls", list_card))

        mode_card = self.card("cmd-launch-permission-mode")
        self.assertTrue(dojo.command_answer_matches("devin --permission-mode=auto", mode_card))

        fix_card = self.card("fix-print-option-order")
        self.assertTrue(dojo.command_answer_matches(
            'devin -p "summarize x" --respect-workspace-trust=false',
            fix_card,
        ))
        self.assertFalse(dojo.command_answer_matches(fix_card["broken"], fix_card))
        self.assertTrue(dojo.command_answer_matches(
            "devin mcp add server-a https://example.test/mcp",
            self.card("cmd-mcp-add"),
        ))

    def test_optional_value_order_trap_and_prompt_separator(self):
        fix_card = self.card("fix-print-option-order")
        broken = 'devin -p --respect-workspace-trust false "x"'
        self.assertFalse(dojo.command_answer_matches(broken, fix_card))

        prompt_card = self.card("cmd-launch-prompt")
        self.assertTrue(dojo.command_answer_matches(
            "devin -- summarize PATH handling",
            prompt_card,
        ))

    def test_cloud_without_subcommand_parses(self):
        parsed = dojo.parse_devin_command("devin cloud")
        self.assertEqual(parsed["path"], ("cloud",))
        card = self.card("cmd-cloud-session")
        self.assertTrue(dojo.command_answer_matches("devin cloud", card))

    def test_unknown_flag_suggestion(self):
        card = self.card("cmd-launch-permission-mode")
        feedback = dojo.command_answer_feedback(
            "devin --permisson-mode auto",
            card,
        )
        self.assertIn("--permission-mode", feedback)
        feedback = dojo.command_answer_feedback(
            "devin mcp addd server",
            self.card("cmd-mcp-add"),
        )
        self.assertIn("did you mean add", feedback)

    def test_default_fill_in_blank_uses_first_flag_then_last_subcommand(self):
        self.assertEqual(
            dojo.command_blank({"category": "launch", "answers": ["devin --model opus"]}),
            "--model",
        )
        self.assertEqual(
            dojo.command_blank({"category": "config-rules", "answers": ["devin rules list"]}),
            "list",
        )
        self.assertEqual(
            dojo.command_blank({"category": "launch", "answers": ["devin"]}),
            "devin",
        )

    def test_slash_and_shell_graders_use_their_own_references(self):
        slash_card = self.card("cmd-slash-ask")
        self.assertTrue(dojo.command_answer_matches("/ask what", slash_card))
        self.assertFalse(dojo.command_answer_matches("/ask what changed", slash_card))
        self.assertFalse(dojo.command_answer_matches("/not-a-command x", slash_card))

        shell_card = self.card("shell-open-files")
        self.assertTrue(dojo.command_answer_matches("lsof -p 1234", shell_card))
        self.assertFalse(dojo.command_answer_matches("devin lsof -p 1234", shell_card))


class ProfessorContentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.content = dojo.load_content(Path(cls.temp.name))
        cls.cards = cls.content["commands"]
        cls.index = dojo.help_index()

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_every_answer_and_fix_is_valid(self):
        for card in self.cards:
            for answer in card["answers"]:
                if card["category"] in ("slash", "shell"):
                    self.assertTrue(dojo.command_answer_matches(answer, card), card["id"])
                else:
                    dojo.parse_devin_command(answer, self.index)
            if card["kind"] == "fix":
                self.assertFalse(dojo.command_answer_matches(card["broken"], card), card["id"])

    def test_new_support_command_answers_parse_and_shell_placeholders_match(self):
        identifiers = (
            "sup-cmd-bypass-headless",
            "sup-fix-invented-flags",
            "sup-cmd-model-id",
            "sup-shell-detach",
            "sup-shell-grep-quota",
            "sup-shell-where-bash",
            "sup-shell-pgrep",
        )
        cards_by_id = {card["id"]: card for card in self.cards}
        for identifier in identifiers:
            card = cards_by_id[identifier]
            with self.subTest(identifier=identifier):
                self.assertTrue(dojo.command_answer_matches(card["answers"][0], card))
                if card["category"] not in ("slash", "shell"):
                    dojo.parse_devin_command(card["answers"][0], self.index)
        grep_card = cards_by_id["sup-shell-grep-quota"]
        self.assertTrue(dojo.command_answer_matches(
            "grep -iE 'resource_exhausted|rate limit' repro-*.log",
            grep_card,
        ))
        detach_card = cards_by_id["sup-shell-detach"]
        self.assertTrue(dojo.command_answer_matches(
            'nohup devin -p "summarize this incident" </dev/null >devin.log 2>&1 &',
            detach_card,
        ))

    def test_coverage_categories_tiers_and_slash_manifest(self):
        self.assertTrue(dojo.validate_content(self.content))
        self.assertEqual(
            {card["category"] for card in self.cards},
            set(dojo.CATEGORIES),
        )

        parsed_paths = {()}
        parsed_flags = set()
        for card in self.cards:
            if card["category"] in ("slash", "shell"):
                continue
            for answer in card["answers"]:
                parsed = dojo.parse_devin_command(answer, self.index)
                parsed_paths.update(
                    parsed["path"][:depth]
                    for depth in range(len(parsed["path"]) + 1)
                )
                parsed_flags.update(flag for flag, _ in parsed["flags"])

        expected_paths = {()}
        for parent, children in self.index["commands"].items():
            if "help" not in parent:
                expected_paths.add(parent)
                expected_paths.update(
                    parent + (child,)
                    for child in children
                    if child != "help"
                )
        self.assertFalse(expected_paths - parsed_paths)

        expected_flags = {
            specification["long"]
            for options in self.index["options"].values()
            for specification in options.values()
            if specification["long"] != "--help"
        }
        self.assertFalse(expected_flags - parsed_flags - set(COVERAGE_EXEMPT))

        slash_names = set(dojo.slash_commands())
        deck_slash_names = {
            answer.split()[0]
            for card in self.cards
            if card["category"] == "slash"
            for answer in card["answers"]
        }
        self.assertFalse(slash_names - deck_slash_names)

        tier_one = {
            card["answers"][0]
            for card in self.cards
            if card["tier"] == 1 and card["category"] not in ("slash", "shell")
        }
        self.assertEqual(tier_one, {
            "devin",
            "devin -- <prompt>",
            "devin -p <prompt>",
            "devin -c",
            "devin -r <session>",
            "devin --model opus",
            "devin --permission-mode auto",
            "devin --permission-mode dangerous -p <prompt>",
            "devin list",
            "devin auth status",
            "devin auth login",
            "devin doctor",
            "devin --version",
            "devin update",
            "devin mcp list",
            "devin mcp add <name> <url>",
            "devin rules list",
            "devin skills list",
            "devin ssh",
            "devin forward <session> <ports>",
            "devin models list",
        })
        tier_one_slash = {
            card["answers"][0]
            for card in self.cards
            if card["category"] == "slash" and card["tier"] == 1
        }
        self.assertEqual(tier_one_slash, {"/shortcuts", "/handoff", "/ask <question>", "/plan", "/model"})
        tier_three = {
            answer
            for card in self.cards
            if card["tier"] == 3
            for answer in card["answers"]
        }
        self.assertTrue(any(answer.startswith("devin cloud drs ") for answer in tier_three))
        self.assertTrue(any(answer.startswith("devin migrate ") for answer in tier_three))
        for answer in ("devin acp", "devin uninstall", "devin setup", "devin desktop"):
            self.assertIn(answer, tier_three)
        self.assertTrue(any(answer.startswith("devin plugins prune") for answer in tier_three))
        tier_three_flags = {
            flag
            for answer in tier_three
            if not answer.startswith("/")
            for flag, _ in dojo.parse_devin_command(answer, self.index)["flags"]
        }
        self.assertTrue({"--gateway", "--config", "--env", "--header"} <= tier_three_flags)
        self.assertTrue(any(flag.startswith("--oauth-") for flag in tier_three_flags))

    def test_deck_tasks_hints_explanations_and_removed_help_subcommands(self):
        tasks = [card["task"] for card in self.cards]
        self.assertEqual(len(tasks), len(set(tasks)))

        hint_counts = Counter(card["hint"] for card in self.cards)
        self.assertLessEqual(max(hint_counts.values()), 3)

        source_files = list((ROOT / "content" / "help").glob("*.txt"))
        source_files += list((ROOT.parent / "docs").glob("*.md"))
        source_files.append(ROOT.parent / "GUIDE.md")
        source_lines = {
            line.strip()
            for source_file in source_files
            for line in source_file.read_text(encoding="utf-8").splitlines()
        }
        all_flags = {
            alias
            for options in self.index["options"].values()
            for flag, specification in options.items()
            for alias in {flag, *specification["aliases"]}
        }
        cards_by_id = {card["id"]: card for card in self.cards}
        help_lines = (ROOT / "content" / "help" / "devin.txt").read_text(
            encoding="utf-8"
        ).splitlines()
        permission_mode_line = next(
            index for index, line in enumerate(help_lines)
            if "--permission-mode" in line
        )
        modes_line = next(
            line for line in help_lines[permission_mode_line:permission_mode_line + 6]
            if "Modes:" in line
        )
        permission_mode_values = set(re.findall(r'"([^"]+)"', modes_line))

        for card in self.cards:
            task = card["task"]
            explanation_lines = card["explain"].splitlines()
            self.assertNotIn(task, card["answers"], card["id"])
            self.assertNotEqual(card["explain"], task, card["id"])
            self.assertNotIn(card["explain"], card["answers"], card["id"])
            self.assertEqual(len(explanation_lines), 2, card["id"])
            self.assertIn(explanation_lines[0], source_lines, card["id"])
            self.assertTrue(explanation_lines[1].startswith("Use it when "), card["id"])

            for answer in card["answers"]:
                self.assertNotIn(answer.casefold(), card["hint"].casefold(), card["id"])
                for token in answer.split():
                    if token.startswith(("-", "/")):
                        self.assertNotIn(token.casefold(), task.casefold(), card["id"])

            for flag in all_flags:
                if flag.startswith("--"):
                    self.assertNotIn(flag.casefold(), task.casefold(), card["id"])
                else:
                    self.assertNotIn(flag, task.split(), card["id"])

            if card["category"] not in ("slash", "shell"):
                parsed = dojo.parse_devin_command(card["answers"][0], self.index)
                self.assertNotIn("help", parsed["path"], card["id"])
                values = [value for _, value in parsed["flags"] if value is not None]
                values.extend(parsed["positionals"])
                values = [
                    value for value in values
                    if not re.fullmatch(r"<[^>]+>", value)
                    and value not in parsed["path"]
                    and value not in permission_mode_values
                ]
            elif card["category"] == "slash":
                tokens = shlex.split(card["answers"][0])
                self.assertNotIn(tokens[0].casefold(), task.casefold(), card["id"])
                values = [
                    value for value in tokens[1:]
                    if not value.startswith("-") and not re.fullmatch(r"<[^>]+>", value)
                ]
            else:
                values = []
            for value in values:
                self.assertIn(value.casefold(), task.casefold(), card["id"])

        self.assertIn("/help", {
            answer.split()[0]
            for card in self.cards
            if card["category"] == "slash"
            for answer in card["answers"]
        })
        self.assertIn("session", cards_by_id["cmd-flag-list-format"]["task"].casefold())
        self.assertIn("model", cards_by_id["cmd-flag-models-list-format"]["task"].casefold())
        self.assertIn("forward", cards_by_id["cmd-flag-forward-gateway"]["task"].casefold())
        self.assertIn("ssh", cards_by_id["cmd-flag-ssh-gateway"]["task"].casefold())
        self.assertEqual(
            permission_mode_values,
            {"auto", "accept-edits", "smart", "dangerous"},
        )
        mode_card = cards_by_id["sup-cmd-bypass-headless"]
        mode_values = [
            value
            for flag, value in dojo.parse_devin_command(mode_card["answers"][0], self.index)["flags"]
            if flag == "--permission-mode"
        ]
        self.assertEqual(mode_values, ["dangerous"])
        self.assertTrue(set(mode_values) <= permission_mode_values)
        self.assertNotIn("dangerous", mode_card["task"].casefold())
        model_card = cards_by_id["cmd-launch-model"]
        model_values = [
            value
            for _, value in dojo.parse_devin_command(model_card["answers"][0], self.index)["flags"]
            if value is not None
        ]
        self.assertIn("opus", model_values)
        self.assertIn("opus", model_card["task"].casefold())
        missing_model_task = model_card["task"].replace("opus", "the requested model")
        self.assertFalse(all(
            value.casefold() in missing_model_task.casefold()
            for value in model_values
        ))

        guide_lines = (ROOT.parent / "GUIDE.md").read_text(
            encoding="utf-8"
        ).splitlines()
        for card in self.cards:
            if card["category"] != "shell":
                continue
            match = re.fullmatch(r"\.\./GUIDE\.md:(\d+)", card["source"])
            self.assertIsNotNone(match, card["id"])
            line_number = int(match.group(1))
            self.assertEqual(
                guide_lines[line_number - 1].strip(),
                card["explain"].splitlines()[0].strip(),
                card["id"],
            )

        self.assertEqual(
            cards_by_id["fix-print-option-order"]["error"],
            "error: the argument '--print [<PROMPT>]' cannot be used with '[PATH]...'\n"
            "\n"
            "Usage: devin --print [<PROMPT>] --respect-workspace-trust "
            "[<RESPECT_WORKSPACE_TRUST>] [PATH]... [-- <PROMPT>...]\n"
            "\n"
            "For more information, try '--help'.",
        )


    def test_every_tsv_row_has_a_cards_json_card(self):
        tsv_rows = [
            line.split("\t", 1)
            for line in (ROOT.parent / "cards.tsv").read_text(
                encoding="utf-8"
            ).splitlines()
            if line.strip()
        ]
        json_cards = [
            card
            for path in (ROOT / "content").glob("cards*.json")
            for card in json.loads(path.read_text(encoding="utf-8"))
        ]
        by_question = {card["q"]: card for card in json_cards}
        for question, answer in tsv_rows:
            card = by_question.get(question)
            self.assertIsNotNone(card, question)
            self.assertIn(
                answer,
                (card["explain"], card["answers"][0]),
                question,
            )


class ProfessorEngineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name)
        self.content = dojo.load_content(self.home)
        self.game = dojo.Dojo(self.home, self.content)

    def tearDown(self):
        self.temp.cleanup()

    def test_form_escalation_and_fix_override(self):
        card = next(card for card in self.content["commands"] if card["kind"] == "write")
        self.assertEqual(self.game.command_form(card), "recognize")
        self.game.state["items"][card["id"]] = {"box": 2}
        self.assertEqual(self.game.command_form(card), "fill in")
        self.game.state["items"][card["id"]]["box"] = 3
        self.assertEqual(self.game.command_form(card), "recall")

        fix = next(card for card in self.content["commands"] if card["kind"] == "fix")
        self.game.state["items"][fix["id"]] = {"box": 5}
        self.assertEqual(self.game.command_form(fix), "fix")

    def test_command_skip_reveals_without_invalid_command_feedback(self):
        card = next(card for card in self.content["commands"] if card["kind"] == "write")
        output = io.StringIO()
        with patch("builtins.input", return_value="skip"), redirect_stdout(output):
            self.assertFalse(self.game.ask_command_card(card, [card], "recall"))
        self.assertIn(card["answers"][0], output.getvalue())
        self.assertIn(card["explain"], output.getvalue())
        self.assertNotIn("command must start with devin", output.getvalue())
        self.assertNotIn("Count it?", output.getvalue())

    def test_command_reveal_displays_confidence(self):
        card = next(
            card for card in self.content["commands"] if card["id"] == "sup-cmd-model-id"
        )
        output = io.StringIO()
        with patch.object(dojo, "use_color", return_value=False):
            with patch("builtins.input", return_value="skip"), redirect_stdout(output):
                self.game.ask_command_card(card, [card], "recall")
        self.assertIn("confidence  confirmed in S-RE; not re-run here (needs auth)", output.getvalue())

    def test_fill_in_shows_task_before_command_template(self):
        card = next(
            card for card in self.content["commands"]
            if card["kind"] == "write" and card["category"] == "launch"
        )
        output = io.StringIO()
        with patch("builtins.input", return_value="skip"), redirect_stdout(output):
            self.game.ask_command_card(card, self.content["commands"], "fill in")
            marker = dojo.glyph("question")
        self.assertEqual(
            output.getvalue().splitlines()[:2],
            [
                "%s %s" % (marker, card["task"]),
                "  " + card["answers"][0].replace(dojo.command_blank(card), "___", 1),
            ],
        )

    def test_recognition_distractors_are_unique_write_cards_with_same_category_priority(self):
        def card(identifier, category, kind, task, answer):
            return {
                "id": identifier,
                "category": category,
                "kind": kind,
                "task": task,
                "answers": [answer],
            }

        target = card("target", "auth", "write", "Find the account status.", "devin auth status")
        same_category = [
            card("auth-1", "auth", "write", "Sign in to the account.", "devin auth login"),
            card("auth-2", "auth", "write", "Clear stored credentials.", "devin auth logout"),
            card("auth-3", "auth", "write", "Inspect authentication settings.", "devin auth status"),
        ]
        other_category = card(
            "launch-1",
            "launch",
            "write",
            "Start a new session.",
            "devin",
        )
        fix_card = card("auth-fix", "auth", "fix", "Fix an auth error.", "devin auth login")
        help_card = card(
            "auth-help",
            "auth",
            "write",
            "Find authentication help.",
            "devin auth help",
        )
        choices = self.game.recognition_choices(
            target,
            [target] + same_category + [other_category, fix_card, help_card],
        )
        self.assertEqual(len(choices), len(set(choices)))
        self.assertEqual(set(choices), {target["task"]} | {item["task"] for item in same_category})
        self.assertIsNone(self.game.recognized_task("4", [target["task"]]))

    def test_command_missed_summary_uses_task_and_answer_only(self):
        card = next(card for card in self.content["commands"] if card["kind"] == "write")
        self.game.session_missed = [card]
        output = io.StringIO()
        with redirect_stdout(output):
            empty_glyph = dojo.glyph("empty")
            self.game.print_summary(training=True)
        summary = output.getvalue()
        expected = "%s %s\n  answer  %s" % (
            empty_glyph,
            card["task"],
            card["answers"][0],
        )
        self.assertIn(expected, summary)
        self.assertEqual(summary.count(card["task"]), 1)
        self.assertNotIn(card["explain"], summary)

    def test_narrow_terminal_width_falls_back_to_seventy_two(self):
        with patch("dojo.shutil.get_terminal_size", return_value=os.terminal_size((39, 24))):
            self.assertEqual(dojo.terminal_width(), 72)

    def test_new_cards_follow_tier_order_and_category_round_robin(self):
        cards = [
            {"id": "launch-2", "category": "launch", "tier": 2},
            {"id": "launch-1", "category": "launch", "tier": 1},
            {"id": "sessions-1", "category": "sessions", "tier": 1},
            {"id": "auth-1", "category": "auth", "tier": 1},
        ]
        self.game.begin_session(seed=2)
        chosen = []
        for _ in range(4):
            item = self.game.choose_command_item(cards)
            chosen.append((item["category"], item["tier"]))
            self.game.state["items"][item["id"]] = {
                "box": 2,
                "due": "2999-01-01T00:00:00+00:00",
            }
        self.assertEqual(chosen, [
            ("launch", 1),
            ("sessions", 1),
            ("auth", 1),
            ("launch", 2),
        ])

    def test_train_category_filter_and_categories_table(self):
        self.game.content["commands"] = [
            card for card in self.content["commands"]
            if card["category"] == "auth" and card["tier"] == 1
        ]
        self.game.content["combo"] = []
        with patch("builtins.input", return_value="skip"), redirect_stdout(io.StringIO()):
            self.game.train(["auth"], rounds=1, tier=1, seed=1)
        self.assertEqual(set(self.game.category_totals), {"auth"})
        auth_ids = {
            card["id"] for card in self.game.content["commands"]
            if card["category"] == "auth"
        }
        self.assertTrue(set(self.game.state["items"]) <= auth_ids)

        output = io.StringIO()
        with redirect_stdout(output):
            dojo.show_categories(self.content, dojo.default_state())
        for category in dojo.CATEGORIES:
            self.assertIn(category, output.getvalue())

    def test_state_home_precedence_and_symlink_from_other_directory(self):
        with patch.dict(os.environ, {
            "PROFESSOR_HOME": "/tmp/professor-state",
            "DOJO_HOME": "/tmp/legacy-state",
        }):
            self.assertEqual(dojo.dojo_home(), Path("/tmp/professor-state"))

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bin_dir = root / "bin"
            other = root / "other"
            home = root / "home"
            bin_dir.mkdir()
            other.mkdir()
            home.mkdir()
            link = bin_dir / "professor-devin"
            link.symlink_to(ROOT / "dojo.py")
            env = {
                **os.environ,
                "HOME": str(home),
                "PROFESSOR_HOME": str(root / "state"),
                "NO_COLOR": "1",
            }
            env.pop("DOJO_HOME", None)
            result = subprocess.run(
                [sys.executable, str(link), "categories"],
                cwd=str(other),
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=20,
            )
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("\x1b", result.stdout)
        self.assertIn("categories", result.stdout)
        self.assertIn("integration", result.stdout)

    def test_no_subcommand_defaults_to_ten_round_train(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {
                "PROFESSOR_HOME": str(Path(directory) / "state"),
            }):
                with patch.object(dojo, "interactive_terminal", return_value=False):
                    with patch.object(dojo.Dojo, "train") as train:
                        self.assertEqual(dojo.main([]), 0)
        train.assert_called_once_with([], 10, 3, None)
        self.assertEqual(dojo.build_parser().prog, "professor-devin")

    def test_unknown_category_lists_valid_categories(self):
        with tempfile.TemporaryDirectory() as directory:
            env = {
                **os.environ,
                "PROFESSOR_HOME": str(Path(directory) / "state"),
                "NO_COLOR": "1",
            }
            result = subprocess.run(
                [sys.executable, str(ROOT / "dojo.py"), "train", "not-a-category"],
                cwd=str(ROOT),
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=20,
            )
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("unknown category", result.stdout)
        for category in dojo.CATEGORIES:
            self.assertIn(category, result.stdout)

    def test_installer_creates_an_idempotent_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            env = {**os.environ, "HOME": str(home)}
            for _ in range(2):
                result = subprocess.run(
                    ["bash", str(ROOT / "install.sh")],
                    cwd=str(ROOT),
                    env=env,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    timeout=20,
                )
                self.assertEqual(result.returncode, 0, result.stdout)
            link = home / ".local" / "bin" / "professor-devin"
            self.assertTrue(link.is_symlink())
            self.assertEqual(link.resolve(), ROOT / "dojo.py")


class MenuAndCliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def run_main(self, inputs, profile="veteran"):
        if profile is not None:
            dojo.save_state(
                self.home, dict(dojo.default_state(), profile=profile)
            )
        output = io.StringIO()
        with patch.dict(os.environ, {"PROFESSOR_HOME": str(self.home)}):
            with patch.object(dojo, "interactive_terminal", return_value=True):
                with patch("builtins.input", side_effect=inputs):
                    with redirect_stdout(output):
                        result = dojo.main([])
        return result, output.getvalue()

    def test_bare_run_in_terminal_opens_home_menu(self):
        with patch.object(dojo.Dojo, "train") as train:
            result, text = self.run_main(["q"])
        self.assertEqual(result, 0)
        self.assertIn("What do you want to practice?", text)
        self.assertIn("quick start", text)
        train.assert_not_called()

    def test_menu_quick_start_runs_default_train(self):
        with patch.object(dojo.Dojo, "train") as train:
            result, _ = self.run_main(["1", "", "q"])
        self.assertEqual(result, 0)
        train.assert_called_once_with([], 10, 3, None)

    def test_menu_enter_starts_quick_start(self):
        with patch.object(dojo.Dojo, "train") as train:
            result, _ = self.run_main(["", "", "q"])
        self.assertEqual(result, 0)
        train.assert_called_once_with([], 10, 3, None)

    def test_menu_pick_a_topic_trains_that_category(self):
        with patch.object(dojo.Dojo, "train") as train:
            result, _ = self.run_main(["2", "mcp", "", "q"])
        self.assertEqual(result, 0)
        train.assert_called_once_with(["mcp"], 10, 3, None)

    def run_cli(self, argv, stdin=""):
        env = {
            **os.environ,
            "PROFESSOR_HOME": str(self.home / "state"),
            "NO_COLOR": "1",
            "PYTHONIOENCODING": "utf-8",
        }
        return subprocess.run(
            [sys.executable, str(ROOT / "dojo.py")] + argv,
            input=stdin,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
            timeout=30,
        )

    def test_help_and_version_look_like_clap(self):
        result = self.run_cli(["--help"])
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("Usage: professor-devin", result.stdout)
        self.assertIn("Commands:", result.stdout)
        for name in ("menu", "train", "play", "stats", "categories", "list", "reset", "help"):
            self.assertIn(name, result.stdout)

        result = self.run_cli(["help", "play"])
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("--rounds", result.stdout)
        self.assertIn("--mode", result.stdout)

        result = self.run_cli(["help", "train"])
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("--rounds", result.stdout)

        for flag in ("-V", "--version"):
            result = self.run_cli([flag])
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertIn("professor-devin 1.1.0", result.stdout)

    def test_train_round_layout_no_color(self):
        result = self.run_cli(["train"], stdin="quit\n")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("round 01/", result.stdout)
        self.assertIn("✱ ", result.stdout)
        self.assertIn("? hint · skip · quit", result.stdout)
        self.assertIn("❭", result.stdout)

    def test_first_run_wizard_offers_profiles_and_saves(self):
        with patch.object(dojo.Dojo, "train") as train:
            result, text = self.run_main(["2", "q"], profile=None)
        self.assertEqual(result, 0)
        self.assertIn("How well do you know the Devin CLI?", text)
        self.assertIn("What do you want to practice?", text)
        train.assert_not_called()
        state = json.loads((self.home / "state.json").read_text())
        self.assertEqual(state["profile"], "veteran")

    def test_first_run_beginner_gets_how_it_works(self):
        result, text = self.run_main(["", "", "q"], profile=None)
        self.assertEqual(result, 0)
        self.assertIn("How well do you know the Devin CLI?", text)
        self.assertIn("how it works", text)
        self.assertIn("What do you want to practice?", text)
        state = json.loads((self.home / "state.json").read_text())
        self.assertEqual(state["profile"], "beginner")

    def test_second_run_with_profile_skips_wizard(self):
        (self.home).mkdir(parents=True, exist_ok=True)
        dojo.save_state(self.home, dict(dojo.default_state(), profile="veteran"))
        result, text = self.run_main(["q"])
        self.assertEqual(result, 0)
        self.assertNotIn("How well do you know the Devin CLI?", text)
        self.assertIn("What do you want to practice?", text)

    def test_train_subcommand_never_shows_wizard(self):
        output = io.StringIO()
        with patch.dict(os.environ, {"PROFESSOR_HOME": str(self.home)}):
            with patch.object(dojo, "interactive_terminal", return_value=True):
                with patch.object(dojo.Dojo, "train"):
                    with redirect_stdout(output):
                        self.assertEqual(dojo.main(["train", "--rounds", "2"]), 0)
        self.assertNotIn("How well do you know", output.getvalue())

    def test_setup_subcommand_and_help(self):
        output = io.StringIO()
        with patch.dict(os.environ, {"PROFESSOR_HOME": str(self.home)}):
            with patch("builtins.input", side_effect=["1", ""]):
                with redirect_stdout(output):
                    self.assertEqual(dojo.main(["setup"]), 0)
        state = json.loads((self.home / "state.json").read_text())
        self.assertEqual(state["profile"], "beginner")

        result = self.run_cli(["--help"])
        self.assertIn("setup", result.stdout)
        result = self.run_cli(["help", "setup"])
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("professor-devin setup", result.stdout)

    def test_get_sh_clones_and_installs(self):
        repo = ROOT.parent
        with tempfile.TemporaryDirectory() as directory:
            # /var is a symlink on macOS; resolve so HOME matches the
            # installer's readlink -f spelling either way.
            root = Path(directory).resolve()
            env = {
                **os.environ,
                "HOME": str(root),
                "PROFESSOR_DEVIN_REPO": str(repo),
                "PROFESSOR_DEVIN_DIR": str(root / "app"),
            }
            for _ in range(2):
                result = subprocess.run(
                    ["bash", str(repo / "get.sh")],
                    input="",
                    env=env,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    timeout=60,
                )
                self.assertEqual(result.returncode, 0, result.stdout)
            link = root / ".local" / "bin" / "professor-devin"
            self.assertTrue(link.is_symlink())
            self.assertEqual(
                link.resolve(), (root / "app" / "dojo" / "dojo.py").resolve()
            )

    def test_veteran_profile_forces_recall_but_fix_stays_fix(self):
        content = dojo.load_content(self.home)
        game = dojo.Dojo(self.home, content)
        write_card = next(
            card for card in content["commands"] if card["kind"] == "write"
        )
        fix_card = next(
            card for card in content["commands"] if card["kind"] == "fix"
        )
        game.state["profile"] = "veteran"
        self.assertEqual(game.command_form(write_card), "recall")
        self.assertEqual(game.command_form(fix_card), "fix")
        game.state["profile"] = "beginner"
        self.assertEqual(game.command_form(write_card), "recognize")

    def test_coach_tip_shows_twice_for_beginner_never_for_veteran(self):
        content = dojo.load_content(self.home)
        card = next(
            card for card in content["commands"] if card["kind"] == "write"
        )
        game = dojo.Dojo(self.home, content)
        game.state["profile"] = "beginner"
        for round_number in range(3):
            output = io.StringIO()
            with patch("builtins.input", return_value="skip"):
                with redirect_stdout(output):
                    game.ask_command_card(card, [card], "recognize")
            if round_number < 2:
                self.assertIn("tip  ", output.getvalue())
            else:
                self.assertNotIn("tip  ", output.getvalue())
        veteran = dojo.Dojo(self.home, content)
        veteran.state["profile"] = "veteran"
        output = io.StringIO()
        with patch("builtins.input", return_value="skip"):
            with redirect_stdout(output):
                veteran.ask_command_card(card, [card], "recognize")
        self.assertNotIn("tip  ", output.getvalue())

    def test_force_color_enables_and_zero_disables(self):
        class NonTty(io.StringIO):
            def isatty(self):
                return False

        with patch.dict(os.environ, {"FORCE_COLOR": "1"}):
            os.environ.pop("NO_COLOR", None)
            with redirect_stdout(NonTty()):
                self.assertTrue(dojo.use_color())
        with patch.dict(os.environ, {"FORCE_COLOR": "0"}):
            os.environ.pop("NO_COLOR", None)
            with redirect_stdout(NonTty()):
                self.assertFalse(dojo.use_color())

    def test_fill_in_accepts_the_whole_command(self):
        content = dojo.load_content(self.home)
        card = next(
            card for card in content["commands"]
            if card["kind"] == "write" and card["category"] == "launch"
        )
        game = dojo.Dojo(self.home, content)
        self.assertTrue(game.command_response_is_correct(
            card, "fill in", card["answers"][0], None
        ))
        self.assertTrue(game.command_response_is_correct(
            card, "fill in", dojo.command_blank(card), None
        ))


if __name__ == "__main__":
    unittest.main()
