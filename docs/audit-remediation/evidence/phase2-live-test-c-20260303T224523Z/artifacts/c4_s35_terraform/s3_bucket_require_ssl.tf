# Enforce SSL-only S3 requests - Action: b0a41ec5-5ef9-4131-9d34-b793c9e1e49d
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
      "arn:aws:s3:::phase2-live-c4-s35-224523z-029037611564",
      "arn:aws:s3:::phase2-live-c4-s35-224523z-029037611564/*",
    ]
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }

}

resource "aws_s3_bucket_policy" "security_autopilot" {
  bucket = "phase2-live-c4-s35-224523z-029037611564"
  policy = data.aws_iam_policy_document.security_autopilot_ssl_enforcement.json
}
