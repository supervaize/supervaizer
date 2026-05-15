# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""Tests for versioned Studio controller contracts."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from supervaizer.contracts import (
    API_VERSION,
    AgentMethodsContract,
    ControllerEndpoint,
    ControllerContract,
    ServerRegistrationContract,
    SupervaizerV2AgentRegistrationContract,
    V2ActionRequest,
    V2ActionResult,
    V2AwaitingState,
    V2JobStateSnapshot,
    V2JobSyncResult,
    V2ReplaySafetyMetadata,
    V2ResourceFieldDefinition,
    V2SurfaceRequest,
    V2SurfaceResult,
    build_data_resource_context_headers,
    controller_contract_info,
    resolve_controller_endpoint,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "supervaizer_v2"


def load_v2_fixture(name: str) -> dict:
    with (FIXTURE_DIR / name).open() as fixture_file:
        return json.load(fixture_file)


def test_controller_contract_endpoints_are_api_prefixed() -> None:
    info = controller_contract_info()

    assert API_VERSION == "v1"
    assert info["controller_contract_version"] == "1.0"
    assert info["api_base_path"] == "/api"
    assert (
        info["endpoints"]["POST_AGENT_JOB_START"]
        == "/api/supervaizer/agents/{agent_slug}/jobs"
    )
    assert (
        info["endpoints"]["POST_AGENT_STATUS"]
        == "/api/supervaizer/agents/{agent_slug}/status"
    )
    assert (
        info["endpoints"]["DATA_RESOURCE"]
        == "/api/agents/{agent_slug}/data/{resource_name}/"
    )
    assert (
        info["endpoints"]["POST_CONTROLLER_REGISTRATION_REFRESH"]
        == "/api/supervaizer/registration/refresh"
    )
    assert "POST_AGENT_JOB_START_DYNAMIC_CHOICES" not in info["endpoints"]


def test_contract_models_export_json_schema() -> None:
    controller_schema = ControllerContract.model_json_schema()
    server_schema = ServerRegistrationContract.model_json_schema()

    assert controller_schema["properties"]["endpoints"]["type"] == "object"
    assert server_schema["properties"]["agents"]["type"] == "array"
    agent_schema = server_schema["$defs"]["AgentRegistrationContract"]
    assert "release_notes_url" in agent_schema["properties"]


def test_contract_module_import_does_not_load_controller_runtime() -> None:
    sys.modules.pop("supervaizer.server", None)
    sys.modules.pop("supervaizer.routes", None)
    importlib.import_module("supervaizer.contracts")

    assert "supervaizer.server" not in sys.modules
    assert "supervaizer.routes" not in sys.modules


def test_version_module_is_package_version_only() -> None:
    version_info = importlib.import_module("supervaizer.__version__")

    assert version_info.__version__ == version_info.VERSION
    assert not hasattr(version_info, "API_VERSION")
    assert not hasattr(version_info, "TELEMETRY_VERSION")


def test_agent_method_contract_exports_timeout_metadata() -> None:
    server_schema = ServerRegistrationContract.model_json_schema()
    method_schema = server_schema["$defs"]["AgentMethodContract"]

    assert method_schema["properties"]["is_async"]["default"] is False
    assert method_schema["properties"]["timeout"]["default"] == 600


def test_agent_methods_contract_rejects_job_poll() -> None:
    with pytest.raises(ValidationError, match="job_poll was removed"):
        AgentMethodsContract.model_validate({
            "job_start": {"name": "start", "method": "agent.start"},
            "job_poll": {"name": "poll", "method": "agent.poll"},
        })


