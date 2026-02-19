#!/usr/bin/env python3
"""
Deployment health gate: fail when API readiness endpoint is not healthy.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check API readiness endpoint.")
    parser.add_argument(
        "--url",
        required=True,
        help="Readiness endpoint URL (e.g. https://api.example.com/ready).",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=10.0,
        help="HTTP timeout in seconds.",
    )
    parser.add_argument(
        "--expected-status",
        type=int,
        default=200,
        help="Expected HTTP status code.",
    )
    parser.add_argument(
        "--expected-ready",
        choices=("true", "false", "any"),
        default="true",
        help="Expected JSON payload ready value (or 'any' to skip assertion).",
    )
    parser.add_argument(
        "--output-json",
        default="",
        help="Optional file path to write structured check results.",
    )
    parser.add_argument(
        "--print-body",
        action="store_true",
        help="Print raw response body in stdout.",
    )
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    req = Request(args.url, method="GET")
    status: int | None = None
    raw = ""
    payload: dict | None = None
    failure_reasons: list[str] = []
    ready_value: bool | None = None

    try:
        with urlopen(req, timeout=args.timeout_seconds) as resp:
            status = int(resp.status)
            raw = resp.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        status = int(exc.code)
        raw = exc.read().decode("utf-8", errors="replace")
    except URLError as exc:
        print(f"Readiness check failed: {exc.reason}", file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover - defensive safety for deployment script usage
        print(f"Readiness check failed: {exc}", file=sys.stderr)
        return 1

    if status != args.expected_status:
        failure_reasons.append(
            f"expected HTTP {args.expected_status}, got {status}"
        )

    try:
        payload = json.loads(raw) if raw else None
    except json.JSONDecodeError:
        payload = None
        if args.expected_ready != "any":
            failure_reasons.append("response body is not valid JSON")

    if payload is not None:
        ready_value = bool(payload.get("ready"))

    if args.expected_ready != "any":
        expected_ready = args.expected_ready == "true"
        if payload is None:
            failure_reasons.append("ready value cannot be asserted without JSON body")
        elif ready_value is not expected_ready:
            failure_reasons.append(
                f"expected ready={str(expected_ready).lower()}, got {str(ready_value).lower()}"
            )

    result = {
        "url": args.url,
        "http_status": status,
        "expected_status": args.expected_status,
        "ready": ready_value,
        "expected_ready": args.expected_ready,
        "status": payload.get("status") if isinstance(payload, dict) else None,
        "passed": not failure_reasons,
        "errors": failure_reasons,
        "raw_body": raw,
    }

    if args.output_json:
        out_path = Path(args.output_json)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    if args.print_body and raw:
        print(raw)

    if failure_reasons:
        print(
            "Readiness check failed: " + "; ".join(failure_reasons),
            file=sys.stderr,
        )
        return 1

    print(
        "Readiness check passed: "
        f"{args.url} (HTTP {status}, ready={str(ready_value).lower() if ready_value is not None else 'n/a'})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
