# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, You can obtain one at
# https://mozilla.org/MPL/2.0/.

import threading
import time
from pathlib import Path
from typing import Any

import pytest
from pytest_mock import MockerFixture

from supervaizer.account import Account
from supervaizer.case import Case, Cases
from supervaizer.job import Job, JobContext, Jobs
from supervaizer.lifecycle import EntityEvents, EntityStatus
from supervaizer.storage import (
    EntityRepository,
    PersistentEntityLifecycle,
    StorageManager,
    create_case_repository,
    create_job_repository,
)


class TestStorageManager:
    """Test the StorageManager class."""

    def test_storage_manager_init(self, temp_db_path: str) -> None:
        """Test StorageManager initialization."""
        storage = StorageManager(db_path=temp_db_path)
        assert hasattr(storage, "_lock")
        assert hasattr(storage, "_db")
        assert Path(temp_db_path).parent.exists()

    def test_save_object(self, storage_manager: StorageManager) -> None:
        """Test saving an object."""
        test_obj = {"id": "test-123", "name": "Test Object", "status": "active"}

        storage_manager.save_object("TestType", test_obj)

        # Verify object was saved
        retrieved = storage_manager.get_object_by_id("TestType", "test-123")
        assert retrieved == test_obj

    def test_save_object_without_id(self, storage_manager: StorageManager) -> None:
        """Test saving an object without id raises error."""
        test_obj = {"name": "Test Object"}

        with pytest.raises(ValueError, match="Object must have an 'id' field"):
            storage_manager.save_object("TestType", test_obj)

    def test_get_objects(self, storage_manager: StorageManager) -> None:
        """Test getting all objects of a type."""
        test_objects = [
            {"id": "test-1", "name": "Object 1"},
            {"id": "test-2", "name": "Object 2"},
        ]

        for obj in test_objects:
            storage_manager.save_object("TestType", obj)

        retrieved = storage_manager.get_objects("TestType")
        assert len(retrieved) == 2
        assert retrieved[0] in test_objects
        assert retrieved[1] in test_objects

    def test_get_object_by_id(self, storage_manager: StorageManager) -> None:
        """Test getting a specific object by ID."""
        test_obj = {"id": "test-123", "name": "Test Object"}
        storage_manager.save_object("TestType", test_obj)

        retrieved = storage_manager.get_object_by_id("TestType", "test-123")
        assert retrieved == test_obj

        # Test non-existent object
        assert storage_manager.get_object_by_id("TestType", "non-existent") is None

    def test_delete_object(self, storage_manager: StorageManager) -> None:
        """Test deleting an object."""
        test_obj = {"id": "test-123", "name": "Test Object"}
        storage_manager.save_object("TestType", test_obj)

        # Verify object exists
        assert storage_manager.get_object_by_id("TestType", "test-123") is not None

        # Delete object
        result = storage_manager.delete_object("TestType", "test-123")
        assert result is True

        # Verify object is gone
        assert storage_manager.get_object_by_id("TestType", "test-123") is None

        # Test deleting non-existent object
        result = storage_manager.delete_object("TestType", "non-existent")
        assert result is False

    def test_reset_storage(self, storage_manager: StorageManager) -> None:
        """Test resetting storage."""
        # Add some test data
        storage_manager.save_object("Type1", {"id": "test-1", "name": "Object 1"})
        storage_manager.save_object("Type2", {"id": "test-2", "name": "Object 2"})

        # Verify data exists
        assert len(storage_manager.get_objects("Type1")) == 1
        assert len(storage_manager.get_objects("Type2")) == 1

        # Reset storage
        storage_manager.reset_storage()

        # Verify all data is gone
        assert len(storage_manager.get_objects("Type1")) == 0
        assert len(storage_manager.get_objects("Type2")) == 0

    def test_get_cases_for_job(self, storage_manager: StorageManager) -> None:
        """Test getting cases for a specific job."""
        cases = [
            {"id": "case-1", "job_id": "job-1", "name": "Case 1"},
            {"id": "case-2", "job_id": "job-1", "name": "Case 2"},
            {"id": "case-3", "job_id": "job-2", "name": "Case 3"},
        ]

        for case in cases:
            storage_manager.save_object("Case", case)

        job1_cases = storage_manager.get_cases_for_job("job-1")
        assert len(job1_cases) == 2
        assert all(case["job_id"] == "job-1" for case in job1_cases)

        job2_cases = storage_manager.get_cases_for_job("job-2")
        assert len(job2_cases) == 1
        assert job2_cases[0]["job_id"] == "job-2"

    def test_thread_safety(self, storage_manager: StorageManager) -> None:
        """Test thread safety of operations."""
        results = []
        errors = []

        def worker(worker_id: int) -> None:
            try:
                for i in range(10):
                    obj = {"id": f"worker-{worker_id}-{i}", "data": f"data-{i}"}
                    storage_manager.save_object("ThreadTest", obj)
                    time.sleep(0.001)  # Small delay to increase contention
                    retrieved = storage_manager.get_object_by_id(
                        "ThreadTest", obj["id"]
                    )
                    assert retrieved == obj
                results.append(f"worker-{worker_id}-success")
            except Exception as e:
                errors.append(f"worker-{worker_id}-error: {e}")

        # Start multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=worker, args=(i,))
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Check results
        assert len(errors) == 0, f"Thread safety errors: {errors}"
        assert len(results) == 5

        # Verify all objects were saved
        all_objects = storage_manager.get_objects("ThreadTest")
        assert len(all_objects) == 50  # 5 workers * 10 objects each


