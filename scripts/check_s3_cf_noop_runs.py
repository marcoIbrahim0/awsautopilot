#!/usr/bin/env python3
"""Retroactive verification marker for legacy S3.1 CloudFormation no-op runs."""
from __future__ import annotations

import argparse
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Protocol

from sqlalchemy import text
from sqlalchemy.orm import Session

LOGGER = logging.getLogger("scripts.check_s3_cf_noop_runs")

TARGET_ACTION_TYPE = "s3_block_public_access"
TARGET_FORMAT = "cloudformation"
TARGET_STATUS = "completed"
UPDATED_STATUS = "verification_required"

BANNER_FLAG_KEY = "show_verification_banner"
BANNER_REASON_KEY = "verification_banner_reason"
BANNER_REASON_VALUE = "s3_cf_noop_requires_reapply"
BANNER_MESSAGE_KEY = "verification_banner_message"
BANNER_MESSAGE = (
    "Your CloudFormation stack for S3 account-level block public access did not apply the actual setting. "
    "Please re-run using Terraform or the updated CloudFormation bundle."
)
BANNER_COLUMN_CANDIDATES = (
    "show_verification_banner",
    "verification_required_banner",
    "ui_show_verification_banner",
)


@dataclass(frozen=True)
class TargetRun:
    run_id: str
    artifacts: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class UpdateResult:
    updated: bool
    status_updated: bool
    banner_updated: bool


@dataclass(frozen=True)
class CheckSummary:
    matched_runs: int
    updated_runs: int
    status_updates: int
    banner_updates: int
    dry_run: bool
    run_ids: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "matched_runs": self.matched_runs,
            "updated_runs": self.updated_runs,
            "status_updates": self.status_updates,
            "banner_updates": self.banner_updates,
            "dry_run": self.dry_run,
            "run_ids": list(self.run_ids),
        }


class RunStore(Protocol):
    def find_target_runs(self, *, limit: int | None = None) -> list[TargetRun]:
        ...

    def mark_verification_required(self, run: TargetRun) -> UpdateResult:
        ...


