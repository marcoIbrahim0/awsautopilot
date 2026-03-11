#!/usr/bin/env python3
"""
find_prospects.py — LinkedIn Prospect Finder for Ocypheris
===========================================================

Uses Google X-Ray search (site:linkedin.com/in/) to find LinkedIn profiles
matching your Ideal Customer Profiles (ICPs) WITHOUT logging into LinkedIn.

This is completely safe and carries zero risk of LinkedIn account bans.

Usage:
    # Search for SOC 2-focused technical leaders
    python scripts/find_prospects.py --campaign soc2

    # Search for recently hired engineering leaders
    python scripts/find_prospects.py --campaign new-hire

    # Search for AWS DevOps roles at startups
    python scripts/find_prospects.py --campaign aws-devops

    # Run all campaigns
    python scripts/find_prospects.py --campaign all

    # Custom query
    python scripts/find_prospects.py --query 'intitle:"Head of Engineering" "AWS" "startup"'

    # Control output
    python scripts/find_prospects.py --campaign soc2 --results 30 --output prospects.csv

Requirements:
    pip install googlesearch-python requests beautifulsoup4

Optional (for faster / higher-volume search):
    Set GOOGLE_CSE_API_KEY and GOOGLE_CSE_ID env vars to use the official
    Google Custom Search API instead of the free googlesearch library.
    See: https://developers.google.com/custom-search/v1/overview
"""

import argparse
import csv
import os
import sys
import time
import re
from datetime import datetime

# ---------------------------------------------------------------------------
# Campaign definitions — tuned to your GTM strategy in client_finding_strategy.md
# ---------------------------------------------------------------------------

CAMPAIGNS = {
    "soc2": {
        "name": "SOC 2 Decision-Makers",
        "description": "CTOs / VP Engineering / Head of DevOps mentioning SOC 2 or compliance.",
        "query": (
            'site:linkedin.com/in/ '
            'intitle:CTO OR intitle:"VP Engineering" OR intitle:"Head of Engineering" '
            '"SOC 2" OR SOC2 OR compliance '
            'AWS -jobs'
        ),
        "hook": (
            "Saw you're working on compliance infrastructure—we help AWS-first teams automate "
            "SOC 2 evidence and fix high-risk gaps in 48h. Happy to run a free baseline scan."
        ),
    },
    "new-hire": {
        "name": "Recently Hired Engineering Leaders",
        "description": "New Heads of Engineering / Lead DevOps in AWS environments.",
        "query": (
            'site:linkedin.com/in/ '
            'intitle:"Head of Engineering" OR intitle:"Lead DevOps" '
            'AWS "new role" OR "started a new" '
            '-jobs'
        ),
        "hook": (
            "Congrats on the new role! As you audit the new infra, our zero-agent tool gives you "
            "a full AWS security baseline in 48h without deploying anything."
        ),
    },
    "aws-devops": {
        "name": "AWS DevOps at Startups",
        "description": "Platform / DevOps engineers at early-stage companies.",
        "query": (
            'site:linkedin.com/in/ '
            'intitle:DevOps OR intitle:Platform '
            'AWS startup OR seed OR "Series A" '
            '-jobs'
        ),
        "hook": (
            "Noticed you're running AWS infra at a startup. We built a read-only security scanner "
            "that flags your biggest gaps and ships Terraform PRs to fix them. Want to see a sample report?"
        ),
    },
}


# ---------------------------------------------------------------------------
# Search backends
# ---------------------------------------------------------------------------

def _search_via_googlesearch_library(query: str, num_results: int, sleep_interval: float = 2.5):
    """Use the free googlesearch-python library (no API key needed)."""
    try:
        from googlesearch import search  # type: ignore
    except ImportError:
        print("ERROR: googlesearch-python is not installed.")
        print("Run: pip install googlesearch-python")
        sys.exit(1)

    results = []
    try:
        # advanced=True returns SearchResult objects (url, title, description)
        for res in search(query, num_results=num_results, lang="en", sleep_interval=sleep_interval, advanced=True):
            results.append({
                "url": res.url,
                "title": res.title,
                "snippet": res.description
            })
            time.sleep(0.5)  # extra courtesy delay
    except Exception as e:
        print(f"  ⚠  Search error: {e}")
        if "429" in str(e):
            import urllib.parse
            encoded_query = urllib.parse.quote(query)
            search_url = f"https://www.google.com/search?q={encoded_query}"
            print(f"\n💡 GOOGLE BLOCKED ACCESS (Too Many Requests).")
            print(f"   You can see the results manually in your browser here:")
            print(f"   {search_url}")
    return results


