# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import pytest

from supervaize_control import (
    Telemetry,
    TelemetryCategory,
    TelemetrySeverity,
    TelemetryType,
)


@pytest.fixture
def telemetry_fixture():
    return Telemetry(
        agentId="123",
        type=TelemetryType.LOGS,
        category=TelemetryCategory.SYSTEM,
        severity=TelemetrySeverity.INFO,
        details={"message": "Test message"},
    )


def test_telemetry(telemetry_fixture):
    assert isinstance(telemetry_fixture, Telemetry)
    assert telemetry_fixture.agentId == "123"
    assert telemetry_fixture.type == TelemetryType.LOGS
    assert telemetry_fixture.category == TelemetryCategory.SYSTEM
    assert telemetry_fixture.severity == TelemetrySeverity.INFO
    assert telemetry_fixture.details == {"message": "Test message"}
