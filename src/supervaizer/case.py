# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.


from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import shortuuid
from pydantic import ConfigDict

from supervaizer.common import SvBaseModel, log, singleton
from supervaizer.lifecycle import EntityEvents, EntityLifecycle, EntityStatus

if TYPE_CHECKING:
    from supervaizer.account import Account


class CaseNodeUpdate(SvBaseModel):
    """
    CaseNodeUpdate is a class that represents an update to a case node.


    Returns:
        CaseNodeUpdate: CaseNodeUpdate object
    """

    index: int | None = None  # added in Case.update
    cost: float | None = None
    name: str | None = None
    # Todo: test with non-serializable objects. Make sure it works.
    payload: Optional[Dict[str, Any]] = None
    is_final: bool = False
    error: Optional[str] = None

    def __init__(
        self,
        cost: float | None = None,
        name: str | None = None,
        payload: Dict[str, Any] | None = None,
        is_final: bool = False,
        index: int | None = None,
        error: Optional[str] = None,
    ) -> None:
        """Initialize a CaseNodeUpdate.

        Args:
            cost (float): Cost of the update
            name (str): Name of the update
            payload (Dict[str, Any]): Additional data for the update - when a question is requested to the user, the payload is the question
            is_final (bool): Whether this is the final update. Default to False
            index (int): Index of the node to update. This is set by Case.update()

            error (Optional[str]): Error message if any. Default to None

        When payload contains a question (supervaizer_form):
            payload = {
                "supervaizer_form": {
                    "question": str,  # The question to ask
                    "answer": {
                        "fields": [
                            {
                                "name": str,        # Field name
                                "description": str, # Field description
                                "type": type,      # Field type (e.g. bool)
                                "field_type": str, # Field type name (e.g. "BooleanField")
                                "required": bool   # Whether field is required
                            },
                            # ... additional fields
                        ]
                    }
                }
            }

        Returns:
            CaseNodeUpdate: CaseNodeUpdate object
        """
        # Use model_construct rather than passing arguments to __init__
        values = {
            "cost": cost,
            "name": name,
            "payload": payload,
            "is_final": is_final,
            "index": index,
            "error": error,
        }
        object.__setattr__(self, "__dict__", {})
        object.__setattr__(self, "__pydantic_fields_set__", set())
        object.__setattr__(self, "__pydantic_extra__", None)
        object.__setattr__(self, "__pydantic_private__", None)

        # Update the model fields without calling the SvBaseModel.__init__
        for key, value in values.items():
            setattr(self, key, value)

    @property
    def registration_info(self) -> Dict[str, Any]:
        """Returns registration info for the case node update"""
        return {
            "index": self.index,
            "name": self.name,
            "error": self.error,
            "cost": self.cost,
            "payload": self.payload,
            "is_final": self.is_final,
        }


class CaseNoteType(Enum):
    """
    CaseNoteType is an enum that represents the type of a case note.
    """

    CHAT = "chat"
    TRIGGER = "trigger"
    NOTIFICATION = "notification"
    VALIDATION = "validation"
    DELIVERY = "delivery"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class CaseNode(SvBaseModel):
    name: str
    description: str
    type: CaseNoteType

    class Config:
        arbitrary_types_allowed = True

    @property
    def registration_info(self) -> Dict[str, Any]:
        """Returns registration info for the case node"""
        return {
            "name": self.name,
            "description": self.description,
            "type": self.type.value,
        }


