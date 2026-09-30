# Contributing: how it works and how to add cards

I'm a Cognition support engineer. I built Professor Devin to help me learn the
commands I use when I investigate a support issue. This file explains where
the facts come from and how I add more practice.

## Where the facts come from

I use the captured help files in `content/help/` for Devin commands and flags.
They come from Devin CLI 3000.11.3. If I update the CLI version, I capture its
help again and save the version output in `content/help/VERSION`.

Slash-command facts come from the documentation snapshots under `../docs/`.
`content/help/slash.txt` lists the allowed slash commands and their source
lines. I don't add a slash command that isn't in that file.

For the `shell` category, I use `../GUIDE.md`. I keep the line number in each
card's source so the test can check the quoted line.

`content/support/SOURCES.md` lists support facts from real repro sessions.
Those facts can support flashcards and tickets when their `source` field names
one or more keys from that table. Command cards stay limited to
`content/help/`, `../GUIDE.md`, and `../docs/` for slash commands.

I don't invent command behavior or output. The captured help and approved
references are the source of truth.

## Install and files

I run `install.sh` to make `dojo.py` executable and add the
`~/.local/bin/professor-devin` symlink. The installer is safe to run again and
prints a PATH hint if `~/.local/bin` is not on `PATH`. Content paths resolve
from the real `dojo.py` location, so the symlink works from another directory.
The command's help uses `professor-devin` as its program name.

I follow `DESIGN.md` for terminal styling, including every new screen.

## Where cards live

- Devin command cards are in `content/commands.json`.
- Flashcards load from the sorted `content/cards*.json` files and
  `../cards.tsv`.
- Mystery tickets load from the sorted `content/scenarios*.json` files.
- Live drills load from `content/drills.json`.

The support pack uses `content/commands.json`, `content/cards.support.json`,
and `content/scenarios.support.json`. The loader merges the command cards and
reads all matching flashcard and ticket files. The optional `tags`, `source`,
and `confidence` fields are accepted on every card type.
The captured CLI version is in `content/help/VERSION`.

## Devin command cards

A command card has these fields:

- `id`: unique name for the card.
- `category`: one of `launch`, `sessions`, `auth`, `config-rules`, `skills`,
  `mcp`, `plugins`, `models`, `cloud`, `maintenance`, `integration`, `slash`,
  or `shell`.
- `tier`: 1, 2, or 3.
- `task`: a concrete goal in plain English. Don't put the answer flag,
  subcommand, or command path in the task. Tasks must be unique. If two cards
  use the same flag on different subcommands, say what each subcommand is for.
- `answers`: one or more correct commands. Use placeholders such as
  `<session>`, `<prompt>`, `<name>`, `<url>`, `<file>`, `<path>`, `<ports>`,
  and `<id>` for values the player supplies. A placeholder matches one token.
- `blank`: the part hidden in a fill-in question. If omitted, the game chooses
  the first flag or the final subcommand word.
- `source_file`: the captured help file used for a Devin command card, such as
  `devin.txt`. Shell cards cite their GUIDE line in `source`.
- `kind`: `write` or `fix`.
- `hint`: a useful nudge that doesn't give away the full answer.
- `explain`: the matching help line, copied exactly, followed by one short
  line that says when to use the command.

`tags`, `source`, and `confidence` are optional. A `fix` card also needs
`broken` and `error`. I record parse errors against the installed CLI in a
throwaway directory. Help and parse-error checks are okay; I don't log in or
run commands that spend credits to record card errors. When the game reveals
an answer, it also shows the card's confidence if one is set.

Here is a command-card example. Change its ID and task before adding a copy:

```json
{
  "id": "example-version-card",
  "category": "maintenance",
  "tier": 1,
  "task": "A customer needs to confirm which Devin release is installed.",
  "answers": ["devin --version"],
  "blank": "--version",
  "kind": "write",
  "hint": "Look at root help and find the option that starts with v.",
  "explain": "-V, --version\nUse it when checking whether the customer's CLI is on the expected release.",
  "source_file": "devin.txt",
  "confidence": "confirmed"
}
```

### Tiers and deck coverage

