"""
nusmods_api.py

Fetches course (module) metadata from the public NUSMods API
(https://api.nusmods.com). Used to:
  1. get the full list of module codes for a given academic year, and
  2. get per-module details (title, description, prereqs, workload, MCs, department)

Results are cached to disk (data/.cache/nusmods/<acadYear>/) since the
catalog barely changes within an academic year and re-fetching ~4000
module detail files on every run is wasteful and slow.
"""

from __future__ import annotations

import json
import os
import time
from datetime import date
from pathlib import Path

import requests

API_BASE = "https://api.nusmods.com/v2"

BACKEND_DIR = Path(__file__).resolve().parents[2]
CACHE_DIR = BACKEND_DIR / "data" / ".cache" / "nusmods"


def current_academic_year(today: date | None = None) -> str:
    """NUS academic years run roughly Aug-Jul, e.g. '2025-2026'."""
    today = today or date.today()
    start_year = today.year if today.month >= 8 else today.year - 1
    return f"{start_year}-{start_year + 1}"


def _cache_path(academic_year: str, name: str) -> Path:
    return CACHE_DIR / academic_year / name


def _read_cache(path: Path):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
    return None


def _write_cache(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def fetch_module_list(academic_year: str | None = None, force: bool = False) -> list[dict]:
    """Fetch the full list of {moduleCode, title, ...} for an academic year."""
    academic_year = academic_year or current_academic_year()
    cache_path = _cache_path(academic_year, "moduleList.json")

    if not force:
        cached = _read_cache(cache_path)
        if cached is not None:
            return cached

    url = f"{API_BASE}/{academic_year}/moduleList.json"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    _write_cache(cache_path, data)
    return data


def fetch_module_detail(
    module_code: str, academic_year: str | None = None, force: bool = False
) -> dict | None:
    """Fetch full detail for one module. Returns None on 404 (module not offered that year)."""
    academic_year = academic_year or current_academic_year()
    cache_path = _cache_path(academic_year, f"modules/{module_code}.json")

    if not force:
        cached = _read_cache(cache_path)
        if cached is not None:
            return cached

    url = f"{API_BASE}/{academic_year}/modules/{module_code}.json"
    resp = requests.get(url, timeout=30)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    data = resp.json()

    _write_cache(cache_path, data)
    return data


def _split_leaf(leaf: str) -> tuple[str, str | None]:
    """A prereqTree leaf is a module code, optionally suffixed with the
    minimum grade required, e.g. "CS1010:D" or just "CS1010"."""
    if ":" in leaf:
        code, grade = leaf.split(":", 1)
        return code, grade
    return leaf, None


def _format_node(node, top: bool = False) -> str:
    if node is None:
        return ""
    if isinstance(node, str):
        code, grade = _split_leaf(node)
        return f"{code} (min grade {grade})" if grade else code
    if isinstance(node, dict):
        for op, sep in (("or", " or "), ("and", " and ")):
            children = node.get(op)
            if not children:
                continue
            # If every option is a plain leaf and they all require the same
            # grade, state the grade once for the group instead of repeating
            # it on every option.
            if all(isinstance(c, str) for c in children):
                codes_grades = [_split_leaf(c) for c in children]
                grades = {g for _, g in codes_grades}
                if len(grades) == 1:
                    grade = next(iter(grades))
                    expr = sep.join(code for code, _ in codes_grades)
                    if grade:
                        expr += f", min grade {grade}"
                else:
                    expr = sep.join(_format_node(c) for c in children)
            else:
                expr = sep.join(_format_node(c) for c in children)
            return f"({expr})" if len(children) > 1 and not top else expr
        return ""  # dict without a recognized "and"/"or" key - unsupported shape
    return ""


def format_prereq_tree(tree: dict | str | None) -> str | None:
    """Render a NUSMods prereqTree (nested and/or of MODULECODE:GRADE leaves)
    into a flat, human-readable boolean expression, e.g.
    "(CS2040 or CS2040S, min grade D) and (CS1231 or CS1231S, min grade D)".
    Returns None if there's no tree (module has no prerequisites)."""
    if not tree:
        return None
    return _format_node(tree, top=True) or None


def extract_summary(detail: dict) -> dict:
    """Pull out the fields the RAG pipeline cares about from a full module detail blob."""
    return {
        "code": detail.get("moduleCode"),
        "title": detail.get("title"),
        "description": detail.get("description"),
        "prereqs": detail.get("prerequisite"),
        # Structured and/or prereq tree - the authoritative version of
        # "prereqs" above, suitable for exact checking rather than prose.
        "prereq_tree": detail.get("prereqTree"),
        "preclusion": detail.get("preclusion"),
        # Modules that list this module as (one option for) their prereq.
        "fulfill_requirements": detail.get("fulfillRequirements") or [],
        "mcs": detail.get("moduleCredit"),
        "department": detail.get("department"),
        "faculty": detail.get("faculty"),
        "workload": detail.get("workload"),
        # "su" is only present (and true) in `attributes` when the module can
        # be taken S/U; absent means not S/U-able, not "unknown".
        "su": bool((detail.get("attributes") or {}).get("su")),
    }


def fetch_all_module_codes(academic_year: str | None = None, force: bool = False) -> list[str]:
    return [m["moduleCode"] for m in fetch_module_list(academic_year, force=force)]


def fetch_module_summaries(
    module_codes: list[str], academic_year: str | None = None, delay: float = 0.2
) -> dict[str, dict]:
    """Fetch + summarize details for a list of module codes, politely rate-limited."""
    academic_year = academic_year or current_academic_year()
    summaries: dict[str, dict] = {}

    for i, code in enumerate(module_codes):
        detail = fetch_module_detail(code, academic_year=academic_year)
        if detail:
            summaries[code] = extract_summary(detail)
        if i < len(module_codes) - 1:
            time.sleep(delay)

    return summaries


if __name__ == "__main__":
    ay = current_academic_year()
    print(f"Academic year: {ay}")
    codes = fetch_all_module_codes(ay)
    print(f"Found {len(codes)} modules")
    print(codes[:10])
