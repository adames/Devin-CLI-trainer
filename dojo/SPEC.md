# Professor Devin game spec

I built this as one terminal game for a Cognition support engineer learning
Devin CLI and general CLI work. It combines command writing, flashcards, live
drills, and mystery tickets under one progress and XP system.

The engine stays in one file, `dojo.py`. It uses Python 3.8 or newer and the
standard library only. It runs on macOS and Linux; Windows support is
best-effort.

## Project files and saved progress

```text
dojo/
  dojo.py
  content/commands.json
  content/cards*.json
  content/drills.json
  content/scenarios*.json
  content/help/
  content/support/
  tests/
```

The built-in flashcards also include the rows from `../cards.tsv`. Command
cards come from `content/commands.json`. The game loads flashcards and tickets
from matching JSON files in sorted filename order. Content paths are relative
to `dojo.py`, not the current working directory.

The game also loads user-added JSON files from
`$PROFESSOR_HOME/content/*.json` (or the selected legacy state home). An item
with `root_cause` is a ticket, one with `kind` is a drill, and other items are
flashcards.

Progress is stored in `$PROFESSOR_HOME`, then `$DOJO_HOME`, then
`~/.professor-devin/`. The state is in `state.json`; live-drill work areas are
under `arena/<drill-id>/`.

## Running the game

```text
professor-devin
professor-devin menu
professor-devin train [CATEGORY ...] [--rounds N] [--tier 1|2|3] [--seed N]
professor-devin categories
professor-devin play [--mode flash|drill|combo] [--topic REGEX] [--rounds N]
                     [--seed N] [--no-live] [--allow-credits]
professor-devin stats
professor-devin list [--type flash|drill|combo|command]
professor-devin reset [--yes]
professor-devin help [COMMAND]
professor-devin -V | --version
```

A bare run opens the home menu when stdin and stdout are both terminals; when
piped it still starts 10 command-writing rounds and one ticket boss, so
scripts keep working. The menu offers quick start, a topic picker over the
command-card categories, flashcards, a mystery ticket, live drills, progress,
and a how-to-play screen; every activity also prints the exact CLI command
that would have launched it (`next time: professor-devin train`). `train` can
limit the categories, number of rounds, highest tier, and random seed. `play`
keeps the mixed flashcard, drill, and ticket game. Unknown categories produce
an error listing the valid category names. `--help` and `help [COMMAND]` print
clap-style help; `-V`/`--version` prints the game and content versions.

All answers use regular `input()`. This lets tests send answers through stdin;
the game doesn't read raw keys or open `/dev/tty`. End-of-file ends the run
gracefully and saves progress. Ctrl-C also saves and exits cleanly.

Colors use ANSI only when stdout is a terminal and `NO_COLOR` is unset, or
always when `FORCE_COLOR` is set to a value other than `0`. Each round opens
with a counter header (`round 03/10 · launch · recall`), asks its question
with a `✱` marker, and takes the answer on a `❭ ` line between hairlines.
Styling: see `DESIGN.md`.

## Session plan and item selection

The mixed `play` plan has six flashcards, two drills, four more flashcards,
then one combo ticket. `--rounds N` caps the plan; a ticket counts as one
round. The `flash`, `drill`, and `combo` modes choose only that kind of item.
If a planned type has no eligible item, the game uses a flashcard instead.

For each type, selection prefers due items, with the most overdue first. It
then introduces new cards, up to five new items per session, and finally
chooses a not-yet-due item with a low Leitner box. `--seed` makes shuffling
repeatable.

An item appears at most once per session through normal selection. This
applies to flashcards, drills, and tickets. A wrong flashcard goes back to box
1 and may be requeued once later in the same session. The requeue becomes
ready after three more flash rounds. If it is the only eligible card, it can
appear early; the game never serves it on consecutive rounds.

## Spaced repetition

Each item ID has a Leitner box from 1 to 5. The box is a simple measure of how
well I know the item.

| Box after a correct answer | Wait before it is due |
|---|---:|
| 2 | 1 day |
| 3 | 3 days |
| 4 | 7 days |
| 5 | 21 days |

New items start in box 1. A correct answer moves the box up by one, to a
maximum of 5, and sets the due date using the new box's interval. A wrong
answer resets the box to 1 and makes the item due now. The game tracks how
often I saw and got each item right, and when I last saw it.

## XP, streaks, levels, and summary

The global streak counts consecutive correct rounds. The multiplier is
`min(1 + 0.25 * streak, 3.0)`. A wrong round resets it to zero.

- Flashcards give 10 XP for an exact or automatic correct answer, 5 XP when a
  hint was used, or 5 XP when I self-grade.
