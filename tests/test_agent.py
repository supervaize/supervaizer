# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.


import json
import os
from datetime import datetime
from typing import Any, Dict, Optional

import pytest
from pydantic import BaseModel, ValidationError

from supervaizer import Agent, AgentMethod, AgentMethods, ApiSuccess, Server
from supervaizer.job import Job, JobContext
from supervaizer.parameter import ParametersSetup
from tests.mock_api_responses import GET_AGENT_BY_SUCCESS_RESPONSE_DETAIL


def test_agent_method_fixture(agent_method_fixture: AgentMethod) -> None:
    """Test that the fixture itself is working"""
    assert agent_method_fixture.name == "start"
    assert agent_method_fixture.method == "start"
    assert agent_method_fixture.params == {"param1": "value1"}
    assert agent_method_fixture.description == "Start the agent"


def test_agent(agent_fixture: Agent) -> None:
    assert isinstance(agent_fixture, Agent)
    assert isinstance(agent_fixture.methods.job_start, AgentMethod)
    assert isinstance(agent_fixture.methods.job_stop, AgentMethod)
    assert isinstance(agent_fixture.methods.job_status, AgentMethod)
    assert agent_fixture.methods.chat is None
    assert isinstance(agent_fixture.methods.custom, dict)
    assert isinstance(agent_fixture.methods.custom["method1"], AgentMethod)
    assert isinstance(agent_fixture.methods.custom["method2"], AgentMethod)


def test_account_error(agent_method_fixture: AgentMethod) -> None:
    with pytest.raises(ValueError):
        """
        Test that the agent ID does not match the name
        """
        Agent(
            id="WILLFAIL",
            name="agentName",
            author="authorName",
            developer="Dev",
            version="1.0.0",
            description="description",
            methods=AgentMethods(
                job_start=agent_method_fixture,
                job_stop=agent_method_fixture,
                job_status=agent_method_fixture,
                chat=None,
                custom={"method1": agent_method_fixture},
            ),
        )


def test_agent_custom_methods(agent_fixture: Agent) -> None:
    assert list(agent_fixture.methods.custom.keys()) == ["method1", "method2"]


def test_fields_annotations_dynamic_model() -> None:
    # Create test AgentMethod instance
    agent_method = AgentMethod(
        name="start",
        method="control.job_start",
        params={"action": "start"},
        fields=[
            {
                "name": "full_name",
                "type": str,
                "field_type": "CharField",
                "max_length": 100,
                "required": True,
            },
            {
                "name": "age",
                "type": int,
                "field_type": "IntegerField",
                "required": True,
            },
            {
                "name": "subscribe",
                "type": bool,
                "field_type": "BooleanField",
                "required": False,
            },
            {
                "name": "gender",
                "type": str,
                "field_type": "ChoiceField",
                "choices": [["M", "Male"], ["F", "Female"]],
                "widget": "RadioSelect",
                "required": True,
            },
            {
                "name": "bio",
                "type": str,
                "field_type": "CharField",
                "widget": "Textarea",
                "required": False,
            },
            {
                "name": "country",
                "type": str,
                "field_type": "ChoiceField",
                "choices": [["US", "United States"], ["CA", "Canada"]],
                "required": True,
            },
            {
                "name": "languages",
                "type": list[str],
                "field_type": "MultipleChoiceField",
                "choices": [["en", "English"], ["fr", "French"], ["es", "Spanish"]],
                "required": False,
            },
        ],
        description="Start the collection of new competitor summary",
    )

    # Get the dynamic model class
    DynamicModel = agent_method.fields_annotations

    # Test 1: Verify it's a Pydantic model
    assert issubclass(DynamicModel, BaseModel)

    # Test 2: Check field annotations match expected types
    assert DynamicModel.__annotations__["full_name"] is str
    assert DynamicModel.__annotations__["age"] is int
    assert DynamicModel.__annotations__["subscribe"] is Optional[bool]
    assert DynamicModel.__annotations__["gender"] is str
    assert DynamicModel.__annotations__["bio"] is Optional[str]
    assert DynamicModel.__annotations__["country"] is str
    assert DynamicModel.__annotations__["languages"] is Optional[list[str]]

    # Test 3: Create a valid instance
    valid_data: Dict[str, Any] = {
        "full_name": "John Doe",
        "age": 30,
        "subscribe": True,
        "gender": "M",
        "bio": "Test bio",
        "country": "US",
        "languages": ["en", "es"],
    }
    model_instance = DynamicModel(**valid_data)

    # Verify we can access the fields
    assert getattr(model_instance, "full_name") == "John Doe"
    assert getattr(model_instance, "age") == 30
    assert getattr(model_instance, "languages") == ["en", "es"]

    # Test 4: Validation errors for invalid types
    with pytest.raises(ValidationError):
        DynamicModel(
            full_name="John Doe",
            age="not an integer",  # Wrong type
            gender="M",
            country="US",
        )

    # Test 5: Missing required fields
    with pytest.raises(ValidationError):
        DynamicModel(
            full_name="John Doe",
            # missing age
            gender="M",
            # missing country
        )

    # Test 6: Test with empty fields
    empty_method = AgentMethod(
        name="empty",
        method="control.empty",
        params={},
    )
    EmptyModel = empty_method.fields_annotations
    assert issubclass(EmptyModel, BaseModel)
    # Should be able to instantiate with no fields
    empty_instance = EmptyModel()
    assert isinstance(empty_instance, BaseModel)


