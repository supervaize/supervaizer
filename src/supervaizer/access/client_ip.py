# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""Client IP extraction with trusted-proxy support."""  # <-- ADDED

from __future__ import annotations

import ipaddress
import os

from starlette.datastructures import Headers
from starlette.types import Scope

from supervaizer.common import log

# Comma-separated CIDRs trusted to set X-Forwarded-For, e.g. "10.0.0.0/8,172.16.0.0/12"
# Empty / unset = no proxy is trusted (use direct peer IP only).
TRUSTED_PROXIES: list[ipaddress._BaseNetwork] = []  # <-- ADDED

_raw = os.getenv("TRUSTED_PROXIES", "").strip()
if _raw:
    for _entry in _raw.split(","):
        _entry = _entry.strip()
        if _entry:
            try:
                TRUSTED_PROXIES.append(ipaddress.ip_network(_entry, strict=False))
            except ValueError:
                log.warning(
                    f"[client_ip] Invalid TRUSTED_PROXIES entry ignored: {_entry!r}"
                )


def _extract_client_ip(scope: Scope) -> str:  # <-- ADDED
    """Return the effective client IP for a request scope.

    Trusts X-Forwarded-For only when the direct peer IP is in TRUSTED_PROXIES.
    Returns "" on any parse failure (callers must treat "" as a deny).
    """
    try:
        client = scope.get("client")
        peer_str = client[0] if client else ""
        if not peer_str:
            return ""

        peer_addr = ipaddress.ip_address(peer_str)

        if TRUSTED_PROXIES and any(peer_addr in net for net in TRUSTED_PROXIES):
            headers = Headers(scope=scope)
            xff = headers.get("x-forwarded-for", "")
            if xff:
                candidate = xff.split(",")[0].strip()
                try:
                    ipaddress.ip_address(candidate)  # validate
                    return candidate
                except ValueError:
                    log.warning(
                        f"[client_ip] Unparseable XFF entry {candidate!r}, falling back to peer"
                    )

        return peer_str

    except Exception as exc:
        log.warning(f"[client_ip] Failed to extract client IP: {exc}")
        return ""
