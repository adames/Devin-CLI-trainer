# dojo terminal design: adames ember, "notebook" register

Source: the user's adames-ember-design SKILL.md (hard rules only; its README/tokens were not provided).
This maps those rules onto a terminal UI. Mechanics, scoring and content do not change.

## Tokens (the only styles allowed)
| token   | terminal form                          | use |
|---------|----------------------------------------|-----|
| ink     | default fg, no SGR                     | all content and most chrome |
| muted   | SGR 2 (dim)                            | metadata: xp, streak, turns, [sim]/[rec], hints labels |
| strong  | SGR 1 (bold)                           | display titles, positive state labels |
| accent  | ember: `38;5;208` default; `DOJO_ACCENT` = `0..255` -> `38;5;N`, or `#rrggbb` -> `38;2;r;g;b`; invalid -> default | ONLY the `☞` input marker in front of every prompt. Nothing else. |
| danger  | SGR 1;7 (bold + inverse fill)          | negative outcome labels (missed, drill failed, wrong root cause) |
Never emit red/green/cyan/any other fg or any bg colour. Remove the existing 31/32/36 uses.
Both themes: because only default fg, dim, bold, inverse and one accent are used, output works on light and dark terminals.

## Chrome vs content
- chrome = labels the game owns (headers, prompt labels, status lines, summary/stats labels, level titles, banners).
  Write source strings in natural case and pass them through `chrome()` which lowercases at render time.
- content = card questions/answers/explains/hints, ticket titles and text, choices, simulated/recorded command output,
  user input. Never change its case.

## Glyphs (no emoji)
`☞` prompt marker, `●` found/filled/correct, `○` not found/missed-item bullet, `·` separator, `✕` give-up/quit notice.
Rules: strong rule `━`, hairline `─`. ScoreBar cells: filled `━` (ink), empty `─` (muted).
ASCII fallback when `sys.stdout.encoding` is not UTF-8: `☞`->`>`, `●`->`*`, `○`->`o`, `·`->`-`, `✕`->`x`, `━`->`=`, `─`->`-`.

## Layout
Width `W = min(shutil.get_terminal_size((72, 24)).columns, 72)`.

Session banner (once, at start of `play`):
```
devin dojo                                  (strong, display voice)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  (strong rule, W wide)
6 flash · 2 drill · 4 flash · 1 ticket       (muted; derived from the actual plan, run-length grouped; combo is shown as "ticket")
```
Round header (replaces `[L1 Intern | ...]`):
```
(blank line)
round 04/13 · flash · hooks            l3 triage tech · 420 xp · x1.75
──────────────────────────────────────────────────────────────────────
```
Left part ink, right part muted, right-aligned to W (if it doesn't fit, put the right part on its own line). Hairline rule under it (muted). Numbers zero-padded to the width of total rounds.

Prompts: every `input()` prompt = accent `☞ ` + muted chrome label, e.g. `☞ answer  ? hint · skip · quit  `,
`☞ count it? y/N  `, `☞ choose 1-4 or type the answer  `, drill `☞ ` + (`!cmd · give up`) label, combo `☞ ` + the scenario's own prompt string (content, keep case).

Outcomes:
- correct: strong `● correct` + muted `+N xp`
- self-graded: strong `● counted` + muted `+N xp`
- wrong/skip: danger label ` missed ` then on following lines ink `answer  <answer>` and ink explain
- drill pass: strong `● drill passed`; drill fail/give up: danger ` drill failed `
- combo: after each command, command output (content) then muted status line `evidence ●●○ · combo x2 · turns 2/8`
  (SignalDots: ● per key evidence found, ○ per remaining). `[sim]`/`[rec]` provenance tag muted, appended to output from
  simulated/recorded commands (add `[rec]`; today only `[sim]` shows).
- root cause wrong: danger ` wrong root cause ` + muted `-20 xp`; right: strong `● root cause`.

Mystery ticket intro: strong chrome label `mystery ticket` + ink ` · <title>` (title is content), strong rule, then ticket text.

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
No SGR at all. Lowercase chrome, glyphs and layout still apply. Danger labels render as `[missed]`, `[drill failed]`,
`[wrong root cause]` so the form distinction survives without inverse fill.
