# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from pydantic import ConfigDict

from .common import SvBaseModel, log

if TYPE_CHECKING:
    from .account import Account


class CaseStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class CaseNodeUpdate(SvBaseModel):
    timestamp: datetime
    cost: float = 0.0
    payload: dict | None = None
    is_final: bool = False
    question: dict | None = None


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
    nodes: list[CaseNode] = []
    updates: list[CaseNodeUpdate] = []


class Case(CaseModel):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def update(self, update: CaseNodeUpdate, **kwargs) -> None:
        log.info(f"CONTROLLER : Updating case {self.id} with update {update}")
        self.account.update_case(self, update)
        self.updates.append(update)

    def human_input(self, update: CaseNodeUpdate, message: str, **kwargs) -> None:
        log.info(f"CONTROLLER : Updating case {self.id} with update {update}")
        self.account.update_case(self, update)
        self.updates.append(update)

    def resume(self, **kwargs):
        pass

    def close(self, **kwargs):
        pass

    @classmethod
    def start(
        cls,
        case_id: str,
        job_id: str,
        account: "Account",
        name: str,
        description: str,
        nodes: list[CaseNode],
    ):
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
        log.info(
            f"CONTROLLER : Starting case {case_id} for job {job_id} with account {account.name}"
        )

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

        account.start_case(case=case)

        return case
