# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""Multi-surface access control: Tailscale gating and API key auth."""  # <-- ADDED

from supervaizer.access.api_auth import API_KEYS, require_api_key, require_scope
from supervaizer.access.client_ip import TRUSTED_PROXIES, _extract_client_ip
from supervaizer.access.tailscale import require_tailscale

__all__ = [
    "API_KEYS",
    "TRUSTED_PROXIES",
    "_extract_client_ip",
    "require_api_key",
    "require_scope",
    "require_tailscale",
]
