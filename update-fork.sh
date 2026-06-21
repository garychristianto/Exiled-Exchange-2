#!/usr/bin/env bash
#
# update-fork.sh — sync this fork with upstream and cut a release.
#
# What it does, in order:
#   1. makes sure an `upstream` remote (Kvan7/Exiled-Exchange-2) exists
#   2. fetches upstream + origin
#   3. fast-forwards local master to origin/master
#   4. merges upstream/master (stops for you if there are conflicts)
#   5. pushes master
#   6. tags vX.Y.Z (from main/package.json) and pushes it — which triggers the
#      release workflow to build + publish, after which your app auto-updates.
#
# Usage:  ./update-fork.sh
#
set -euo pipefail

UPSTREAM_URL="https://github.com/Kvan7/Exiled-Exchange-2.git"
BRANCH="master"

info() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!!\033[0m  %s\n' "$*"; }
die()  { printf '\033[1;31mxx\033[0m  %s\n' "$*" >&2; exit 1; }

# 0. Refuse to run on a dirty tree.
[ -z "$(git status --porcelain)" ] || die "You have uncommitted changes — commit or stash them first."

# 1. Ensure the upstream remote exists.
if ! git remote get-url upstream >/dev/null 2>&1; then
  info "Adding 'upstream' remote → $UPSTREAM_URL"
  git remote add upstream "$UPSTREAM_URL"
fi

# 2. Fetch.
info "Fetching upstream and origin…"
git fetch --quiet upstream "$BRANCH"
git fetch --quiet --tags origin "$BRANCH"

# 3. Get onto an up-to-date local master.
git checkout --quiet "$BRANCH"
git merge --ff-only --quiet "origin/$BRANCH" \
  || die "Local '$BRANCH' has diverged from origin/$BRANCH — reconcile that manually first."

# 4. Merge upstream (only if it actually has new commits).
if git merge-base --is-ancestor "upstream/$BRANCH" HEAD; then
  info "No new upstream commits to merge."
else
  info "Merging upstream/$BRANCH…"
  if ! git merge --no-edit "upstream/$BRANCH"; then
    warn "Merge has conflicts. Resolve them, then finish with:"
    warn "    git add <files> && git commit"
    warn "    ./update-fork.sh        # re-run to push + tag the release"
    die  "Conflicts need manual resolution (merge left in progress)."
  fi
  # 5. Push the merge result.
  info "Pushing $BRANCH to origin…"
  git push origin "$BRANCH"
fi

# 6. Tag the release if this version hasn't been tagged yet.
VERSION="$(node -p "require('./main/package.json').version" 2>/dev/null \
  || sed -nE 's/.*"version":[[:space:]]*"([^"]+)".*/\1/p' main/package.json | head -n1)"
[ -n "$VERSION" ] || die "Could not read the version from main/package.json."
TAG="v$VERSION"

if git rev-parse -q --verify "refs/tags/$TAG" >/dev/null; then
  info "Version $VERSION is already tagged ($TAG) — nothing to release."
  warn "If upstream added commits without bumping the version, bump 'version' in"
  warn "main/package.json, commit, push, then re-run this script."
  exit 0
fi

info "Tagging $TAG and pushing (this triggers the release build)…"
git tag "$TAG"
git push origin "$TAG"

info "Done. Build progress: https://github.com/garychristianto/Exiled-Exchange-2/actions"
info "Once it publishes, your installed app auto-updates to $TAG."