class TestEntityRepository:
    """Test the EntityRepository class."""

    def test_repository_init(
        self, storage_manager: StorageManager, mock_entity_class: Any
    ) -> None:
        """Test repository initialization."""
        repo = EntityRepository(mock_entity_class, storage_manager)

        assert repo.entity_class == mock_entity_class
        assert repo.type_name == "MockEntity"
        assert repo.storage == storage_manager

    def test_save_and_get_by_id(
        self, mock_entity_repository: EntityRepository, mock_entity_class: Any
    ) -> None:
        """Test saving and retrieving entities."""
        entity = mock_entity_class("test-123", "Test Entity")

        # Save entity
        mock_entity_repository.save(entity)

        # Retrieve entity
        retrieved = mock_entity_repository.get_by_id("test-123")
        assert retrieved is not None
        assert retrieved.id == entity.id
        assert retrieved.name == entity.name

    def test_get_all(
        self, mock_entity_repository: EntityRepository, mock_entity_class: Any
    ) -> None:
        """Test getting all entities."""
        entities = [
            mock_entity_class("entity-1", "Entity 1"),
            mock_entity_class("entity-2", "Entity 2"),
        ]

        # Save entities
        for entity in entities:
            mock_entity_repository.save(entity)

        # Get all entities
        retrieved = mock_entity_repository.get_all()
        assert len(retrieved) == 2
        assert all(isinstance(e, mock_entity_class) for e in retrieved)

    def test_delete(
        self, mock_entity_repository: EntityRepository, mock_entity_class: Any
    ) -> None:
        """Test deleting entities."""
        entity = mock_entity_class("test-123", "Test Entity")

        # Save entity
        mock_entity_repository.save(entity)
        assert mock_entity_repository.get_by_id("test-123") is not None

        # Delete entity
        result = mock_entity_repository.delete("test-123")
        assert result is True
        assert mock_entity_repository.get_by_id("test-123") is None

        # Delete non-existent entity
        result = mock_entity_repository.delete("non-existent")
        assert result is False


class TestPersistentEntityLifecycle:
    """Test the PersistentEntityLifecycle class."""

    @pytest.fixture
    def mock_entity(self, mocker: MockerFixture) -> Any:
        """Create a mock entity for testing."""
        entity = mocker.MagicMock()
        entity.id = "test-entity-123"
        entity.status = EntityStatus.STOPPED
        entity.to_dict = {"id": "test-entity-123", "status": "stopped"}
        entity.__class__.__name__ = "MockEntity"
        return entity

    def test_persistent_transition(
        self,
        mocker: MockerFixture,
        storage_manager: StorageManager,
        mock_entity: Any,
    ) -> None:
        """Test persistent transition method."""
        mock_lifecycle = mocker.patch("supervaizer.lifecycle.EntityLifecycle")
        mock_lifecycle.transition.return_value = (True, "")

        success, error = PersistentEntityLifecycle.transition(
            mock_entity, EntityStatus.IN_PROGRESS, storage_manager
        )

        assert success is True
        assert error == ""
        mock_lifecycle.transition.assert_called_once_with(
            mock_entity, EntityStatus.IN_PROGRESS
        )

        # Verify entity was persisted
        stored = storage_manager.get_object_by_id("MockEntity", "test-entity-123")
        assert stored is not None

    def test_persistent_handle_event(
        self, mocker: MockerFixture, storage_manager: StorageManager, mock_entity: Any
    ) -> None:
        """Test persistent handle_event method."""
        mock_lifecycle = mocker.patch("supervaizer.lifecycle.EntityLifecycle")
        mock_lifecycle.handle_event.return_value = (True, "")

        success, error = PersistentEntityLifecycle.handle_event(
            mock_entity, EntityEvents.START_WORK, storage_manager
        )

        assert success is True
        assert error == ""
        mock_lifecycle.handle_event.assert_called_once_with(
            mock_entity, EntityEvents.START_WORK
        )

        # Verify entity was persisted
        stored = storage_manager.get_object_by_id("MockEntity", "test-entity-123")
        assert stored is not None

    def test_persistent_transition_failure(
        self,
        mocker: MockerFixture,
        storage_manager: StorageManager,
        mock_entity: Any,
    ) -> None:
        """Test persistent transition when underlying transition fails."""
        mock_lifecycle = mocker.patch("supervaizer.lifecycle.EntityLifecycle")
        mock_lifecycle.transition.return_value = (False, "Invalid transition")

        success, error = PersistentEntityLifecycle.transition(
            mock_entity, EntityStatus.COMPLETED, storage_manager
        )

        assert success is False
        assert error == "Invalid transition"

        # Verify entity was NOT persisted
        stored = storage_manager.get_object_by_id("MockEntity", "test-entity-123")
        assert stored is None


