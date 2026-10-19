#!/usr/bin/env bash
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
target="$script_dir/dojo/dojo.py"
launcher="$script_dir/professor-devin"
bin_dir="$HOME/.local/bin"
link="$bin_dir/professor-devin"
path_line='export PATH="$HOME/.local/bin:$PATH"'

chmod +x "$target" "$launcher"
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
printf 'Or run it without installing: ./professor-devin\n'

case ":${PATH:-}:" in
    *":$bin_dir:"*)
        printf 'Done. Run: professor-devin\n'
        exit 0
        ;;
esac

rc=""
case "${SHELL:-}" in
    */zsh) rc="$HOME/.zshrc" ;;
    */bash) rc="$HOME/.bashrc" ;;
esac

if [ -n "$rc" ] && [ -t 0 ]; then
    printf 'Add ~/.local/bin to your PATH in %s? [y/N] ' "$rc"
    read -r answer || answer=""
    case "$answer" in
        y | Y | yes | YES)
            if ! grep -q '.local/bin' "$rc" 2>/dev/null; then
                printf '\n# professor-devin\n%s\n' "$path_line" >>"$rc"
            fi
            printf 'Done. Then open a new terminal and run: professor-devin\n'
            exit 0
            ;;
    esac
fi

printf 'Add this to your shell config: %s\n' "$path_line"
printf 'Then open a new terminal and run: professor-devin\n'
