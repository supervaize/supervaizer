# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

from __future__ import annotations

import atexit
import os
from typing import TYPE_CHECKING, Any, Literal

import httpx
from pydantic import Field

from supervaizer.common import SvBaseModel

if TYPE_CHECKING:
    from supervaizer.account import Account

ContextScope = Literal["workspace", "mission"]

_sync_httpx_transport = httpx.HTTPTransport(
    retries=int(os.getenv("SUPERVAIZE_HTTP_MAX_RETRIES", 2))
)
_sync_httpx_client = httpx.Client(transport=_sync_httpx_transport)


class ContextCitation(SvBaseModel):
    ref: str
    title: str
    source_type: str
    version: int


class ContextSearchResult(SvBaseModel):
    ref: str
    title: str
    scope: ContextScope
    source_type: str
    version: int
    tags: list[str] = Field(default_factory=list)
    excerpt: str = ""
    score: int = 0
    citation: ContextCitation | None = None


class ContextSearchResponse(SvBaseModel):
    query: str
    results: list[ContextSearchResult] = Field(default_factory=list)


class ContextOpenResponse(SvBaseModel):
    ref: str
    title: str
    scope: ContextScope
    source_type: str
    version: int
    instructions: str = ""
    tags: list[str] = Field(default_factory=list)
    content: str
    citations: list[ContextCitation] = Field(default_factory=list)


class ContextClient:
    def __init__(self, account: Account) -> None:
        self.account: Account = account

    def search(
        self,
        *,
        query: str,
        mission_id: str | None = None,
        scope: ContextScope | None = None,
        tags: list[str] | None = None,
        limit: int = 5,
        expected_workspace_id: str | None = None,
    ) -> ContextSearchResponse:
        self._reject_conflicting_workspace(expected_workspace_id)
        payload: dict[str, Any] = {"query": query, "limit": limit}
        self._add_mission_id(payload, mission_id)
        if scope:
            payload["scope"] = scope
        if tags:
            payload["tags"] = tags
        response = _sync_httpx_client.post(
            self._url("search"), headers=self.account.api_headers, json=payload
        )
        response.raise_for_status()
        return ContextSearchResponse.model_validate(response.json())

    def open(
        self,
        *,
        ref: str,
        mission_id: str | None = None,
        query: str | None = None,
        max_chars: int = 3000,
        expected_workspace_id: str | None = None,
    ) -> ContextOpenResponse:
        self._reject_conflicting_workspace(expected_workspace_id)
        payload: dict[str, Any] = {"ref": ref, "max_chars": max_chars}
        self._add_mission_id(payload, mission_id)
        if query:
            payload["query"] = query
        response = _sync_httpx_client.post(
            self._url("open"), headers=self.account.api_headers, json=payload
        )
        response.raise_for_status()
        return ContextOpenResponse.model_validate(response.json())

    def _url(self, action: str) -> str:
        return f"{self.account.api_url_w_v1}/context/{action}/"

    def _reject_conflicting_workspace(self, expected_workspace_id: str | None) -> None:
        if expected_workspace_id and expected_workspace_id != self.account.workspace_id:
            raise ValueError(
                f"expected_workspace_id {expected_workspace_id!r} does not match "
                f"account.workspace_id {self.account.workspace_id!r}"
            )

    def _add_mission_id(self, payload: dict[str, Any], mission_id: str | None) -> None:
        if mission_id is None:
            return
        if not mission_id.strip():
            raise ValueError("mission_id must be a non-empty string when provided")
        payload["mission_id"] = mission_id


def search(
    *,
    account: Account,
    query: str,
    mission_id: str | None = None,
    scope: ContextScope | None = None,
    tags: list[str] | None = None,
    limit: int = 5,
    expected_workspace_id: str | None = None,
) -> ContextSearchResponse:
    return ContextClient(account).search(
        query=query,
        mission_id=mission_id,
        scope=scope,
        tags=tags,
        limit=limit,
        expected_workspace_id=expected_workspace_id,
    )


def open(
    *,
    account: Account,
    ref: str,
    mission_id: str | None = None,
    query: str | None = None,
    max_chars: int = 3000,
    expected_workspace_id: str | None = None,
) -> ContextOpenResponse:
    return ContextClient(account).open(
        ref=ref,
        mission_id=mission_id,
        query=query,
        max_chars=max_chars,
        expected_workspace_id=expected_workspace_id,
    )


def close_httpx_client_sync() -> None:
    _sync_httpx_client.close()


atexit.register(close_httpx_client_sync)
