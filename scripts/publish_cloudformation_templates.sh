#!/usr/bin/env bash

set -euo pipefail

BUCKET_NAME="security-autopilot-templates"
REGION="eu-north-1"
PROJECT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || echo "$PWD/..")
READ_VERSION="v1.5.9"
WRITE_VERSION="v1.4.7"
READ_KEY="cloudformation/read-role/${READ_VERSION}.yaml"
WRITE_KEY="cloudformation/write-role/${WRITE_VERSION}.yaml"

echo "=== Security Autopilot CloudFormation Template Publisher ==="
echo "Bucket: $BUCKET_NAME"
echo "Region: $REGION"
echo ""

echo "[1/3] Uploading CloudFormation templates..."
python3 "$PROJECT_ROOT/scripts/upload_read_role_template.py" --bucket "$BUCKET_NAME" --region "$REGION"
python3 "$PROJECT_ROOT/scripts/upload_write_role_template.py" --bucket "$BUCKET_NAME" --region "$REGION"
echo "      Uploaded:"
echo "      - s3://${BUCKET_NAME}/${READ_KEY}"
echo "      - s3://${BUCKET_NAME}/${WRITE_KEY}"
echo ""

echo "[2/3] Verifying uploaded objects via S3 head-object..."
aws s3api head-object \
    --bucket "$BUCKET_NAME" \
    --key "$READ_KEY" \
    --region "$REGION" \
    --query '{content_type:ContentType,sse:ServerSideEncryption,etag:ETag}'
aws s3api head-object \
    --bucket "$BUCKET_NAME" \
    --key "$WRITE_KEY" \
    --region "$REGION" \
    --query '{content_type:ContentType,sse:ServerSideEncryption,etag:ETag}'
echo ""

echo "[3/3] Runtime note"
echo "      The template bucket remains private to anonymous callers."
echo "      Raw HTTPS object fetches may still return 403 when account-level public-access blocks stay enabled."
echo "      That is expected: the SaaS runtime generates presigned S3 TemplateURLs for Launch Stack flows."
echo "      Base template URLs:"
echo "      - https://${BUCKET_NAME}.s3.${REGION}.amazonaws.com/${READ_KEY}"
echo "      - https://${BUCKET_NAME}.s3.${REGION}.amazonaws.com/${WRITE_KEY}"
echo ""
echo "Publish complete."
