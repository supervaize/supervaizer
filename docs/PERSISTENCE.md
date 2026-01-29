# TinyDB Persistence Layer

The Supervaizer TinyDB persistence layer provides thread-safe, local storage for WorkflowEntity instances (Jobs, Cases, Missions) across sessions and processes.

## Features

- **Thread-safe operations** using TinyDB's CachingMiddleware and threading locks
- **Entity-specific tables** with foreign key relationships via ID references
- **Auto-persistence** on EntityLifecycle state transitions
- **Type-safe repositories** for entity-specific operations
- **Configurable storage path** with automatic directory creation
- **Cross-session data loading** for service restarts

## Core Components

### StorageManager

The main persistence interface providing CRUD operations for entity dictionaries.

```python
from supervaizer.storage import StorageManager

# Initialize with custom path
storage = StorageManager(db_path="./data/entities.json")

# Save an entity
job_dict = job.to_dict
storage.save_object("Job", job_dict)

# Retrieve entities
job_data = storage.get_object_by_id("Job", "job-123")
all_jobs = storage.get_objects("Job")

# Delete entities
storage.delete_object("Job", "job-123")

# Reset all data
storage.reset_storage()
```

### EntityRepository

Type-safe repository pattern for specific entity types.

```python
from supervaizer.storage import create_job_repository, create_case_repository

# Create repositories
job_repo = create_job_repository()
case_repo = create_case_repository()

# Save entities (auto-converts using to_dict)
job_repo.save(job)
case_repo.save(case)

# Retrieve entities (auto-reconstructs using model_validate)
job = job_repo.get_by_id("job-123")
all_jobs = job_repo.get_all()

# Delete entities
job_repo.delete("job-123")
```

### PersistentEntityLifecycle

Enhanced lifecycle management with automatic persistence.

```python
from supervaizer.storage import PersistentEntityLifecycle, StorageManager
from supervaizer.lifecycle import EntityStatus, EntityEvents

storage = StorageManager()

# Auto-persist on transitions
success, error = PersistentEntityLifecycle.transition(
    job, EntityStatus.IN_PROGRESS, storage
)

# Auto-persist on events
success, error = PersistentEntityLifecycle.handle_event(
    job, EntityEvents.START_WORK, storage
)
```

## Data Model

### Entity Tables

Each entity type is stored in a dedicated TinyDB table:

- **Job table**: Stores Job entities with `case_ids` field for relationships
- **Case table**: Stores Case entities with `job_id` field for parent reference
- **Mission table**: Future extension for Mission entities

### Foreign Key Relationships

Relationships are represented via ID references:

```python
# Job stores list of case IDs
job.case_ids = ["case-1", "case-2", "case-3"]

# Case stores its parent job ID
case.job_id = "job-123"
```

### Entity Structure

Entities are persisted using their `to_dict` property:

```python
job_dict = {
    "id": "job-123",
    "name": "Example Job",
    "status": "in_progress",
    "case_ids": ["case-1", "case-2"],
    "job_context": {...},
    "finished_at": "2025-01-01T12:00:00",
    # ... other fields
}
```

## Usage Patterns

### Basic Setup

```python
from supervaizer.storage import StorageManager

# Production setup
storage = StorageManager(db_path="./data/entities.json")

# Test setup
storage = StorageManager(db_path="./test_data/test_entities.json")

# In-memory for unit tests
storage = StorageManager(db_path=":memory:")
```

### Entity Creation and Persistence

```python
from supervaizer.job import Job, JobContext
from supervaizer.case import Case
from supervaizer.storage import StorageManager

storage = StorageManager()

# Create job
job = Job(
    id="job-123",
    name="My Job",
    agent_name="my-agent",
    status=EntityStatus.STOPPED,
    job_context=job_context,
)

# Create case (automatically adds to job.case_ids)
case = Case.start(
    job_id="job-123",
    name="My Case",
    account=account,
    description="Case description",
)

# Persist entities
storage.save_object("Job", job.to_dict)
storage.save_object("Case", case.to_dict)
```

### Loading Data on Startup

The system automatically loads running entities from storage during server startup. This ensures that after a server restart, all running workflows continue to be accessible through the in-memory registries.

#### Automatic Loading

The server startup process includes automatic loading of running entities:

```python
# This happens automatically during server initialization
load_running_entities_on_startup()
```

Only entities in running states are loaded:

- `IN_PROGRESS`
- `CANCELLING`
- `AWAITING`

This selective loading ensures that only active workflows are restored to memory, keeping the system efficient.

#### Manual Loading (All Entities)

For testing or special cases, you can manually load all entities:

```python
def load_all_entities_on_startup():
    """Load all entities from storage and populate registries."""
    storage = StorageManager()

    # Load jobs
    job_data_list = storage.get_objects("Job")
    for job_data in job_data_list:
        # Reconstruct Job object and add to registry
        job = Job.model_validate(job_data)
        Jobs().add_job(job)

    # Load cases
    case_data_list = storage.get_objects("Case")
    for case_data in case_data_list:
        # Reconstruct Case object and add to registry
        case = Case.model_validate(case_data)
        Cases().add_case(case)

    print(f"Loaded {len(job_data_list)} jobs and {len(case_data_list)} cases")
```

### Auto-Persistence Integration

Replace standard lifecycle calls with persistent versions:

```python
# Standard (no persistence)
from supervaizer.lifecycle import EntityLifecycle
EntityLifecycle.transition(job, EntityStatus.IN_PROGRESS)

# Auto-persisting version
from supervaizer.storage import PersistentEntityLifecycle
PersistentEntityLifecycle.transition(job, EntityStatus.IN_PROGRESS, storage)
```

### Relationship Queries

