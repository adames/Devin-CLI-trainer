# dojo terminal design: adames ember, "notebook" register

Source: the user's adames-ember-design SKILL.md (hard rules only; its README/tokens were not provided).
This maps those rules onto a terminal UI. Mechanics, scoring and content do not change.

## Tokens (the only styles allowed)
| token   | terminal form                          | use |
|---------|----------------------------------------|-----|
| ink     | default fg, no SGR                     | all content and most chrome |
| muted   | SGR 2 (dim)                            | metadata: xp, streak, turns, [sim]/[rec], hints labels |
| strong  | SGR 1 (bold)                           | display titles, positive state labels |
| accent  | ember: `38;5;208` default; `DOJO_ACCENT` = `0..255` -> `38;5;N`, or `#rrggbb` -> `38;2;r;g;b`; invalid -> default | ONLY the `❭` input marker in front of every prompt. Nothing else. |
| danger  | SGR 1;7 (bold + inverse fill)          | negative outcome labels (missed, drill failed, wrong root cause) |
Never emit red/green/cyan/any other fg or any bg colour. Remove the existing 31/32/36 uses.
Both themes: because only default fg, dim, bold, inverse and one accent are used, output works on light and dark terminals.

## Chrome vs content
- chrome = labels the game owns (headers, prompt labels, status lines, summary/stats labels, level titles, banners).
  Write source strings in natural case and pass them through `chrome()` which lowercases at render time.
- content = card questions/answers/explains/hints, ticket titles and text, choices, simulated/recorded command output,
  user input. Never change its case.

## Glyphs (no emoji)
`❭` prompt marker, `✱` question marker, `●` found/filled/correct, `○` not found/missed-item bullet, `·` separator,
`✕` give-up/quit notice.
Rules: strong rule `━`, hairline `─`. ScoreBar cells: filled `━` (ink), empty `─` (muted).
ASCII fallback when `sys.stdout.encoding` is not UTF-8: `❭`->`>`, `✱`->`*`, `●`->`*`, `○`->`o`, `·`->`-`, `✕`->`x`,
`━`->`=`, `─`->`-`.

## Layout
Width `W = min(shutil.get_terminal_size((72, 24)).columns, 72)`.

Session header (once, at start of `train` and `play`):
```
professor devin · play · 6 flash · 2 drill · 4 flash · 1 ticket   (strong chrome line)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  (strong rule, W wide)
next time: professor-devin play                                  (muted; only when launched from the menu)
```
Train uses `professor devin · train · 10 command rounds · 1 ticket boss`. The muted third line is the exact
CLI equivalent of the menu choice.

Round header:
```
(blank line)
round 04/13 · flash · hooks            l3 triage tech · 420 xp · x1.75
```
Left part ink, right part muted, right-aligned to W (if it doesn't fit, put the right part on its own line).
Numbers zero-padded to the width of total rounds. Train headers are the same (`round 03/10 · launch · recall`),
except the hairline under the header is omitted — the answer box provides the rules.

Questions and the answer box: a round question starts with `✱ ` (plain ink marker, text keeps content case).
Then a blank line, a muted `·`-separated footer of key hints (`? hint · skip · quit`,
`1-4 to choose · ? hint · skip · quit`, ...), a hairline, the `❭ ` input line (accent marker), and a closing
hairline before the outcome. Re-prompts inside the box (`?` hints, invalid choices) print no new rules.
The combo shell is exempt: its prompt is `❭ ` + the scenario's own prompt string (content, keep case), with
one footer printed after the ticket text instead. Drills print one footer (`!command runs a shell command ·
give up`) and bare `❭ ` prompts. The count-it prompt is `❭ count it as correct? y/n ` (muted chrome label,
no rules). Numbered options: `  1 choice` with the digit muted; the selected/default row shows an accent
`❭ ` marker and a strong title (menu).

Menu logo banner (home menu):
```
⠀⣴⣾⣶⡄⠀⠀⠀⠀
⠀⠛⠿⠟⠻⣶⣾⣶⡄  professor devin                       (strong)
⠀⣤⣶⣦⣴⠿⢿⠿⠃  learn the devin cli by typing it      (muted)
⠀⠻⢿⠿⠃⠀⠀⠀⠀  cards written for devin cli <content> · you have <ver>   (muted)
```
followed by a muted progress line (`l1 intern · 0 xp · 0 cards due today`), the `✱ What do you want to
practice?` question, the numbered options, the `1-7 to choose · ↵ quick start · q quit` footer, and `❭ `.

The setup wizard (first run or `professor-devin setup`) reuses the same banner with the fourth line reading
`first run · cards written for devin cli <content> · you have <ver>` (or `setup · ...`), then a `✱ How well do
you know the Devin CLI?` question with the same numbered-option styling.

Coach tips: on the beginner profile, one muted chrome line `tip  <text>` is printed between the question and
the footer the first two times a form is seen.

Outcomes:
- correct: strong `● correct` + muted `+N xp`
- self-graded: strong `● counted` + muted `+N xp`
- wrong/skip: danger label ` missed ` then on following lines ink `answer  <answer>` and ink explain
- drill pass: strong `● drill passed`; drill fail/give up: danger ` drill failed `
- combo: after each command, command output (content) then muted status line `evidence ●●○ · combo x2 · turns 2/8`
  (SignalDots: ● per key evidence found, ○ per remaining). `[sim]`/`[rec]` provenance tag muted, appended to output from
  simulated/recorded commands (add `[rec]`; today only `[sim]` shows).
- root cause wrong: danger ` wrong root cause ` + muted `-20 xp`; right: strong `● root cause`.

Mystery ticket intro: `✱ ` + strong chrome label `mystery ticket` + ` · <title>` (title is content), strong
rule, then ticket text, then one muted footer (`shell commands as the customer · hint (-10 xp) · ticket ·
solve · quit`). Root-cause and fix questions print as `✱ root cause  <q>` / `✱ fix  <q>` with muted labels,
numbered muted-digit choices, a `1-4 to choose or type the answer` footer, and the `❭ ` answer box.

Summary and stats (app data surfaces):
- section title strong chrome (`session summary`, `stats`), strong rule `━` under it.
- KVList: keys muted chrome left-padded to a fixed width (14), values ink; numbers right-aligned in a fixed width
  (tabular): e.g. `xp gained        390`, `accuracy       7/13  53.8%`.
- DataTable for per-topic accuracy: thead `topic  right  seen  acc  ` (muted chrome), strong rule under thead, rows with
  right-aligned numbers and a 10-cell ScoreBar for acc. Sorted by topic.
- weakest topics, missed items (`○ <question>` then indented `<answer>`), due tomorrow, best combo, leitner boxes
  (stats: `box 1  box 2 ...` as a DataTable header with counts).
- level progress in stats: `l3 triage tech` + ScoreBar of progress to next level + muted `420/450 xp`.

## NO_COLOR / non-TTY
No SGR at all. `FORCE_COLOR` (any value except `""`/`0`) forces color on even when piped. Lowercase chrome,
glyphs and layout still apply. Danger labels render as `[missed]`, `[drill failed]`,
`[wrong root cause]` so the form distinction survives without inverse fill.
