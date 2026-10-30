# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""Billing catalog and billable consumption wire contract."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError

import supervaizer
from supervaizer import contracts
from supervaizer.contracts import (
    BillableConsumption,
    BillingCatalogItem,
    ConsumptionReceipt,
    ConsumptionReport,
    ConsumptionReportResponse,
)

RECORD: dict[str, Any] = {
    "sku": "interview_minute",
    "quantity": "1.50",
    "unit": "minute",
    "job_id": "job-1",
    "case_id": "case-1",
    "idempotency_key": "session-1:interview_minute",
    "agent_cost_usd": "0.04",
    "description": "Interview session",
    "occurred_at": "2026-10-30T10:00:00+00:00",
}


def test_catalog_item_defaults_description_to_empty() -> None:
    item = BillingCatalogItem(sku="hello_message", unit="message")

    assert item.model_dump(mode="json") == {
        "sku": "hello_message",
        "unit": "message",
        "description": "",
    }


@pytest.mark.parametrize(
    "override",
    [
        {"sku": ""},
        {"sku": "Interview_Minute"},
        {"sku": "interview-minute"},
        {"sku": "interview minute"},
        {"sku": "x" * 65},
        {"unit": ""},
        {"unit": "x" * 33},
        {"description": "x" * 256},
    ],
)
def test_catalog_item_rejects_out_of_contract_values(override: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        BillingCatalogItem.model_validate({
            "sku": "interview_minute",
            "unit": "minute",
            **override,
        })


def test_consumption_serializes_decimals_as_strings() -> None:
    record = BillableConsumption.model_validate(RECORD)

    assert record.quantity == Decimal("1.50")
    assert record.model_dump(mode="json") == {
        **RECORD,
        "occurred_at": "2026-10-30T10:00:00Z",
    }


def test_consumption_sends_null_for_unset_optional_fields() -> None:
    record = BillableConsumption(
        sku="interview_minute",
        quantity=Decimal(2),
        unit="minute",
        job_id="job-1",
        idempotency_key="k",
        occurred_at=datetime(2026, 10, 30, 12, tzinfo=timezone(timedelta(hours=2))),
    )

    payload = record.model_dump(mode="json")

    assert payload["case_id"] is None
    assert payload["agent_cost_usd"] is None
    assert payload["description"] is None
    assert payload["quantity"] == "2"
    assert payload["occurred_at"] == "2026-10-30T12:00:00+02:00"


@pytest.mark.parametrize(
    "override",
    [
        {"quantity": "0"},
        {"quantity": "-1"},
        {"quantity": "NaN"},
        {"quantity": "Infinity"},
        {"idempotency_key": ""},
        {"idempotency_key": "k" * 129},
        {"sku": "Interview-Minute"},
        {"unit": ""},
        {"job_id": ""},
        {"agent_cost_usd": "-0.01"},
        {"description": "x" * 256},
        {"occurred_at": "2026-10-30T10:00:00"},
        {"occurred_at": datetime(2026, 10, 30, 10)},
    ],
)
def test_consumption_rejects_out_of_contract_values(override: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        BillableConsumption.model_validate({**RECORD, **override})


@pytest.mark.parametrize(
    "override",
    [
        {"quantity": "1.1234567"},
        {"quantity": "1.5000000"},
        {"quantity": "1000000000000"},
        {"agent_cost_usd": "0.0000001"},
        {"agent_cost_usd": "0.1000000"},
        {"agent_cost_usd": "1000000000000"},
        {"job_id": "j" * 65},
        {"case_id": "c" * 65},
    ],
)
def test_consumption_rejects_values_studio_refuses(override: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        BillableConsumption.model_validate({**RECORD, **override})


def test_consumption_accepts_studio_bounds() -> None:
    record = BillableConsumption.model_validate({
        **RECORD,
        "quantity": "999999999999.999999",
        "agent_cost_usd": "0.000001",
        "job_id": "j" * 64,
        "case_id": "c" * 64,
    })

    assert record.model_dump(mode="json")["quantity"] == "999999999999.999999"


def test_consumption_accepts_bounds() -> None:
    record = BillableConsumption.model_validate({
        **RECORD,
        "idempotency_key": "k" * 128,
        "description": "x" * 255,
        "agent_cost_usd": None,
        "occurred_at": datetime(2026, 10, 30, 10, tzinfo=UTC),
    })

    assert len(record.idempotency_key) == 128


def test_report_carries_agent_slug_and_records() -> None:
    report = ConsumptionReport(
        agent_slug="aidan",
        records=[BillableConsumption.model_validate(RECORD)],
    )

    payload = report.model_dump(mode="json")

    assert list(payload) == ["agent_slug", "records"]
    assert payload["records"][0]["quantity"] == "1.50"


@pytest.mark.parametrize("count", [0, 201])
def test_report_bounds_record_count(count: int) -> None:
    with pytest.raises(ValidationError):
        ConsumptionReport(
            agent_slug="aidan",
            records=[BillableConsumption.model_validate(RECORD)] * count,
        )


def test_report_accepts_two_hundred_records() -> None:
    report = ConsumptionReport(
        agent_slug="aidan",
        records=[BillableConsumption.model_validate(RECORD)] * 200,
    )

    assert len(report.records) == 200


def test_report_requires_agent_slug() -> None:
    with pytest.raises(ValidationError):
        ConsumptionReport(
            agent_slug="", records=[BillableConsumption.model_validate(RECORD)]
        )


def test_response_parses_the_three_statuses_in_order() -> None:
    response = ConsumptionReportResponse.model_validate({
        "results": [
            {"idempotency_key": "a", "status": "accepted", "reason": None},
            {"idempotency_key": "b", "status": "duplicate", "reason": None},
            {"idempotency_key": "c", "status": "rejected", "reason": "unknown_sku"},
        ]
    })

    assert [(r.idempotency_key, r.status, r.reason) for r in response.results] == [
        ("a", "accepted", None),
        ("b", "duplicate", None),
        ("c", "rejected", "unknown_sku"),
    ]


def test_receipt_rejects_unknown_status() -> None:
    with pytest.raises(ValidationError):
        ConsumptionReceipt.model_validate({"idempotency_key": "a", "status": "booked"})


def test_receipt_reason_defaults_to_none() -> None:
    receipt = ConsumptionReceipt(idempotency_key="a", status="accepted")

    assert receipt.reason is None


@pytest.mark.parametrize(
    "name",
    [
        "BillingCatalogItem",
        "BillableConsumption",
        "ConsumptionReceipt",
        "ConsumptionReport",
        "ConsumptionReportResponse",
    ],
)
def test_billing_models_are_public_exports(name: str) -> None:
    assert getattr(supervaizer, name) is getattr(contracts, name)
    assert name in supervaizer.__all__
