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

import os
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Generic, List, Optional, TypeVar

from tinydb import Query, TinyDB
from tinydb.storages import MemoryStorage

from supervaizer.common import log, singleton
from supervaizer.lifecycle import WorkflowEntity


class _MemoryStorage(MemoryStorage):
    """MemoryStorage that accepts TinyDB's sort_keys/indent kwargs (ignored)."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args)


if TYPE_CHECKING:
    from supervaizer.case import Case
    from supervaizer.job import Job
    from supervaizer.lifecycle import EntityEvents, EntityStatus


T = TypeVar("T", bound=WorkflowEntity)

DATA_STORAGE_PATH = os.getenv("DATA_STORAGE_PATH", "./data")

# When False (default), use in-memory storage only (e.g. Vercel, serverless).
# Set SUPERVAIZER_PERSISTENCE=true to persist to file.
PERSISTENCE_ENABLED = os.getenv("SUPERVAIZER_PERSISTENCE", "false").lower() in (
    "true",
    "1",
    "yes",
)


@singleton
class StorageManager:
    """
    Thread-safe TinyDB-based persistence manager for WorkflowEntity instances.

    Stores entities in separate tables by type, with foreign key relationships
    represented as ID references (Job.case_ids, Case.job_id).

    When SUPERVAIZER_PERSISTENCE is false (default), uses in-memory storage only.
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the storage manager.

        Args:
            db_path: Path to the TinyDB JSON file, or None to use env-based
                     persistence (file if SUPERVAIZER_PERSISTENCE=true, else memory).
        """
        self._lock = threading.Lock()
        # Explicit file path (e.g. tests) uses file; else file only if persistence enabled
        use_file = (db_path is not None and db_path != ":memory:") or (
            db_path is None and PERSISTENCE_ENABLED
        )
        if use_file:
            path = (
                db_path
                if (db_path and db_path != ":memory:")
                else f"{DATA_STORAGE_PATH}/entities.json"
            )
            self.db_path = Path(path)
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            self._db = TinyDB(path, sort_keys=True, indent=2)
        else:
            # In-memory only (default for Vercel/serverless)
            self.db_path = Path(":memory:")
            self._db = TinyDB(storage=_MemoryStorage, sort_keys=True, indent=2)

        # log.debug(
        #    f"[StorageManager] 🗃️ Local DB initialized at {self.db_path.absolute()}"
        # )

    def save_object(self, type: str, obj: Dict[str, Any]) -> None:
        """
        Save an object to the appropriate table.

        Args:
            type: The object type (class name)
            obj: Dictionary representation of the object
        """
        with self._lock:
            table = self._db.table(type)
            obj_id = obj.get("id")

            if not obj_id:
                raise ValueError(
                    f"[StorageManager] §SSSS01 Object must have an 'id' field: {obj}"
                )

            # Use upsert to handle both new and existing objects
            query = Query()
            table.upsert(obj, query.id == obj_id)

            # log.debug(f"Saved object with ID: {type} {obj_id} - {obj}")

    def get_objects(self, type: str) -> List[Dict[str, Any]]:
        """
        Get all objects of a specific type.

        Args:
            type: The object type (class name)

        Returns:
            List of object dictionaries
        """
        with self._lock:
            table = self._db.table(type)
            documents = table.all()
            return [dict(doc) for doc in documents]

    def get_object_by_id(self, type: str, obj_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific object by its ID.

        Args:
            type: The object type (class name)
            obj_id: The object ID

        Returns:
            Object dictionary if found, None otherwise
        """
        with self._lock:
            table = self._db.table(type)
            query = Query()
            result = table.search(query.id == obj_id)
            return result[0] if result else None

    def delete_object(self, type: str, obj_id: str) -> bool:
        """
        Delete an object by its ID.

        Args:
            type: The object type (class name)
            obj_id: The object ID

        Returns:
            True if object was deleted, False if not found
        """
        with self._lock:
            table = self._db.table(type)
            query = Query()
            deleted_count = len(table.remove(query.id == obj_id))

            if deleted_count > 0:
                log.debug(f"Deleted {type} object with ID: {obj_id}")
                return True
            return False

    def reset_storage(self) -> None:
        """
        Reset storage by clearing all tables but preserving the database file.
        """
        with self._lock:
            # Clear all tables
            for table_name in self._db.tables():
                self._db.drop_table(table_name)

            log.info("Storage reset - all tables cleared")

    def get_cases_for_job(self, job_id: str) -> List[Dict[str, Any]]:
        """
        Helper method to get all cases for a specific job.

        Args:
            job_id: The job ID

        Returns:
            List of case dictionaries
        """
        with self._lock:
            table = self._db.table("Case")
            query = Query()
            documents = table.search(query.job_id == job_id)
            return [dict(doc) for doc in documents]

    def close(self) -> None:
        """Close the database connection."""
        with self._lock:
            if hasattr(self, "_db") and self._db is not None:
                try:
                    if hasattr(self._db, "close"):
                        self._db.close()
                    log.info("StorageManager database closed")
                except ValueError as e:
                    # Handle the case where the file is already closed
                    if "I/O operation on closed file" in str(e):
                        log.debug("Database file already closed")
                    else:
                        raise


