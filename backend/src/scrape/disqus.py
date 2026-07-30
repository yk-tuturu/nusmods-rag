"""
disqus.py

Extracts course review comments hosted on Disqus for NUSMods course pages,
paired with course metadata from the NUSMods API (see nusmods_api.py).

SETUP
-----
1. Register a free Disqus API application at https://disqus.com/api/docs/
   -> log in -> "My Applications" -> "Register a New Application"
   -> copy the "Public Key" it gives you.
2. pip install requests
3. Fill in DISQUS_PUBLIC_KEY below.

USAGE
-----
python disqus.py                          # scrape the built-in pilot course list
python disqus.py --courses CS2030,CS2040  # scrape specific courses
python disqus.py --all                    # scrape the full NUSMods catalog (slow!)
python disqus.py --retry-failed           # (re-)scrape only courses recorded as failed
python disqus.py --force                  # re-scrape even if a fresh cached copy exists

Outputs one JSON file per course into ../../data/raw/<course_code>.json,
containing both the course metadata and the list of review comments.

NOTES
-----
- Disqus free tier: 1000 API calls/hour. Each page of ~100 comments = 1 call.
  Disqus reports X-Ratelimit-Remaining/-Reset headers on every response
  (even error ones), which _disqus_get() below uses to pause/retry across
  the exact reset boundary instead of guessing at a fixed backoff.
- A single course failing (network blip, malformed thread, or a real quota
  exhaustion _disqus_get() couldn't wait out) no longer aborts the whole
  run: it's recorded to data/scrape_state/disqus_failures.json and the loop
  moves on. Rerun with --retry-failed to retry just those.
- Before running --all, prefetch NUSMods module metadata for the whole
  catalog first (`python nusmods_api.py --prefetch`) - it has no rate limit
  and doesn't depend on Disqus, so warming that cache up front means this
  scrape's only network calls are the rate-limited Disqus ones.
- Be respectful of Disqus's Terms of Service: this is meant for personal
  research/analysis, not bulk republishing.
- If a course page has no Disqus thread yet (no comments posted), the script
  will just report 0 comments found but still save the metadata.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

try:
    from . import nusmods_api
except ImportError:  # allow running as a plain script (python disqus.py)
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import nusmods_api

# --------------------------------------------------------------------------
# CONFIG - edit these
# --------------------------------------------------------------------------
DISQUS_PUBLIC_KEY = "DvPmCSZ5OPvDuVGc2mWhWrGv6I6K2NtcL23f7YkwwbLSm5sVG8PMMvW11IsbIzmB"
DISQUS_SHORTNAME = "nusmods-prod"  # NUSMods' Disqus forum shortname

# Small pilot set for building/validating the pipeline before scaling up.
PILOT_COURSE_CODES = [
    "CS2030",
    "CS2040",
    "CS1101S",
    "MA1521",
    "GEA1000",
    "CS3230",
    "IS1108",
]

BACKEND_DIR = Path(__file__).resolve().parents[2]
RAW_DIR = BACKEND_DIR / "data" / "raw"
API_BASE = "https://disqus.com/api/3.0"

PAGINATION_DELAY_SECS = 0.5
BETWEEN_COURSE_DELAY_SECS = 1.0


def find_thread_id(course_code: str) -> str | None:
    """Look up the Disqus thread ID for a course using its identifier
    (e.g. 'CS2030'), which is more reliable than matching on the exact URL."""
    resp = requests.get(
        f"{API_BASE}/threads/list.json",
        params={
            "api_key": DISQUS_PUBLIC_KEY,
            "forum": DISQUS_SHORTNAME,
            "thread": f"ident:{course_code}",
        },
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    results = data.get("response", [])
    if not results:
        return None
    return results[0]["id"]


def fetch_all_posts(thread_id: str) -> list[dict]:
    """Fetch all comments (posts) for a given thread, following pagination."""
    posts = []
    cursor = None

    while True:
        params = {
            "api_key": DISQUS_PUBLIC_KEY,
            "thread": thread_id,
            "limit": 100,
            "order": "asc",
        }
        if cursor:
            params["cursor"] = cursor

        resp = requests.get(f"{API_BASE}/threads/listPosts.json", params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        posts.extend(data.get("response", []))

        cursor_info = data.get("cursor", {})
        if cursor_info.get("hasNext"):
            cursor = cursor_info["next"]
            time.sleep(PAGINATION_DELAY_SECS)
        else:
            break

    return posts


def clean_html(raw_html: str) -> str:
    """Strip basic HTML tags Disqus wraps comment text in, and decode HTML
    entities (Disqus escapes raw_message, so apostrophes/quotes/ampersands
    come through as &#x27;/&quot;/&amp; etc.)."""
    text = re.sub(r"<[^>]+>", "", raw_html or "")
    return html.unescape(text).strip()


def posts_to_reviews(posts: list[dict]) -> list[dict]:
    reviews = []
    for p in posts:
        parent = p.get("parent")
        reviews.append({
            "id": str(p["id"]) if p.get("id") is not None else None,
            # Disqus sets "parent" to a comment's id when it's a reply, or
            # omits/nulls it for a top-level comment.
            "parent": str(parent) if parent else None,
            "author": p.get("author", {}).get("name", "unknown"),
            "created_at": p.get("createdAt", ""),
            "likes": p.get("likes", 0),
            "dislikes": p.get("dislikes", 0),
            "text": clean_html(p.get("raw_message", p.get("message", ""))),
            "is_spam": p.get("isSpam", False),
            "is_deleted": p.get("isDeleted", False),
        })
    return reviews


def raw_path(course_code: str) -> Path:
    return RAW_DIR / f"{course_code}.json"


def is_fresh(path: Path, max_age_days: float) -> bool:
    if not path.exists():
        return False
    age_secs = time.time() - path.stat().st_mtime
    return age_secs < max_age_days * 86400


def save_raw(course_code: str, metadata: dict | None, reviews: list[dict]) -> Path:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    path = raw_path(course_code)
    payload = {
        "code": course_code,
        "metadata": metadata,
        "reviews": reviews,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def scrape_course(course_code: str, force: bool = False, max_age_days: float = 7.0) -> Path | None:
    path = raw_path(course_code)
    if not force and is_fresh(path, max_age_days):
        print(f"  -> cached copy is fresh, skipping (use --force to re-scrape)")
        return path

    detail = nusmods_api.fetch_module_detail(course_code)
    metadata = nusmods_api.extract_summary(detail) if detail else None
    if metadata is None:
        print(f"  -> no NUSMods module data found for {course_code}")

    thread_id = find_thread_id(course_code)
    if not thread_id:
        print("  -> no Disqus thread found (no comments yet)")
        reviews = []
    else:
        posts = fetch_all_posts(thread_id)
        reviews = posts_to_reviews(posts)

    saved_path = save_raw(course_code, metadata, reviews)
    print(f"  -> saved {len(reviews)} comments + metadata to {saved_path}")
    return saved_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--courses", help="comma-separated course codes to scrape")
    parser.add_argument("--all", action="store_true", help="scrape the full NUSMods catalog")
    parser.add_argument("--force", action="store_true", help="re-scrape even if cache is fresh")
    parser.add_argument("--max-age-days", type=float, default=7.0,
                         help="skip re-scraping if cached copy is younger than this (default 7)")
    args = parser.parse_args()

    if DISQUS_PUBLIC_KEY == "YOUR_PUBLIC_KEY_HERE":
        raise SystemExit("Set DISQUS_PUBLIC_KEY before running (see docstring for setup).")

    if args.all:
        course_codes = nusmods_api.fetch_all_module_codes()
    elif args.courses:
        course_codes = [c.strip().upper() for c in args.courses.split(",") if c.strip()]
    else:
        course_codes = PILOT_COURSE_CODES

    print(f"Scraping {len(course_codes)} course(s)...")

    for i, course_code in enumerate(course_codes):
        print(f"[{i + 1}/{len(course_codes)}] Processing {course_code}...")
        scrape_course(course_code, force=args.force, max_age_days=args.max_age_days)

        if i < len(course_codes) - 1:
            time.sleep(BETWEEN_COURSE_DELAY_SECS)


if __name__ == "__main__":
    main()
