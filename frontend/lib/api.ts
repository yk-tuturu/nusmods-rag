export interface SourceChunk {
  course_code: string | null;
  chunk_type: string | null;
  date: string | null;
  likes: number | null;
  text: string;
  programme_code: string | null;
  section_title: string | null;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface ChatResponse {
  answer: string;
  sources: SourceChunk[];
}

export interface CourseSummary {
  code: string;
  title: string | null;
}

export interface ProgrammeSummary {
  code: string;
  title: string;
}

export interface CourseAISummary {
  code: string;
  title: string | null;
  summary: string;
  difficulty: number;
  review_count: number;
  reviews_used: number;
  generated_at: string;
  model: string;
}

export interface NUSModsCourseDetail {
  code: string;
  title: string | null;
  mcs: string | null;
  description: string | null;
  workload_hours: [string, number][] | null;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function sendChat(
  question: string,
  courseCode?: string | null,
  history?: ChatMessage[],
  programmeCode?: string | null
): Promise<ChatResponse> {
  const res = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question,
      course_code: courseCode || null,
      programme_code: programmeCode || null,
      history: history ?? [],
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

export async function getProgrammes(): Promise<ProgrammeSummary[]> {
  const res = await fetch(`${API_BASE}/programmes`);
  if (!res.ok) {
    throw new Error(`Failed to load programmes (${res.status})`);
  }
  return res.json();
}

export async function getCourseSummary(code: string): Promise<CourseAISummary | null> {
  const res = await fetch(`${API_BASE}/courses/${code}/summary`);
  if (res.status === 404) return null;
  if (!res.ok) {
    throw new Error(`Failed to load summary for ${code} (${res.status})`);
  }
  return res.json();
}

export async function getModuleDetail(code: string): Promise<NUSModsCourseDetail | null> {
  const res = await fetch(`${API_BASE}/nusmods/courses/${code}`);
  if (res.status === 404) return null;
  if (!res.ok) {
    throw new Error(`Failed to load module detail for ${code} (${res.status})`);
  }
  return res.json();
}
