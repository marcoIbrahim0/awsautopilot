#!/usr/bin/env python3
"""
Upload the write-role CloudFormation template to S3 with versioned naming.

Usage (from project root):
  python scripts/upload_write_role_template.py [--version VERSION] [--bucket BUCKET] [--region REGION]

Defaults: version=v1.0.0, bucket=security-autopilot-templates, region=eu-north-1.
Requires AWS credentials with s3:PutObject on the bucket.
"""
from __future__ import annotations

import argparse
import os
import sys

import boto3

TEMPLATE_REL_PATH = "infrastructure/cloudformation/write-role-template.yaml"
S3_KEY_PREFIX = "cloudformation/write-role"


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload write-role template to S3 with version naming")
    parser.add_argument("--version", default="v1.0.0", help="Version segment for key (e.g. v1.0.0)")
    parser.add_argument("--bucket", default="security-autopilot-templates", help="S3 bucket name")
    parser.add_argument("--region", default="eu-north-1", help="AWS region for the bucket")
    args = parser.parse_args()

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    template_path = os.path.join(project_root, TEMPLATE_REL_PATH)
    if not os.path.isfile(template_path):
        print(f"Template not found: {template_path}", file=sys.stderr)
        sys.exit(1)

    key = f"{S3_KEY_PREFIX}/{args.version}.yaml"
    url = f"https://{args.bucket}.s3.{args.region}.amazonaws.com/{key}"

    try:
        s3 = boto3.client("s3", region_name=args.region)
        with open(template_path, "rb") as f:
            s3.put_object(
                Bucket=args.bucket,
                Key=key,
                Body=f.read(),
                ContentType="text/yaml",
            )
        print(f"Uploaded: s3://{args.bucket}/{key}")
        print(f"URL: {url}")
    except Exception as e:
        print(f"Upload failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
