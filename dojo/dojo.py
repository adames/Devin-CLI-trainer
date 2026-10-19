#!/usr/bin/env python3

import argparse
import datetime as dt
import difflib
from functools import lru_cache
import json
import math
import os
import random
import re
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
BOX_INTERVALS = {1: 0, 2: 1, 3: 3, 4: 7, 5: 21}
NEW_ITEMS_PER_SESSION = 5
FLASH_MODE_ROUNDS = 6
DRILL_MODE_ROUNDS = 2
MIXED_FLASH_OPENING_ROUNDS = 6
MIXED_FLASH_CLOSING_ROUNDS = 4
DRILL_TIME_BONUS_CAP = 15
DRILL_TIME_BONUS_SECONDS = 20
DRILL_BASE_XP = 25
VALID_TIERS = (1, 2, 3)
TITLES = {
    1: "Intern",
    2: "Log Reader",
    3: "Triage Tech",
    4: "Tracer",
    5: "Config Whisperer",
    6: "Root-Causer",
}
KNOWN_COMMANDS = {
    "devin", "cat", "ls", "jq", "rg", "grep", "env", "echo", "type", "which",
    "command", "bash", "curl", "ps", "lsof", "ss", "strace", "tail", "head",
    "find", "sqlite3", "git", "python3", "printenv", "diff", "where", "where.exe",
    "tasklist", "findstr", "select-string", "get-childitem", "get-command", "dir",
    "pgrep", "nohup", "mvn", "sudo", "fs_usage", "tr",
}
CATEGORIES = (
    "launch", "sessions", "auth", "config-rules", "skills", "mcp", "plugins",
    "models", "cloud", "maintenance", "integration", "slash", "shell",
)
COVERAGE_EXEMPT = ()
COMMAND_HELP_DIR = BASE_DIR / "content" / "help"
CONTENT_TOPICS = {
    "launch", "sessions", "auth", "config", "permissions", "modes", "slash",
    "cloud", "hooks", "rules", "skills", "mcp", "logs", "debug", "acp", "general-cli",
}
FLASH_REQUIRED_FIELDS = {"id", "topic", "q", "answers", "keywords", "hint", "explain"}
DRILL_REQUIRED_FIELDS = {
    "id", "topic", "prompt", "platforms", "requires", "costs_credits",
    "setup", "kind", "cleanup", "explain",
}
SCENARIO_REQUIRED_FIELDS = {
    "id", "topic", "title", "ticket", "prompt", "turns", "commands",
    "unknown_output", "root_cause", "fix", "optimal", "explain",
}
COMMAND_REQUIRED_FIELDS = {
    "id", "category", "tier", "task", "answers", "hint", "explain", "kind",
}
VERSION = "1.1.0"
GLYPHS = {
    "prompt": ("❭", ">"),
    "question": ("✱", "*"),
    "found": ("●", "*"),
    "empty": ("○", "o"),
    "separator": ("·", "-"),
    "quit": ("✕", "x"),
    "strong_rule": ("━", "="),
    "hairline": ("─", "-"),
}


def use_color():
    force = os.environ.get("FORCE_COLOR")
    if force and force != "0":
        return True
    return os.environ.get("NO_COLOR") is None and bool(
        getattr(sys.stdout, "isatty", lambda: False)()
    )


def interactive_terminal():
    stdin_tty = getattr(sys.stdin, "isatty", lambda: False)
    stdout_tty = getattr(sys.stdout, "isatty", lambda: False)
    return bool(stdin_tty() and stdout_tty())


def glyph(name):
    unicode_glyph, ascii_glyph = GLYPHS[name]
    encoding = getattr(sys.stdout, "encoding", None)
    if isinstance(encoding, str) and encoding.lower().replace("-", "").replace("_", "") in (
        "utf8",
        "utf8sig",
    ):
        return unicode_glyph
    return ascii_glyph


def chrome(text):
    return str(text).lower()


def _style(text, code):
    text = str(text)
    if not use_color():
        return text
    return "\033[%sm%s\033[0m" % (code, text)


def muted(text):
    return _style(text, "2")


def strong(text):
    return _style(text, "1")


def accent(text):
    return _style(text, accent_code())


def danger(text):
    text = str(text)
    if use_color():
        return _style(text, "1;7")
    return "[%s]" % text.strip()


def accent_code():
    value = os.environ.get("DOJO_ACCENT", "")
    if re.fullmatch(r"\d+", value):
        color_index = int(value)
        if color_index <= 255:
            return "38;5;%d" % color_index
    if re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        red, green, blue = (
            int(value[index:index + 2], 16)
            for index in (1, 3, 5)
        )
        return "38;2;%d;%d;%d" % (red, green, blue)
    return "38;5;208"


def terminal_width():
    columns = shutil.get_terminal_size((72, 24)).columns
    return 72 if columns < 40 else min(columns, 72)


def rule(is_strong=False):
    width = terminal_width()
    if is_strong:
        return strong(glyph("strong_rule") * width)
    return muted(glyph("hairline") * width)


def dots(found, total):
    found = max(0, min(found, total))
    return glyph("found") * found + glyph("empty") * (total - found)


def score_bar(fraction, cells=10):
    cells = max(0, cells)
    filled = max(0, min(cells, int(round(float(fraction) * cells))))
    return glyph("strong_rule") * filled + muted(glyph("hairline") * (cells - filled))


def kv(key, value):
    return "%s %s" % (muted(chrome(key).ljust(14)), str(value).rjust(12))


def input_prompt(label=None, is_content=False):
    marker = accent(glyph("prompt"))
    if not label:
        return "%s " % marker
    if is_content:
        return "%s %s" % (marker, label)
    return "%s %s " % (marker, muted(chrome(label)))


def question(text):
    print("%s %s" % (glyph("question"), text))


def footer(*hints):
    print(muted(chrome((" %s " % glyph("separator")).join(str(hint) for hint in hints))))


def box_open():
    print(rule())


def box_close():
    print(rule())


def read_answer(label=None):
    return read_input(input_prompt(label))


def read_input(prompt):
    try:
        return input(prompt)
    finally:
        if not sys.stdin.isatty():
            print()


def print_answer_reveal(answer, explain=None, confidence=None):
    print("%s  %s" % (chrome("Answer"), answer))
    if explain and explain != answer:
        print(explain)
    print_confidence(confidence)


def print_confidence(confidence):
    if confidence:
        print(muted("%s  %s" % (chrome("Confidence"), confidence)))


def load_json_items(path):
    with path.open(encoding="utf-8") as stream:
        data = json.load(stream)
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "id" in data:
        return [data]
    if isinstance(data, dict):
        result = []
        for value in data.values():
            if isinstance(value, list):
                result.extend(value)
            elif isinstance(value, dict) and "id" in value:
                result.append(value)
        return result
    raise ValueError("%s must contain an item or a list of items" % path)


def support_source_keys():
    path = BASE_DIR / "content" / "support" / "SOURCES.md"
    if not path.is_file():
        return set()
    keys = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        key = line.split("|", 2)[1].strip()
        if re.fullmatch(r"[A-Z][A-Z0-9-]*", key):
            keys.add(key)
    return keys


def load_content(home):
    content_dir = BASE_DIR / "content"
    content = {
        "flash": [
            item
            for path in sorted(content_dir.glob("cards*.json"))
            for item in load_json_items(path)
        ],
        "drill": load_json_items(content_dir / "drills.json"),
        "combo": [
            item
            for path in sorted(content_dir.glob("scenarios*.json"))
            for item in load_json_items(path)
        ],
        "commands": load_json_items(content_dir / "commands.json"),
    }
    custom_dir = home / "content"
    if custom_dir.exists():
        for path in sorted(custom_dir.glob("*.json")):
            for item in load_json_items(path):
                if "root_cause" in item:
                    content["combo"].append(item)
                elif "kind" in item:
                    content["drill"].append(item)
                else:
                    content["flash"].append(item)
    return content


def _validate_shared_item(item, kind, required, ids, source_keys):
    missing = required - set(item)
    if missing:
        raise ValueError("%s %s is missing %s" % (kind, item.get("id"), sorted(missing)))
    if item["id"] in ids:
        raise ValueError("duplicate content id: %s" % item["id"])
    if item["topic"] not in CONTENT_TOPICS:
        raise ValueError("invalid topic %r in %s" % (item["topic"], item["id"]))
    if kind in ("flash", "combo") and "source" in item:
        source = item["source"]
        if not isinstance(source, str):
            raise ValueError("invalid source keys in %s %s" % (kind, item["id"]))
        unknown_sources = [key for key in source.split(", ") if key not in source_keys]
        if not source or unknown_sources:
            raise ValueError(
                "invalid source keys in %s %s: %s" %
                (kind, item["id"], ", ".join(unknown_sources or [source]))
            )
    ids.add(item["id"])


def _validate_flash_item(item, ids, source_keys):
    _validate_shared_item(item, "flash", FLASH_REQUIRED_FIELDS, ids, source_keys)
    if (
        not isinstance(item["answers"], list)
        or not item["answers"]
        or not isinstance(item["keywords"], list)
    ):
        raise ValueError("invalid flash answers or keywords: %s" % item["id"])
    if "choices" in item and (
        len(item["choices"]) != 4 or item["answers"][0] not in item["choices"]
    ):
        raise ValueError("invalid multiple-choice answers: %s" % item["id"])


def _validate_drill_item(item, ids, source_keys):
    _validate_shared_item(item, "drill", DRILL_REQUIRED_FIELDS, ids, source_keys)
    if item["kind"] not in ("answer", "check"):
        raise ValueError("invalid drill kind: %s" % item["id"])
    if item["kind"] == "answer" and "truth" not in item:
        raise ValueError("answer drill has no truth command: %s" % item["id"])
    if item["kind"] == "check" and "check" not in item:
        raise ValueError("check drill has no check command: %s" % item["id"])


def _validate_scenario_question(item, question):
    choices = item[question].get("choices", [])
    answer = item[question].get("answer")
    if len(choices) != 4 or type(answer) is not int or not 0 <= answer < len(choices):
        raise ValueError("invalid %s answer index: %s" % (question, item["id"]))


def _validate_scenario_command(item, command, command_ids, patterns):
    missing = {"id", "match", "output", "evidence", "source"} - set(command)
    if missing:
        raise ValueError(
            "scenario command in %s is missing %s" % (item["id"], sorted(missing))
        )
    if command["id"] in command_ids:
        raise ValueError("duplicate command id in %s: %s" % (item["id"], command["id"]))
    if command["source"] not in ("recorded", "simulated"):
        raise ValueError("invalid command source in %s: %s" % (item["id"], command["id"]))
    if not isinstance(command["evidence"], bool):
        raise ValueError("invalid evidence flag in %s: %s" % (item["id"], command["id"]))
    command_ids.add(command["id"])
    if not command.get("match"):
        raise ValueError("command has no match patterns: %s" % item["id"])
    for pattern in command["match"]:
        patterns.append(re.compile(pattern, re.IGNORECASE))


def _validate_scenario_commands(item):
    patterns = []
    command_ids = set()
    for command in item["commands"]:
        _validate_scenario_command(item, command, command_ids, patterns)
    for optimal in item["optimal"]:
        normalized = normalize_whitespace(optimal)
        if not any(pattern.fullmatch(normalized) for pattern in patterns):
            raise ValueError("unmatched optimal command %r in %s" % (optimal, item["id"]))


def _validate_scenario_item(item, ids, source_keys):
    _validate_shared_item(item, "combo", SCENARIO_REQUIRED_FIELDS, ids, source_keys)
    if not isinstance(item["turns"], int) or item["turns"] < 1:
        raise ValueError("invalid turn count: %s" % item["id"])
    _validate_scenario_question(item, "root_cause")
    _validate_scenario_question(item, "fix")
    _validate_scenario_commands(item)


