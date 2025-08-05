# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

import logging
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Protocol, TypeVar

if TYPE_CHECKING:
    pass

log = logging.getLogger(__name__)


class EntityStatus(str, Enum):
    """Base status enum for workflow entities."""

    STOPPED = "stopped"
    IN_PROGRESS = "in_progress"
    CANCELLING = "cancelling"
    AWAITING = "awaiting"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @staticmethod
    def status_stopped() -> list["EntityStatus"]:
        return [
            EntityStatus.STOPPED,
            EntityStatus.CANCELLED,
            EntityStatus.FAILED,
            EntityStatus.COMPLETED,
        ]

    @property
    def is_stopped(self) -> bool:
        return self in EntityStatus.status_stopped()

    @staticmethod
    def status_running() -> list["EntityStatus"]:
        return [
            EntityStatus.IN_PROGRESS,
            EntityStatus.CANCELLING,
            EntityStatus.AWAITING,
        ]

    @property
    def is_running(self) -> bool:
        return self in EntityStatus.status_running()

    @staticmethod
    def status_anomaly() -> list["EntityStatus"]:
        return [
            EntityStatus.CANCELLING,
            EntityStatus.CANCELLED,
            EntityStatus.FAILED,
        ]

    @property
    def is_anomaly(self) -> bool:
        return self in EntityStatus.status_anomaly()

    @property
    def label(self) -> str:
        """Get the display label for the enum value."""
        return self.name.replace("_", " ").title()


class EntityEvents(str, Enum):
    """Events that trigger transitions between entity states."""

    START_WORK = "start_work"
    SUCCESSFULLY_DONE = "successfully_done"
    AWAITING_ON_INPUT = "awaiting_on_input"
    CANCEL_REQUESTED = "cancel_requested"
    ERROR_ENCOUNTERED = "error_encountered"
    TIMEOUT_OR_ERROR = "timeout_or_error"
    INPUT_RECEIVED = "input_received"
    CANCEL_WHILE_WAITING = "cancel_while_waiting"
    CANCEL_CONFIRMED = "cancel_confirmed"

    @property
    def label(self) -> str:
        """Get the display label for the enum value."""
        return self.name.replace("_", " ").title()


