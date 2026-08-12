import Link from "next/link";
import Icon from "@/components/Icon";

const FEATURES = [
  {
    icon: "analytics",
    iconBg: "bg-tertiary-container",
    iconColor: "text-on-tertiary-container",
    title: "Module Requirements",
    description:
      "Instantly resolve complex prerequisite chains and corequisite conditions to ensure your selected modules align perfectly with graduation requirements.",
    cta: "Learn More",
    href: "/chat",
  },
  {
    icon: "calendar_today",
    iconBg: "bg-secondary-container",
    iconColor: "text-on-secondary-container",
    title: "Module Planning",
    description:
      "Visualize your upcoming semesters. The AI suggests balanced workloads and identifies potential timetable clashes before module registration begins.",
    cta: "Explore Planner",
    href: "/planner",
  },
  {
    icon: "rate_review",
    iconBg: "bg-surface-variant",
    iconColor: "text-on-surface-variant",
    title: "Course Reviews",
    description:
      "Access aggregated sentiment analysis from past students. Understand workload expectations and teaching quality at a glance.",
    cta: "Read Reviews",
    href: "/reviews",
  },
];

export default function Home() {
  return (
    <div className="flex flex-col flex-1 bg-surface">
      <main className="flex-grow flex flex-col items-center justify-center w-full max-w-[1200px] mx-auto px-gutter py-xl">
        <section className="text-center max-w-3xl mb-xl">
          <h1 className="font-headline-lg text-headline-lg text-primary mb-md">
            Navigate Your Academic Journey with AI Precision
          </h1>
          <p className="font-body-lg text-body-lg text-on-surface-variant mb-lg">
            The NUS AI Advisor combines robust academic data from NUSMods with
            advanced conversational AI to help you plan modules, understand
            prerequisites, and optimize your degree progress seamlessly.
          </p>
          <Link
            href="/chat"
            className="inline-block bg-primary hover:bg-primary-container text-on-primary font-headline-sm text-headline-sm py-sm px-lg rounded-lg transition-colors shadow-sm active:scale-95"
          >
            Start Chatting
          </Link>
        </section>

        <section className="w-full grid grid-cols-1 md:grid-cols-3 gap-md">
          {FEATURES.map((feature) => (
            <div
              key={feature.title}
              className="bg-surface-container-lowest border border-surface-variant rounded-xl p-md flex flex-col gap-sm hover:shadow-md transition-shadow"
            >
              <div
                className={`w-12 h-12 rounded-full ${feature.iconBg} flex items-center justify-center mb-sm`}
              >
                <Icon name={feature.icon} className={feature.iconColor} />
              </div>
              <h3 className="font-headline-sm text-headline-sm text-on-surface">
                {feature.title}
              </h3>
              <p className="font-body-sm text-body-sm text-on-surface-variant flex-grow">
                {feature.description}
              </p>
              <Link
                href={feature.href}
                className="text-secondary font-label-md text-label-md font-mono hover:underline flex items-center gap-xs mt-auto w-max"
              >
                {feature.cta} <Icon name="arrow_forward" size={14} />
              </Link>
            </div>
          ))}
        </section>
      </main>

      <footer className="bg-surface-container-highest w-full py-lg mt-auto hidden md:block border-t border-outline-variant">
        <div className="flex flex-col md:flex-row justify-between items-center px-margin-desktop max-w-[1200px] mx-auto w-full gap-md">
          <span className="font-body-sm text-body-sm text-on-surface-variant">
            © 2026 NUS AI Advisor. Academic data sourced from NUSMods.
          </span>
          <div className="flex gap-md">
            <a
              className="font-body-sm text-body-sm text-on-surface-variant hover:text-primary transition-colors"
              href="#"
            >
              Terms of Service
            </a>
            <a
              className="font-body-sm text-body-sm text-on-surface-variant hover:text-primary transition-colors"
              href="#"
            >
              Privacy Policy
            </a>
            <a
              className="font-body-sm text-body-sm text-on-surface-variant hover:text-primary transition-colors"
              href="#"
            >
              Contact Support
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
}