def _search_via_custom_search_api(query: str, num_results: int):
    """
    Use the official Google Custom Search JSON API.

    Requires:
        GOOGLE_CSE_API_KEY  — your API key from Google Cloud Console
        GOOGLE_CSE_ID       — your Custom Search Engine ID (set to search linkedin.com)

    Free tier: 100 queries/day. Paid: $5 per 1000 queries.
    """
    try:
        import requests  # type: ignore
    except ImportError:
        print("ERROR: requests is not installed. Run: pip install requests")
        sys.exit(1)

    api_key = os.environ.get("GOOGLE_CSE_API_KEY")
    cse_id = os.environ.get("GOOGLE_CSE_ID")

    if not api_key or not cse_id:
        print("ERROR: Set GOOGLE_CSE_API_KEY and GOOGLE_CSE_ID environment variables to use the API backend.")
        sys.exit(1)

    base_url = "https://www.googleapis.com/customsearch/v1"
    results = []
    # Max 10 per request; paginate as needed
    for start in range(1, num_results + 1, 10):
        batch = min(10, num_results - start + 1)
        params = {"key": api_key, "cx": cse_id, "q": query, "num": batch, "start": start}
        resp = requests.get(base_url, params=params, timeout=15)
        if resp.status_code != 200:
            print(f"  ⚠  API error {resp.status_code}: {resp.text[:200]}")
            break
        data = resp.json()
        for item in data.get("items", []):
            results.append({
                "url": item.get("link", ""),
                "title": item.get("title", ""),
                "snippet": item.get("snippet", ""),
            })
        if len(data.get("items", [])) < batch:
            break  # no more pages
        time.sleep(0.3)

    return results


def search_linkedin(query: str, num_results: int, use_api: bool = False):
    """Run the search using the appropriate backend."""
    if use_api or (os.environ.get("GOOGLE_CSE_API_KEY") and os.environ.get("GOOGLE_CSE_ID")):
        return _search_via_custom_search_api(query, num_results)
    else:
        return _search_via_googlesearch_library(query, num_results)


# ---------------------------------------------------------------------------
# Result helpers
# ---------------------------------------------------------------------------

def extract_name_from_url(url: str) -> str:
    """Best-effort name extraction from a LinkedIn profile URL slug."""
    match = re.search(r"linkedin\.com/in/([^/?]+)", url)
    if not match:
        return ""
    slug = match.group(1)
    # slugs like "jane-doe-12345678" → "Jane Doe"
    parts = re.split(r"[-_]", slug)
    # drop trailing numeric IDs
    parts = [p for p in parts if p and not re.fullmatch(r"\d+", p)]
    return " ".join(p.capitalize() for p in parts[:3])


def is_valid_profile_url(url: str) -> bool:
    return bool(re.search(r"linkedin\.com/in/[a-zA-Z0-9\-_%.]+", url))


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def write_csv(rows: list[dict], output_path: str):
    fieldnames = ["campaign", "campaign_name", "name_guess", "url", "title", "snippet", "outreach_hook"]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"\n✅ Saved {len(rows)} prospects → {output_path}")


