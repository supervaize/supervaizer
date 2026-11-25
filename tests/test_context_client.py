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
        self._data: dict[str, Any] = data

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._data


def test_context_search_posts_to_workspace_context_search(
    account_fixture: Account, mocker: Any
) -> None:
    post = mocker.patch(
        "supervaizer.context._sync_httpx_client.post",
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
        "supervaizer.context._sync_httpx_client.post",
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
    post = mocker.patch("supervaizer.context._sync_httpx_client.post")
    client = ContextClient(account_fixture)

    with pytest.raises(
        ValueError, match="expected_workspace_id .* does not match account.workspace_id"
    ):
        client.search(query="x", expected_workspace_id="other-workspace")

    post.assert_not_called()


def test_context_search_rejects_empty_mission_id(
    account_fixture: Account, mocker: Any
) -> None:
    post = mocker.patch("supervaizer.context._sync_httpx_client.post")

    with pytest.raises(ValueError, match="mission_id must be a non-empty string"):
        context.search(account=account_fixture, query="billing", mission_id="")

    post.assert_not_called()


def test_context_open_rejects_empty_mission_id(
    account_fixture: Account, mocker: Any
) -> None:
    post = mocker.patch("supervaizer.context._sync_httpx_client.post")

    with pytest.raises(ValueError, match="mission_id must be a non-empty string"):
        account_fixture.context.open(
            ref="supervaize.context.workspace.billing", mission_id=" "
        )

    post.assert_not_called()


def test_context_open_helper_forwards_mission_and_request_options(
    account_fixture: Account, mocker: Any
) -> None:
    post = mocker.patch(
        "supervaizer.context._sync_httpx_client.post",
        return_value=_Response({
            "ref": "context-ref",
            "title": "Policy",
            "scope": "mission",
            "source_type": "text",
            "version": 1,
            "content": "Policy text",
        }),
    )

    result = context.open(
        account=account_fixture,
        ref="context-ref",
        mission_id="mission-1",
        query="policy",
        max_chars=500,
        expected_workspace_id=account_fixture.workspace_id,
    )

    assert result.content == "Policy text"
    post.assert_called_once_with(
        f"{account_fixture.api_url_w_v1}/context/open/",
        headers=account_fixture.api_headers,
        json={
            "ref": "context-ref",
            "mission_id": "mission-1",
            "query": "policy",
            "max_chars": 500,
        },
    )


def test_context_open_helper_rejects_wrong_workspace_before_request(
    account_fixture: Account, mocker: Any
) -> None:
    post = mocker.patch("supervaizer.context._sync_httpx_client.post")

    with pytest.raises(ValueError, match="does not match account.workspace_id"):
        context.open(
            account=account_fixture,
            ref="context-ref",
            expected_workspace_id="other-workspace",
        )

    post.assert_not_called()


def test_context_search_helper_rejects_wrong_workspace_before_request(
    account_fixture: Account, mocker: Any
) -> None:
    post = mocker.patch("supervaizer.context._sync_httpx_client.post")

    with pytest.raises(ValueError, match="does not match account.workspace_id"):
        context.search(
            account=account_fixture,
            query="policy",
            expected_workspace_id="other-workspace",
        )

    post.assert_not_called()


def test_context_client_uses_search_and_open_limits_by_default(
    account_fixture: Account, mocker: Any
) -> None:
    post = mocker.patch(
        "supervaizer.context._sync_httpx_client.post",
        side_effect=[
            _Response({"query": "policy", "results": []}),
            _Response({
                "ref": "context-ref",
                "title": "Policy",
                "scope": "workspace",
                "source_type": "text",
                "version": 1,
                "content": "Policy text",
            }),
        ],
    )
    client = ContextClient(account_fixture)

    client.search(query="policy")
    client.open(ref="context-ref")

    assert post.call_args_list[0].kwargs["json"] == {"query": "policy", "limit": 5}
    assert post.call_args_list[1].kwargs["json"] == {
        "ref": "context-ref",
        "max_chars": 3000,
    }


def test_context_open_helper_uses_default_content_limit(
    account_fixture: Account, mocker: Any
) -> None:
    post = mocker.patch(
        "supervaizer.context._sync_httpx_client.post",
        return_value=_Response({
            "ref": "context-ref",
            "title": "Policy",
            "scope": "workspace",
            "source_type": "text",
            "version": 1,
            "content": "Policy text",
        }),
    )

    context.open(account=account_fixture, ref="context-ref")

    assert post.call_args.kwargs["json"] == {"ref": "context-ref", "max_chars": 3000}
