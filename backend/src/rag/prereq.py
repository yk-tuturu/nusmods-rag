"""
prereq.py

Deterministic prerequisite checker over NUSMods' structured prereqTree
(stored per course in data/processed/<CODE>.json as "prereq_tree").

Evaluation is three-valued - True / False / None ("unknown") - because some
nodes depend on facts we don't have: a student's cohort or programme type
({"cohort": ...}, {"programType": ..., "then": ...}). An unknown never gets
silently rounded to met or not met.

Grades are not checked: a completed course is assumed to meet the tree's
minimum grade, and the result says so.
"""

from __future__ import annotations

import json
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
PROCESSED_DIR = BACKEND_DIR / "data" / "processed"


def _leaf_code(leaf: str) -> str:
    return leaf.split(":", 1)[0]


def _leaf_matches(leaf_code: str, completed: set[str]) -> bool:
    # NUSMods wildcards look like "AN%" (any module starting with "AN").
    if leaf_code.endswith("%"):
        prefix = leaf_code[:-1]
        return any(c.startswith(prefix) for c in completed)
    return leaf_code in completed


def _describe(node) -> str:
    """Short human-readable form of a node, used for 'what's missing'."""
    if isinstance(node, str):
        return _leaf_code(node)
    if isinstance(node, dict):
        if "and" in node:
            return "(" + " and ".join(_describe(c) for c in node["and"]) + ")"
        if "or" in node:
            return "(" + " or ".join(_describe(c) for c in node["or"]) + ")"
        if "nOf" in node:
            n, children = node["nOf"]
            return f"at least {n} of ({', '.join(_describe(c) for c in children)})"
        if "then" in node:
            return _describe(node["then"])
        if "cohort" in node:
            return "a cohort condition"
    return "an unrecognised condition"


def _evaluate(node, completed: set[str], missing: list[str]) -> bool | None:
    """Returns True/False/None. Appends a description of each unmet or
    undecidable requirement to `missing`."""
    if isinstance(node, str):
        if _leaf_matches(_leaf_code(node), completed):
            return True
        missing.append(_leaf_code(node))
        return False

    if not isinstance(node, dict):
        missing.append("an unrecognised condition")
        return None

    if "and" in node:
        results = [_evaluate(child, completed, missing) for child in node["and"]]
        if any(r is False for r in results):
            return False
        return None if any(r is None for r in results) else True

    if "or" in node:
        results = [_evaluate(child, completed, []) for child in node["or"]]
        if any(r is True for r in results):
            return True
        missing.append(_describe(node))
        return None if any(r is None for r in results) else False

    if "nOf" in node:
        n, children = node["nOf"]
        results = [_evaluate(child, completed, []) for child in children]
        met = sum(r is True for r in results)
        unknown = sum(r is None for r in results)
        if met >= n:
            return True
        missing.append(_describe(node))
        return None if met + unknown >= n else False

    if "then" in node:
        # "If <cohort/programme condition> then <requirement>". If the
        # requirement is met it doesn't matter whether the condition applies;
        # otherwise whether it applies to this student is unknown to us.
        result = _evaluate(node["then"], completed, [])
        if result is True:
            return True
        missing.append(f"{_describe(node['then'])} (only if it applies to your programme/cohort)")
        return None

    if "cohort" in node:
        missing.append("a cohort condition")
        return None

    missing.append("an unrecognised condition")
    return None


def evaluate_prereqs(tree, completed_courses: list[str]) -> dict:
    """Pure function over a prereqTree. Returns
    {"status": "met" | "not_met" | "unknown", "missing": [str]}."""
    completed = {c.strip().upper() for c in completed_courses if c and c.strip()}
    if not tree:
        return {"status": "met", "missing": []}
    missing: list[str] = []
    result = _evaluate(tree, completed, missing)
    status = "met" if result is True else "not_met" if result is False else "unknown"
    return {"status": status, "missing": [] if status == "met" else missing}


def check_prereqs(course_code: str, completed_courses: list[str]) -> dict:
    """Look up `course_code`'s stored prereq tree and evaluate it against the
    courses the student says they've completed."""
    code = course_code.strip().upper()
    path = PROCESSED_DIR / f"{code}.json"
    if not path.exists():
        return {"course": code, "error": f"no data for course {code}"}

    course = json.loads(path.read_text(encoding="utf-8"))
    tree = course.get("prereq_tree")
    result = evaluate_prereqs(tree, completed_courses)

    return {
        "course": code,
        "has_prerequisites": bool(tree),
        "status": result["status"],
        "missing": result["missing"],
        "prerequisite_text": course.get("prereqs"),
        "preclusion_text": course.get("preclusion"),
        "assumptions": "Completed courses are assumed to meet each requirement's minimum grade.",
    }
