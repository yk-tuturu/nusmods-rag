"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import Icon from "@/components/Icon";

const NAV_ITEMS = [
  { href: "/chat", label: "Chat", icon: "chat_bubble" },
  { href: "/planner", label: "Planner", icon: "calendar_today" },
  { href: "/reviews", label: "Reviews", icon: "rate_review" },
];

export default function BottomNav() {
  const pathname = usePathname();

  return (
    <nav className="bg-surface-container-lowest fixed bottom-0 w-full z-50 lg:hidden border-t border-surface-variant shadow-sm flex justify-around items-center h-16 px-sm">
      {NAV_ITEMS.map((item) => {
        const active = pathname === item.href;
        return (
          <Link
            key={item.href}
            href={item.href}
            className={`flex flex-col items-center justify-center px-4 py-1 active:scale-90 transition-transform ${
              active
                ? "text-primary bg-primary-fixed rounded-full"
                : "text-on-surface-variant hover:opacity-80"
            }`}
          >
            <Icon name={item.icon} filled={active} />
            <span className="font-label-sm text-label-sm font-mono">{item.label}</span>
          </Link>
        );
      })}
      <button
        type="button"
        className="flex flex-col items-center justify-center px-4 py-1 text-on-surface-variant hover:opacity-80 active:scale-90 transition-transform"
      >
        <Icon name="person" />
        <span className="font-label-sm text-label-sm font-mono">Profile</span>
      </button>
    </nav>
  );
}
