# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""Unmodified v2 agents register byte-for-byte as before the guided setup fields.

`registration_baseline.json` was captured before those fields existed. To
refresh it on purpose, dump `_registration_payloads()` with
`json.dumps(payloads, indent=2, ensure_ascii=False) + "\\n"`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from supervaizer import Agent, build_v2_agent_registration
from supervaizer.contracts import (
    AgentRegistrationContract,
    BillingCatalogItem,
    SupervaizerV2AgentRegistrationContract,
    V2AgentFullDescription,
    V2AgentIntroduction,
)
from supervaizer.examples.hello_world_agent import HELLO_WORLD_BILLING_CATALOG
from supervaizer.examples.local_server import get_default_local_agent
from tests.test_v2_only_agents import _v2_only_agent

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "supervaizer_v2"
BASELINE = json.loads((FIXTURE_DIR / "registration_baseline.json").read_text())
INTRODUCTION = {
    "tagline": "Runs long jobs for you",
    "summary": "Collects a goal, plans the work and reports back.",
    "example_goals": ["Prepare a weekly digest", "Review a document"],
    "avatar_url": "https://example.com/avatar.png",
}
FULL_DESCRIPTION = {
    "format": "markdown",
    "content": "# Runner\n\nCollects a goal, plans the work and reports back.",
}
BILLING_CATALOG = [
    {"sku": "interview_minute", "unit": "minute", "description": "Voice time"},
    {"sku": "transcript_token", "unit": "token", "description": ""},
]


def _registration_payloads() -> dict[str, Any]:
    v2_only = _v2_only_agent()
    fixture = json.loads((FIXTURE_DIR / "agent_interviewer_mvp.json").read_text())
    contract_keys = (
        "id",
        "slug",
        "name",
        "api_path",
        "methods",
        "parameters_setup",
        "data_resources",
    )
    return {
        "v2_only_agent.registration_info": v2_only.registration_info,
        "local_agent.registration_info": get_default_local_agent().registration_info,
        "fixture.registration": SupervaizerV2AgentRegistrationContract.model_validate(
            fixture["registration"]
        ).model_dump(mode="json"),
        "v2_only_agent.AgentRegistrationContract": (
            AgentRegistrationContract.model_validate({
                key: v2_only.registration_info[key] for key in contract_keys
            }).model_dump(mode="json")
        ),
    }


@pytest.mark.parametrize("payload", sorted(BASELINE))
def test_unmodified_v2_agent_registration_is_byte_identical(payload: str) -> None:
    current = _registration_payloads()[payload]

    assert json.dumps(current, indent=2, ensure_ascii=False) == json.dumps(
        BASELINE[payload], indent=2, ensure_ascii=False
    )


def test_registration_without_introduction_has_no_introduction_key() -> None:
    contract = AgentRegistrationContract(slug="a", name="A", api_path="/agents/a")

    assert "introduction" not in contract.model_dump(mode="json")
    assert "introduction" not in _v2_only_agent().registration_info


def test_agent_introduction_rides_on_registration_info() -> None:
    agent = Agent(
        name="Introduced Agent",
        version="1.0.0",
        supervaizer_v2_registration=build_v2_agent_registration(
            agent_slug="introduced-agent",
            display_name="Introduced Agent",
            a2ui_catalog_version="introduced.1",
            actions=["job.start"],
        ),
        introduction=INTRODUCTION,
    )
    info = agent.registration_info

    assert isinstance(agent.introduction, V2AgentIntroduction)
    assert info["introduction"] == INTRODUCTION
    contract = AgentRegistrationContract.model_validate({
        key: info[key] for key in ("slug", "name", "api_path", "introduction")
    })
    assert contract.model_dump(mode="json")["introduction"] == INTRODUCTION


def test_agent_introduction_omits_unset_avatar() -> None:
    introduction = V2AgentIntroduction(**{**INTRODUCTION, "avatar_url": None})

    assert "avatar_url" not in introduction.model_dump(mode="json")


@pytest.mark.parametrize(
    "override",
    [
        {"avatar_url": "http://example.com/avatar.png"},
        {"example_goals": []},
        {"example_goals": ["goal"] * 6},
        {"example_goals": ["x" * 121]},
        {"example_goals": ["   "]},
        {"tagline": "x" * 121},
        {"summary": "x" * 301},
        {"tagline": ""},
    ],
)
def test_agent_introduction_rejects_out_of_contract_values(
    override: dict[str, Any],
) -> None:
    with pytest.raises(ValidationError):
        V2AgentIntroduction.model_validate({**INTRODUCTION, **override})


