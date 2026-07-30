export interface SourceChunk {
  course_code: string | null;
  chunk_type: string | null;
  date: string | null;
  likes: number | null;
  text: string;
}

export interface ChatResponse {
  answer: string;
  sources: SourceChunk[];
}

export interface CourseSummary {
  code: string;
  title: string | null;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function sendChat(
  question: string,
  courseCode?: string | null
): Promise<ChatResponse> {
  const res = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question,
      course_code: courseCode || null,
    }),
  });

  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`Chat request failed (${res.status}): ${detail}`);
  }

  return res.json();
}

export async function getCourses(): Promise<CourseSummary[]> {
  const res = await fetch(`${API_BASE}/courses`);
  if (!res.ok) {
    throw new Error(`Failed to load courses (${res.status})`);
  }
  return res.json();
}
