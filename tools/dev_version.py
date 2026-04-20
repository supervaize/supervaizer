#!/usr/bin/env python3
# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""Toggle PEP 440 .devN suffix for local dev (keeps __version__.py and bumpversion config in sync)."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERSION_FILE = ROOT / "src" / "supervaizer" / "__version__.py"
PYPROJECT = ROOT / "pyproject.toml"

VERSION_LINE_RE = re.compile(r'^(VERSION\s*=\s*")([^"]+)(")', re.M)
CURRENT_VERSION_LINE_RE = re.compile(r'^(current_version\s*=\s*")([^"]+)(")', re.M)

RELEASE_RE = re.compile(r"^\d+\.\d+\.\d+$")
DEV_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)\.dev(\d+)$")


def _read_version_py() -> str:
    text = VERSION_FILE.read_text(encoding="utf-8")
    m = VERSION_LINE_RE.search(text)
    if not m:
        msg = f'Could not find VERSION = "..." line in {VERSION_FILE}'
        raise SystemExit(msg)
    return m.group(2)


def _write_version_py(new_ver: str) -> None:
    text = VERSION_FILE.read_text(encoding="utf-8")
    new_text, n = VERSION_LINE_RE.subn(rf"\g<1>{new_ver}\g<3>", text, count=1)
    if n != 1:
        msg = f"Failed to replace VERSION in {VERSION_FILE}"
        raise SystemExit(msg)
    VERSION_FILE.write_text(new_text, encoding="utf-8", newline="\n")


def _read_pyproject_version() -> str:
    text = PYPROJECT.read_text(encoding="utf-8")
    m = CURRENT_VERSION_LINE_RE.search(text)
    if not m:
        msg = f'Could not find current_version = "..." under [tool.bumpversion] in {PYPROJECT}'
        raise SystemExit(msg)
    return m.group(2)


def _write_pyproject_version(new_ver: str) -> None:
    text = PYPROJECT.read_text(encoding="utf-8")
    new_text, n = CURRENT_VERSION_LINE_RE.subn(rf"\g<1>{new_ver}\g<3>", text, count=1)
    if n != 1:
        msg = f"Failed to replace current_version in {PYPROJECT}"
        raise SystemExit(msg)
    PYPROJECT.write_text(new_text, encoding="utf-8", newline="\n")


def _assert_sync() -> str:
    v_py = _read_version_py()
    v_toml = _read_pyproject_version()
    if v_py != v_toml:
        msg = (
            "Version mismatch — fix manually or run one of:\n"
            f"  {VERSION_FILE.relative_to(ROOT)}: {v_py!r}\n"
            f"  {PYPROJECT.relative_to(ROOT)}: {v_toml!r}"
        )
        raise SystemExit(msg)
    return v_py


def cmd_on() -> None:
    v = _assert_sync()
    if DEV_RE.match(v):
        print(f"Already a dev version ({v!r}); nothing to do.")
        return
    if not RELEASE_RE.match(v):
        msg = f"Expected release X.Y.Z (got {v!r}); cannot add .dev0."
        raise SystemExit(msg)
    new_v = f"{v}.dev0"
    _write_version_py(new_v)
    _write_pyproject_version(new_v)
    print(f"Dev on:  {v} → {new_v}")


def cmd_off() -> None:
    v = _assert_sync()
    m = DEV_RE.match(v)
    if not m:
        print(f"No .devN suffix ({v!r}); nothing to do.")
        return
    base = f"{m.group(1)}.{m.group(2)}.{m.group(3)}"
    _write_version_py(base)
    _write_pyproject_version(base)
    print(f"Dev off: {v} → {base}")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("on", help="Append .dev0 (X.Y.Z → X.Y.Z.dev0)")
    sub.add_parser("off", help="Strip .devN (X.Y.Z.devN → X.Y.Z)")
    args = p.parse_args()
    if args.cmd == "on":
        cmd_on()
    else:
        cmd_off()


if __name__ == "__main__":
    main()