class TestFactoryFunctions:
    """Test the factory functions."""

    def test_create_job_repository(self) -> None:
        """Test creating a job repository."""
        repo = create_job_repository()
        assert isinstance(repo, EntityRepository)
        assert repo.type_name == "Job"

    def test_create_case_repository(self) -> None:
        """Test creating a case repository."""
        repo = create_case_repository()
        assert isinstance(repo, EntityRepository)
        assert repo.type_name == "Case"


class TestIntegrationWithActualEntities:
    """Integration tests with actual Job and Case entities."""

    def _clear_singletons(self) -> None:
        """Helper to properly clear singleton instances."""
        # Clear Jobs singleton
        jobs = Jobs()
        jobs.jobs_by_agent = {}

        # Clear Cases singleton
        cases = Cases()
        cases.cases_by_job = {}

    def test_job_persistence(
        self, storage_manager: StorageManager, test_job_context: JobContext
    ) -> None:
        """Test persisting actual Job entities."""
        self._clear_singletons()

        job = Job(
            id="test-job-123",
            name="Test Job",
            agent_name="test-agent",
            status=EntityStatus.STOPPED,
            job_context=test_job_context,
        )

        # Save job to storage
        storage_manager.save_object("Job", job.to_dict)

        # Retrieve job data
        stored_data = storage_manager.get_object_by_id("Job", "test-job-123")
        assert stored_data is not None
        assert stored_data["id"] == "test-job-123"
        assert stored_data["name"] == "Test Job"
        assert stored_data["agent_name"] == "test-agent"
        assert stored_data["case_ids"] == []

    def test_case_persistence(
        self,
        mocker: MockerFixture,
        storage_manager: StorageManager,
        account_fixture: Account,
    ) -> None:
        """Test persisting actual Case entities."""
        self._clear_singletons()

        # Mock the send_event service to avoid HTTP calls
        mock_send_event = mocker.patch("supervaizer.account_service.send_event")
        mock_send_event.return_value = mocker.MagicMock()

        case = Case.start(
            job_id="test-job-123",
            name="Test Case",
            account=account_fixture,
            description="Test Case Description",
            case_id="test-case-123",
        )

        # Save case to storage
        storage_manager.save_object("Case", case.to_dict)

        # Retrieve case data
        stored_data = storage_manager.get_object_by_id("Case", "test-case-123")
        assert stored_data is not None
        assert stored_data["id"] == "test-case-123"
        assert stored_data["job_id"] == "test-job-123"
        assert stored_data["name"] == "Test Case"

    def test_foreign_key_relationships(
        self,
        mocker: MockerFixture,
        storage_manager: StorageManager,
        test_job_context: JobContext,
        account_fixture: Account,
    ) -> None:
        """Test foreign key relationships between Job and Case."""
        self._clear_singletons()

        # Mock the send_event service to avoid HTTP calls
        mock_send_event = mocker.patch("supervaizer.account_service.send_event")
        mock_send_event.return_value = mocker.MagicMock()

        # Create job
        job = Job(
            id="test-job-123",
            name="Test Job",
            agent_name="test-agent",
            status=EntityStatus.STOPPED,
            job_context=test_job_context,
        )

        # Create case (should automatically add to job's case_ids)
        case = Case.start(
            job_id="test-job-123",
            name="Test Case",
            account=account_fixture,
            description="Test Case Description",
            case_id="test-case-123",
        )

        # Verify foreign key relationship
        assert "test-case-123" in job.case_ids
        assert case.job_id == "test-job-123"

        # Test storage helper method
        storage_manager.save_object("Job", job.to_dict)
        storage_manager.save_object("Case", case.to_dict)

        job_cases = storage_manager.get_cases_for_job("test-job-123")
        assert len(job_cases) == 1
        assert job_cases[0]["id"] == "test-case-123"