class EntityRepository(Generic[T]):
    """
    Generic repository for WorkflowEntity types with type-safe operations.

    Provides higher-level abstraction over StorageManager for specific entity types.
    """

    def __init__(
        self, entity_class: type[T], storage_manager: Optional[StorageManager] = None
    ):
        """
        Initialize repository for a specific entity type.

        Args:
            entity_class: The entity class this repository manages
            storage_manager: Optional storage manager instance
        """
        self.entity_class = entity_class
        self.type_name = entity_class.__name__
        self.storage = storage_manager or StorageManager()

    def get_by_id(self, entity_id: str) -> Optional[T]:
        """
        Get an entity by its ID.

        Args:
            entity_id: The entity ID

        Returns:
            Entity instance if found, None otherwise
        """
        data = self.storage.get_object_by_id(self.type_name, entity_id)
        if data:
            return self._from_dict(data)
        return None

    def save(self, entity: T) -> None:
        """
        Save an entity to storage.

        Args:
            entity: The entity to save
        """
        data = self._to_dict(entity)
        self.storage.save_object(self.type_name, data)

    def get_all(self) -> List[T]:
        """
        Get all entities of this type.

        Returns:
            List of entity instances
        """
        data_list = self.storage.get_objects(self.type_name)
        return [self._from_dict(data) for data in data_list]

    def delete(self, entity_id: str) -> bool:
        """
        Delete an entity by its ID.

        Args:
            entity_id: The entity ID

        Returns:
            True if deleted, False if not found
        """
        return self.storage.delete_object(self.type_name, entity_id)

    def _to_dict(self, entity: T) -> Dict[str, Any]:
        """Convert entity to dictionary using its to_dict property."""
        if hasattr(entity, "to_dict"):
            return dict(entity.to_dict)
        else:
            # Fallback for entities without to_dict
            return {
                field: getattr(entity, field)
                for field in getattr(entity, "__dataclass_fields__", {})
                if hasattr(entity, field)
            }

    def _from_dict(self, data: Dict[str, Any]) -> T:
        """
        Convert dictionary back to entity instance.

        Note: This is a simplified implementation. In practice, you might need
        more sophisticated deserialization depending on your entity structure.
        """
        # For entities inheriting from SvBaseModel (Pydantic), use model construction
        if hasattr(self.entity_class, "model_validate"):
            return self.entity_class.model_validate(data)  # type: ignore
        else:
            # Fallback for other types
            return self.entity_class(**data)


