#!/bin/bash
#
# Catch-up push for the weekly digest. The local scheduled task normally pushes
# straight after rendering; this only has work to do when that push failed
# (SSH agent locked, offline), leaving a commit ahead of origin.
#
# Run by launchd (see launchd-jobs/threshold-and-bar), which sends stdout and
# stderr to the same log file.

set -u

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly REPO
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

#######################################
# Writes an error message to stderr.
# Arguments:
#   The message.
# Outputs:
#   Writes the message to stderr.
#######################################
err() {
  echo "$*" >&2
}

#######################################
# Pushes commits on main that origin does not have yet.
# Globals:
#   REPO
# Arguments:
#   None.
# Outputs:
#   Writes progress to stdout and failures to stderr.
# Returns:
#   Exits 0 when there is nothing to push or the push succeeds, 1 when the
#   repo is missing or the push fails. A failed fetch is reported but not
#   fatal.
#######################################
main() {
  local ahead

  echo "=== $(date '+%Y-%m-%d %H:%M:%S %Z')  ${REPO}"
  cd "${REPO}" || {
    err "repo not found"
    exit 1
  }

  git fetch --quiet origin || err "fetch failed, continuing"

  ahead="$(git rev-list --count origin/main..HEAD 2> /dev/null || echo 0)"
  if [[ "${ahead}" -eq 0 ]]; then
    echo "nothing to push"
    exit 0
  fi

  echo "pushing ${ahead} commit(s)"
  if git push origin main; then
    echo "ok -> $(git rev-parse --short HEAD)"
  else
    err "PUSH FAILED (check: ssh -T git@github.com)"
    exit 1
  fi
}

main "$@"
