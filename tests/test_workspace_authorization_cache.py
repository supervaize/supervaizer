# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

from collections import OrderedDict

import pytest
from cryptography.hazmat.primitives.asymmetric import ed25519

import supervaizer.workspace_authorization as authorization


def test_jwks_cache_evicts_the_least_recently_used_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache: OrderedDict[
        tuple[str, str], authorization.WorkspaceAuthorizationPublicKey
    ] = OrderedDict()
    monkeypatch.setattr(authorization, "_JWKS_KEY_CACHE", cache)
    monkeypatch.setattr(authorization, "JWKS_KEY_CACHE_MAX_SIZE", 2)
    url = "https://studio.example.test/jwks"
    first = ed25519.Ed25519PrivateKey.generate().public_key()
    second = ed25519.Ed25519PrivateKey.generate().public_key()
    third = ed25519.Ed25519PrivateKey.generate().public_key()

    authorization._cache_jwks_key(url, "first", first)
    authorization._cache_jwks_key(url, "second", second)
    assert authorization._get_cached_jwks_key(url, "first") is first
    authorization._cache_jwks_key(url, "third", third)

    assert len(cache) == 2
    assert authorization._get_cached_jwks_key(url, "second") is None
    assert authorization._get_cached_jwks_key(url, "first") is first
    assert authorization._get_cached_jwks_key(url, "third") is third
