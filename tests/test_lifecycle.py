# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

import pytest

from supervaizer.lifecycle import (
    EntityEvents,
    EntityLifecycle,
    EntityStatus,
    Lifecycle,
)


class TestEntityStatus:
    """Test the EntityStatus enum and its properties."""

    @pytest.mark.parametrize(
        "status,is_stopped,is_running,is_anomaly",
        [
            (EntityStatus.STOPPED, True, False, False),
            (EntityStatus.IN_PROGRESS, False, True, False),
            (EntityStatus.CANCELLING, False, True, True),
            (EntityStatus.AWAITING, False, True, False),
            (EntityStatus.COMPLETED, True, False, False),
            (EntityStatus.FAILED, True, False, True),
            (EntityStatus.CANCELLED, True, False, True),
        ],
    )
    def test_status_properties(self, status, is_stopped, is_running, is_anomaly):
        """Test the status enum properties."""
        assert status.is_stopped == is_stopped
        assert status.is_running == is_running
        assert status.is_anomaly == is_anomaly


class TestEntityTransitions:
    """Test the EntityTransitions class methods."""

    def test_get_valid_transitions(self):
        """Test getting valid transitions for a status."""
        # Test for a status with multiple transitions
        in_progress_transitions = Lifecycle.get_valid_transitions(
            EntityStatus.IN_PROGRESS
        )
        assert len(in_progress_transitions) == 4
        assert EntityStatus.COMPLETED in in_progress_transitions
        assert EntityStatus.AWAITING in in_progress_transitions
        assert EntityStatus.CANCELLING in in_progress_transitions
        assert EntityStatus.FAILED in in_progress_transitions

        # Test for a terminal state with no transitions
        completed_transitions = Lifecycle.get_valid_transitions(EntityStatus.COMPLETED)
        assert len(completed_transitions) == 0

        # Test for a status with single transition
        stopped_transitions = Lifecycle.get_valid_transitions(EntityStatus.STOPPED)
        assert len(stopped_transitions) == 1
        assert EntityStatus.IN_PROGRESS in stopped_transitions

    @pytest.mark.parametrize(
        "from_status,to_status,expected",
        [
            (EntityStatus.STOPPED, EntityStatus.IN_PROGRESS, True),
            (EntityStatus.IN_PROGRESS, EntityStatus.COMPLETED, True),
            (EntityStatus.IN_PROGRESS, EntityStatus.AWAITING, True),
            (EntityStatus.AWAITING, EntityStatus.IN_PROGRESS, True),
            (EntityStatus.STOPPED, EntityStatus.COMPLETED, False),  # Invalid transition
            (
                EntityStatus.COMPLETED,
                EntityStatus.IN_PROGRESS,
                False,
            ),  # No way back from terminal state
            (
                EntityStatus.CANCELLING,
                EntityStatus.AWAITING,
                False,
            ),  # Invalid transition
        ],
    )
    def test_can_transition(self, from_status, to_status, expected):
        """Test checking if a transition is valid."""
        assert Lifecycle.can_transition(from_status, to_status) == expected

    def test_get_transition_reason(self):
        """Test getting the reason/event for a transition."""
        # Valid transition
        reason = Lifecycle.get_transition_reason(
            EntityStatus.STOPPED, EntityStatus.IN_PROGRESS
        )
        assert reason == EntityEvents.START_WORK

        # Invalid transition
        reason = Lifecycle.get_transition_reason(
            EntityStatus.STOPPED, EntityStatus.COMPLETED
        )
        assert reason == "Invalid transition"

    @pytest.mark.parametrize(
        "current_status,event,expected",
        [
            (EntityStatus.STOPPED, EntityEvents.START_WORK, EntityStatus.IN_PROGRESS),
            (
                EntityStatus.IN_PROGRESS,
                EntityEvents.SUCCESSFULLY_DONE,
                EntityStatus.COMPLETED,
            ),
            (
                EntityStatus.AWAITING,
                EntityEvents.INPUT_RECEIVED,
                EntityStatus.IN_PROGRESS,
            ),
            (
                EntityStatus.IN_PROGRESS,
                EntityEvents.CANCEL_REQUESTED,
                EntityStatus.CANCELLING,
            ),
            (
                EntityStatus.COMPLETED,
                EntityEvents.START_WORK,
                None,
            ),  # Invalid event for this status
            (
                EntityStatus.STOPPED,
                EntityEvents.CANCEL_CONFIRMED,
                None,
            ),  # Invalid event for this status
        ],
    )
    def test_get_status_from_event(self, current_status, event, expected):
        """Test getting the target status for an event."""
        assert Lifecycle.get_status_from_event(current_status, event) == expected

    def test_generate_valid_transitions_dict(self):
        """Test generating the valid transitions dictionary."""
        valid_transitions = Lifecycle.generate_valid_transitions_dict()

        # Check structure
        assert valid_transitions == {
            # From "created" (equivalent to STOPPED in EntityStatus)
            EntityStatus.STOPPED: {
                EntityStatus.IN_PROGRESS: EntityEvents.START_WORK,
            },
            # From "in progress"
            EntityStatus.IN_PROGRESS: {
                EntityStatus.COMPLETED: EntityEvents.SUCCESSFULLY_DONE,
                EntityStatus.AWAITING: EntityEvents.AWAITING_ON_INPUT,
                EntityStatus.CANCELLING: EntityEvents.CANCEL_REQUESTED,
                EntityStatus.FAILED: EntityEvents.ERROR_ENCOUNTERED,
            },
            # From "awaiting"
            EntityStatus.AWAITING: {
                EntityStatus.FAILED: EntityEvents.TIMEOUT_OR_ERROR,
                EntityStatus.IN_PROGRESS: EntityEvents.INPUT_RECEIVED,
                EntityStatus.CANCELLING: EntityEvents.CANCEL_WHILE_WAITING,
            },
            # From "cancelling"
            EntityStatus.CANCELLING: {
                EntityStatus.CANCELLED: EntityEvents.CANCEL_CONFIRMED,
            },
            # Terminal states - no transitions out
            EntityStatus.COMPLETED: {},
            EntityStatus.CANCELLED: {},
            EntityStatus.FAILED: {},
        }

    def test_mermaid_diagram_all_steps(self):
        """Test generating a Mermaid state diagram."""
        steps = Lifecycle.mermaid_diagram_all_steps()
        expected_lines = [
            "[*] --> stopped",
            "stopped --> in_progress : Start work",
            "in_progress --> completed : Successfully done",
            "in_progress --> awaiting : Awaiting on input",
            "in_progress --> cancelling : Cancel requested",
            "in_progress --> failed : Error encountered",
            "awaiting --> failed : Timeout or error",
            "awaiting --> in_progress : Input received",
            "awaiting --> cancelling : Cancel while waiting",
            "cancelling --> cancelled : Cancel confirmed",
            "completed --> [*]",
            "failed --> [*]",
            "cancelled --> [*]",
        ]

        print(steps)
        # Compare line by line
        for expected, actual in zip(expected_lines, steps):
            assert expected.lower() == actual.lower(), (
                f"\nExpected: {expected}\nActual: {actual}"
            )

        # Verify same number of lines
        assert len(steps) == len(expected_lines), (
            f"Different number of lines: expected {len(expected_lines)}, got {len(steps)}"
        )

    def test_generate_mermaid_diagram(self):
        """Test generating a Mermaid state diagram."""
        diagram = Lifecycle.generate_mermaid_diagram(
            Lifecycle.mermaid_diagram_all_steps()
        )

        # Check that the result is a string and has expected format
        assert isinstance(diagram, str)
        assert diagram.startswith("```mermaid")
        assert diagram.endswith("```")
        expected_mermaid = """```mermaid
        stateDiagram-v2
            [*] --> stopped
            stopped --> in_progress : Start work
            in_progress --> completed : Successfully done
            in_progress --> awaiting : Awaiting on input
            in_progress --> cancelling : Cancel requested
            in_progress --> failed : Error encountered
            awaiting --> failed : Timeout or error
            awaiting --> in_progress : Input received
            awaiting --> cancelling : Cancel while waiting
            cancelling --> cancelled : Cancel confirmed
            completed --> [*]
            failed --> [*]
            cancelled --> [*]
            ```
        """
        # Split both strings into lines and strip whitespace
        actual_lines = [line.strip() for line in diagram.split("\n") if line.strip()]
        expected_lines = [
            line.strip() for line in expected_mermaid.split("\n") if line.strip()
        ]

        # Compare each line
        for actual, expected in zip(actual_lines, expected_lines):
            assert actual.lower() == expected.lower(), (
                f"\nExpected: {expected}\nActual: {actual}"
            )

        # Verify same number of lines
        assert len(actual_lines) == len(expected_lines), (
            f"Different number of lines: expected {len(expected_lines)}, got {len(actual_lines)}"
        )

    def test_get_terminal_states(self):
        """Test identifying terminal states in the state machine."""
        terminal_states = Lifecycle.get_terminal_states()

        expected_terminal = [
            EntityStatus.COMPLETED,
            EntityStatus.CANCELLED,
            EntityStatus.FAILED,
        ]

        # Sort to ensure order-independent comparison
        assert sorted([state.value for state in terminal_states]) == sorted(
            [state.value for state in expected_terminal]
        )

        # Verify that these are indeed terminal states
        for state in terminal_states:
            transitions = Lifecycle.get_valid_transitions(state)
            assert len(transitions) == 0, (
                f"Terminal state {state} should have no outgoing transitions"
            )

    def test_start_states_values(self):
        """Test specific expected values for start states."""
        start_states = Lifecycle.get_start_states()

        # Test values match our expectation
        assert len(start_states) == 1
        assert start_states == [EntityStatus.STOPPED]


