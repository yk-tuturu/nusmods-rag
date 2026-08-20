"""
generate.py

Builds a prompt from retrieved chunks and calls an LLM (OpenAI) to answer
the user's question, grounded only in the provided context. Returns the
answer plus the source chunks actually used, so callers can render
"based on N reviews for CS2030" style attribution.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from src.rag.retriever import retrieve

BACKEND_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BACKEND_DIR / ".env")

MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

# How many prior turns (user+assistant messages) to feed back to the LLM for
# conversational continuity. Capped defensively here even though the caller
# (frontend) already trims what it sends, since token cost grows with every
# turn otherwise.
MAX_HISTORY_MESSAGES = 8

# General NUS academic background (terminology, university-wide
# requirements, grading) that's small and universally relevant regardless
# of which course/major a question is about - see backend/programme/_common.md.
# Loaded once and folded into the system prompt below rather than going
# through retrieval/embedding like course or programme chunks, since it
# doesn't need to compete for relevance - it always applies.
_COMMON_KNOWLEDGE_PATH = BACKEND_DIR / "programme" / "_common.md"
COMMON_KNOWLEDGE = (
    _COMMON_KNOWLEDGE_PATH.read_text(encoding="utf-8")
    if _COMMON_KNOWLEDGE_PATH.exists()
    else ""
)

# Organized into labeled sections (rather than one dense paragraph) so each
# rule competes less with the others for the model's attention - empirically,
# a single long run-on instruction blob got the required-course rule ignored
# more often than a clearly separated one does (see the REQUIRED COURSES
# section, and generate.py's per-turn reminder for the same reasoning
# applied at the per-request level).
SYSTEM_PROMPT = """You are a precise assistant answering questions about NUS courses and degree \
programmes. Ground every answer strictly in the "Context" attached to the CURRENT question and \
the background notes below - never in outside/pretrained knowledge, even for well-known facts.

GROUNDING
- Every factual claim, number, or quote must trace back to the Context attached to THIS \
question, or to the background notes below. If the Context doesn't contain enough to answer, \
say so explicitly rather than filling the gap from memory.
- Earlier turns of the conversation may appear above the current question - use them ONLY to \
resolve what the user is referring to (e.g. what "it" or "either" means), NEVER as a source of \
facts.
- NEVER mention or make a claim about a course code that isn't in the CURRENT Context, even if \
it's a well-known fact about that course, even if an earlier turn discussed it, and even if the \
question is clearly about it.

CONTEXT TYPES
Each Context entry is labeled with its type - treat them differently:
- "review": a student's opinion, not a verified fact. Ground workload/difficulty/professor \
claims in these, quote directly when a review is specific, interesting, or funny, and flag \
anything that reads as sarcastic rather than literal. Some reviews are short or terse but still \
valid. Reviews are dated where available - for currency-sensitive questions (workload, exam \
format, professors, syllabus), note how recent the reviews you drew on are, especially if \
they're old or all from one period.
- "info": structured course metadata (prerequisites, modular credits, department) - state \
plainly as fact, no sarcasm/opinion handling needed.
- "programme": structured degree-requirement data straight from NUS programme documents (units, \
requirements, electives) - state plainly as fact, never as opinion, and never blend it with the \
conflicting-opinions handling used for reviews.

REQUIRED COURSES
Whenever a "programme" entry lists the course being discussed as compulsory, core, or otherwise \
required for a major (as opposed to elective), state that plainly and explicitly, as its own \
clearly flagged sentence near the start of the answer, separate from workload/difficulty \
commentary - e.g. "CS2030S is a compulsory Computer Science Foundation course for the CS major \
and must be completed to graduate." Do not soften this to vague language like "foundational" or \
"important," and do not let review sentiment about difficulty change whether you state it. Only \
make this claim when a "programme" entry actually supports it for the major in question; if no \
programme Context is present, or it doesn't mention the course, do not claim or deny that it's \
required - say you're unsure instead of guessing.

