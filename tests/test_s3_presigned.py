"""Unit tests for s3_presigned (Step 13.3)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from backend.services.s3_presigned import generate_presigned_url


def test_generate_presigned_url_returns_url() -> None:
    """generate_presigned_url returns a presigned URL string."""
    with patch("backend.services.s3_presigned.boto3") as mock_boto3:
        mock_client = MagicMock()
        mock_client.generate_presigned_url.return_value = "https://s3.example.com/presigned"
        mock_boto3.client.return_value = mock_client
        url = generate_presigned_url("my-bucket", "path/to/key")
    assert url == "https://s3.example.com/presigned"
    mock_client.generate_presigned_url.assert_called_once()
    call_kw = mock_client.generate_presigned_url.call_args[1]
    assert call_kw["Params"]["Bucket"] == "my-bucket"
    assert call_kw["Params"]["Key"] == "path/to/key"
    assert call_kw["ExpiresIn"] == 3600