Tier 1 is the daily core: `devin`, `devin -- <prompt>`, `-p`, `-c`, `-r`,
`--model`, `--permission-mode`, `devin list`, `devin auth status`,
`devin auth login`, `devin doctor`, `devin --version`, `devin update`,
`devin mcp list`, `devin mcp add`, `devin rules list`, `devin skills list`,
`devin ssh`, `devin forward`, `devin models list`, the five most common
documented slash commands, and `type -a devin`.

Tier 2 holds other useful commands. Tier 3 completes the less common parts:
`cloud drs`, `migrate`, `acp`, `uninstall`, `setup`, `desktop`, `plugins
prune`, MCP OAuth/header/environment options, `--gateway`, and `--config`.

Tests check that every top-level command, subcommand, and help-listed flag has
at least one card. The only automatic exclusions are `-h` and `--help`, plus
items listed in `COVERAGE_EXEMPT`. That list is empty now. Keep it short and
document any exception in the test.

The deck must have cards in every category. It also includes fix cards for
known traps: the print/trust option-order error, print mode in an untrusted
directory, a misspelled flag, and `mcp add` without its required name.
Every fix card's corrected answer must parse, and its broken command must not
match the answer.

The `shell` category is for general support work from `../GUIDE.md`. Current
cards cover log lookup, live log search, JSON and config checks, process and
socket inspection, file tracing, environment inspection, PATH checks, HTTP
connectivity, print-mode scripting, and the support one-liners. That includes
`type -a`, `command -v`, `rg -z`, `strace -f -e trace=file`, `lsof -p`,
`sqlite3 -readonly`, `jq`, `tail -F`, and `/proc/<pid>/environ` checks. The
support one-liners include `where bash`, `nohup`, quota-log search, and
`pgrep -af language_server`. I keep each answer tied to its cited GUIDE line;
I don't add a command that the guide doesn't show. I leave out
`lsof -iTCP -sTCP:LISTEN -P -n` and `env | sort` because neither appears in the
current guide.

### How command answers are checked

For Devin commands, the game builds a parser from the captured help. It reads
subcommands from `Commands:` sections and options from the option lines.

I split an answer into shell-like tokens and require it to start with `devin`.
The parser resolves the subcommand path, maps short options to long ones, and
accepts `--flag=value` as the same as `--flag value`. It recognizes required
and optional option values. An optional value is taken from the next token
only when that token doesn't start with a dash. Boolean options take no value.
Everything after `--` is one prompt positional.

Option order doesn't matter. The subcommand path and option/value pairs must
match, and positional arguments must stay in order. Placeholders match one
token. For example, `-p --respect-workspace-trust false "x"` is not the same
as `--respect-workspace-trust=false -p <prompt>`.

When an answer is wrong, the game points out unknown subcommands or flags,
suggests close matches, and reports missing options, extra options, or the
wrong number of positional arguments. It then shows the canonical answer and
the matching help line from its source file, the explanation, and the
self-grade prompt. Slash commands are checked against the command word in
`slash.txt`, with arguments compared as tokens. Shell answers use normalized
exact matching.

## Training flow

A bare `professor-devin` starts 10 command rounds and one mystery-ticket boss.
I can also run `professor-devin train [CATEGORY ...] --rounds N --tier 1|2|3
--seed N`. A tier limit includes every lower tier. A fixed seed makes a run
repeatable. An unknown category prints the valid category names.

`professor-devin categories` shows each category's card count, seen count,
mastered count, due count, and mastery bar. `professor-devin stats` shows my
overall progress, `professor-devin list` shows cards and Leitner boxes, and
`professor-devin reset --yes` clears saved progress.

New cards are introduced from the lowest tier first, then by category in
round-robin order. A session introduces at most five new cards. The existing
overflow rule stays in place.

The command question changes as I learn each card. The game uses a Leitner
box, a numbered level for how well I know an item:

- Box 1: recognize the shown command from four task choices.
- Box 2: fill in a missing part of the command.
- Box 3 and up: recall the whole command from its task.
- Fix cards always show the broken command and error.

Choices are shuffled. Recognition choices come from other write-card tasks,
prefer the same category, and never use fix cards, help subcommands, duplicates,
or the correct task.

The game gives 5 XP for recognition, 10 for fill-in, and 15 for recall or fix.
Using a hint or self-grading halves that round's command XP. XP also uses the
same global streak multiplier as the mixed game. The training summary includes
category accuracy and the number of new cards coming up next.

## Flashcards and tickets

