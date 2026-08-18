import type { LucideIcon } from "lucide-react";
import {
  School,
  MessageCircle,
  CalendarDays,
  Star,
  User,
  Search,
  BarChart3,
  Bookmark,
  Settings,
  ArrowRight,
  Bot,
  Send,
  FileText,
  ChevronDown,
  ChevronUp,
  Sparkles,
  SlidersHorizontal,
  ThumbsUp,
  Share2,
  Plus,
  CheckCircle,
  AlertTriangle,
  MoreHorizontal,
  Presentation,
  Monitor,
  Users,
  Palette,
  CircleUserRound,
  BookOpen,
  ShieldCheck,
  Sun,
  Moon,
  X,
  Clock,
  Brain,
} from "lucide-react";

const ICONS: Record<string, LucideIcon> = {
  school: School,
  chat_bubble: MessageCircle,
  calendar_today: CalendarDays,
  rate_review: Star,
  person: User,
  search: Search,
  analytics: BarChart3,
  bookmark: Bookmark,
  bookmark_border: Bookmark,
  bookmark_add: Bookmark,
  settings: Settings,
  arrow_forward: ArrowRight,
  smart_toy: Bot,
  send: Send,
  description: FileText,
  expand_more: ChevronDown,
  expand_less: ChevronUp,
  auto_awesome: Sparkles,
  filter_list: SlidersHorizontal,
  thumb_up: ThumbsUp,
  share: Share2,
  add: Plus,
  check_circle: CheckCircle,
  warning: AlertTriangle,
  more_horiz: MoreHorizontal,
  save_as: Presentation,
  computer: Monitor,
  group: Users,
  palette: Palette,
  account_circle: CircleUserRound,
  book: BookOpen,
  security: ShieldCheck,
  light_mode: Sun,
  dark_mode: Moon,
  contrast: Monitor,
  close: X,
  schedule: Clock,
  psychology: Brain,
};

export default function Icon({
  name,
  className,
  filled,
  size = 24,
}: {
  name: string;
  className?: string;
  filled?: boolean;
  size?: number;
}) {
  const LucideIcon = ICONS[name];
  if (!LucideIcon) return null;

  return (
    <LucideIcon
      className={className}
      size={size}
      strokeWidth={filled ? 2.5 : 2}
      fill={filled ? "currentColor" : "none"}
    />
  );
}
