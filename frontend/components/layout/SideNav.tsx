import Link from "next/link";
import Icon from "@/components/Icon";

const TOOLS = [
  { label: "Module Search", icon: "search" },
  { label: "Degree Progress", icon: "analytics" },
  { label: "Saved Modules", icon: "bookmark" },
  { label: "Settings", icon: "settings", href: "/settings" },
];

export default function SideNav({ active }: { active?: string }) {
  return (
    <aside className="bg-surface-container-low h-full w-64 fixed left-0 top-16 hidden lg:flex flex-col border-r border-surface-variant pt-md gap-base z-30">
      <div className="px-md pb-md">
        <h2 className="font-headline-sm text-headline-sm font-bold text-secondary">
          Academic Tools
        </h2>
      </div>
      <nav className="flex flex-col">
        {TOOLS.map((tool) => {
          const isActive = tool.label === active;
          const className = `flex items-center gap-sm mx-2 my-1 px-4 py-3 rounded-full transition-all cursor-pointer active:scale-[0.98] text-left ${
            isActive
              ? "bg-secondary-container text-on-secondary-container"
              : "text-on-surface-variant hover:bg-surface-variant"
          }`;
          const content = (
            <>
              <Icon name={tool.icon} filled={isActive} />
              <span className="font-body-md text-body-md">{tool.label}</span>
            </>
          );
          return tool.href ? (
            <Link key={tool.label} href={tool.href} className={className}>
              {content}
            </Link>
          ) : (
            <button key={tool.label} type="button" className={className}>
              {content}
            </button>
          );
        })}
      </nav>
    </aside>
  );
}
