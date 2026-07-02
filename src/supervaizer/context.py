# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

import httpx
from pydantic import Field

from supervaizer.common import SvBaseModel

if TYPE_CHECKING:
    from supervaizer.account import Account

ContextScope = Literal["workspace", "mission"]


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
        self.account = account

    def search(
        self,
        *,
        query: str,
        mission_id: str | None = None,
        scope: ContextScope | None = None,
        tags: list[str] | None = None,
        limit: int = 5,
        workspace_id: str | None = None,
    ) -> ContextSearchResponse:
        self._reject_conflicting_workspace(workspace_id)
        payload: dict[str, Any] = {"query": query, "limit": limit}
        if mission_id:
            payload["mission_id"] = mission_id
        if scope:
            payload["scope"] = scope
        if tags:
            payload["tags"] = tags
        response = httpx.post(
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
        workspace_id: str | None = None,
    ) -> ContextOpenResponse:
        self._reject_conflicting_workspace(workspace_id)
        payload: dict[str, Any] = {"ref": ref, "max_chars": max_chars}
        if mission_id:
            payload["mission_id"] = mission_id
        if query:
            payload["query"] = query
        response = httpx.post(
            self._url("open"), headers=self.account.api_headers, json=payload
        )
        response.raise_for_status()
        return ContextOpenResponse.model_validate(response.json())

    def _url(self, action: str) -> str:
        return f"{self.account.api_url_w_v1}/context/{action}/"

    def _reject_conflicting_workspace(self, workspace_id: str | None) -> None:
        if workspace_id and workspace_id != self.account.workspace_id:
            raise ValueError(
                f"workspace_id {workspace_id!r} does not match account.workspace_id {self.account.workspace_id!r}"
            )


def search(
    *,
    account: Account,
    query: str,
    mission_id: str | None = None,
    scope: ContextScope | None = None,
    tags: list[str] | None = None,
    limit: int = 5,
    workspace_id: str | None = None,
) -> ContextSearchResponse:
    return ContextClient(account).search(
        query=query,
        mission_id=mission_id,
        scope=scope,
        tags=tags,
        limit=limit,
        workspace_id=workspace_id,
    )


def open(
    *,
    account: Account,
    ref: str,
    mission_id: str | None = None,
    query: str | None = None,
    max_chars: int = 3000,
    workspace_id: str | None = None,
) -> ContextOpenResponse:
    return ContextClient(account).open(
        ref=ref,
        mission_id=mission_id,
        query=query,
        max_chars=max_chars,
        workspace_id=workspace_id,
    )
