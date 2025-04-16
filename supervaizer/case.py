# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.


from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional
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
    question: Optional[Dict[str, Any]] = None

    def __init__(
        self,
        cost: float | None = None,
        name: str | None = None,
        payload: Dict[str, Any] | None = None,
        is_final: bool = False,
        question: Dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            cost=cost,
            name=name,
            payload=payload,
            is_final=is_final,
            question=question,
        )

    @property
    def registration_info(self) -> Dict[str, Any]:
        """Returns registration info for the case node update"""
        return {
            "index": self.index,
            "cost": self.cost,
            "payload": self.payload,
            "is_final": self.is_final,
            "question": self.question,
        }


class CaseNode(SvBaseModel):
    name: str
    description: str
    type: str

    @property
    def registration_info(self) -> Dict[str, Any]:
        """Returns registration info for the case node"""
        return {
            "name": self.name,
            "description": self.description,
            "type": self.type,
        }


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
        log.info(f"[Update case] {self.id} with update {update}")
        update.index = len(self.updates) + 1
        self.account.send_update_case(self, update)
        self.updates.append(update)

    def human_input(
        self, updateCaseNode: CaseNodeUpdate, message: str, **kwargs: Any
    ) -> None:
        log.info(f"[Update case] {self.id} with update {updateCaseNode}")
        updateCaseNode.index = len(self.updates) + 1
        self.account.send_update_case(self, updateCaseNode)
        self.updates.append(updateCaseNode)

    def resume(self, **kwargs: Any) -> None:
        pass

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
            f"[Close case] {self.id} with result {case_result} - Case cost is {self.total_cost}"
        )
        self.status = CaseStatus.COMPLETED
        update = CaseNodeUpdate(
            payload=case_result,
            is_final=True,
        )
        self.final_delivery = case_result
        self.account.send_update_case(self, update)

    @property
    def registration_info(self) -> Dict[str, Any]:
        """Returns registration info for the case"""
        return {
            "case_id": self.id,
            "job_id": self.job_id,
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
        case_id: str = str(uuid4()),
    ) -> "Case":
        """
        Start a new case

        Args:
            case_id (str): The id of the case
            job_id (str): The id of the job
            name (str): The name of the case
            account (Account): The account
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
        log.info(f"[Case created] {case.id}")

        # Send case startvent to Supervaize SaaS.
        account.send_start_case(case=case)

        return case
