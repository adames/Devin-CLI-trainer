#!/usr/bin/env python3
"""Render deterministic README screenshots of Professor Devin sessions.

Captures dojo output in-process (SGR on, 80 columns) and renders it to a
terminal-window PNG through an SVG. Requires rsvg-convert or ImageMagick's
`magick`; without either it still writes the SVGs.

    python3 tools/screenshots.py [--only NAME] [--svg-dir DIR]
"""

import argparse
import datetime as dt
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "dojo"))
sys.path.insert(0, str(REPO / "tools"))

import dojo  # noqa: E402

COLUMNS = 90
FONT = "JetBrainsMono Nerd Font Mono, JetBrains Mono, Menlo, DejaVu Sans Mono, monospace"
FONT_SIZE = 14
LINE_HEIGHT = 20
CHAR_WIDTH = 8.43
PAD = 16
TITLE_HEIGHT = 36
BG = "#1b1b1f"
FG = "#d6d6d6"
DIM = "#8b8b8b"
BORDER = "#333"

PALETTE16 = [
    "#000000", "#cd0000", "#00cd00", "#cdcd00", "#0000ee", "#cd00cd",
    "#00cdcd", "#e5e5e5", "#7f7f7f", "#ff0000", "#00ff00", "#ffff00",
    "#5c5cff", "#ff00ff", "#00ffff", "#ffffff",
]
CUBE_LEVELS = (0, 95, 135, 175, 215, 255)

SGR_RE = re.compile(r"\x1b\[([0-9;]*)m")


