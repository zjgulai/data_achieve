import {
  Activity,
  Bell,
  Bot,
  BookOpenCheck,
  Boxes,
  ChartNoAxesCombined,
  Database,
  FileText,
  FolderKanban,
  Gauge,
  Github,
  Globe2,
  type LucideIcon,
  Megaphone,
  Radio,
  ShieldAlert,
  ShieldCheck,
  ShoppingCart,
  SquareStack,
  Wrench,
} from "lucide-react";
import type { Route } from "next";
import Link from "next/link";

type NavItem = {
  href: Route;
  label: string;
  icon: LucideIcon;
};

function route(href: string): Route {
  return href as Route;
}

const scopeItems = [
  { href: route("/domain/osint"), label: "开源雷达", icon: Github },
  { href: route("/domain/ecommerce"), label: "电商风向", icon: ShoppingCart },
  { href: route("/domain/social"), label: "社媒脉搏", icon: Radio },
  { href: route("/domain/competitor"), label: "竞品守望", icon: Globe2 },
  { href: route("/domain/agent"), label: "Agent 生态", icon: Bot },
  { href: route("/domain/platform"), label: "平台采集", icon: Boxes },
  { href: route("/domain/governance"), label: "合规边界", icon: ShieldCheck },
] satisfies NavItem[];

const generalItems = [
  { href: route("/dashboard"), label: "全局仪表盘", icon: Gauge },
  { href: route("/toolkit"), label: "采集工具库", icon: Wrench },
  { href: route("/playbooks/site-user-playbook.html"), label: "使用手册", icon: BookOpenCheck },
  { href: route("/projects"), label: "项目", icon: FolderKanban },
  { href: route("/signals"), label: "信号中心", icon: Activity },
  { href: route("/intelligence"), label: "情报中心", icon: ChartNoAxesCombined },
  { href: route("/reports"), label: "报告中心", icon: FileText },
  { href: route("/alerts"), label: "预警中心", icon: ShieldAlert },
  { href: route("/notifications"), label: "站内通知", icon: Bell },
] satisfies NavItem[];

const engineItems = [
  { href: route("/tasks"), label: "采集任务", icon: SquareStack },
  { href: route("/sources"), label: "数据源", icon: Boxes },
  { href: route("/raw-records"), label: "原始数据", icon: Database },
  { href: route("/entities"), label: "实体库", icon: Megaphone },
] satisfies NavItem[];

export function Sidebar() {
  return (
    <aside className="hidden min-h-screen w-72 border-r border-[#E9E5E2] bg-white px-4 py-5 lg:fixed lg:inset-y-0 lg:flex lg:flex-col">
      <Link className="mb-7 flex items-center gap-3 px-2" href="/dashboard">
        <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#C25B6E] text-white">
          <ChartNoAxesCombined size={20} aria-hidden="true" />
        </span>
        <span>
          <span className="block text-sm font-semibold text-[#1D1D1F]">Data Intelligence</span>
          <span className="block text-xs text-[#86868B]">Hub</span>
        </span>
      </Link>

      <NavGroup label="业务域" items={scopeItems} />
      <NavGroup label="全局中心" items={generalItems} />
      <NavGroup label="工程中心" items={engineItems} />
    </aside>
  );
}

function NavGroup({ label, items }: { label: string; items: NavItem[] }) {
  return (
    <nav className="mb-6">
      <p className="mb-2 px-2 text-xs font-semibold uppercase text-[#86868B]">
        {label}
      </p>
      <div className="grid gap-1">
        {items.map((item) => {
          const Icon = item.icon;
          return (
            <Link
              className="flex items-center gap-3 rounded-xl px-2 py-2 text-sm font-medium text-[#5F5757] transition-colors hover:bg-[#FBF8F5] hover:text-[#1D1D1F]"
              href={item.href}
              key={item.href}
            >
              <Icon size={17} className="text-[#86868B]" aria-hidden="true" />
              {item.label}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