def test_registration_without_full_description_has_no_key() -> None:
    contract = AgentRegistrationContract(slug="a", name="A", api_path="/agents/a")

    assert "full_description" not in contract.model_dump(mode="json")
    assert "full_description" not in _v2_only_agent().registration_info


def test_agent_full_description_rides_on_registration_info() -> None:
    agent = Agent(
        name="Described Agent",
        version="1.0.0",
        supervaizer_v2_registration=build_v2_agent_registration(
            agent_slug="described-agent",
            display_name="Described Agent",
            a2ui_catalog_version="described.1",
            actions=["job.start"],
        ),
        full_description=FULL_DESCRIPTION,
    )
    info = agent.registration_info

    assert isinstance(agent.full_description, V2AgentFullDescription)
    assert info["full_description"] == FULL_DESCRIPTION
    contract = AgentRegistrationContract.model_validate({
        key: info[key] for key in ("slug", "name", "api_path", "full_description")
    })
    assert contract.model_dump(mode="json")["full_description"] == FULL_DESCRIPTION


def test_agent_full_description_formats_and_size_cap() -> None:
    assert V2AgentFullDescription(content="<p>Hi</p>").format == "markdown"
    html = V2AgentFullDescription(format="html", content="x" * 100_000)

    assert html.model_dump(mode="json") == {"format": "html", "content": "x" * 100_000}


@pytest.mark.parametrize(
    "override",
    [
        {"format": "plain"},
        {"format": "Markdown"},
        {"content": "x" * 100_001},
        {"content": ""},
        {"content": " \n\t "},
    ],
)
def test_agent_full_description_rejects_out_of_contract_values(
    override: dict[str, Any],
) -> None:
    with pytest.raises(ValidationError):
        V2AgentFullDescription.model_validate({**FULL_DESCRIPTION, **override})


def _billed_agent(billing_catalog: list[dict[str, Any]] | None) -> Agent:
    return Agent(
        name="Billed Agent",
        version="1.0.0",
        supervaizer_v2_registration=build_v2_agent_registration(
            agent_slug="billed-agent",
            display_name="Billed Agent",
            a2ui_catalog_version="billed.1",
            actions=["job.start"],
        ),
        billing_catalog=billing_catalog,
    )


def test_registration_without_billing_catalog_has_no_key() -> None:
    contract = AgentRegistrationContract(slug="a", name="A", api_path="/agents/a")

    assert "billing_catalog" not in contract.model_dump(mode="json")
    assert "billing_catalog" not in _v2_only_agent().registration_info
    assert "billing_catalog" not in _billed_agent(None).registration_info


def test_agent_billing_catalog_rides_on_registration_info() -> None:
    agent = _billed_agent(BILLING_CATALOG)
    info = agent.registration_info

    assert agent.billing_catalog is not None
    assert all(isinstance(item, BillingCatalogItem) for item in agent.billing_catalog)
    assert info["billing_catalog"] == BILLING_CATALOG
    contract = AgentRegistrationContract.model_validate({
        key: info[key] for key in ("slug", "name", "api_path", "billing_catalog")
    })
    assert contract.model_dump(mode="json")["billing_catalog"] == BILLING_CATALOG


def test_empty_billing_catalog_is_sent_as_empty_list() -> None:
    assert _billed_agent([]).registration_info["billing_catalog"] == []


def test_billing_catalog_rejects_duplicate_skus() -> None:
    duplicated = [*BILLING_CATALOG, {"sku": "interview_minute", "unit": "second"}]

    with pytest.raises(ValidationError, match="interview_minute"):
        _billed_agent(duplicated)
    with pytest.raises(ValidationError, match="interview_minute"):
        AgentRegistrationContract.model_validate({
            "slug": "a",
            "name": "A",
            "api_path": "/agents/a",
            "billing_catalog": duplicated,
        })


def test_hello_world_example_declares_one_sku_outside_the_baseline() -> None:
    catalog = [item.model_dump(mode="json") for item in HELLO_WORLD_BILLING_CATALOG]

    assert catalog == [
        {"sku": "hello_message", "unit": "message", "description": "One hello"}
    ]
    assert _billed_agent(catalog).registration_info["billing_catalog"] == catalog
    assert "billing_catalog" not in get_default_local_agent().registration_info