- Live drills give 25 XP plus a speed bonus:
  `max(0, 15 - elapsed_seconds // 20)`.
- Tickets start at 50 XP, add 10 for each evidence command and 5 for each
  unused turn, then use the best in-ticket combo multiplier. A wrong root
  cause costs 20 XP, down to zero; a correct fix adds 25 XP.
- Command cards give 5 XP for recognize, 10 for fill-in, and 15 for recall or
  fix. A hint or self-grade halves that command round's XP.

The global streak multiplier applies to round XP. Level is
`floor(sqrt(xp / 50)) + 1`. Titles are Intern, Log Reader, Triage Tech, Tracer,
Config Whisperer, Root-Causer, then Staff RCA for level 7 and above. A daily
streak counts consecutive days with at least one session.

The summary shows XP gained, accuracy, topic accuracy, the weakest topics,
missed items, items due tomorrow, and the best combo. Training summaries also
show category performance and the next new cards.

## Command-card training

Each card has one stable ID, a category, a tier, a task, answers, a hint, an
explanation, and a `write` or `fix` kind. The task describes a real goal
without giving away its command. Answers are checked against the captured
help-derived parser, except shell answers, which use normalized exact matching,
and slash answers, which use the command word and argument tokens.

The card's Leitner box chooses its question form:

- Box 1: recognize the command from four task choices.
- Box 2: fill in the hidden part of a command template. Typing the whole
  command also counts as correct.
- Box 3 or higher: recall the whole command from its task.
- A fix card always shows a broken command and its error.

Recognition distractors come from other write cards, preferably in the same
category. They are unique and never include the correct task, a fix card, or a
help subcommand. New cards are introduced by tier, then category round-robin,
with a limit of five per session.

The Devin parser reads subcommands from captured `Commands:` help sections and
flags from option lines. It requires the command to start with `devin`, maps
short flags to long names, and treats `--flag=value` like `--flag value`.
Required values are consumed. Optional values use the next token only when it
doesn't start with a dash. Everything after `--` is one prompt positional.
Option order doesn't matter; subcommand paths and flag/value pairs must match,
and positionals stay in order. Placeholders match one token.

For a wrong answer, the game reports unknown subcommands or flags, suggestions,
missing or extra flags, and positional-count errors before showing the answer.
It then shows the matching help lines and asks whether to count the answer as
correct. A fix card's broken command must not match its corrected answer.

## Flashcards

A flashcard needs `id`, `topic`, `q`, `answers`, `keywords`, `hint`, and
`explain`. It can include four `choices`; the first correct answer must be one
of those choices. Topics are `launch`, `sessions`, `auth`, `config`,
`permissions`, `modes`, `slash`, `cloud`, `hooks`, `rules`, `skills`, `mcp`,
`logs`, `debug`, `acp`, and `general-cli`.

The game lowercases answers, removes quotes and backticks, and collapses
whitespace. An answer is correct if it matches a saved answer or contains all
required keywords. With choices, the game shuffles a/b/c/d labels and accepts
the letter or the full choice text.

Type `?` once to see a hint. A wrong answer reveals the answer and explanation
and asks whether to count it as correct. `skip` reveals the same information
without asking for self-grading. If the explanation is identical to the
answer, it appears only once. Confidence is shown when the item has it.
Command-card and ticket reveals also show confidence when the item has it.

The original TSV facts stay as written. New cards must use the approved
references; I also add multiple-choice questions about documented precedence
and mode ordering.

## Live drills

A drill has `id`, `topic`, `prompt`, `platforms`, `requires`,
`costs_credits`, `setup`, `kind`, `cleanup`, and `explain`. Answer drills also
have `truth`; check drills have `check`.

Each run recreates `$PROFESSOR_HOME/arena/<drill-id>/`, uses it as the working
directory, and sets `DOJO_ARENA`. An answer drill compares the response with
the truth command's normalized output. A check drill passes when its check
command exits successfully. In either kind, `!<command>` runs a shell command
in the arena and shows its output. I can do that repeatedly before answering.
`give up` counts as wrong and shows the explanation.

A drill is skipped when its platform doesn't match, a required program is
missing, required auth reports `Not logged in`, it may use credits and
`--allow-credits` is absent, or `--no-live` is set. Cleanup always runs,
including after Ctrl-C. Truth and check commands must not require `jq`; use
Python for JSON checks.

The current drill set covers CLI version, newest log, doctor checks, auth
status, project skills, rules, hooks, local deny rules, MCP setup, session
counts, log searches, invalid JSON, a local port, system policy tracing, and
print mode. Each drill must be checked against the installed CLI. If its
described behavior isn't true, fix or remove it and record why.