def test_resolve_controller_endpoint() -> None:
    contract = ControllerContract()

    assert (
        resolve_controller_endpoint(
            contract,
            ControllerEndpoint.POST_AGENT_JOB_START,
            agent_slug="agent-interviewer",
        )
        == "/api/supervaizer/agents/agent-interviewer/jobs"
    )
    assert (
        resolve_controller_endpoint(
            contract,
            ControllerEndpoint.POST_AGENT_STATUS,
            agent_slug="agent-interviewer",
        )
        == "/api/supervaizer/agents/agent-interviewer/status"
    )
    assert (
        resolve_controller_endpoint(
            contract.model_dump(mode="json"),
            "DATA_RESOURCE_ITEM",
            agent_slug="agent-interviewer",
            resource_name="contacts",
            item_id="c1",
        )
        == "/api/agents/agent-interviewer/data/contacts/c1"
    )


def test_resolve_controller_endpoint_rejects_unknown_endpoint() -> None:
    contract = ControllerContract()

    try:
        resolve_controller_endpoint(contract, "UNKNOWN")
    except KeyError as exc:
        assert "UNKNOWN" in str(exc)
    else:
        raise AssertionError("Expected unknown endpoint to raise KeyError")


def test_data_resource_context_headers() -> None:
    headers = build_data_resource_context_headers(
        workspace_id="1",
        workspace_slug="team-slug",
        mission_id="mission-1",
        request_id="request-1",
    )

    assert headers == {
        "X-Supervaize-Workspace-Id": "1",
        "X-Supervaize-Workspace-Slug": "team-slug",
        "X-Supervaize-Mission-Id": "mission-1",
        "X-Supervaize-Request-Id": "request-1",
    }


def test_v2_agent_interviewer_registration_fixture() -> None:
    fixture = load_v2_fixture("agent_interviewer_mvp.json")

    registration = SupervaizerV2AgentRegistrationContract.model_validate(
        fixture["registration"]
    )

    assert registration.supervaizer_contract_version == 2
    assert registration.versions.a2ui_version == "v0.8"
    assert registration.versions.a2a_version == "0.2.6"
    assert registration.a2a.transport.json_rpc is True
    assert registration.a2a.transport.sse is True
    assert registration.a2a.transport.push_notifications is False
    assert registration.job_policy.sync is not None
    assert registration.job_policy.sync.action == "job.sync"
    assert "job.start" in registration.capabilities.surfaces
    assert "mission.agent.surface.contact_import" in registration.capabilities.surfaces
    assert "mission.agent.surface.prompt_editor" in registration.capabilities.surfaces
    assert "campaigns.sync" in registration.capabilities.actions
    assert "resource.contacts.import" in registration.capabilities.actions
    assert any(
        lane.id == "work" and lane.default
        for lane in registration.capabilities.case_lanes
    )
    assert {resource.id for resource in registration.resources} >= {
        "campaigns",
        "contacts",
        "prompts",
    }
    campaigns = next(
        resource for resource in registration.resources if resource.id == "campaigns"
    )
    assert [field.id for field in campaigns.fields] == ["name"]
    assert campaigns.fields[0].required is True


def test_v2_resource_field_options_source_is_typed() -> None:
    field = V2ResourceFieldDefinition.model_validate({
        "id": "contact_id",
        "label": "Contact",
        "type": "resource_ref",
        "required": True,
        "options_source": {
            "type": "resource",
            "resource": "contacts",
            "value_field": "id",
            "label_field": "email",
        },
    })

    assert field.options_source is not None
    assert field.options_source.resource == "contacts"
    assert field.options_source.value_field == "id"
    assert field.options_source.label_field == "email"


def test_v2_awaiting_state_declares_typed_form_fields() -> None:
    awaiting = V2AwaitingState.model_validate({
        "reason": "Review campaign setup",
        "surface": "case.step.awaiting",
        "action": "step.awaiting.submit",
        "fields": [
            {
                "id": "approve_scenario",
                "label": "Approve scenario",
                "type": "boolean",
                "required": True,
            }
        ],
    })

    assert awaiting.fields[0].id == "approve_scenario"
    assert awaiting.fields[0].type == "boolean"
    assert awaiting.fields[0].required is True


