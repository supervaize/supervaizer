import pytest
from pydantic import BaseModel
from supervaizer.storage import EntityRepository
from tinydb import TinyDB, Query
from tinydb.storages import MemoryStorage


class DummyEntity(BaseModel):
    id: str
    value: int


class MinimalStorageManager:
    def __init__(self):
        self._db = TinyDB(storage=MemoryStorage)

    def save_object(self, type: str, obj: dict) -> None:
        table = self._db.table(type)
        obj_id = obj.get("id")
        if not obj_id:
            raise ValueError("Object must have an 'id' field")
        table.upsert(obj, Query().id == obj_id)

    def get_objects(self, type: str) -> list[dict]:
        return [dict(doc) for doc in self._db.table(type).all()]

    def get_object_by_id(self, type: str, obj_id: str) -> dict | None:
        result = self._db.table(type).search(Query().id == obj_id)
        return dict(result[0]) if result else None

    def delete_object(self, type: str, obj_id: str) -> bool:
        return bool(self._db.table(type).remove(Query().id == obj_id))


@pytest.fixture
def dummy_entity() -> DummyEntity:
    return DummyEntity(id="dummy-1", value=42)


@pytest.fixture
def repo() -> EntityRepository[DummyEntity]:
    storage = MinimalStorageManager()

    class DummyRepo(EntityRepository[DummyEntity]):
        def _to_dict(self, entity: DummyEntity) -> dict:
            return entity.model_dump(exclude_unset=False)

        def _from_dict(self, data: dict) -> DummyEntity:
            return DummyEntity.model_validate(data)

    return DummyRepo(DummyEntity, storage_manager=storage)


def test_save_and_get_by_id(
    repo: EntityRepository[DummyEntity], dummy_entity: DummyEntity
) -> None:
    repo.save(dummy_entity)
    loaded = repo.get_by_id(dummy_entity.id)
    assert loaded is not None
    assert loaded.id == dummy_entity.id
    assert loaded.value == dummy_entity.value


def test_get_all_empty(repo: EntityRepository[DummyEntity]) -> None:
    """get_all returns an empty list when no entities are saved."""
    all_entities = repo.get_all()
    assert isinstance(all_entities, list)
    assert len(all_entities) == 0


def test_get_all_after_save(
    repo: EntityRepository[DummyEntity], dummy_entity: DummyEntity
) -> None:
    """get_all returns the saved entity after save."""
    repo.save(dummy_entity)
    all_entities = repo.get_all()
    assert isinstance(all_entities, list)
    assert any(e.id == dummy_entity.id for e in all_entities)


def test_delete_entity(
    repo: EntityRepository[DummyEntity], dummy_entity: DummyEntity
) -> None:
    repo.save(dummy_entity)
    deleted = repo.delete(dummy_entity.id)
    assert deleted is True
    assert repo.get_by_id(dummy_entity.id) is None


def test_delete_nonexistent_entity(repo: EntityRepository[DummyEntity]) -> None:
    deleted = repo.delete("doesnotexist")
    assert deleted is False


def test_get_by_id_not_found(repo: EntityRepository[DummyEntity]) -> None:
    assert repo.get_by_id("doesnotexist") is None
