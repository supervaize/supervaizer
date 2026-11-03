# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""Shared rig for admin endpoint tests: a router on real in-memory storage."""

from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pytest_mock import MockerFixture

from supervaizer.admin import routes
from supervaizer.admin.routes import create_admin_routes
from supervaizer.storage import StorageManager


class Page:
    """What one endpoint call produced: the HTTP response and the template input."""

    def __init__(self, response: Any, template: str | None, context: dict[str, Any]):
        self.response = response
        self.template = template
        self.context = context

    @property
    def status(self) -> int:
        return int(self.response.status_code)

    def ids(self, key: str) -> list[str]:
        return [row["id"] for row in self.context[key]]

    def names(self, key: str) -> list[str]:
        return [row["name"] for row in self.context[key]]


class AdminRig:
    """An admin router bound to a real in-memory storage, with template calls recorded."""

    def __init__(self, mocker: MockerFixture, storage: StorageManager) -> None:
        self.storage = storage
        mocker.patch(
            "supervaizer.admin.routes.StorageManager", return_value=self.storage
        )
        self.spy = mocker.spy(routes.templates, "TemplateResponse")
        app = FastAPI()
        app.include_router(create_admin_routes(), prefix="/manage")
        self.client = TestClient(app, raise_server_exceptions=False)

    def seed(self, kind: str, rows: list[dict[str, Any]]) -> None:
        for row in rows:
            self.storage.save_object(kind, dict(row))

    def request(self, method: str, url: str, **kwargs: Any) -> Page:
        self.spy.reset_mock()
        response = self.client.request(method, url, **kwargs)
        if not self.spy.called:
            return Page(response, None, {})
        args = self.spy.call_args.args
        return Page(response, args[1], args[2])

    def get(self, url: str) -> Page:
        return self.request("GET", url)