def print_preview(rows: list[dict], limit: int = 5):
    preview = rows[:limit]
    for i, row in enumerate(preview, 1):
        print(f"\n  [{i}] {row.get('name_guess') or '(name unknown)'}")
        print(f"       URL    : {row['url']}")
        if row.get("title"):
            print(f"       Title  : {row['title']}")
        if row.get("snippet"):
            snippet = row["snippet"].replace("\n", " ")[:120]
            print(f"       Snippet: {snippet}…")
    if len(rows) > limit:
        print(f"\n  … and {len(rows) - limit} more. See the CSV for the full list.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_campaign(campaign_key: str, num_results: int) -> list[dict]:
    campaign = CAMPAIGNS[campaign_key]
    print(f"\n{'─' * 60}")
    print(f"  Campaign  : {campaign['name']}")
    print(f"  ICP desc  : {campaign['description']}")
    print(f"  Searching for up to {num_results} results…")
    print(f"{'─' * 60}")

    raw = search_linkedin(campaign["query"], num_results)

    rows = []
    for item in raw:
        url = item.get("url", "")
        if not is_valid_profile_url(url):
            continue
        rows.append({
            "campaign": campaign_key,
            "campaign_name": campaign["name"],
            "name_guess": extract_name_from_url(url),
            "url": url,
            "title": item.get("title", ""),
            "snippet": item.get("snippet", ""),
            "outreach_hook": campaign["hook"],
        })

    print(f"  Found {len(rows)} valid profile URLs.")
    return rows


def run_custom_query(query: str, num_results: int) -> list[dict]:
    print(f"\n{'─' * 60}")
    print(f"  Custom query: {query[:80]}…" if len(query) > 80 else f"  Custom query: {query}")
    print(f"  Searching for up to {num_results} results…")
    print(f"{'─' * 60}")

    raw = search_linkedin(query, num_results)
    rows = []
    for item in raw:
        url = item.get("url", "")
        if not is_valid_profile_url(url):
            continue
        rows.append({
            "campaign": "custom",
            "campaign_name": "Custom Query",
            "name_guess": extract_name_from_url(url),
            "url": url,
            "title": item.get("title", ""),
            "snippet": item.get("snippet", ""),
            "outreach_hook": "— personalise manually —",
        })

    print(f"  Found {len(rows)} valid profile URLs.")
    return rows


def main():
    parser = argparse.ArgumentParser(
        description="Find LinkedIn prospects via Google X-Ray search (no login required).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--campaign",
        choices=list(CAMPAIGNS.keys()) + ["all"],
        default="soc2",
        help="Which ICP campaign to run. Use 'all' to run every campaign.",
    )
    parser.add_argument(
        "--query",
        type=str,
        default=None,
        help="Skip a campaign and run a fully custom Google query instead.",
    )
    parser.add_argument(
        "--results",
        type=int,
        default=20,
        help="Maximum LinkedIn profiles to retrieve per campaign (default: 20).",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output CSV file path. Defaults to prospects_YYYYMMDD_HHMMSS.csv in the current directory.",
    )
    parser.add_argument(
        "--preview",
        type=int,
        default=5,
        metavar="N",
        help="Number of results to preview in terminal (default: 5).",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("  Ocypheris LinkedIn Prospect Finder")
    print("  (Google X-Ray search — no login required)")
    print("=" * 60)

    all_rows: list[dict] = []

    if args.query:
        all_rows = run_custom_query(args.query, args.results)
    elif args.campaign == "all":
        for key in CAMPAIGNS:
            rows = run_campaign(key, args.results)
            all_rows.extend(rows)
            if key != list(CAMPAIGNS.keys())[-1]:
                print("\n  ⏳ Pausing 5 s between campaigns to be polite to Google…")
                time.sleep(5)
    else:
        all_rows = run_campaign(args.campaign, args.results)

    if not all_rows:
        print("\n⚠  No valid LinkedIn profiles found. Try again in a few minutes (Google rate-limits heavy queries).")
        sys.exit(0)

    # Deduplicate by URL
    seen = set()
    deduped = []
    for row in all_rows:
        if row["url"] not in seen:
            seen.add(row["url"])
            deduped.append(row)

    print_preview(deduped, args.preview)

    output_path = args.output or f"prospects_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    write_csv(deduped, output_path)

    print("\n💡 Next steps:")
    print("   1. Open the CSV in Excel / Google Sheets.")
    print("   2. Manually review each profile URL.")
    print("   3. Copy the 'outreach_hook' column as your conversation starter.")
    print("   4. Send the 48h Baseline Report offer to qualified profiles.")
    print()


if __name__ == "__main__":
    main()
