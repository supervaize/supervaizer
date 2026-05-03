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


from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import shortuuid
from pydantic import ConfigDict, Field
from supervaizer.common import ApiResult, SvBaseModel, log, singleton
from supervaizer.lifecycle import EntityEvents, EntityStatus
from supervaizer.storage import PersistentEntityLifecycle, StorageManager

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
    upsert: bool = False  # if True, Studio updates the existing step at the same index instead of creating a new one
    error: Optional[str] = None
    scheduled_at: datetime | None = None  # When to execute (UTC)
    scheduled_method: str | None = None  # Agent method dotted path
    scheduled_params: Optional[Dict[str, Any]] = None  # Params for the method
    scheduled_status: str | None = (
        None  # pending, executing, completed, failed, cancelled
    )

    def __init__(
        self,
        cost: float | None = None,
        name: str | None = None,
        payload: Dict[str, Any] | None = None,
        is_final: bool = False,
        upsert: bool = False,
        index: int | None = None,
        error: Optional[str] = None,
        scheduled_at: datetime | None = None,
        scheduled_method: str | None = None,
        scheduled_params: Dict[str, Any] | None = None,
        scheduled_status: str | None = None,
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
            "upsert": upsert,
            "index": index,
            "error": error,
            "scheduled_at": scheduled_at,
            "scheduled_method": scheduled_method,
            "scheduled_params": scheduled_params,
            "scheduled_status": scheduled_status,
        }
        object.__setattr__(self, "__dict__", {})
        object.__setattr__(self, "__pydantic_fields_set__", set())
        object.__setattr__(self, "__pydantic_extra__", None)
        object.__setattr__(self, "__pydantic_private__", None)

        # Update the model fields without calling the SvBaseModel.__init__
        for key, value in values.items():
            setattr(self, key, value)

    @property
    def is_scheduled(self) -> bool:
        return self.scheduled_at is not None

    @property
    def registration_info(self) -> Dict[str, Any]:
        """Returns registration info for the case node update"""
        # Serialize payload to convert type objects to strings for JSON serialization
        serialized_payload = (
            self.serialize_value(self.payload) if self.payload else None
        )
        info = {
            "index": self.index,
            "name": self.name,
            "error": self.error,
            "cost": self.cost,
            "payload": serialized_payload,
            "is_final": self.is_final,
            "upsert": self.upsert,
        }
        if self.scheduled_at:
            info["scheduled_at"] = self.scheduled_at.isoformat()
        if self.scheduled_method:
            info["scheduled_method"] = self.scheduled_method
        if self.scheduled_status:
            info["scheduled_status"] = self.scheduled_status
        return info


