# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""Payload shape of the v2 job push events, as Studio reads it.

Studio reads `source.job`, `details.job`, `details.cases`,
`details.removed_cases`, `details.reason` and `details.input`
(`apps/sv_entities/services/event_processor.py`).
"""

import json
from datetime import UTC, datetime

import pytest
from pytest_mock import MockerFixture

from supervaizer import (
    Account,
    EventType,
    V2CaseSnapshot,
    V2JobRefreshRequestedEvent,
    V2JobUpdatedEvent,
    V2StepSnapshot,
)

JOB_ID = "job-123"


def test_event_type_values() -> None:
    assert EventType.V2_JOB_UPDATED.value == "supervaizer.v2.job.updated"
    assert (
        EventType.V2_JOB_REFRESH_REQUESTED.value
        == "supervaizer.v2.job.refresh_requested"
    )


def test_job_updated_payload(account_fixture: Account) -> None:
    case = V2CaseSnapshot(
        id="case-1",
        status="in_progress",
        steps=[V2StepSnapshot(id="step-1", activity="operation", status="in_progress")],
    )
    event = V2JobUpdatedEvent(
        job_id=JOB_ID,
        account=account_fixture,
        job={"status": "in_progress", "information": {"started_at": "2026-11-16"}},
        cases=[case, {"id": "case-2", "status": "awaiting"}],
        removed_cases=[{"id": "case-0", "reason": "duplicate"}],
        reason="phase 1 done",
    )

    assert event.payload == {
        "source": {"job": JOB_ID},
        "workspace": account_fixture.workspace_id,
        "event_type": "supervaizer.v2.job.updated",
        "object_type": "job",
        "details": {
            "job": {
                "status": "in_progress",
                "information": {"started_at": "2026-11-16"},
            },
            "cases": [
                {
                    "id": "case-1",
                    "status": "in_progress",
                    "steps": [
                        {
                            "id": "step-1",
                            "activity": "operation",
                            "status": "in_progress",
                        }
                    ],
                },
                {"id": "case-2", "status": "awaiting"},
            ],
            "removed_cases": [{"id": "case-0", "reason": "duplicate"}],
            "reason": "phase 1 done",
        },
    }


def test_job_updated_omits_absent_keys(account_fixture: Account) -> None:
    """A case without steps must not send `steps: []`: Studio reads that as zero steps."""
    event = V2JobUpdatedEvent(
        job_id=JOB_ID,
        account=account_fixture,
        cases=[V2CaseSnapshot(id="case-1", status="completed")],
    )

    assert event.details == {"cases": [{"id": "case-1", "status": "completed"}]}


def test_job_refresh_requested_payload(account_fixture: Account) -> None:
    event = V2JobRefreshRequestedEvent(
        job_id=JOB_ID,
        account=account_fixture,
        input={"cursor": "abc"},
        reason="external change",
    )

    assert event.payload["source"] == {"job": JOB_ID}
    assert event.payload["event_type"] == "supervaizer.v2.job.refresh_requested"
    assert event.payload["details"] == {
        "input": {"cursor": "abc"},
        "reason": "external change",
    }
    assert (
        V2JobRefreshRequestedEvent(job_id=JOB_ID, account=account_fixture).details == {}
    )


@pytest.mark.parametrize("job_id", ["", "  "])
def test_blank_job_id_is_refused(account_fixture: Account, job_id: str) -> None:
    with pytest.raises(ValueError, match="Studio job id"):
        V2JobUpdatedEvent(job_id=job_id, account=account_fixture)
    with pytest.raises(ValueError, match="Studio job id"):
        V2JobRefreshRequestedEvent(job_id=job_id, account=account_fixture)


@pytest.mark.asyncio
async def test_account_helpers_use_send_event(
    account_fixture: Account, mocker: MockerFixture
) -> None:
    mock_post = mocker.patch(
        "supervaizer.account_service._httpx_client.post", new=mocker.AsyncMock()
    )
    mock_post.return_value.text = "{}"
    mock_post.return_value.raise_for_status = mocker.Mock()

    await account_fixture.push_job_update(JOB_ID, job={"status": "awaiting"})
    await account_fixture.request_job_refresh(JOB_ID, reason="pull")

    sent = [call.kwargs["json"] for call in mock_post.call_args_list]
    assert [body["event_type"] for body in sent] == [
        "supervaizer.v2.job.updated",
        "supervaizer.v2.job.refresh_requested",
    ]
    assert all(body["source"] == {"job": JOB_ID} for body in sent)
    assert sent[0]["details"] == {"job": {"status": "awaiting"}}
    assert sent[1]["details"] == {"reason": "pull"}


def test_account_sync_helpers_use_send_event_sync(
    account_fixture: Account, mocker: MockerFixture
) -> None:
    mock_post = mocker.patch("supervaizer.account_service._sync_httpx_client.post")
    mock_post.return_value.text = "{}"

    account_fixture.push_job_update_sync(JOB_ID, removed_cases=[{"id": "case-0"}])
    account_fixture.request_job_refresh_sync(JOB_ID, input={"cursor": "abc"})

    sent = [call.kwargs["json"] for call in mock_post.call_args_list]
    assert sent[0]["details"] == {"removed_cases": [{"id": "case-0"}]}
    assert sent[1]["details"] == {"input": {"cursor": "abc"}}
    assert all(body["source"] == {"job": JOB_ID} for body in sent)


def test_job_update_serializes_case_timestamps_for_studio(
    account_fixture: Account,
) -> None:
    event = V2JobUpdatedEvent(
        job_id=JOB_ID,
        account=account_fixture,
        cases=[
            V2CaseSnapshot(
                id="case-1",
                status="in_progress",
                started_at=datetime(2026, 11, 25, 10, 30, tzinfo=UTC),
            )
        ],
    )

    assert event.details["cases"] == [
        {"id": "case-1", "status": "in_progress", "started_at": "2026-11-25T10:30:00Z"}
    ]
    json.dumps(event.payload)
