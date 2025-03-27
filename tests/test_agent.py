# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/.

import pytest
from pydantic import BaseModel, ValidationError

from supervaize_control import Agent, AgentMethod
from supervaize_control.job import JobContext
from supervaize_control.parameter import ParametersSetup


def test_agent_method_fixture(agent_method_fixture):
    """Test that the fixture itself is working"""
    assert agent_method_fixture.name == "start"
    assert agent_method_fixture.method == "start"
    assert agent_method_fixture.params == {"param1": "value1"}
    assert agent_method_fixture.description == "Start the agent"


def test_agent(agent_fixture):
    assert isinstance(agent_fixture, Agent)
    assert isinstance(agent_fixture.job_start_method, AgentMethod)
    assert isinstance(agent_fixture.job_stop_method, AgentMethod)
    assert isinstance(agent_fixture.job_status_method, AgentMethod)
    assert isinstance(agent_fixture.chat_method, AgentMethod)
    assert isinstance(agent_fixture.custom_methods, dict)
    assert isinstance(agent_fixture.custom_methods["method1"], AgentMethod)
    assert isinstance(agent_fixture.custom_methods["method2"], AgentMethod)


def test_account_error(agent_method_fixture):
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
            start_method=agent_method_fixture,
            stop_method=agent_method_fixture,
            status_method=agent_method_fixture,
            chat_method=agent_method_fixture,
            custom_methods={"method1": agent_method_fixture},
        )


def test_agent_custom_methods(agent_fixture):
    assert agent_fixture.custom_methods_names == ["method1", "method2"]


def test_fields_annotations_dynamic_model():
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
    assert DynamicModel.__annotations__["full_name"] == str
    assert DynamicModel.__annotations__["age"] == int
    assert DynamicModel.__annotations__["subscribe"] == bool
    assert DynamicModel.__annotations__["gender"] == str
    assert DynamicModel.__annotations__["bio"] == str
    assert DynamicModel.__annotations__["country"] == str
    assert DynamicModel.__annotations__["languages"] == list[str]

    # Test 3: Create a valid instance
    valid_data = {
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
    assert model_instance.full_name == "John Doe"
    assert model_instance.age == 30
    assert model_instance.languages == ["en", "es"]

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


def test_job_model_dynamic_model():
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
    assert "supervaize_context" in JobModel.__annotations__
    assert "job_fields" in JobModel.__annotations__
    assert JobModel.__annotations__["supervaize_context"] == JobContext

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
                "mission_name": "Test Mission",
            },
            job_fields={
                "full_name": "John Doe",
                "age": "not an integer",  # Wrong type
            },
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
    assert empty_instance.supervaize_context.workspace_id == "ws-123"


def test_agent_parameters(agent_fixture):
    assert agent_fixture.parameters_setup is not None
    assert isinstance(agent_fixture.parameters_setup, ParametersSetup)
    assert len(agent_fixture.parameters_setup.definitions) == 2
    assert agent_fixture.parameters_setup.definitions["parameter1"].value == "value1"
    assert agent_fixture.parameters_setup.definitions["parameter2"].value == "value2"
    assert (
        agent_fixture.parameters_setup.definitions["parameter2"].description == "desc2"
    )
    assert agent_fixture.parameters_setup.definitions["parameter1"].description is None


def test_agent_secrets_not_found(agent_fixture):
    with pytest.raises(KeyError):
        agent_fixture.parameters_setup.definitions["nonexistent"]
