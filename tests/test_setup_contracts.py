# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""Guided setup contracts: field schema, typed plan, help actions, cost, dry run."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

import supervaizer
from supervaizer.contracts import (
    SupervaizerV2AgentRegistrationContract,
    V2ActionDefinition,
    V2ActionResult,
    V2AwaitingFieldDefinition,
    V2CostEstimate,
    V2FieldDependsOn,
    V2JobSetupPolicy,
    V2ResourceFieldDefinition,
    V2SetupFieldDefinition,
    V2SetupPlan,
    V2SetupStep,
    build_v2_agent_registration,
)

FIELD_MODELS = [
    V2SetupFieldDefinition,
    V2AwaitingFieldDefinition,
    V2ResourceFieldDefinition,
]
ITEM_FIELDS = [{"id": "name", "label": "Name"}, {"id": "note", "label": "Note"}]


def _field(model: type, **overrides: Any) -> Any:
    return model.model_validate({"id": "goal", "label": "Goal", **overrides})


@pytest.mark.parametrize("model", FIELD_MODELS)
def test_field_rejects_bare_string_options(model: type) -> None:
    with pytest.raises(ValidationError, match="bare strings"):
        _field(model, type="select", options=["a", "b"])

    field = _field(model, type="select", options=[{"value": "a", "label": "A"}])
    assert field.options[0].value == "a"


@pytest.mark.parametrize("model", FIELD_MODELS)
@pytest.mark.parametrize(
    ("field_type", "rules"),
    [
        ("string", {"min": 1}),
        ("text", {"max_items": 2}),
        ("integer", {"pattern": "^a"}),
        ("boolean", {"max_length": 2}),
        ("select", {"min_items": 1}),
        ("multi_select", {"min": 1}),
        ("file", {"max_items": 1}),
        ("date", {"min": 0}),
    ],
)
def test_field_rejects_validation_rules_that_do_not_fit_the_type(
    model: type, field_type: str, rules: dict[str, Any]
) -> None:
    with pytest.raises(ValidationError, match="does not accept validation rules"):
        _field(model, type=field_type, validation=rules)


@pytest.mark.parametrize(
    ("field_type", "rules"),
    [
        ("string", {"min_length": 1, "max_length": 5, "pattern": "^a"}),
        ("custom_widget", {"max_length": 5}),
        ("number", {"min": 0, "max": 1.5}),
        ("multi_select", {"min_items": 1, "max_items": 3}),
        ("boolean", {"message": "Tick it"}),
    ],
)
def test_field_accepts_validation_rules_that_fit(
    field_type: str, rules: dict[str, Any]
) -> None:
    field = _field(V2SetupFieldDefinition, type=field_type, validation=rules)

    assert field.model_dump(mode="json")["validation"] == rules


def test_list_field_requires_one_level_of_item_fields() -> None:
    field = _field(
        V2SetupFieldDefinition,
        type="list",
        item_fields=ITEM_FIELDS,
        validation={"max_items": 3},
    )
    assert [item.id for item in field.item_fields or []] == ["name", "note"]

    with pytest.raises(ValidationError, match="requires item_fields"):
        _field(V2SetupFieldDefinition, type="list")
    with pytest.raises(ValidationError, match="is not of type 'list'"):
        _field(V2SetupFieldDefinition, type="string", item_fields=ITEM_FIELDS)
    with pytest.raises(ValidationError, match="cannot be of type 'list'"):
        _field(
            V2SetupFieldDefinition,
            type="list",
            item_fields=[
                {**ITEM_FIELDS[0], "type": "list", "item_fields": ITEM_FIELDS}
            ],
        )


@pytest.mark.parametrize("model", FIELD_MODELS)
def test_list_field_round_trips_with_two_item_fields(model: type) -> None:
    """A list value is `[{item field id: value}, ...]`; the schema carries the ids."""
    expected = {
        **_field(model).model_dump(mode="json"),
        "type": "list",
        "item_fields": [
            {"id": "name", "label": "Name", "type": "string", "required": True},
            {"id": "note", "label": "Note", "type": "text", "required": False},
        ],
    }
    field = _field(
        model,
        type="list",
        item_fields=[
            {"id": "name", "label": "Name", "required": True},
            {"id": "note", "label": "Note", "type": "text"},
        ],
    )

    payload = field.model_dump(mode="json")
    assert payload == expected
    assert model.model_validate(payload).model_dump(mode="json") == payload
    assert field.item_fields is not None
    assert all(isinstance(item, V2SetupFieldDefinition) for item in field.item_fields)