def test_job_model_dynamic_model() -> None:
    # Create test AgentMethod instance with fields
    agent_method = AgentMethod(
        name="start",
        method="control.job_start",
        params={"action": "start"},
        fields=[
            {
                "name": "full_name",
                "type": str,
                "field_type": "CharField",
                "required": True,
            },
            {
                "name": "age",
                "type": int,
                "field_type": "IntegerField",
                "required": True,
            },
        ],
        description="Start job test",
    )

    # Get the dynamic job model class
    JobModel = agent_method.job_model

    # Test 1: Verify it's a Pydantic model
    assert issubclass(JobModel, BaseModel)

    # Test 2: Check the structure of the model
    assert JobModel.model_fields["supervaize_context"].annotation == JobContext
    assert "job_fields" in JobModel.model_fields

    # Test 3: Create a valid instance
    from datetime import datetime

    valid_data = {
        "supervaize_context": {
            "workspace_id": "ws-123",
            "job_id": "job-456",
            "started_by": "user-789",
            "started_at": datetime.now(),
            "mission_id": "mission-abc",
            "mission_name": "Test Mission",
        },
        "job_fields": {"full_name": "John Doe", "age": 30},
        "encrypted_agent_parameters": "encrypted_agent_parameters",
    }
    model_instance = JobModel(**valid_data)

    # Verify we can access the fields
    assert model_instance.supervaize_context.workspace_id == "ws-123"
    assert model_instance.supervaize_context.job_id == "job-456"
    # Job fields is dynamically created
    assert model_instance.job_fields.full_name == "John Doe"
    assert model_instance.job_fields.age == 30

    # Test 4: Validation errors for invalid types
    with pytest.raises(ValidationError):
        JobModel(
            supervaize_context={
                "workspace_id": "ws-123",
                "job_id": "job-456",
                "started_by": "user-789",
                "started_at": datetime.now(),
                "mission_id": "mission-abc",
            },
            job_fields={"full_name": "John Doe", "age": "not an integer"},
            encrypted_agent_parameters="encrypted_agent_parameters",
        )

    # Test 5: Missing required fields in context
    with pytest.raises(ValidationError):
        JobModel(
            supervaize_context={
                # missing required fields
                "workspace_id": "ws-123"
            },
            job_fields={"full_name": "John Doe", "age": 30},
        )

    # Test 6: Missing required fields in job_fields
    with pytest.raises(ValidationError):
        JobModel(
            supervaize_context={
                "workspace_id": "ws-123",
                "job_id": "job-456",
                "started_by": "user-789",
                "started_at": datetime.now(),
                "mission_id": "mission-abc",
                "mission_name": "Test Mission",
            },
            job_fields={
                "full_name": "John Doe"
                # missing age
            },
        )

    # Test 7: Test with empty fields
    empty_method = AgentMethod(
        name="empty",
        method="control.empty",
        params={},
    )
    EmptyJobModel = empty_method.job_model
    assert issubclass(EmptyJobModel, BaseModel)

    # Create a valid instance with empty fields
    empty_valid_data = {
        "supervaize_context": {
            "workspace_id": "ws-123",
            "job_id": "job-456",
            "started_by": "user-789",
            "started_at": datetime.now(),
            "mission_id": "mission-abc",
            "mission_name": "Test Mission",
        },
        "job_fields": {},
        "encrypted_agent_parameters": "encrypted_agent_parameters",
    }
    empty_instance = EmptyJobModel(**empty_valid_data)
    assert isinstance(empty_instance, BaseModel)
    assert model_instance.supervaize_context.workspace_id == "ws-123"


