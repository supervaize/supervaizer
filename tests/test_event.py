# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

import json
from datetime import datetime, timezone
from uuid import uuid4

from supervaizer import (
    Account,
    Agent,
    AgentRegisterEvent,
    Case,
    CaseNodeUpdate,
    CasesBatchEvent,
    CaseStartEvent,
    CaseUpdateEvent,
    Event,
    EventType,
    JobFinishedEvent,
    JobStartConfirmationEvent,
    Server,
    ServerRegisterEvent,
)
from supervaizer.job import Job, JobContext
from supervaizer.lifecycle import EntityStatus


def test_event(event_fixture: Event) -> None:
    assert isinstance(event_fixture, Event)
    assert event_fixture.type == EventType.AGENT_WAKEUP
    assert event_fixture.source == {"test": "value"}
    assert event_fixture.details == {"test": "value"}
    assert (
        list(event_fixture.payload.keys()).sort()
        == [
            "name",
            "source",
            "workspace_id",
            "event_type",
            "details",
        ].sort()
    )


def test_agent_register_event(agent_fixture: Agent, account_fixture: Account) -> None:
    agent_register_event = AgentRegisterEvent(
        agent=agent_fixture,
        account=account_fixture,
        polling=False,
    )
    assert isinstance(agent_register_event, AgentRegisterEvent)
    assert agent_register_event.type == EventType.AGENT_REGISTER
    assert agent_register_event.source == {"agent": agent_fixture.slug}
    assert agent_register_event.details["name"] == "agentName"
    assert agent_register_event.details["polling"] is False


def test_server_register_event(
    server_fixture: Server, account_fixture: Account
) -> None:
    server_register_event = ServerRegisterEvent(
        server=server_fixture,
        account=account_fixture,
    )
    assert isinstance(server_register_event, ServerRegisterEvent)
    assert server_register_event.type == EventType.SERVER_REGISTER
    assert server_register_event.source == {"server": server_fixture.uri}
    assert server_register_event.details == server_fixture.registration_info


def test_case_start_event(case_fixture: Case, account_fixture: Account) -> None:
    case_start_event = CaseStartEvent(
        case=case_fixture,
        account=account_fixture,
    )
    assert isinstance(case_start_event, CaseStartEvent)
    assert case_start_event.type == EventType.CASE_START
    assert case_start_event.source == {
        "job": case_fixture.job_id,
        "case": case_fixture.id,
    }
    assert case_start_event.details == case_fixture.registration_info


def test_case_update_event(
    case_fixture: Case,
    account_fixture: Account,
    case_node_update_fixture: CaseNodeUpdate,
) -> None:
    case_update_event = CaseUpdateEvent(
        case=case_fixture,
        account=account_fixture,
        update=case_node_update_fixture,
    )
    assert isinstance(case_update_event, CaseUpdateEvent)
    assert case_update_event.type == EventType.CASE_UPDATE
    assert case_update_event.source == {
        "job": case_fixture.job_id,
        "case": case_fixture.id,
    }
    assert case_update_event.details == case_node_update_fixture.registration_info


def test_job_start_confirmation_event(
    job_fixture: Job, account_fixture: Account
) -> None:
    job_start_confirmation_event = JobStartConfirmationEvent(
        job=job_fixture,
        account=account_fixture,
    )
    assert isinstance(job_start_confirmation_event, JobStartConfirmationEvent)
    assert job_start_confirmation_event.type == EventType.JOB_START_CONFIRMATION
    assert job_start_confirmation_event.source == {"job": job_fixture.id}
    assert job_start_confirmation_event.details == job_fixture.registration_info


def test_job_finished_event(job_fixture: Job, account_fixture: Account) -> None:
    job_finished_event = JobFinishedEvent(
        job=job_fixture,
        account=account_fixture,
    )
    assert isinstance(job_finished_event, JobFinishedEvent)


def test_cases_batch_event_single_job(
    case_fixture: Case,
    account_fixture: Account,
    case_node_update_fixture: CaseNodeUpdate,
) -> None:
    # Pre-populate the case with one step so the batch carries existing history.
    case_fixture.updates = [case_node_update_fixture]

    second_case = Case(
        id=str(uuid4()),
        job_id=case_fixture.job_id,
        account=account_fixture,
        status=case_fixture.status,
        name="Second Case",
        description="Second Case Description",
    )

    batch = CasesBatchEvent(
        cases=[case_fixture, second_case],
        account=account_fixture,
    )

    assert batch.type == EventType.CASES_BATCH
    assert batch.object_type == "cases_batch"
    # job_id is inferred when all cases share one
    assert batch.source == {"job": case_fixture.job_id, "batch_size": 2}
    assert batch.details["job_id"] == case_fixture.job_id
    assert batch.details["count"] == 2
    assert len(batch.details["cases"]) == 2
    assert batch.details["cases"][0]["case_id"] == case_fixture.id
    assert batch.details["cases"][0]["updates"][0]["index"] == 1
    # Payload is JSON-encodable for httpx
    json.dumps(batch.payload)


def test_cases_batch_event_explicit_job_id(
    case_fixture: Case,
    account_fixture: Account,
) -> None:
    other_job_case = Case(
        id=str(uuid4()),
        job_id="another-job",
        account=account_fixture,
        status=case_fixture.status,
        name="Other Job Case",
        description="Different job",
    )

    # Mixed jobs => job_id is not inferred unless explicitly provided.
    batch_no_id = CasesBatchEvent(
        cases=[case_fixture, other_job_case],
        account=account_fixture,
    )
    assert batch_no_id.details["job_id"] is None
    assert "job" not in batch_no_id.source
    assert batch_no_id.source["batch_size"] == 2

    # Explicit job_id wins.
    batch_explicit = CasesBatchEvent(
        cases=[case_fixture, other_job_case],
        account=account_fixture,
        job_id="explicit-job",
    )
    assert batch_explicit.details["job_id"] == "explicit-job"
    assert batch_explicit.source["job"] == "explicit-job"


def test_event_payload_json_encodable_with_metadata_datetime(
    context_fixture: JobContext,
    account_fixture: Account,
) -> None:
    """Metadata with datetime/type must JSON-encode for httpx (event.details → payload)."""
    dt = datetime(2024, 6, 15, 10, 30, 0, tzinfo=timezone.utc)
    job = Job.new(
        job_context=context_fixture,
        agent_name="test-agent",
        metadata={"scheduled_at": dt, "kind": str},
    )
    job_event = JobStartConfirmationEvent(job=job, account=account_fixture)
    json.dumps(job_event.payload)
    assert job_event.details["metadata"]["scheduled_at"] == dt.isoformat()
    assert job_event.details["metadata"]["kind"] == "str"

    case = Case(
        id=str(uuid4()),
        job_id=context_fixture.job_id,
        account=account_fixture,
        status=EntityStatus.IN_PROGRESS,
        name="n",
        description="d",
        metadata={"at": dt},
    )
    case_event = CaseStartEvent(case=case, account=account_fixture)
    json.dumps(case_event.payload)
    assert case_event.details["metadata"]["at"] == dt.isoformat()