def color_256(index):
    if index < 16:
        return PALETTE16[index]
    if index < 232:
        index -= 16
        red = CUBE_LEVELS[index // 36]
        green = CUBE_LEVELS[(index % 36) // 6]
        blue = CUBE_LEVELS[index % 6]
        return "#%02x%02x%02x" % (red, green, blue)
    level = 8 + 10 * (index - 232)
    return "#%02x%02x%02x" % (level, level, level)


def parse_line(line):
    """Split a line into (text, style) runs. Style keys: bold, dim, inverse, fg."""
    style = {"bold": False, "dim": False, "inverse": False, "fg": FG}
    runs = []
    cursor = 0
    for match in SGR_RE.finditer(line):
        if match.start() > cursor:
            runs.append((line[cursor:match.start()], dict(style)))
        codes = [int(code) for code in match.group(1).split(";") if code] or [0]
        index = 0
        while index < len(codes):
            code = codes[index]
            if code == 0:
                style = {"bold": False, "dim": False, "inverse": False, "fg": FG}
            elif code == 1:
                style["bold"] = True
            elif code == 2:
                style["dim"] = True
            elif code == 7:
                style["inverse"] = True
            elif code == 22:
                style["bold"] = style["dim"] = False
            elif code == 27:
                style["inverse"] = False
            elif code == 38 and index + 2 < len(codes) and codes[index + 1] == 5:
                style["fg"] = color_256(codes[index + 2])
                index += 2
            elif code == 38 and index + 4 < len(codes) and codes[index + 1] == 2:
                style["fg"] = "#%02x%02x%02x" % tuple(codes[index + 2:index + 5])
                index += 4
            elif code == 39:
                style["fg"] = FG
            index += 1
        cursor = match.end()
    if cursor < len(line):
        runs.append((line[cursor:], dict(style)))
    return runs


def wrap_cells(runs):
    """Break a parsed line into (start_column, [(char, style), ...]) rows.

    Wraps at the last space inside the row width (hard break only when a token
    exceeds the row), drops the break space, and indents continuation rows of
    numbered-choice lines by 4 cells.
    """
    plain = "".join(segment for segment, _ in runs)
    cells = [(ch, style) for segment, style in runs for ch in segment]
    indent = 4 if re.match(r"^\s*\d+ ", plain) else 0
    rows = []
    index = 0
    while True:
        start = indent if rows else 0
        capacity = COLUMNS - start
        window = cells[index:index + capacity]
        if index + capacity >= len(cells):
            piece, index = window, len(cells)
        else:
            gap = max(
                (j for j, (ch, _) in enumerate(window) if ch == " "),
                default=-1,
            )
            if gap <= 0:
                piece, index = window, index + capacity
            else:
                piece, index = window[:gap], index + gap + 1
        rows.append((start, piece))
        if index >= len(cells):
            return rows


def group_cells(cells):
    """Merge adjacent (char, style) cells with identical styles into runs."""
    groups = []
    for ch, style in cells:
        if groups and groups[-1][1] == style:
            groups[-1][0].append(ch)
        else:
            groups.append(([ch], style))
    return [("".join(chars), style) for chars, style in groups]


def escape(text):
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def render_svg(text, title):
    lines = text.split("\n")
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not SGR_RE.sub("", lines[-1]).strip():
        lines.pop()
    parsed = [parse_line(line) for line in lines]

    wrapped = [wrap_cells(runs) for runs in parsed]
    rows = sum(len(line_rows) for line_rows in wrapped)
    width = int(PAD + COLUMNS * CHAR_WIDTH + PAD)
    height = TITLE_HEIGHT + PAD + rows * LINE_HEIGHT + PAD
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" '
        'width="%d" height="%d" viewBox="0 0 %d %d">' % (width, height, width, height),
        '<rect x="0.5" y="0.5" width="%d" height="%d" rx="10" fill="%s" stroke="%s"/>'
        % (width - 1, height - 1, BG, BORDER),
        '<path d="M0.5 10.5 a10 10 0 0 1 10 -10 h%d a10 10 0 0 1 10 10 v25.5 h-%d z" '
        'fill="#2a2a2e"/>' % (width - 21, width - 1),
        '<circle cx="20" cy="18.5" r="6" fill="#ff5f57"/>',
        '<circle cx="40" cy="18.5" r="6" fill="#febc2e"/>',
        '<circle cx="60" cy="18.5" r="6" fill="#28c840"/>',
        '<text x="%d" y="23" fill="%s" font-family="%s" font-size="13" '
        'text-anchor="middle">%s</text>'
        % (width // 2, DIM, FONT, escape(title)),
        '<g font-family="%s" font-size="%d" xml:space="preserve">'
        % (FONT, FONT_SIZE),
    ]
    top = TITLE_HEIGHT + PAD
    row = 0
    for line_rows in wrapped:
        for start, piece in line_rows:
            column = start
            for segment, style in group_cells(piece):
                fill = DIM if style["dim"] else style["fg"]
                x = PAD + column * CHAR_WIDTH
                y = top + row * LINE_HEIGHT + 14
                if style["inverse"]:
                    span = len(segment) * CHAR_WIDTH
                    parts.append(
                        '<rect x="%.2f" y="%d" width="%.2f" height="18" fill="%s"/>'
                        % (x, top + row * LINE_HEIGHT + 1, span, fill)
                    )
                    fill = BG
                weight = ' font-weight="700"' if style["bold"] else ""
                parts.append(
                    '<text x="%.2f" y="%d" fill="%s"%s>%s</text>'
                    % (x, y, fill, weight, escape(segment))
                )
                column += len(segment)
            row += 1
    parts.append("</g>")
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


class TerminalCapture(io.StringIO):
    @property
    def encoding(self):
        return "utf-8"

    def isatty(self):
        return True


def capture_session(run, answers):
    """Run `run` with scripted answers; return (full_text, eof_pos, after_answer_pos).

    eof_pos marks the byte offset right after the first unscripted prompt (the
    prompt itself is included). after_answer_pos marks the offset right after
    the newline that follows the last consumed answer.
    """
    capture = TerminalCapture()
    scripted = iter(answers)
    marks = {"eof": None, "after_answer": None}

    def fake_input(prompt=""):
        try:
            answer = next(scripted)
        except StopIteration:
            print(prompt, end="")
            marks["eof"] = len(capture.getvalue())
            raise EOFError
        print(prompt + answer)
        marks["after_answer"] = len(capture.getvalue())
        return answer

    class TtyStdin(io.StringIO):
        def isatty(self):
            return True

    stdin = sys.stdin
    sys.stdin = TtyStdin()
    try:
        with redirect_stdout(capture):
            with patch("builtins.input", fake_input):
                with patch("dojo.shutil.get_terminal_size",
                           return_value=os.terminal_size((COLUMNS, 24))):
                    with patch.object(dojo, "installed_cli_version",
                                      return_value=dojo.content_cli_version()):
                        run()
    except EOFError:
        pass
    finally:
        sys.stdin = stdin
    return capture.getvalue(), marks


def slice_at(text, pos):
    return text if pos is None else text[:pos]


def drop_at_line(text, pattern):
    lines = text.split("\n")
    for index, line in enumerate(lines):
        if re.search(pattern, SGR_RE.sub("", line)):
            text = "\n".join(lines[:index])
            break
    return text.rstrip("\n") + "\n"


CURSOR = "\x1b[2m▍\x1b[0m"


def fresh_home():
    home = Path(tempfile.mkdtemp(prefix="professor-shot-"))
    return home, dojo.load_content(home)


def shot_home():
    home, _ = fresh_home()
    dojo.save_state(
        home, dict(dojo.default_state(), profile="beginner")
    )
    env = dict(os.environ)
    env["FORCE_COLOR"] = "1"
    env["PROFESSOR_HOME"] = str(home)
    with patch.dict(os.environ, env, clear=True):
        text, marks = capture_session(lambda: dojo.main(["menu"]), [])
    return slice_at(text, marks["eof"]) + CURSOR, "professor-devin"


def seed_train_state(home, content):
    launch = [
        card for card in content["commands"]
        if card["category"] == "launch" and card["tier"] == 1 and card["kind"] == "write"
    ]
    now = dt.datetime.now().astimezone()
    state = dojo.default_state()
    recall_card = launch[0]
    fill_card = launch[1]
    for card, days_ago in ((recall_card, 3), (fill_card, 2)):
        progress = dojo.review_item(state, card["id"], True, now)
        progress["due"] = (now - dt.timedelta(days=days_ago)).isoformat()
    progress = dojo.review_item(state, recall_card["id"], True, now)
    progress["due"] = (now - dt.timedelta(days=3)).isoformat()
    dojo.save_state(home, state)
    return recall_card, fill_card


def shot_first_run():
    home, _ = fresh_home()
    env = dict(os.environ)
    env["FORCE_COLOR"] = "1"
    env["PROFESSOR_HOME"] = str(home)
    with patch.dict(os.environ, env, clear=True):
        text, marks = capture_session(
            lambda: dojo.setup_wizard(home, dojo.load_state(home), True), []
        )
    return slice_at(text, marks["eof"]) + CURSOR, "professor-devin"


def shot_train():
    home, content = fresh_home()
    recall_card, fill_card = seed_train_state(home, content)
    answers = [
        recall_card["answers"][0],
        dojo.command_blank(fill_card),
        "2",
        "n",
    ]
    env = dict(os.environ)
    env["FORCE_COLOR"] = "1"
    env["PROFESSOR_HOME"] = str(home)
    with patch.dict(os.environ, env, clear=True):
        game = dojo.Dojo(home, content)
        text, marks = capture_session(
            lambda: game.train(["launch"], 3, 3, 1), answers
        )
    return slice_at(text, marks["after_answer"]), "professor-devin train launch"


def shot_ticket():
    home, content = fresh_home()
    answers = ["type node", "bash -lic 'echo $PATH'", "solve", "1", "1"]
    env = dict(os.environ)
    env["FORCE_COLOR"] = "1"
    env["PROFESSOR_HOME"] = str(home)
    with patch.dict(os.environ, env, clear=True):
        game = dojo.Dojo(home, content)
        text, _ = capture_session(
            lambda: game.play(mode="combo", rounds=1, seed=3, no_live=True),
            answers,
        )
    return drop_at_line(text, r"^session summary"), "professor-devin play --mode combo"


def shot_stats():
    home, content = fresh_home()
    now = dt.datetime.now().astimezone()
    state = dojo.default_state()
    state["xp"] = 230
    state["streak"] = 4
    state["daily_streak"] = 3
    state["profile"] = "beginner"
    pool = []
    for category, count in (
        ("launch", 8), ("sessions", 5), ("auth", 3), ("mcp", 12), ("slash", 12)
    ):
        pool.extend(
            [
                card for card in content["commands"]
                if card["category"] == category
            ][:count]
        )
    boxes = (3, 4, 2, 5, 3, 4, 3, 2, 4, 5, 3, 1, 4, 3, 5, 2, 4, 3, 4, 2)
    for index, card in enumerate(pool):
        box = boxes[index % len(boxes)]
        seen = box + 2 if box >= 2 else 3
        correct = max(0, seen - 1 if box >= 4 else seen - 2)
        if box <= 2:
            due = now - dt.timedelta(days=1)
        elif index % 5 == 4:
            due = now
        else:
            due = now + dt.timedelta(days=box)
        state["items"][card["id"]] = {
            "box": box,
            "seen": seen,
            "correct": correct,
            "due": due.isoformat(),
            "last_seen": (now - dt.timedelta(days=1)).isoformat(),
            "topic": card["category"],
        }
    with patch.dict(os.environ, {"FORCE_COLOR": "1"}, clear=False):
        text, _ = capture_session(lambda: (
            dojo.show_stats(state),
            dojo.show_categories(content, state),
        ), [])
    return text, "professor-devin stats"


SHOTS = {
    "first-run": shot_first_run,
    "home": shot_home,
    "train": shot_train,
    "ticket": shot_ticket,
    "stats": shot_stats,
}


def convert(svg_path, png_path):
    rsvg = shutil.which("rsvg-convert")
    if rsvg:
        subprocess.run(
            [rsvg, "-z", "2", str(svg_path), "-o", str(png_path)],
            check=True,
        )
        if png_path.stat().st_size > 400 * 1024:
            subprocess.run(
                [rsvg, "-z", "1.5", str(svg_path), "-o", str(png_path)],
                check=True,
            )
        return True
    magick = shutil.which("magick")
    if magick:
        subprocess.run(
            [magick, "-density", "192", str(svg_path), str(png_path)],
            check=True,
        )
        return True
    return False


def main():
    parser = argparse.ArgumentParser(prog="screenshots")
    parser.add_argument("--only", choices=sorted(SHOTS))
    parser.add_argument("--svg-dir", help="keep the intermediate SVGs here")
    args = parser.parse_args()

    assets = REPO / "assets"
    assets.mkdir(exist_ok=True)
    svg_dir = Path(args.svg_dir) if args.svg_dir else Path(
        tempfile.mkdtemp(prefix="shots-svg-")
    )
    svg_dir.mkdir(parents=True, exist_ok=True)

    names = [args.only] if args.only else list(SHOTS)
    wrote_png = False
    for name in names:
        text, title = SHOTS[name]()
        svg_path = svg_dir / ("%s.svg" % name)
        svg_path.write_text(render_svg(text, title), encoding="utf-8")
        png_path = assets / ("%s.png" % name)
        if convert(svg_path, png_path):
            wrote_png = True
            print(png_path)
        else:
            print("no rsvg-convert/magick found; wrote SVG only: %s" % svg_path)
    if args.svg_dir:
        print("SVGs kept in %s" % svg_dir)
    return 0 if wrote_png or args.svg_dir else 1


if __name__ == "__main__":
    sys.exit(main())
