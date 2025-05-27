# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

import logging
from typing import TYPE_CHECKING, Union

import httpx

from supervaizer.common import ApiError, ApiResult, ApiSuccess, log

logger = logging.getLogger("httpx")
# Enable httpx debug logging (optional - uncomment for transport-level debugging)
logger.setLevel(logging.DEBUG)

if TYPE_CHECKING:
    from supervaizer.account import Account
    from supervaizer.agent import Agent
    from supervaizer.case import Case, CaseNodeUpdate
    from supervaizer.event import Event
    from supervaizer.job import Job
    from supervaizer.server import Server


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

    # Generate curl equivalent for debugging

    curl_headers = " ".join([f'-H "{k}: {v}"' for k, v in headers.items()])
    curl_cmd = f"curl -X 'GET' '{account.url_event}'  {curl_headers}"

    try:
        response = httpx.post(account.url_event, headers=headers, json=payload)

        # Log response details before raising for status

        response.raise_for_status()
        result = ApiSuccess(
            message=f"POST Event {event.type.name} sent", detail=response.text
        )

        log.success(result.log_message)
    except httpx.HTTPError as e:
        # Enhanced error logging
        log.error("[Send event] HTTP Error occurred")
        log.warning(f"⚠️ Try to connect via curl:\n{curl_cmd}")

        error_result = ApiError(
            message=f"Error sending event {event.type.name}",
            url=account.url_event,
            payload=event.payload,
            exception=e,
        )
        log.error(f"[Send event] Error details: {error_result.dict}")
        log.error(error_result.log_message)
        raise e
    return result
