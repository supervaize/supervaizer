# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""AnalyticsResource model for exposing Vega-Lite dashboards to Studio."""

from __future__ import annotations

from typing import Any, Callable, Literal

from pydantic import Field, model_validator

from supervaizer.common import SvBaseModel

_ANALYTICS_RESOURCE_NAME_PATTERN = r"^[a-z0-9][a-z0-9_-]*$"


class AnalyticsResourceContext(SvBaseModel):
    """Studio request context passed to AnalyticsResource callbacks."""

    workspace_id: str | None = None
    workspace_slug: str | None = None
    mission_id: str | None = None
    job_id: str | None = None
    agent_slug: str
    request_id: str | None = None
    filters: dict[str, Any] = Field(default_factory=dict)


class AnalyticsFilter(SvBaseModel):
    """Describes a dashboard filter Studio can render and forward."""

    id: str
    type: Literal["enum", "date_range", "string", "number", "boolean"] = "enum"
    label: str | None = None
    default: Any = None
    options: list[dict[str, Any]] = Field(default_factory=list)


class AnalyticsDataset(SvBaseModel):
    """Describes a dataset served for one or more Vega-Lite dashboards."""

    id: str
    description: str = ""


class AnalyticsResource(SvBaseModel):
    """Declares a named analytics surface exposed to Studio.

    Dashboard manifests use Vega-Lite JSON. Agents may declare static manifests,
    dynamic callbacks, or both. Dataset callbacks return JSON values consumed by
    the Vega-Lite ``data.url`` references in those manifests.
    """

    model_config = {"arbitrary_types_allowed": True}

    name: str = Field(
        description=(
            "URL-safe analytics resource identifier, e.g. 'interviewer'. "
            "Lowercase letters, digits, underscores, and hyphens only; "
            "must start with a letter or digit."
        ),
        pattern=_ANALYTICS_RESOURCE_NAME_PATTERN,
    )
    display_name: str = Field(default="")
    description: str = Field(default="")
    dashboards: list[dict[str, Any]] = Field(default_factory=list)
    datasets: list[AnalyticsDataset | dict[str, Any]] = Field(default_factory=list)
    filters: list[AnalyticsFilter | dict[str, Any]] = Field(default_factory=list)
    on_list_dashboards: Callable[..., list[dict[str, Any]]] | None = Field(
        default=None, exclude=True
    )
    on_get_dashboard: Callable[..., dict[str, Any] | None] | None = Field(
        default=None, exclude=True
    )
    on_get_dataset: (
        Callable[..., dict[str, Any] | list[dict[str, Any]] | None] | None
    ) = Field(default=None, exclude=True)

    @model_validator(mode="after")
    def check_dashboard_source(self) -> "AnalyticsResource":
        if not self.dashboards and self.on_list_dashboards is None:
            raise ValueError(
                f"AnalyticsResource '{self.name}' must define dashboards or on_list_dashboards"
            )
        for dashboard in self.dashboards:
            if not dashboard.get("id"):
                raise ValueError(
                    f"Static dashboard in AnalyticsResource '{self.name}' must define id"
                )
        return self

    @property
    def operations(self) -> dict[str, bool]:
        return {
            "list_dashboards": True,
            "get_dashboard": True,
            "get_dataset": self.on_get_dataset is not None,
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
            "dashboards": [
                _dashboard_summary(dashboard) for dashboard in self.dashboards
            ],
            "datasets": [
                dataset.model_dump(mode="json")
                if isinstance(dataset, AnalyticsDataset)
                else dataset
                for dataset in self.datasets
            ],
            "filters": [
                filter_.model_dump(mode="json")
                if isinstance(filter_, AnalyticsFilter)
                else filter_
                for filter_ in self.filters
            ],
            "operations": self.operations,
        }

    def list_dashboards(self) -> list[dict[str, Any]]:
        return self.dashboards

    def get_static_dashboard(self, dashboard_id: str) -> dict[str, Any] | None:
        for dashboard in self.dashboards:
            if dashboard.get("id") == dashboard_id:
                return dashboard
        return None


def _dashboard_summary(dashboard: dict[str, Any]) -> dict[str, Any]:
    return {
        key: dashboard[key]
        for key in ("id", "title", "description", "version")
        if key in dashboard
    }
