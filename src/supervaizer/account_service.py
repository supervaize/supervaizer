# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

import asyncio
import atexit
import logging
import os
from typing import TYPE_CHECKING, Any, NoReturn, Union

import httpx

from supervaizer.common import (
    ApiError,
    ApiResult,
    ApiSuccess,
    SvBaseModel,
    is_local_mode,
    log,
)

logger = logging.getLogger("httpx")
# Enable httpx debug logging (optional - uncomment for transport-level debugging)
logger.setLevel(logging.DEBUG)

_httpx_transport = httpx.AsyncHTTPTransport(
    retries=int(os.getenv("SUPERVAIZE_HTTP_MAX_RETRIES", 2))
)
_httpx_client = httpx.AsyncClient(transport=_httpx_transport)
_sync_httpx_transport = httpx.HTTPTransport(
    retries=int(os.getenv("SUPERVAIZE_HTTP_MAX_RETRIES", 2))
)
_sync_httpx_client = httpx.Client(transport=_sync_httpx_transport)

if TYPE_CHECKING:
    from supervaizer.account import Account
    from supervaizer.agent import Agent
    from supervaizer.case import Case, CaseNodeUpdate
    from supervaizer.event import Event
    from supervaizer.job import Job
    from supervaizer.server import Server


def _event_request(
    account: "Account",
    sender: Union["Agent", "Server", "Job", "Case", "CaseNodeUpdate"],
    event: "Event",
) -> tuple[str, dict[str, str], Any]:
    headers = account.api_headers
    payload = SvBaseModel.serialize_value(event.payload)
    url_event = account.url_event.strip()
    return url_event, headers, payload


def _event_curl(url_event: str, headers: dict[str, str]) -> str:
    curl_headers = " ".join([f'-H "{key}: {value}"' for key, value in headers.items()])
    return f"curl -X 'POST' '{url_event}' {curl_headers}"


def _event_success(event: "Event", response: httpx.Response) -> ApiSuccess:
    result = ApiSuccess(
        message=f"POST Event {event.type.name} sent", detail=response.text
    )
    log.success(result.log_message)
    return result


def _handle_event_http_error(
    event: "Event",
    url_event: str,
    curl_cmd: str,
    error: httpx.HTTPError,
) -> NoReturn:
    log.error("[Send event] HTTP Error occurred")
    log.warning(f"⚠️ Try to connect via curl:\n{curl_cmd}")

    error_result = ApiError(
        message=f"Error sending event {event.type.name}",
        url=url_event,
        payload=event.payload,
        exception=error,
    )
    log.error(f"[Send event] Error details: {error_result.dict}")
    log.error(error_result.log_message)
    raise error


def _local_mode_result(event: "Event") -> ApiSuccess | None:
    if not is_local_mode():
        return None
    log.debug(f"[Send event] Local mode — skipping {event.type.name}")
    return ApiSuccess(
        message=f"Event {event.type.name} skipped (local mode)", detail=None
    )


async def send_event(
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

    local_result = _local_mode_result(event)
    if local_result:
        return local_result

    url_event, headers, payload = _event_request(account, sender, event)
    curl_cmd = _event_curl(url_event, headers)

    try:
        response = await _httpx_client.post(url_event, headers=headers, json=payload)
        response.raise_for_status()
        return _event_success(event, response)
    except (httpx.ConnectError, httpx.ConnectTimeout) as e:
        log.error(
            f"Supervaize controller is not available at {url_event}. "
            "Connection refused or timed out. Is the controller server running?"
        )
        log.error(f"❌ Error sending event {event.type.name}: {e!s}")
        raise e
    except httpx.HTTPError as e:
        _handle_event_http_error(event, url_event, curl_cmd, e)


def send_event_sync(
    account: "Account",
    sender: Union["Agent", "Server", "Job", "Case", "CaseNodeUpdate"],
    event: "Event",
) -> ApiResult:
    """Sync entry point for CLI, startup, and other non-async callers."""
    local_result = _local_mode_result(event)
    if local_result:
        return local_result

    url_event, headers, payload = _event_request(account, sender, event)
    curl_cmd = _event_curl(url_event, headers)

    try:
        response = _sync_httpx_client.post(url_event, headers=headers, json=payload)
        response.raise_for_status()
        return _event_success(event, response)
    except (httpx.ConnectError, httpx.ConnectTimeout) as e:
        log.error(
            f"Supervaize controller is not available at {url_event}. "
            "Connection refused or timed out. Is the controller server running?"
        )
        log.error(f"❌ Error sending event {event.type.name}: {e!s}")
        raise e
    except httpx.HTTPError as e:
        _handle_event_http_error(event, url_event, curl_cmd, e)


async def close_httpx_client() -> None:
    """Close the shared async event client."""
    if not _httpx_client.is_closed:
        await _httpx_client.aclose()


def close_httpx_client_sync() -> None:
    """Close shared HTTP clients from sync shutdown hooks."""
    _sync_httpx_client.close()
    if not _httpx_client.is_closed:
        try:
            asyncio.run(_httpx_client.aclose())
        except RuntimeError:
            log.warning("[Send event] Could not close async HTTP client at exit")


atexit.register(close_httpx_client_sync)
