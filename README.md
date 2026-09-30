# Devin CLI mastery

A self-study kit for learning Devin CLI (pinned to CLI v3000.11.3) for support
work. It has three parts: a written guide, a bash flashcard drill, and a
terminal game ("Professor Devin") that quizzes real commands against captured
`--help` output.

## Start here

- **Read:** [GUIDE.md](GUIDE.md) — learning plan, architecture, labs, and
  break-it drills.
- **Drill:** `./drill.sh [N] [regex]` — flashcards from `cards.tsv`.
- **Play:** `cd dojo && bash install.sh && professor-devin` — the game.

## Folder map

```
GUIDE.md     learning plan, mental model, commands, labs, break-it drills,
             triage checklist
cards.tsv    66 Q/A flashcards (question<TAB>answer); used by drill.sh and
             also loaded by the dojo
drill.sh     bash flashcard drill; misses weighted 3x next run; writes
             .misses.tsv / .history.log (gitignored)
docs/        offline snapshots of docs.devin.ai CLI pages (see
             docs/README.md)
dojo/        Professor Devin game:
  dojo.py        single-file game, stdlib only, Python 3.8+
  install.sh     installs the professor-devin symlink into ~/.local/bin
  content/       commands.json, cards*.json, scenarios*.json, drills.json,
                 help/ (captured --help output + VERSION),
                 support/ (SOURCES.md + RECORDINGS.md)
  tests/         unittest suite
  transcripts/   review captures (see transcripts/README.md)
  README.md / CONTRIBUTING.md / SPEC.md / DESIGN.md
```

## How the pieces connect

- The dojo reads `../cards.tsv` for flashcards and `../GUIDE.md` **by line
  number** for `shell`-category cards. GUIDE.md is effectively append-only:
  if you edit existing lines, you must update the `source` fields in
  `dojo/content/commands.json` and the tests that verify quoted line text.
- Devin command answers are validated against `dojo/content/help/*.txt`.
- Slash commands come from the `docs/` snapshots.
- Every support fact cites a key in `dojo/content/support/SOURCES.md`.

## Which doc do I read?

| Doc | Audience |
| - | - |
| [GUIDE.md](GUIDE.md) | Learner: the main study guide |
| [dojo/README.md](dojo/README.md) | Playing the game |
| [dojo/CONTRIBUTING.md](dojo/CONTRIBUTING.md) | Adding cards / where facts come from |
| [dojo/SPEC.md](dojo/SPEC.md) | Exact game behaviour |
| [dojo/DESIGN.md](dojo/DESIGN.md) | Terminal styling rules |
| [docs/README.md](docs/README.md) | Index of doc snapshots |

## Updating for a new CLI version

1. `devin --version` — confirm the installed release.
2. Re-capture `devin <cmd> --help` into `dojo/content/help/` and update
   `dojo/content/help/VERSION`.
3. Re-fetch changed doc pages into `docs/`.
4. Run the dojo tests — they check that every command and flag has a card.

## Tests

```
cd dojo && python3 -m unittest discover -s tests -v
flake8 --max-line-length 120 dojo.py tests/
```
