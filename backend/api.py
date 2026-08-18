"""
api.py

FastAPI app exposing the RAG pipeline over HTTP for the Next.js frontend.

USAGE
-----
uvicorn api:app --reload --port 8000
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.pipeline.summarize import load_cached_summary
from src.rag.generate import answer_question
from src.scrape import nusmods_api

BACKEND_DIR = Path(__file__).resolve().parent
PROCESSED_DIR = BACKEND_DIR / "data" / "processed"
PROGRAMME_DIR = BACKEND_DIR / "programme"

# Friendlier labels for the frontend's major picker than the bare
# programme_code (which is just each doc's filename stem). Falls back to
# the code itself for any doc added without a corresponding entry here.
PROGRAMME_DISPLAY_NAMES = {
    "CS": "Computer Science",
    "BBA": "Business Administration",
    "BAIS": "Business Artificial Intelligence Systems",
    "BZA": "Business Analytics",
    "InfoSec": "Information Security",
}

app = FastAPI(title="NUSMods Course Review RAG API")

allowed_origins = os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    question: str
    course_code: str | None = None
    programme_code: str | None = None
    k: int = 8
    history: list[ChatMessage] = []


class SourceChunk(BaseModel):
    course_code: str | None = None
    chunk_type: str | None = None
    date: str | None = None
    likes: int | None = None
    text: str
    programme_code: str | None = None
    section_title: str | None = None


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceChunk]


class CourseSummary(BaseModel):
    code: str
    title: str | None = None


class CourseAISummary(BaseModel):
    code: str
    title: str | None = None
    summary: str
    difficulty: float
    review_count: int
    reviews_used: int
    generated_at: str
    model: str


class NUSModsCourse(BaseModel):
    moduleCode: str
    title: str | None = None
    semesters: list[int] = []


class ProgrammeSummary(BaseModel):
    code: str
    title: str


@app.get("/")
def root():
    return {"status": "ok", "service": "nusmods-rag-api"}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="question must not be empty")

    history = [m.model_dump() for m in req.history]
    result = answer_question(
        req.question,
        k=req.k,
        course_code=req.course_code,
        history=history,
        programme_code=req.programme_code,
    )
    return ChatResponse(answer=result["answer"], sources=result["sources"])


@app.get("/courses", response_model=list[CourseSummary])
def list_courses():
    courses = []
    for path in sorted(PROCESSED_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        courses.append(CourseSummary(code=data["code"], title=data.get("title")))
    return courses


@app.get("/courses/{code}/summary", response_model=CourseAISummary)
def get_course_summary(code: str):
    """Cached AI-generated summary blending the course's NUSMods description
    with its Disqus reviews. Serves the pre-generated cache written by
    src/pipeline/summarize.py only - this endpoint never calls the LLM
    itself, so a cache miss just reports the summary isn't ready yet rather
    than generating one inline on a request thread."""
    result = load_cached_summary(code.upper())
    if result is None:
        raise HTTPException(status_code=404, detail="no summary available for this course yet")
    return result


@app.get("/programmes", response_model=list[ProgrammeSummary])
def list_programmes():
    """Selectable majors for the frontend's major picker - one per
    programme/<code>.md doc. Excludes _common.md (not a major - always
    injected as static context, see generate.py's COMMON_KNOWLEDGE) and
    GE.md (general education applies to every student automatically, see
    retriever.py's PROGRAMME_ALIASES, so it isn't something a student
    "selects" as their major)."""
    codes = sorted(
        p.stem for p in PROGRAMME_DIR.glob("*.md")
        if not p.stem.startswith("_") and p.stem != "GE"
    )
    return [ProgrammeSummary(code=c, title=PROGRAMME_DISPLAY_NAMES.get(c, c)) for c in codes]


@app.get("/nusmods/courses", response_model=list[NUSModsCourse])
def list_nusmods_courses(academic_year: str | None = None):
    """Full NUSMods module catalog (code, title, semesters offered) for the
    given academic year, for use by the module planner. Backed by
    nusmods_api's on-disk cache, so this doesn't hit the NUSMods API on
    every request."""
    return nusmods_api.fetch_module_list(academic_year)
