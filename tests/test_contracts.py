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
    AGENT_REFRESH_ACTION,
    API_VERSION,
    AgentMethodsContract,
    ControllerEndpoint,
    ControllerContract,
    EventType,
    ServerRegistrationContract,
    SupervaizerV2AgentRegistrationContract,
    V2A2UIResourceImportDocument,
    V2ActionRequest,
    V2ActionResult,
    V2AgentMethod,
    V2AgentMethods,
    V2AwaitingState,
    V2CaseSnapshot,
    V2DashboardWidgetDataRef,
    V2DashboardWidgetDefinition,
    V2DashboardWidgetVisualization,
    V2Effect,
    V2JobStateSnapshot,
    V2JobSyncResult,
    V2ReplaySafetyMetadata,
    V2ResourceFieldDefinition,
    V2SurfaceRequest,
    V2SurfaceResult,
    V2VerifiedWorkspaceContext,
    V2WorkspaceAuthorizationSettings,
    V2WorkspaceBindingDefinition,
    build_data_resource_context_headers,
    build_v2_agent_registration,
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


def test_event_type_agent_anomaly_members_are_not_aliases() -> None:
    assert EventType.AGENT_SEND_ANOMALY is not EventType.AGENT_ANOMALY
    assert EventType.AGENT_SEND_ANOMALY.value != EventType.AGENT_ANOMALY.value


def test_v2_effect_has_typed_common_fields() -> None:
    effect = V2Effect(
        type="resource.imported",
        job_id="job-1",
        resource="campaign_contacts",
        count=1,
        items=[{"email": "ada@example.com"}],
        errors=[],
        gaps=[],
        summary={"enrollments_created": 1},
        case={"lane": "setup", "title": "User enrollment"},
    )

    assert effect.job_id == "job-1"
    assert effect.resource == "campaign_contacts"
    assert effect.count == 1
    assert effect.model_dump(mode="json", exclude_none=True) == {
        "type": "resource.imported",
        "job_id": "job-1",
        "resource": "campaign_contacts",
        "count": 1,
        "items": [{"email": "ada@example.com"}],
        "errors": [],
        "gaps": [],
        "summary": {"enrollments_created": 1},
        "case": {"lane": "setup", "title": "User enrollment"},
    }


def test_v2_case_snapshot_accepts_public_metadata() -> None:
    case = V2CaseSnapshot(
        id="enrollment-1",
        metadata={"interview_url": "https://app.example.com/interview/tok-abc"},
    )

    assert case.metadata == {
        "interview_url": "https://app.example.com/interview/tok-abc"
    }


