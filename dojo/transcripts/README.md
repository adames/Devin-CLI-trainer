# transcripts/ — review captures

Terminal captures kept for review and regression reference.

## Pattern index

- `drill-d-<name>-right.txt` / `drill-d-<name>-wrong.txt` — live drill
  captures: the same drill passing and failing.
- `combo-s<N>-*.txt` — mystery-ticket runs. Each maps to one of the break-it
  drills in `../../GUIDE.md` section 6 (the `s<N>` is the scenario id, not the
  GUIDE number). `combo-sup-win-bash.txt` is the support-pack ticket for the
  Windows `bash.exe` case (R-WIN-BASH in `../content/support/SOURCES.md`).
- `prof-*.txt` / `prof-*.ansi` — Professor mode review captures:
  `prof-train.txt` (seeded training run), `prof-forms.txt` (recognize /
  fill-in / recall / fix forms), `prof-categories.txt` (category table),
  `prof-deck.txt` (command cards in review format), `prof-color.ansi` (raw
  color capture).
- `render/prof-light.html`, `render/prof-dark.html` — HTML renders of
  `prof-color.ansi` in light and dark themes.
- `devin-user-state-before.txt`, `devin-user-state-after.txt`,
  `devin-user-state-diff.txt`, `devin-config-diff.txt` — before/after state of
  `~/.config` and `~/.local/share` recorded around a drill, showing what the
  CLI writes locally.
- `session.txt` — a captured game session.
- `unittest.txt`, `flake8.txt` — test-suite and lint output captures.
- `color-*.ansi` — raw terminal color demos (`color-demo.ansi`,
  `color-stats.ansi`).
