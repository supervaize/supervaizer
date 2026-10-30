# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""Account.report_consumption pushes billable consumption to Studio."""

from __future__ import annotations

import inspect
import json
import subprocess
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import httpx
import pytest
from pydantic import ValidationError
from pytest_mock import MockerFixture

from supervaizer import BillableConsumption, ConsumptionReceipt
from supervaizer.account import Account

RESULTS: list[dict[str, Any]] = [
    {"idempotency_key": "s1:minute", "status": "accepted", "reason": None},
    {"idempotency_key": "s1:token", "status": "duplicate", "reason": None},
    {"idempotency_key": "s2:minute", "status": "rejected", "reason": "no_grant"},
]


@pytest.fixture(autouse=True)
def remote_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SUPERVAIZER_LOCAL_MODE", raising=False)


def _record(key: str, quantity: str = "1.25") -> BillableConsumption:
    return BillableConsumption(
        sku="interview_minute",
        quantity=Decimal(quantity),
        unit="minute",
        job_id="job-1",
        idempotency_key=key,
        occurred_at=datetime(2026, 10, 30, 10, tzinfo=UTC),
    )


def _records() -> list[BillableConsumption]:
    return [_record(result["idempotency_key"]) for result in RESULTS]


def _url(account: Account, workspace: str) -> str:
    return f"{account.api_url}/w/{workspace}/api/v1/billing/consumption/"


def _statuses(receipts: list[ConsumptionReceipt]) -> list[tuple[str, str]]:
    return [(receipt.idempotency_key, receipt.status) for receipt in receipts]


@pytest.mark.asyncio
async def test_report_consumption_posts_report_and_keeps_order(
    account_fixture: Account, respx_mock: Any
) -> None:
    route = respx_mock.post(_url(account_fixture, account_fixture.workspace_id))
    route.respond(200, json={"results": RESULTS})

    receipts = await account_fixture.report_consumption(_records(), agent_slug="aidan")

    assert _statuses(receipts) == [
        ("s1:minute", "accepted"),
        ("s1:token", "duplicate"),
        ("s2:minute", "rejected"),
    ]
    assert receipts[2].reason == "no_grant"
    request = route.calls.last.request
    body = json.loads(request.content)
    assert body["agent_slug"] == "aidan"
    assert [record["idempotency_key"] for record in body["records"]] == [
        result["idempotency_key"] for result in RESULTS
    ]
    assert body["records"][0]["quantity"] == "1.25"
    assert body["records"][0]["occurred_at"] == "2026-10-30T10:00:00Z"
    assert request.headers["Authorization"] == f"Api-Key {account_fixture.api_key}"
    assert request.headers["workspace"] == account_fixture.workspace_id


def test_report_consumption_sync_posts_to_the_given_workspace(
    account_fixture: Account, respx_mock: Any
) -> None:
    route = respx_mock.post(_url(account_fixture, "guest-ws"))
    route.respond(200, json={"results": RESULTS[:1]})

    receipts = account_fixture.report_consumption_sync(
        [_record("s1:minute")], agent_slug="aidan", workspace_id="guest-ws"
    )

    assert _statuses(receipts) == [("s1:minute", "accepted")]
    assert route.calls.last.request.headers["workspace"] == "guest-ws"


