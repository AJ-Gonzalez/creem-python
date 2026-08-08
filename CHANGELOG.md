# Changelog

All notable changes to this project are documented here. The format is based
on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-08-08

### Added
- Both dict-params and kwargs-only call styles on all body methods.
- Live test suite runs in CI against the sandbox on every push to main.

## [0.1.1] - 2026-08-08

### Added
- First public release on PyPI (and Test PyPI).
- Typed client covering all 49 endpoints across 12 resources.
- Generated TypedDict models from the official OpenAPI spec
  (`scripts/generate_models.py`).
- Webhook verification, parsing, and sync/async dispatch (`creem.webhooks`).
- Pagination iterators for both the page-number and cursor styles.
- Automatic retry with exponential backoff, jitter, `Retry-After` support,
  and idempotency gating.
- GitHub Actions pipeline: quality gate (mypy, pytest, build), Test PyPI and
  PyPI publishing via trusted publishing.


## [Unreleased]

### Added
- Release tooling: scripts/release.sh with --dry-run, changelog, and a CI
  check that the version tag matches pyproject and __init__ versions.
- Live test suite runs in CI (workflow gated on the CREEM_API_KEY secret).

### Changed
- Both dict-params and keyword-only call styles on all body methods.
- pylint now covers examples/ (CI and local).
