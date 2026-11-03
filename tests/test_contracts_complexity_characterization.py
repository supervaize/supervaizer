# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""Characterize complex public contract behavior before structural changes."""

import pytest
from pydantic import ValidationError

from supervaizer.contracts import (
    RULE_CHECKPOINT_RESUME_ACTION,
    V2AgentCapabilities,
    V2SetupFieldDefinition,
    build_v2_agent_registration,
)


def test_unknown_field_types_use_string_rules() -> None:
    """Unknown field types retain string validation and reject number rules."""
    field = V2SetupFieldDefinition.model_validate({
        "id": "agent_format",
        "label": "Agent format",
        "type": "agent_specific",
        "validation": {"min_length": 3, "pattern": "^[a-z]+$"},
    })

    assert field.validation is not None
    assert field.validation.min_length == 3
    with pytest.raises(
        ValidationError, match=r"does not accept validation rules \['min'\]"
    ):
        V2SetupFieldDefinition.model_validate({
            "id": "agent_format",
            "label": "Agent format",
            "type": "agent_specific",
            "validation": {"min": 1},
        })


def test_list_fields_reject_nested_list_item_definitions() -> None:
    """List fields allow one level of item definitions only."""
    with pytest.raises(ValidationError, match=r"item fields \['nested'\] cannot"):
        V2SetupFieldDefinition.model_validate({
            "id": "contacts",
            "label": "Contacts",
            "type": "list",
            "item_fields": [
                {
                    "id": "nested",
                    "label": "Nested contacts",
                    "type": "list",
                    "item_fields": [{"id": "email", "label": "Email"}],
                }
            ],
        })


def test_derived_action_collision_keeps_the_first_derived_metadata() -> None:
    """A bare declared id adopts the first generated action's scope and order."""
    registration = build_v2_agent_registration(
        agent_slug="contacts-agent",
        display_name="Contacts agent",
        a2ui_catalog_version="test.0",
        actions=["resource.contacts.list"],
        resources=[
            {
                "id": "contacts",
                "label": "Workspace contacts",
                "scope": "workspace",
                "operations": ["list"],
            },
            {
                "id": "contacts",
                "label": "Mission contacts",
                "scope": "mission",
                "operations": ["list"],
            },
        ],
    )

    assert [
        (action.id, action.mutating, action.scope)
        for action in registration.capabilities.actions
    ] == [("resource.contacts.list", True, "workspace")]


def test_rule_checkpoints_add_the_resume_action() -> None:
    """Checkpoint support supplies its required resume action."""
    capabilities = V2AgentCapabilities.model_validate({
        "rule_checkpoints": {"phases": ["before"]},
    })

    assert [action.id for action in capabilities.actions] == [
        RULE_CHECKPOINT_RESUME_ACTION
    ]
    assert capabilities.actions[0].mutating is True
    assert capabilities.actions[0].scope == "job"
