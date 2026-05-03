# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

import pytest
from pydantic import ValidationError

from supervaizer.analytics_resource import (
    AnalyticsDataset,
    AnalyticsFilter,
    AnalyticsResource,
)


def test_analytics_resource_name_must_be_url_safe() -> None:
    with pytest.raises(ValidationError):
        AnalyticsResource(name="Bad Name", dashboards=[{"id": "overview"}])


def test_analytics_resource_requires_dashboard_source() -> None:
    with pytest.raises(
        ValueError, match="must define dashboards or on_list_dashboards"
    ):
        AnalyticsResource(name="interviewer")


def test_static_dashboards_require_id() -> None:
    with pytest.raises(ValueError, match="must define id"):
        AnalyticsResource(name="interviewer", dashboards=[{"title": "Overview"}])


def test_analytics_resource_registration_info() -> None:
    resource = AnalyticsResource(
        name="interviewer",
        display_name="Interviewer Analytics",
        description="Interview funnel health",
        dashboards=[
            {
                "id": "overview",
                "title": "Overview",
                "description": "Mission summary",
                "version": "1.0.0",
                "widgets": [{"id": "sessions", "spec": {"mark": "bar"}}],
            }
        ],
        datasets=[AnalyticsDataset(id="sessions", description="Session rows")],
        filters=[
            AnalyticsFilter(
                id="status",
                label="Status",
                options=[{"value": "complete", "label": "Complete"}],
            )
        ],
        on_get_dataset=lambda dashboard_id, dataset_id: {"values": []},
    )

    info = resource.registration_info

    assert info["name"] == "interviewer"
    assert info["display_name"] == "Interviewer Analytics"
    assert info["dashboards"] == [
        {
            "id": "overview",
            "title": "Overview",
            "description": "Mission summary",
            "version": "1.0.0",
        }
    ]
    assert info["datasets"] == [{"id": "sessions", "description": "Session rows"}]
    assert info["filters"][0]["id"] == "status"
    assert info["operations"]["get_dataset"] is True


def test_static_dashboard_lookup() -> None:
    resource = AnalyticsResource(
        name="interviewer",
        dashboards=[{"id": "overview", "title": "Overview"}],
    )

    assert resource.get_static_dashboard("overview") == {
        "id": "overview",
        "title": "Overview",
    }
    assert resource.get_static_dashboard("missing") is None


def test_callbacks_excluded_from_serialization() -> None:
    resource = AnalyticsResource(
        name="interviewer",
        dashboards=[{"id": "overview"}],
        on_get_dataset=lambda dashboard_id, dataset_id: {"values": []},
    )

    dumped = resource.model_dump()

    assert "on_list_dashboards" not in dumped
    assert "on_get_dashboard" not in dumped
    assert "on_get_dataset" not in dumped
