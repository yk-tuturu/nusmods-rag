"""
tools.py

Tools the answer model may call mid-generation (OpenAI function calling).
Retrieval stays the default path; tools cover questions where an exact
answer beats retrieved prose.
"""

from __future__ import annotations

import json

from src.rag.prereq import check_prereqs

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "check_prereqs",
            "description": (
                "Deterministically check whether a student meets a course's prerequisites, "
                "given courses they say they have completed. Call this whenever the user "
                "states what they have taken and asks if they can/are eligible to take a "
                "course. Do not call it for general questions about what a course's "
                "prerequisites are - the Context already covers that. Include courses the "
                "user mentioned in earlier turns."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "course_code": {
                        "type": "string",
                        "description": "The course the student wants to take, e.g. CS2040S.",
                    },
                    "completed_courses": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Course codes the student has completed, e.g. [\"CS1010\", \"CS1231\"].",
                    },
                },
                "required": ["course_code", "completed_courses"],
            },
        },
    }
]


def run_tool(name: str, arguments_json: str) -> str:
    """Execute a tool call and return its result as a JSON string. Errors
    are returned as a result rather than raised, so the model can recover."""
    try:
        args = json.loads(arguments_json or "{}")
        if name == "check_prereqs":
            result = check_prereqs(args["course_code"], args.get("completed_courses", []))
        else:
            result = {"error": f"unknown tool {name}"}
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        result = {"error": f"invalid arguments: {e}"}
    return json.dumps(result)
