# AGENTS

Professor Devin is a terminal game for learning the Devin CLI: command rounds
validated against the CLI's real `--help`, mystery tickets, flashcards, and
live drills under one XP/spaced-repetition system.

## Layout and commands

- Engine: `dojo/dojo.py` — single file, Python 3.8+, standard library only.
- Content: `dojo/content/*.json` + `dojo/content/help/` (captured `--help`).
- Tests: `cd dojo && python3 -m unittest discover -s tests -v`
- Lint: `cd dojo && flake8 --max-line-length 120 dojo.py tests/`
- Install: `install.sh` (symlink into ~/.local/bin) or `get.sh` (one-line
  curl installer). CLI surface includes `menu`, `train`, `play`, `stats`,
  `categories`, `list`, `reset`, `setup` (profile wizard), `help`.
- Screenshots: `python3 tools/screenshots.py` → `assets/*.png` (regenerate
  after any UI change; needs `rsvg-convert` or `magick`).

## Constraints

- `chrome()` lowercases chrome (labels/headers/status); content (questions,
  answers, card text, command output) is never re-cased.
- No foreground colors besides the accent (ember `38;5;208`, only on the `❭`
  marker); a test rejects `\x1b[3x` literals. See `dojo/DESIGN.md`.
- Shell cards in `dojo/content/commands.json` quote `GUIDE.md` lines verbatim
  and cite them by line number: keep those lines intact when editing the guide
  and run `python3 tools/relink_guide_sources.py` afterwards (a test checks it).
- Content is pinned to Devin CLI 3000.11.92 (`dojo/content/help/VERSION`).
- Behaviour details: `dojo/SPEC.md` (mechanics) and `dojo/DESIGN.md` (styling)
  are the sources of truth — keep them in sync with `dojo.py`.
