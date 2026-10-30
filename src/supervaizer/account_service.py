# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
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
from collections.abc import Sequence
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
from supervaizer.contracts import (
    BillableConsumption,
    ConsumptionReceipt,
    ConsumptionReport,
    ConsumptionReportResponse,
)

logger = logging.getLogger("httpx")
# Enable httpx debug logging (optional - uncomment for transport-level debugging)
logger.setLevel(logging.DEBUG)

_httpx_transport = httpx.AsyncHTTPTransport(
    retries=int(os.getenv("SUPERVAIZE_HTTP_MAX_RETRIES", "2"))
)
_httpx_client = httpx.AsyncClient(transport=_httpx_transport)
_sync_httpx_transport = httpx.HTTPTransport(
    retries=int(os.getenv("SUPERVAIZE_HTTP_MAX_RETRIES", "2"))
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
    curl_headers = " ".join(
        f'-H "{key}: {_redact_header_value(key, value)}"'
        for key, value in headers.items()
    )
    return f"curl -X 'POST' '{url_event}' {curl_headers}"


def _is_sensitive_field(name: Any) -> bool:
    normalized = "".join(
        character for character in str(name).casefold() if character.isalnum()
    )
    return "token" in normalized or normalized in {
        "apikey",
        "xapikey",
        "authorization",
        "proxyauthorization",
        "secret",
    }


def _redact_header_value(name: str, value: str) -> str:
    if not _is_sensitive_field(name):
        return value
    if name.casefold() in {"authorization", "proxy-authorization"}:
        scheme, separator, _ = value.partition(" ")
        if separator:
            return f"{scheme} ***"
    return "***"


def _redact_sensitive_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "***" if _is_sensitive_field(key) else _redact_sensitive_value(nested)
            for key, nested in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_redact_sensitive_value(item) for item in value]
    return value


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
    if (response := getattr(error, "response", None)) is not None:
        request_id = response.headers.get("X-Request-ID", "unavailable")[:80]
        log.error(
            f"[Send event] Remote response status={response.status_code} request_id={request_id!r}"
        )

    error_result = ApiError(
        message=f"Error sending event {event.type.name}",
        url=url_event,
        payload=event.payload,
        exception=error,
    )
    log.error(
        f"[Send event] Error details: {_redact_sensitive_value(error_result.dict)}"
    )
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
        raise
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
        raise
    except httpx.HTTPError as e:
        _handle_event_http_error(event, url_event, curl_cmd, e)


def _consumption_request(
    account: "Account",
    agent_slug: str,
    records: Sequence[BillableConsumption | dict[str, Any]],
    workspace_id: str | None,
) -> tuple[str, dict[str, str], ConsumptionReport]:
    workspace = account.workspace_id if workspace_id is None else workspace_id
    if not workspace.strip():
        raise ValueError("report_consumption workspace_id must not be blank")
    report = ConsumptionReport.model_validate({
        "agent_slug": agent_slug,
        "records": list(records),
    })
    url = account.get_url("billing_consumption", workspace_id=workspace)
    headers = {**account.api_headers, "workspace": workspace}
    return url, headers, report


def _local_consumption_receipts(
    report: ConsumptionReport,
) -> list[ConsumptionReceipt] | None:
    if not is_local_mode():
        return None
    log.debug(f"[Report consumption] Local mode — accepting {len(report.records)}")
    return [
        ConsumptionReceipt(idempotency_key=record.idempotency_key, status="accepted")
        for record in report.records
    ]


def _consumption_receipts(
    report: ConsumptionReport, response: httpx.Response
) -> list[ConsumptionReceipt]:
    results = ConsumptionReportResponse.model_validate(response.json()).results
    sent = [record.idempotency_key for record in report.records]
    received = [result.idempotency_key for result in results]
    if received != sent:
        raise ValueError(
            "Studio consumption response must hold one result per record, in "
            f"order: sent {len(sent)} records, received {len(received)} results"
        )
    return results


def _response_body(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return response.text[:1000]


def _handle_consumption_error(url: str, error: httpx.HTTPError) -> NoReturn:
    if isinstance(error, (httpx.ConnectError, httpx.ConnectTimeout)):
        log.error(
            f"Supervaize Studio is not available at {url}. "
            "Connection refused or timed out."
        )
    elif isinstance(error, httpx.HTTPStatusError):
        request_id = error.response.headers.get("X-Request-ID", "unavailable")[:80]
        log.error(
            f"[Report consumption] Remote response "
            f"status={error.response.status_code} request_id={request_id!r}"
        )
        if error.response.is_client_error:
            body = _redact_sensitive_value(_response_body(error.response))
            log.error(f"[Report consumption] Response body: {body}")
    log.error(f"❌ Error reporting consumption: {error!s}")
    raise error


async def report_consumption(
    account: "Account",
    agent_slug: str,
    records: Sequence[BillableConsumption | dict[str, Any]],
    workspace_id: str | None = None,
) -> list[ConsumptionReceipt]:
    """Push billable consumption to Studio; return one receipt per record, in order.

    Raises the httpx error of a transport failure or a whole-batch 400/403,
    like ``send_event``. In local mode every record is accepted without HTTP.

    Tested in tests/test_report_consumption.py
    """
    url, headers, report = _consumption_request(
        account, agent_slug, records, workspace_id
    )
    local_receipts = _local_consumption_receipts(report)
    if local_receipts is not None:
        return local_receipts
    try:
        response = await _httpx_client.post(
            url, headers=headers, json=report.model_dump(mode="json")
        )
        response.raise_for_status()
    except httpx.HTTPError as error:
        _handle_consumption_error(url, error)
    return _consumption_receipts(report, response)


def report_consumption_sync(
    account: "Account",
    agent_slug: str,
    records: Sequence[BillableConsumption | dict[str, Any]],
    workspace_id: str | None = None,
) -> list[ConsumptionReceipt]:
    """Sync variant of ``report_consumption`` for non-async callers."""
    url, headers, report = _consumption_request(
        account, agent_slug, records, workspace_id
    )
    local_receipts = _local_consumption_receipts(report)
    if local_receipts is not None:
        return local_receipts
    try:
        response = _sync_httpx_client.post(
            url, headers=headers, json=report.model_dump(mode="json")
        )
        response.raise_for_status()
    except httpx.HTTPError as error:
        _handle_consumption_error(url, error)
    return _consumption_receipts(report, response)


async def close_httpx_client() -> None:
    """Close the shared async event client."""
    if not _httpx_client.is_closed:
        await _httpx_client.aclose()


def close_httpx_client_sync() -> None:
    """Close shared HTTP clients from sync shutdown hooks."""
    _sync_httpx_client.close()
    aclose = getattr(_httpx_client, "aclose", None)
    if aclose and not _httpx_client.is_closed:
        try:
            asyncio.run(aclose())
        except RuntimeError:
            log.warning("[Send event] Could not close async HTTP client at exit")


atexit.register(close_httpx_client_sync)
