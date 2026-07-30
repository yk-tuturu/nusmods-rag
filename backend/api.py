"""
api.py

FastAPI app exposing the RAG pipeline over HTTP for the Next.js frontend.

USAGE
-----
uvicorn api:app --reload --port 8000
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.rag.generate import answer_question

BACKEND_DIR = Path(__file__).resolve().parent
PROCESSED_DIR = BACKEND_DIR / "data" / "processed"

app = FastAPI(title="NUSMods Course Review RAG API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    question: str
    course_code: str | None = None
    k: int = 8


class SourceChunk(BaseModel):
    course_code: str | None = None
    chunk_type: str | None = None
    date: str | None = None
    likes: int | None = None
    text: str


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceChunk]


class CourseSummary(BaseModel):
    code: str
    title: str | None = None


@app.get("/")
def root():
    return {"status": "ok", "service": "nusmods-rag-api"}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="question must not be empty")

    result = answer_question(req.question, k=req.k, course_code=req.course_code)
    return ChatResponse(answer=result["answer"], sources=result["sources"])


@app.get("/courses", response_model=list[CourseSummary])
def list_courses():
    courses = []
    for path in sorted(PROCESSED_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        courses.append(CourseSummary(code=data["code"], title=data.get("title")))
    return courses
