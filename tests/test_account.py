# Copyright (c) 2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import pytest

from supervaize_control import Account


@pytest.fixture
def account_fixture():
    return Account(
        name="CUSTOMERFIRST",
        id="o34Z484gY9Nxz8axgTAdiH",
        api_key="1234567890",
        api_url="https://api.supervaize.com",
    )


def test_account(account_fixture):
    assert isinstance(account_fixture, Account)
    assert account_fixture.name == "CUSTOMERFIRST"
    assert account_fixture.id == "o34Z484gY9Nxz8axgTAdiH"


def test_account_error():
    with pytest.raises(ValueError):
        Account(
            name="CUSTOMERFIRST",
            id="NOTWORKING",
            api_key="1234567890",
            api_url="https://api.supervaize.com",
        )
