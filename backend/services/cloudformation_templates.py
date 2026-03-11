"""
CloudFormation template version detection and pre-signed URL generation from S3.

Automatically detects the latest version of CloudFormation templates from S3
by listing objects and comparing semantic versions. Generates pre-signed URLs
so CloudFormation can fetch templates from a private bucket (CloudFormation
only accepts S3-domain URLs — CloudFront domains are rejected).
"""
from __future__ import annotations

import logging
import re
import time
from typing import TYPE_CHECKING
from urllib.parse import urlparse

import boto3
from botocore.exceptions import ClientError

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client

logger = logging.getLogger(__name__)

# Cache for latest version (version_string, timestamp)
_version_cache: dict[str, tuple[str | None, float]] = {}
CACHE_TTL_SECONDS = 300  # 5 minutes

# Pre-signed URL expiry: 7 days (CloudFormation fetches within seconds of the user clicking)
PRESIGNED_URL_EXPIRY_SECONDS = 7 * 24 * 60 * 60


def parse_semantic_version(version_str: str) -> tuple[int, int, int] | None:
    """
    Parse semantic version string (e.g., 'v1.2.3' or '1.2.3') into (major, minor, patch).
    
    Returns None if version string is invalid.
    """
    # Remove 'v' prefix if present
    version_str = version_str.lstrip('v')
    
    # Match MAJOR.MINOR.PATCH format
    match = re.match(r'^(\d+)\.(\d+)\.(\d+)$', version_str)
    if not match:
        return None
    
    try:
        return (int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError:
        return None


def compare_versions(v1: tuple[int, int, int], v2: tuple[int, int, int]) -> int:
    """
    Compare two semantic versions.
    
    Returns:
        -1 if v1 < v2
         0 if v1 == v2
         1 if v1 > v2
    """
    if v1[0] != v2[0]:
        return -1 if v1[0] < v2[0] else 1
    if v1[1] != v2[1]:
        return -1 if v1[1] < v2[1] else 1
    if v1[2] != v2[2]:
        return -1 if v1[2] < v2[2] else 1
    return 0


def extract_bucket_and_key_from_url(url: str) -> tuple[str, str, str] | None:
    """
    Extract bucket name, region, and key prefix from S3 URL.
    
    Supports formats:
    - https://bucket.s3.region.amazonaws.com/path/to/file.yaml
    - https://bucket.s3-region.amazonaws.com/path/to/file.yaml
    
    Returns (bucket, region, key_prefix) or None if URL is invalid.
    """
    parsed = urlparse(url)
    
    if parsed.scheme not in ('http', 'https'):
        return None
    
    # Parse hostname: bucket.s3.region.amazonaws.com
    # Format: bucket-name.s3.region-name.amazonaws.com
    # Example: security-autopilot-templates.s3.eu-north-1.amazonaws.com
    hostname = parsed.hostname or ''
    
    # Match bucket.s3.region.amazonaws.com
    # Region name can contain dashes (e.g., eu-north-1) but no dots
    match = re.match(r'^([^.]+)\.s3\.([^.]+)\.amazonaws\.com$', hostname)
    if not match:
        return None
    
    bucket = match.group(1)
    region = match.group(2)
    
    # Extract key prefix (everything before the version segment)
    # e.g., /cloudformation/read-role/v1.1.0.yaml -> /cloudformation/read-role/
    path = parsed.path.lstrip('/')
    
    # Remove version segment (vX.Y.Z.yaml) to get prefix
    # Match pattern: .../vX.Y.Z.yaml or .../X.Y.Z.yaml
    version_match = re.search(r'/(v?\d+\.\d+\.\d+)\.yaml$', path)
    if version_match:
        # Remove the version segment
        key_prefix = path[:version_match.start() + 1]  # Include trailing /
    else:
        # If no version in URL, assume the path is the prefix
        key_prefix = path if path.endswith('/') else path + '/'
    
    return (bucket, region, key_prefix)


def get_latest_template_version(
    base_url: str,
    force_refresh: bool = False,
) -> str | None:
    """
    Get the latest CloudFormation template version from S3.
    
    Args:
        base_url: Full URL to a versioned template (e.g., 
                  https://bucket.s3.region.amazonaws.com/cloudformation/read-role/v1.1.0.yaml)
                  The version segment will be replaced with the latest found.
        force_refresh: If True, bypass cache and fetch fresh from S3.
    
    Returns:
        Full URL to the latest version, or None if:
        - URL is invalid
        - S3 access fails
        - No versions found
        - Cache is used and previous fetch failed
    
    The result is cached for CACHE_TTL_SECONDS (5 minutes) to avoid excessive S3 calls.
    """
    # Check cache first
    if not force_refresh:
        cached_version, cached_time = _version_cache.get(base_url, (None, 0))
        if cached_version is not None and (time.time() - cached_time) < CACHE_TTL_SECONDS:
            logger.debug(f"Using cached template version for {base_url}: {cached_version}")
            return cached_version
        elif cached_version is None and (time.time() - cached_time) < CACHE_TTL_SECONDS:
            # Previous fetch failed, return None without retrying
            logger.debug(f"Using cached failure for {base_url}")
            return None
    
    # Parse URL to extract bucket, region, and key prefix
    parsed = extract_bucket_and_key_from_url(base_url)
    if not parsed:
        logger.warning(f"Invalid template URL format: {base_url}")
        _version_cache[base_url] = (None, time.time())
        return None
    
    bucket, region, key_prefix = parsed
    
    try:
        # Create S3 client
        s3_client: S3Client = boto3.client("s3", region_name=region)
        
        # List objects with prefix
        logger.info(f"Listing S3 objects in s3://{bucket}/{key_prefix} to find latest template version")
        response = s3_client.list_objects_v2(
            Bucket=bucket,
            Prefix=key_prefix,
        )
        
        if "Contents" not in response:
            logger.warning(f"No objects found in s3://{bucket}/{key_prefix}")
            _version_cache[base_url] = (None, time.time())
            return None
        
        # Extract versions from object keys
        # Pattern: cloudformation/read-role/v1.2.3.yaml
        versions: list[tuple[tuple[int, int, int], str]] = []
        
        for obj in response["Contents"]:
            key = obj["Key"]
            # Extract version from key (e.g., v1.2.3.yaml or 1.2.3.yaml)
            version_match = re.search(r'/(v?\d+\.\d+\.\d+)\.yaml$', key)
            if version_match:
                version_str = version_match.group(1)
                parsed_version = parse_semantic_version(version_str)
                if parsed_version:
                    versions.append((parsed_version, version_str))
        
        if not versions:
            logger.warning(f"No valid versioned templates found in s3://{bucket}/{key_prefix}")
            _version_cache[base_url] = (None, time.time())
            return None
        
        # Find latest version (highest semantic version)
        latest_version_tuple, latest_version_str = max(versions, key=lambda x: x[0])
        logger.info(f"Found latest template version: {latest_version_str}")
        
        # Build new URL with latest version
        # Replace version segment in original URL
        version_pattern = re.compile(r'/v?\d+\.\d+\.\d+\.yaml$')
        if version_pattern.search(base_url):
            latest_url = version_pattern.sub(f'/{latest_version_str}.yaml', base_url)
        else:
            # If no version in original URL, append it
            base_url_clean = base_url.rstrip('/')
            latest_url = f"{base_url_clean}/{latest_version_str}.yaml"
        
        # Update cache
        _version_cache[base_url] = (latest_url, time.time())
        return latest_url
        
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        logger.error(f"Failed to list S3 objects for template version detection: {error_code} - {e}")
        # Cache failure for shorter time (1 minute)
        _version_cache[base_url] = (None, time.time() - (CACHE_TTL_SECONDS - 60))
        return None
    except Exception as e:
        logger.exception(f"Unexpected error detecting template version: {e}")
        _version_cache[base_url] = (None, time.time() - (CACHE_TTL_SECONDS - 60))
        return None


def generate_presigned_template_url(
    base_url: str,
    expires_in: int = PRESIGNED_URL_EXPIRY_SECONDS,
) -> str | None:
    """
    Resolve the latest template version from S3 and return a pre-signed URL.

    CloudFormation's TemplateURL only accepts S3-domain URLs — CloudFront and
    other custom domains are rejected with "TemplateURL must be a supported URL".
    A pre-signed URL uses the S3 hostname (bucket.s3.region.amazonaws.com) and
    embeds short-lived credentials in query params, so CloudFormation accepts it
    while the bucket remains fully private.

    Args:
        base_url: Configured HTTPS S3 URL (CloudFront or S3) for the template.
                  The S3 bucket and key are extracted from the configured URL.
        expires_in: Seconds until the pre-signed URL expires (default: 7 days).

    Returns:
        A pre-signed S3 URL valid for `expires_in` seconds, or None on failure.
    """
    # Resolve the configured URL to bucket + region + key.
    # The configured URL may still be a CloudFront URL (for the config.py default);
    # we always fall back to the original S3 bucket URL for signing.
    # First, try to resolve from the configured base_url directly (S3 URL).
    parsed = extract_bucket_and_key_from_url(base_url)

    if not parsed:
        # Could be a CloudFront URL — can't extract bucket from it. Cannot sign.
        logger.warning(
            "generate_presigned_template_url: cannot extract S3 bucket from URL %s. "
            "Set CLOUDFORMATION_*_TEMPLATE_URL to an S3 URL (not CloudFront) for pre-signed URL support.",
            base_url,
        )
        return None

    bucket, region, key_prefix = parsed

    # Resolve the latest version key
    latest_url = get_latest_template_version(base_url)
    if not latest_url:
        # Fall back to the base_url key itself
        latest_url = base_url

    # Re-parse the resolved latest URL to get the exact versioned key
    latest_parsed = extract_bucket_and_key_from_url(latest_url)
    if latest_parsed:
        _, _, resolved_prefix = latest_parsed
        # The resolved URL ends with /vX.Y.Z.yaml; rebuild the key
        path = urlparse(latest_url).path.lstrip("/")
    else:
        path = urlparse(base_url).path.lstrip("/")

    try:
        s3_client: S3Client = boto3.client("s3", region_name=region)
        presigned = s3_client.generate_presigned_url(
            ClientMethod="get_object",
            Params={"Bucket": bucket, "Key": path},
            ExpiresIn=expires_in,
        )
        logger.debug(
            "Generated pre-signed template URL for s3://%s/%s (expires in %ds)",
            bucket,
            path,
            expires_in,
        )
        return presigned
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        logger.error(
            "Failed to generate pre-signed URL for s3://%s/%s: %s - %s",
            bucket,
            path,
            error_code,
            e,
        )
        return None
    except Exception as e:
        logger.exception("Unexpected error generating pre-signed URL: %s", e)
        return None
