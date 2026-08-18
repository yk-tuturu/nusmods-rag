"""
chunk.py

Splits cleaned per-course data (data/processed/<CODE>.json) into embeddable
chunks with metadata:

  - one "info" chunk per course: title + description + prereqs (rendered from
    the structured prereq tree when available, see nusmods_api.format_prereq_tree)
    + mcs + department + fulfill_requirements
  - one or more "review" chunks per course: each reply thread (a top-level
    comment plus any replies to it, via the "id"/"parent" fields from
    clean.py) kept together as a unit, or short adjacent threads merged up
    to MAX_CHUNK_CHARS. A thread with no replies is just the one comment,
    so courses without reply data chunk exactly as before. Replies are
    frequently a back-and-forth between two *different* students (not the
    original reviewer elaborating), so each reply is labeled with its
    author and indented by its depth in the thread — otherwise a multi-person
    conversation reads as one garbled paragraph with no indication who said
    what to whom. Standalone comments and reply threads are merged into
    separate chunks (never mixed in the same one), so each chunk's
    "is_thread" flag below is unambiguous - see retriever.py, which
    deprioritizes reply-thread chunks slightly since a back-and-forth is
    often lower-signal than a standalone review.
  - one "programme" chunk per markdown section in programme/*.md (degree
    requirement documents, e.g. CS.md, BBA.md, GE.md), split at every "#" or
    "##" header - see split_markdown_sections(). programme/_common.md is
    skipped here: it's small and universally relevant, so generate.py injects
    it directly as static context instead of going through retrieval.

Writes all chunks (across every processed course, plus every programme doc)
to a single JSONL file at data/chunks/chunks.jsonl, one JSON object per line:

    {"id": str, "course_code": str|None, "chunk_type": "info"|"review"|"programme",
     "text": str, "date": str|None, "likes": int|None, "is_thread": bool,
     "prereq_tree": dict|None, "programme_code": str|None, "section_title": str|None}

"prereq_tree" is only ever set on "info" chunks (None on "review" and
"programme" chunks) - it's the raw structured tree carried alongside the
rendered prose in "text" so embed.py can also store it as exact-checkable
metadata. "is_thread" is only meaningful on "review" chunks (always False
otherwise); for a merged chunk it's the date of its most recent thread, not
its oldest, so recency-based retrieval isn't working off a stale timestamp.
"programme_code" and "section_title" are only set on "programme" chunks.

USAGE
-----
python chunk.py
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]

try:
    from src.scrape.nusmods_api import format_prereq_tree
except ImportError:  # running as a plain script rather than a package module
    import sys
    sys.path.insert(0, str(BACKEND_DIR))
    from src.scrape.nusmods_api import format_prereq_tree

# ~500 tokens ballpark, approximated as ~4 chars/token
MAX_CHUNK_CHARS = 2000
# Some modules unlock 40+ downstream modules - cap so one line doesn't
# dominate the chunk.
FULFILL_REQUIREMENTS_CAP = 8

PROCESSED_DIR = BACKEND_DIR / "data" / "processed"
PROGRAMME_DIR = BACKEND_DIR / "programme"
CHUNKS_DIR = BACKEND_DIR / "data" / "chunks"
CHUNKS_PATH = CHUNKS_DIR / "chunks.jsonl"

# Matches a markdown "#" or "##" header line (but not "###+", which none of
# the programme docs use at the top level we care about).
HEADER_PATTERN = re.compile(r"^(#{1,2})\s+(.*?)\s*$", re.MULTILINE)


def build_info_chunk(course: dict) -> dict | None:
    parts = []
    if course.get("title"):
        parts.append(f"{course['code']}: {course['title']}")
    if course.get("mcs"):
        parts.append(f"Modular credits: {course['mcs']}")
    if course.get("department"):
        parts.append(f"Department: {course['department']}")

    # Prefer the structured prereq tree (authoritative) over the free-text
    # "prereqs" description; fall back to the free text if there's no tree.
    prereq_tree = course.get("prereq_tree")
    prereq_text = format_prereq_tree(prereq_tree) if prereq_tree else None
    if prereq_text:
        parts.append(f"Prerequisites: {prereq_text}")
    elif course.get("prereqs"):
        parts.append(f"Prerequisites: {course['prereqs']}")

    fulfill_requirements = course.get("fulfill_requirements") or []
    if fulfill_requirements:
        shown = ", ".join(fulfill_requirements[:FULFILL_REQUIREMENTS_CAP])
        extra = len(fulfill_requirements) - FULFILL_REQUIREMENTS_CAP
        if extra > 0:
            shown += f", and {extra} more"
        parts.append(f"Required for: {shown}")

    parts.append(f"S/U-able: {'Yes' if course.get('su') else 'No'}")
    if course.get("description"):
        parts.append(f"Description: {course['description']}")

    if not parts:
        return None

    return {
        "id": f"{course['code']}_info",
        "course_code": course["code"],
        "chunk_type": "info",
        "text": "\n".join(parts),
        "date": None,
        "likes": None,
        # Kept alongside the rendered prose above so embed.py can also store
        # it as exact-checkable structured metadata (see embed.py).
        "prereq_tree": prereq_tree,
    }


def group_into_threads(reviews: list[dict]) -> list[list[tuple[dict, int]]]:
    """Group flat reviews into threads: each top-level comment followed by
    its replies (recursively), in chronological order, paired with each
    reply's depth (0 = the top-level comment) so formatting can preserve
    the conversation structure. A reply whose parent was dropped during
    cleaning (spam/dedupe) or was never captured (older scrapes without
    id/parent) just becomes its own top-level thread."""
    by_id = {r["id"]: r for r in reviews if r.get("id")}
    children: dict[str, list[dict]] = {}
    top_level = []

    for r in reviews:
        parent = r.get("parent")
        if parent and parent in by_id:
            children.setdefault(parent, []).append(r)
        else:
            top_level.append(r)

    def collect(review: dict, depth: int = 0) -> list[tuple[dict, int]]:
        thread = [(review, depth)]
        for child in sorted(children.get(review.get("id"), []), key=lambda c: c.get("date") or ""):
            thread.extend(collect(child, depth + 1))
        return thread

    top_level.sort(key=lambda r: r.get("date") or "")
    return [collect(r) for r in top_level]


def format_thread(thread: list[tuple[dict, int]]) -> str:
    root, _ = thread[0]
    lines = [root.get("text", "")]
    for reply, depth in thread[1:]:
        indent = "  " * depth
        author = reply.get("author") or "unknown"
        lines.append(f"{indent}↳ {author} replied: {reply.get('text', '')}")
    return "\n".join(lines)


def build_review_chunks(course: dict) -> list[dict]:
    threads = group_into_threads(course.get("reviews", []))
    chunks: list[dict] = []

    # Two buffers so a merged chunk's is_thread flag is unambiguous - never
    # "some of this chunk had replies, some didn't".
    buffers = {
        False: {"texts": [], "dates": [], "likes": 0, "len": 0},
        True: {"texts": [], "dates": [], "likes": 0, "len": 0},
    }

    def flush(is_thread: bool):
        buf = buffers[is_thread]
        if not buf["texts"]:
            return
        idx = len(chunks)
        chunks.append({
            "id": f"{course['code']}_review_{idx}",
            "course_code": course["code"],
            "chunk_type": "review",
            "text": "\n\n".join(buf["texts"]),
            # Most recent thread in the buffer, not the oldest, so
            # recency-based retrieval isn't working off a stale timestamp.
            "date": max((d for d in buf["dates"] if d), default=None),
            "likes": buf["likes"],
            "is_thread": is_thread,
        })
        buf["texts"] = []
        buf["dates"] = []
        buf["likes"] = 0
        buf["len"] = 0

    for thread in threads:
        text = format_thread(thread)
        if not text.strip():
            continue
        is_thread = len(thread) > 1
        thread_date = thread[0][0].get("date")
        thread_likes = sum(r.get("likes", 0) for r, _ in thread)

        # A long thread stands on its own chunk.
        if len(text) >= MAX_CHUNK_CHARS:
            flush(is_thread)
            idx = len(chunks)
            chunks.append({
                "id": f"{course['code']}_review_{idx}",
                "course_code": course["code"],
                "chunk_type": "review",
                "text": text,
                "date": thread_date,
                "likes": thread_likes,
                "is_thread": is_thread,
            })
            continue

        # Would this thread push the buffer over the cap? Flush first.
        buf = buffers[is_thread]
        if buf["len"] + len(text) > MAX_CHUNK_CHARS:
            flush(is_thread)
            buf = buffers[is_thread]

        buf["texts"].append(text)
        buf["dates"].append(thread_date)
        buf["likes"] += thread_likes
        buf["len"] += len(text)

    flush(False)
    flush(True)
    return chunks


def split_markdown_sections(text: str) -> list[dict]:
    """Split a programme doc into sections at every "#" or "##" header line,
    regardless of level - the docs mix header levels inconsistently (e.g.
    BBA.md uses "##" for its intro and "#" for later sections), so a strict
    hierarchy isn't reliable, but every header line is still a genuine
    section boundary worth its own chunk.

    Returns an ordered list of {"title": str, "parent": str | None, "body":
    str}. Content before the first header becomes a single "Overview"
    section. "parent" is the nearest preceding "#"-level header, used to
    disambiguate two "##" sections that share a title but sit under
    different parents - e.g. GE.md has two "## Data Literacy" sections: one
    under the pillar-description intro, one under "List of Courses approved
    under the GE pillars". Without the parent, a chunker keyed on title
    alone would collide the two."""
    matches = list(HEADER_PATTERN.finditer(text))
    if not matches:
        body = text.strip()
        return [{"title": "Overview", "parent": None, "body": body}] if body else []

    sections = []
    preamble = text[:matches[0].start()].strip()
    if preamble:
        sections.append({"title": "Overview", "parent": None, "body": preamble})

    current_parent = None
    for i, m in enumerate(matches):
        level = len(m.group(1))
        title = m.group(2).strip()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[m.end():end].strip()

        if level == 1:
            current_parent = title
            parent = None
        else:
            parent = current_parent

        if body:
            sections.append({"title": title, "parent": parent, "body": body})

    return sections


def build_programme_chunks(path: Path) -> list[dict]:
    programme_code = path.stem
    text = path.read_text(encoding="utf-8")
    chunks = []
    for idx, section in enumerate(split_markdown_sections(text)):
        # Disambiguate same-titled subsections under different parents (see
        # split_markdown_sections docstring) and give the embedded text a
        # heading, since a section's body alone doesn't always mention what
        # it's about (e.g. a bare course list doesn't say "Data Literacy").
        if section["parent"] and section["parent"] != section["title"]:
            section_title = f"{section['parent']} — {section['title']}"
        else:
            section_title = section["title"]

        chunks.append({
            "id": f"{programme_code}_prog_{idx}",
            "course_code": None,
            "chunk_type": "programme",
            "programme_code": programme_code,
            "section_title": section_title,
            "text": f"{programme_code} programme — {section_title}\n\n{section['body']}",
            "date": None,
            "likes": None,
        })
    return chunks


def build_chunks_for_course(course: dict) -> list[dict]:
    chunks = []
    info_chunk = build_info_chunk(course)
    if info_chunk:
        chunks.append(info_chunk)
    chunks.extend(build_review_chunks(course))
    return chunks


def load_existing_chunks() -> list[dict]:
    if not CHUNKS_PATH.exists():
        return []
    chunks = []
    with CHUNKS_PATH.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                chunks.append(json.loads(line))
    return chunks


def build_programme_chunk_list() -> list[dict]:
    all_chunks = []
    programme_paths = sorted(
        p for p in PROGRAMME_DIR.glob("*.md") if not p.stem.startswith("_")
    )
    for path in programme_paths:
        programme_chunks = build_programme_chunks(path)
        all_chunks.extend(programme_chunks)
        print(f"{path.stem} (programme): {len(programme_chunks)} chunks")
    return all_chunks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--courses", help="comma-separated course codes to chunk (default: all processed files)")
    # Course data can grow to the full NUSMods catalog (thousands of chunks
    # once every course has been scraped) while programme docs stay tiny -
    # re-deriving the whole course side just to pick up a programme.md edit
    # is wasteful at best and, on a small production VM, OOM-killing at
    # worst (see the CI incident this flag was added to fix). This rebuilds
    # only the programme chunks and merges them into whatever's already in
    # chunks.jsonl, leaving existing course chunks untouched rather than
    # re-reading every file in data/processed/.
    parser.add_argument(
        "--programme-only",
        action="store_true",
        help="rebuild only programme/*.md chunks, merged into the existing chunks.jsonl "
        "(course chunks are left as-is, not re-derived from data/processed/)",
    )
    args = parser.parse_args()

    if args.programme_only:
        existing = load_existing_chunks()
        course_chunks = [c for c in existing if c.get("chunk_type") != "programme"]
        stale_programme_count = len(existing) - len(course_chunks)
        print(f"keeping {len(course_chunks)} existing course chunks as-is "
              f"(dropping {stale_programme_count} stale programme chunks)")
        all_chunks = course_chunks + build_programme_chunk_list()
    else:
        if args.courses:
            codes = [c.strip().upper() for c in args.courses.split(",") if c.strip()]
            paths = [PROCESSED_DIR / f"{c}.json" for c in codes]
        else:
            paths = sorted(PROCESSED_DIR.glob("*.json"))

        all_chunks = []
        for path in paths:
            if not path.exists():
                print(f"skip {path.name}: no processed file")
                continue
            course = json.loads(path.read_text(encoding="utf-8"))
            course_chunks = build_chunks_for_course(course)
            all_chunks.extend(course_chunks)
            print(f"{course['code']}: {len(course_chunks)} chunks")

        all_chunks.extend(build_programme_chunk_list())

    CHUNKS_DIR.mkdir(parents=True, exist_ok=True)
    with CHUNKS_PATH.open("w", encoding="utf-8") as f:
        for chunk in all_chunks:
            f.write(json.dumps(chunk, ensure_ascii=False) + "\n")

    print(f"\nWrote {len(all_chunks)} total chunks to {CHUNKS_PATH}")


if __name__ == "__main__":
    main()