class CaseNodeType(Enum):
    """
    CaseNodeType is an enum that represents the type of a case note.
    """

    CHAT = "chat"
    TRIGGER = "trigger"
    NOTIFICATION = "notification"
    STATUS_UPDATE = "status_update"
    INTERMEDIARY_DELIVERY = "intermediary_delivery"
    HITL = "human_in_the_loop"
    DELIVERABLE = "deliverable"
    VALIDATION = "validation"
    DELIVERY = "delivery"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class CaseNode(SvBaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    type: CaseNodeType
    # Runtime type is ``Callable[..., CaseNodeUpdate] | None``. Declared as ``Any`` so Pydantic JSON
    # Schema / FastAPI OpenAPI never emit ``CallableSchema`` (SkipJsonSchema on Callable is not
    # enough for $ref / definitions generation in Pydantic 2.12+).
    factory: Any = None
    description: str = ""
    can_be_confirmed: bool = False

    def __call__(self, *args: Any, **kwargs: Any) -> CaseNodeUpdate:
        """Make it callable directly."""
        if self.factory is None:
            raise ValueError("CaseNode factory is not set")
        return self.factory(*args, **kwargs)

    @property
    def registration_info(self) -> Dict[str, Any]:
        """Returns registration info for the case node"""
        return {
            "name": self.name,
            "type": self.type.value,
            "description": self.description,
            "can_be_confirmed": self.can_be_confirmed,
        }


class CaseNodes(SvBaseModel):
    nodes: List[CaseNode] = []

    def get(self, name: str) -> CaseNode | None:
        return next((node for node in self.nodes if node.name == name), None)

    def node_index(self, name: str, *, start: int = 1) -> int:
        """Return the stable 1-based index for a named case node."""
        for offset, node in enumerate(self.nodes):
            if node.name == name:
                return start + offset
        raise ValueError(f"Case node {name!r} not found")

    def make_update(
        self,
        name: str,
        *,
        payload: Dict[str, Any] | None = None,
        cost: float = 0.0,
        is_final: bool = False,
        upsert_to: str | None = None,
    ) -> CaseNodeUpdate:
        """Build a CaseNodeUpdate with an index derived from this node set."""
        target_name = upsert_to or name
        return CaseNodeUpdate(
            name=name,
            cost=cost,
            payload=payload or {},
            is_final=is_final,
            index=self.node_index(target_name),
            upsert=upsert_to is not None,
        )

    @property
    def registration_info(self) -> Dict[str, Any]:
        """Returns registration info for the case nodes"""
        return {
            "nodes": [node.registration_info for node in self.nodes],
        }


class CaseAbstractModel(SvBaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    id: str
    job_id: str
    name: str
    account: "Account"
    description: str
    status: EntityStatus
    updates: List[CaseNodeUpdate] = []
    total_cost: float = 0.0
    final_delivery: Optional[Dict[str, Any]] = None
    finished_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Agent-provided domain metadata (e.g. contact context)",
    )


class Case(CaseAbstractModel):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        # Register the case in the global registry
        Cases().add_case(self)
        # Persist case to storage
        from supervaizer.storage import StorageManager

        storage = StorageManager()
        storage.save_object("Case", self.to_dict)

    @property
    def uri(self) -> str:
        return f"case:{self.id}"

    @property
    def case_ref(self) -> str:
        return f"{self.job_id}-{self.id}"

    @property
    def calculated_cost(self) -> float:
        return sum(update.cost or 0.0 for update in self.updates)

    def _prepare_update(self, update: CaseNodeUpdate) -> None:
        update.index = len(self.updates) + 1
        if update.error:
            success, error = PersistentEntityLifecycle.handle_event(
                self, EntityEvents.ERROR_ENCOUNTERED
            )
            log.warning(
                f"[Case update] CaseRef {self.case_ref} has error {update.error}"
            )
            assert self.status == EntityStatus.FAILED  # Just to be sure

    def _persist(self) -> None:
        storage = StorageManager()
        storage.save_object("Case", self.to_dict)

    async def update(self, updateCaseNode: CaseNodeUpdate, **kwargs: Any) -> None:
        self._prepare_update(updateCaseNode)
        await self.account.send_update_case(self, updateCaseNode)
        self.updates.append(updateCaseNode)
        self._persist()

    def update_sync(self, updateCaseNode: CaseNodeUpdate, **kwargs: Any) -> None:
        self._prepare_update(updateCaseNode)
        self.account.send_update_case_sync(self, updateCaseNode)
        self.updates.append(updateCaseNode)
        self._persist()

    async def patch_step(self, index: int, updateCaseNode: CaseNodeUpdate) -> None:
        """Update an existing step at the given index instead of appending a new one.

        Sets upsert=True so Studio performs an update_or_create on the step at that index.
        Use this when a later event should enrich or complete a previously sent step
        (e.g. adding interview end time to the interview start step).
        """
        updateCaseNode.index = index
        updateCaseNode.upsert = True
        await self.account.send_update_case(self, updateCaseNode)
        # Update the matching entry in the in-memory registry
        for i, existing in enumerate(self.updates):
            if existing.index == index:
                self.updates[i] = updateCaseNode
                break
        self._persist()

    def patch_step_sync(self, index: int, updateCaseNode: CaseNodeUpdate) -> None:
        """Sync entry point for updating an existing step."""
        updateCaseNode.index = index
        updateCaseNode.upsert = True
        self.account.send_update_case_sync(self, updateCaseNode)
        for i, existing in enumerate(self.updates):
            if existing.index == index:
                self.updates[i] = updateCaseNode
                break
        self._persist()

    async def request_human_input(
        self, updateCaseNode: CaseNodeUpdate, message: str, **kwargs: Any
    ) -> None:
        updateCaseNode.index = len(self.updates) + 1
        log.debug(
            f"[Update case human_input] CaseRef {self.case_ref} with update {updateCaseNode}"
        )
        await self.account.send_update_case(self, updateCaseNode)
        from supervaizer.storage import PersistentEntityLifecycle

        PersistentEntityLifecycle.handle_event(self, EntityEvents.AWAITING_ON_INPUT)
        self.updates.append(updateCaseNode)
        self._persist()

    def request_human_input_sync(
        self, updateCaseNode: CaseNodeUpdate, message: str, **kwargs: Any
    ) -> None:
        updateCaseNode.index = len(self.updates) + 1
        log.debug(
            f"[Update case human_input] CaseRef {self.case_ref} with update {updateCaseNode}"
        )
        self.account.send_update_case_sync(self, updateCaseNode)
        from supervaizer.storage import PersistentEntityLifecycle

        PersistentEntityLifecycle.handle_event(self, EntityEvents.AWAITING_ON_INPUT)
        self.updates.append(updateCaseNode)
        self._persist()

    async def receive_human_input(
        self, updateCaseNode: CaseNodeUpdate, **kwargs: Any
    ) -> None:
        # Add the update to the case (this handles index, send_update_case, and persistence)
        await self.update(updateCaseNode)
        # Transition from AWAITING to IN_PROGRESS
        from supervaizer.storage import PersistentEntityLifecycle

        PersistentEntityLifecycle.handle_event(self, EntityEvents.INPUT_RECEIVED)

    def receive_human_input_sync(
        self, updateCaseNode: CaseNodeUpdate, **kwargs: Any
    ) -> None:
        self.update_sync(updateCaseNode)
        from supervaizer.storage import PersistentEntityLifecycle

        PersistentEntityLifecycle.handle_event(self, EntityEvents.INPUT_RECEIVED)

    def _prepare_close(
        self,
        case_result: Dict[str, Any],
        final_cost: Optional[float] = None,
    ) -> CaseNodeUpdate:
        if final_cost:
            self.total_cost = final_cost
        else:
            self.total_cost = self.calculated_cost
        log.info(
            f"[Close case] CaseRef {self.case_ref} with result {case_result} - Case cost is {self.total_cost}"
        )
        # Transition from IN_PROGRESS to COMPLETED
        from supervaizer.storage import PersistentEntityLifecycle

        PersistentEntityLifecycle.handle_event(self, EntityEvents.SUCCESSFULLY_DONE)

        update = CaseNodeUpdate(
            payload=case_result,
            is_final=True,
        )
        update.index = len(self.updates) + 1

        self.final_delivery = case_result
        self.finished_at = datetime.now()
        return update

    async def close(
        self,
        case_result: Dict[str, Any],
        final_cost: Optional[float] = None,
        **kwargs: Any,
    ) -> None:
        """
        Close the case and send the final update to the account.
        """
        update = self._prepare_close(case_result, final_cost)
        await self.account.send_update_case(self, update)
        self._persist()

    def close_sync(
        self,
        case_result: Dict[str, Any],
        final_cost: Optional[float] = None,
        **kwargs: Any,
    ) -> None:
        update = self._prepare_close(case_result, final_cost)
        self.account.send_update_case_sync(self, update)
        self._persist()

    def cancel_scheduled_steps(self) -> None:
        """Cancel all pending scheduled steps for this case."""
        for update in self.updates:
            if (
                getattr(update, "scheduled_at", None) is not None
                and getattr(update, "scheduled_status", None) == "pending"
            ):
                object.__setattr__(update, "scheduled_status", "cancelled")

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
            "updates": [update.registration_info for update in self.updates],
            "total_cost": self.total_cost,
            "final_delivery": self.final_delivery,
            "metadata": SvBaseModel.serialize_value(self.metadata),
        }

    @classmethod
    def _create_started_case(
        cls,
        job_id: str,
        name: str,
        account: "Account",
        description: str,
        case_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "Case":
        case = cls(
            id=case_id or shortuuid.uuid(),
            job_id=job_id,
            account=account,
            name=name,
            description=description,
            status=EntityStatus.STOPPED,
            metadata=metadata or {},
        )
        log.info(f"[Case created] {case.id}")

        # Add case to job's case_ids for foreign key relationship
        from supervaizer.job import Jobs

        job = Jobs().get_job(job_id)
        if job:
            job.add_case_id(case.id)

        # Transition from STOPPED to IN_PROGRESS

        PersistentEntityLifecycle.handle_event(case, EntityEvents.START_WORK)
        return case

    @staticmethod
    def _log_start_result(case: "Case", result: ApiResult | None) -> None:
        if result:
            log.debug(
                f"[Case start] Case {case.id} send to Supervaize with result {result}"
            )
        else:
            log.error(
                f"[Case start] §SCCS01 Case {case.id} failed to send to Supervaize"
            )

    @classmethod
    async def start(
        cls,
        job_id: str,
        name: str,
        account: "Account",
        description: str,
        case_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "Case":
        """
        Start a new case.
        """
        case = cls._create_started_case(
            job_id=job_id,
            name=name,
            account=account,
            description=description,
            case_id=case_id,
            metadata=metadata,
        )
        # Send case start event to Supervaize SaaS.
        result = await account.send_start_case(case=case)
        cls._log_start_result(case, result)

        return case

    @classmethod
    def start_sync(
        cls,
        job_id: str,
        name: str,
        account: "Account",
        description: str,
        case_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "Case":
        """Start a new case from sync-only contexts."""
        case = cls._create_started_case(
            job_id=job_id,
            name=name,
            account=account,
            description=description,
            case_id=case_id,
            metadata=metadata,
        )
        result = account.send_start_case_sync(case=case)
        cls._log_start_result(case, result)
        return case


@singleton
class Cases:
    """Global registry for all cases, organized by job."""

    def __init__(self) -> None:
        # Structure: {job_id: {case_id: Case}}
        self.cases_by_job: dict[str, dict[str, "Case"]] = {}

    def reset(self) -> None:
        self.cases_by_job.clear()

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

    def get_due_scheduled_steps(self) -> list[tuple]:
        """Return all steps where scheduled_at <= now() and status == 'pending'.

        Returns list of (case, step_index, update) tuples.
        """
        now = datetime.now(timezone.utc)
        due = []
        for job_cases in self.cases_by_job.values():
            for case_id, case in job_cases.items():
                for i, update in enumerate(case.updates):
                    scheduled_at = getattr(update, "scheduled_at", None)
                    scheduled_status = getattr(update, "scheduled_status", None)
                    if (
                        scheduled_at is not None
                        and scheduled_status == "pending"
                        and scheduled_at <= now
                    ):
                        due.append((case, i, update))
        return due

    def __contains__(self, case_id: str) -> bool:
        """Check if case exists in any job's registry"""
        return any(case_id in cases for cases in self.cases_by_job.values())


def rebuild_case_model_forward_refs() -> None:
    """Resolve runtime-only forward references used by Case models."""
    from supervaizer.account import Account

    Case.model_rebuild(_types_namespace={"Account": Account})


rebuild_case_model_forward_refs()
