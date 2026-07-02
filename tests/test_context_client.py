# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

from __future__ import annotations

from typing import Any

import pytest

from supervaizer import (
    Account,
    ContextClient,
    ContextOpenResponse,
    ContextSearchResponse,
    context,
)


class _Response:
    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._data


def test_context_search_posts_to_workspace_context_search(
    account_fixture: Account, mocker: Any
) -> None:
    post = mocker.patch(
        "supervaizer.context.httpx.post",
        return_value=_Response({
            "query": "billing",
            "results": [
                {
                    "ref": "supervaize.context.workspace.billing",
                    "title": "Billing",
                    "scope": "workspace",
                    "source_type": "text",
                    "version": 1,
                    "tags": ["ops"],
                    "excerpt": "Billing policy",
                    "score": 3,
                    "citation": {
                        "ref": "supervaize.context.workspace.billing",
                        "title": "Billing",
                        "source_type": "text",
                        "version": 1,
                    },
                }
            ],
        }),
    )

    result = context.search(
        account=account_fixture,
        query="billing",
        mission_id="mission-1",
        scope="mission",
        tags=["ops"],
        limit=7,
    )

    assert isinstance(result, ContextSearchResponse)
    assert result.results[0].ref == "supervaize.context.workspace.billing"
    post.assert_called_once_with(
        f"{account_fixture.api_url_w_v1}/context/search/",
        headers=account_fixture.api_headers,
        json={
            "query": "billing",
            "limit": 7,
            "mission_id": "mission-1",
            "scope": "mission",
            "tags": ["ops"],
        },
    )


def test_context_open_posts_to_workspace_context_open(
    account_fixture: Account, mocker: Any
) -> None:
    post = mocker.patch(
        "supervaizer.context.httpx.post",
        return_value=_Response({
            "ref": "supervaize.context.workspace.billing",
            "title": "Billing",
            "scope": "workspace",
            "source_type": "text",
            "version": 2,
            "instructions": "Use for policy answers.",
            "tags": ["ops"],
            "content": "Billing policy",
            "citations": [
                {
                    "ref": "supervaize.context.workspace.billing",
                    "title": "Billing",
                    "source_type": "text",
                    "version": 2,
                }
            ],
        }),
    )

    result = account_fixture.context.open(
        ref="supervaize.context.workspace.billing", query="policy", max_chars=1000
    )

    assert isinstance(result, ContextOpenResponse)
    assert result.content == "Billing policy"
    post.assert_called_once_with(
        f"{account_fixture.api_url_w_v1}/context/open/",
        headers=account_fixture.api_headers,
        json={
            "ref": "supervaize.context.workspace.billing",
            "max_chars": 1000,
            "query": "policy",
        },
    )


def test_context_rejects_conflicting_workspace_id(
    account_fixture: Account, mocker: Any
) -> None:
    post = mocker.patch("supervaizer.context.httpx.post")
    client = ContextClient(account_fixture)

    with pytest.raises(ValueError, match="does not match account.workspace_id"):
        client.search(query="x", workspace_id="other-workspace")

    post.assert_not_called()
