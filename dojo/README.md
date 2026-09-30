# Professor Devin

I'm a support engineer at Cognition. I built Professor Devin so I could stop
looking up Devin CLI flags and start knowing them. It asks me to write real
commands, points out what I got wrong, and brings missed cards back later.

This folder is part of the [devin-cli-mastery kit](../README.md); it expects
`../cards.tsv` and `../GUIDE.md` to be in place next to it.

## Install

1. Open a terminal in this project folder.
2. Run `bash install.sh`. It puts `professor-devin` in `~/.local/bin`.
3. Run `professor-devin`.

## Your first 5 minutes

The first run gives you 10 command rounds and a mystery-ticket boss. Each round
shows a support task. Type the command you would use, then press Enter. Type
`?` for a hint. Type `skip` to see the answer and explanation without taking a
guess.

The game keeps your progress between runs. It uses spaced repetition: missed
cards come back sooner, and cards you know stay away longer.

### Four question types

- **Recognize:** See `devin -c` and choose what it does.
- **Fill in:** See the task and `devin ___`; type the missing part.
- **Recall:** See “Reopen the latest session in this directory”; write the
  whole command.
- **Fix:** See a broken command and its error; write the corrected command.

The form gets harder as you learn a card. Fix cards always show the broken
command and error.

## Categories and tiers

Categories group commands by job: `launch`, `sessions`, `auth`, `config-rules`,
`skills`, `mcp`, `plugins`, `models`, `cloud`, `maintenance`, `integration`,
`slash`, and `shell`.

Tier 1 covers commands I use often. Tier 2 adds useful commands. Tier 3 fills
out the less common parts of the CLI. `--tier 2` includes tiers 1 and 2.

For a focused session, run
`professor-devin train launch --rounds 5 --tier 1 --seed 1`. Replace `launch`
with any category. `--seed` makes the order repeatable.

## Other commands

- `professor-devin play --mode flash` runs flashcards.
- `professor-devin play --mode drill --no-live` practices without running live
  drills.
- `professor-devin play --mode combo` runs a mystery ticket.
- `professor-devin stats` shows your progress.
- `professor-devin list --type command` lists command cards.
- `professor-devin categories` shows the category deck.
- `professor-devin reset --yes` clears saved progress.

You can add `--topic REGEX`, `--rounds N`, and `--seed N` to `play`. Live
credit-using drills are off unless you add `--allow-credits`.

## Saved progress

Progress goes to `$PROFESSOR_HOME` if set, otherwise `$DOJO_HOME`, otherwise
`~/.professor-devin/`.

## Troubleshooting

If `professor-devin` is not found, add `~/.local/bin` to your `PATH`, then
open a new terminal. Run `professor-devin --help` to see the available
commands.

## Development

```
python3 -m unittest discover -s tests -v
flake8 --max-line-length 120 dojo.py tests/
```

## More docs

- [CONTRIBUTING.md](CONTRIBUTING.md) — where card facts come from and how to
  add cards.
- [SPEC.md](SPEC.md) — exact game behaviour.
- [DESIGN.md](DESIGN.md) — terminal styling rules.
- [transcripts/README.md](transcripts/README.md) — index of review captures.
