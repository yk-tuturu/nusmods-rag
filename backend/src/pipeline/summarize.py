"""
summarize.py

Generates a cached AI summary and difficulty rating for each cleaned course
(data/processed/<CODE>.json), blending the official NUSMods description with
student Disqus reviews. Written to data/summaries/<CODE>.json so api.py can
serve it without calling the LLM on every request.

When a course has few reviews, its official description is emphasized more -
a handful of reviews is weak evidence of what the course is actually like, so
the summary leans on the (always-present, always-accurate) NUSMods metadata
instead of over-indexing on a couple of anecdotes.

USAGE
-----
python summarize.py                    # summarize every course in data/processed/
python summarize.py --courses CS2030S,MA1521
python summarize.py --force            # regenerate even if a fresh cached copy exists
python summarize.py --max-age-days 7   # treat cached summaries older than this as stale
"""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

BACKEND_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BACKEND_DIR / ".env")

PROCESSED_DIR = BACKEND_DIR / "data" / "processed"
SUMMARIES_DIR = BACKEND_DIR / "data" / "summaries"

MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

# Below this many reviews, the prompt explicitly tells the model to treat
# reviews as thin anecdotal evidence and lean on the official description.
FEW_REVIEWS_THRESHOLD = 5

# Reviews are sorted by (likes, recency) and appended to the prompt until this
# character budget is spent, so one course with hundreds of long reviews
# doesn't blow up the prompt - roughly 3k tokens at ~4 chars/token.
MAX_REVIEW_CHARS = 12000

# Cached summaries older than this are treated as stale by default. Course
# metadata and reviews both change slowly, so this can be generous.
DEFAULT_MAX_AGE_DAYS = 30.0

SYSTEM_PROMPT = """You are writing a short cached summary of an NUS course for a course \
directory. You'll be given the course's official NUSMods description/metadata and a \
selection of student reviews scraped from Disqus. Respond with a JSON object with two \
fields:

"summary": a concise summary (roughly 150-250 words) covering what the course actually \
covers/is like, workload and difficulty, and any standout notes about teaching or \
assessment style, if the reviews mention them. Write it as neutral, third-person prose \
(not a first-person review, and not addressed to "you"). Do not fabricate specifics \
(professor names, exact grading weights, etc.) that aren't present in the given context. \
If the review count note below says reviews are few, rely mainly on the official \
description for facts and treat the reviews only as light color/anecdotes, not as \
representative of the whole cohort's experience.

"difficulty": your best-estimate rating of the course's difficulty, as a number from 0 \
(trivial) to 5 (extremely difficult), decimals allowed (e.g. 3.5). Base this primarily on \
how reviewers describe the difficulty/workload; if reviews are few or absent, estimate \
cautiously from the workload, prerequisites, and description instead, and lean toward the \
middle of the scale rather than an extreme when genuinely unsure."""


def summary_path(code: str) -> Path:
    return SUMMARIES_DIR / f"{code}.json"


def is_fresh(path: Path, max_age_days: float) -> bool:
    if not path.exists():
        return False
    age_secs = time.time() - path.stat().st_mtime
    return age_secs < max_age_days * 86400


def load_course(code: str) -> dict | None:
    path = PROCESSED_DIR / f"{code}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def load_cached_summary(code: str) -> dict | None:
    path = summary_path(code)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def save_summary(code: str, data: dict) -> Path:
    SUMMARIES_DIR.mkdir(parents=True, exist_ok=True)
    path = summary_path(code)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY not set. Add it to backend/.env or the environment."
            )
        _client = OpenAI(api_key=api_key)
    return _client


def build_description_block(course: dict) -> str:
    parts = [f"{course.get('code', '')}: {course.get('title') or '(no title)'}"]
    if course.get("mcs"):
        parts.append(f"Modular credits: {course['mcs']}")
    if course.get("department"):
        parts.append(f"Department: {course['department']}")
    if course.get("prereqs"):
        parts.append(f"Prerequisites: {course['prereqs']}")
    if course.get("preclusion"):
        parts.append(f"Preclusion: {course['preclusion']}")
    parts.append(f"S/U-able: {'Yes' if course.get('su') else 'No'}")
    if course.get("description"):
        parts.append(f"Official description: {course['description']}")
    return "\n".join(parts)


