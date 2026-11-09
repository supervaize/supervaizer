# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""Keep rendering failures behind the public internal-error response."""

import pytest
from fastapi import HTTPException
from pytest_mock import MockerFixture

from supervaizer.admin import routes
from tests.admin_rig import AdminRig


@pytest.mark.parametrize(
    "path",
    [
        "/manage/",
        "/manage/api/jobs",
        "/manage/api/cases",
        "/manage/api/recent-activity",
    ],
)
def test_rendering_http_errors_keep_the_internal_error_policy(
    rig: AdminRig, mocker: MockerFixture, path: str
) -> None:
    render = mocker.patch.object(
        routes.templates,
        "TemplateResponse",
        side_effect=HTTPException(status_code=418, detail="template failure"),
    )

    page = rig.get(path)

    render.assert_called_once()
    assert page.status == 500
    assert page.response.json() == {"detail": "418: template failure"}
