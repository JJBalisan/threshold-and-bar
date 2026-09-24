#!/bin/bash
# Catch-up push for the weekly digest. The local scheduled task normally pushes
# straight after rendering; this only has work to do when that push failed
# (SSH agent locked, offline), leaving a commit ahead of origin.
set -u

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

echo "=== $(date '+%Y-%m-%d %H:%M:%S %Z')  $REPO"
cd "$REPO" || { echo "repo not found"; exit 1; }

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
