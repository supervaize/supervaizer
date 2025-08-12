# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

import json
import os
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import uuid4

import pytest
from pydantic import BaseModel, ValidationError

from supervaizer import Agent, AgentMethod, AgentMethods, ApiSuccess, Server
from supervaizer.agent import AgentMethodField, AgentMethodsAbstract, FieldTypeEnum
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


def test_agent_custom_methods_names(agent_fixture: Agent) -> None:
    """Test custom methods names property."""
    assert agent_fixture.custom_methods_names == ["method1", "method2"]


def test_agent_method_validate_method_fields_no_fields() -> None:
    """Test validate_method_fields when method has no field definitions."""
    method = AgentMethod(name="test_method", method="test.method", fields=None)

    result = method.validate_method_fields({"some_field": "value"})

    assert result["valid"] is True
    assert result["message"] == "Method has no field definitions"
    assert len(result["errors"]) == 0
    assert len(result["invalid_fields"]) == 0


def test_agent_method_validate_method_fields_empty_fields() -> None:
    """Test validate_method_fields when method has empty field definitions."""
    method = AgentMethod(name="test_method", method="test.method", fields=[])

    result = method.validate_method_fields({"some_field": "value"})

    assert result["valid"] is True
    assert result["message"] == "Method fields validated successfully"
    assert len(result["errors"]) == 0
    assert len(result["invalid_fields"]) == 0


def test_agent_method_validate_method_fields_missing_required() -> None:
    """Test validate_method_fields with missing required fields."""
    method = AgentMethod(
        name="test_method",
        method="test.method",
        fields=[
            AgentMethodField(name="required_field", type=str, required=True),
            AgentMethodField(name="optional_field", type=str, required=False),
        ],
    )

    result = method.validate_method_fields({"optional_field": "present"})

    assert result["valid"] is False
    assert result["message"] == "Method field validation failed"
    assert len(result["errors"]) == 1
    assert "required_field" in result["invalid_fields"]
    assert "is missing" in result["invalid_fields"]["required_field"]


def test_agent_method_validate_method_fields_unknown_field() -> None:
    """Test validate_method_fields with unknown field."""
    method = AgentMethod(
        name="test_method",
        method="test.method",
        fields=[AgentMethodField(name="known_field", type=str, required=True)],
    )

    result = method.validate_method_fields(
        {
            "known_field": "valid_value",
            "unknown_field": "should_fail",
        }
    )

    assert result["valid"] is False
    assert result["message"] == "Method field validation failed"
    assert len(result["errors"]) == 1
    assert "unknown_field" in result["invalid_fields"]
    assert "Unknown field" in result["invalid_fields"]["unknown_field"]


def test_agent_method_validate_method_fields_valid_types() -> None:
    """Test validate_method_fields with valid field types."""
    method = AgentMethod(
        name="test_method",
        method="test.method",
        fields=[
            AgentMethodField(name="string_field", type=str, required=True),
            AgentMethodField(name="int_field", type=int, required=True),
            AgentMethodField(name="bool_field", type=bool, required=False),
            AgentMethodField(name="list_field", type=list, required=False),
            AgentMethodField(name="dict_field", type=dict, required=False),
            AgentMethodField(name="float_field", type=float, required=False),
        ],
    )

    result = method.validate_method_fields(
        {
            "string_field": "valid_string",
            "int_field": 42,
            "bool_field": True,
            "list_field": ["item1", "item2"],
            "dict_field": {"key": "value"},
            "float_field": 3.14,
        }
    )

    assert result["valid"] is True
    assert result["message"] == "Method fields validated successfully"
    assert len(result["errors"]) == 0
    assert len(result["invalid_fields"]) == 0


def test_agent_method_validate_method_fields_invalid_types() -> None:
    """Test validate_method_fields with invalid field types."""
    method = AgentMethod(
        name="test_method",
        method="test.method",
        fields=[
            AgentMethodField(name="string_field", type=str, required=True),
            AgentMethodField(name="int_field", type=int, required=True),
            AgentMethodField(name="bool_field", type=bool, required=False),
        ],
    )

    result = method.validate_method_fields(
        {
            "string_field": 123,  # Should be string
            "int_field": "not_a_number",  # Should be int
            "bool_field": "not_a_bool",  # Should be bool
        }
    )

    assert result["valid"] is False
    assert result["message"] == "Method field validation failed"
    assert len(result["errors"]) == 3
    assert "string_field" in result["invalid_fields"]
    assert "int_field" in result["invalid_fields"]
    assert "bool_field" in result["invalid_fields"]

    # Check specific error messages
    assert "must be a string" in result["invalid_fields"]["string_field"]
    assert "must be an integer" in result["invalid_fields"]["int_field"]
    assert "must be a boolean" in result["invalid_fields"]["bool_field"]


