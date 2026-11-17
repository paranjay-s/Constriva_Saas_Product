"""Plan store: a row in the existing `plans` table round-trips, and DB trouble never
loses the plan (it stays in memory with saved=false)."""

import pytest

from app.modules.ai.floorplan.store import (
    DEFAULT_PROJECT_ID,
    KIND,
    StoredPlan,
    SupabasePlanStore,
)
from app.modules.plans.schemas import PlanJSON


class FakeTable:
    """Just enough of the supabase query builder: insert/update/select().eq().execute()."""

    def __init__(self, rows: dict, fail_insert: Exception | None = None, broken=False) -> None:
        self.rows, self.fail_insert, self.broken = rows, fail_insert, broken
        self._op: tuple = ()

    def insert(self, row):
        self._op = ("insert", row)
        return self

    def update(self, row):
        self._op = ("update", row)
        return self

    def select(self, *_):
        self._op = ("select",)
        return self

    def eq(self, _col, value):
        self._op = (*self._op, value)
        return self

    def limit(self, _n):
        return self

    def execute(self):
        if self.broken:
            raise ConnectionError("database down")
        kind = self._op[0]
        if kind == "insert":
            row = self._op[1]
            if self.fail_insert and row["origin"] == "chat":
                raise self.fail_insert
            self.rows[row["id"]] = row
        elif kind == "update":
            self.rows[self._op[2]].update(self._op[1])
        else:
            return type(
                "R", (), {"data": [self.rows[self._op[1]]] if self._op[1] in self.rows else []}
            )
        return type("R", (), {"data": []})


def _store(table: FakeTable) -> SupabasePlanStore:
    s = SupabasePlanStore()
    s._table = lambda: table  # type: ignore[method-assign]
    return s


def _sp(sample_plan) -> StoredPlan:
    return StoredPlan(id="p1", owner_id="u1", name="My house", plan=sample_plan)


def test_row_shape_and_round_trip(sample_plan) -> None:
    rows: dict = {}
    sp = _store(FakeTable(rows)).create(_sp(sample_plan))
    assert sp.saved
    row = rows["p1"]
    assert row["project_id"] == DEFAULT_PROJECT_ID and row["origin"] == "chat"
    PlanJSON.model_validate(row["plan_json"])  # the 3D viewer / BOQ format
    meta = row["generation_metadata"]
    assert meta["kind"] == KIND and meta["owner_user_id"] == "u1" and meta["version"] == 1

    fresh = _store(FakeTable(rows)).get("p1")  # new process: read from the table
    assert fresh is not None and fresh.saved
    assert fresh.plan == sample_plan and fresh.owner_id == "u1" and fresh.name == "My house"


def test_origin_check_falls_back_to_extracted(sample_plan) -> None:
    rows: dict = {}
    err = Exception('new row violates check constraint "plans_origin_check"')
    sp = _store(FakeTable(rows, fail_insert=err)).create(_sp(sample_plan))
    assert sp.saved and rows["p1"]["origin"] == "extracted"


def test_database_down_keeps_plan_in_memory(sample_plan) -> None:
    store = _store(FakeTable({}, broken=True))
    sp = store.create(_sp(sample_plan))
    assert not sp.saved
    got = store.get("p1")
    assert got is not None and got.plan == sample_plan
    got.version = 2
    assert not store.update(got).saved
    assert store.get("p1").version == 2


def test_update_bumps_version_in_row(sample_plan) -> None:
    rows: dict = {}
    store = _store(FakeTable(rows))
    sp = store.create(_sp(sample_plan))
    sp.version = 3
    sp.messages.append({"role": "user", "text": "hi"})
    store.update(sp)
    meta = rows["p1"]["generation_metadata"]
    assert meta["version"] == 3 and meta["messages"][0]["text"] == "hi"


@pytest.mark.parametrize("meta", [{}, {"kind": "something_else"}, {"kind": KIND}])
def test_rows_from_other_features_are_ignored(meta) -> None:
    row = {"id": "x", "name": "n", "generation_metadata": meta}
    assert StoredPlan.from_row(row) is None
