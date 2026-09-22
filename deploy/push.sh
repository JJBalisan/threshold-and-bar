#!/bin/bash
# Push commits the weekly digest task made locally in the Cowork VM.
# That VM has no GitHub credentials and cannot resolve github.com over SSH,
# so the push has to happen here, in JJ's own login session, using his keys.
set -u

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

echo "=== $(date '+%Y-%m-%d %H:%M:%S %Z')  $REPO"
cd "$REPO" || { echo "repo not found"; exit 1; }

# Sweep aside any lock/temp files the Cowork mount left behind (it forbids unlink).
if [ -d .git ]; then
  mkdir -p _to_delete
  find .git -maxdepth 2 \( -name '*.lock' -o -name 'tmp_*' \) -print 2>/dev/null | while read -r f; do
    mv -f "$f" "_to_delete/$(basename "$f").$$" 2>/dev/null && echo "swept $f"
  done
fi

git fetch --quiet origin || echo "fetch failed, continuing"

AHEAD=$(git rev-list --count origin/main..HEAD 2>/dev/null || echo 0)
if [ "$AHEAD" -eq 0 ]; then
  echo "nothing to push"
  exit 0
fi

echo "pushing $AHEAD commit(s)"
if git push origin main; then
  echo "ok -> $(git rev-parse --short HEAD)"
else
  echo "PUSH FAILED (check: ssh -T git@github.com)"
  exit 1
fi
