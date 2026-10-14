"""Single source of truth for the Radia AI release version.

The version lives in ``app/VERSION`` so the backend, its package metadata and the
frontend build all read the same value. Bump it there only.
"""

from pathlib import Path

VERSION_FILE = Path(__file__).resolve().parent.parent / "VERSION"


def _read_version() -> str:
    version = VERSION_FILE.read_text(encoding="utf-8").strip()
    if not version:
        raise RuntimeError(f"App version file is empty: {VERSION_FILE}")
    return version


APP_VERSION = _read_version()
