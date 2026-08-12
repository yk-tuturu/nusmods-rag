import AppShell from "@/components/layout/AppShell";
import Icon from "@/components/Icon";

const MODULES = [
  {
    code: "CS2030S",
    title: "Programming Methodology II",
    mcs: 4,
    status: "satisfied" as const,
    slots: [
      { icon: "save_as", color: "text-tertiary", label: "LEC [1]: Mon 1000-1200", error: false },
      { icon: "computer", color: "text-secondary", label: "LAB [12]: Wed 1400-1600", error: false },
    ],
  },
  {
    code: "CS2100",
    title: "Computer Organisation",
    mcs: 4,
    status: "conflict" as const,
    slots: [
      {
        icon: "save_as",
        color: "text-error",
        label: "LEC [1]: Mon 1100-1300 (Clashes with CS2030S)",
        error: true,
      },
      { icon: "group", color: "text-secondary", label: "TUT [5]: Thu 1000-1100", error: false },
    ],
  },
];

const SUGGESTED_ELECTIVE = {
  code: "GET1020",
  mcs: 4,
  title: "Darwin and Evolution. Fits your Tuesday afternoon gap.",
};

const USUALLY_TAKEN_WITH = [
  { code: "CS2100", label: "Computer Org." },
  { code: "ST2334", label: "Probability & Stat." },
];

export default function PlannerPage() {
  return (
    <AppShell sideNavActive="Degree Progress">
      <div className="flex flex-col lg:flex-row gap-md">
        <div className="flex-1 flex flex-col gap-sm">
          <div className="flex justify-between items-center mb-sm">
            <h1 className="font-headline-lg text-headline-lg text-primary">
              Semester 1, AY2025/26
            </h1>
            <button className="bg-primary text-on-primary px-sm py-xs rounded flex items-center gap-xs hover:bg-primary-container transition-colors">
              <Icon name="add" size={18} /> Add Module
            </button>
          </div>

          {MODULES.map((mod) => (
            <div
              key={mod.code}
              className={`bg-surface-container-lowest border rounded-lg p-sm relative hover:shadow-[0_4px_12px_rgba(0,0,0,0.05)] transition-shadow ${
                mod.status === "conflict" ? "border-error-red" : "border-surface-variant"
              }`}
            >
              <div className="absolute top-sm right-sm flex gap-xs">
                {mod.status === "satisfied" ? (
                  <span className="bg-success-green text-[#155724] px-2 py-1 rounded text-[10px] font-bold flex items-center gap-1 uppercase tracking-wider">
                    <Icon name="check_circle" size={12} /> Satisfied
                  </span>
                ) : (
                  <span className="bg-error-container text-error px-2 py-1 rounded text-[10px] font-bold flex items-center gap-1 uppercase tracking-wider">
                    <Icon name="warning" size={12} /> Conflict
                  </span>
                )}
              </div>
              <h3 className="font-headline-sm text-headline-sm font-bold text-on-surface mb-xs">
                {mod.code}
              </h3>
              <p className="font-body-sm text-body-sm text-on-surface-variant mb-sm">
                {mod.title}
              </p>
              <div className="flex flex-wrap gap-xs mb-sm">
                {mod.slots.map((slot) => (
                  <div
                    key={slot.label}
                    className={`px-2 py-1 rounded border flex items-center gap-1 ${
                      slot.error
                        ? "bg-error-container/30 border-error-red/50"
                        : "bg-surface-container-low border-surface-variant"
                    }`}
                  >
                    <Icon name={slot.icon} className={slot.color} size={14} />
                    <span className={`font-label-sm text-label-sm font-mono ${slot.color}`}>
                      {slot.label}
                    </span>
                  </div>
                ))}
              </div>
              <div className="text-[12px] text-on-surface-variant flex justify-between items-center pt-xs border-t border-surface-variant">
                <span>{mod.mcs} MCs</span>
                {mod.status === "conflict" ? (
                  <button className="text-error-red hover:underline text-[12px] font-bold">
                    Resolve Conflict
                  </button>
                ) : (
                  <span className="cursor-pointer hover:text-primary flex items-center gap-1">
                    <Icon name="more_horiz" size={14} /> Options
                  </span>
                )}
              </div>
            </div>
          ))}

          <p className="font-body-sm text-body-sm text-on-surface-variant text-center py-sm">
            Sample plan shown — timetable sync coming soon.
          </p>
        </div>

        <div className="w-full lg:w-80 flex flex-col gap-sm">
          <div className="bg-surface-container-lowest border border-surface-variant rounded-lg p-sm sticky top-24">
            <div className="flex items-center gap-xs mb-md border-b border-surface-variant pb-xs">
              <Icon name="smart_toy" className="text-secondary" />
              <h2 className="font-headline-sm text-headline-sm font-bold text-secondary">
                AI Recommendations
              </h2>
            </div>
            <div className="mb-md">
              <h4 className="font-label-sm text-label-sm font-mono font-bold text-on-surface mb-xs uppercase tracking-wide">
                Slot Alternatives
              </h4>
              <div className="bg-inverse-on-surface border border-secondary-fixed rounded p-2 text-sm text-on-surface-variant">
                <p className="mb-1">
                  <strong className="text-tertiary">CS2100:</strong> Consider changing LEC [1] to{" "}
                  <strong>LEC [2] (Tue 1200-1400)</strong> to resolve the conflict with CS2030S.
                </p>
                <button className="mt-2 text-primary border border-primary px-2 py-1 rounded text-xs hover:bg-primary-fixed-dim transition-colors w-full">
                  Apply Change
                </button>
              </div>
            </div>
            <div>
              <h4 className="font-label-sm text-label-sm font-mono font-bold text-on-surface mb-xs uppercase tracking-wide">
                Suggested Electives
              </h4>
              <div className="border border-surface-variant rounded p-2 hover:bg-surface-container-low cursor-pointer transition-colors">
                <div className="flex justify-between">
                  <span className="font-bold text-sm text-on-surface">
                    {SUGGESTED_ELECTIVE.code}
                  </span>
                  <span className="text-xs text-on-surface-variant">
                    {SUGGESTED_ELECTIVE.mcs} MCs
                  </span>
                </div>
                <p className="text-[11px] text-on-surface-variant mt-1">
                  {SUGGESTED_ELECTIVE.title}
                </p>
              </div>
            </div>
          </div>

          <div className="bg-surface-container-lowest border border-surface-variant rounded-lg p-sm">
            <h4 className="font-headline-sm text-headline-sm text-on-surface mb-sm">
              Usually Taken With
            </h4>
            <ul className="space-y-2">
              {USUALLY_TAKEN_WITH.map((item) => (
                <li
                  key={item.code}
                  className="flex items-center justify-between p-2 hover:bg-surface-variant rounded cursor-pointer transition-colors"
                >
                  <span className="font-body-sm text-body-sm text-primary">{item.code}</span>
                  <span className="font-label-sm text-label-sm font-mono text-on-surface-variant">
                    {item.label}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
