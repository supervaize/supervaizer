# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""Data Resource model for exposing agent-owned CRUD endpoints to Studio.

Agents declare DataResource objects on their Agent instance. The SDK
auto-generates FastAPI CRUD routes for each declared resource, secured
with the same API key as all other agent routes.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Callable

from pydantic import Field, model_validator

from supervaizer.common import SvBaseModel

# Used for URL path segments (/data/{name}/) and OpenAPI operation_id fragments.
_DATA_RESOURCE_NAME_PATTERN = r"^[a-z0-9][a-z0-9_-]*$"


class FieldType(StrEnum):
    """Allowed field types for DataResourceField."""

    STRING = "string"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"
    TEXT = "text"
    EMAIL = "email"
    URL = "url"


class Editable(StrEnum):
    """Controls when Studio may edit a field."""

    ALWAYS = "always"  # Editable on create and update forms
    CREATE_ONLY = "create_only"  # Set on create; shown read-only on edit
    NEVER = "never"  # Agent-controlled; never shown in a form input


class DataResourceField(SvBaseModel):
    """Describes a single field in a DataResource for Studio rendering."""

    name: str = Field(description="Column/attribute name")
    field_type: FieldType = Field(
        default=FieldType.STRING,
        description="One of: string, integer, boolean, date, datetime, text, email, url",
    )
    label: str | None = Field(
        default=None, description="Human-readable label; defaults to name.title()"
    )
    required: bool = Field(default=False, description="Required on create form")
    editable: Editable = Field(default=Editable.ALWAYS)
    visible_on: list[str] = Field(
        default_factory=lambda: ["list", "detail", "create", "edit"],
        description="Views that render this field: list, detail, create, edit",
    )
    description: str | None = Field(
        default=None, description="Help text shown in Studio"
    )
    related_resource: str | None = Field(
        default=None,
        description="Name of another DataResource this field FK-references",
    )

    @property
    def display_label(self) -> str:
        return self.label or self.name.replace("_", " ").title()


class DataResource(SvBaseModel):
    """Declares a named data resource the agent exposes for Studio CRUD access.

    The agent provides callback functions for each operation. The SDK generates
    the corresponding FastAPI routes automatically.

    Example::

        contacts_resource = DataResource(
            name="contacts",
            display_name="Contacts",
            fields=[
                DataResourceField(name="id", editable=Editable.NEVER, visible_on=["list", "detail"]),
                DataResourceField(name="email", field_type=FieldType.EMAIL, required=True),
            ],
            on_list=lambda: repo.list_all(),
            on_get=lambda item_id: repo.get(item_id),
            on_create=lambda data: repo.create(data),
            on_update=lambda item_id, data: repo.update(item_id, data),
            on_delete=lambda item_id: repo.delete(item_id),
        )
    """

    model_config = {"arbitrary_types_allowed": True}

    name: str = Field(
        description=(
            "URL-safe resource identifier, e.g. 'contacts'. "
            "Lowercase letters, digits, underscores, and hyphens only; "
            "must start with a letter or digit."
        ),
        pattern=_DATA_RESOURCE_NAME_PATTERN,
    )
    display_name: str = Field(default="")
    description: str = Field(default="")
    fields: list[DataResourceField] = Field(default_factory=list)
    read_only: bool = Field(default=False)
    importable: bool = Field(default=False, description="Enables CSV bulk import route")
    # Callbacks — excluded from model serialization
    on_list: Callable[[], list[dict[str, Any]]] | None = Field(
        default=None, exclude=True
    )
    on_get: Callable[[str], dict[str, Any] | None] | None = Field(
        default=None, exclude=True
    )
    on_create: Callable[[dict[str, Any]], dict[str, Any]] | None = Field(
        default=None, exclude=True
    )
    on_update: Callable[[str, dict[str, Any]], dict[str, Any] | None] | None = Field(
        default=None, exclude=True
    )
    on_delete: Callable[[str], bool] | None = Field(default=None, exclude=True)
    on_import: Callable[[list[dict[str, Any]]], dict[str, Any]] | None = Field(
        default=None, exclude=True
    )

    @model_validator(mode="after")
    def check_callbacks(self) -> "DataResource":
        """Validate required callbacks.

        on_list is always required.
        on_create is required for writable resources (read_only=False).
        on_import is required when importable=True.

        on_get, on_update, and on_delete are optional — their presence is
        reflected in the operations dict. A writable resource may support
        create-only (no update/delete).
        """
        if self.on_list is None:
            raise ValueError(f"DataResource '{self.name}' must define on_list")
        if not self.read_only and self.on_create is None:
            raise ValueError(
                f"Writable DataResource '{self.name}' must define on_create"
            )
        if self.importable and self.on_import is None:
            raise ValueError(
                f"Importable DataResource '{self.name}' must define on_import"
            )
        return self

    @property
    def operations(self) -> dict[str, bool]:
        return {
            "list": self.on_list is not None,
            "get": self.on_get is not None,
            "create": self.on_create is not None and not self.read_only,
            "update": self.on_update is not None and not self.read_only,
            "delete": self.on_delete is not None and not self.read_only,
            "import": self.importable and self.on_import is not None,
        }

    @property
    def display_name_resolved(self) -> str:
        return self.display_name or self.name.replace("_", " ").title()

    @property
    def registration_info(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "display_name": self.display_name_resolved,
            "description": self.description,
            "fields": [
                {**f.model_dump(), "display_label": f.display_label}
                for f in self.fields
            ],
            "read_only": self.read_only,
            "importable": self.importable,
            "operations": self.operations,
        }
