---
name: python-pypi-publishing
description: Publish a Python package to PyPI (and Test PyPI) with quality gates, version tags, trusted publishing, and a changelog. Use when the human asks to release, publish, bump the version, tag a release, or set up packaging for a Python project.
version: 1.0.0
---

# Python Package Publishing (PyPI)

A battle-tested playbook for publishing Python packages to PyPI with zero
tokens in the repo, automatic quality gates, and nicknamed GitHub Releases.
Built from a production release run in 2026; every pitfall below cost a
failed pipeline at least once.

## When to Use

- The project has a `pyproject.toml` (PEP 621), a `src/` layout, and a
  git repo on GitHub.
- The human says "put out a release", "bump the version", "publish to
  PyPI", or "can we nickname releases".
- Setting up publishing for a fresh project.

## The Pipeline Shape

One workflow (`publish.yml`), triggered by version tags (`v*`) and
`workflow_dispatch`:

1. **quality** — matrix over the supported Python versions (floor + newest):
   lint (flake8, pylint), type check (mypy --strict), tests, build sdist +
   wheel with `python -m build`.
2. **tag == version check** — on tag pushes, `vX.Y.Z` must equal both the
   `pyproject.toml` version and `__version__` in `__init__.py`. Fail the
   build otherwise. This stops tag/version drift silently shipping the
   wrong artifact.
3. **publish-testpypi** — upload to `https://test.pypi.org/legacy/` via
   trusted publishing (OIDC).
4. **publish-pypi** — same job without `repository-url` (defaults to
   pypi.org).
5. **release-github** — create a GitHub Release titled from the changelog,
   including an optional nickname.

## Trusted Publishing Setup (one-time, per index)

No API tokens. On test.pypi.org AND pypi.org, for the project name:

- Publishing → "Add a new pending publisher"
- Publisher: GitHub; Owner: <user>; Repository: <repo>; Workflow:
  `publish.yml`; Environment: leave empty.

Register the project name on each index first (they are separate
registries). PyPI requires email verification and 2FA.

## The Release Script Pattern

`scripts/release.sh <version> ["Nickname"]` with a `--dry-run` flag (always
verify with it first):

```bash
#!/usr/bin/env bash
VERSION="${1:?usage: ./scripts/release.sh [--dry-run] <version> [\"Nickname\"]}"
NICKNAME="${2:-}"
TAG="v$VERSION"
# validate ^[0-9]+\.[0-9]+\.[0-9]+$ before anything else
# require a "## [Unreleased]" section in CHANGELOG.md
# bump version in pyproject.toml and src/<pkg>/__init__.py
HEADING="## [$VERSION] - $(date +%Y-%m-%d)"
if [ -n "$NICKNAME" ]; then HEADING="$HEADING — \"$NICKNAME\""; fi
sed -i "0,/^## \[Unreleased\]/s//$HEADING/" CHANGELOG.md
# insert a fresh "## [Unreleased]" section at the TOP (newest-first order):
# awk to print the new section before the first "## [" heading
git add pyproject.toml src/<pkg>/__init__.py CHANGELOG.md
git commit -m "release $VERSION"
git tag "$TAG"
git push origin main "$TAG"
```

## GitHub Release Job (nicknames)

GitHub Releases accept free-text titles; PyPI versions do not (PEP 440).
Extract the title and body from the changelog in CI:

```yaml
- name: Compute release title and body from the changelog
  id: release
  run: |
    HEADING="$(grep '^## \[' CHANGELOG.md | grep -v '^## \[Unreleased\]' | head -1)"
    VERSION="$(echo "$HEADING" | sed -n 's/^## \[\([0-9.]*\)\].*/\1/p')"
    NICKNAME="$(echo "$HEADING" | sed -n 's/.*— "\(.*\)".*/\1/p')"
    TITLE="v$VERSION${NICKNAME:+ — $NICKNAME}"
    BODY="$(awk 'BEGIN { n = 0 } /^## \[Unreleased\]/ { next } /^## \[/ { n++; if (n == 1) { next } } n == 1 { print } n > 1 { exit }' CHANGELOG.md)"
    echo "title=$TITLE" >> "$GITHUB_OUTPUT"
    echo "body=$BODY" >> "$GITHUB_OUTPUT"
- uses: softprops/action-gh-release@v2
  with:
    name: ${{ steps.release.outputs.title }}
    body: ${{ steps.release.outputs.body }}
```

