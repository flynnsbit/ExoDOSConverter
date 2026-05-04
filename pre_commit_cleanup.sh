#!/usr/bin/env bash
set -euo pipefail

TRAILER='Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>'

if ! git rev-parse --git-dir >/dev/null 2>&1; then
    echo "Not in a git repository." >&2
    exit 1
fi

if ! git rev-parse --verify HEAD >/dev/null 2>&1; then
    exit 0
fi

msg="$(git log -1 --pretty=%B)"
if ! printf '%s\n' "$msg" | grep -Fqx "$TRAILER"; then
    exit 0
fi

tmp_file="$(mktemp)"
trap 'rm -f "$tmp_file"' EXIT
printf '%s\n' "$msg" | awk -v trailer="$TRAILER" '$0 != trailer { print }' > "$tmp_file"

git commit --amend -F "$tmp_file" >/dev/null
echo "Removed Copilot trailer from latest commit."