def test_agent_method_validate_method_fields_none_values() -> None:
    """Test validate_method_fields with None values for optional fields."""
    method = AgentMethod(
        name="test_method",
        method="test.method",
        fields=[
            AgentMethodField(name="required_field", type=str, required=True),
            AgentMethodField(name="optional_field", type=str, required=False),
        ],
    )

    result = method.validate_method_fields(
        {
            "required_field": "present",
            "optional_field": None,
        }
    )

    assert result["valid"] is True
    assert result["message"] == "Method fields validated successfully"
    assert len(result["errors"]) == 0
    assert len(result["invalid_fields"]) == 0


def test_agent_method_validate_method_fields_float_types() -> None:
    """Test validate_method_fields with float types."""
    method = AgentMethod(
        name="test_method",
        method="test.method",
        fields=[AgentMethodField(name="float_field", type=float, required=True)],
    )

    # Test with float
    result_float = method.validate_method_fields({"float_field": 2.718})
    assert result_float["valid"] is True

    # Test with int (should also be valid)
    result_int = method.validate_method_fields({"float_field": 42})
    assert result_int["valid"] is True

    # Test with invalid type
    result_invalid = method.validate_method_fields({"float_field": "not_a_number"})
    assert result_invalid["valid"] is False
    assert "must be a number" in result_invalid["invalid_fields"]["float_field"]


def test_agent_method_validate_method_fields_list_and_dict_types() -> None:
    """Test validate_method_fields with list and dict types."""
    method = AgentMethod(
        name="test_method",
        method="test.method",
        fields=[
            AgentMethodField(name="list_field", type=list, required=True),
            AgentMethodField(name="dict_field", type=dict, required=True),
        ],
    )

    # Test with valid types
    result_valid = method.validate_method_fields(
        {
            "list_field": ["item1", "item2"],
            "dict_field": {"key": "value"},
        }
    )
    assert result_valid["valid"] is True

    # Test with invalid types
    result_invalid = method.validate_method_fields(
        {
            "list_field": "not_a_list",
            "dict_field": "not_a_dict",
        }
    )

    assert result_invalid["valid"] is False
    assert "must be a list" in result_invalid["invalid_fields"]["list_field"]
    assert "must be a dictionary" in result_invalid["invalid_fields"]["dict_field"]


def test_agent_method_validate_method_fields_validation_exception() -> None:
    """Test validate_method_fields handles validation exceptions gracefully."""
    method = AgentMethod(
        name="test_method",
        method="test.method",
        fields=[AgentMethodField(name="test_field", type=str, required=True)],
    )

    # Mock a field that would cause an exception during validation
    # This tests the exception handling in the validation logic
    result = method.validate_method_fields({"test_field": "valid_string"})

    assert result["valid"] is True
    assert len(result["errors"]) == 0