class Lifecycle:
    """
    Defines valid state transitions for workflow entities.

    From: https://agentcommunicationprotocol.dev/core-concepts/agent-lifecycle
    ```mermaid
        stateDiagram-v2
            [*] --> created
            created --> in_progress : Start work
            in_progress --> completed : Successfully done
            in_progress --> awaiting : Awaiting on input
            in_progress --> cancelling : Cancel requested
            awaiting --> failed : Timeout or error
            in_progress --> failed : Error encountered
            awaiting --> in_progress : Input received
            awaiting --> cancelling : Cancel while waiting
            cancelling --> cancelled : Cancel confirmed
            cancelled --> [*]
            completed --> [*]
            failed --> [*]
    ```
    """

    # Event to transition mapping
    EVENT_TRANSITIONS = {
        EntityEvents.START_WORK: (EntityStatus.STOPPED, EntityStatus.IN_PROGRESS),
        EntityEvents.SUCCESSFULLY_DONE: (
            EntityStatus.IN_PROGRESS,
            EntityStatus.COMPLETED,
        ),
        EntityEvents.AWAITING_ON_INPUT: (
            EntityStatus.IN_PROGRESS,
            EntityStatus.AWAITING,
        ),
        EntityEvents.CANCEL_REQUESTED: (
            EntityStatus.IN_PROGRESS,
            EntityStatus.CANCELLING,
        ),
        EntityEvents.ERROR_ENCOUNTERED: (EntityStatus.IN_PROGRESS, EntityStatus.FAILED),
        EntityEvents.TIMEOUT_OR_ERROR: (EntityStatus.AWAITING, EntityStatus.FAILED),
        EntityEvents.INPUT_RECEIVED: (EntityStatus.AWAITING, EntityStatus.IN_PROGRESS),
        EntityEvents.CANCEL_WHILE_WAITING: (
            EntityStatus.AWAITING,
            EntityStatus.CANCELLING,
        ),
        EntityEvents.CANCEL_CONFIRMED: (
            EntityStatus.CANCELLING,
            EntityStatus.CANCELLED,
        ),
    }

    @classmethod
    def get_terminal_states(cls) -> List[EntityStatus]:
        """
        Identify terminal states in the state machine.

        A terminal state is a state that has no outgoing transitions.

        Returns:
            list: List of EntityStatus enum values representing terminal states
        """
        # Get all states that appear as 'from_status' in transitions
        states_with_outgoing = set(
            from_status for _, (from_status, _) in cls.EVENT_TRANSITIONS.items()
        )

        # Terminal states are those that have no outgoing transitions
        terminal_states = [
            status for status in EntityStatus if status not in states_with_outgoing
        ]

        return terminal_states

    @classmethod
    def get_start_states(cls) -> List[EntityStatus]:
        """
        Identify start states in the state machine.

        A start state is a state that can be entered directly at the beginning of
        the workflow. In our case, this is determined by convention and by examining
        which states don't appear as target states in any transition except their own.

        Returns:
            list: List of EntityStatus enum values representing start states
        """
        # Get all states that appear as 'to_status' in transitions
        target_states = set(
            to_status for _, (_, to_status) in cls.EVENT_TRANSITIONS.items()
        )

        # Get all states that appear as 'from_status' in transitions
        source_states = set(
            from_status for _, (from_status, _) in cls.EVENT_TRANSITIONS.items()
        )

        # Find states that are source states but never target states
        # (except for cycles where they might transition to themselves)
        start_candidates = source_states.difference(target_states)

        # If no clear start states are found based on the above logic,
        # use STOPPED as the conventional start state
        if not start_candidates:
            return [EntityStatus.STOPPED]

        return list(start_candidates)

    @classmethod
    def get_valid_transitions(
        cls, current_status: EntityStatus
    ) -> Dict[EntityStatus, EntityEvents]:
        """Get valid transitions from the current status."""
        result = {}
        for event, (from_status, to_status) in cls.EVENT_TRANSITIONS.items():
            if from_status == current_status:
                result[to_status] = event
        return result

    @classmethod
    def can_transition(cls, from_status: EntityStatus, to_status: EntityStatus) -> bool:
        """Check if transition from current status to target status is valid."""
        for event, (event_from, event_to) in cls.EVENT_TRANSITIONS.items():
            if event_from == from_status and event_to == to_status:
                return True
        return False

    @classmethod
    def get_transition_reason(
        cls, from_status: EntityStatus, to_status: EntityStatus
    ) -> str:
        """Get the reason/description for a transition."""
        for event, (event_from, event_to) in cls.EVENT_TRANSITIONS.items():
            if event_from == from_status and event_to == to_status:
                return event.value
        return "Invalid transition"

    @classmethod
    def get_status_from_event(
        cls, current_status: EntityStatus, event: EntityEvents
    ) -> EntityStatus | None:
        """Get the target status for a given event from the current status."""
        if event not in cls.EVENT_TRANSITIONS:
            return None

        from_status, to_status = cls.EVENT_TRANSITIONS[event]
        if current_status == from_status:
            return to_status

        return None

    @classmethod
    def generate_valid_transitions_dict(
        cls,
    ) -> Dict[EntityStatus, Dict[EntityStatus, EntityEvents]]:
        """
        Generate a complete dictionary of all valid transitions in the format:
        {
            StatusA: {StatusB: EventAB, StatusC: EventAC},
            StatusB: {StatusD: EventBD},
            ...
            TerminalStatusX: {},
        }
        """
        # Initialize the result dictionary with all statuses
        result: Dict[EntityStatus, Dict[EntityStatus, EntityEvents]] = {
            status: {} for status in EntityStatus
        }

        # Populate with transitions from EVENT_TRANSITIONS
        for event, (from_status, to_status) in cls.EVENT_TRANSITIONS.items():
            result[from_status][to_status] = event

        return result

    @classmethod
    def generate_mermaid_diagram(cls, steps_list: list[str]) -> str:
        """
        Generate a Mermaid stateDiagram-v2 representation of the state machine.

        Args:
            steps_list: List of steps to include in the diagram (get it from cls.mermaid_diagram_all_steps())

        Returns:
            str: Mermaid markdown for the state diagram
        """
        # Start with diagram header
        mermaid = "```mermaid\nstateDiagram-v2\n"
        # Start state
        mermaid += "\n    ".join(steps_list)

        # Close the diagram
        mermaid += "\n```"

        return mermaid

    @classmethod
    def mermaid_diagram_all_steps(cls) -> list[str]:
        """Get all steps for the Mermaid diagram."""
        steps = cls.mermaid_start_state()
        steps.extend(cls.mermaid_diagram_steps())
        steps.extend(cls.mermaid_terminal_states())
        return steps

    @classmethod
    def mermaid_diagram_steps(cls) -> list[str]:
        """
        Generate a list of steps for the Mermaid diagram.
        """
        steps = []
        for event, (from_status, to_status) in cls.EVENT_TRANSITIONS.items():
            # Get the event display name for the transition label
            event_display = str(event.label)
            from_state = from_status.value
            to_state = to_status.value

            steps.append(f"{from_state} --> {to_state} : {event_display}")

        return steps

    @classmethod
    def mermaid_start_state(cls) -> list[str]:
        """Get the start state for the Mermaid diagram."""
        return [f"[*] --> {state.value}" for state in cls.get_start_states()]

    @classmethod
    def mermaid_terminal_states(cls) -> list[str]:
        """Get the terminal states for the Mermaid diagram."""
        return [f"{state.value} --> [*]" for state in cls.get_terminal_states()]