def build_review_block(reviews: list[dict]) -> tuple[str, int]:
    """Sort reviews by (likes desc, recency desc) and concatenate them into a
    prompt block up to MAX_REVIEW_CHARS. Returns (block, reviews_used)."""
    ranked = sorted(reviews, key=lambda r: (r.get("likes", 0), r.get("date") or ""), reverse=True)

    blocks = []
    used = 0
    total_chars = 0
    for r in ranked:
        text = r.get("text", "")
        date = r.get("date", "")
        likes = r.get("likes", 0)
        entry = f"[{date} | {likes} likes]\n{text}"

        if total_chars > 0 and total_chars + len(entry) > MAX_REVIEW_CHARS:
            break
        blocks.append(entry)
        total_chars += len(entry)
        used += 1
        if total_chars >= MAX_REVIEW_CHARS:
            break

    return "\n\n---\n\n".join(blocks), used


def build_user_prompt(course: dict) -> tuple[str, int, int]:
    """Returns (prompt, total_review_count, reviews_used_in_prompt)."""
    reviews = course.get("reviews", [])
    review_count = len(reviews)
    review_block, reviews_used = build_review_block(reviews)

    if review_count == 0:
        review_note = "This course currently has no scraped student reviews at all."
    elif review_count < FEW_REVIEWS_THRESHOLD:
        review_note = (
            f"This course currently has only {review_count} review(s), which is very "
            "little evidence - emphasize the official description over the reviews."
        )
    else:
        review_note = f"This course has {review_count} review(s), {reviews_used} of which are included below."

    sections = [
        "=== Official NUSMods metadata ===",
        build_description_block(course),
        "",
        f"=== Student reviews ({review_note}) ===",
        review_block if review_block else "(none available)",
    ]
    return "\n".join(sections), review_count, reviews_used


RESPONSE_SCHEMA = {
    "name": "course_summary",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
            "difficulty": {"type": "number"},
        },
        "required": ["summary", "difficulty"],
        "additionalProperties": False,
    },
}


def generate_summary_text(course: dict) -> tuple[str, float, int, int]:
    """Returns (summary_text, difficulty, review_count, reviews_used)."""
    prompt, review_count, reviews_used = build_user_prompt(course)
    client = _get_client()

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
        response_format={"type": "json_schema", "json_schema": RESPONSE_SCHEMA},
    )
    parsed = json.loads(response.choices[0].message.content)
    summary_text = parsed["summary"]
    # Clamp defensively in case the model strays outside the requested 0-5
    # range despite the schema/prompt - a rating just outside the range is
    # more useful clamped than silently trusted or dropped.
    difficulty = round(max(0.0, min(5.0, float(parsed["difficulty"]))), 1)
    return summary_text, difficulty, review_count, reviews_used


def summarize_course(code: str, force: bool = False, max_age_days: float = DEFAULT_MAX_AGE_DAYS) -> dict | None:
    """Return the cached summary for `code`, regenerating it first if missing
    or stale. Returns None if there's no processed data for the course."""
    path = summary_path(code)
    if not force and is_fresh(path, max_age_days):
        return load_cached_summary(code)

    course = load_course(code)
    if course is None:
        return None

    summary_text, difficulty, review_count, reviews_used = generate_summary_text(course)
    data = {
        "code": course["code"],
        "title": course.get("title"),
        "summary": summary_text,
        "difficulty": difficulty,
        "review_count": review_count,
        "reviews_used": reviews_used,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": MODEL,
    }
    save_summary(code, data)
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--courses", help="comma-separated course codes to summarize (default: all processed files)")
    parser.add_argument("--force", action="store_true", help="regenerate even if a fresh cached copy exists")
    parser.add_argument("--max-age-days", type=float, default=DEFAULT_MAX_AGE_DAYS,
                         help=f"skip regenerating if cached copy is younger than this (default {DEFAULT_MAX_AGE_DAYS})")
    args = parser.parse_args()

    if args.courses:
        codes = [c.strip().upper() for c in args.courses.split(",") if c.strip()]
    else:
        codes = sorted(p.stem for p in PROCESSED_DIR.glob("*.json"))

    for code in codes:
        print(f"{code}...")
        result = summarize_course(code, force=args.force, max_age_days=args.max_age_days)
        if result is None:
            print(f"  ! skip {code}: no processed data found")
            continue
        print(f"  -> difficulty {result['difficulty']}/5, {result['review_count']} review(s) "
              f"({result['reviews_used']} used) -> {summary_path(code)}")


if __name__ == "__main__":
    main()
