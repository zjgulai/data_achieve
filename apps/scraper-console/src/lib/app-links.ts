/**
 * 跨应用链接。
 *
 * 控制台与洞察工作台同域部署。生产上 web 挂在 /insight，默认值就是该
 * 路径。本地开发时 web 跑在 3000 端口，在 .env.local 里设置：
 *
 *   NEXT_PUBLIC_INSIGHT_URL=http://localhost:3000
 *
 * NEXT_PUBLIC_* 由 Next 在构建期内联，所以这里写成模块级常量。
 */

/** 绝对地址前缀。用来区分 https://host 与站点内路径。 */
const ABSOLUTE_URL = /^[a-z][a-z\d+.-]*:\/\//i;

/**
 * 归一化跨应用地址。
 *
 * 未配置或只有空白时返回默认值。末尾斜杠去掉，避免拼出 //。
 * 不是绝对地址、也不以 / 开头的值按站点内路径处理，补上前导斜杠。
 */
export function resolveAppUrl(
  configured: string | undefined,
  fallback: string,
): string {
  const value = configured?.trim();
  if (!value) return fallback;
  if (value === "/") return value;
  const trimmed = value.replace(/\/+$/, "");
  if (ABSOLUTE_URL.test(trimmed) || trimmed.startsWith("/")) return trimmed;
  return `/${trimmed}`;
}

/** 洞察工作台地址。同域生产为 /insight。 */
export const INSIGHT_URL = resolveAppUrl(
  process.env.NEXT_PUBLIC_INSIGHT_URL,
  "/insight",
);