def _validate_command_identity(card, ids):
    missing = COMMAND_REQUIRED_FIELDS - set(card)
    if missing:
        raise ValueError("command card %s is missing %s" % (card.get("id"), sorted(missing)))
    if card["id"] in ids:
        raise ValueError("duplicate content id: %s" % card["id"])
    ids.add(card["id"])
    if card["category"] not in CATEGORIES:
        raise ValueError("invalid category %r in %s" % (card["category"], card["id"]))
    if type(card["tier"]) is not int or card["tier"] not in (1, 2, 3):
        raise ValueError("invalid tier in %s" % card["id"])
    if card["kind"] not in ("write", "fix"):
        raise ValueError("invalid command kind in %s" % card["id"])
    if not isinstance(card["answers"], list) or not card["answers"]:
        raise ValueError("command card has no answers: %s" % card["id"])
    if "blank" in card and (
        not isinstance(card["blank"], str)
        or not card["blank"]
        or card["blank"] not in card["answers"][0]
    ):
        raise ValueError("invalid fill-in blank in %s" % card["id"])
    if card["kind"] == "fix" and not {"broken", "error"}.issubset(card):
        raise ValueError("fix card is missing broken or error: %s" % card["id"])


def _validate_command_answer(card, answer):
    if card["category"] == "shell":
        try:
            shlex.split(answer)
        except ValueError as error:
            raise ValueError("invalid shell answer in %s: %s" % (card["id"], error))
        return
    if card["category"] == "slash":
        if not slash_answer_matches(answer, answer):
            raise ValueError("invalid slash answer in %s: %s" % (card["id"], answer))
        return
    try:
        parse_devin_command(answer)
    except CommandParseError as error:
        raise ValueError("invalid Devin answer in %s: %s" % (card["id"], error))


def _validate_command_card(card, ids):
    _validate_command_identity(card, ids)
    for answer in card["answers"]:
        _validate_command_answer(card, answer)
    if card["kind"] == "fix" and command_answer_matches(card["broken"], card):
        raise ValueError("fix card broken command matches its answer: %s" % card["id"])


def _validate_command_categories(cards):
    empty_categories = []
    for category in CATEGORIES:
        if not any(card["category"] == category for card in cards):
            empty_categories.append(category)
    if empty_categories:
        raise ValueError("empty command categories: %s" % ", ".join(empty_categories))


def validate_content(content):
    ids = set()
    source_keys = support_source_keys()
    for item in content["flash"]:
        _validate_flash_item(item, ids, source_keys)
    for item in content["drill"]:
        _validate_drill_item(item, ids, source_keys)
    for item in content["combo"]:
        _validate_scenario_item(item, ids, source_keys)
    command_cards = content.get("commands", [])
    for card in command_cards:
        _validate_command_card(card, ids)
    _validate_command_categories(command_cards)
    return True


def level_for_xp(xp):
    return int(math.sqrt(max(0, xp) / 50)) + 1


def title_for_level(level):
    return TITLES.get(level, "Staff RCA")


def streak_multiplier(streak):
    return min(1 + 0.25 * streak, 3.0)


def levelled_xp(base, global_multiplier):
    return int(round(base * global_multiplier))


def combo_score(evidence_found, unused_turns, best_combo, root_correct, fix_correct):
    base = max(0, 50 + 10 * evidence_found + 5 * unused_turns)
    if not root_correct:
        base = max(0, base - 20)
    if fix_correct:
        base += 25
    return base * max(1, best_combo)


def default_state():
    return {
        "xp": 0,
        "streak": 0,
        "daily_streak": 0,
        "last_session_date": None,
        "sessions": 0,
        "items": {},
    }


def dojo_home():
    configured = os.environ.get("PROFESSOR_HOME") or os.environ.get("DOJO_HOME")
    return Path(configured).expanduser() if configured else Path.home() / ".professor-devin"


def load_state(home):
    path = home / "state.json"
    if not path.exists():
        return default_state()
    with path.open(encoding="utf-8") as stream:
        state = json.load(stream)
    base = default_state()
    base.update(state)
    if not isinstance(base.get("items"), dict):
        raise ValueError("state.json items must be an object")
    return base


def save_state(home, state):
    home.mkdir(parents=True, exist_ok=True)
    target = home / "state.json"
    temporary = home / ".state.json.tmp"
    temporary.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(str(temporary), str(target))


def parse_time(value):
    if not value:
        return None
    parsed = dt.datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.astimezone()
    return parsed


def review_item(state, item_id, correct, now=None):
    now = now or dt.datetime.now().astimezone()
    items = state.setdefault("items", {})
    progress = items.setdefault(item_id, {"box": 1, "seen": 0, "correct": 0})
    progress["seen"] = progress.get("seen", 0) + 1
    if correct:
        progress["correct"] = progress.get("correct", 0) + 1
        progress["box"] = min(5, progress.get("box", 1) + 1)
        days = BOX_INTERVALS[progress["box"]]
        progress["due"] = (now + dt.timedelta(days=days)).isoformat()
    else:
        progress["box"] = 1
        progress["due"] = now.isoformat()
    progress["last_seen"] = now.isoformat()
    return progress


def select_item(items, state, new_seen, rng, now=None, played=None):
    now = now or dt.datetime.now().astimezone()
    played = set() if played is None else played
    progress_by_id = state.get("items", {})
    shuffled = list(items)
    rng.shuffle(shuffled)

    due = []
    new = []
    not_due = []
    for item in shuffled:
        if item["id"] in played:
            continue
        progress = progress_by_id.get(item["id"])
        if progress is None:
            new.append(item)
            continue
        due_date = parse_time(progress.get("due"))
        if due_date is None or due_date <= now:
            due.append((due_date or now, item))
        else:
            not_due.append((progress.get("box", 1), due_date, item))
    if due:
        due.sort(key=lambda pair: pair[0])
        return due[0][1]
    if len(new_seen) < 5 and new:
        return new[0]
    if not_due:
        not_due.sort(key=lambda row: (row[0], row[1]))
        return not_due[0][2]
    if new:
        return new[0]
    return None


class CommandParseError(ValueError):
    def __init__(self, kind, message, token=None, path=()):
        super().__init__(message)
        self.kind = kind
        self.token = token
        self.path = tuple(path)


def _usage_path(usage):
    tokens = re.findall(r"\[[^\]]+\]|<[^>]+>|[^\s]+", usage)
    path = []
    for token in tokens:
        if token == "devin":
            continue
        if token.startswith(("-", "[", "<")):
            break
        path.append(token)
    return tuple(path)


@lru_cache(maxsize=1)
def help_index():
    index = {
        "commands": {},
        "aliases": {},
        "options": {},
        "usages": {},
        "usages_all": {},
        "files": {},
        "descriptions": {},
        "help_lines": {},
    }
    for path in sorted(COMMAND_HELP_DIR.glob("*.txt")):
        if path.name != "slash.txt":
            _add_help_file(index, path)
    return index


def _help_usage(lines):
    usage_line = next((line for line in lines if line.startswith("Usage:")), None)
    if not usage_line:
        return None
    usage = usage_line.split(":", 1)[1].strip()
    variants = []
    in_usage = False
    for line in lines:
        if line.startswith("Usage:"):
            variants.append(line)
            in_usage = True
        elif in_usage and not line.strip():
            in_usage = False
        elif in_usage and line.strip().startswith("devin "):
            variants.append(line.strip())
        elif in_usage:
            in_usage = False
    variants = [
        variant if variant.startswith("Usage:") else "Usage: " + variant
        for variant in variants
    ]
    return usage_line, _usage_path(usage), variants


def _add_help_file(index, path):
    lines = path.read_text(encoding="utf-8").splitlines()
    usage = _help_usage(lines)
    if usage is None:
        return
    usage_line, command_path, variants = usage
    index["usages"][command_path] = usage_line
    index["usages_all"][command_path] = variants
    index["files"][command_path] = path.name
    index["help_lines"][command_path] = lines
    _parse_help_sections(lines, command_path, index)


def _parse_help_sections(lines, command_path, index):
    section = None
    for line in lines:
        stripped = line.strip()
        if stripped in ("Commands:", "Options:"):
            section = stripped[:-1].lower()
            continue
        if stripped.endswith(":"):
            section = None
            continue
        if not stripped:
            if section == "commands":
                section = None
            continue
        if section == "commands":
            _add_help_command(line, command_path, index)
        else:
            _add_help_option(line, command_path, index["options"])


def _add_help_command(line, command_path, index):
    match = re.match(r"^\s{2}([A-Za-z][A-Za-z0-9-]*)\s{2,}(.*?)\s*$", line)
    if not match:
        return
    name, description = match.groups()
    child_path = command_path + (name,)
    index["commands"].setdefault(command_path, {})[name] = description
    index["descriptions"][child_path] = description
    alias_match = re.search(r"\[aliases?:\s*([^\]]+)\]", description)
    if not alias_match:
        return
    for alias in re.findall(r"[A-Za-z][A-Za-z0-9-]*", alias_match.group(1)):
        index["aliases"][command_path + (alias,)] = child_path


def _add_help_option(line, command_path, options):
    match = re.match(r"^\s{2,}((?:-[A-Za-z],\s*)?--[A-Za-z][A-Za-z0-9-]*|-[A-Za-z])(.*)$", line)
    if not match:
        return
    flag_text, tail = match.groups()
    flag_names = re.findall(r"--[A-Za-z][A-Za-z0-9-]*|-[A-Za-z]", flag_text)
    long_name = next((name for name in flag_names if name.startswith("--")), flag_names[0])
    optional_value = re.search(r"\[<([^>]+)>\]", tail)
    required_value = re.search(r"(?<!\[)<([^>]+)>", tail)
    value_name = (
        optional_value.group(1) if optional_value
        else required_value.group(1) if required_value
        else None
    )
    specification = {
        "long": long_name,
        "aliases": flag_names,
        "value": value_name,
        "optional": bool(optional_value),
        "line": line.strip(),
    }
    scoped = options.setdefault(command_path, {})
    for name in flag_names:
        scoped[name] = specification


def _option_for(index, path, name):
    path = tuple(path)
    for depth in range(len(path), -1, -1):
        specification = index["options"].get(path[:depth], {}).get(name)
        if specification:
            return specification
    return None


def _child_for(index, path, word):
    path = tuple(path)
    child = index["commands"].get(path, {}).get(word)
    if child is not None:
        return word
    alias_path = index["aliases"].get(path + (word,))
    return alias_path[-1] if alias_path else None


def _suggestion(value, options):
    choices = sorted(set(options))
    match = difflib.get_close_matches(value, choices, n=1, cutoff=0.55)
    return match[0] if match else None


def _is_value_placeholder(value):
    return isinstance(value, str) and value.startswith("<") and value.endswith(">")


def _usage_for_path(index, path):
    usage_path = path
    usage = index["usages"].get(path)
    for depth in range(len(path) - 1, -1, -1):
        if usage is not None:
            break
        usage_path = path[:depth]
        usage = index["usages"].get(usage_path)
    return usage_path, usage


def _positionals_for_usage(index, path, usage_path, variant):
    tokens = variant.split(":", 1)[1].split()
    path_cursor = 0
    minimum = 0
    maximum = 0
    unbounded = False
    while tokens:
        token = tokens.pop(0)
        if token == "devin":
            continue
        if path_cursor < len(path) and token == path[path_cursor]:
            path_cursor += 1
            continue
        if token.startswith("[") and "OPTIONS" in token:
            continue
        if path == () and token in ("[--", "--"):
            unbounded = True
            break
        if token.startswith("-"):
            option = _option_for(index, path, token.split("=", 1)[0])
            if option and option["value"] and "=" not in token and tokens:
                tokens.pop(0)
            continue
        if token in ("<COMMAND>", "[COMMAND]") and usage_path in index["commands"]:
            return 0, None, True
        if not re.search(r"<([^>]+)>|\b([A-Z][A-Z0-9_]*)\b", token):
            continue
        optional = token.startswith("[")
        variadic = "..." in token
        if not optional:
            minimum += 1
        maximum += 1
        if variadic:
            unbounded = True
    maximum_value = None if unbounded else maximum
    return minimum, maximum_value, False


