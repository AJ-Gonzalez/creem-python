"""Test bootstrap: load the gitignored .env file so live tests can use the
sandbox API key without it ever being committed."""

from __future__ import annotations

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent

# The examples package lives at the repo root. The `pytest` console script
# does not put the working directory on sys.path (unlike `python -m pytest`),
# so make the root importable explicitly for the examples import tests.
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_ENV_PATH = _ROOT / ".env"


def _load_dotenv() -> None:
    if not _ENV_PATH.exists():
        return
    for line in _ENV_PATH.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


_load_dotenv()