def test_v2_action_request_and_result_fixture() -> None:
    fixture = load_v2_fixture("agent_interviewer_mvp.json")

    request = V2ActionRequest.model_validate(fixture["action_request"])
    result = V2ActionResult.model_validate(fixture["action_result"])

    assert request.action == "job.start"
    assert request.idempotency_key == "idem_start_campaign_123"
    assert request.draft_session_id == "draft_123"
    assert result.status == "ok"
    assert [effect.type for effect in result.effects] == [
        "job.started",
        "case.created",
    ]


def test_v2_surface_request_and_result_models() -> None:
    request = V2SurfaceRequest.model_validate({
        "request_id": "surface-request-1",
        "actor": {"user_id": "user-1"},
        "workspace": {"id": "workspace-1", "slug": "workspace"},
        "mission_id": "mission-1",
        "agent_slug": "agent-interviewer",
        "surface": "job.start",
        "draft_session_id": "draft-1",
        "input": {"campaign_id": "campaign-1"},
    })
    result = V2SurfaceResult.model_validate({
        "surface": "job.start",
        "a2ui_version": "v0.8",
        "document": {"type": "Form", "submit": {"action": "job.start"}},
    })

    assert request.surface == "job.start"
    assert request.draft_session_id == "draft-1"
    assert result.a2ui_version == "v0.8"
    assert result.document["submit"] == {"action": "job.start"}


def test_v2_job_state_snapshot_fixture() -> None:
    fixture = load_v2_fixture("agent_interviewer_mvp.json")

    snapshot = V2JobStateSnapshot.model_validate(fixture["job_state"])
    step = snapshot.cases[0].steps[0]

    assert snapshot.job.source.type == "fresh_start"
    assert snapshot.cases[0].lane == "work"
    assert step.activity == "operation"
    assert step.status == "awaiting"
    assert step.awaiting is not None
    assert step.awaiting.reason == "human_input"
    assert {artifact.type for artifact in step.outputs} == {
        "agent_interviewer.transcript",
        "agent_interviewer.synthesis",
    }


def test_v2_job_sync_result_is_convergent_not_strictly_idempotent() -> None:
    fixture = load_v2_fixture("agent_interviewer_mvp.json")

    sync_result = V2JobSyncResult.model_validate(fixture["sync_result"])
    replay_safety = V2ReplaySafetyMetadata.model_validate(fixture["replay_safety"])

    assert sync_result.status == "ok"
    assert sync_result.external_version == "campaign_123:rev_42"
    assert sync_result.sync_cursor == "rev_42"
    assert sync_result.job_state is not None
    assert (
        sync_result.job_state.cases[0].steps[0].outputs[0].type
        == "agent_interviewer.transcript"
    )
    assert replay_safety.convergent is True
    assert replay_safety.strictly_idempotent_response is False


def test_v2_contract_models_are_public_sdk_exports() -> None:
    import supervaizer

    assert supervaizer.SUPERVAIZER_V2_CONTRACT_VERSION == 2
    assert (
        supervaizer.SupervaizerV2AgentRegistrationContract
        is SupervaizerV2AgentRegistrationContract
    )
    assert supervaizer.V2ActionRequest is V2ActionRequest
    assert supervaizer.V2JobStateSnapshot is V2JobStateSnapshot
    assert supervaizer.V2AwaitingFieldDefinition.__name__ == (
        "V2AwaitingFieldDefinition"
    )
    assert supervaizer.V2ResourceFieldDefinition.__name__ == (
        "V2ResourceFieldDefinition"
    )
    assert supervaizer.V2ResourceFieldOptionsSource.__name__ == (
        "V2ResourceFieldOptionsSource"
    )
    assert supervaizer.V2SurfaceRequest is V2SurfaceRequest
    assert supervaizer.V2SurfaceResult is V2SurfaceResult