PRECISION AND STYLE
- Answer the actual question first - lead with the specific number, requirement, or verdict \
being asked for, before any supporting detail. Don't bury the answer under a preamble.
- Use exact figures from the Context (units, counts, ratings) rather than rounding or \
paraphrasing them loosely.
- When the Context enumerates several items (a course list, a requirement breakdown, several \
majors or focus areas), present them as a short list rather than folding them into a dense \
paragraph, so the answer stays scannable.
- When comparing multiple courses or majors, structure the answer per item (its own short \
section each) so the comparison reads side by side, rather than merging everything into one \
narrative.
- If the Context contains conflicting opinions (e.g. reviews that disagree), summarize the \
range rather than picking a side. If it contains conflicting facts, say so explicitly rather \
than silently choosing one.
- Keep prose tight: every sentence should add information. Don't restate the question, and \
don't hedge beyond what the Context actually leaves uncertain.
"""

if COMMON_KNOWLEDGE:
    SYSTEM_PROMPT += (
        "\n\nThe following is general NUS academic background that always applies, "
        "independent of whatever Context is attached to the current question. "
        "Treat it as ground truth you may draw on directly, the same as the Context:\n\n"
        f"{COMMON_KNOWLEDGE}"
    )

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


def format_context(chunks: list[dict]) -> str:
    blocks = []
    for c in chunks:
        if c["chunk_type"] == "programme":
            # No date/likes on programme chunks - labeled by major and
            # section instead, e.g. "[CS programme | Summary of Degree Requirements]".
            label = f"[{c['programme_code']} programme | {c['section_title']}]"
        else:
            # date is "" for non-review (e.g. metadata/prereq) chunks, which have
            # no meaningful date - omit rather than print an empty field.
            date_part = f" | {c['date']}" if c.get("date") else ""
            label = f"[{c['course_code']} | {c['chunk_type']}{date_part}]"
        blocks.append(f"{label}\n{c['text']}")
    return "\n\n---\n\n".join(blocks)


def answer_question(
    query: str,
    k: int = 8,
    course_codes: list[str] | None = None,
    history: list[dict] | None = None,
    programme_codes: list[str] | None = None,
) -> dict:
    """`history` is prior turns as [{"role": "user"|"assistant", "content": str}, ...]
    in chronological order, NOT including the current `query`. `programme_codes`
    are the student's selected major(s) (e.g. from a frontend multi-select), if
    any - see retrieve()'s docstring for how they combine with majors named in
    the query/history text."""
    recent_history = (history or [])[-MAX_HISTORY_MESSAGES:]
    history_texts = [m["content"] for m in recent_history]

    chunks = retrieve(
        query, k=k, course_codes=course_codes, history=history_texts, programme_codes=programme_codes
    )

    if not chunks:
        return {
            "answer": "I couldn't find any relevant course data to answer that question.",
            "sources": [],
        }

    context = format_context(chunks)
    client = _get_client()

    reminder = (
        "(Answer using only the Context above. Do not mention any course code "
        "that isn't in it, whether from earlier in this conversation or from "
        "general knowledge about NUS courses.)"
    )
    # Explicit disambiguation for "my major"/"my degree" style phrasing.
    # Course info/review chunks aren't affiliated with any particular major -
    # testing showed that when the only course chunks available happened to
    # all be CS courses (a dataset-coverage artifact, not a signal about the
    # user), the model would guess "my major" meant CS purely because CS
    # course codes were the ones it saw most, even with the *actual* selected
    # major's programme chunk sitting right there in the same Context. Naming
    # the selected major(s) directly removes the need for the model to infer it.
    if programme_codes:
        majors_list = ", ".join(programme_codes)
        if len(programme_codes) > 1:
            reminder += (
                f" The user has selected multiple majors: {majors_list}. If they refer to "
                "\"my major\"/\"my degree\" without naming one, treat it as referring to "
                "whichever of these the question is actually about (or all of them, if the "
                "question doesn't distinguish); if a course is required for one selected "
                "major but not another, say so explicitly per major rather than blending "
                "them into one answer. Do not infer a different major from which course "
                "codes happen to appear in the Context - course chunks aren't tied to any "
                "particular major."
            )
        else:
            reminder += (
                f" The user's selected major is \"{majors_list}\" - if they refer to "
                f"\"my major\"/\"my degree\" without naming one, that means {majors_list} "
                "specifically. Do not infer a different major from which course codes "
                "happen to appear in the Context - course chunks aren't tied to any "
                "particular major."
            )
    # Repeated here, close to this turn's actual Context, rather than relying
    # solely on the general instruction in SYSTEM_PROMPT - a reminder tied to
    # what's actually retrieved this turn is followed far more reliably than
    # a standing rule stated once, further up, in the abstract.
    if any(c["chunk_type"] == "programme" for c in chunks):
        reminder += (
            " If a \"programme\" entry above lists the course(s) being discussed "
            "as compulsory/required/core for a major, you MUST say so explicitly "
            "and plainly (e.g. \"is a compulsory/required course for the CS major\") "
            "rather than only softer language like \"foundational\" or \"important\"."
        )
    else:
        # Explicit suppression, not just omission - gpt-4o-mini has enough
        # pretrained knowledge of real NUS courses that leaving this unsaid
        # let it assert a course was "compulsory" from memory alone once the
        # topic was primed elsewhere in the prompt, even with zero programme
        # Context this turn. Silence wasn't enough; it needs telling not to.
        reminder += (
            " No \"programme\" (degree-requirement) entry is present in the Context "
            "above, so do not state or imply whether any course is required, "
            "compulsory, core, or elective for any major - that information isn't "
            "available this turn, even if you recognize the course."
        )

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend({"role": m["role"], "content": m["content"]} for m in recent_history)
    messages.append({
        "role": "user",
        "content": f"Context:\n\n{context}\n\nQuestion: {query}\n\n{reminder}",
    })

    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        # Lowered from 0.3 - testing the REQUIRED COURSES rule showed real
        # run-to-run variance in whether it was followed at 0.3; precision/
        # consistency matters more here than answer variety.
        temperature=0.2,
    )

    answer = response.choices[0].message.content

    sources = [
        {
            "course_code": c["course_code"],
            "chunk_type": c["chunk_type"],
            "date": c["date"],
            "likes": c["likes"],
            "text": c["text"],
            "programme_code": c.get("programme_code"),
            "section_title": c.get("section_title"),
        }
        for c in chunks
    ]

    return {"answer": answer, "sources": sources}


if __name__ == "__main__":
    import sys
    q = " ".join(sys.argv[1:]) or "is CS2030 hard for beginners?"
    result = answer_question(q)
    print(result["answer"])
    print(f"\n--- based on {len(result['sources'])} chunks ---")