Here is a flashcard example. Support flashcards can include a source key from
`content/support/SOURCES.md`:

```json
{
  "id": "example-flash-card",
  "topic": "launch",
  "q": "Which command prints the installed CLI version?",
  "answers": ["devin --version"],
  "keywords": ["--version"],
  "hint": "Check the root help options.",
  "explain": "The root help lists a version option.",
  "source": "S-MASTER",
  "confidence": "confirmed"
}
```

Flashcards need `id`, `topic`, `q`, `answers`, `keywords`, `hint`, and
`explain`. They can also have four `choices`; the correct answer must be one
of them. I keep facts from the TSV cards as they are and add new cards only
from approved sources.

Here is a ticket example. Replace the sample ID before saving it:

```json
{
  "id": "example-ticket",
  "topic": "debug",
  "title": "A version check",
  "ticket": "A customer needs to check which CLI release is installed.",
  "prompt": "customer@laptop ~/app$ ",
  "turns": 2,
  "commands": [
    {
      "id": "show-version",
      "match": ["devin --version"],
      "output": "devin 3000.11.3 (9c803229faa4)",
      "evidence": true,
      "source": "recorded"
    }
  ],
  "unknown_output": "(no useful output)",
  "root_cause": {
    "q": "What should the customer check?",
    "choices": ["The CLI version", "The wallpaper", "The mouse", "The monitor"],
    "answer": 0
  },
  "fix": {
    "q": "What should they do first?",
    "choices": ["Read the version", "Restart the monitor", "Change the wallpaper", "Replace the mouse"],
    "answer": 0
  },
  "optimal": ["devin --version"],
  "explain": "The version output identifies the installed CLI release.",
  "source": "S-MASTER",
  "confidence": "confirmed"
}
```

Tickets need a topic, customer message, prompt, turn limit, command matches,
unknown-command output, four choices for both questions, an optimal command
chain, and an explanation. Each command has its own ID, match patterns, output,
evidence flag, and `recorded` or `simulated` label. The item's `source` names
one or more support-source keys, separated by comma and space. Every key must
exist in `SOURCES.md`.

The terminal ticket uses a small shell simulator. It matches commands without
case sensitivity, tags recorded or simulated output, and tracks new evidence.
An unmatched known command gets the ticket's unknown output. An unknown
command gets a shell-style error; a `PS ` prompt uses PowerShell's error form.
Repeated commands still use a turn but don't add evidence. `ticket` reprints
the ticket, `hint` shows the next optimal command and costs XP, `solve` ends
the shell part, and `quit` ends the session.

Flash, drill, and ticket items use the same spaced-repetition system. Correct
answers move an item up one box, up to box 5. Missed flashcards can be
requeued once later in that session.

## Mixed game, state, and checks

`professor-devin play` keeps the original mix of flashcards, live drills, and
mystery tickets. The default plan is six flashcards, two drills, four more
flashcards, then one ticket. If no item is eligible for a planned round, the
game falls back to flashcards.

`play --mode flash`, `play --mode drill`, and `play --mode combo` choose one
kind. `--topic REGEX` filters topics, `--rounds N` limits rounds, `--seed N`
makes order repeatable, and `--no-live` disables live drills.
`--allow-credits` enables drills that may use credits. The game saves its
state under `$PROFESSOR_HOME`, then `$DOJO_HOME`, then
`~/.professor-devin/`.

I run the tests with `python3 -m unittest discover -s tests -v` and lint with
`flake8 --max-line-length 120 dojo.py tests/`. The tests cover parser aliases
and option ordering, deck coverage, every command answer and fix, answer forms,
spaced repetition, combo behavior, categories, saved state, the install
symlink, and terminal output.

I keep review captures in `transcripts/`:

- `prof-train.txt`: a seeded run with right, wrong, skipped, and hinted
  answers, plus a misspelled flag and option-order trap.
- `prof-forms.txt`: recognize, fill-in, recall, and fix forms.
- `prof-categories.txt`: the category table.
- `prof-color.ansi`: a four-round terminal color capture.
- `prof-deck.txt`: the command cards in a format that's easy to review.
- `render/prof-light.html` and `render/prof-dark.html`: HTML renders of
  `prof-color.ansi` in light and dark themes.

`transcripts/README.md` indexes the rest of the captures (drill results,
mystery-ticket runs, and test/lint output).
