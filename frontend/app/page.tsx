import ChatWindow from "@/components/ChatWindow";

export default function Home() {
  return (
    <div className="flex flex-col flex-1 bg-zinc-50 dark:bg-black">
      <header className="border-b border-zinc-200 dark:border-zinc-800 px-4 py-3">
        <h1 className="text-lg font-semibold">NUSMods Course Review Chat</h1>
      </header>
      <ChatWindow />
    </div>
  );
}
