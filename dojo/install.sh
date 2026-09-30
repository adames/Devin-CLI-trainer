#!/usr/bin/env bash
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
target="$script_dir/dojo.py"
bin_dir="$HOME/.local/bin"
link="$bin_dir/professor-devin"

chmod +x "$target"
mkdir -p "$bin_dir"

if [ -L "$link" ]; then
    if [ "$(readlink -f "$link")" != "$target" ]; then
        printf 'Refusing to replace existing symlink: %s\n' "$link" >&2
        exit 1
    fi
elif [ -e "$link" ]; then
    printf 'Refusing to replace existing file: %s\n' "$link" >&2
    exit 1
else
    ln -s "$target" "$link"
fi

printf 'Installed %s -> %s\n' "$link" "$target"
case ":${PATH:-}:" in
    *":$bin_dir:"*) ;;
    *) printf 'Add %s to PATH to run professor-devin from any shell.\n' "$bin_dir" ;;
esac
