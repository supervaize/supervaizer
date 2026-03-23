"""
Read GitButler workspace status JSON from stdin and output the single applied
branch/stack CLI id.

This is used by `just ready-to-go` to ensure the documentation commit happens
in the active stack only.
"""

from __future__ import annotations

import json
import sys
from typing import Any


def main() -> int:
    data = json.load(sys.stdin)

    branches: list[dict[str, Any]] = []
    for stack in data.get("stacks", []):
        branches.extend(stack.get("branches", []))

    if len(branches) != 1:
        applied_ids = [b.get("cliId") for b in branches]
        msg = (
            "Expected exactly 1 active GitButler branch (applied stack). "
            f"Found {len(branches)}. Stop: apply exactly one stack/branch (or none), "
            f"then rerun ready-to-go. Applied branches (cliId): {applied_ids}"
        )
        print(msg, file=sys.stderr)
        return 1

    cli_id = branches[0].get("cliId")
    if not isinstance(cli_id, str):
        print(
            "GitButler status JSON did not include a valid branch cliId. Refusing to commit.",
            file=sys.stderr,
        )
        return 1

    print(cli_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