# Type aliases for backward compatibility
JobTransitions = Lifecycle


class WorkflowEntity(Protocol):
    """Protocol that defines the interface required for an entity to work with lifecycle transitions."""

    status: EntityStatus
    finished_at: Any
    id: Any
    name: str


T = TypeVar("T", bound=WorkflowEntity)


class EntityLifecycle:
    """
    Generic lifecycle manager for workflow entities like Job and Case.
    Handles state transitions according to defined business rules.
    """

    @staticmethod
    def transition(entity: T, to_status: EntityStatus) -> tuple[bool, str]:
        """
        Transition an entity to a new status if the transition is valid.

        Args:
            entity: The entity object to transition (Job, Case, etc.)
            to_status: The target EntityStatus to transition to

        Returns:
            tuple[bool, str]: (True, "") if transition was successful,
                             (False, "error explanation") otherwise

        Side effects:
            - Updates the entity status
            - Records the finished time if the entity is in a terminal state

        Tested in apps.sv_entities.tests.test_lifecycle
        """
        current_status = entity.status

        # Check if transition is valid
        if not Lifecycle.can_transition(current_status, to_status):
            error_msg = (
                f"Invalid transition: {current_status} → {to_status} "
                f"for {entity.__class__.__name__} {entity.id} ({entity.name})"
            )
            log.warning(error_msg)
            return False, error_msg

        # Log the transition
        reason = Lifecycle.get_transition_reason(current_status, to_status)
        log.info(
            f"{entity.__class__.__name__} {entity.id} ({entity.name}) "
            f"transitioning: {current_status} → {to_status}. Reason: {reason}"
        )

        # Update the entity status
        entity.status = to_status

        # If transitioning to a terminal state, record the finished time
        if to_status in [
            EntityStatus.COMPLETED,
            EntityStatus.CANCELLED,
            EntityStatus.FAILED,
        ]:
            if not entity.finished_at:
                entity.finished_at = datetime.now()

        return True, ""

    @staticmethod
    def handle_event(entity: T, event: EntityEvents) -> tuple[bool, str]:
        """
        Handle an event by transitioning the entity to the appropriate status.

        Args:
            entity: The entity object to transition
            event: The event that occurred

        Returns:
            tuple[bool, str]: (True, "") if handling was successful,
                             (False, "error explanation") otherwise
        """
        current_status = entity.status
        to_status = Lifecycle.get_status_from_event(current_status, event)

        if not to_status:
            error_msg = (
                f"Invalid event {event} for current status {current_status} "
                f"in {entity.__class__.__name__} {entity.id} ({entity.name})"
            )
            log.warning(error_msg)
            return False, error_msg

        return EntityLifecycle.transition(entity, to_status)
