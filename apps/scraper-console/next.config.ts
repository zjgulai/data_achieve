import type { NextConfig } from "next";
import { buildRedirects } from "./src/lib/routes";

const nextConfig: NextConfig = {
  output: "standalone",
  // 开发服务器默认只信任 localhost。Playwright 与人工调试常用
  // 127.0.0.1 访问，不带此白名单时 /_next/static/chunks 会返回 403，
  // 页面看似渲染但懒加载 chunk 全部失败。只影响 next dev，不影响构建产物。
  allowedDevOrigins: ["127.0.0.1", "localhost"],
  // 旧路由的重定向。表在 P0 冻结。
  // 见 src/lib/routes.ts 与整合方案 §4.3。
  async redirects() {
    return buildRedirects();
  },
};

export default nextConfig;