def test_v2_action_result_validates_job_state() -> None:
    with pytest.raises(ValidationError):
        V2ActionResult.model_validate({
            "status": "ok",
            "job_state": {"job": {"id": "missing-required-fields"}},
        })


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
        agent_slug="agent-interviewer",
        request_id="request-1",
    )

    assert headers == {
        "X-Supervaize-Workspace-Id": "1",
        "X-Supervaize-Workspace-Slug": "team-slug",
        "X-Supervaize-Mission-Id": "mission-1",
        "X-Supervaize-Agent-Slug": "agent-interviewer",
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
    assert "mission.agent.overview" in registration.capabilities.surfaces
    assert (
        "mission.agent.resource.campaign_contacts" in registration.capabilities.surfaces
    )
    assert "job.start" in registration.capabilities.surfaces
    assert "mission.agent.surface.contact_import" in registration.capabilities.surfaces
    assert "mission.agent.surface.prompt_editor" in registration.capabilities.surfaces
    assert (
        "mission.agent.surface.scenario_builder" in registration.capabilities.surfaces
    )
    assert AGENT_REFRESH_ACTION in registration.capabilities.actions
    assert "resource.campaign_contacts.create" in registration.capabilities.actions
    assert "resource.campaign_contacts.delete" in registration.capabilities.actions
    assert "resource.contacts.import" in registration.capabilities.actions
    assert "resource.scenarios.update" in registration.capabilities.actions
    assert any(
        lane.id == "work" and lane.default
        for lane in registration.capabilities.case_lanes
    )
    assert {resource.id for resource in registration.resources} >= {
        "campaigns",
        "contacts",
        "campaign_contacts",
        "prompts",
        "scenarios",
    }
    campaign_contacts = next(
        resource
        for resource in registration.resources
        if resource.id == "campaign_contacts"
    )
    assert set(campaign_contacts.operations) >= {"list", "create", "delete"}
    assert [field.id for field in campaign_contacts.fields] == [
        "campaign_id",
        "contact_id",
    ]
    assert campaign_contacts.fields[0].options_source is not None
    assert campaign_contacts.fields[0].options_source.resource == "campaigns"
    assert campaign_contacts.fields[1].options_source is not None
    assert campaign_contacts.fields[1].options_source.resource == "contacts"
    campaigns = next(
        resource for resource in registration.resources if resource.id == "campaigns"
    )
    assert [field.id for field in campaigns.fields] == ["name"]
    assert campaigns.fields[0].required is True
    contacts = next(
        resource for resource in registration.resources if resource.id == "contacts"
    )
    assert len(contacts.mounted_views) == 1
    assert contacts.mounted_views[0].view == "import"
    assert contacts.mounted_views[0].surface == "mission.agent.surface.contact_import"


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


def test_build_v2_agent_registration_derives_capabilities() -> None:
    registration = build_v2_agent_registration(
        agent_id="hello",
        agent_slug="hello-world",
        display_name="Hello World",
        agent_card_url="/.well-known/agents/v1/hello-world_agent.json",
        controller_url="/a2a",
        a2ui_catalog_version="supervaizer-v2-local.0",
        surfaces=["job.start", "case.step.awaiting", "job.start"],
        actions=["job.start", "step.awaiting.submit"],
        resources=[
            {
                "id": "contacts",
                "label": "Contacts",
                "auto_surface": True,
                "operations": ["list", "create"],
                "fields": [{"id": "email", "label": "Email", "required": True}],
            }
        ],
        datasets=[
            {
                "id": "campaign_progress",
                "label": "Campaign Progress",
                "auto_surface": True,
                "display": {"columns": ["campaign_name", "completion_pct"]},
            }
        ],
        dashboards=[
            {
                "id": "mission_overview",
                "label": "Mission Overview",
                "widgets": [
                    {
                        "id": "completion_chart",
                        "title": "Completion",
                        "data": {
                            "mode": "ref",
                            "datasetId": "campaign_progress",
                        },
                        "visualization": {
                            "type": "vega-lite",
                            "spec": {
                                "mark": "bar",
                                "encoding": {
                                    "x": {
                                        "field": "campaign_name",
                                        "type": "nominal",
                                    },
                                    "y": {
                                        "field": "completion_pct",
                                        "type": "quantitative",
                                    },
                                },
                            },
                        },
                    }
                ],
            }
        ],
        case_lanes=[{"id": "work", "label": "Work", "default": True}],
        job_policy={"sync": {"action": "job.sync"}},
        workspace_binding={
            "required": True,
            "modes": ["bind_existing", "create_and_bind"],
            "reference_label": "Agent workspace reference",
            "create": {
                "fields": [
                    {
                        "id": "display_name",
                        "label": "Display name",
                        "type": "text",
                        "required": True,
                    }
                ]
            },
        },
    )

    assert registration.versions.a2ui_version == "v0.8"
    assert registration.versions.a2a_version == "0.2.6"
    assert registration.a2a.controller_url == "/a2a"
    assert registration.a2a.transport.push_notifications is False
    assert registration.capabilities.surfaces == [
        "job.start",
        "case.step.awaiting",
        "mission.agent.resource.contacts",
        "mission.agent.dataset.campaign_progress",
        "mission.analytics",
        "workspace_binding.create",
    ]
    assert registration.capabilities.actions == [
        "job.start",
        "step.awaiting.submit",
        "resource.contacts.list",
        "resource.contacts.create",
        "dataset.campaign_progress.query",
        "job.sync",
        "workspace_binding.options",
        "workspace_binding.create",
    ]
    assert registration.workspace_binding is not None
    assert registration.workspace_binding.existing is not None
    assert registration.workspace_binding.existing.action == "workspace_binding.options"
    assert registration.workspace_binding.create is not None
    assert registration.workspace_binding.create.surface == "workspace_binding.create"
    assert registration.workspace_binding.create.action == "workspace_binding.create"
    assert registration.resources[0].scope == "workspace"
    assert registration.resources[0].requires_context == ["workspace.id"]
    assert registration.resources[0].fields[0].id == "email"
    assert registration.datasets[0].display is not None
    assert registration.datasets[0].display.columns == [
        "campaign_name",
        "completion_pct",
    ]
    widget = registration.dashboards[0].widgets[0]
    assert widget.visualization.type == "vega-lite"
    assert widget.data is not None
    assert widget.data.mode == "ref"
    assert widget.data.datasetId == "campaign_progress"
    assert widget.visualization.spec == {
        "mark": "bar",
        "encoding": {
            "x": {"field": "campaign_name", "type": "nominal"},
            "y": {"field": "completion_pct", "type": "quantitative"},
        },
    }
    assert registration.capabilities.case_lanes[0].default is True


def test_build_v2_agent_registration_derives_agent_method_actions() -> None:
    registration = build_v2_agent_registration(
        agent_id="hello",
        agent_slug="hello-world",
        display_name="Hello World",
        agent_card_url="/.well-known/agents/v1/hello-world_agent.json",
        controller_url="/a2a",
        a2ui_catalog_version="supervaizer-v2-local.0",
        agent_methods=V2AgentMethods(
            refresh=V2AgentMethod(method="hello_agent.refresh"),
            custom={
                "reindex": V2AgentMethod(method="hello_agent.reindex"),
                "dry-run": V2AgentMethod(method="hello_agent.dry_run"),
            },
        ),
    )

    assert registration.capabilities.actions == [
        AGENT_REFRESH_ACTION,
        "agent.custom.reindex",
        "agent.custom.dry-run",
    ]


def test_v2_workspace_binding_required_requires_mode() -> None:
    with pytest.raises(ValidationError, match="at least one mode"):
        V2WorkspaceBindingDefinition(required=True)


def test_v2_dashboard_widget_validates_data_ref_target() -> None:
    with pytest.raises(ValidationError, match="datasetId"):
        V2DashboardWidgetDataRef(mode="ref")


def test_v2_dashboard_widget_requires_vega_lite_spec() -> None:
    with pytest.raises(ValidationError, match="visualization.spec"):
        V2DashboardWidgetDefinition(
            id="missing-spec",
            title="Missing Spec",
            visualization={"type": "vega-lite"},
            data={"mode": "ref", "datasetId": "metrics"},
        )


def test_v2_dashboard_widget_rejects_unknown_visualization() -> None:
    with pytest.raises(ValidationError):
        V2DashboardWidgetVisualization(type="agent-specific-chart")


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


def test_v2_action_result_validates_replay_safety() -> None:
    with pytest.raises(ValidationError):
        V2ActionResult.model_validate({
            "status": "ok",
            "replay_safety": {"dedupe_keys": ["job-1"], "convergent": "sometimes"},
        })


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


def test_v2_surface_result_accepts_document_review_a2ui_document() -> None:
    result = V2SurfaceResult.model_validate({
        "surface": "case.step.awaiting",
        "a2ui_version": "v0.8",
        "document": {
            "type": "DocumentReview",
            "document": {
                "title": "Review",
                "field": "review_text",
                "language": "markdown",
                "value": "# Draft\n\nReview this content.",
            },
            "submit": {
                "action": "step.awaiting.submit",
                "label": "Approve",
            },
            "fields": [
                {
                    "id": "review_text",
                    "label": "Review text",
                    "type": "text",
                    "multiline": True,
                    "required": True,
                },
                {
                    "id": "approved",
                    "label": "Approved",
                    "type": "boolean",
                    "required": True,
                },
            ],
        },
    })

    assert result.document["type"] == "DocumentReview"
    assert result.document["submit"]["action"] == "step.awaiting.submit"


def test_v2_resource_import_document_declares_columns_and_submit_action() -> None:
    document = V2A2UIResourceImportDocument.model_validate({
        "id": "agent.contacts.import",
        "title": "Enroll users",
        "resource": "campaign_contacts",
        "accepted_formats": ["csv", "xlsx"],
        "fields": [
            {
                "id": "campaign_id",
                "label": "Campaign",
                "type": "resource_ref",
                "required": True,
                "options_source": {"type": "resource", "resource": "campaigns"},
            }
        ],
        "columns": [
            {"id": "email", "label": "Email", "required": True},
            {"id": "first_name", "label": "First name"},
        ],
        "submit": {"action": "resource.campaign_contacts.import", "label": "Enroll"},
    })

    assert document.type == "ResourceImport"
    assert document.columns[0].id == "email"
    assert document.submit.action == "resource.campaign_contacts.import"


def test_v2_resource_import_document_requires_csv_columns() -> None:
    with pytest.raises(ValidationError, match="columns"):
        V2A2UIResourceImportDocument.model_validate({
            "id": "agent.contacts.import",
            "title": "Enroll users",
            "resource": "campaign_contacts",
            "accepted_formats": ["csv"],
            "submit": {"action": "resource.campaign_contacts.import"},
        })


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

    assert sync_result.status == "ok"
    assert sync_result.external_version == "campaign_123:rev_42"
    assert sync_result.sync_cursor == "rev_42"
    assert sync_result.job_state is not None
    assert (
        sync_result.job_state.cases[0].steps[0].outputs[0].type
        == "agent_interviewer.transcript"
    )
    assert sync_result.replay_safety is not None
    assert sync_result.replay_safety.convergent is True
    assert sync_result.replay_safety.strictly_idempotent_response is False


def test_v2_contract_models_are_public_sdk_exports() -> None:
    import supervaizer

    assert supervaizer.SUPERVAIZER_V2_CONTRACT_VERSION == 2
    assert (
        supervaizer.SupervaizerV2AgentRegistrationContract
        is SupervaizerV2AgentRegistrationContract
    )
    assert supervaizer.V2A2AController.__name__ == "V2A2AController"
    assert supervaizer.V2A2AExternalInterop.__name__ == "V2A2AExternalInterop"
    assert supervaizer.V2A2ATransport.__name__ == "V2A2ATransport"
    assert supervaizer.V2A2UIResourceImportDocument is V2A2UIResourceImportDocument
    assert supervaizer.V2ActionRequest is V2ActionRequest
    assert supervaizer.V2AgentMethod is V2AgentMethod
    assert supervaizer.V2AgentMethods is V2AgentMethods
    assert supervaizer.V2DashboardDefinition.__name__ == "V2DashboardDefinition"
    assert supervaizer.V2DashboardWidgetDataRef is V2DashboardWidgetDataRef
    assert supervaizer.V2DashboardWidgetDefinition is V2DashboardWidgetDefinition
    assert supervaizer.V2DashboardWidgetVisualization is V2DashboardWidgetVisualization
    assert supervaizer.V2JobStateSnapshot is V2JobStateSnapshot
    assert supervaizer.V2JobSyncPolicy.__name__ == "V2JobSyncPolicy"
    assert supervaizer.V2MountedResourceViewDefinition.__name__ == (
        "V2MountedResourceViewDefinition"
    )
    assert supervaizer.V2ReplaySafetyMetadata is V2ReplaySafetyMetadata
    assert supervaizer.V2AwaitingFieldDefinition.__name__ == (
        "V2AwaitingFieldDefinition"
    )
    assert supervaizer.V2ResourceDisplayDefinition.__name__ == (
        "V2ResourceDisplayDefinition"
    )
    assert supervaizer.V2ResourceFieldDefinition.__name__ == (
        "V2ResourceFieldDefinition"
    )
    assert supervaizer.V2ResourceFieldOptionsSource.__name__ == (
        "V2ResourceFieldOptionsSource"
    )
    assert supervaizer.V2SurfaceRequest is V2SurfaceRequest
    assert supervaizer.V2SurfaceResult is V2SurfaceResult
    assert supervaizer.V2VerifiedWorkspaceContext is V2VerifiedWorkspaceContext
    assert (
        supervaizer.V2WorkspaceAuthorizationSettings is V2WorkspaceAuthorizationSettings
    )
    assert supervaizer.V2WorkspaceBindingDefinition is V2WorkspaceBindingDefinition
    assert supervaizer.build_v2_agent_registration is build_v2_agent_registration
