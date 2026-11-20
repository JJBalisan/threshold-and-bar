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
#   repo is missing, git cannot compare main with origin/main, main has
#   diverged from origin/main, or the push fails. A failed fetch is
#   reported but not fatal. Only main counts, whatever branch is checked
#   out.
#######################################
main() {
  local ahead behind counts

  echo "=== $(date '+%Y-%m-%d %H:%M:%S %Z')  ${REPO}"
  cd "${REPO}" || {
    err "repo not found"
    exit 1
  }

  git fetch --quiet origin || err "fetch failed, continuing"

  # Prints "<ahead>\t<behind>": commits only on main, then only on
  # origin/main. Full refnames so a file or tag named main cannot match.
  # Any failure is an error, never "nothing to push".
  if ! counts="$(git rev-list --left-right --count \
    refs/heads/main...refs/remotes/origin/main)"; then
    err "cannot compare main with origin/main"
    exit 1
  fi
  read -r ahead behind <<< "${counts}"
  if [[ ! "${ahead}" =~ ^[0-9]+$ || ! "${behind}" =~ ^[0-9]+$ ]]; then
    err "unexpected rev-list output: ${counts}"
    exit 1
  fi

  if ((ahead == 0)); then
    echo "nothing to push"
    exit 0
  fi
  if ((behind > 0)); then
    err "main has diverged from origin/main (${ahead} ahead, ${behind}" \
      "behind): rebase or merge by hand"
    exit 1
  fi

  echo "pushing ${ahead} commit(s)"
  if git push origin refs/heads/main:refs/heads/main; then
    echo "ok -> $(git rev-parse --short refs/heads/main)"
  else
    err "PUSH FAILED (check: ssh -T git@github.com)"
    exit 1
  fi
}

main "$@"