## Mystery tickets

A ticket has an ID, topic, title, customer message, shell prompt, turn limit,
command patterns, unknown-command output, root-cause question, fix question,
optimal command chain, and explanation. Each question has four choices and a
zero-based answer index.

The ticket shell matches the first command entry whose case-insensitive
regular expression fully matches the whitespace-normalized command. Each
command costs one turn. A new evidence command adds evidence. Running the
same command again costs a turn but adds no evidence. Recorded and simulated
outputs get `[rec]` and `[sim]` provenance labels.

If a command's first token isn't in the known-command set, the simulator
prints a bash command-not-found message. At a prompt starting with `PS `, it
prints the PowerShell form instead. A known but unmatched command prints the
ticket's unknown output. Command lookup ignores case. The known set includes
`devin`, `cat`, `ls`, `jq`, `rg`, `grep`, `env`, `echo`, `type`, `which`,
`command`, `bash`, `curl`, `ps`, `lsof`, `ss`, `strace`, `tail`, `head`,
`find`, `sqlite3`, `git`, `python3`, `printenv`, `diff`, `where`, `where.exe`,
`tasklist`, `findstr`, `select-string`, `get-childitem`, `get-command`, `dir`,
`pgrep`, `nohup`, `mvn`, `sudo`, `fs_usage`, and `tr`.

Consecutive new evidence commands build the in-ticket combo from x1 to x3.
A non-evidence command resets it to x1. The best combo reached is used for
scoring. `ticket` reprints the customer message. `hint` reveals the next
optimal command and costs 10 XP. `solve` ends shell work; `quit` ends the
session. Running out of turns forces the player to solve.

After solving, the game shows the correct cause and fix, the optimal chain,
the explanation, and evidence found. A correct cause marks the ticket correct
for spaced repetition. A correct fix adds its XP bonus.

## Recorded output rules

When a ticket command is marked `RECORD`, reproduce the fault for real in a
throwaway home directory. Add the installed Devin binary to `PATH`. Paste the
actual output, trim it to 15 lines or fewer, and replace a temporary home path
with `/home/customer`.

If recording needs authentication, or the real behavior contradicts the
scenario, report that instead of making up output. Mark output `SIM` only when
the scenario says to. Simulated output must look like ordinary tool output
from commands such as Bash, `ls`, or `cat`. Do not invent Devin error text.

### S1: hooks file has an extra wrapper

The ticket is: “I added a PreToolUse hook in `.devin/hooks.v1.json` to block
`rm -rf` but it never fires.” The fault is a hooks file wrapped in
`{"hooks":{"PreToolUse":[...]}}`.

Commands: `cat .devin/hooks.v1.json` (evidence, simulated file), `devin
--version` (simulated `devin 3000.11.3 (9c803229faa4)`), `devin doctor`
(record in a project with the file), `ls -la .devin` (simulated),
`python3 -m json.tool .devin/hooks.v1.json` or `jq . .devin/hooks.v1.json`
(evidence, simulated pretty JSON), and `devin rules list` (record). If a
no-auth command can list hooks, record it as evidence.

Cause: the standalone file must contain the hooks object directly. The
`hooks` wrapper is for config or settings files. Fix: remove the wrapper or
move the hook under `hooks` in `.devin/config.json`, then verify with `/hooks`.
Distractors: org enablement, event-name casing, user-only hook loading,
`--sandbox`, dangerous permission mode, or renaming the file.

### S2: an alias hides the executable from Devin

The ticket is: “Devin keeps saying `node: command not found`, but node works
in my terminal.” Simulated Bash output should show an interactive alias but
no exported PATH entry. `command -v node` and `which node` show the alias
target; `type node` explains the alias. `echo $PATH`, `bash -lic 'command -v
node'`, and `bash -lic "echo $PATH"` show the login-shell environment.
`cat ~/.bashrc` or `grep node ~/.bashrc` shows the alias and missing PATH
export. Include `devin --version`.

Cause: node exists only as an alias. Devin takes an environment snapshot from
the login shell at startup; aliases and functions aren't exported. Fix: export
the nvm bin directory in the shell profile and restart Devin. Distractors:
the sandbox blocks node, nvm is unsupported, PATH is too long, `/clear`,
`devin update`, or `--sandbox`.

### S3: a dead proxy blocks network calls

The fault is `HTTPS_PROXY=http://127.0.0.1:9` with nothing listening there.
Use `env | grep -i proxy` or `printenv | grep -i proxy` as simulated evidence.
Record `curl -sv https://cli.devin.ai -o /dev/null`, `devin update`, and
`RUST_LOG=reqwest=trace,hyper=trace CHISEL_LOG_STDERR=1 devin update`. Keep
the proxy/connection error lines. Also record `devin auth status`. If update
doesn't use the network without auth, choose another no-auth network command
and report the change.