def test_min_rows_requires_multiline() -> None:
    with pytest.raises(ValidationError, match="min_rows without multiline"):
        _field(V2SetupFieldDefinition, type="text", min_rows=3)

    field = _field(V2SetupFieldDefinition, type="text", multiline=True, min_rows=3)
    assert field.model_dump(mode="json")["min_rows"] == 3


def test_depends_on_serializes_with_the_in_key() -> None:
    field = _field(
        V2SetupFieldDefinition,
        depends_on={"field": "mode", "in": ["custom"]},
    )

    assert field.depends_on == V2FieldDependsOn(field="mode", in_=["custom"])
    assert field.model_dump(mode="json")["depends_on"] == {
        "field": "mode",
        "in": ["custom"],
    }


@pytest.mark.parametrize(
    ("model", "expected"),
    [
        (V2SetupFieldDefinition, {"type": "string", "required": False}),
        (V2AwaitingFieldDefinition, {"type": "boolean", "required": False}),
        (
            V2ResourceFieldDefinition,
            {
                "type": "string",
                "required": False,
                "read_only": False,
                "multiline": False,
                "options_source": None,
            },
        ),
    ],
)
def test_field_definitions_omit_unset_optional_keys(
    model: type, expected: dict[str, Any]
) -> None:
    assert _field(model).model_dump(mode="json") == {
        "id": "goal",
        "label": "Goal",
        **expected,
    }


def test_help_action_must_not_mutate() -> None:
    with pytest.raises(ValidationError, match="must declare mutating=False"):
        V2ActionDefinition(id="goal.suggest", kind="help")
    with pytest.raises(ValidationError, match="must declare mutating=False"):
        V2ActionDefinition(id="goal.suggest", kind="help", mutating=True)

    action = V2ActionDefinition(
        id="goal.suggest", kind="help", mutating=False, target_field="goal"
    )
    assert action.model_dump(mode="json") == {
        "id": "goal.suggest",
        "mutating": False,
        "scope": "job",
        "kind": "help",
        "target_field": "goal",
    }


def test_target_field_requires_help_kind() -> None:
    with pytest.raises(ValidationError, match="is not kind='help'"):
        V2ActionDefinition(id="job.start", target_field="goal")


def test_action_definition_omits_default_kind_and_dry_run() -> None:
    assert V2ActionDefinition(id="job.start").model_dump(mode="json") == {
        "id": "job.start",
        "mutating": True,
        "scope": "job",
    }
    assert (
        V2ActionDefinition(id="job.test", dry_run=True).model_dump(mode="json")[
            "dry_run"
        ]
        is True
    )


def test_unknown_cost_rejects_numbers() -> None:
    for override in ({"min": 1.0}, {"max": 2.0}, {"unit": "USD"}):
        with pytest.raises(ValidationError, match="must not set unit, min or max"):
            V2CostEstimate.model_validate({"status": "unknown", **override})

    assert V2CostEstimate(status="unknown").model_dump(mode="json") == {
        "status": "unknown"
    }


def test_estimated_cost_requires_a_non_negative_range() -> None:
    with pytest.raises(ValidationError, match="requires unit, min and max"):
        V2CostEstimate(status="estimated", unit="USD", min=1.0)
    with pytest.raises(ValidationError, match="max must be >= min"):
        V2CostEstimate(status="estimated", unit="USD", min=2.0, max=1.0)
    with pytest.raises(ValidationError):
        V2CostEstimate(status="estimated", unit="USD", min=-1.0, max=1.0)

    cost = V2CostEstimate(
        status="estimated", unit="credits", min=1.0, max=1.0, basis="for 50 runs"
    )
    assert cost.model_dump(mode="json") == {
        "status": "estimated",
        "unit": "credits",
        "min": 1.0,
        "max": 1.0,
        "basis": "for 50 runs",
    }


def _registration(actions: list[Any], help_actions: list[str]) -> Any:
    return build_v2_agent_registration(
        agent_slug="agent-1",
        display_name="Agent 1",
        a2ui_catalog_version="test.0",
        actions=actions,
        job_policy={
            "setup": {
                "plan": V2SetupPlan(
                    steps=[
                        V2SetupStep(id="goal", title="Goal", help_actions=help_actions)
                    ]
                )
            }
        },
    )