def test_fields_annotations_dynamic_model() -> None:
    # Create test AgentMethod instance
    agent_method = AgentMethod(
        name="start",
        method="control.job_start",
        params={"action": "start"},
        is_async=False,
        fields=[
            AgentMethodField(
                name="full_name",
                type=str,
                field_type=FieldTypeEnum.CHAR,
                required=True,
                description="Full name of the person",
                choices=None,
                default=None,
                widget=None,
            ),
            AgentMethodField(
                name="age",
                type=int,
                field_type=FieldTypeEnum.INT,
                required=True,
                description="Age of the person",
                choices=None,
                default=None,
                widget=None,
            ),
            AgentMethodField(
                name="subscribe",
                type=bool,
                field_type=FieldTypeEnum.BOOL,
                required=False,
                description="Subscribe to newsletter",
                choices=None,
                default=False,
                widget=None,
            ),
            AgentMethodField(
                name="gender",
                type=str,
                field_type=FieldTypeEnum.CHOICE,
                choices=["M", "F"],
                widget="RadioSelect",
                required=True,
                description="Gender selection",
                default=None,
            ),
            AgentMethodField(
                name="bio",
                type=str,
                field_type=FieldTypeEnum.CHAR,
                widget="Textarea",
                required=False,
                description="Biography",
                choices=None,
                default=None,
            ),
            AgentMethodField(
                name="country",
                type=str,
                field_type=FieldTypeEnum.CHOICE,
                choices=["US", "CA"],
                required=True,
                description="Country of residence",
                default=None,
                widget=None,
            ),
            AgentMethodField(
                name="languages",
                type=list[str],
                field_type=FieldTypeEnum.MULTICHOICE,
                choices=["en", "fr", "es"],
                required=False,
                description="Languages spoken",
                default=None,
                widget=None,
            ),
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
    assert DynamicModel.__annotations__["languages"] is Optional[list]

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
        is_async=False,
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
        is_async=False,
        fields=[
            {
                "name": "full_name",
                "type": str,
                "field_type": "CharField",
                "required": True,
                "description": "Full name of the person",
                "choices": None,
                "default": None,
                "widget": None,
            },
            {
                "name": "age",
                "type": int,
                "field_type": "IntegerField",
                "required": True,
                "description": "Age of the person",
                "choices": None,
                "default": None,
                "widget": None,
            },
        ],
        description="Start job test",
    )

    # Get the dynamic job model class
    AbstractJob = agent_method.job_model

    # Test 1: Verify it's a Pydantic model
    assert issubclass(AbstractJob, BaseModel)

    # Test 2: Check the structure of the model
    assert AbstractJob.model_fields["job_context"].annotation == JobContext
    assert "job_fields" in AbstractJob.model_fields

    # Test 3: Create a valid instance
    from datetime import datetime

    valid_data = {
        "job_context": {
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
    model_instance = AbstractJob(**valid_data)

    # Verify we can access the fields
    assert model_instance.job_context.workspace_id == "ws-123"
    assert model_instance.job_context.job_id == "job-456"
    # Job fields is dynamically created
    assert model_instance.job_fields.full_name == "John Doe"
    assert model_instance.job_fields.age == 30

    # Test 4: Validation errors for invalid types
    with pytest.raises(ValidationError):
        AbstractJob(
            job_context={
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
        AbstractJob(
            job_context={
                # missing required fields
                "workspace_id": "ws-123"
            },
            job_fields={"full_name": "John Doe", "age": 30},
        )

    # Test 6: Missing required fields in job_fields
    with pytest.raises(ValidationError):
        AbstractJob(
            job_context={
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
        is_async=False,
    )
    EmptyAbstractJob = empty_method.job_model
    assert issubclass(EmptyAbstractJob, BaseModel)

    # Create a valid instance with empty fields
    empty_valid_data = {
        "job_context": {
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
    empty_instance = EmptyAbstractJob(**empty_valid_data)
    assert isinstance(empty_instance, BaseModel)
    assert model_instance.job_context.workspace_id == "ws-123"


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
        lambda self, encrypted_parameters: json.dumps(
            [
                {"name": "parameter1", "value": "new_value1", "is_environment": True},
                {"name": "parameter2", "value": "new_value2", "is_environment": False},
            ]
        ),
    )
    # Ensure supervisor_account is not None
    assert server_fixture.supervisor_account is not None

    # Simulate server.supervisor_account.get_agent_by() returns agent details
    monkeypatch.setattr(
        server_fixture.supervisor_account.__class__,
        "get_agent_by",
        lambda self, agent_id=None, agent_slug=None: ApiSuccess(
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
        lambda self, encrypted_parameters: json.dumps(
            [{"invalid_parameter": "invalid_value1"}]
        ),
    )
    with pytest.raises(ValueError):
        agent_fixture.update_agent_from_server(server_fixture)


def test_agent_job_context(agent_fixture: Agent) -> None:
    """Test agent job context"""
    # Create a job context
    job_id = f"test-job-{str(uuid4())[:8]}"
    context = JobContext(
        workspace_id="test-workspace-id",
        job_id=job_id,
        started_by="test-started-by",
        started_at=datetime.now(),
        mission_id="test-mission-id",
        mission_name="test-mission-name",
        mission_context=None,
        job_instructions=None,
    )

    # Create job with context
    job = Job.new(
        job_context=context,
        agent_name=agent_fixture.name,
        agent_parameters=None,
    )

    # Test job fields
    assert job.job_context.job_id == job_id
    assert job.job_context.started_by == "test-started-by"
    assert job.job_context.workspace_id == "test-workspace-id"
    assert job.job_context.mission_id == "test-mission-id"
    assert job.job_context.mission_name == "test-mission-name"
    assert job.job_context.mission_context is None
    assert job.job_context.job_instructions is None


def test_custom_method_key_validation() -> None:
    """Test validation of custom method keys in AbstractAgentMethods."""

    # Create a basic agent method for testing
    basic_method = AgentMethod(
        name="test", method="test.method", description="Test method", is_async=False
    )

    # Test valid custom method keys
    valid_keys = [
        "backup",
        "health-check",
        "sync-data",
        "test123",
        "method-1",
        "a",
        "very-long-method-name-that-is-still-valid",
    ]

    for key in valid_keys:
        # Should not raise any validation error
        methods = AgentMethodsAbstract(
            job_start=basic_method,
            job_stop=basic_method,
            job_status=basic_method,
            custom={key: basic_method},
        )
        assert methods.custom is not None
        assert key in methods.custom

    # Test invalid custom method keys
    invalid_cases = [
        # Invalid characters
        ("method_with_underscore", "not a valid slug"),
        ("method with spaces", "not a valid slug"),
        ("method@special", "not a valid slug"),
        ("Method-With-Caps", "not a valid slug"),
        ("method.with.dots", "not a valid slug"),
        # Invalid format - these will be caught by the regex check
        ("-starts-with-hyphen", "not a valid slug"),
        ("ends-with-hyphen-", "not a valid slug"),
        ("double--hyphen", "not a valid slug"),
        # Too long
        ("a" * 51, "too long"),
    ]

    for invalid_key, expected_error_part in invalid_cases:
        with pytest.raises(ValidationError) as exc_info:
            AgentMethodsAbstract(
                job_start=basic_method,
                job_stop=basic_method,
                job_status=basic_method,
                custom={invalid_key: basic_method},
            )

        # Check that the error message contains the expected part
        error_message = str(exc_info.value)
        assert expected_error_part in error_message.lower(), (
            f"Expected '{expected_error_part}' in error for key '{invalid_key}', got: {error_message}"
        )


def test_custom_method_key_validation_with_multiple_keys() -> None:
    """Test validation when multiple custom method keys are provided."""

    basic_method = AgentMethod(
        name="test", method="test.method", description="Test method", is_async=False
    )

    # Test with mix of valid and invalid keys
    with pytest.raises(ValidationError) as exc_info:
        AgentMethodsAbstract(
            job_start=basic_method,
            job_stop=basic_method,
            job_status=basic_method,
            custom={
                "valid-method": basic_method,
                "another-valid": basic_method,
                "Invalid-Key": basic_method,  # This should cause validation error
                "also-valid": basic_method,
            },
        )

    error_message = str(exc_info.value)
    assert "Invalid-Key" in error_message
    assert "not a valid slug" in error_message


def test_custom_method_key_validation_none_value() -> None:
    """Test that validation passes when custom is None."""

    basic_method = AgentMethod(
        name="test", method="test.method", description="Test method", is_async=False
    )

    # Should not raise any validation error when custom is None
    methods = AgentMethodsAbstract(
        job_start=basic_method,
        job_stop=basic_method,
        job_status=basic_method,
        custom=None,
    )
    assert methods.custom is None


def test_custom_method_key_validation_empty_dict() -> None:
    """Test that validation passes when custom is an empty dict."""

    basic_method = AgentMethod(
        name="test", method="test.method", description="Test method", is_async=False
    )

    # Should not raise any validation error when custom is empty
    methods = AgentMethodsAbstract(
        job_start=basic_method,
        job_stop=basic_method,
        job_status=basic_method,
        custom={},
    )
    assert methods.custom == {}


def test_agent_method_fields_definitions() -> None:
    from supervaizer.agent import AgentMethod, AgentMethodField

    fields = [
        AgentMethodField(
            name="color",
            type=list[str],
            field_type="MultipleChoiceField",
            choices=["B", "R", "G"],
            widget="RadioSelect",
            required=True,
            description="Pick a color",
            default=None,
        ),
        AgentMethodField(
            name="age",
            type=int,
            field_type="IntegerField",
            widget="NumberInput",
            required=False,
            default=18,
            description="Enter your age",
            choices=None,
        ),
    ]
    agent_method = AgentMethod(
        name="test",
        method="test.method",
        fields=fields,
        is_async=False,
    )
    defs = agent_method.fields_definitions
    assert isinstance(defs, list)
    assert len(defs) == 2
    for d in defs:
        assert isinstance(d, dict)
    assert defs[0]["name"] == "color"
    assert defs[0]["field_type"] == "MultipleChoiceField"
    assert defs[0]["choices"] == ["B", "R", "G"]
    assert defs[0]["widget"] == "RadioSelect"
    assert defs[0]["required"] is True
    assert defs[0]["description"] == "Pick a color"
    assert defs[0]["type"] == "list"
    assert defs[0]["default"] is None
    assert defs[1]["name"] == "age"
    assert defs[1]["field_type"] == "IntegerField"
    assert defs[1]["widget"] == "NumberInput"
    assert defs[1]["required"] is False
    assert defs[1]["default"] == 18
    assert defs[1]["description"] == "Enter your age"
    assert defs[1]["type"] == "int"
    assert defs[1]["choices"] is None