Cause: the CLI uses proxy environment variables in system mode, and the
configured proxy is dead. Fix or unset `HTTPS_PROXY`, or set proxy mode and
URL in config or use `NO_PROXY`. Distractors: expired token, Devin service
outage, missing TLS CA, reinstall, logging in again, or `--sandbox`.

### S4: print mode can't show a trust prompt

The ticket is: “`devin -p` works on my laptop but fails in our CI job in a
freshly cloned repo.” Record `devin -p "summarize the repo"` in a fresh
untrusted directory only if the trust message appears before auth. If it only
shows a login error, report that. Also record `devin --help | grep -A3 trust`.
The version, auth status, and directory listing can be simulated.

Cause: print mode can't show the workspace-trust prompt. Fix: pass
`--respect-workspace-trust false` in CI or trust the directory first.
Distractors: `DEVIN_MODEL`, `--sandbox`, or `-c`.

### S5: team policy still asks in dangerous mode

The ticket is: “I run with `--permission-mode dangerous` but Devin still asks
before every git push. Bug?” Simulate the local config files without ask
rules and the missing `config.local.json`. Record a normal `devin doctor`.
Simulated evidence may show `team_settings.bin` in `~/.cache/devin` and
`strings ~/.cache/devin/team_settings.bin | grep -i push` with an ask rule.

Cause: an org or team ask rule cannot be overridden by a permission mode or
local config. The admin must change Team Settings. Distractors: deprecated
dangerous mode, project config overriding CLI flags, model judgment, a local
allow rule, `/bypass`, or deleting the cache.

### S6: an old binary comes first on PATH

The ticket is: “I ran `devin update` twice and it says I'm on the latest, but
`devin --version` still shows an old version.” Simulate an old version and
`type -a devin` or `which -a devin` showing `/usr/local/bin/devin` before
`/home/customer/.local/bin/devin`. Simulate PATH with `/usr/local/bin` first
and the newer version from `~/.local/bin/devin --version`. Record
`ls ~/.local/share/devin/cli/_versions` with the path scrubbed. Simulate
`ls -la /usr/local/bin/devin` showing an old, root-owned file.

Cause: a second old copy earlier on PATH hides the updated binary. Fix the
PATH order or remove the stale copy, run `hash -r`, and check `type -a devin`.
Distractors: `devin update --force`, clearing the cache, or reinstalling with
sudo.

### S7: Devin imported a Claude hook

The ticket is: “Some hook keeps blocking my commands with ‘blocked by policy’
but I have no Devin hooks configured.” Simulate no `.devin` directory, a
minimal user config, `.claude/settings.json`, and a hook that prints the
message and exits 2. Include `devin --version`.

Cause: Devin imports hooks from `.claude/settings.json` because
`read_config_from.claude` is on by default. Fix the hook or set
`read_config_from.claude=false` in user config, then use `/hooks` to confirm
the source. Distractors: org policy, sandbox, damaged sessions DB, or
Windsurf rules.

### S8: the MCP package name is misspelled

The fault is an stdio server called `fs` whose command is
`npx -y @modelcontextprotocol/server-filesystm /home/customer/docs`. With a
temporary home, record `devin mcp list`, `devin mcp get fs`, and the MCP
config file actually written by `devin mcp add`; don't create that file by
hand. Use command output as evidence only when it shows useful status.
Simulated npm output may show the E404 response for the misspelled package.
Include `devin --version`.

Cause: the package name typo stops the server from starting. Remove `fs` and
add it again with `@modelcontextprotocol/server-filesystem`; run the command
manually to verify it. Distractors: org MCP policy, `devin mcp login`, HTTP
transport, enabling the server, restarting the terminal, or changing the
allow list.

## Tests and checks

Tests use `unittest` and a temporary `DOJO_HOME`. They cover answer
normalization, keyword grading, multiple choice, Leitner transitions and due
dates, due-first selection, the five-new-card cap, seeded order, combo
matching and scoring, content validation, command coverage, and a piped
end-to-end run that saves `state.json`. Content checks also validate required
fields, unique IDs, multiple-choice answer indexes, regex patterns, reachable
optimal commands, and reachable evidence commands. The drill set is checked
against the installed CLI; if a drill doesn't match, fix it or remove it and
record why.

Run:

```text
python3 -m unittest discover -s tests -v
flake8 --max-line-length 120 dojo.py tests/
```
