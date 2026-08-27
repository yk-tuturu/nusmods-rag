"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import Icon from "@/components/Icon";

const NAV_LINKS = [
  { href: "/chat", label: "Chat" },
  { href: "/planner", label: "Planner" },
  // Reviews tab hidden for now; keep entry around for when it's re-enabled.
  // { href: "/reviews", label: "Reviews" },
];

export default function TopNav() {
  const pathname = usePathname();

  return (
    <header className="bg-surface-container-lowest w-full top-0 sticky z-50 border-b border-surface-variant">
      <div className="flex justify-between items-center px-gutter py-base max-w-[1200px] mx-auto w-full h-16">
        <Link
          href="/"
          className="flex items-center gap-xs hover:bg-surface-container-low transition-colors rounded-lg p-2 -ml-2 active:scale-95 duration-200"
        >
          <Icon name="school" className="text-primary" />
          <span className="font-headline-md text-headline-md font-bold text-primary">
            NUS AI Advisor
          </span>
        </Link>
        <nav className="hidden md:flex gap-md items-center h-full">
          {NAV_LINKS.map((link) => {
            const active = pathname === link.href;
            return (
              <Link
                key={link.href}
                href={link.href}
                className={`font-headline-sm text-headline-sm h-full flex items-center px-2 transition-colors active:scale-95 duration-200 ${
                  active
                    ? "text-primary border-b-2 border-primary"
                    : "text-on-surface-variant hover:bg-surface-container-low"
                }`}
              >
                {link.label}
              </Link>
            );
          })}
        </nav>
        <div className="flex items-center gap-sm">
          <div className="w-8 h-8 rounded-full bg-secondary-container flex items-center justify-center text-on-secondary-container font-label-md text-label-md font-mono">
            UP
          </div>
        </div>
      </div>
    </header>
  );
}
