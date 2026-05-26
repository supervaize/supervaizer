# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

from __future__ import annotations

import os
import uuid
from hashlib import sha256
from typing import Any, cast

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey

from supervaizer.common import log
from supervaizer.contracts import V2WorkspaceAuthorizationSettings


def _get_or_create_server_id() -> str:
    """Use SUPERVAIZER_SERVER_ID from env if set; else create uuid and set env."""
    existing = os.getenv("SUPERVAIZER_SERVER_ID")
    if existing and len(existing) > 5:
        return existing
    new_id = str(uuid.uuid4())
    os.environ["SUPERVAIZER_SERVER_ID"] = new_id
    return new_id


def _controller_key_fingerprint(api_key: str | None) -> str | None:
    if not api_key:
        return None
    return sha256(api_key.encode("utf-8")).hexdigest()[:12]


def _resolve_workspace_authorization_settings(
    explicit_settings: V2WorkspaceAuthorizationSettings | dict[str, Any] | None,
) -> V2WorkspaceAuthorizationSettings:
    if explicit_settings is not None:
        return V2WorkspaceAuthorizationSettings.model_validate(explicit_settings)
    return V2WorkspaceAuthorizationSettings(
        enabled=_env_bool("SUPERVAIZER_WORKSPACE_AUTH_REQUIRED", default=False),
        issuer=os.getenv("SUPERVAIZER_WORKSPACE_AUTH_ISSUER") or None,
        audience=os.getenv("SUPERVAIZER_WORKSPACE_AUTH_AUDIENCE") or None,
        public_key_pem=os.getenv("SUPERVAIZER_WORKSPACE_AUTH_PUBLIC_KEY") or None,
        jwks_url=os.getenv("SUPERVAIZER_WORKSPACE_AUTH_JWKS_URL") or None,
        leeway_seconds=int(
            os.getenv("SUPERVAIZER_WORKSPACE_AUTH_LEEWAY_SECONDS", "30")
        ),
    )


def _env_bool(name: str, *, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def _get_or_create_private_key() -> RSAPrivateKey:
    """Use SUPERVAIZER_PRIVATE_KEY from env if set; else create key and set env."""
    pem = os.getenv("SUPERVAIZER_PRIVATE_KEY")
    if pem and len(pem) > 5:
        try:
            key = serialization.load_pem_private_key(
                pem.encode("utf-8"),
                password=None,
                backend=default_backend(),
            )
            return cast(RSAPrivateKey, key)
        except Exception as e:
            log.warning(
                f"[Server] Invalid SUPERVAIZER_PRIVATE_KEY, generating new key: {e}"
            )
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend(),
    )
    pem_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    os.environ["SUPERVAIZER_PRIVATE_KEY"] = pem_bytes.decode("utf-8")
    log.info("[Server] Generated new RSA private key and set SUPERVAIZER_PRIVATE_KEY")
    return private_key
