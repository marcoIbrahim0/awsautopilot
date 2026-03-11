#!/usr/bin/env bash
# scripts/setup_cloudfront_templates.sh
# Creates CloudFront OAC, Distribution, and configures S3 Bucket Policy
set -e

BUCKET_NAME="security-autopilot-templates"
REGION="eu-north-1"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
OAC_NAME="security-autopilot-templates-oac"

echo "=== AWS Security Autopilot CloudFront Setup ==="

# 1. Create Origin Access Control
echo "[1/4] Creating Origin Access Control (OAC)..."
OAC_ID=$(aws cloudfront create-origin-access-control \
  --origin-access-control-config "Name=$OAC_NAME,Description='OAC for templates bucket',SigningProtocol=sigv4,SigningBehavior=always,OriginAccessControlOriginType=s3" \
  --query 'OriginAccessControl.Id' --output text 2>/dev/null || aws cloudfront list-origin-access-controls \
  --query "OriginAccessControlList.Items[?Name=='$OAC_NAME'].Id | [0]" --output text)

if [ "$OAC_ID" == "None" ] || [ -z "$OAC_ID" ]; then
    echo "Failed to create or find OAC."
    exit 1
fi
echo "      OAC ID: $OAC_ID"

# 2. Create CloudFront Distribution
echo "[2/4] Creating CloudFront Distribution..."
# Check if a distribution for this origin already exists
DIST_ID=$(aws cloudfront list-distributions \
    --query "DistributionList.Items[?Origins.Items[0].Id=='$BUCKET_NAME-origin'].Id | [0]" \
    --output text)

if [ "$DIST_ID" == "None" ] || [ -z "$DIST_ID" ]; then
    CALLER_REFERENCE=$(date +%s)
    cat <<EOF > /tmp/cf-dist-config.json
{
  "CallerReference": "$CALLER_REFERENCE",
  "Aliases": {"Quantity": 0},
  "DefaultRootObject": "",
  "Origins": {
    "Quantity": 1,
    "Items": [
      {
        "Id": "$BUCKET_NAME-origin",
        "DomainName": "$BUCKET_NAME.s3.$REGION.amazonaws.com",
        "OriginPath": "",
        "CustomHeaders": {"Quantity": 0},
        "S3OriginConfig": {"OriginAccessIdentity": ""},
        "OriginAccessControlId": "$OAC_ID",
        "ConnectionAttempts": 3,
        "ConnectionTimeout": 10,
        "OriginShield": {"Enabled": false}
      }
    ]
  },
  "DefaultCacheBehavior": {
    "TargetOriginId": "$BUCKET_NAME-origin",
    "ForwardedValues": {"QueryString": false, "Cookies": {"Forward": "none"}},
    "TrustedSigners": {"Enabled": false, "Quantity": 0},
    "TrustedKeyGroups": {"Enabled": false, "Quantity": 0},
    "ViewerProtocolPolicy": "redirect-to-https",
    "MinTTL": 0,
    "AllowedMethods": {"Quantity": 2, "Items": ["HEAD", "GET"], "CachedMethods": {"Quantity": 2, "Items": ["HEAD", "GET"]}},
    "SmoothStreaming": false,
    "DefaultTTL": 86400,
    "MaxTTL": 31536000,
    "Compress": true
  },
  "CacheBehaviors": {"Quantity": 0},
  "CustomErrorResponses": {"Quantity": 0},
  "Comment": "Security Autopilot Templates",
  "PriceClass": "PriceClass_100",
  "Enabled": true,
  "ViewerCertificate": {"CloudFrontDefaultCertificate": true},
  "Restrictions": {"GeoRestriction": {"RestrictionType": "none", "Quantity": 0}},
  "WebACLId": "",
  "HttpVersion": "http2",
  "IsIPV6Enabled": true
}
EOF

    CREATE_OUT=$(aws cloudfront create-distribution --distribution-config file:///tmp/cf-dist-config.json)
    DIST_ID=$(echo "$CREATE_OUT" | jq -r '.Distribution.Id')
    DIST_DOMAIN=$(echo "$CREATE_OUT" | jq -r '.Distribution.DomainName')
    echo "      Created new Distribution: $DIST_ID"
else
    DIST_DOMAIN=$(aws cloudfront get-distribution --id "$DIST_ID" --query 'Distribution.DomainName' --output text)
    echo "      Distribution already exists: $DIST_ID"
fi
echo "      Domain: $DIST_DOMAIN"

# 3. Update S3 Bucket Policy
echo "[3/4] Updating S3 Bucket Policy to allow CloudFront OAC..."
DIST_ARN="arn:aws:cloudfront::$ACCOUNT_ID:distribution/$DIST_ID"

cat <<EOF > /tmp/s3-oac-policy.json
{
    "Version": "2012-10-17",
    "Statement": {
        "Sid": "AllowCloudFrontServicePrincipalReadOnly",
        "Effect": "Allow",
        "Principal": {
            "Service": "cloudfront.amazonaws.com"
        },
        "Action": "s3:GetObject",
        "Resource": "arn:aws:s3:::$BUCKET_NAME/cloudformation/*",
        "Condition": {
            "StringEquals": {
                "AWS:SourceArn": "$DIST_ARN"
            }
        }
    }
}
EOF

aws s3api put-bucket-policy --bucket "$BUCKET_NAME" --policy file:///tmp/s3-oac-policy.json
echo "      Done."

# 4. Instructions
echo ""
echo "[4/4] Next Steps:"
echo "1. Wait a few minutes for the CloudFront distribution to deploy."
echo "2. Update your .env files or config.py to use the new domain:"
echo "   https://$DIST_DOMAIN/cloudformation/read-role/v1.5.4.yaml"
echo ""
echo "Test command:"
echo "curl -I https://$DIST_DOMAIN/cloudformation/read-role/v1.5.4.yaml"
