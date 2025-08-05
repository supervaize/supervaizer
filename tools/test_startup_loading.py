#!/usr/bin/env python3
# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""
Test script to verify startup loading of running entities.

This script:
1. Creates test jobs and cases in running states
2. Persists them to storage
3. Simulates server restart by clearing registries
4. Tests the load_running_entities_on_startup function
5. Verifies entities are loaded correctly
"""

import sys
from pathlib import Path
import tempfile
import os

# Add the src directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from datetime import datetime

from supervaizer.account import Account
from supervaizer.case import Case, Cases
from supervaizer.job import Job, JobContext, Jobs
from supervaizer.lifecycle import EntityStatus
from supervaizer.storage import StorageManager, load_running_entities_on_startup


def test_startup_loading():
    """Test the startup loading functionality."""
    print("=== Testing Startup Loading ===")

    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = os.path.join(temp_dir, "test_entities.json")
        storage = StorageManager(db_path=db_path)

        # Clear registries to start fresh
        Jobs().__init__()
        Cases().__init__()

        print(f"Using temporary database: {db_path}")

        # Step 1: Create test entities in running states
        print("\n1. Creating test entities...")

        # Create job context
        job_context = JobContext(
            workspace_id="test-workspace",
            job_id="test-job-running",
            started_by="test-user",
            started_at=datetime.now(),
            mission_id="test-mission",
            mission_name="Test Mission",
        )

        # Create jobs in different states
        running_job = Job.model_construct(
            id="test-job-running",
            name="Running Job",
            agent_name="test-agent",
            status=EntityStatus.IN_PROGRESS,
            job_context=job_context,
            case_ids=[],
        )

        awaiting_job = Job.model_construct(
            id="test-job-awaiting",
            name="Awaiting Job",
            agent_name="test-agent",
            status=EntityStatus.AWAITING,
            job_context=job_context,
            case_ids=[],
        )

        completed_job = Job.model_construct(
            id="test-job-completed",
            name="Completed Job",
            agent_name="test-agent",
            status=EntityStatus.COMPLETED,
            job_context=job_context,
            case_ids=[],
        )

        # Save jobs directly to storage (bypassing registries)
        storage.save_object("Job", running_job.to_dict)
        storage.save_object("Job", awaiting_job.to_dict)
        storage.save_object("Job", completed_job.to_dict)

        # Create account for cases
        account = Account(
            workspace_id="test-workspace",
            api_key="test-api-key",
            api_url="https://test.api.url",
        )

        # Create cases in different states
        running_case = Case.model_construct(
            id="test-case-running",
            job_id="test-job-running",
            name="Running Case",
            account=account,
            description="Running case description",
            status=EntityStatus.IN_PROGRESS,
            nodes=[],
            updates=[],
        )

        cancelling_case = Case.model_construct(
            id="test-case-cancelling",
            job_id="test-job-running",
            name="Cancelling Case",
            account=account,
            description="Cancelling case description",
            status=EntityStatus.CANCELLING,
            nodes=[],
            updates=[],
        )

        failed_case = Case.model_construct(
            id="test-case-failed",
            job_id="test-job-completed",
            name="Failed Case",
            account=account,
            description="Failed case description",
            status=EntityStatus.FAILED,
            nodes=[],
            updates=[],
        )

        # Save cases directly to storage (bypassing registries)
        storage.save_object("Case", running_case.to_dict)
        storage.save_object("Case", cancelling_case.to_dict)
        storage.save_object("Case", failed_case.to_dict)

        print("Created 3 jobs and 3 cases in storage")

        # Step 2: Clear registries to simulate restart
        print("\n2. Simulating server restart (clearing registries)...")
        Jobs().__init__()
        Cases().__init__()

        # Verify registries are empty
        all_jobs = []
        for agent_jobs in Jobs().jobs_by_agent.values():
            all_jobs.extend(agent_jobs.values())

        all_cases = []
        for job_cases in Cases().cases_by_job.values():
            all_cases.extend(job_cases.values())

        print(f"Registries cleared - Jobs: {len(all_jobs)}, Cases: {len(all_cases)}")

        # Step 3: Test loading function
        print("\n3. Testing load_running_entities_on_startup()...")
        load_running_entities_on_startup()

        # Step 4: Verify results
        print("\n4. Verifying loaded entities...")

        # Check loaded jobs
        loaded_jobs = []
        for agent_jobs in Jobs().jobs_by_agent.values():
            loaded_jobs.extend(agent_jobs.values())

        loaded_cases = []
        for job_cases in Cases().cases_by_job.values():
            loaded_cases.extend(job_cases.values())

        print(f"Loaded {len(loaded_jobs)} jobs and {len(loaded_cases)} cases")

        # Verify only running entities were loaded
        expected_running_jobs = 2  # IN_PROGRESS and AWAITING
        expected_running_cases = 2  # IN_PROGRESS and CANCELLING

        assert len(loaded_jobs) == expected_running_jobs, (
            f"Expected {expected_running_jobs} jobs, got {len(loaded_jobs)}"
        )
        assert len(loaded_cases) == expected_running_cases, (
            f"Expected {expected_running_cases} cases, got {len(loaded_cases)}"
        )

        # Verify specific entities
        loaded_job_ids = [job.id for job in loaded_jobs]
        loaded_case_ids = [case.id for case in loaded_cases]

        assert "test-job-running" in loaded_job_ids, "Running job not loaded"
        assert "test-job-awaiting" in loaded_job_ids, "Awaiting job not loaded"
        assert "test-job-completed" not in loaded_job_ids, (
            "Completed job should not be loaded"
        )

        assert "test-case-running" in loaded_case_ids, "Running case not loaded"
        assert "test-case-cancelling" in loaded_case_ids, "Cancelling case not loaded"
        assert "test-case-failed" not in loaded_case_ids, (
            "Failed case should not be loaded"
        )

        # Verify statuses
        running_status_values = [
            status.value
            for status in [
                EntityStatus.IN_PROGRESS,
                EntityStatus.CANCELLING,
                EntityStatus.AWAITING,
            ]
        ]

        for job in loaded_jobs:
            status_value = (
                job.status if isinstance(job.status, str) else job.status.value
            )
            assert status_value in running_status_values, (
                f"Job {job.id} has non-running status: {status_value}"
            )

        for case in loaded_cases:
            status_value = (
                case.status if isinstance(case.status, str) else case.status.value
            )
            assert status_value in running_status_values, (
                f"Case {case.id} has non-running status: {status_value}"
            )

        print("✅ All verification checks passed!")

        print("\n5. Entity details:")
        for job in loaded_jobs:
            print(f"  Job: {job.id} (status: {job.status}, agent: {job.agent_name})")

        for case in loaded_cases:
            print(f"  Case: {case.id} (status: {case.status}, job: {case.job_id})")

    print("\n✅ Startup loading test completed successfully!")


if __name__ == "__main__":
    test_startup_loading()
