# Enforce SSL-only S3 requests - Action: 07ab40cb-e2c0-45c6-b124-f109e9a7c072
data "aws_iam_policy_document" "security_autopilot_ssl_enforcement" {
  statement {
    sid    = "DenyInsecureTransport"
    effect = "Deny"
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    actions = ["s3:*"]
    resources = [
      "arn:aws:s3:::phase2-live-c3-s35-224523z-029037611564",
      "arn:aws:s3:::phase2-live-c3-s35-224523z-029037611564/*",
    ]
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }

}

resource "aws_s3_bucket_policy" "security_autopilot" {
  bucket = "phase2-live-c3-s35-224523z-029037611564"
  policy = data.aws_iam_policy_document.security_autopilot_ssl_enforcement.json
}
