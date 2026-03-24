from __future__ import annotations

import argparse
import asyncio
import uuid

from sqlalchemy import select

from backend.database import AsyncSessionLocal
from backend.models.action import Action
from backend.models.action_group_action_state import ActionGroupActionState
from backend.models.enums import ActionGroupStatusBucket
from backend.services.action_run_confirmation import reevaluate_confirmation_for_actions_async


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reproject successful action-group states.")
    parser.add_argument("--tenant-id", type=uuid.UUID, required=True)
    parser.add_argument("--account-id")
    parser.add_argument("--action-type")
    return parser.parse_args()


async def _load_action_ids(args: argparse.Namespace) -> list[uuid.UUID]:
    async with AsyncSessionLocal() as session:
        stmt = (
            select(Action.id)
            .join(ActionGroupActionState, ActionGroupActionState.action_id == Action.id)
            .where(
                Action.tenant_id == args.tenant_id,
                ActionGroupActionState.latest_run_status_bucket
                == ActionGroupStatusBucket.run_successful_pending_confirmation,
            )
        )
        if args.account_id:
            stmt = stmt.where(Action.account_id == args.account_id)
        if args.action_type:
            stmt = stmt.where(Action.action_type == args.action_type)
        rows = (await session.execute(stmt)).all()
    return [row[0] for row in rows]


async def main() -> None:
    args = _parse_args()
    action_ids = await _load_action_ids(args)
    if not action_ids:
        print("No matching action-group states found.")
        return

    async with AsyncSessionLocal() as session:
        results = await reevaluate_confirmation_for_actions_async(session, action_ids=action_ids)
        await session.commit()

    buckets: dict[str, int] = {}
    for result in results:
        bucket = str(result.get("bucket") or "unknown")
        buckets[bucket] = buckets.get(bucket, 0) + 1

    print(f"Reprojected {len(results)} action-group states.")
    for bucket, count in sorted(buckets.items()):
        print(f"  {bucket}: {count}")


if __name__ == "__main__":
    asyncio.run(main())
