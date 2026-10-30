"""The release reconcile script takes no arguments: a stale command must not fall back to the default repo."""

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