class AbstractModel(SvBaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    id: str
    job_id: str
    name: str
    account: "Account"  # type: ignore
    description: str
    status: EntityStatus
    nodes: List[CaseNode] = []
    updates: List[CaseNodeUpdate] = []
    total_cost: float = 0.0
    final_delivery: Optional[Dict[str, Any]] = None
    finished_at: Optional[datetime] = None


class Case(AbstractModel):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        # Register the case in the global registry
        Cases().add_case(self)

    @property
    def uri(self) -> str:
        return f"case:{self.id}"

    @property
    def case_ref(self) -> str:
        return f"{self.job_id}-{self.id}"

    @property
    def calculated_cost(self) -> float:
        return sum(update.cost or 0.0 for update in self.updates)

    def update(self, updateCaseNode: CaseNodeUpdate, **kwargs: Any) -> None:
        updateCaseNode.index = len(self.updates) + 1
        if updateCaseNode.error:
            EntityLifecycle.handle_event(self, EntityEvents.ERROR_ENCOUNTERED)
            assert self.status == EntityStatus.FAILED  # Just to be sure
        self.account.send_update_case(self, updateCaseNode)
        self.updates.append(updateCaseNode)

    def request_human_input(
        self, updateCaseNode: CaseNodeUpdate, message: str, **kwargs: Any
    ) -> None:
        updateCaseNode.index = len(self.updates) + 1
        log.info(
            f"[Update case human_input] CaseRef {self.case_ref} with update {updateCaseNode}"
        )
        self.account.send_update_case(self, updateCaseNode)
        EntityLifecycle.handle_event(self, EntityEvents.AWAITING_ON_INPUT)
        self.updates.append(updateCaseNode)

    def receive_human_input(self, **kwargs: Any) -> None:
        # Transition from AWAITING to IN_PROGRESS
        EntityLifecycle.handle_event(self, EntityEvents.INPUT_RECEIVED)

    def close(
        self,
        case_result: Dict[str, Any],
        final_cost: Optional[float] = None,
        **kwargs: Any,
    ) -> None:
        """
        Close the case and send the final update to the account.
        """
        if final_cost:
            self.total_cost = final_cost
        else:
            self.total_cost = self.calculated_cost
        log.info(
            f"[Close case] CaseRef {self.case_ref} with result {case_result} - Case cost is {self.total_cost}"
        )
        # Transition from IN_PROGRESS to COMPLETED
        EntityLifecycle.handle_event(self, EntityEvents.SUCCESSFULLY_DONE)

        update = CaseNodeUpdate(
            payload=case_result,
            is_final=True,
        )
        update.index = len(self.updates) + 1

        self.final_delivery = case_result
        self.finished_at = datetime.now()
        self.account.send_update_case(self, update)

    @property
    def registration_info(self) -> Dict[str, Any]:
        """Returns registration info for the case"""
        return {
            "case_id": self.id,
            "job_id": self.job_id,
            "case_ref": self.case_ref,
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "nodes": [node.registration_info for node in self.nodes],
            "updates": [update.registration_info for update in self.updates],
            "total_cost": self.total_cost,
            "final_delivery": self.final_delivery,
        }

    @classmethod
    def start(
        cls,
        job_id: str,
        name: str,
        account: "Account",
        description: str,
        nodes: List[CaseNode],
        case_id: Optional[str] = None,
    ) -> "Case":
        """
        Start a new case

        Args:
            case_id (str): The id of the case - should be unique for the job. If not provided, a shortuuid will be generated.
            job_id (str): The id of the job
            name (str): The name of the case
            account (Account): The account
            description (str): The description of the case
            nodes (list[CaseNode]): The nodes of the case

        Returns:
            Case: The case
        """

        case = cls(
            id=case_id or shortuuid.uuid(),
            job_id=job_id,
            account=account,
            name=name,
            description=description,
            status=EntityStatus.STOPPED,
            nodes=nodes,
        )
        log.info(f"[Case created] {case.id}")

        # Transition from STOPPED to IN_PROGRESS
        EntityLifecycle.handle_event(case, EntityEvents.START_WORK)

        # Send case startvent to Supervaize SaaS.
        account.send_start_case(case=case)

        return case


@singleton
class Cases:
    """Global registry for all cases, organized by job."""

    def __init__(self) -> None:
        # Structure: {job_id: {case_id: Case}}
        self.cases_by_job: dict[str, dict[str, "Case"]] = {}

    def add_case(self, case: "Case") -> None:
        """Add a case to the registry under its job

        Args:
            case (Case): The case to add

        Raises:
            ValueError: If case with same ID already exists for this job
        """
        job_id = case.job_id

        # Initialize job's case dict if not exists
        if job_id not in self.cases_by_job:
            self.cases_by_job[job_id] = {}

        # Check if case already exists for this job
        if case.id in self.cases_by_job[job_id]:
            raise ValueError(f"Case ID '{case.id}' already exists for job {job_id}")

        self.cases_by_job[job_id][case.id] = case

    def get_case(self, case_id: str, job_id: str | None = None) -> "Case | None":
        """Get a case by its ID and optionally job ID

        Args:
            case_id (str): The ID of the case to get
            job_id (str | None): The ID of the job. If None, searches all jobs.

        Returns:
            Case | None: The case if found, None otherwise
        """
        if job_id:
            # Search in specific job's cases
            return self.cases_by_job.get(job_id, {}).get(case_id)

        # Search across all jobs
        for job_cases in self.cases_by_job.values():
            if case_id in job_cases:
                return job_cases[case_id]
        return None

    def get_job_cases(self, job_id: str) -> dict[str, "Case"]:
        """Get all cases for a specific job

        Args:
            job_id (str): The ID of the job

        Returns:
            dict[str, Case]: Dictionary of cases for this job, empty if job not found
        """
        return self.cases_by_job.get(job_id, {})

    def __contains__(self, case_id: str) -> bool:
        """Check if case exists in any job's registry"""
        return any(case_id in cases for cases in self.cases_by_job.values())
