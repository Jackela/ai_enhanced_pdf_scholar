from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from src.repositories.base_repository import BaseRepository

pytestmark = pytest.mark.repositories


@dataclass
class DummyModel:
    id: int | None
    name: str


class SimpleDB:
    def __init__(self, connection: sqlite3.Connection):
        self.conn = connection

    def fetch_one(self, query, params=()):
        cur = self.conn.execute(query, params)
        result = cur.fetchone()
        cur.close()
        return result

    def fetch_all(self, query, params=()):
        cur = self.conn.execute(query, params)
        rows = cur.fetchall()
        cur.close()
        return rows

    def execute(self, query, params=()):
        cur = self.conn.execute(query, params)
        return cur

    def get_last_insert_id(self):
        return self.conn.execute("SELECT last_insert_rowid()").fetchone()[0]


class DummyRepository(BaseRepository[DummyModel]):
    def __init__(self, connection: sqlite3.Connection):
        super().__init__(SimpleDB(connection))  # type: ignore[arg-type]

    def get_table_name(self) -> str:
        return "dummy"

    def to_model(self, row: dict[str, Any]) -> DummyModel:
        return DummyModel(id=row["id"], name=row["name"])

    def to_database_dict(self, model: DummyModel) -> dict[str, Any]:
        return {"id": model.id, "name": model.name}


@pytest.fixture
def repo(tmp_path: Path) -> DummyRepository:
    conn = sqlite3.connect(tmp_path / "dummy.sqlite")
    conn.isolation_level = None
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE dummy (
            id INTEGER PRIMARY KEY,
            name TEXT
        )
        """
    )
    conn.execute("INSERT INTO dummy (id, name) VALUES (1, 'alpha')")
    conn.execute("INSERT INTO dummy (id, name) VALUES (2, 'beta')")
    conn.commit()
    return DummyRepository(conn)


def test_find_by_id(repo: DummyRepository) -> None:
    assert repo.find_by_id(1) == DummyModel(id=1, name="alpha")
    assert repo.find_by_id(99) is None


def test_find_all_with_limit(repo: DummyRepository) -> None:
    models = repo.find_all(limit=1, offset=1)
    assert len(models) == 1
    assert models[0].name == "beta"


def test_count(repo: DummyRepository) -> None:
    assert repo.count() == 2


def test_create(repo: DummyRepository) -> None:
    created = repo.create(DummyModel(id=None, name="gamma"))
    assert created.id is not None
    assert repo.count() == 3


def test_update(repo: DummyRepository) -> None:
    model = DummyModel(id=1, name="alpha-updated")
    updated = repo.update(model)
    assert updated.name == "alpha-updated"


def test_delete(repo: DummyRepository) -> None:
    assert repo.delete(2) is True
    assert repo.delete(999) is False
