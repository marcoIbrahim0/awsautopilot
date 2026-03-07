from __future__ import annotations

from dataclasses import dataclass

from scripts.check_s3_cf_noop_runs import (
    TargetRun,
    UpdateResult,
    apply_retroactive_check,
)


@dataclass
class FakeRun:
    run_id: str
    artifacts: dict
    updated: bool = False


class FakeDbStore:
    def __init__(self, runs: list[FakeRun]) -> None:
        self._runs = runs
        self.write_calls = 0

    def find_target_runs(self, *, limit: int | None = None) -> list[TargetRun]:
        runs = self._runs if limit is None else self._runs[:limit]
        return [TargetRun(run_id=run.run_id, artifacts=dict(run.artifacts)) for run in runs]

    def mark_verification_required(self, run: TargetRun) -> UpdateResult:
        self.write_calls += 1
        for item in self._runs:
            if item.run_id != run.run_id:
                continue
            item.updated = True
            item.artifacts["show_verification_banner"] = True
            return UpdateResult(updated=True, status_updated=True, banner_updated=True)
        return UpdateResult(updated=False, status_updated=False, banner_updated=False)


def test_apply_retroactive_check_updates_all_matching_runs() -> None:
    store = FakeDbStore(
        [
            FakeRun(run_id="run-1", artifacts={}),
            FakeRun(run_id="run-2", artifacts={}),
            FakeRun(run_id="run-3", artifacts={}),
        ]
    )

    summary = apply_retroactive_check(store, dry_run=False)

    assert summary.matched_runs == 3
    assert summary.updated_runs == 3
    assert summary.status_updates == 3
    assert summary.banner_updates == 3
    assert store.write_calls == 3
    assert all(run.updated is True for run in store._runs)


def test_apply_retroactive_check_no_matches_exits_without_writes() -> None:
    store = FakeDbStore([])

    summary = apply_retroactive_check(store, dry_run=False)

    assert summary.matched_runs == 0
    assert summary.updated_runs == 0
    assert summary.status_updates == 0
    assert summary.banner_updates == 0
    assert summary.run_ids == []
    assert store.write_calls == 0
