import { ExternalLink } from "lucide-react";

import { CONSOLE_URL } from "@/lib/app-links";

type AppSwitchLinkProps = {
  className?: string;
  onNavigate?: () => void;
};

/**
 * 跨应用入口：回到采集控制台。
 *
 * 跨应用切换用裸 <a>，不走 next/link。控制台在站点根；本应用的
 * basePath 不能加到它上面。
 */
export function AppSwitchLink({
  className = "",
  onNavigate,
}: AppSwitchLinkProps) {
  return (
    <a
      className={`flex min-h-11 items-center gap-3 rounded-[var(--radius-2)] px-3 py-2.5 text-sm font-medium text-[var(--text-tertiary)] transition-colors duration-[var(--duration-base)] hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)] ${className}`}
      href={CONSOLE_URL}
      onClick={onNavigate}
    >
      采集控制台
      <ExternalLink aria-hidden="true" size={14} />
    </a>
  );
}
