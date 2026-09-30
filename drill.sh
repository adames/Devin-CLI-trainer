#!/usr/bin/env bash
# Spaced-repetition-ish flashcards. Missed cards are logged and weighted 3x next run.
# Usage: ./drill.sh [N cards, default 15] [filter regex]
set -euo pipefail
dir="$(cd "$(dirname "$0")" && pwd)"
cards="$dir/cards.tsv"; misses="$dir/.misses.tsv"; hist="$dir/.history.log"
n="${1:-15}"; filter="${2:-.}"
touch "$misses"
shuffle() { awk 'BEGIN{srand()} {print rand() "\t" $0}' | sort -k1,1n | cut -f2-; }  # portable shuf (macOS lacks shuf)
deck="$( { grep -E -i -- "$filter" "$cards" || true; for _ in 1 2 3; do grep -E -i -- "$filter" "$misses" || true; done; } | shuffle | awk -F'\t' '!seen[$1]++' | head -n "$n")"
[ -z "$deck" ] && { echo "no cards match '$filter'"; exit 1; }
right=0; total=0; : > "$misses.new"
while IFS=$'\t' read -r q a; do
  total=$((total+1))
  printf '\n\033[1m[%d] %s\033[0m\n' "$total" "$q"
  read -r -p "  your answer (Enter to reveal): " _ </dev/tty
  printf '  \033[32m%s\033[0m\n' "$a"
  read -r -n1 -p "  got it? [y/n] " yn </dev/tty; echo
  if [[ "$yn" == [yY] ]]; then right=$((right+1)); else printf '%s\t%s\n' "$q" "$a" >> "$misses.new"; fi
done <<< "$deck"
# keep old misses that weren't drilled this round, plus new misses
{ awk -F'\t' 'NR==FNR{d[$1];next} !($1 in d)' <(printf '%s\n' "$deck") "$misses"; cat "$misses.new"; } | awk -F'\t' '!s[$1]++' > "$misses.tmp"
mv "$misses.tmp" "$misses"; rm -f "$misses.new"
printf '%s\t%d/%d\t%s\n' "$(date '+%Y-%m-%dT%H:%M:%S%z')" "$right" "$total" "$filter" >> "$hist"
echo; echo "Score: $right/$total  |  weak cards queued: $(wc -l < "$misses")  |  history: tail $hist"
