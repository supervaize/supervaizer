# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

from typing import TYPE_CHECKING, Union

import httpx

from .common import ApiError, ApiResult, ApiSuccess, log

if TYPE_CHECKING:
    from .agent import Agent
    from .case import Case, CaseNodeUpdate
    from .event import Event
    from .server import Server
    from .account import Account
    from .job import Job


def send_event(
    account: "Account",
    sender: Union["Agent", "Server", "Job", "Case", "CaseNodeUpdate"],
    event: "Event",
) -> ApiResult:
    """Send an event to the Supervaize SaaS API.

    Args:
        account (Account): The account used to authenticate the request
        sender (Union[Agent, Server, Case, CaseNodeUpdate]): The sender of the event
        event (Event): The event to be sent

    Returns:
        ApiResult: ApiSuccess with response details if successful,
    Raises:
        Request exception if the request fails.

    Side effects:
        - Sends an event to the Supervaize Control API

        Tested in tests/test_account_service.py
    """

    headers = account.api_headers
    payload = event.payload
    log.debug(f"[Send event] <{event.type.name}> to <{account.url_event}>")
    log.debug(f"[Send event] Payload: {payload}")
    try:
        response = httpx.post(account.url_event, headers=headers, json=payload)
        response.raise_for_status()
        result = ApiSuccess(
            message=f"POST Event {event.type.name} sent", detail=response.text
        )

        log.success(result.log_message)
    except httpx.HTTPError as e:
        error_result = ApiError(
            message=f"Error sending event {event.type.name}",
            url=account.url_event,
            payload=event.payload,
            exception=e,
        )
        log.debug(f"[Send event] Payload: {payload}")
        log.error(f"[Send event] Error details: {error_result.dict}")
        log.error(error_result.log_message)
        raise e
    return result
