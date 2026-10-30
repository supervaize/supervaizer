# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""The release reconcile script takes no arguments: a stale command must stop before any side effect."""

import subprocess
from pathlib import Path

SCRIPT = (
    Path(__file__).resolve().parents[1] / "tools" / "reconcile-release-after-ship.sh"
)


def test_script_refuses_arguments_before_any_side_effect() -> None:
    result = subprocess.run(
        ["bash", str(SCRIPT), "owner/repo", "--timeout-seconds", "7200"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "takes no arguments" in result.stderr
    assert result.stdout == ""
