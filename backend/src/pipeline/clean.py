"""
clean.py

Cleans and normalizes raw scraped course data (data/raw/<CODE>.json) into
a consistent schema written to data/processed/<CODE>.json:

    {
      "code": str, "title": str, "description": str, "prereqs": str,
      "prereq_tree": dict|None, "preclusion": str|None,
      "fulfill_requirements": list[str],
      "mcs": str, "department": str, "su": bool,
      "reviews": [{"id": str|None, "parent": str|None, "author": str,
                   "date": str, "text": str, "likes": int}]
    }

"prereq_tree" is NUSMods' structured and/or prerequisite tree (from
nusmods_api.extract_summary's "prereq_tree", itself NUSMods' `prereqTree`)
- the authoritative counterpart to the free-text "prereqs" string, meant
for exact checking rather than prose. "fulfill_requirements" is the
reverse edge: module codes that list this module as (one option for)
their prerequisite. Older raw metadata predating these fields defaults
to None/None/[] respectively.

"su" is whether the module can be taken S/U (from the NUSMods module's
`attributes.su` field via nusmods_api.extract_summary; missing/older raw
metadata defaults to False, not unknown).

"id"/"parent" identify reply chains (parent is the id of the comment being
replied to, or None for a top-level comment) — see chunk.py, which groups a
thread's replies into the same chunk. Older raw data scraped before this
field existed will simply have id=None, parent=None for every review, which
chunk.py treats as all-top-level (unchanged prior behavior).

Cleaning rules:
  - strip HTML from comment text (raw scrape already does this, but re-run
    defensively in case raw data came from elsewhere)
  - drop comments under MIN_REVIEW_LENGTH characters (likely not real reviews)
  - drop isSpam / isDeleted posts
  - dedupe identical comment text within a course

USAGE
-----
python clean.py              # clean every file in data/raw/
python clean.py --courses CS2030,CS2040
"""

from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path

MIN_REVIEW_LENGTH = 15

BACKEND_DIR = Path(__file__).resolve().parents[2]
RAW_DIR = BACKEND_DIR / "data" / "raw"
PROCESSED_DIR = BACKEND_DIR / "data" / "processed"


def clean_html(raw_html: str) -> str:
    text = re.sub(r"<[^>]+>", "", raw_html or "")
    text = html.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"[ \t]*\n[ \t]*", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def clean_reviews(raw_reviews: list[dict]) -> list[dict]:
    cleaned = []
    seen_text = set()

    for r in raw_reviews:
        if r.get("is_spam") or r.get("is_deleted"):
            continue

        text = clean_html(r.get("text", ""))
        if len(text) < MIN_REVIEW_LENGTH:
            continue
        if text in seen_text:
            continue
        seen_text.add(text)

        cleaned.append({
            "id": r.get("id"),
            "parent": r.get("parent"),
            "author": r.get("author", "unknown"),
            "date": r.get("created_at", ""),
            "text": text,
            "likes": r.get("likes", 0),
        })

    return cleaned


def clean_course(raw: dict) -> dict:
    metadata = raw.get("metadata") or {}
    return {
        "code": raw.get("code"),
        "title": metadata.get("title"),
        "description": metadata.get("description"),
        "prereqs": metadata.get("prereqs"),
        "prereq_tree": metadata.get("prereq_tree"),
        "preclusion": metadata.get("preclusion"),
        "fulfill_requirements": metadata.get("fulfill_requirements") or [],
        "mcs": metadata.get("mcs"),
        "department": metadata.get("department"),
        "su": metadata.get("su", False),
        "reviews": clean_reviews(raw.get("reviews", [])),
    }


def process_file(raw_path: Path) -> Path:
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    cleaned = clean_course(raw)

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    out_path = PROCESSED_DIR / raw_path.name
    out_path.write_text(json.dumps(cleaned, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--courses", help="comma-separated course codes to clean (default: all raw files)")
    args = parser.parse_args()

    if args.courses:
        codes = [c.strip().upper() for c in args.courses.split(",") if c.strip()]
        raw_paths = [RAW_DIR / f"{c}.json" for c in codes]
    else:
        raw_paths = sorted(RAW_DIR.glob("*.json"))

    for raw_path in raw_paths:
        if not raw_path.exists():
            print(f"skip {raw_path.name}: no raw file")
            continue
        out_path = process_file(raw_path)
        cleaned = json.loads(out_path.read_text(encoding="utf-8"))
        print(f"{raw_path.stem}: {len(cleaned['reviews'])} reviews -> {out_path}")


if __name__ == "__main__":
    main()