Gate the job with `if: startsWith(github.ref, 'refs/tags/')` — otherwise a
`workflow_dispatch` run tries to release the branch.

## Pitfalls That Cost Real Failures

1. **`secrets` is not allowed in `if:` conditions** — not at job level, not
   at step level. The documented pattern: pass the secret into a step's
   `env:`, write a marker to `$GITHUB_OUTPUT`, and gate the next step on
   `steps.<id>.outputs.<marker> == '1'`.
2. **Validate workflows with actionlint** (`pip install actionlint-py`).
   GitHub's server rejects files that YAML-parsers accept; a rejected
   workflow shows as a run with zero jobs and "workflow file issue".
3. **Duplicate TOML tables break pylint's config silently** — a duplicated
   `[tool.pylint.main]` table made the whole `pyproject.toml` unreadable to
   pylint, which then ran with defaults (10/10 scores lied). Check with
   `python -c "import tomllib; tomllib.load(open('pyproject.toml','rb'))"`.
4. **Pylint option naming drifts between versions** — put check disables in
   `[tool.pylint."messages control"]` only. Never set them as options in
   `[tool.pylint.main]` (`too-many-locals = 0` broke on a newer pylint with
   E0015 "unrecognized option"). Pin what CI installs if you must.
5. **Pylint's examples-import trap** — astroid cannot resolve
   `import examples.x` from a test module unless `examples` is also passed
   as a lint target. Run `pylint src tests scripts examples`, not a subset.
6. **The `pytest` console script does not put the working directory on
   `sys.path`** (unlike `python -m pytest`). Tests that import a top-level
   `examples/` package pass locally and fail in CI unless conftest.py
   inserts the repo root explicitly.
7. **pip's HTTP cache serves stale versions** — a fresh venv can install an
   old release while the index shows the new one. Always verify with
   `pip install --no-cache-dir` or by querying
   `https://pypi.org/pypi/<name>/json` (`info.version`).
8. **Versions are immutable per index** — Test PyPI and PyPI are separate
   registries, so `0.4.0` can exist on Test PyPI and still be published to
   PyPI. But the same version can never be re-uploaded to the SAME index:
   a broken release means bumping.
9. **A failed tag run cannot be re-run with fixed code** — the run binds to
   the workflow file at the tagged commit. Options: `workflow_dispatch`
   (runs from the default branch; note the release-github tag gate), or a
   new version bump. Never move a pushed tag.
10. **Keep the CHANGELOG newest-first** — `[Unreleased]` at the top. The
    release script must INSERT the fresh section at the top, never append:
    appending inverts the order over successive releases.
11. **Generated files get lint exemptions** — exclude `models.py`-style
    generated code from flake8 (`exclude =`) and pylint (`ignore =`);
    lint the generator script instead.
12. **Live/browser test suites need their dependencies in CI** — a
    Playwright-based live suite requires `playwright install --with-deps
    chromium` as a CI step, or the whole live job fails on a missing
    browser binary.

## Safety Rules

- Always `--dry-run` the release script before the real run. (An
  unguarded test run accidentally shipped a real release once.)
- Never publish on a red quality gate. CI is the gate; the release script
  does not run tests.
- Test-PyPI-first when changing pipeline tooling; the dual-publish setup
  sends every tag to both indexes.
- Keys are environment-scoped: `creem_test_`-style sandbox keys never mix
  with live keys. Gitignore key files (`prodkey`), keep `.env` for the
  sandbox key, and never run live-environment suites with a production key.
- A production smoke test is a separate, gated script
  (`PROD_SMOKE=1`-style env gate) that is read-only plus
  create-then-archive round trips — never financial mutations.

## Verification After Publishing

```bash
# index truth:
curl -s https://pypi.org/pypi/<name>/json | python3 -c \
  "import json,sys; d=json.load(sys.stdin); print(d['info']['version'])"
# clean install (bypasses pip cache):
python3 -m venv /tmp/v && /tmp/v/bin/pip install --no-cache-dir <name>
/tmp/v/bin/python -c "import <name>; print(<name>.__version__)"
```

Then exercise the core paths from a script (client construction, one
read endpoint, one create-then-archive round trip) against the sandbox or
the gated production smoke script.