def _expected_positionals(index, path):
    usage_path, usage = _usage_for_path(index, path)
    if usage is None:
        return 0, None
    variants = index.get("usages_all", {}).get(path, [usage])
    ranges = []
    for variant in variants:
        minimum, maximum, needs_subcommand = _positionals_for_usage(
            index,
            path,
            usage_path,
            variant,
        )
        if needs_subcommand:
            return 0, None
        ranges.append((minimum, maximum))
    if not ranges:
        return 0, None
    minimum = min(value[0] for value in ranges)
    maximum = None if any(value[1] is None for value in ranges) else max(
        value[1] for value in ranges
    )
    return minimum, maximum


def _raise_unknown_flag(name, path, index):
    choices = []
    for depth in range(len(path), -1, -1):
        for alias in index["options"].get(tuple(path[:depth]), {}):
            if alias.startswith("-"):
                choices.append(alias)
    suggestion = _suggestion(name, choices)
    suffix = " (did you mean %s?)" % suggestion if suggestion else ""
    raise CommandParseError(
        "flag",
        "Unknown flag %s%s" % (name, suffix),
        name,
        tuple(path),
    )


def _consume_path_flag(arguments, cursor, path, index):
    token = arguments[cursor]
    name = token.split("=", 1)[0]
    option = _option_for(index, path, name)
    if option is None:
        _raise_unknown_flag(name, path, index)
    cursor += 1
    if option["value"] and "=" not in token:
        if not option["optional"] or (
            cursor < len(arguments) and not arguments[cursor].startswith("-")
        ):
            cursor += 1
    return cursor


def _unknown_subcommand(token, path, index):
    if path and tuple(path) in index["usages"]:
        usage = index["usages"][tuple(path)]
        if "<COMMAND>" in usage or "<command>" in usage:
            choices = index["commands"].get(tuple(path), {})
            suggestion = _suggestion(token, choices)
            suffix = " (did you mean %s?)" % suggestion if suggestion else ""
            return CommandParseError(
                "subcommand",
                "Unknown sub-command %r under devin %s%s" %
                (token, " ".join(path), suffix),
                token,
                path,
            )
    if not path:
        choices = index["commands"].get((), {})
        suggestion = _suggestion(token, choices)
        if suggestion:
            return CommandParseError(
                "subcommand",
                "Unknown sub-command %r under devin (did you mean %s?)" %
                (token, suggestion),
                token,
                path,
            )
    return None


def _command_path(arguments, index):
    path = []
    path_indices = set()
    cursor = 0
    while cursor < len(arguments):
        token = arguments[cursor]
        if token == "--":
            break
        if token.startswith("-"):
            cursor = _consume_path_flag(arguments, cursor, path, index)
            continue
        child = _child_for(index, path, token)
        if child is None:
            error = _unknown_subcommand(token, path, index)
            if error:
                raise error
            break
        path_indices.add(cursor)
        path.append(child)
        cursor += 1
    return tuple(path), path_indices


def _validate_command_path(command_path, index):
    usage = index["usages"].get(command_path, "")
    if "<COMMAND>" not in usage and "<command>" not in usage:
        return
    choices = sorted(index["commands"].get(command_path, {}))
    raise CommandParseError(
        "subcommand",
        "Missing sub-command after devin %s (choose %s)" %
        (" ".join(command_path), ", ".join(choices)),
        path=command_path,
    )


def _parse_flag_argument(arguments, cursor, command_path, index):
    token = arguments[cursor]
    name, equals, inline_value = token.partition("=")
    option = _option_for(index, command_path, name)
    if option is None:
        _raise_unknown_flag(name, command_path, index)
    value = inline_value if equals else None
    if value is not None and not option["value"]:
        raise CommandParseError(
            "flag-value",
            "Flag %s does not take a value" % name,
            name,
            command_path,
        )
    next_cursor = cursor + 1
    if option["value"] and value is None:
        if next_cursor < len(arguments) and (
            not option["optional"] or not arguments[next_cursor].startswith("-")
        ):
            value = arguments[next_cursor]
            next_cursor += 1
        elif not option["optional"]:
            raise CommandParseError(
                "missing-value",
                "Flag %s requires a value" % name,
                name,
                command_path,
            )
    return (option["long"], value), next_cursor


def _command_arguments(arguments, command_path, path_indices, index):
    parsed_flags = []
    positionals = []
    cursor = 0
    while cursor < len(arguments):
        if cursor in path_indices:
            cursor += 1
            continue
        token = arguments[cursor]
        if token == "--":
            remaining = arguments[cursor + 1:]
            if command_path:
                positionals.extend(remaining)
            else:
                prompt = " ".join(remaining)
                if prompt:
                    positionals.append(prompt)
            break
        if token.startswith("-"):
            flag, cursor = _parse_flag_argument(arguments, cursor, command_path, index)
            parsed_flags.append(flag)
            continue
        positionals.append(token)
        cursor += 1
    return parsed_flags, positionals


def _validate_positional_count(positionals, command_path, index):
    minimum, maximum = _expected_positionals(index, command_path)
    if len(positionals) < minimum:
        raise CommandParseError(
            "positional-count",
            "Expected at least %d positional argument(s), got %d" %
            (minimum, len(positionals)),
            path=command_path,
        )
    if maximum is not None and len(positionals) > maximum:
        raise CommandParseError(
            "positional-count",
            "Expected at most %d positional argument(s), got %d" %
            (maximum, len(positionals)),
            path=command_path,
        )


def parse_devin_command(command, index=None):
    index = index or help_index()
    try:
        tokens = shlex.split(command)
    except ValueError as error:
        raise CommandParseError("syntax", "Invalid shell quoting: %s" % error)
    if not tokens or tokens[0].lower() != "devin":
        raise CommandParseError("prefix", "Command must start with devin")
    arguments = tokens[1:]
    command_path, path_indices = _command_path(arguments, index)
    _validate_command_path(command_path, index)
    flags, positionals = _command_arguments(arguments, command_path, path_indices, index)
    _validate_positional_count(positionals, command_path, index)
    return {
        "path": command_path,
        "flags": flags,
        "positionals": positionals,
        "help_file": index["files"].get(command_path),
    }


def _flag_value_matches(actual_value, expected_value):
    if _is_value_placeholder(expected_value):
        return actual_value is not None
    return actual_value == expected_value


def _find_matching_flag(flags, expected_name, expected_value):
    for position, (name, value) in enumerate(flags):
        if name == expected_name and _flag_value_matches(value, expected_value):
            return position
    return None


def _parsed_commands_match(actual, expected):
    if actual["path"] != expected["path"]:
        return False
    if len(actual["flags"]) != len(expected["flags"]):
        return False
    remaining = list(actual["flags"])
    for expected_name, expected_value in expected["flags"]:
        match_index = _find_matching_flag(remaining, expected_name, expected_value)
        if match_index is None:
            return False
        remaining.pop(match_index)
    if len(actual["positionals"]) != len(expected["positionals"]):
        return False
    pairs = zip(actual["positionals"], expected["positionals"])
    return all(_flag_value_matches(value, wanted) for value, wanted in pairs)


def slash_commands():
    path = COMMAND_HELP_DIR / "slash.txt"
    if not path.exists():
        return {}
    commands = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        name, source = line.split("\t", 1)
        commands[name] = source
    return commands


def _command_parse_feedback(error):
    message = str(error)
    labels = (
        "Unknown sub-command",
        "Missing sub-command",
        "Unknown flag",
        "Flag",
        "Expected",
        "Invalid shell quoting",
        "Command must start with devin",
    )
    for label in labels:
        if message.startswith(label):
            return chrome(label) + message[len(label):]
    return message


def _command_mismatch_feedback(actual, expected):
    if _parsed_commands_match(actual, expected):
        return ""
    feedback = []
    if actual["path"] != expected["path"]:
        feedback.append("%s: devin %s" % (
            chrome("Use sub-command path"),
            " ".join(expected["path"]),
        ))
    actual_names = [name for name, _ in actual["flags"]]
    expected_names = [name for name, _ in expected["flags"]]
    for name in expected_names:
        if name not in actual_names:
            feedback.append("%s: %s" % (chrome("Missing flag"), name))
    for name in actual_names:
        if name not in expected_names:
            feedback.append("%s: %s" % (chrome("Unexpected extra flag"), name))
    for name, wanted in expected["flags"]:
        values = [value for actual_name, value in actual["flags"] if actual_name == name]
        if values and not any(
            (_is_value_placeholder(wanted) and value is not None) or value == wanted
            for value in values
        ):
            feedback.append("%s %s" % (chrome("Wrong value for flag"), name))
    if len(actual["positionals"]) != len(expected["positionals"]):
        feedback.append(
            "%s: expected %d, got %d" % (
                chrome("Wrong positional count"),
                len(expected["positionals"]),
                len(actual["positionals"]),
            )
        )
    elif actual["positionals"] != expected["positionals"]:
        feedback.append(chrome("Wrong positional argument"))
    return "; ".join(feedback) or chrome(
        "The command does not match the required flags and arguments"
    )


def command_feedback(command, card, index=None):
    index = index or help_index()
    try:
        actual = parse_devin_command(command, index)
        expected = parse_devin_command(card["answers"][0], index)
    except CommandParseError as error:
        return _command_parse_feedback(error)
    return _command_mismatch_feedback(actual, expected)


def normalize_shell_command(command):
    try:
        return " ".join(shlex.split(command))
    except ValueError:
        return " ".join(command.split())


def shell_command_matches(command, answer):
    try:
        actual = shlex.split(command)
        expected = shlex.split(answer)
    except ValueError:
        return False
    if len(actual) != len(expected):
        return False
    for value, wanted in zip(actual, expected):
        if value == wanted:
            continue
        pattern = "".join(
            r".+" if re.fullmatch(r"<[^<>]+>", part) else re.escape(part)
            for part in re.split(r"(<[^<>]+>)", wanted)
        )
        if not re.fullmatch(pattern, value):
            return False
    return True


def slash_answer_matches(command, answer):
    try:
        actual = shlex.split(command)
        expected = shlex.split(answer)
    except ValueError:
        return False
    if not actual or not expected or actual[0] != expected[0]:
        return False
    allowed = slash_commands()
    if actual[0] not in allowed or len(actual) != len(expected):
        return False
    return all(
        (
            _is_value_placeholder(wanted)
            and value is not None
        ) or value == wanted
        for value, wanted in zip(actual[1:], expected[1:])
    )


def command_answer_matches(command, card, index=None):
    if card["category"] == "shell":
        return any(shell_command_matches(command, answer) for answer in card["answers"])
    if card["category"] == "slash":
        return any(slash_answer_matches(command, answer) for answer in card["answers"])
    index = index or help_index()
    try:
        actual = parse_devin_command(command, index)
    except CommandParseError:
        return False
    for answer in card["answers"]:
        try:
            expected = parse_devin_command(answer, index)
        except CommandParseError:
            continue
        if _parsed_commands_match(actual, expected):
            return True
    return False


def command_blank(card):
    if card.get("blank"):
        return card["blank"]
    try:
        tokens = shlex.split(card["answers"][0])
    except (IndexError, ValueError):
        return ""
    flag = next((token for token in tokens if token.startswith("-")), None)
    if flag:
        return flag
    if card["category"] not in ("slash", "shell"):
        try:
            path = parse_devin_command(card["answers"][0])["path"]
        except CommandParseError:
            path = ()
        if path:
            return path[-1]
    return tokens[0] if tokens else ""


def command_answer_feedback(command, card, index=None):
    index = index or help_index()
    if card["category"] == "shell":
        return chrome("The command must match the documented shell form")
    if card["category"] == "slash":
        try:
            tokens = shlex.split(command)
        except ValueError as error:
            return "%s: %s" % (chrome("Invalid shell quoting"), error)
        if not tokens:
            return chrome("Enter a slash command")
        allowed = slash_commands()
        if tokens[0] not in allowed:
            suggestion = _suggestion(tokens[0], allowed)
            suffix = " (did you mean %s?)" % suggestion if suggestion else ""
            return "%s %s%s" % (chrome("Unknown slash command"), tokens[0], suffix)
        expected = shlex.split(card["answers"][0])
        if tokens[0] != expected[0]:
            return "%s %s" % (chrome("Use slash command"), expected[0])
        if len(tokens) != len(expected):
            return "%s: expected %d, got %d" % (
                chrome("Wrong positional count"),
                len(expected) - 1,
                len(tokens) - 1,
            )
        return chrome("Wrong slash-command argument")
    return command_feedback(command, card, index)


