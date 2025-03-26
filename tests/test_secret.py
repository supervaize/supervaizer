# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import pytest

from supervaize_control.secret import Secret


def test_secret_creation():
    secret = Secret(name="test")
    assert secret.name == "test"
    assert secret.value is None
    assert secret.description is None


def test_secret_with_all_fields(secret_fixture):
    assert secret_fixture.name == "test_secret"
    assert secret_fixture.value == "test_value"
    assert secret_fixture.description == "test description"


def test_secrets_initialization(secrets_fixture, secrets_list_fixture):
    assert len(secrets_fixture.secrets) == 2
    assert all(isinstance(s, Secret) for s in secrets_fixture.secrets.values())
    assert "secret1" in secrets_fixture.secrets
    assert "secret2" in secrets_fixture.secrets


def test_get_secret(secrets_fixture):
    secret = secrets_fixture.get_secret("secret1")
    assert isinstance(secret, Secret)
    assert secret.name == "secret1"
    assert secret.value == "value1"


def test_get_nonexistent_secret(secrets_fixture):
    with pytest.raises(KeyError):
        secrets_fixture.get_secret("nonexistent")
