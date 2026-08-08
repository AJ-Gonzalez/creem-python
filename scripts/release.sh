#!/usr/bin/env bash
# Release the SDK: bump the version, finalize the changelog, tag, and push.
#
# Usage:
#   ./scripts/release.sh 0.2.0 ["Nickname"]
#
# What it does:
#   1. Updates the version in pyproject.toml and src/creem/__init__.py
#   2. Renames the CHANGELOG [Unreleased] section to the new version,
#      optionally with a release nickname: `## [0.2.0] - date — "Nickname"`
#   3. Commits, tags vX.Y.Z, and pushes branch + tag
#
# CI then runs the quality gate (lint, type check, tests, build), creates a
# GitHub Release titled with the nickname, and publishes to Test PyPI and
# PyPI. This script does not run tests.
#
# Pass --dry-run to print what would change without touching the repo.
SECONDS=0

DRY_RUN=0
if [ "${1:-}" = "--dry-run" ]; then
    DRY_RUN=1
    shift
fi

VERSION="${1:?usage: ./scripts/release.sh [--dry-run] <version> [\"Nickname\"]}"
NICKNAME="${2:-}"
TAG="v$VERSION"

if ! [[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "version must be X.Y.Z, got: $VERSION" >&2
    exit 1
fi

cd "$(dirname "$0")/.."

if ! grep -q '^## \[Unreleased\]' CHANGELOG.md; then
    echo "CHANGELOG.md has no [Unreleased] section; add one before releasing." >&2
    exit 1
fi

if [ "$DRY_RUN" = 1 ]; then
    echo "Dry run: would bump to $VERSION and tag $TAG"
    grep -n '^version = ' pyproject.toml
    grep -n '__version__ = ' src/creem/__init__.py
    echo "Unreleased changelog section:"
    sed -n '/^## \[Unreleased\]/,/^## /p' CHANGELOG.md | head -20
    exit 0
fi

sed -i "s/^version = \".*\"/version = \"$VERSION\"/" pyproject.toml
sed -i "s/__version__ = \".*\"/__version__ = \"$VERSION\"/" src/creem/__init__.py
HEADING="## [$VERSION] - $(date +%Y-%m-%d)"
if [ -n "$NICKNAME" ]; then
    HEADING="$HEADING — \"$NICKNAME\""
fi
sed -i "0,/^## \[Unreleased\]/s//$HEADING/" CHANGELOG.md
# Insert a fresh Unreleased section at the top (newest-first order).
awk '
    !inserted && /^## \[/ {
        print "## [Unreleased]"
        print ""
        print "### Added"
        print ""
        print "### Changed"
        print ""
        inserted = 1
    }
    { print }
' CHANGELOG.md > CHANGELOG.md.tmp && mv CHANGELOG.md.tmp CHANGELOG.md

git add pyproject.toml src/creem/__init__.py CHANGELOG.md
git commit -m "release $VERSION"
git tag "$TAG"
git push origin main "$TAG"

duration=$SECONDS
echo "Released $TAG in $((duration / 60)):$((duration % 60))"

