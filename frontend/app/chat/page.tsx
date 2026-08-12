import SideNav from "@/components/layout/SideNav";
import ChatInterface from "@/components/chat/ChatInterface";

export default function ChatPage() {
  return (
    <div className="flex h-[calc(100vh-4rem)] w-full overflow-hidden">
      <SideNav active="Module Search" />
      <ChatInterface />
    </div>
  );
}
