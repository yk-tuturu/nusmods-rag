import SideNav from "@/components/layout/SideNav";

export default function AppShell({
  children,
  sideNavActive,
}: {
  children: React.ReactNode;
  sideNavActive?: string;
}) {
  return (
    <div className="flex flex-1 w-full">
      <SideNav active={sideNavActive} />
      <main className="flex-1 lg:ml-64 p-gutter md:p-md max-w-[1200px] mx-auto w-full">
        {children}
      </main>
    </div>
  );
}
