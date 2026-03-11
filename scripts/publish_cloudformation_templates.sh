#!/usr/bin/env bash

set -e

# Configuration
BUCKET_NAME="security-autopilot-templates"
REGION="eu-north-1"
PROJECT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || echo "$PWD/..")
POLICY_FILE="$PROJECT_ROOT/infrastructure/cloudformation/templates-bucket-policy.json"
TEST_VERSION="v1.5.4"
TEST_URL="https://${BUCKET_NAME}.s3.${REGION}.amazonaws.com/cloudformation/read-role/${TEST_VERSION}.yaml"

echo "=== Security Autopilot CloudFormation Template Publisher ==="
echo "Bucket: $BUCKET_NAME"
echo "Region: $REGION"
echo ""

# 1. Ensure Block Public Access allows Bucket Policies
echo "[1/4] Configuring S3 Block Public Access..."
echo "      Disabling BlockPublicPolicy so a public bucket policy can be applied."
aws s3api put-public-access-block \
    --bucket "$BUCKET_NAME" \
    --region "$REGION" \
    --public-access-block-configuration "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=false,RestrictPublicBuckets=false"
echo "      Waiting 10 seconds for Block Public Access changes to propagate..."
sleep 10
echo "      Done."
echo ""

# 2. Apply Bucket Policy
echo "[2/4] Applying Targeted Bucket Policy..."
if [ ! -f "$POLICY_FILE" ]; then
    echo "ERROR: Policy file not found at $POLICY_FILE"
    exit 1
fi
aws s3api put-bucket-policy \
    --bucket "$BUCKET_NAME" \
    --region "$REGION" \
    --policy "file://$POLICY_FILE"
echo "      Done. cloudformation/* prefix is now publicly readable."
echo ""

# 3. Upload Templates
# (We only do read-role by default, but others can be added here)
echo "[3/4] Uploading Read Role Template (versions explicitly handled by python script)..."
python3 "$PROJECT_ROOT/scripts/upload_read_role_template.py" --bucket "$BUCKET_NAME" --region "$REGION"
python3 "$PROJECT_ROOT/scripts/upload_write_role_template.py" --bucket "$BUCKET_NAME" --region "$REGION" || true # ignore failure if missing
echo "      Done."
echo ""

# 4. Verification Check
echo "[4/4] Verifying Template Accessibility..."
echo "      Running: curl -sI $TEST_URL"
STATUS_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$TEST_URL")

if [ "$STATUS_CODE" -eq 200 ]; then
    echo "      SUCCESS! Template is accessible (HTTP 200)."
else
    echo "      WARNING: Template returned HTTP $STATUS_CODE (Expected 200)."
    echo "      It might take a few seconds for the policy to propagate, or the version might not exist."
fi

echo ""
echo "Publish complete. Onboarding should now work!"
