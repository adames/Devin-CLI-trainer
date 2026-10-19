#!/usr/bin/env bash
# Install Professor Devin with one command:
#   curl -fsSL https://raw.githubusercontent.com/adames/professor-devin/main/get.sh | bash
set -eu

for tool in git python3; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        printf 'Professor Devin needs %s. On macOS run: xcode-select --install\n' "$tool" >&2
        exit 1
    fi
done

repo="${PROFESSOR_DEVIN_REPO:-https://github.com/adames/professor-devin.git}"
dir="${PROFESSOR_DEVIN_DIR:-$HOME/.local/share/professor-devin}"

if [ -d "$dir/.git" ]; then
    git -C "$dir" pull -q --ff-only
else
    git clone -q "$repo" "$dir"
fi

printf 'Installed into %s\n' "$dir"

if ( : </dev/tty ) 2>/dev/null; then
    bash "$dir/install.sh" </dev/tty
else
    bash "$dir/install.sh"
fi
