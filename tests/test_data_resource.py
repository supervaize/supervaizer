# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

import pytest
from pydantic import ValidationError

from supervaizer.data_resource import (
    DataResource,
    DataResourceField,
    Editable,
    FieldType,
)


def test_field_defaults() -> None:
    f = DataResourceField(name="email")
    assert f.field_type == FieldType.STRING
    assert f.editable == Editable.ALWAYS
    assert f.visible_on == ["list", "detail", "create", "edit"]
    assert f.required is False


def test_field_display_label_defaults_to_name_title() -> None:
    f = DataResourceField(name="first_name")
    assert f.display_label == "First Name"


def test_field_display_label_custom() -> None:
    f = DataResourceField(name="first_name", label="Given Name")
    assert f.display_label == "Given Name"


@pytest.mark.parametrize(
    "bad_name",
    [
        "",
        "contacts/admin",
        "{id}",
        "bad name",
        "CamelCase",
    ],
)
def test_data_resource_name_must_be_url_safe(bad_name: str) -> None:
    with pytest.raises(ValidationError):
        DataResource(name=bad_name, fields=[], on_list=lambda: [])


def test_data_resource_requires_on_list() -> None:
    with pytest.raises(ValueError, match="must define on_list"):
        DataResource(name="contacts", fields=[])


def test_data_resource_writable_requires_on_create() -> None:
    with pytest.raises(ValueError, match="must define on_create"):
        DataResource(name="contacts", fields=[], on_list=lambda: [], read_only=False)


def test_data_resource_read_only_no_on_create_required() -> None:
    dr = DataResource(name="prompts", fields=[], on_list=lambda: [], read_only=True)
    assert dr.operations["create"] is False
    assert dr.operations["update"] is False
    assert dr.operations["delete"] is False
    assert dr.operations["list"] is True


def test_data_resource_importable_requires_on_import() -> None:
    with pytest.raises(ValueError, match="must define on_import"):
        DataResource(
            name="contacts",
            fields=[],
            on_list=lambda: [],
            on_create=lambda d: {**d, "id": "1"},
            importable=True,
        )


def test_data_resource_operations_full() -> None:
    dr = DataResource(
        name="contacts",
        fields=[],
        on_list=lambda: [],
        on_get=lambda item_id: {"id": item_id},
        on_create=lambda d: {**d, "id": "new"},
        on_update=lambda item_id, d: {**d, "id": item_id},
        on_delete=lambda item_id: True,
    )
    assert dr.operations == {
        "list": True,
        "get": True,
        "create": True,
        "update": True,
        "delete": True,
        "import": False,
    }


def test_data_resource_registration_info() -> None:
    dr = DataResource(
        name="contacts",
        display_name="Contacts",
        fields=[
            DataResourceField(
                name="id", editable=Editable.NEVER, visible_on=["list", "detail"]
            ),
            DataResourceField(name="email", field_type=FieldType.EMAIL, required=True),
        ],
        on_list=lambda: [],
        on_create=lambda d: {**d, "id": "1"},
    )
    info = dr.registration_info
    assert info["name"] == "contacts"
    assert info["display_name"] == "Contacts"
    assert len(info["fields"]) == 2
    assert info["fields"][0]["name"] == "id"
    assert info["fields"][0]["editable"] == "never"
    assert info["fields"][1]["required"] is True
    assert info["operations"]["create"] is True
    assert info["operations"]["import"] is False


def test_data_resource_display_name_derived_from_name() -> None:
    dr = DataResource(
        name="contact_knowledge", fields=[], on_list=lambda: [], read_only=True
    )
    assert dr.display_name_resolved == "Contact Knowledge"


def test_data_resource_callbacks_excluded_from_serialization() -> None:
    dr = DataResource(name="prompts", fields=[], on_list=lambda: [], read_only=True)
    dumped = dr.model_dump()
    assert "on_list" not in dumped
    assert "on_create" not in dumped
