#!/usr/bin/env python3
"""Re-point shell-card `source` citations at the right GUIDE.md lines.

Every shell-category card's explain line 1 is copied verbatim from GUIDE.md.
When the guide is edited, the cited line numbers drift; this tool finds the
line whose stripped text equals explain line 1 and rewrites
`source` to `../GUIDE.md:<line>`.

    python3 tools/relink_guide_sources.py

Exits 1 (with a clear message) if a card's explain line is missing from
GUIDE.md or matches more than one line.
"""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
COMMANDS = REPO / "dojo" / "content" / "commands.json"
GUIDE = REPO / "GUIDE.md"


def main():
    guide_lines = GUIDE.read_text(encoding="utf-8").splitlines()
    stripped_index = {}
    for number, line in enumerate(guide_lines, 1):
        stripped_index.setdefault(line.strip(), []).append(number)

    cards = json.loads(COMMANDS.read_text(encoding="utf-8"))
    failures = []
    changed = 0
    shell = 0
    for card in cards:
        if card.get("category") != "shell":
            continue
        shell += 1
        explain_first = card["explain"].splitlines()[0].strip()
        matches = stripped_index.get(explain_first, [])
        if len(matches) != 1:
            failures.append(
                "%s: explain line 1 found %d times in GUIDE.md" % (
                    card["id"], len(matches)
                )
            )
            continue
        wanted = "../GUIDE.md:%d" % matches[0]
        if card.get("source") != wanted:
            card["source"] = wanted
            changed += 1
    for failure in failures:
        print(failure, file=sys.stderr)
    if failures:
        return 1
    COMMANDS.write_text(
        json.dumps(cards, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print("relinked %d of %d shell card(s)" % (changed, shell))
    return 0


if __name__ == "__main__":
    sys.exit(main())