def test_agent_parameters(agent_fixture: Agent) -> None:
    assert agent_fixture.parameters_setup is not None
    parameters_setup = agent_fixture.parameters_setup
    assert isinstance(parameters_setup, ParametersSetup)
    assert len(parameters_setup.definitions) == 2
    assert parameters_setup.definitions["parameter1"].value == "value1"
    assert parameters_setup.definitions["parameter2"].value == "value2"
    assert parameters_setup.definitions["parameter2"].description == "desc2"
    assert parameters_setup.definitions["parameter1"].description is None


def test_agent_secrets_not_found(agent_fixture: Agent) -> None:
    assert agent_fixture.parameters_setup is not None
    parameters_setup = agent_fixture.parameters_setup
    with pytest.raises(KeyError):
        parameters_setup.definitions["nonexistent"]


def test_agent_update_agent_from_server(
    agent_fixture: Agent, server_fixture: Server, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Simulate that decrypt method is called and returns the registered values
    monkeypatch.setattr(
        server_fixture.__class__,
        "decrypt",
        lambda self, encrypted_parameters: json.dumps([
            {"name": "parameter1", "value": "new_value1", "is_environment": True},
            {"name": "parameter2", "value": "new_value2", "is_environment": False},
        ]),
    )
    # Simulate server.account.get_agent_by() returns agent details
    monkeypatch.setattr(
        server_fixture.account.__class__,
        "get_agent_by",
        lambda self, agent_id=None, agent_name=None: ApiSuccess(
            message="Success",
            detail=GET_AGENT_BY_SUCCESS_RESPONSE_DETAIL,
            code=200,
        ),
    )
    updated_agent = agent_fixture.update_agent_from_server(server_fixture)
    assert isinstance(updated_agent, Agent)

    assert updated_agent.parameters_setup is not None
    parameters_setup = updated_agent.parameters_setup
    assert parameters_setup.definitions["parameter1"].value == "new_value1"

    assert agent_fixture.parameters_setup is not None
    agent_parameters = agent_fixture.parameters_setup
    assert agent_parameters.definitions["parameter2"].value == "new_value2"

    # Check environment variables were set correctly
    assert "parameter1" in os.environ
    assert os.environ["parameter1"] == "new_value1"
    assert "parameter2" not in os.environ

    # Simulate that decrypt returns an invalid parameter name
    monkeypatch.setattr(
        server_fixture.__class__,
        "decrypt",
        lambda self, encrypted_parameters: json.dumps([
            {"invalid_parameter": "invalid_value1"}
        ]),
    )
    with pytest.raises(ValueError):
        agent_fixture.update_agent_from_server(server_fixture)


def test_agent_job_context(agent_fixture: Agent) -> None:
    """Test agent job context"""
    # Create a job context
    context = JobContext(
        workspace_id="test-workspace-id",
        job_id="test-job-id",
        started_by="test-started-by",
        started_at=datetime.now(),
        mission_id="test-mission-id",
        mission_name="test-mission-name",
        mission_context=None,
        job_instructions=None,
    )

    # Test with valid fields
    job_fields = {"full_name": "John Doe", "age": 30}

    # Create job with context
    job = Job.new(
        supervaize_context=context, agent_name=agent_fixture.name, parameters=None
    )

    # Test job fields
    assert job.supervaize_context.job_id == "test-job-id"
    assert job.supervaize_context.started_by == "test-started-by"
    assert job.supervaize_context.workspace_id == "test-workspace-id"
    assert job.supervaize_context.mission_id == "test-mission-id"
    assert job.supervaize_context.mission_name == "test-mission-name"
    assert job.supervaize_context.mission_context is None
    assert job.supervaize_context.job_instructions is None