def _table_exists(session: Session, table_name: str) -> bool:
    row = session.execute(
        text(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name = :table_name
            LIMIT 1
            """
        ),
        {"table_name": table_name},
    ).first()
    return row is not None


def _column_record(session: Session, table_name: str, column_name: str) -> dict[str, Any] | None:
    row = session.execute(
        text(
            """
            SELECT data_type, udt_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = :table_name
              AND column_name = :column_name
            LIMIT 1
            """
        ),
        {"table_name": table_name, "column_name": column_name},
    ).mappings().first()
    return dict(row) if row is not None else None


def _column_exists(session: Session, table_name: str, column_name: str) -> bool:
    return _column_record(session, table_name, column_name) is not None


def _enum_has_label(session: Session, enum_name: str, label: str) -> bool:
    row = session.execute(
        text(
            """
            SELECT 1
            FROM pg_type t
            JOIN pg_enum e
              ON e.enumtypid = t.oid
            WHERE t.typname = :enum_name
              AND e.enumlabel = :label
            LIMIT 1
            """
        ),
        {"enum_name": enum_name, "label": label},
    ).first()
    return row is not None


def apply_retroactive_check(
    store: RunStore,
    *,
    dry_run: bool = False,
    limit: int | None = None,
) -> CheckSummary:
    targets = store.find_target_runs(limit=limit)
    run_ids = [run.run_id for run in targets]
    matched = len(targets)

    if matched == 0:
        return CheckSummary(
            matched_runs=0,
            updated_runs=0,
            status_updates=0,
            banner_updates=0,
            dry_run=dry_run,
            run_ids=[],
        )

    if dry_run:
        return CheckSummary(
            matched_runs=matched,
            updated_runs=0,
            status_updates=0,
            banner_updates=0,
            dry_run=True,
            run_ids=run_ids,
        )

    updated_runs = 0
    status_updates = 0
    banner_updates = 0
    for run in targets:
        result = store.mark_verification_required(run)
        if result.updated:
            updated_runs += 1
        if result.status_updated:
            status_updates += 1
        if result.banner_updated:
            banner_updates += 1

    return CheckSummary(
        matched_runs=matched,
        updated_runs=updated_runs,
        status_updates=status_updates,
        banner_updates=banner_updates,
        dry_run=False,
        run_ids=run_ids,
    )


class SqlRemediationRunStore:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.has_runs_table = _table_exists(session, "remediation_runs")
        self.has_actions_table = _table_exists(session, "actions")
        self.has_runs_action_type = _column_exists(session, "remediation_runs", "action_type")
        self.has_runs_action_id = _column_exists(session, "remediation_runs", "action_id")
        self.has_runs_format = _column_exists(session, "remediation_runs", "format")
        self.has_runs_status = _column_exists(session, "remediation_runs", "status")
        self.has_runs_artifacts = _column_exists(session, "remediation_runs", "artifacts")
        self.has_runs_updated_at = _column_exists(session, "remediation_runs", "updated_at")
        self.has_actions_action_type = _column_exists(session, "actions", "action_type")
        self.banner_column = self._discover_banner_column()
        self.status_update_supported = self._status_can_use_verification_required()

    def _discover_banner_column(self) -> str | None:
        for column_name in BANNER_COLUMN_CANDIDATES:
            if _column_exists(self.session, "remediation_runs", column_name):
                return column_name
        return None

    def _status_can_use_verification_required(self) -> bool:
        if not self.has_runs_status:
            return False
        record = _column_record(self.session, "remediation_runs", "status")
        if record is None:
            return False
        if str(record.get("data_type", "")).upper() != "USER-DEFINED":
            return True
        enum_name = str(record.get("udt_name") or "").strip()
        if not enum_name:
            return False
        return _enum_has_label(self.session, enum_name, UPDATED_STATUS)

    def find_target_runs(self, *, limit: int | None = None) -> list[TargetRun]:
        if not self.has_runs_table or not self.has_runs_status:
            LOGGER.warning("No remediation_runs table/status column found; skipping retroactive check.")
            return []
        if not self._can_filter_action_type():
            LOGGER.warning("Unable to filter action_type for remediation_runs; skipping retroactive check.")
            return []
        if not self._can_filter_format():
            LOGGER.warning("Unable to filter format for remediation_runs; skipping retroactive check.")
            return []

        select_parts = ["SELECT rr.id, rr.artifacts FROM remediation_runs rr"]
        where_parts = ["LOWER(rr.status::text) = :target_status"]
        params: dict[str, Any] = {
            "target_status": TARGET_STATUS,
            "target_action_type": TARGET_ACTION_TYPE,
            "target_format": TARGET_FORMAT,
            "banner_flag_key": BANNER_FLAG_KEY,
        }

        if self.has_runs_action_type:
            where_parts.append("rr.action_type = :target_action_type")
        else:
            select_parts.append("JOIN actions a ON a.id = rr.action_id")
            where_parts.append("a.action_type = :target_action_type")

        if self.has_runs_format:
            where_parts.append("LOWER(COALESCE(rr.format::text, '')) = :target_format")
        else:
            where_parts.append(
                "LOWER(COALESCE(rr.artifacts->'pr_bundle'->>'format', rr.artifacts->>'format', '')) = :target_format"
            )

        if self.has_runs_artifacts:
            # Keep repeated runs idempotent when status cannot be migrated (e.g., enum mismatch).
            where_parts.append("COALESCE(rr.artifacts->>:banner_flag_key, 'false') <> 'true'")
        if self.banner_column:
            where_parts.append(f"COALESCE(rr.{self.banner_column}, FALSE) = FALSE")

        sql = " ".join(select_parts) + " WHERE " + " AND ".join(where_parts) + " ORDER BY rr.created_at ASC"
        if isinstance(limit, int) and limit > 0:
            sql += " LIMIT :limit_count"
            params["limit_count"] = limit

        rows = self.session.execute(text(sql), params).mappings().all()
        result: list[TargetRun] = []
        for row in rows:
            raw_artifacts = row.get("artifacts")
            artifacts = dict(raw_artifacts) if isinstance(raw_artifacts, dict) else {}
            result.append(TargetRun(run_id=str(row["id"]), artifacts=artifacts))
        return result

    def _can_filter_action_type(self) -> bool:
        if self.has_runs_action_type:
            return True
        return self.has_actions_table and self.has_runs_action_id and self.has_actions_action_type

    def _can_filter_format(self) -> bool:
        return self.has_runs_format or self.has_runs_artifacts

    def mark_verification_required(self, run: TargetRun) -> UpdateResult:
        assignments: list[str] = []
        params: dict[str, Any] = {"run_id": run.run_id, "target_status": TARGET_STATUS}

        status_updated = False
        banner_updated = False

        if self.status_update_supported:
            assignments.append("status = :updated_status")
            params["updated_status"] = UPDATED_STATUS
            status_updated = True
        else:
            LOGGER.warning(
                "status column does not support '%s'; run %s will be banner-marked only.",
                UPDATED_STATUS,
                run.run_id,
            )

        if self.banner_column:
            assignments.append(f"{self.banner_column} = TRUE")
            banner_updated = True

        if self.has_runs_artifacts:
            artifacts = dict(run.artifacts)
            artifacts[BANNER_FLAG_KEY] = True
            artifacts[BANNER_REASON_KEY] = BANNER_REASON_VALUE
            artifacts[BANNER_MESSAGE_KEY] = BANNER_MESSAGE
            assignments.append("artifacts = CAST(:artifacts_json AS JSONB)")
            params["artifacts_json"] = json.dumps(artifacts)
            banner_updated = True

        if self.has_runs_updated_at:
            assignments.append("updated_at = NOW()")

        if not assignments:
            return UpdateResult(updated=False, status_updated=False, banner_updated=False)

        sql = (
            "UPDATE remediation_runs "
            f"SET {', '.join(assignments)} "
            "WHERE id = :run_id AND LOWER(status::text) = :target_status"
        )
        updated = self.session.execute(text(sql), params).rowcount > 0
        if not updated:
            return UpdateResult(updated=False, status_updated=False, banner_updated=False)
        return UpdateResult(updated=True, status_updated=status_updated, banner_updated=banner_updated)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Retroactively mark S3.1 CloudFormation no-op remediation runs as verification_required."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List matching runs without writing updates.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional safety cap on number of runs to process.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Python logging level (default: INFO).",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    logging.basicConfig(
        level=getattr(logging, str(args.log_level).upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )

    from backend.workers.database import get_session

    session = get_session()
    try:
        store = SqlRemediationRunStore(session)
        summary = apply_retroactive_check(store, dry_run=bool(args.dry_run), limit=args.limit)
        if not args.dry_run and summary.updated_runs > 0:
            session.commit()
        else:
            session.rollback()
    except Exception:
        session.rollback()
        LOGGER.exception("Retroactive check failed.")
        raise
    finally:
        session.close()

    LOGGER.info(
        "S3.1 CF no-op retroactive check summary: matched=%s updated=%s status_updates=%s banner_updates=%s dry_run=%s",
        summary.matched_runs,
        summary.updated_runs,
        summary.status_updates,
        summary.banner_updates,
        summary.dry_run,
    )
    if summary.run_ids:
        LOGGER.info("Affected run_ids: %s", ", ".join(summary.run_ids))

    print(json.dumps(summary.as_dict(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
