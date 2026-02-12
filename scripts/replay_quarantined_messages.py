#!/usr/bin/env python3
"""
Replay queue-contract quarantine payloads back into worker queues.

Default mode is dry-run and does not publish or delete anything.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

import boto3
from botocore.exceptions import ClientError

from backend.utils.sqs import parse_queue_region
from worker.config import settings


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Replay contract-quarantine SQS messages to target queues.",
    )
    parser.add_argument(
        "--quarantine-queue-url",
        default=(settings.SQS_CONTRACT_QUARANTINE_QUEUE_URL or "").strip(),
        help="Queue URL to read quarantined payloads from (default: SQS_CONTRACT_QUARANTINE_QUEUE_URL).",
    )
    parser.add_argument(
        "--target-queue-url",
        default="",
        help="Optional override target queue URL. If unset, uses each envelope's original_queue_url.",
    )
    parser.add_argument(
        "--max-messages",
        type=int,
        default=10,
        help="Maximum messages per receive call (1-10).",
    )
    parser.add_argument(
        "--polls",
        type=int,
        default=1,
        help="How many receive calls to perform before exiting.",
    )
    parser.add_argument(
        "--wait-time-seconds",
        type=int,
        default=2,
        help="SQS long-poll wait time per receive call.",
    )
    parser.add_argument(
        "--visibility-timeout",
        type=int,
        default=120,
        help="Visibility timeout applied when receiving quarantine messages.",
    )
    parser.add_argument(
        "--reason-code",
        default="",
        help="Optional filter; only process envelopes with this reason_code.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually publish replay payloads. Without this flag, script is dry-run.",
    )
    parser.add_argument(
        "--delete-on-success",
        action="store_true",
        help="Delete quarantine messages after successful replay publish (only with --execute).",
    )
    return parser


def _extract_replay_payload(envelope: dict[str, Any]) -> str | None:
    original_body = envelope.get("original_body")
    if isinstance(original_body, str) and original_body:
        return original_body

    parsed_job = envelope.get("parsed_job")
    if isinstance(parsed_job, dict):
        return json.dumps(parsed_job, separators=(",", ":"), ensure_ascii=True)

    return None


def _receive_messages(
    sqs: Any,
    *,
    queue_url: str,
    max_messages: int,
    wait_time_seconds: int,
    visibility_timeout: int,
) -> list[dict[str, Any]]:
    response = sqs.receive_message(
        QueueUrl=queue_url,
        MaxNumberOfMessages=max(1, min(10, max_messages)),
        WaitTimeSeconds=max(0, min(20, wait_time_seconds)),
        VisibilityTimeout=max(0, visibility_timeout),
        AttributeNames=["All"],
        MessageAttributeNames=["All"],
    )
    return response.get("Messages", [])


def main() -> int:
    args = _build_parser().parse_args()

    quarantine_queue_url = (args.quarantine_queue_url or "").strip()
    if not quarantine_queue_url:
        print("Error: --quarantine-queue-url is required (or set SQS_CONTRACT_QUARANTINE_QUEUE_URL).", file=sys.stderr)
        return 2

    reason_filter = (args.reason_code or "").strip()
    dry_run = not args.execute

    quarantine_region = parse_queue_region(quarantine_queue_url)
    quarantine_sqs = boto3.client("sqs", region_name=quarantine_region)
    target_clients: dict[str, Any] = {}

    seen = 0
    matched = 0
    replayed = 0
    deleted = 0
    skipped = 0
    failed = 0

    mode = "DRY-RUN" if dry_run else "EXECUTE"
    print(f"Mode: {mode}")
    print(f"Quarantine queue: {quarantine_queue_url}")

    for poll_idx in range(max(1, args.polls)):
        try:
            messages = _receive_messages(
                quarantine_sqs,
                queue_url=quarantine_queue_url,
                max_messages=args.max_messages,
                wait_time_seconds=args.wait_time_seconds,
                visibility_timeout=args.visibility_timeout,
            )
        except ClientError as exc:
            print(f"[poll {poll_idx + 1}] receive_message failed: {exc}", file=sys.stderr)
            return 1

        if not messages:
            print(f"[poll {poll_idx + 1}] no messages")
            continue

        for msg in messages:
            seen += 1
            message_id = msg.get("MessageId", "unknown")
            receipt_handle = msg.get("ReceiptHandle", "")
            body_raw = msg.get("Body", "")

            try:
                envelope = json.loads(body_raw)
            except json.JSONDecodeError:
                failed += 1
                print(f"[{message_id}] skip: quarantine payload is not valid JSON")
                continue

            if not isinstance(envelope, dict):
                failed += 1
                print(f"[{message_id}] skip: quarantine payload is not a JSON object")
                continue

            reason_code = str(envelope.get("reason_code") or "unknown")
            if reason_filter and reason_code != reason_filter:
                skipped += 1
                print(f"[{message_id}] skip: reason_code={reason_code} does not match filter={reason_filter}")
                continue

            matched += 1
            target_queue_url = (args.target_queue_url or envelope.get("original_queue_url") or "").strip()
            replay_payload = _extract_replay_payload(envelope)
            payload_sha = str(envelope.get("payload_sha256") or "")

            if not target_queue_url:
                failed += 1
                print(f"[{message_id}] skip: no target queue URL (set --target-queue-url or original_queue_url)")
                continue
            if not replay_payload:
                failed += 1
                print(f"[{message_id}] skip: missing replay payload (original_body/parsed_job)")
                continue

            payload_preview = replay_payload[:120].replace("\n", " ")
            print(
                f"[{message_id}] reason={reason_code} target={target_queue_url} sha256={payload_sha} "
                f"payload_preview={payload_preview!r}"
            )

            if dry_run:
                continue

            target_region = parse_queue_region(target_queue_url)
            target_sqs = target_clients.get(target_region)
            if target_sqs is None:
                target_sqs = boto3.client("sqs", region_name=target_region)
                target_clients[target_region] = target_sqs

            try:
                target_sqs.send_message(QueueUrl=target_queue_url, MessageBody=replay_payload)
                replayed += 1
            except ClientError as exc:
                failed += 1
                print(f"[{message_id}] replay failed: {exc}")
                continue

            if args.delete_on_success and receipt_handle:
                try:
                    quarantine_sqs.delete_message(
                        QueueUrl=quarantine_queue_url,
                        ReceiptHandle=receipt_handle,
                    )
                    deleted += 1
                except ClientError as exc:
                    failed += 1
                    print(f"[{message_id}] replayed but failed to delete quarantine message: {exc}")

    print(
        "Summary: "
        f"seen={seen} matched={matched} replayed={replayed} deleted={deleted} "
        f"skipped={skipped} failed={failed}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
