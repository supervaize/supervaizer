# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""Characterize public AgentMethod field-model behavior before refactoring."""

from typing import Any, Protocol, cast

import pytest
from pydantic import ValidationError

from supervaizer.agent import AgentMethod, AgentMethodField, FieldTypeEnum


class DynamicFieldsModel(Protocol):
    def to_dict(self) -> dict[str, Any]: ...


def _method(fields: list[AgentMethodField]) -> AgentMethod:
    return AgentMethod(name="start", method="control.start", fields=fields)


def test_validation_aggregates_missing_unknown_and_type_errors_in_input_order() -> None:
    method = _method([
        AgentMethodField(name="title", type=str, required=True),
        AgentMethodField(name="count", type=int, required=True),
        AgentMethodField(name="enabled", type=bool, required=False),
    ])

    result = method.validate_method_fields({
        "title": 7,
        "unknown": "value",
        "enabled": None,
    })

    assert result == {
        "valid": False,
        "message": "Method field validation failed",
        "errors": [
            "Required field 'count' is missing",
            "Field 'title' must be a string, got int",
            "Unknown field 'unknown'",
        ],
        "invalid_fields": {
            "count": "Required field 'count' is missing",
            "title": "Field 'title' must be a string, got int",
            "unknown": "Unknown field 'unknown'",
        },
    }


def test_dynamic_annotations_keep_optional_fields_required_without_input() -> None:
    method = _method([
        AgentMethodField(name="title", type=str, required=True),
        AgentMethodField(name="nickname", type=str, default="guest", required=False),
        AgentMethodField(
            name="mode",
            type=str,
            field_type=FieldTypeEnum.CHOICE,
            choices=["safe", "fast"],
            default="safe",
            required=False,
        ),
    ])
    fields_model = method.fields_annotations

    assert fields_model.__annotations__["nickname"] == str | None
    assert fields_model.__annotations__["mode"] == str | None
    assert fields_model.model_fields["nickname"].is_required() is True
    assert fields_model.model_fields["mode"].is_required() is True

    with pytest.raises(ValidationError) as error:
        fields_model(title="A title")

    assert {item["loc"] for item in error.value.errors()} == {("nickname",), ("mode",)}


def test_dynamic_annotations_normalize_containers_and_accept_unknown_types() -> None:
    method = _method([
        AgentMethodField(name="records", type=dict[str, int], required=True),
        AgentMethodField(name="tags", type=list[str], required=True),
        AgentMethodField(name="opaque", type=tuple[str, ...], required=True),
    ])
    fields_model = method.fields_annotations
    opaque_value = object()

    instance = cast(
        DynamicFieldsModel,
        fields_model(records={"one": 1}, tags=["one"], opaque=opaque_value),
    )

    assert fields_model.__annotations__["records"] is dict
    assert fields_model.__annotations__["tags"] is list
    assert fields_model.__annotations__["opaque"] is Any
    assert instance.to_dict() == {
        "records": {"one": 1},
        "tags": ["one"],
        "opaque": opaque_value,
    }


def test_registration_info_serializes_field_type_and_preserves_choice_metadata() -> (
    None
):
    method = _method([
        AgentMethodField(
            name="modes",
            type=list[str],
            field_type=FieldTypeEnum.MULTICHOICE,
            choices=["safe", "fast"],
            default=["safe"],
            required=False,
        )
    ])

    field = method.registration_info["fields"][0]

    assert field["type"] == "list"
    assert field["choices"] == ["safe", "fast"]
    assert field["default"] == ["safe"]
    assert field["required"] is False
