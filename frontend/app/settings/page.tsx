"use client";

import { useState, type ReactNode } from "react";
import AppShell from "@/components/layout/AppShell";
import Icon from "@/components/Icon";
import { setTheme as persistTheme, type Theme } from "@/lib/theme";
import { useTheme } from "@/lib/use-theme";

const THEME_OPTIONS: { value: Theme; label: string; icon: string }[] = [
  { value: "light", label: "Light", icon: "light_mode" },
  { value: "dark", label: "Dark", icon: "dark_mode" },
  { value: "system", label: "System", icon: "contrast" },
];

const FACULTIES = [
  { value: "soc", label: "School of Computing" },
  { value: "fass", label: "Faculty of Arts and Social Sciences" },
  { value: "biz", label: "NUS Business School" },
  { value: "cde", label: "College of Design and Engineering" },
  { value: "fos", label: "Faculty of Science" },
];

const MAJORS = [
  { value: "cs", label: "Computer Science" },
  { value: "is", label: "Information Systems" },
  { value: "bza", label: "Business Analytics" },
  { value: "ceg", label: "Computer Engineering" },
  { value: "isec", label: "Information Security" },
];

export default function SettingsPage() {
  const theme = useTheme();
  const [saveHistory, setSaveHistory] = useState(true);

  return (
    <AppShell sideNavActive="Settings">
      <div className="max-w-3xl mx-auto w-full">
        <header className="mb-md">
          <h1 className="font-headline-lg text-headline-lg text-on-surface mb-xs">Settings</h1>
          <p className="font-body-md text-body-md text-on-surface-variant">
            Manage your account preferences and application settings.
          </p>
        </header>

        <div className="flex flex-col gap-md">
          <Section icon="palette" title="Appearance">
            <p className="font-body-sm text-body-sm text-on-surface-variant mb-sm">
              Select your preferred theme for the interface.
            </p>
            <div className="inline-flex bg-surface-container-low rounded-lg p-1 border border-surface-variant">
              {THEME_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  aria-pressed={theme === opt.value}
                  onClick={() => persistTheme(opt.value)}
                  className={`px-md py-xs rounded-md font-label-md text-label-md flex items-center gap-xs transition-all ${
                    theme === opt.value
                      ? "bg-surface-container-lowest shadow-sm text-primary"
                      : "text-on-surface-variant hover:text-on-surface"
                  }`}
                >
                  <Icon name={opt.icon} size={18} />
                  {opt.label}
                </button>
              ))}
            </div>
          </Section>

          <Section icon="book" title="Academic Preferences">
            <div className="flex flex-col gap-md">
              <Field label="Faculty / School" htmlFor="faculty">
                <Select id="faculty" defaultValue="soc" options={FACULTIES} />
              </Field>
              <Field label="Primary Major" htmlFor="major">
                <Select id="major" defaultValue="cs" options={MAJORS} />
              </Field>
            </div>
          </Section>

          <Section icon="security" title="Privacy & Data">
            <div className="flex flex-col gap-md">
              <div className="flex items-center justify-between">
                <div className="flex flex-col">
                  <span className="font-body-md text-body-md font-semibold text-on-surface">
                    Save Chat History
                  </span>
                  <span className="font-body-sm text-body-sm text-on-surface-variant">
                    Allow AI Advisor to remember past conversations for context.
                  </span>
                </div>
                <Switch
                  checked={saveHistory}
                  onChange={setSaveHistory}
                  label="Save chat history"
                />
              </div>
              <div className="flex items-center justify-between pt-sm border-t border-surface-variant">
                <div className="flex flex-col">
                  <span className="font-body-md text-body-md font-semibold text-error">
                    Clear Data
                  </span>
                  <span className="font-body-sm text-body-sm text-on-surface-variant">
                    Permanently delete all saved modules and chat history.
                  </span>
                </div>
                <button
                  type="button"
                  className="bg-transparent border border-error text-error hover:bg-error-container transition-colors px-md py-xs rounded font-label-md text-label-md"
                >
                  Clear All Data
                </button>
              </div>
            </div>
          </Section>
        </div>

        <div className="mt-md flex justify-end gap-sm">
          <button
            type="button"
            className="bg-transparent border border-secondary text-secondary hover:bg-surface-container-low transition-colors px-md py-xs rounded font-label-md text-label-md"
          >
            Cancel
          </button>
          <button
            type="button"
            className="bg-primary text-on-primary hover:opacity-90 transition-opacity px-md py-xs rounded font-label-md text-label-md shadow-sm"
          >
            Save Changes
          </button>
        </div>
      </div>
    </AppShell>
  );
}

function Section({
  icon,
  title,
  children,
}: {
  icon: string;
  title: string;
  children: ReactNode;
}) {
  return (
    <section className="bg-surface-container-lowest rounded-xl border border-surface-variant p-md">
      <div className="flex items-center gap-sm mb-sm border-b border-surface-variant pb-sm">
        <Icon name={icon} className="text-secondary" />
        <h2 className="font-headline-md text-headline-md text-on-surface">{title}</h2>
      </div>
      {children}
    </section>
  );
}

function Field({
  label,
  htmlFor,
  children,
}: {
  label: string;
  htmlFor: string;
  children: ReactNode;
}) {
  return (
    <div className="flex flex-col gap-xs">
      <label
        htmlFor={htmlFor}
        className="font-label-md text-label-md text-on-surface-variant uppercase tracking-wider"
      >
        {label}
      </label>
      {children}
    </div>
  );
}

function Select({
  id,
  defaultValue,
  options,
}: {
  id: string;
  defaultValue: string;
  options: { value: string; label: string }[];
}) {
  return (
    <div className="relative w-full max-w-[28rem]">
      <select
        id={id}
        defaultValue={defaultValue}
        className="appearance-none w-full bg-surface-container-lowest border border-outline rounded-md pl-sm pr-8 py-xs font-body-md text-body-md text-on-surface focus:outline-none focus:border-secondary focus:ring-1 focus:ring-secondary"
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
      <Icon
        name="expand_more"
        size={16}
        className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-on-surface-variant"
      />
    </div>
  );
}

function Switch({
  checked,
  onChange,
  label,
}: {
  checked: boolean;
  onChange: (value: boolean) => void;
  label: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      onClick={() => onChange(!checked)}
      className={`relative w-10 h-6 rounded-full shrink-0 transition-colors ${
        checked ? "bg-primary" : "bg-surface-variant"
      }`}
    >
      <span
        className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white shadow-sm transition-transform ${
          checked ? "translate-x-4" : "translate-x-0"
        }`}
      />
    </button>
  );
}
