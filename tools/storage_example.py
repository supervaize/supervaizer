#!/usr/bin/env python3
# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""
Example usage of the TinyDB-based persistence layer for Supervaizer entities.

This example demonstrates:
1. Setting up the StorageManager
2. Creating and persisting Job and Case entities
3. Using EntityRepository for type-safe operations
4. Auto-persistence with PersistentEntityLifecycle
5. Loading entities from storage across sessions
"""

import os
import tempfile
from datetime import datetime
from unittest.mock import MagicMock, patch

from supervaizer.case import Case, Cases
from supervaizer.job import Job, JobContext, Jobs
from supervaizer.lifecycle import EntityEvents, EntityStatus
from supervaizer.storage import (
    PersistentEntityLifecycle,
    StorageManager,
    create_case_repository,
    create_job_repository,
)


def demo_storage_manager():
    """Demonstrate basic StorageManager operations."""
    print("=== StorageManager Demo ===")

    # Create a temporary database for demo
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = os.path.join(temp_dir, "demo_entities.json")
        storage = StorageManager(db_path=db_path)

        # Save some test objects
        job_data = {
            "id": "demo-job-1",
            "name": "Demo Job",
            "status": "in_progress",
            "case_ids": ["case-1", "case-2"],
        }

        case_data = {
            "id": "case-1",
            "job_id": "demo-job-1",
            "name": "Demo Case",
            "status": "completed",
        }

        storage.save_object("Job", job_data)
        storage.save_object("Case", case_data)

        # Retrieve objects
        retrieved_job = storage.get_object_by_id("Job", "demo-job-1")
        print(f"Retrieved job: {retrieved_job}")

        # Get all cases for a job
        job_cases = storage.get_cases_for_job("demo-job-1")
        print(f"Cases for demo-job-1: {job_cases}")

        # Get all objects of a type
        all_jobs = storage.get_objects("Job")
        print(f"All jobs: {len(all_jobs)} found")

        storage.close()


def demo_entity_repository():
    """Demonstrate EntityRepository usage."""
    print("\n=== EntityRepository Demo ===")

    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = os.path.join(temp_dir, "demo_entities.json")

        # Create repositories
        job_repo = create_job_repository()
        job_repo.storage = StorageManager(db_path=db_path)

        case_repo = create_case_repository()
        case_repo.storage = job_repo.storage  # Share same storage

        print(f"Job repository type: {job_repo.type_name}")
        print(f"Case repository type: {case_repo.type_name}")


def demo_full_workflow():
    """Demonstrate a complete workflow with Job/Case creation and persistence."""
    print("\n=== Full Workflow Demo ===")

    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = os.path.join(temp_dir, "demo_entities.json")
        storage = StorageManager(db_path=db_path)

        # Clear any existing singletons
        Jobs().__init__()
        Cases().__init__()

        # Create a job
        job_context = JobContext(
            workspace_id="demo-workspace",
            job_id="demo-job-123",
            started_by="demo-user",
            started_at=datetime.now(),
            mission_id="demo-mission",
            mission_name="Demo Mission",
        )

        job = Job(
            id="demo-job-123",
            name="Demo Job",
            agent_name="demo-agent",
            status=EntityStatus.STOPPED,
            job_context=job_context,
        )

        # Save job to storage
        print(f"Created job: {job.id}")
        storage.save_object("Job", job.to_dict)

        # Create a case with proper Account
        from supervaizer.account import Account

        account = Account(
            workspace_id="demo-workspace",
            api_key="demo-api-key",
            api_url="https://demo.api.url",
        )

        # Mock the send_event to avoid HTTP calls
        with patch("supervaizer.account_service.send_event") as mock_send:
            mock_send.return_value = MagicMock()
            case = Case.start(
                job_id="demo-job-123",
                name="Demo Case",
                account=account,
                description="Demo Case Description",
                nodes=case_nodes,
                case_id="demo-case-456",
            )

        print(f"Created case: {case.id}")
        print(f"Case job_id: {case.job_id}")
        print(f"Job case_ids: {job.case_ids}")

        # Save case to storage
        storage.save_object("Case", case.to_dict)

        # Demonstrate retrieval
        stored_job = storage.get_object_by_id("Job", "demo-job-123")
        stored_case = storage.get_object_by_id("Case", "demo-case-456")

        print(f"Stored job data: {stored_job['name']}")
        print(f"Stored case data: {stored_case['name']}")

        # Demonstrate relationship queries
        job_cases = storage.get_cases_for_job("demo-job-123")
        print(f"Cases for job: {len(job_cases)}")

        storage.close()


def demo_persistent_lifecycle():
    """Demonstrate auto-persistence with PersistentEntityLifecycle."""
    print("\n=== PersistentEntityLifecycle Demo ===")

    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = os.path.join(temp_dir, "demo_entities.json")
        storage = StorageManager(db_path=db_path)

        # Clear singletons
        Jobs().__init__()
        Cases().__init__()

        # Create a job
        job_context = JobContext(
            workspace_id="demo-workspace",
            job_id="persistent-job-123",
            started_by="demo-user",
            started_at=datetime.now(),
            mission_id="demo-mission",
            mission_name="Persistent Demo Mission",
        )

        job = Job(
            id="persistent-job-123",
            name="Persistent Demo Job",
            agent_name="demo-agent",
            status=EntityStatus.STOPPED,
            job_context=job_context,
        )

        print(f"Initial job status: {job.status}")

        # Use PersistentEntityLifecycle for automatic persistence
        success, error = PersistentEntityLifecycle.transition(
            job, EntityStatus.IN_PROGRESS, storage
        )

        print(f"Transition success: {success}")
        print(f"New job status: {job.status}")

        # Verify it was automatically persisted
        stored_job = storage.get_object_by_id("Job", "persistent-job-123")
        print(f"Stored job status: {stored_job['status']}")

        # Handle an event with auto-persistence
        success, error = PersistentEntityLifecycle.handle_event(
            job, EntityEvents.SUCCESSFULLY_DONE, storage
        )

        print(f"Event handling success: {success}")
        print(f"Final job status: {job.status}")

        # Verify the final state was persisted
        stored_job = storage.get_object_by_id("Job", "persistent-job-123")
        print(f"Final stored job status: {stored_job['status']}")

        storage.close()


def demo_data_loading():
    """Demonstrate loading entities from storage across sessions."""
    print("\n=== Data Loading Demo ===")

    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = os.path.join(temp_dir, "persistent_entities.json")

        # Session 1: Create and save entities
        print("Session 1: Creating entities...")
        storage1 = StorageManager(db_path=db_path)

        Jobs().__init__()
        Cases().__init__()

        job_context = JobContext(
            workspace_id="session-workspace",
            job_id="session-job-123",
            started_by="session-user",
            started_at=datetime.now(),
            mission_id="session-mission",
            mission_name="Session Demo Mission",
        )

        job = Job(
            id="session-job-123",
            name="Session Demo Job",
            agent_name="session-agent",
            status=EntityStatus.IN_PROGRESS,
            job_context=job_context,
        )

        storage1.save_object("Job", job.to_dict)

        from supervaizer.account import Account

        account = Account(
            workspace_id="session-workspace",
            api_key="session-api-key",
            api_url="https://session.api.url",
        )

        with patch("supervaizer.account_service.send_event") as mock_send:
            mock_send.return_value = MagicMock()
            case = Case.start(
                job_id="session-job-123",
                name="Session Demo Case",
                account=account,
                description="Session Case Description",
                nodes=[],
                case_id="session-case-456",
            )

        storage1.save_object("Case", case.to_dict)

        print(f"Saved job: {job.id}, case: {case.id}")
        storage1.close()

        # Session 2: Load entities from storage
        print("\nSession 2: Loading entities...")
        storage2 = StorageManager(db_path=db_path)

        # Clear in-memory registries to simulate fresh start
        Jobs().__init__()
        Cases().__init__()

        # Load all jobs and cases
        all_jobs = storage2.get_objects("Job")
        all_cases = storage2.get_objects("Case")

        print(f"Loaded {len(all_jobs)} jobs")
        print(f"Loaded {len(all_cases)} cases")

        for job_data in all_jobs:
            print(
                f"  Job: {job_data['id']} - {job_data['name']} ({job_data['status']})"
            )

        for case_data in all_cases:
            print(
                f"  Case: {case_data['id']} - {case_data['name']} ({case_data['status']})"
            )

        # Demonstrate relationship restoration
        for job_data in all_jobs:
            job_cases = storage2.get_cases_for_job(job_data["id"])
            print(f"  Job {job_data['id']} has {len(job_cases)} cases")

        storage2.close()


if __name__ == "__main__":
    print("Supervaizer TinyDB Persistence Demo")
    print("===================================")

    demo_storage_manager()
    demo_entity_repository()
    demo_full_workflow()
    demo_persistent_lifecycle()
    demo_data_loading()

    print("\n✅ Demo completed successfully!")
