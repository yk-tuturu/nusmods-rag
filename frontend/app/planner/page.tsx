"use client";

import { useEffect, useMemo, useState } from "react";
import AppShell from "@/components/layout/AppShell";
import Icon from "@/components/Icon";
import {
  getCourses,
  getCourseSummary,
  getModuleDetail,
  type CourseAISummary,
  type CourseSummary,
  type NUSModsCourseDetail,
} from "@/lib/api";

const STORAGE_KEY = "nusmods-planner-modules";

export default function PlannerPage() {
  const [courses, setCourses] = useState<CourseSummary[]>([]);
  const [savedCodes, setSavedCodes] = useState<string[]>([]);
  const [hydrated, setHydrated] = useState(false);
  const [showAdd, setShowAdd] = useState(false);
  const [query, setQuery] = useState("");
  const [detailsByCode, setDetailsByCode] = useState<
    Record<string, NUSModsCourseDetail | null>
  >({});
  const [summariesByCode, setSummariesByCode] = useState<
    Record<string, CourseAISummary | null>
  >({});

  useEffect(() => {
    getCourses()
      .then(setCourses)
      .catch(() => setCourses([]));

    try {
      const stored = window.localStorage.getItem(STORAGE_KEY);
      if (stored) setSavedCodes(JSON.parse(stored));
    } catch {
      // ignore malformed/corrupt storage
    }
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(savedCodes));
  }, [savedCodes, hydrated]);

  // Metrics view: pull per-module workload/MCs from NUSMods and the
  // AI-generated difficulty/summary for every saved module we haven't
  // already fetched.
  useEffect(() => {
    const missing = savedCodes.filter((code) => !(code in detailsByCode));
    for (const code of missing) {
      getModuleDetail(code)
        .then((detail) => setDetailsByCode((prev) => ({ ...prev, [code]: detail })))
        .catch(() => setDetailsByCode((prev) => ({ ...prev, [code]: null })));
      getCourseSummary(code)
        .then((summary) => setSummariesByCode((prev) => ({ ...prev, [code]: summary })))
        .catch(() => setSummariesByCode((prev) => ({ ...prev, [code]: null })));
    }
  }, [savedCodes, detailsByCode]);

  const courseByCode = useMemo(() => {
    const map = new Map<string, CourseSummary>();
    for (const c of courses) map.set(c.code, c);
    return map;
  }, [courses]);

  const savedModules = savedCodes.map((code) => courseByCode.get(code) ?? { code, title: null });

  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    return courses
      .filter((c) => !savedCodes.includes(c.code))
      .filter(
        (c) => !q || c.code.toLowerCase().includes(q) || (c.title ?? "").toLowerCase().includes(q)
      )
      .slice(0, 20);
  }, [courses, savedCodes, query]);

  function addModule(code: string) {
    setSavedCodes((prev) => (prev.includes(code) ? prev : [...prev, code]));
    setQuery("");
    setShowAdd(false);
  }

  function removeModule(code: string) {
    setSavedCodes((prev) => prev.filter((c) => c !== code));
  }

  return (
    <AppShell sideNavActive="Saved Modules">
      <div className="flex flex-col gap-sm max-w-[720px] mx-auto w-full">
        <div className="flex justify-between items-center mb-sm relative">
          <h1 className="font-headline-lg text-headline-lg text-primary">My Planner</h1>
          <button
            onClick={() => setShowAdd((v) => !v)}
            className="bg-primary text-on-primary px-sm py-xs rounded flex items-center gap-xs hover:bg-primary-container transition-colors"
          >
            <Icon name="add" size={18} /> Add Module
          </button>

          {showAdd && (
            <div className="absolute right-0 top-full mt-2 w-80 bg-surface-container-lowest border border-surface-variant rounded-lg shadow-lg p-sm z-10">
              <input
                autoFocus
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search module code or title..."
                className="w-full bg-surface-container border border-surface-variant rounded px-2 py-1 text-sm text-on-surface mb-2 focus:outline-none focus:border-primary"
              />
              <div className="max-h-64 overflow-y-auto flex flex-col gap-1">
                {results.length === 0 ? (
                  <p className="text-xs text-on-surface-variant px-1 py-2">
                    {courses.length === 0 ? "Loading modules…" : "No matching modules found."}
                  </p>
                ) : (
                  results.map((c) => (
                    <button
                      key={c.code}
                      onClick={() => addModule(c.code)}
                      className="text-left px-2 py-1 rounded hover:bg-surface-variant transition-colors"
                    >
                      <span className="font-bold text-sm text-on-surface">{c.code}</span>
                      {c.title && (
                        <span className="text-xs text-on-surface-variant ml-2">{c.title}</span>
                      )}
                    </button>
                  ))
                )}
              </div>
            </div>
          )}
        </div>

        {savedModules.length === 0 ? (
          <div className="border border-dashed border-surface-variant rounded-lg p-lg text-center text-on-surface-variant">
            <p className="font-body-md text-body-md">
              You haven&apos;t added any modules yet. Click &quot;Add Module&quot; to start
              building your plan.
            </p>
          </div>
        ) : (
          savedModules.map((mod) => {
            const detail = detailsByCode[mod.code];
            const summary = summariesByCode[mod.code];
            const workloadHours = detail?.workload_hours;
            const hasMetrics = (workloadHours && workloadHours.length > 0) || summary;

            return (
              <div
                key={mod.code}
                className="bg-surface-container-lowest border border-surface-variant rounded-lg p-sm relative hover:shadow-[0_4px_12px_rgba(0,0,0,0.05)] transition-shadow"
              >
                <button
                  onClick={() => removeModule(mod.code)}
                  aria-label={`Remove ${mod.code}`}
                  className="absolute top-sm right-sm text-on-surface-variant hover:text-error transition-colors"
                >
                  <Icon name="close" size={16} />
                </button>
                <h3 className="font-headline-sm text-headline-sm font-bold text-on-surface mb-xs pr-6">
                  {mod.code}
                </h3>
                <p className="font-body-sm text-body-sm text-on-surface-variant mb-sm">
                  {mod.title ?? detail?.title ?? detail?.description ?? "No description available yet."}
                </p>

                {hasMetrics && (
                  <div className="flex flex-col gap-2 mb-sm">
                    <div className="flex flex-wrap gap-xs">
                      {workloadHours && workloadHours.length > 0 && (
                        <div className="bg-surface-container-low px-2 py-1 rounded border border-surface-variant flex items-center gap-1">
                          <Icon name="schedule" size={14} className="text-tertiary" />
                          <span className="font-label-sm text-label-sm text-tertiary">
                            {workloadHours
                              .map(([label, hrs]) => `${label}: ${hrs} hr${hrs === 1 ? "" : "s"}/wk`)
                              .join(" · ")}
                          </span>
                        </div>
                      )}
                      {summary && (
                        <div className="bg-surface-container-low px-2 py-1 rounded border border-surface-variant flex items-center gap-1">
                          <Icon name="psychology" size={14} className="text-primary" />
                          <span className="font-label-sm text-label-sm text-primary">
                            AI Difficulty: {summary.difficulty.toFixed(1)}/5
                          </span>
                        </div>
                      )}
                    </div>
                    {summary && (
                      <p className="text-[13px] text-on-surface-variant">
                        <strong className="text-on-surface">AI Summary:</strong> {summary.summary}
                      </p>
                    )}
                  </div>
                )}

                {detail?.mcs && (
                  <div className="text-[12px] text-on-surface-variant pt-xs border-t border-surface-variant">
                    <span>{detail.mcs} MCs</span>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </AppShell>
  );
}