class TestEntityLifecycle:
    """Test the EntityLifecycle class methods."""

    def create_mock_entity(self, mocker, status=EntityStatus.STOPPED):
        """Create a mock entity for testing."""
        entity = mocker.MagicMock()
        entity.status = status
        entity.finished_at = None
        entity.id = "test-id"
        entity.name = "Test Entity"
        return entity

    def test_transition_success(self, mocker):
        """Test successful transition."""
        entity = self.create_mock_entity(mocker, EntityStatus.STOPPED)

        # Transition from STOPPED to IN_PROGRESS
        success, error = EntityLifecycle.transition(entity, EntityStatus.IN_PROGRESS)

        assert success is True
        assert error == ""
        assert entity.status == EntityStatus.IN_PROGRESS
        assert entity.finished_at is None  # Should not be set for non-terminal states

    def test_transition_invalid(self, mocker):
        """Test invalid transition."""
        entity = self.create_mock_entity(mocker, EntityStatus.STOPPED)

        # Try invalid transition from STOPPED to COMPLETED
        success, error = EntityLifecycle.transition(entity, EntityStatus.COMPLETED)

        assert success is False
        assert error != ""  # Error message should not be empty
        assert entity.status == EntityStatus.STOPPED  # Status should not change

    def test_transition_to_terminal_state(self, mocker):
        """Test transition to a terminal state sets finished_at."""
        entity = self.create_mock_entity(mocker, EntityStatus.IN_PROGRESS)

        # Transition to a terminal state
        success, error = EntityLifecycle.transition(entity, EntityStatus.COMPLETED)

        assert success is True
        assert error == ""
        assert entity.status == EntityStatus.COMPLETED
        assert entity.finished_at is not None

    def test_handle_event_success(self, mocker):
        """Test successful event handling."""
        entity = self.create_mock_entity(mocker, EntityStatus.STOPPED)

        # Handle START_WORK event
        success, error = EntityLifecycle.handle_event(entity, EntityEvents.START_WORK)

        assert success is True
        assert error == ""
        assert entity.status == EntityStatus.IN_PROGRESS

    def test_handle_event_invalid(self, mocker):
        """Test invalid event handling."""
        entity = self.create_mock_entity(mocker, EntityStatus.STOPPED)

        # Try invalid event for current state
        success, error = EntityLifecycle.handle_event(
            entity, EntityEvents.CANCEL_CONFIRMED
        )

        assert success is False
        assert error != ""  # Error message should not be empty
        assert entity.status == EntityStatus.STOPPED  # Status should not change

    def test_sequential_transitions(self, mocker):
        """Test a sequence of transitions."""
        entity = self.create_mock_entity(mocker, EntityStatus.STOPPED)

        # Complete lifecycle: STOPPED -> IN_PROGRESS -> AWAITING -> IN_PROGRESS -> COMPLETED
        success, _ = EntityLifecycle.transition(entity, EntityStatus.IN_PROGRESS)
        assert success is True
        assert entity.status == EntityStatus.IN_PROGRESS

        success, _ = EntityLifecycle.transition(entity, EntityStatus.AWAITING)
        assert success is True
        assert entity.status == EntityStatus.AWAITING

        success, _ = EntityLifecycle.transition(entity, EntityStatus.IN_PROGRESS)
        assert success is True
        assert entity.status == EntityStatus.IN_PROGRESS

        success, _ = EntityLifecycle.transition(entity, EntityStatus.COMPLETED)
        assert success is True
        assert entity.status == EntityStatus.COMPLETED
        assert entity.finished_at is not None

    def test_sequential_events(self, mocker):
        """Test a sequence of events."""
        entity = self.create_mock_entity(mocker, EntityStatus.STOPPED)

        # Complete lifecycle using events
        success, _ = EntityLifecycle.handle_event(entity, EntityEvents.START_WORK)
        assert success is True
        assert entity.status == EntityStatus.IN_PROGRESS

        success, _ = EntityLifecycle.handle_event(
            entity, EntityEvents.AWAITING_ON_INPUT
        )
        assert success is True
        assert entity.status == EntityStatus.AWAITING

        success, _ = EntityLifecycle.handle_event(entity, EntityEvents.INPUT_RECEIVED)
        assert success is True
        assert entity.status == EntityStatus.IN_PROGRESS

        success, _ = EntityLifecycle.handle_event(
            entity, EntityEvents.SUCCESSFULLY_DONE
        )
        assert success is True
        assert entity.status == EntityStatus.COMPLETED
        assert entity.finished_at is not None
