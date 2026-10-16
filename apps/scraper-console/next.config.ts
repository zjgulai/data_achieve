import type { NextConfig } from "next";
import { buildRedirects } from "./src/lib/routes";

const nextConfig: NextConfig = {
  output: "standalone",
  // 旧路由的重定向。表在 P0 冻结。
  // 见 src/lib/routes.ts 与整合方案 §4.3。
  async redirects() {
    return buildRedirects();
  },
};

export default nextConfig;