def command_help_lines(card):
    source_file = card.get("source_file")
    if card["category"] == "slash":
        try:
            command = shlex.split(card["answers"][0])[0]
        except (IndexError, ValueError):
            return []
        source = slash_commands().get(command)
        return ["content/help/slash.txt: %s\t%s" % (command, source)] if source else []
    if card["category"] == "shell":
        source = card.get("source", "")
        match = re.fullmatch(r"\.\./GUIDE\.md:(\d+)", source)
        if match:
            line_number = int(match.group(1))
            guide_path = BASE_DIR.parent / "GUIDE.md"
            lines = guide_path.read_text(encoding="utf-8").splitlines()
            if 1 <= line_number <= len(lines):
                return ["../GUIDE.md:%d: %s" % (line_number, lines[line_number - 1].strip())]
        return [source] if source else []
    if not source_file:
        return []
    path = COMMAND_HELP_DIR / source_file
    if not path.is_file():
        return []
    try:
        parsed = parse_devin_command(card["answers"][0])
    except CommandParseError:
        parsed = {"flags": []}
    selected = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("Usage:"):
            selected.append(line.strip())
        elif line.startswith("  ") and any(
            flag in line.split()[:2]
            for flag, _ in parsed.get("flags", [])
        ):
            selected.append(line.strip())
    return ["content/help/%s: %s" % (source_file, line) for line in selected]


def normalize(value):
    value = str(value).lower().replace("'", "").replace('"', "").replace("`", "")
    return " ".join(value.split())


def normalize_whitespace(value):
    return " ".join(value.split())


def grade_answer(item, response, displayed_choices=None):
    candidate = response
    if displayed_choices and len(response.strip()) == 1:
        letter = response.strip().lower()
        if letter in "abcd":
            index = ord(letter) - ord("a")
            if index < len(displayed_choices):
                candidate = displayed_choices[index]
    candidate_normalized = normalize(candidate)
    answers = [normalize(value) for value in item.get("answers", [])]
    if candidate_normalized in answers:
        return True
    return all(
        normalize(keyword) in candidate_normalized
        for keyword in item.get("keywords", [])
    )


def parse_choice(value, choices, displayed_choices=None):
    candidate = value.strip()
    if len(candidate) == 1 and candidate.lower() in "abcd":
        index = ord(candidate.lower()) - ord("a")
        if displayed_choices is not None and index < len(displayed_choices):
            text = displayed_choices[index]
            return next((i for i, choice in enumerate(choices) if normalize(choice) == normalize(text)), None)
    if candidate.isdigit():
        index = int(candidate) - 1
        if 0 <= index < len(choices):
            return index
    return next((i for i, choice in enumerate(choices) if normalize(choice) == normalize(candidate)), None)


def plan_description(plan):
    labels = {"flash": "Flash", "drill": "Drill", "combo": "Ticket"}
    groups = []
    for category in plan:
        label = labels[category]
        if groups and groups[-1][1] == label:
            groups[-1][0] += 1
        else:
            groups.append([1, label])
    return (" %s " % glyph("separator")).join(
        "%d %s" % (count, label) for count, label in groups
    )


def command_environment(arena):
    env = os.environ.copy()
    env.pop("DEVIN_DESKTOP_AUTH_TOKEN", None)
    local_bin = str(Path.home() / ".local" / "bin")
    path_parts = env.get("PATH", "").split(os.pathsep)
    if local_bin not in path_parts:
        env["PATH"] = local_bin + os.pathsep + env.get("PATH", "")
    env["DOJO_ARENA"] = str(arena)
    return env


