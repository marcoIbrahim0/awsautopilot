# Policy Snippets (Live Test C)

## C2 Before (existing bucket policy)
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "C2PreExistingDenyDeleteBucket",
      "Effect": "Deny",
      "Principal": "*",
      "Action": "s3:DeleteBucket",
      "Resource": "arn:aws:s3:::phase2-live-c2-trail-224523z-029037611564"
    },
    {
      "Sid": "AWSCloudTrailAclCheck",
      "Effect": "Allow",
      "Principal": {
        "Service": "cloudtrail.amazonaws.com"
      },
      "Action": "s3:GetBucketAcl",
      "Resource": "arn:aws:s3:::phase2-live-c2-trail-224523z-029037611564"
    },
    {
      "Sid": "AWSCloudTrailWrite",
      "Effect": "Allow",
      "Principal": {
        "Service": "cloudtrail.amazonaws.com"
      },
      "Action": "s3:PutObject",
      "Resource": "arn:aws:s3:::phase2-live-c2-trail-224523z-029037611564/AWSLogs/029037611564/CloudTrail/*",
      "Condition": {
        "StringEquals": {
          "s3:x-amz-acl": "bucket-owner-full-control"
        }
      }
    }
  ]
}
```

## C2 After (post CloudTrail bundle apply)
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AWSCloudTrailAclCheck",
      "Effect": "Allow",
      "Principal": {
        "Service": "cloudtrail.amazonaws.com"
      },
      "Action": "s3:GetBucketAcl",
      "Resource": "arn:aws:s3:::phase2-live-c2-trail-224523z-029037611564"
    },
    {
      "Sid": "AWSCloudTrailWrite",
      "Effect": "Allow",
      "Principal": {
        "Service": "cloudtrail.amazonaws.com"
      },
      "Action": "s3:PutObject",
      "Resource": "arn:aws:s3:::phase2-live-c2-trail-224523z-029037611564/AWSLogs/029037611564/CloudTrail/*",
      "Condition": {
        "StringEquals": {
          "s3:x-amz-acl": "bucket-owner-full-control"
        }
      }
    }
  ]
}
```

## C3 Before (existing deny)
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "C3PreExistingDenyDeleteBucket",
      "Effect": "Deny",
      "Principal": "*",
      "Action": "s3:DeleteBucket",
      "Resource": "arn:aws:s3:::phase2-live-c3-s35-224523z-029037611564"
    }
  ]
}
```

## C3 After (post S3.5 bundle apply)
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DenyInsecureTransport",
      "Effect": "Deny",
      "Principal": "*",
      "Action": "s3:*",
      "Resource": [
        "arn:aws:s3:::phase2-live-c3-s35-224523z-029037611564/*",
        "arn:aws:s3:::phase2-live-c3-s35-224523z-029037611564"
      ],
      "Condition": {
        "Bool": {
          "aws:SecureTransport": "false"
        }
      }
    }
  ]
}
```

## C4 After (no prior policy -> SSL deny only)
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DenyInsecureTransport",
      "Effect": "Deny",
      "Principal": "*",
      "Action": "s3:*",
      "Resource": [
        "arn:aws:s3:::phase2-live-c4-s35-224523z-029037611564/*",
        "arn:aws:s3:::phase2-live-c4-s35-224523z-029037611564"
      ],
      "Condition": {
        "Bool": {
          "aws:SecureTransport": "false"
        }
      }
    }
  ]
}
```