```python
# Get all cases for a job
job_cases = storage.get_cases_for_job("job-123")

# Get job for a case
case_data = storage.get_object_by_id("Case", "case-456")
job_data = storage.get_object_by_id("Job", case_data["job_id"])

# Count cases per job
all_jobs = storage.get_objects("Job")
for job_data in all_jobs:
    case_count = len(storage.get_cases_for_job(job_data["id"]))
    print(f"Job {job_data['id']} has {case_count} cases")
```

## Configuration

### Persistence Default (Off)

Data persistence is **off by default** so the server works on Vercel and other serverless platforms where the filesystem is ephemeral.

- **Default**: In-memory only (no file). Data is lost on restart.
- **To enable file persistence**: Set `SUPERVAIZER_PERSISTENCE=true` (or `1`/`yes`), or run `supervaizer start --persist`.

When persistence is enabled, the storage path is `DATA_STORAGE_PATH/entities.json` (default `./data/entities.json`).

### Environment-Based Setup

```python
import os
from supervaizer.storage import StorageManager

# Environment-based configuration
def create_storage():
    if os.getenv("SUPERVAIZER_PERSISTENCE", "false").lower() in ("true", "1", "yes"):
        env = os.getenv("SUPERVAIZER_ENV", "production")
        if env == "test":
            return StorageManager(db_path="./test_data/entities.json")
        elif env == "development":
            return StorageManager(db_path="./dev_data/entities.json")
        else:
            return StorageManager(db_path="./data/entities.json")
    return StorageManager()  # in-memory (default)
```

### Storage Path Configuration

When persistence is enabled, the default storage path is `./data/entities.json`. It can be customized via `DATA_STORAGE_PATH`:

```python
# Custom path
storage = StorageManager(db_path="/var/lib/supervaizer/entities.json")

# Relative to project root
storage = StorageManager(db_path="./storage/production_entities.json")

# Temporary for testing
import tempfile
with tempfile.TemporaryDirectory() as temp_dir:
    storage = StorageManager(db_path=f"{temp_dir}/test_entities.json")
```

## Thread Safety

The StorageManager is thread-safe through:

1. **TinyDB CachingMiddleware**: Provides atomic writes
2. **Threading locks**: Protects concurrent access to database operations
3. **Singleton pattern**: Ensures single database instance per path

```python
import threading
from supervaizer.storage import StorageManager

storage = StorageManager()

def worker_thread(worker_id):
    for i in range(100):
        # Thread-safe operations
        data = {"id": f"worker-{worker_id}-{i}", "data": f"data-{i}"}
        storage.save_object("Test", data)
        retrieved = storage.get_object_by_id("Test", data["id"])
        assert retrieved == data

# Start multiple threads - all operations are thread-safe
threads = [threading.Thread(target=worker_thread, args=(i,)) for i in range(10)]
for thread in threads:
    thread.start()
for thread in threads:
    thread.join()
```

## Error Handling

```python
from supervaizer.storage import StorageManager

storage = StorageManager()

try:
    # Missing required 'id' field
    storage.save_object("Job", {"name": "No ID"})
except ValueError as e:
    print(f"Validation error: {e}")

# Non-existent object returns None
job = storage.get_object_by_id("Job", "non-existent")
assert job is None

# Failed deletion returns False
deleted = storage.delete_object("Job", "non-existent")
assert deleted is False
```

## Testing

### Unit Test Setup

```python
import tempfile
import pytest
from supervaizer.storage import StorageManager

@pytest.fixture
def temp_storage():
    """Create a temporary storage manager for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield StorageManager(db_path=f"{temp_dir}/test_entities.json")

def test_job_persistence(temp_storage):
    job_data = {"id": "test-job", "name": "Test Job"}
    temp_storage.save_object("Job", job_data)

    retrieved = temp_storage.get_object_by_id("Job", "test-job")
    assert retrieved == job_data
```

### Integration Test Patterns

```python
def test_full_workflow():
    """Test complete job/case workflow with persistence."""
    with tempfile.TemporaryDirectory() as temp_dir:
        storage = StorageManager(db_path=f"{temp_dir}/test.json")

        # Clear registries
        Jobs().__init__()
        Cases().__init__()

        # Create and persist entities
        job = create_test_job()
        case = create_test_case(job.id)

        storage.save_object("Job", job.to_dict)
        storage.save_object("Case", case.to_dict)

        # Verify persistence
        assert storage.get_object_by_id("Job", job.id) is not None
        assert len(storage.get_cases_for_job(job.id)) == 1
```

## Best Practices

1. **Use the singleton pattern**: StorageManager is a singleton to prevent multiple database connections
2. **Leverage EntityRepository**: Use type-safe repositories for better code organization
3. **Auto-persist lifecycle changes**: Use PersistentEntityLifecycle for automatic persistence
4. **Load data on startup**: Restore entity registries from storage when service starts
5. **Handle errors gracefully**: Check for None returns and catch validation errors
6. **Test with temporary storage**: Use temporary directories for unit tests
7. **Environment-specific paths**: Use different storage paths for dev/test/production

## Limitations

1. **No complex queries**: TinyDB is suitable for simple key-value and basic filtering operations
2. **JSON serialization**: All data must be JSON-serializable (handled by entity `to_dict` methods)
3. **Single-process locks**: Thread safety within a single process, not across processes
4. **No transactions**: No atomic multi-table operations (use application-level coordination)
5. **Memory usage**: TinyDB loads data into memory (fine for moderate datasets)

## Migration Path

If you need to migrate to a more robust database later:

1. **Keep the interface**: StorageManager interface can be implemented with SQLite, PostgreSQL, etc.
2. **Export data**: Use `get_objects()` to export all data for migration
3. **Preserve relationships**: Foreign key structure translates well to relational databases
4. **Maintain threading**: Keep thread-safety patterns for any database backend