@pytest.mark.asyncio
async def test_report_consumption_local_mode_accepts_every_record(
    account_fixture: Account,
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SUPERVAIZER_LOCAL_MODE", "true")
    mock_post = mocker.patch(
        "supervaizer.account_service._httpx_client.post", new=mocker.AsyncMock()
    )

    receipts = await account_fixture.report_consumption(_records(), agent_slug="aidan")

    assert _statuses(receipts) == [
        (result["idempotency_key"], "accepted") for result in RESULTS
    ]
    assert all(receipt.reason is None for receipt in receipts)
    mock_post.assert_not_called()


def test_report_consumption_sync_local_mode_accepts_every_record(
    account_fixture: Account,
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SUPERVAIZER_LOCAL_MODE", "true")
    mock_post = mocker.patch("supervaizer.account_service._sync_httpx_client.post")

    receipts = account_fixture.report_consumption_sync(
        [_record("s1:minute")], agent_slug="aidan"
    )

    assert _statuses(receipts) == [("s1:minute", "accepted")]
    mock_post.assert_not_called()


@pytest.mark.asyncio
async def test_report_consumption_reraises_whole_batch_error(
    account_fixture: Account, respx_mock: Any
) -> None:
    respx_mock.post(_url(account_fixture, account_fixture.workspace_id)).respond(
        403, json={"detail": "forbidden"}, headers={"X-Request-ID": "req-9"}
    )

    with pytest.raises(httpx.HTTPStatusError, match="403"):
        await account_fixture.report_consumption(_records(), agent_slug="aidan")


def test_report_consumption_sync_reraises_whole_batch_error(
    account_fixture: Account, respx_mock: Any
) -> None:
    respx_mock.post(_url(account_fixture, account_fixture.workspace_id)).respond(400)

    with pytest.raises(httpx.HTTPStatusError, match="400"):
        account_fixture.report_consumption_sync(_records(), agent_slug="aidan")


@pytest.mark.asyncio
async def test_report_consumption_reraises_connect_error(
    account_fixture: Account, respx_mock: Any
) -> None:
    respx_mock.post(_url(account_fixture, account_fixture.workspace_id)).mock(
        side_effect=httpx.ConnectError("refused")
    )

    with pytest.raises(httpx.ConnectError, match="refused"):
        await account_fixture.report_consumption(_records(), agent_slug="aidan")


def test_report_consumption_sync_reraises_connect_error(
    account_fixture: Account, respx_mock: Any
) -> None:
    respx_mock.post(_url(account_fixture, account_fixture.workspace_id)).mock(
        side_effect=httpx.ConnectTimeout("timed out")
    )

    with pytest.raises(httpx.ConnectTimeout, match="timed out"):
        account_fixture.report_consumption_sync(_records(), agent_slug="aidan")


@pytest.mark.parametrize(
    "results",
    [
        RESULTS[:2],
        [RESULTS[1], RESULTS[0], RESULTS[2]],
    ],
)
def test_report_consumption_rejects_results_that_do_not_match_records(
    account_fixture: Account, respx_mock: Any, results: list[dict[str, Any]]
) -> None:
    respx_mock.post(_url(account_fixture, account_fixture.workspace_id)).respond(
        200, json={"results": results}
    )

    with pytest.raises(ValueError, match="one result per record"):
        account_fixture.report_consumption_sync(_records(), agent_slug="aidan")


def test_report_consumption_validates_the_batch_before_sending(
    account_fixture: Account,
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SUPERVAIZER_LOCAL_MODE", "true")
    mock_post = mocker.patch("supervaizer.account_service._sync_httpx_client.post")

    with pytest.raises(ValidationError):
        account_fixture.report_consumption_sync([], agent_slug="aidan")
    with pytest.raises(ValidationError):
        account_fixture.report_consumption_sync(
            [_record(f"k{index}") for index in range(201)], agent_slug="aidan"
        )
    mock_post.assert_not_called()


def test_report_consumption_rejects_blank_workspace(account_fixture: Account) -> None:
    with pytest.raises(ValueError, match="workspace_id"):
        account_fixture.report_consumption_sync(
            _records(), agent_slug="aidan", workspace_id="  "
        )


def test_report_consumption_logs_the_redacted_body_of_a_4xx(
    account_fixture: Account, respx_mock: Any, mocker: MockerFixture
) -> None:
    respx_mock.post(_url(account_fixture, account_fixture.workspace_id)).respond(
        400,
        json={
            "records": [{"quantity": ["Ensure no more than 6 decimal places."]}],
            "api_key": "leaked-value",
        },
    )
    mock_log = mocker.patch("supervaizer.account_service.log")

    with pytest.raises(httpx.HTTPStatusError):
        account_fixture.report_consumption_sync(_records(), agent_slug="aidan")

    errors = " ".join(str(call.args[0]) for call in mock_log.error.call_args_list)
    assert "6 decimal places" in errors
    assert "leaked-value" not in errors


@pytest.mark.parametrize(
    "method", [Account.report_consumption, Account.report_consumption_sync]
)
def test_report_consumption_documents_its_errors(method: Callable[..., Any]) -> None:
    doc = inspect.getdoc(method) or ""

    for name in ("httpx.HTTPError", "ValueError", "ValidationError"):
        assert name in doc


def test_importing_account_does_not_build_the_http_clients() -> None:
    code = (
        "import sys, supervaizer.account; "
        "print('supervaizer.account_service' in sys.modules)"
    )

    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )

    assert result.stdout.strip() == "False"


def test_report_consumption_accepts_dict_records(
    account_fixture: Account, respx_mock: Any
) -> None:
    route = respx_mock.post(_url(account_fixture, account_fixture.workspace_id))
    route.respond(200, json={"results": RESULTS[:1]})
    record: dict[str, Any] = {
        **_record("s1:minute").model_dump(mode="json"),
        "quantity": "3.5",
    }

    receipts = account_fixture.report_consumption_sync([record], agent_slug="aidan")

    assert _statuses(receipts) == [("s1:minute", "accepted")]
    assert json.loads(route.calls.last.request.content)["records"][0]["quantity"] == (
        "3.5"
    )
