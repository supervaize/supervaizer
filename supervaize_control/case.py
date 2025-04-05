# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License,
# v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at https://mozilla.org/MPL/2.0/.

from enum import Enum
from typing import TYPE_CHECKING, Dict, List, Any, Optional
from uuid import uuid4

from pydantic import ConfigDict

from .common import SvBaseModel, log

if TYPE_CHECKING:
    from .account import Account


class CaseStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class CaseNodeUpdate(SvBaseModel):
    cost: float | None = None
    # Todo: test with non-serializable objects. Make sure it works.
    payload: Optional[Dict[str, Any]] = None
    is_final: bool = False
    question: Optional[Dict[str, Any]] = None


class CaseNode(SvBaseModel):
    name: str
    description: str
    type: str


class CaseModel(SvBaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    id: str
    job_id: str
    name: str
    account: "Account"  # type: ignore
    description: str
    status: CaseStatus
    nodes: List[CaseNode] = []
    updates: List[CaseNodeUpdate] = []
    total_cost: float = 0.0
    final_delivery: Optional[Dict[str, Any]] = None


class Case(CaseModel):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

    @property
    def uri(self) -> str:
        return f"case:{self.id}"

    @property
    def calculated_cost(self) -> float:
        return sum(update.cost or 0.0 for update in self.updates)

    def update(self, update: CaseNodeUpdate, **kwargs: Any) -> None:
        log.info(f"CONTROLLER : Updating case {self.id} with update {update}")
        self.account.send_update_case(self, update)
        self.updates.append(update)

    def human_input(self, update: CaseNodeUpdate, message: str, **kwargs: Any) -> None:
        log.info(f"CONTROLLER : Updating case {self.id} with update {update}")
        self.account.send_update_case(self, update)
        self.updates.append(update)

    def resume(self, **kwargs: Any) -> None:
        pass

    def close(
        self, case_result: Dict[str, Any], final_cost: Optional[float], **kwargs: Any
    ) -> None:
        """
        Close the case and send the final update to the account.
        """
        if final_cost:
            self.total_cost = final_cost
        else:
            self.total_cost = self.calculated_cost
        log.info(
            f"CONTROLLER : Closing case {self.id} with result {case_result} - Case cost is {self.total_cost}"
        )
        self.status = CaseStatus.COMPLETED
        update = CaseNodeUpdate(
            payload=case_result,
            is_final=True,
        )
        self.final_delivery = case_result
        self.account.send_update_case(self, update)

    @classmethod
    def start(
        cls,
        job_id: str,
        account: "Account",
        name: str,
        description: str,
        nodes: List[CaseNode],
        case_id: str = str(uuid4()),
    ) -> "Case":
        """
        Start a new case

        Args:
            case_id (str): The id of the case
            job_id (str): The id of the job
            account (Account): The account
            name (str): The name of the case
            description (str): The description of the case
            nodes (list[CaseNode]): The nodes of the case

        Returns:
            Case: The case
        """

        case = cls(
            id=case_id,
            job_id=job_id,
            account=account,
            name=name,
            description=description,
            status=CaseStatus.IN_PROGRESS,
            nodes=nodes,
        )
        log.info(f"CONTROLLER : Case {case.id} created")

        # Send case startvent to Supervaize SaaS.
        account.send_start_case(case=case)

        return case