class PersistentEntityLifecycle:
    """
    Enhanced EntityLifecycle that automatically persists entity state changes.

    This class wraps the original EntityLifecycle methods to add persistence.
    """

    @staticmethod
    def transition(
        entity: T, to_status: "EntityStatus", storage: Optional[StorageManager] = None
    ) -> tuple[bool, str]:
        """
        Transition an entity and automatically persist the change.

        Args:
            entity: The entity to transition
            to_status: Target status
            storage: Optional storage manager instance

        Returns:
            Tuple of (success, error_message)
        """
        # Import here to avoid circular imports
        from supervaizer.lifecycle import EntityLifecycle

        # Perform the transition
        success, error = EntityLifecycle.transition(entity, to_status)

        # If successful, persist the entity
        if success:
            storage_mgr = storage or StorageManager()
            entity_dict = entity.to_dict if hasattr(entity, "to_dict") else vars(entity)
            storage_mgr.save_object(type(entity).__name__, entity_dict)
            log.debug(
                f"[Storage transition] Auto-persisted {type(entity).__name__} {entity.id} after transition to {to_status}"
            )

        return success, error

    @staticmethod
    def handle_event(
        entity: T, event: "EntityEvents", storage: Optional[StorageManager] = None
    ) -> tuple[bool, str]:
        """
        Handle an event and automatically persist the change.

        Args:
            entity: The entity to handle event for
            event: The event to handle
            storage: Optional storage manager instance

        Returns:
            Tuple of (success, error_message)
        """
        # Import here to avoid circular imports
        from supervaizer.lifecycle import EntityLifecycle

        # Handle the event
        success, error = EntityLifecycle.handle_event(entity, event)

        # If successful, persist the entity
        if success:
            storage_mgr = storage or StorageManager()
            entity_dict = entity.to_dict if hasattr(entity, "to_dict") else vars(entity)
            storage_mgr.save_object(type(entity).__name__, entity_dict)
            log.debug(
                f"[Storage handle_event] Auto-persisted {type(entity).__name__} {entity.id} after handling event {event}"
            )

        return success, error


def create_job_repository() -> "EntityRepository[Job]":
    """Factory function to create a Job repository."""
    from supervaizer.job import Job

    return EntityRepository(Job)


def create_case_repository() -> "EntityRepository[Case]":
    """Factory function to create a Case repository."""
    from supervaizer.case import Case

    return EntityRepository(Case)


def load_running_entities_on_startup() -> None:
    """
    Load all running entities from storage and populate registries at startup.

    This function loads jobs and cases that are in running states:
    - IN_PROGRESS
    - CANCELLING
    - AWAITING

    This ensures that after a server restart, all running workflows
    continue to be accessible through the in-memory registries.
    """
    from supervaizer.case import Case, Cases
    from supervaizer.job import Job, Jobs
    from supervaizer.lifecycle import EntityStatus

    storage = StorageManager()

    # Clear existing registries to start fresh
    Jobs().reset()
    Cases().reset()

    # Load running jobs
    job_data_list = storage.get_objects("Job")
    loaded_jobs = 0

    for job_data in job_data_list:
        job_status = job_data.get("status")
        if job_status in [status.value for status in EntityStatus.status_running()]:
            try:
                # Use model_construct to avoid triggering __init__ side effects
                job = Job.model_construct(**job_data)
                # Manually add to registry since we bypassed __init__
                Jobs().add_job(job)
                loaded_jobs += 1
                # log.debug(
                #     f"[Startup] Loaded running job: {job.id} (status: {job.status})"
                # )
            except Exception as e:
                log.error(
                    f"[Storage] §SSL01 Failed to load job {job_data.get('id', 'unknown')}: {e}"
                )

    # Load running cases
    case_data_list = storage.get_objects("Case")
    loaded_cases = 0

    for case_data in case_data_list:
        case_status = case_data.get("status")
        if case_status in [status.value for status in EntityStatus.status_running()]:
            try:
                # Use model_construct to avoid triggering __init__ side effects
                case = Case.model_construct(**case_data)
                # Manually add to registry since we bypassed __init__
                Cases().add_case(case)
                loaded_cases += 1
                # log.debug(
                #    f"[Storage] Loaded running case: {case.id} (status: {case.status}, job: {case.job_id})"
                # )
            except Exception as e:
                log.error(
                    f"[Storage] §SSL03 Failed to load case {case_data.get('id', 'unknown')}: {e}"
                )

    log.info(
        f"[Storage] Entity re-loading complete: {loaded_jobs} running jobs, {loaded_cases} running cases"
    )


storage_manager = StorageManager()