def test_registration_rejects_help_actions_not_declared_as_help() -> None:
    with pytest.raises(ValidationError, match="not declared in capabilities.actions"):
        _registration(actions=["job.start"], help_actions=["goal.suggest"])
    with pytest.raises(ValidationError, match="not declared in capabilities.actions"):
        _registration(
            actions=[{"id": "goal.suggest", "mutating": False}],
            help_actions=["goal.suggest"],
        )

    registration = _registration(
        actions=[{"id": "goal.suggest", "kind": "help", "mutating": False}],
        help_actions=["goal.suggest"],
    )
    plan = registration.model_dump(mode="json")["job_policy"]["setup"]["plan"]
    assert plan["steps"][0]["help_actions"] == ["goal.suggest"]


def test_plan_dicts_pass_through_untouched() -> None:
    opaque = {"agent_descriptor": {"template_id": "opaque-id"}, "steps": "n/a"}

    assert V2JobSetupPolicy(plan=opaque).plan == opaque
    assert V2ActionResult(status="ok", setup_plan=opaque).setup_plan == opaque
    assert V2JobSetupPolicy.model_validate_json('{"plan": {"steps": []}}').plan == {
        "steps": []
    }


def test_typed_plan_round_trips_to_the_same_json_shape() -> None:
    plan = V2SetupPlan(
        steps=[
            V2SetupStep(
                id="goal",
                title="Goal",
                fields=[V2SetupFieldDefinition(id="goal", label="Goal", required=True)],
            )
        ],
        cost_estimate=V2CostEstimate(status="unknown"),
    )
    expected = {
        "confirmation_required": True,
        "steps": [
            {
                "id": "goal",
                "title": "Goal",
                "status": "pending",
                "fields": [
                    {"id": "goal", "label": "Goal", "type": "string", "required": True}
                ],
            }
        ],
        "cost_estimate": {"status": "unknown"},
    }

    assert V2JobSetupPolicy(plan=plan).model_dump(mode="json")["plan"] == expected
    result = V2ActionResult(status="ok", setup_plan=plan).model_dump(mode="json")
    assert result["setup_plan"] == expected
    assert V2SetupPlan.model_validate(expected).model_dump(mode="json") == expected
    assert V2ActionResult.model_validate(result).setup_plan == expected


def test_plan_step_ids_must_be_unique() -> None:
    with pytest.raises(ValidationError, match="must be unique"):
        V2SetupPlan(
            steps=[V2SetupStep(id="a", title="A"), V2SetupStep(id="a", title="B")]
        )


def test_action_result_serializes_draft_and_dry_run_only_when_set() -> None:
    assert V2ActionResult(status="ok").model_dump(mode="json") == {
        "status": "ok",
        "effects": [],
        "job_state": None,
        "replay_safety": None,
        "setup_plan": None,
    }

    result = V2ActionResult.model_validate({
        "status": "ok",
        "draft": {
            "field": "goal",
            "value": "Prepare a digest",
            "suggestions": [{"message": "Add a deadline", "severity": "info"}],
        },
        "dry_run": {
            "expires_at": "2026-10-29T10:00:00Z",
            "deletable": True,
            "cost_incurred": {
                "status": "estimated",
                "unit": "tokens",
                "min": 0,
                "max": 1200,
            },
        },
    })
    payload = result.model_dump(mode="json")
    assert payload["draft"] == {
        "field": "goal",
        "value": "Prepare a digest",
        "suggestions": [{"message": "Add a deadline", "severity": "info"}],
    }
    assert payload["dry_run"]["deletable"] is True
    assert payload["dry_run"]["cost_incurred"]["max"] == 1200.0
    assert payload["dry_run"]["expires_at"].startswith("2026-10-29T10:00:00")


def test_guided_setup_models_are_public_sdk_exports() -> None:
    for name in (
        "V2AgentIntroduction",
        "V2SetupFieldDefinition",
        "V2FieldOption",
        "V2FieldDependsOn",
        "V2FieldValidation",
        "V2SetupPlan",
        "V2SetupStep",
        "V2CostEstimate",
        "V2FieldDraft",
        "V2Suggestion",
        "V2DryRunOutcome",
        "assert_confirm_idempotent",
    ):
        assert getattr(supervaizer, name).__name__ == name
    assert isinstance(SupervaizerV2AgentRegistrationContract.model_json_schema(), dict)