def run_shell(command, arena, timeout=30):
    try:
        return subprocess.run(
            command,
            shell=True,
            cwd=str(arena),
            env=command_environment(arena),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as error:
        output = error.stdout or ""
        stderr = error.stderr or ""
        if isinstance(output, bytes):
            output = output.decode(errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode(errors="replace")
        return subprocess.CompletedProcess(command, 124, output, stderr + "\ncommand timed out")


def print_process_output(result):
    output = (result.stdout or "") + (result.stderr or "")
    if output:
        print(output.rstrip("\n"))
    if result.returncode:
        print(muted(chrome("Exit code %s" % result.returncode)))


class Dojo:
    def __init__(self, home, content):
        self.home = home
        self.arena_root = home / "arena"
        self.state = load_state(home)
        self.content = content
        self.rng = random.Random()
        self.new_seen = set()
        self.session_seen = []
        self.session_missed = []
        self.topic_totals = {}
        self.session_xp = 0
        self.best_combo = 1
        self.flash_rounds = 0
        self.flash_requeues = {}
        self.requeued = set()
        self.played = set()
        self.last_flash_id = None
        self.auth_status = None
        self.stop_requested = False
        self.round_attempts = 0
        self.round_correct = 0
        self.category_totals = {}
        self.last_new_category = None
        self.last_new_tier = None
        self.session_hint = None

    def award(self, points):
        old_xp = self.state.get("xp", 0)
        self.state["xp"] = max(0, old_xp + points)
        actual = self.state["xp"] - old_xp
        self.session_xp += actual
        return actual

    def begin_session(self, seed=None):
        if seed is not None:
            self.rng.seed(seed)
        self.new_seen.clear()
        self.played.clear()
        self.flash_rounds = 0
        self.flash_requeues.clear()
        self.requeued.clear()
        self.last_flash_id = None
        self.stop_requested = False
        today = dt.date.today()
        previous = self.state.get("last_session_date")
        if previous == today.isoformat():
            pass
        elif previous:
            previous_date = dt.date.fromisoformat(previous)
            self.state["daily_streak"] = (
                self.state.get("daily_streak", 0) + 1
                if previous_date == today - dt.timedelta(days=1)
                else 1
            )
        else:
            self.state["daily_streak"] = 1
        self.state["last_session_date"] = today.isoformat()
        self.state["sessions"] = self.state.get("sessions", 0) + 1

    def record_round(self, item, correct):
        self.round_attempts += 1
        if correct:
            self.round_correct += 1
        topic = item.get("topic", item.get("category", "unknown"))
        total = self.topic_totals.setdefault(topic, [0, 0])
        total[0] += int(bool(correct))
        total[1] += 1
        progress = review_item(self.state, item["id"], correct)
        progress["topic"] = topic
        self.session_seen.append(item)
        if not correct:
            self.session_missed.append(item)

    def record_command_round(self, item, correct):
        self.record_round(item, correct)
        total = self.category_totals.setdefault(item["category"], [0, 0])
        total[0] += int(bool(correct))
        total[1] += 1

    def global_multiplier(self):
        return streak_multiplier(self.state.get("streak", 0))

    def resolve_streak(self, correct):
        self.state["streak"] = self.state.get("streak", 0) + 1 if correct else 0

    def header(self, item, category, round_number, total_rounds):
        level = level_for_xp(self.state.get("xp", 0))
        multiplier = self.global_multiplier()
        digits = len(str(total_rounds))
        round_label = "%0*d/%0*d" % (
            digits,
            round_number,
            digits,
            total_rounds,
        )
        separator = glyph("separator")
        category_label = {
            "flash": "Flash",
            "drill": "Drill",
            "combo": "Ticket",
        }[category]
        left = chrome("Round %s %s %s %s %s" % (
            round_label,
            separator,
            category_label,
            separator,
            item["topic"],
        ))
        right = chrome("L%d %s %s %d xp %s x%.2f" % (
            level,
            title_for_level(level),
            separator,
            self.state.get("xp", 0),
            separator,
            multiplier,
        ))
        width = terminal_width()
        print()
        if len(left) + len(right) + 1 <= width:
            print(left + " " * (width - len(left) - len(right)) + muted(right))
        else:
            print(left)
            print(muted(right.rjust(width)))
        print()

    def print_session_header(self, description):
        print(strong(chrome("Professor Devin %s %s" % (glyph("separator"), description))))
        print(rule(is_strong=True))
        if self.session_hint:
            print(muted(chrome("Next time: %s" % self.session_hint)))

    def training_header(self, item, form, round_number, total_rounds):
        level = level_for_xp(self.state.get("xp", 0))
        digits = len(str(total_rounds))
        round_label = "%0*d/%0*d" % (digits, round_number, digits, total_rounds)
        left = chrome("Round %s %s %s %s %s" % (
            round_label,
            glyph("separator"),
            item["category"],
            glyph("separator"),
            form,
        ))
        right = chrome("L%d %s %s %d xp %s x%.2f" % (
            level,
            title_for_level(level),
            glyph("separator"),
            self.state.get("xp", 0),
            glyph("separator"),
            self.global_multiplier(),
        ))
        width = terminal_width()
        print()
        if len(left) + len(right) + 1 <= width:
            print(left + " " * (width - len(left) - len(right)) + muted(right))
        else:
            print(left)
            print(muted(right.rjust(width)))
        print()

    def choose_new_command(self, items):
        lowest_tier = min(item["tier"] for item in items)
        tier_items = [item for item in items if item["tier"] == lowest_tier]
        categories = [
            category for category in CATEGORIES
            if any(item["category"] == category for item in tier_items)
        ]
        if self.last_new_tier == lowest_tier and self.last_new_category in categories:
            start = (categories.index(self.last_new_category) + 1) % len(categories)
            categories = categories[start:] + categories[:start]
        category = categories[0]
        choices = [item for item in tier_items if item["category"] == category]
        selected = self.rng.choice(choices)
        self.last_new_tier = lowest_tier
        self.last_new_category = category
        return selected

    def choose_command_item(self, cards):
        now = dt.datetime.now().astimezone()
        progress_by_id = self.state.get("items", {})
        available = [card for card in cards if card["id"] not in self.played]
        if not available:
            return None
        due = []
        new = []
        not_due = []
        for card in available:
            progress = progress_by_id.get(card["id"])
            if progress is None:
                new.append(card)
                continue
            due_date = parse_time(progress.get("due"))
            if due_date is None or due_date <= now:
                due.append((due_date or now, card))
            else:
                not_due.append((progress.get("box", 1), due_date, card))
        if due:
            due.sort(key=lambda pair: pair[0])
            item = due[0][1]
        elif new and len(self.new_seen) < 5:
            item = self.choose_new_command(new)
        elif not_due:
            not_due.sort(key=lambda row: (row[0], row[1]))
            item = not_due[0][2]
        elif new:
            item = self.choose_new_command(new)
        else:
            return None
        if item["id"] not in progress_by_id:
            self.new_seen.add(item["id"])
        self.played.add(item["id"])
        return item

    def command_form(self, card):
        if card["kind"] == "fix":
            return "fix"
        box = self.state.get("items", {}).get(card["id"], {}).get("box", 1)
        return "recognize" if box <= 1 else "fill in" if box == 2 else "recall"

    def recognition_choices(self, card, cards):
        tasks = []
        seen = {card["task"]}
        candidates = []
        for candidate in cards:
            if candidate["id"] == card["id"] or candidate.get("kind") != "write":
                continue
            if candidate.get("category") not in ("slash", "shell"):
                try:
                    path = parse_devin_command(candidate["answers"][0])["path"]
                except (CommandParseError, IndexError):
                    continue
                if "help" in path:
                    continue
            candidates.append(candidate)
        for candidate in candidates:
            if candidate["category"] == card["category"] and candidate["task"] not in seen:
                tasks.append(candidate["task"])
                seen.add(candidate["task"])
        self.rng.shuffle(tasks)
        for candidate in candidates:
            if candidate["task"] not in seen:
                tasks.append(candidate["task"])
                seen.add(candidate["task"])
        choices = [card["task"]] + tasks[:3]
        self.rng.shuffle(choices)
        return choices

    @staticmethod
    def recognized_task(response, choices):
        value = response.strip()
        if len(value) == 1 and value.lower() in "abcd":
            index = ord(value.lower()) - ord("a")
            return choices[index] if index < len(choices) else None
        if value in ("1", "2", "3", "4"):
            index = int(value) - 1
            return choices[index] if index < len(choices) else None
        return next((choice for choice in choices if normalize(choice) == normalize(value)), None)

    def command_hint(self, card):
        if card.get("hint"):
            return card["hint"]
        if card["category"] == "slash":
            command = shlex.split(card["answers"][0])[0]
            return "Look for %s in the slash-command reference." % command
        if card["category"] == "shell":
            return "Use the shell command from the linked GUIDE.md line."
        try:
            parsed = parse_devin_command(card["answers"][0])
        except CommandParseError:
            return "Compare the flags and arguments shown in the prompt."
        command_path = " ".join(parsed["path"])
        return "Look in the help for %s." % (command_path or "the root command")

    def show_command_reveal(self, card, response, form):
        if form not in ("recognize",) and response.strip().lower() != "skip":
            feedback_input = response
            if form == "fill in":
                value = response.strip()
                first_token = card["answers"][0].split(maxsplit=1)[0]
                if value.startswith(first_token):
                    feedback_input = value
                else:
                    feedback_input = card["answers"][0].replace(
                        command_blank(card),
                        value,
                        1,
                    )
            feedback = command_answer_feedback(feedback_input, card)
            if feedback:
                print(muted(feedback))
        print(danger(chrome("Missed")))
        if form == "recognize":
            print("%s  %s" % (chrome("Answer"), card["task"]))
            print("%s  %s" % (chrome("Command"), card["answers"][0]))
        else:
            for canonical in card["answers"]:
                print("%s  %s" % (chrome("Answer"), canonical))
        for line in command_help_lines(card):
            print(muted(line))
        revealed = card["answers"] + ([card["task"]] if form == "recognize" else [])
        if card.get("explain") and card["explain"] not in revealed:
            print(card["explain"])
        print_confidence(card.get("confidence"))

    def show_command_prompt(self, card, cards, form):
        if form == "fix":
            question("Fix this command")
            print("  %s  %s" % (muted(chrome("Broken")), card["broken"]))
            print("  %s  %s" % (muted(chrome("Error")), card["error"]))
        elif form == "recognize":
            question("What does this command do?")
            print("  %s" % card["answers"][0])
            print()
            choices = self.recognition_choices(card, cards)
            for index, choice in enumerate(choices):
                print("  %s %s" % (muted(str(index + 1)), choice))
            return choices
        elif form == "fill in":
            question(card["task"])
            print("  %s" % card["answers"][0].replace(command_blank(card), "___", 1))
        else:
            question(card["task"])
        return None

    COMMAND_FOOTERS = {
        "recognize": ("1-4 to choose", "? hint", "skip", "quit"),
        "fill in": ("type the missing part or the whole command", "? hint", "skip", "quit"),
        "fix": ("type the corrected command", "? hint", "skip", "quit"),
        "recall": ("? hint", "skip", "quit"),
    }

    def handle_command_special_input(self, card, form, choices, response, hint_used):
        value = response.strip()
        if value.lower() == "quit":
            self.stop_requested = True
            return "quit", None, hint_used
        if value == "?":
            if not hint_used:
                print("%s  %s" % (muted(chrome("Hint")), self.command_hint(card)))
                hint_used = True
            else:
                print(muted(chrome("Hint already used")))
            return "hint", False, hint_used
        if value.lower() == "skip":
            return "skip", False, hint_used
        correct = self.command_response_is_correct(card, form, response, choices)
        return "answer", correct, hint_used

    def command_response_is_correct(self, card, form, response, choices):
        if form == "recognize":
            selected = self.recognized_task(response, choices)
            return selected is not None and normalize(selected) == normalize(card["task"])
        if form == "fill in":
            value = response.strip()
            if command_answer_matches(value, card):
                return True
            candidate = card["answers"][0].replace(command_blank(card), value, 1)
            return command_answer_matches(candidate, card)
        return command_answer_matches(response, card)

    def record_missed_command_card(self, card, form, response, hint_used):
        self.show_command_reveal(card, response, form)
        count_it = read_answer("Count it as correct? y/n")
        if count_it.strip().lower() == "y":
            self.record_command_round(card, True)
            self.award_command_xp(form, hint_used, True)
            self.resolve_streak(True)
            print("%s %s" % (
                strong("%s %s" % (glyph("found"), chrome("Counted"))),
                muted("+%d xp" % self.last_command_xp),
            ))
            return True
        self.record_command_round(card, False)
        self.resolve_streak(False)
        return False

    def record_correct_command_card(self, card, form, hint_used):
        self.record_command_round(card, True)
        self.award_command_xp(form, hint_used, False)
        self.resolve_streak(True)
        print("%s %s" % (
            strong("%s %s" % (glyph("found"), chrome("Correct"))),
            muted("+%d xp" % self.last_command_xp),
        ))

    def ask_command_card(self, card, cards, form):
        choices = self.show_command_prompt(card, cards, form)
        print()
        footer(*self.COMMAND_FOOTERS[form])
        box_open()
        hint_used = False
        while True:
            response = read_answer()
            action, correct, hint_used = self.handle_command_special_input(
                card,
                form,
                choices,
                response,
                hint_used,
            )
            if action == "hint":
                continue
            break
        box_close()
        if action == "quit":
            print("%s %s" % (glyph("quit"), muted(chrome("Session ended"))))
            return None
        if action == "skip":
            self.show_command_reveal(card, response, form)
            self.record_command_round(card, False)
            self.resolve_streak(False)
            return correct
        if not correct:
            return self.record_missed_command_card(card, form, response, hint_used)
        self.record_correct_command_card(card, form, hint_used)
        return True

    def award_command_xp(self, form, hint_used, self_graded):
        base = {"recognize": 5, "fill in": 10, "recall": 15, "fix": 15}[form]
        if hint_used or self_graded:
            base //= 2
        self.last_command_xp = self.award(levelled_xp(base, self.global_multiplier()))

    def next_new_up(self, cards):
        remaining = [card for card in cards if card["id"] not in self.state.get("items", {})]
        if not remaining:
            tier = max((card["tier"] for card in cards), default=1)
            category = self.last_new_category or (cards[0]["category"] if cards else CATEGORIES[0])
            return 0, tier, category
        tier = min(card["tier"] for card in remaining)
        categories = [
            category for category in CATEGORIES
            if any(card["category"] == category and card["tier"] == tier for card in remaining)
        ]
        if self.last_new_tier == tier and self.last_new_category in categories:
            start = (categories.index(self.last_new_category) + 1) % len(categories)
            categories = categories[start:] + categories[:start]
        category = categories[0]
        count = sum(
            card["category"] == category and card["tier"] == tier
            for card in remaining
        )
        return count, tier, category

    def train(self, categories=None, rounds=10, tier=3, seed=None):
        categories = list(categories or CATEGORIES)
        filtered = [
            card for card in self.content["commands"]
            if card["category"] in categories and card["tier"] <= tier
        ]
        if not filtered:
            raise ValueError("no command cards match the selected categories and tier")
        self.begin_session(seed)
        self.category_totals.clear()
        self.last_new_category = None
        self.last_new_tier = None
        self.print_session_header("Train %s %d command rounds %s 1 ticket boss" % (
            glyph("separator"),
            rounds,
            glyph("separator"),
        ))
        try:
            for round_number in range(rounds):
                card = self.choose_command_item(filtered)
                if card is None:
                    print(muted(chrome("No eligible command cards; ending session")))
                    break
                form = self.command_form(card)
                self.training_header(card, form, round_number + 1, rounds + 1)
                result = self.ask_command_card(card, filtered, form)
                if result is None or self.stop_requested:
                    break
            if not self.stop_requested:
                scenarios = self.content["combo"]
                matching = [scenario for scenario in scenarios if scenario.get("topic") in categories]
                ticket = self.rng.choice(matching or scenarios) if scenarios else None
                if ticket:
                    self.header(ticket, "combo", rounds + 1, rounds + 1)
                    self.play_combo(ticket)
        except EOFError:
            print("\n%s %s" % (glyph("quit"), muted(chrome("Input ended; saving progress"))))
        except KeyboardInterrupt:
            print("\n%s %s" % (glyph("quit"), muted(chrome("Interrupted; saving progress"))))
        self.print_summary(training=True, next_up=self.next_new_up(filtered))
        save_state(self.home, self.state)

    def eligible_drills(self, topic_filter, no_live, allow_credits):
        if no_live:
            return []
        platform = "darwin" if sys.platform == "darwin" else "linux" if sys.platform.startswith("linux") else "win32"
        eligible = []
        for drill in self.content["drill"]:
            if topic_filter and not topic_filter.search(drill["topic"]):
                continue
            if platform not in drill["platforms"]:
                continue
            if drill.get("costs_credits") and not allow_credits:
                continue
            missing = False
            for requirement in drill.get("requires", []):
                if requirement == "auth":
                    if self.auth_status is None:
                        self.auth_status = self.query_auth_status()
                    if "Not logged in" in self.auth_status:
                        missing = True
                        break
                elif shutil.which(requirement) is None:
                    missing = True
                    break
            if not missing:
                eligible.append(drill)
        return eligible

    @staticmethod
    def query_auth_status():
        try:
            result = subprocess.run(
                ["devin", "auth", "status"],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env=command_environment(Path.cwd()),
                timeout=10,
            )
            return result.stdout or ""
        except (OSError, subprocess.TimeoutExpired):
            return "Not logged in."

    def choose_item(self, category, items):
        ready = []
        if category == "flash":
            self.flash_rounds += 1
            for item in items:
                ready_after = self.flash_requeues.get(item["id"])
                if ready_after is not None and ready_after <= self.flash_rounds:
                    ready.append(item)
            if ready:
                item = min(ready, key=lambda candidate: self.flash_requeues[candidate["id"]])
                del self.flash_requeues[item["id"]]
                self.played.add(item["id"])
                self.last_flash_id = item["id"]
                return item
        item = select_item(
            items,
            self.state,
            self.new_seen,
            self.rng,
            played=self.played,
        )
        if item is None and category == "flash" and self.flash_requeues:
            pending = [
                (ready_after, candidate)
                for candidate in items
                for ready_after in [self.flash_requeues.get(candidate["id"])]
                if ready_after is not None and candidate["id"] != self.last_flash_id
            ]
            if pending:
                item = min(pending, key=lambda pair: pair[0])[1]
                del self.flash_requeues[item["id"]]
        if item is not None:
            self.played.add(item["id"])
            if category == "flash":
                self.last_flash_id = item["id"]
        return item

    def make_arena(self, drill):
        arena = self.arena_root / drill["id"]
        if arena.exists():
            shutil.rmtree(str(arena))
        arena.mkdir(parents=True)
        return arena

    def prepare_drill(self, drill, arena):
        for command in drill.get("setup", []):
            result = run_shell(command, arena)
            print_process_output(result)
            if result.returncode:
                print(danger(chrome("Setup command failed")))
        started = time.monotonic()
        print(drill["prompt"])
        return started

    def check_drill_answer(self, drill, answer, arena):
        if drill["kind"] == "answer":
            expected = run_shell(drill["truth"], arena).stdout.strip()
            return normalize(answer) == normalize(expected), expected
        result = run_shell(drill["check"], arena)
        print_process_output(result)
        return result.returncode == 0, None

    def show_drill_result(self, drill, correct, expected, elapsed):
        if correct:
            self.record_round(drill, True)
            bonus = max(0, 15 - int(elapsed // 20))
            earned = self.award(
                levelled_xp(25 + bonus, self.global_multiplier())
            )
            print("%s %s" % (
                strong("%s %s" % (glyph("found"), chrome("Drill passed"))),
                muted("+%d xp" % earned),
            ))
            return
        print(danger(chrome("Drill failed")))
        expected_value = expected if drill["kind"] == "answer" else drill["explain"]
        print("%s  %s" % (chrome("Expected"), expected_value))
        print(drill["explain"])
        self.record_round(drill, False)

    def handle_drill_answer(self, drill, arena, answer, started):
        value = answer.strip()
        if value.lower().startswith("!"):
            command = value[1:].strip()
            if command:
                print_process_output(run_shell(command, arena))
            return "continue", False
        if value.lower() == "quit":
            print("%s %s" % (glyph("quit"), muted(chrome("Session ended"))))
            return "quit", False
        if value.lower() == "give up":
            print("%s %s" % (glyph("quit"), danger(chrome("Drill failed"))))
            print(drill["explain"])
            self.record_round(drill, False)
            return "done", False
        if drill["kind"] == "check" and value:
            print(muted(chrome("Press Enter when your check is ready")))
            return "continue", False
        elapsed = time.monotonic() - started
        correct, expected = self.check_drill_answer(drill, answer, arena)
        self.show_drill_result(drill, correct, expected, elapsed)
        return "done", correct

    def clean_drill_arena(self, drill, arena):
        for command in drill.get("cleanup", []):
            result = run_shell(command, arena)
            print_process_output(result)
        print(muted(chrome("Cleanup completed")))

    def run_drill(self, drill):
        arena = self.make_arena(drill)
        correct = False
        quit_game = False
        resolved = False
        try:
            started = self.prepare_drill(drill, arena)
            footer("!command runs a shell command", "give up")
            while True:
                answer = read_answer()
                action, correct = self.handle_drill_answer(
                    drill,
                    arena,
                    answer,
                    started,
                )
                if action == "continue":
                    continue
                if action == "quit":
                    quit_game = True
                    return None, quit_game
                resolved = True
                break
        finally:
            self.clean_drill_arena(drill, arena)
        if resolved and not quit_game:
            self.resolve_streak(correct)
        return correct, quit_game

    def show_flash_prompt(self, item):
        displayed_choices = None
        if item.get("choices"):
            displayed_choices = list(item["choices"])
            self.rng.shuffle(displayed_choices)
        question(item["q"])
        if displayed_choices:
            print()
            for index, choice in enumerate(displayed_choices):
                print("  %s %s" % (muted(str(index + 1)), choice))
        return displayed_choices

    def reveal_flash_answer(self, item):
        answer = item.get("answers", [""])[0]
        print(danger(chrome("Missed")))
        print_answer_reveal(answer, item.get("explain"), item.get("confidence"))

    def ask_flash_answer(self, item, displayed_choices):
        hints = ("? hint", "skip", "quit")
        if displayed_choices:
            hints = ("1-4 to choose",) + hints
        print()
        footer(*hints)
        box_open()
        hint_used = False
        while True:
            response = read_answer()
            stripped = response.strip()
            if stripped == "?":
                if not hint_used:
                    print("%s  %s" % (muted(chrome("Hint")), item["hint"]))
                    hint_used = True
                else:
                    print(muted(chrome("Hint already used")))
                continue
            break
        box_close()
        if stripped.lower() == "quit":
            print("%s %s" % (glyph("quit"), muted(chrome("Session ended"))))
            return None
        if stripped.lower() == "skip":
            self.reveal_flash_answer(item)
            return False, hint_used, False
        correct = grade_answer(item, response, displayed_choices)
        if correct:
            return True, hint_used, False
        self.reveal_flash_answer(item)
        count_it = read_answer("Count it as correct? y/n")
        self_graded = count_it.strip().lower() == "y"
        return self_graded, hint_used, self_graded

    def record_flash_answer(self, item, correct, hint_used, self_graded):
        if correct:
            label = "Counted" if self_graded else "Correct"
            base = 5 if hint_used or self_graded else 10
        else:
            label = None
            base = 0
        self.record_round(item, correct)
        if not correct and item["id"] not in self.requeued:
            self.requeued.add(item["id"])
            self.flash_requeues[item["id"]] = self.flash_rounds + 3
        earned = self.award(levelled_xp(base, self.global_multiplier()))
        if label is not None:
            print("%s %s" % (
                strong("%s %s" % (glyph("found"), chrome(label))),
                muted("+%d xp" % earned),
            ))
        self.resolve_streak(correct)
        return correct

    def play_flash(self, item):
        displayed_choices = self.show_flash_prompt(item)
        answer = self.ask_flash_answer(item, displayed_choices)
        if answer is None:
            return None
        correct, hint_used, self_graded = answer
        return self.record_flash_answer(item, correct, hint_used, self_graded)

    def match_scenario_command(self, scenario, command):
        normalized = normalize_whitespace(command)
        for entry in scenario["commands"]:
            for pattern in entry["match"]:
                if re.fullmatch(pattern, normalized, re.IGNORECASE):
                    return entry
        return None

    def run_combo_command(self, scenario, command, engine_state):
        entry = self.match_scenario_command(scenario, command)
        engine_state["turns_used"] += 1
        if entry is None:
            token = command.strip().split(maxsplit=1)[0] if command.strip() else ""
            if (
                token
                and scenario.get("prompt", "").startswith("PS ")
                and token.casefold() not in KNOWN_COMMANDS
            ):
                output = (
                    "%s : The term '%s' is not recognized as the name of a cmdlet, "
                    "function, script file, or operable program."
                ) % (token, token)
            elif token and token.casefold() not in KNOWN_COMMANDS:
                output = "bash: %s: command not found" % token
            else:
                output = scenario["unknown_output"]
            engine_state["evidence_streak"] = 0
            return output, False
        output = entry["output"]
        is_new = entry["id"] not in engine_state["run_ids"]
        engine_state["run_ids"].add(entry["id"])
        evidence = bool(entry.get("evidence")) and is_new
        if evidence:
            engine_state["evidence_ids"].add(entry["id"])
            engine_state["evidence_streak"] = min(3, engine_state["evidence_streak"] + 1)
            engine_state["best_combo"] = max(
                engine_state["best_combo"], engine_state["evidence_streak"]
            )
        else:
            engine_state["evidence_streak"] = 0
        return output, evidence

    def next_hint(self, scenario, engine_state):
        for optimal in scenario["optimal"]:
            entry = self.match_scenario_command(scenario, optimal)
            if entry is None or entry["id"] not in engine_state["run_ids"]:
                return optimal
        return scenario["optimal"][-1] if scenario["optimal"] else ""

    def ask_scenario_question(self, scenario_question):
        choices = scenario_question["choices"]
        for index, choice in enumerate(choices):
            print("  %s %s" % (muted(str(index + 1)), choice))
        print()
        footer("1-4 to choose or type the answer")
        box_open()
        while True:
            response = read_answer()
            selected = parse_choice(response, choices)
            if selected is not None:
                break
            print(muted(chrome("Choose one of the listed answers")))
        box_close()
        return selected

    def show_combo_intro(self, scenario):
        question("%s %s %s" % (
            strong(chrome("Mystery ticket")),
            glyph("separator"),
            scenario["title"],
        ))
        print(rule(is_strong=True))
        print(scenario["ticket"])
        print()
        footer(
            "shell commands as the customer",
            "hint (-10 xp)",
            "ticket",
            "solve",
            "quit",
        )

    def new_combo_state(self):
        return {
            "turns_used": 0,
            "run_ids": set(),
            "evidence_ids": set(),
            "evidence_streak": 0,
            "best_combo": 1,
        }

    def show_combo_turn(self, scenario, command, state):
        entry = self.match_scenario_command(scenario, command)
        output, _ = self.run_combo_command(scenario, command, state)
        if output:
            source = entry.get("source") if entry else None
            tag = {"simulated": "[Sim]", "recorded": "[Rec]"}.get(source)
            suffix = " " + muted(chrome(tag)) if tag else ""
            print(output + suffix)
        evidence_total = sum(bool(item.get("evidence")) for item in scenario["commands"])
        status = "%s %s %s %s x%d %s %s %d/%d" % (
            "Evidence",
            dots(len(state["evidence_ids"]), evidence_total),
            glyph("separator"),
            "Combo",
            state["evidence_streak"],
            glyph("separator"),
            "Turns",
            state["turns_used"],
            scenario["turns"],
        )
        print(muted(chrome(status)))

    def run_combo_turns(self, scenario, state):
        while state["turns_used"] < scenario["turns"]:
            command = read_input(input_prompt(scenario["prompt"], is_content=True))
            lowered = command.strip().lower()
            if lowered == "ticket":
                print(scenario["ticket"])
                continue
            if lowered == "hint":
                print("%s  %s" % (
                    muted(chrome("Next optimal command")),
                    self.next_hint(scenario, state),
                ))
                self.award(-10)
                continue
            if lowered == "solve":
                return True
            if lowered == "quit":
                self.stop_requested = True
                print("%s %s" % (glyph("quit"), muted(chrome("Session ended"))))
                return None
            self.show_combo_turn(scenario, command, state)
        return False

    def ask_combo_questions(self, scenario):
        print()
        question("%s  %s" % (
            muted(chrome("Root cause")),
            scenario["root_cause"]["q"],
        ))
        root_index = self.ask_scenario_question(scenario["root_cause"])
        root_correct = root_index == scenario["root_cause"]["answer"]
        if not root_correct:
            print("%s %s" % (
                danger(chrome("Wrong root cause")),
                muted("-20 xp"),
            ))
        print()
        question("%s  %s" % (
            muted(chrome("Fix")),
            scenario["fix"]["q"],
        ))
        fix_index = self.ask_scenario_question(scenario["fix"])
        fix_correct = fix_index == scenario["fix"]["answer"]
        if root_correct:
            print(strong("%s %s" % (glyph("found"), chrome("Root cause"))))
        if fix_correct:
            print("%s %s" % (
                strong("%s %s" % (glyph("found"), chrome("Fix correct"))),
                muted("+25 xp"),
            ))
        return root_correct, fix_correct

    def show_combo_reveal(self, scenario, state):
        print("%s  %s" % (
            muted(chrome("Correct root cause")),
            scenario["root_cause"]["choices"][scenario["root_cause"]["answer"]],
        ))
        print("%s  %s" % (
            muted(chrome("Correct fix")),
            scenario["fix"]["choices"][scenario["fix"]["answer"]],
        ))
        print("%s  %s" % (
            muted(chrome("Optimal chain")),
            " -> ".join(scenario["optimal"]),
        ))
        print(scenario["explain"])
        print_confidence(scenario.get("confidence"))
        evidence_total = sum(bool(entry.get("evidence")) for entry in scenario["commands"])
        print(muted(chrome("Evidence %s" % dots(len(state["evidence_ids"]), evidence_total))))

    def record_combo_result(self, scenario, state, root_correct, fix_correct):
        self.best_combo = max(self.best_combo, state["best_combo"])
        self.record_round(scenario, root_correct)
        round_points = combo_score(
            len(state["evidence_ids"]),
            scenario["turns"] - state["turns_used"],
            state["best_combo"],
            root_correct,
            fix_correct,
        )
        self.award(levelled_xp(round_points, self.global_multiplier()))
        self.resolve_streak(root_correct)

    def play_combo(self, scenario):
        self.show_combo_intro(scenario)
        state = self.new_combo_state()
        solved = self.run_combo_turns(scenario, state)
        if solved is None:
            return None
        if not solved:
            print(danger(chrome("Out of turns; solve the ticket")))
        root_correct, fix_correct = self.ask_combo_questions(scenario)
        self.show_combo_reveal(scenario, state)
        self.record_combo_result(scenario, state, root_correct, fix_correct)
        return root_correct

    def play_plan(self, mode, rounds):
        if mode == "flash":
            plan = ["flash"] * FLASH_MODE_ROUNDS
        elif mode == "drill":
            plan = ["drill"] * DRILL_MODE_ROUNDS
        elif mode == "combo":
            plan = ["combo"]
        else:
            plan = (
                ["flash"] * MIXED_FLASH_OPENING_ROUNDS
                + ["drill"] * DRILL_MODE_ROUNDS
                + ["flash"] * MIXED_FLASH_CLOSING_ROUNDS
                + ["combo"]
            )
        if rounds is not None:
            plan = plan[:rounds]
        return plan

    def play_requested_round(self, round_number, total, requested, options):
        if self.stop_requested:
            return False
        available = options[requested]
        category = requested if available else "flash"
        items = available if available else options["flash"]
        item = self.choose_item(category, items)
        if item is None:
            print(muted(chrome("No eligible %s items; ending session" % category)))
            return False
        self.new_seen.add(item["id"])
        self.header(item, category, round_number, total)
        if category == "flash":
            if self.play_flash(item) is None:
                self.stop_requested = True
        elif category == "drill":
            _, quit_game = self.run_drill(item)
            if quit_game:
                self.stop_requested = True
        else:
            self.play_combo(item)
        return True

    def run_play_rounds(self, plan, options):
        total = len(plan)
        try:
            for round_number, requested in enumerate(plan, 1):
                if not self.play_requested_round(round_number, total, requested, options):
                    break
        except EOFError:
            print("\n%s %s" % (glyph("quit"), muted(chrome("Input ended; saving progress"))))
        except KeyboardInterrupt:
            print("\n%s %s" % (glyph("quit"), muted(chrome("Interrupted; saving progress"))))
        self.print_summary()
        save_state(self.home, self.state)

    def play(self, mode=None, topic=None, rounds=None, seed=None, no_live=False, allow_credits=False):
        try:
            topic_filter = re.compile(topic, re.IGNORECASE) if topic else None
        except re.error as error:
            raise ValueError("invalid topic regex: %s" % error)
        self.begin_session(seed)
        flash = [
            item for item in self.content["flash"]
            if not topic_filter or topic_filter.search(item["topic"])
        ]
        combos = [
            item for item in self.content["combo"]
            if not topic_filter or topic_filter.search(item["topic"])
        ]
        plan = self.play_plan(mode, rounds)
        self.print_session_header("Play %s %s" % (glyph("separator"), plan_description(plan)))
        drills = (
            self.eligible_drills(topic_filter, no_live, allow_credits)
            if "drill" in plan else []
        )
        options = {"flash": flash, "drill": drills, "combo": combos}
        self.run_play_rounds(plan, options)

    def print_summary_header(self):
        accuracy = (
            100 * self.round_correct / self.round_attempts
            if self.round_attempts
            else 0
        )
        print()
        print(strong(chrome("Session summary")))
        print(rule(is_strong=True))
        print(kv("XP gained", self.session_xp))
        print(kv(
            "Accuracy",
            "%d/%d  %.1f%%" % (self.round_correct, self.round_attempts, accuracy),
        ))

    def print_summary_tables(self, training):
        if training and self.category_totals:
            print_category_table("Category performance", self.category_totals)
        elif self.topic_totals and not training:
            print_topic_table("Per-topic accuracy", self.topic_totals)

    def print_weakest_topics(self):
        if self.topic_totals:
            weakest = sorted(
                (
                    (topic, totals)
                    for topic, totals in self.topic_totals.items()
                    if totals[0] < totals[1]
                ),
                key=lambda pair: (pair[1][0] / pair[1][1], pair[0]),
            )[:3]
            if weakest:
                weak_topics = ", ".join(topic for topic, _ in weakest)
            else:
                weak_topics = chrome("None")
            print("%s  %s" % (muted(chrome("Weakest topics")), weak_topics))
        else:
            print("%s  %s" % (muted(chrome("Weakest topics")), chrome("None")))

    def print_missed_items(self):
        if not self.session_missed:
            return
        print(muted(chrome("Missed items")))
        missed_ids = set()
        for item in self.session_missed:
            if item["id"] in missed_ids:
                continue
            missed_ids.add(item["id"])
            if "root_cause" in item:
                question = item["root_cause"]["q"]
                answer = item["root_cause"]["choices"][item["root_cause"]["answer"]]
            else:
                question = item.get(
                    "task",
                    item.get("q", item.get("prompt", item.get("ticket", item["id"]))),
                )
                answer = item.get("answers", [item.get("explain", "")])[0]
            print("%s %s" % (glyph("empty"), question))
            if item.get("kind") in ("write", "fix"):
                print("  %s  %s" % (chrome("answer"), answer))
                print_confidence(item.get("confidence"))
            else:
                print_answer_reveal(answer, item.get("explain"), item.get("confidence"))

    def print_summary_progress(self, training, next_up):
        now = dt.datetime.now().astimezone()
        tomorrow = now + dt.timedelta(days=1)
        due_tomorrow = []
        for item_id, progress in self.state.get("items", {}).items():
            due = parse_time(progress.get("due"))
            if due and due.date() == tomorrow.date():
                due_tomorrow.append(item_id)
        print(kv("Items due tomorrow", len(due_tomorrow)))
        print(kv("Best combo", "x%d" % self.best_combo))
        if training and next_up:
            count, tier, category = next_up
            print(muted(chrome(
                "Next up: %d new tier-%d cards in %s" % (count, tier, category)
            )))

    def print_summary(self, training=False, next_up=None):
        self.print_summary_header()
        self.print_summary_tables(training)
        self.print_weakest_topics()
        self.print_missed_items()
        self.print_summary_progress(training, next_up)


def print_topic_table(title, topics):
    print(muted(chrome(title)))
    headings = "%-14s %5s %5s %7s  " % ("Topic", "Right", "Seen", "Acc")
    print(muted(chrome(headings)))
    print(rule(is_strong=True))
    for topic in sorted(topics):
        count, total = topics[topic]
        percent = 100 * count / total if total else 0
        print("%-14s %5d %5d %6.1f%%  %s" % (
            topic,
            count,
            total,
            percent,
            score_bar(percent / 100),
        ))


def print_category_table(title, categories):
    print(muted(chrome(title)))
    headings = "%-15s %7s %7s %7s  %s" % (
        "Category",
        "Correct",
        "Seen",
        "Acc",
        "Progress",
    )
    print(muted(chrome(headings)))
    print(rule(is_strong=True))
    for category in CATEGORIES:
        if category not in categories:
            continue
        correct, total = categories[category]
        percent = 100 * correct / total if total else 0
        print("%-15s %7d %7d %6.1f%%  %s" % (
            category,
            correct,
            total,
            percent,
            score_bar(percent / 100),
        ))


def stats_accuracy(items):
    seen = sum(progress.get("seen", 0) for progress in items.values())
    correct = sum(progress.get("correct", 0) for progress in items.values())
    percent = 100 * correct / seen if seen else 0
    return correct, seen, percent


def stats_leitner_boxes(items, now):
    boxes = {box: 0 for box in range(1, 6)}
    due_today = 0
    for progress in items.values():
        box = progress.get("box", 1)
        boxes[box] = boxes.get(box, 0) + 1
        due = parse_time(progress.get("due"))
        if due and due.date() <= now.date():
            due_today += 1
    return boxes, due_today


def stats_topic_totals(items):
    topics = {}
    for progress in items.values():
        topic = progress.get("topic", "unknown")
        totals = topics.setdefault(topic, [0, 0])
        totals[0] += progress.get("correct", 0)
        totals[1] += progress.get("seen", 0)
    return topics


def show_stats(state):
    xp = state.get("xp", 0)
    level = level_for_xp(xp)
    level_floor = 50 * (level - 1) ** 2
    level_ceiling = 50 * level ** 2
    progress = (xp - level_floor) / max(1, level_ceiling - level_floor)
    print(strong(chrome("Stats")))
    print(rule(is_strong=True))
    print("%s  %s  %s" % (
        strong(chrome("L%d %s" % (level, title_for_level(level)))),
        score_bar(progress),
        muted("%d/%d xp" % (xp, level_ceiling)),
    ))
    print(kv("XP", xp))
    print(kv("Streak", state.get("streak", 0)))
    print(kv("Daily streak", state.get("daily_streak", 0)))
    items = state.get("items", {})
    correct, seen, percent = stats_accuracy(items)
    print(kv("Accuracy", "%d/%d  %.1f%%" % (correct, seen, percent)))
    now = dt.datetime.now().astimezone()
    boxes, due_today = stats_leitner_boxes(items, now)
    print(muted(chrome("Leitner boxes")))
    box_headings = "  ".join(chrome("Box %d" % box).rjust(8) for box in range(1, 6))
    print(muted(box_headings))
    print(rule(is_strong=True))
    print("  ".join(str(boxes[box]).rjust(8) for box in range(1, 6)))
    print(kv("Due today", due_today))
    topics = stats_topic_totals(items)
    if topics:
        print_topic_table("Accuracy by topic", topics)


def show_categories(content, state):
    print(strong(chrome("Categories")))
    print(rule(is_strong=True))
    headings = "%-15s %5s %5s %8s %5s  %s" % (
        "Category",
        "Cards",
        "Seen",
        "Mastered",
        "Due",
        "Progress",
    )
    print(muted(chrome(headings)))
    print(rule(is_strong=True))
    now = dt.datetime.now().astimezone()
    for category in CATEGORIES:
        cards = [card for card in content["commands"] if card["category"] == category]
        seen = 0
        mastered = 0
        due = 0
        for card in cards:
            progress = state.get("items", {}).get(card["id"])
            if not progress:
                continue
            seen += progress.get("seen", 0)
            if progress.get("box", 1) >= 4:
                mastered += 1
            due_time = parse_time(progress.get("due"))
            if due_time and due_time <= now:
                due += 1
        total = len(cards)
        fraction = mastered / total if total else 0
        print("%-15s %5d %5d %8d %5d  %s" % (
            category,
            total,
            seen,
            mastered,
            due,
            score_bar(fraction),
        ))


def list_items(content, state, item_type=None):
    labels = (
        ("flash", "flash"),
        ("drill", "drill"),
        ("combo", "combo"),
        ("command", "commands"),
    )
    for category, key in labels:
        if item_type and item_type != category:
            continue
        print(strong(chrome("%s items" % category)))
        for item in content[key]:
            progress = state.get("items", {}).get(item["id"], {})
            if category == "command":
                description = "tier %d · %s · %s" % (
                    item["tier"],
                    item["category"],
                    item["task"],
                )
            else:
                description = item["topic"]
            print("%s  %s  %s %d" % (
                item["id"],
                description,
                muted(chrome("Box")),
                progress.get("box", 1),
            ))


def ask_reset():
    try:
        return read_answer("Reset all dojo progress? y/N").strip().lower() == "y"
    except EOFError:
        return False


def content_cli_version():
    try:
        text = (COMMAND_HELP_DIR / "VERSION").read_text(encoding="utf-8").strip()
    except OSError:
        return "unknown"
    match = re.search(r"\d+\.\d+\.\d+", text)
    return match.group(0) if match else text


def installed_cli_version():
    try:
        result = subprocess.run(
            ["devin", "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=1,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    match = re.search(r"\d+\.\d+\.\d+", result.stdout or "")
    return match.group(0) if match else None


def version_string():
    return "professor-devin %s (content for devin cli %s)" % (
        VERSION,
        content_cli_version(),
    )


MENU_LOGO = (
    "⠀⣴⣾⣶⡄⠀⠀⠀⠀",
    "⠀⠛⠿⠟⠻⣶⣾⣶⡄",
    "⠀⣤⣶⣦⣴⠿⢿⠿⠃",
    "⠀⠻⢿⠿⠃⠀⠀⠀⠀",
)

MENU_OPTIONS = (
    ("Quick start", "10 rounds of real commands, then a mystery ticket"),
    ("Pick a topic", "launch, sessions, auth, mcp, slash commands, ..."),
    ("Flashcards", "short questions on config, hooks, skills, rules"),
    ("Mystery ticket", "debug a broken setup, one shell command at a time"),
    ("Live drills", "run real devin commands on this machine"),
    ("Progress", "level, xp, accuracy by topic, cards due"),
    ("How to play", "the rules on one screen"),
)

HOW_TO_PLAY = """Each round shows a job to do with the Devin CLI. Type the command you would
run and press ↵. Command rounds and tickets are simulated: nothing you type
there runs for real. Live drills do run real devin commands on this machine.

  recognize   see a command, pick what it does (1-4)
  fill in     type the missing piece of a command, or the whole command
  recall      write the whole command from the task
  fix         a broken command and its error; type the corrected command

A card moves up a step each time you get it right and comes back later:
1 day, 3 days, 7 days, 21 days. A miss sends it back to the start.

  ?      hint (halves the xp for that round)
  skip   show the answer and move on
  quit   stop and save (ctrl-c works too)

XP builds a streak multiplier (up to x3) and levels: intern, log reader,
triage tech, tracer, config whisperer, root-causer, staff rca.

The same things from the command line:
  professor-devin train [topic]        professor-devin play --mode flash
  professor-devin play --mode combo    professor-devin stats
Progress is saved in ~/.professor-devin"""


def print_how_to_play():
    print(strong(chrome("How to play")))
    print(rule(is_strong=True))
    print(HOW_TO_PLAY)


def menu_progress_line(state):
    xp = state.get("xp", 0)
    level = level_for_xp(xp)
    now = dt.datetime.now().astimezone()
    due = 0
    for progress in state.get("items", {}).values():
        due_date = parse_time(progress.get("due"))
        if due_date and due_date <= now:
            due += 1
    return "L%d %s %s %d xp %s %d cards due today" % (
        level,
        title_for_level(level),
        glyph("separator"),
        xp,
        glyph("separator"),
        due,
    )


def print_home_menu(state):
    installed = installed_cli_version()
    version_note = (
        "you have %s" % installed if installed else "devin not installed"
    )
    print(MENU_LOGO[0])
    print("%s  %s" % (MENU_LOGO[1], strong(chrome("Professor Devin"))))
    print("%s  %s" % (MENU_LOGO[2], muted(chrome("Learn the Devin CLI by typing it"))))
    print("%s  %s" % (MENU_LOGO[3], muted(chrome(
        "Cards written for Devin CLI %s %s %s" % (
            content_cli_version(),
            glyph("separator"),
            version_note,
        )
    ))))
    print()
    print(muted(chrome(menu_progress_line(state))))
    print()
    question("What do you want to practice?")
    print()
    title_width = max(len(title) for title, _ in MENU_OPTIONS)
    for index, (title, description) in enumerate(MENU_OPTIONS, 1):
        padded = chrome(title).ljust(title_width)
        if index == 1:
            marker = accent(glyph("prompt"))
            title_text = strong(padded)
        else:
            marker = " "
            title_text = padded
        print("%s %s %s  %s" % (
            marker,
            muted(str(index)),
            title_text,
            muted(chrome(description)),
        ))
    print()
    footer("1-7 to choose", "↵ quick start", "q quit")


def category_mastered_counts(content, state):
    counts = {}
    for category in CATEGORIES:
        cards = [card for card in content["commands"] if card["category"] == category]
        mastered = sum(
            1
            for card in cards
            if state.get("items", {}).get(card["id"], {}).get("box", 1) >= 4
        )
        counts[category] = (len(cards), mastered)
    return counts


def choose_topic_menu(content, state):
    print()
    question("Which topic?")
    counts = category_mastered_counts(content, state)
    for index, category in enumerate(CATEGORIES, 1):
        total, mastered = counts[category]
        print("  %s %-14s %s" % (
            muted(str(index)),
            category,
            muted(chrome("%d cards %s %d mastered" % (total, glyph("separator"), mastered))),
        ))
    print()
    footer("1-%d to choose" % len(CATEGORIES), "name also works", "↵ back")
    response = read_answer().strip().lower()
    if not response:
        return None
    if response.isdigit() and 1 <= int(response) <= len(CATEGORIES):
        return CATEGORIES[int(response) - 1]
    if response in CATEGORIES:
        return response
    print(muted(chrome("Choose a topic 1-%d or a name" % len(CATEGORIES))))
    return None


def home_menu(home, content):
    while True:
        state = load_state(home)
        print_home_menu(state)
        choice = read_answer().strip().lower()
        if not choice:
            choice = "1"
        if choice in ("q", "quit"):
            return
        if choice == "1":
            game = Dojo(home, content)
            game.session_hint = "professor-devin train"
            game.train([], 10, 3, None)
        elif choice == "2":
            category = choose_topic_menu(content, state)
            if category is None:
                print()
                continue
            game = Dojo(home, content)
            game.session_hint = "professor-devin train %s" % category
            game.train([category], 10, 3, None)
        elif choice == "3":
            game = Dojo(home, content)
            game.session_hint = "professor-devin play --mode flash"
            game.play(mode="flash")
        elif choice == "4":
            game = Dojo(home, content)
            game.session_hint = "professor-devin play --mode combo"
            game.play(mode="combo")
        elif choice == "5":
            game = Dojo(home, content)
            game.session_hint = "professor-devin play --mode drill"
            game.play(mode="drill")
        elif choice == "6":
            show_stats(state)
            show_categories(content, state)
        elif choice == "7":
            print_how_to_play()
        else:
            print()
            print(muted(chrome("Choose 1-7 or q")))
            print()
            continue
        print()
        footer("↵ menu", "q quit")
        again = read_answer().strip().lower()
        if again in ("q", "quit"):
            return
        print()


ROOT_HELP = """Professor Devin: learn the Devin CLI by typing real commands.

Usage: professor-devin [COMMAND] [OPTIONS]

Commands:
  menu        Open the home menu (default in a terminal)
  train       Command rounds: write real devin commands, then a mystery-ticket boss [default when piped]
  play        Mixed session: flashcards, live drills, and a mystery ticket
  stats       Show your level, XP, accuracy, and cards due
  categories  Show every category with cards seen, mastered, and due
  list        List every card and its review box
  reset       Erase saved progress
  help        Print this message or the help of the given subcommand(s)

Options:
  -h, --help     Print help
  -V, --version  Print version"""

TRAIN_HELP = """Command rounds: write real devin commands, then a mystery-ticket boss

Usage: professor-devin train [CATEGORY]... [OPTIONS]

Arguments:
  [CATEGORY]...   Limit rounds to these categories

Options:
      --rounds <N>     Number of command rounds [default: 10]
      --tier <1|2|3>   Highest card tier [default: 3]
      --seed <N>       Shuffle seed for a repeatable session
  -h, --help           Print help"""

PLAY_HELP = """Mixed session: flashcards, live drills, and a mystery ticket

Usage: professor-devin play [OPTIONS]

Options:
      --mode <flash|drill|combo>   Session mode
      --topic <REGEX>              Limit items by topic
      --rounds <N>                 Cap the session plan
      --seed <N>                   Shuffle seed for a repeatable session
      --no-live                    Skip live drills
      --allow-credits              Allow drills that may use credits
  -h, --help                       Print help"""

MENU_HELP = """Open the home menu (default in a terminal)

Usage: professor-devin menu [OPTIONS]

Options:
  -h, --help  Print help"""

STATS_HELP = """Show your level, XP, accuracy, and cards due

Usage: professor-devin stats [OPTIONS]

Options:
  -h, --help  Print help"""

CATEGORIES_HELP = """Show every category with cards seen, mastered, and due

Usage: professor-devin categories [OPTIONS]

Options:
  -h, --help  Print help"""

LIST_HELP = """List every card and its review box

Usage: professor-devin list [OPTIONS]

Options:
      --type <flash|drill|combo|command>   Only list one item type
  -h, --help                               Print help"""

RESET_HELP = """Erase saved progress

Usage: professor-devin reset [OPTIONS]

Options:
      --yes     Do not ask for confirmation
  -h, --help    Print help"""

HELP_HELP = """Print this message or the help of the given subcommand(s)

Usage: professor-devin help [COMMAND]

Arguments:
  [COMMAND]   Subcommand to show help for

Options:
  -h, --help  Print help"""

SUBCOMMAND_HELP = {
    "menu": MENU_HELP,
    "train": TRAIN_HELP,
    "play": PLAY_HELP,
    "stats": STATS_HELP,
    "categories": CATEGORIES_HELP,
    "list": LIST_HELP,
    "reset": RESET_HELP,
    "help": HELP_HELP,
}


def add_play_arguments(parser):
    parser.add_argument("--mode", choices=("flash", "drill", "combo"))
    parser.add_argument("--topic")
    parser.add_argument("--rounds", type=int)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--no-live", action="store_true")
    parser.add_argument("--allow-credits", action="store_true")


def _static_help(text):
    return lambda: text + "\n"


def build_parser():
    parser = argparse.ArgumentParser(prog="professor-devin")
    parser.format_help = _static_help(ROOT_HELP)
    parser.add_argument("-V", "--version", action="store_true")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("menu").format_help = _static_help(MENU_HELP)

    train_parser = subparsers.add_parser("train")
    train_parser.add_argument("categories", nargs="*")
    train_parser.add_argument("--rounds", type=int, default=10)
    train_parser.add_argument("--tier", type=int, choices=(1, 2, 3), default=3)
    train_parser.add_argument("--seed", type=int)
    train_parser.format_help = _static_help(TRAIN_HELP)

    play_parser = subparsers.add_parser("play")
    add_play_arguments(play_parser)
    play_parser.format_help = _static_help(PLAY_HELP)

    subparsers.add_parser("categories").format_help = _static_help(CATEGORIES_HELP)
    subparsers.add_parser("stats").format_help = _static_help(STATS_HELP)

    list_parser = subparsers.add_parser("list")
    list_parser.add_argument("--type", choices=("flash", "drill", "combo", "command"))
    list_parser.format_help = _static_help(LIST_HELP)

    reset_parser = subparsers.add_parser("reset")
    reset_parser.add_argument("--yes", action="store_true")
    reset_parser.format_help = _static_help(RESET_HELP)

    help_parser = subparsers.add_parser("help")
    help_parser.add_argument("topic", nargs="?", choices=sorted(SUBCOMMAND_HELP))
    help_parser.format_help = _static_help(HELP_HELP)
    return parser


def parse_cli_arguments(argv, parser):
    commands = set(SUBCOMMAND_HELP)
    if not argv:
        if interactive_terminal():
            return parser.parse_args(["menu"])
        return parser.parse_args(["train"])
    if (
        argv[0] not in commands
        and argv[0] not in ("-h", "--help", "-V", "--version")
    ):
        args = parser.parse_args(["train"] + argv)
    else:
        args = parser.parse_args(argv)
        if getattr(args, "version", False):
            print(version_string())
            return None
        if args.command is None:
            parser.print_help()
            return None
    return args


def validate_training_arguments(args, parser):
    unknown = list(dict.fromkeys(
        category for category in args.categories if category not in CATEGORIES
    ))
    if unknown:
        parser.error(
            "unknown category %s; valid categories: %s" %
            (", ".join(unknown), ", ".join(CATEGORIES))
        )
    if args.rounds < 1:
        parser.error("--rounds must be at least 1")


def run_cli_command(args, parser, home, content, state):
    if args.command == "menu":
        home_menu(home, content)
        return
    if args.command == "help":
        print(SUBCOMMAND_HELP[args.topic] if args.topic else ROOT_HELP)
        return
    if args.command == "train":
        validate_training_arguments(args, parser)
        game = Dojo(home, content)
        game.train(args.categories, args.rounds, args.tier, args.seed)
        return
    if args.command == "categories":
        show_categories(content, state)
        return
    if args.command == "stats":
        show_stats(state)
        return
    if args.command == "list":
        list_items(content, state, getattr(args, "type", None))
        return
    if args.command == "reset":
        if args.yes or ask_reset():
            save_state(home, default_state())
            print(muted(chrome("Progress reset")))
        else:
            print(muted(chrome("Reset cancelled")))
        return
    if args.rounds is not None and args.rounds < 1:
        raise ValueError("--rounds must be at least 1")
    game = Dojo(home, content)
    game.play(
        mode=args.mode,
        topic=args.topic,
        rounds=args.rounds,
        seed=args.seed,
        no_live=args.no_live,
        allow_credits=args.allow_credits,
    )


def main(argv=None):
    arguments = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    args = parse_cli_arguments(arguments, parser)
    if args is None:
        return 0
    home = dojo_home()
    try:
        content = load_content(home)
        validate_content(content)
        state = load_state(home)
        run_cli_command(args, parser, home, content, state)
    except EOFError:
        print("\n%s %s" % (glyph("quit"), muted(chrome("Input ended; saving progress"))))
    except KeyboardInterrupt:
        print("\n%s %s" % (glyph("quit"), muted(chrome("Interrupted; saving progress"))))
        save_state(home, load_state(home))
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print("%s: %s" % (chrome("dojo"), error), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
