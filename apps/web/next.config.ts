import type { NextConfig } from "next";

/**
 * 部署子路径。生产构建注入 `/insight`，本地开发与 E2E 不设该变量（空串）。
 *
 * 必须是构建期常量：basePath 会写进 routes-manifest 与客户端 publicPath，
 * 运行时改环境变量无效。
 */
const basePath = process.env.NEXT_PUBLIC_BASE_PATH ?? "";

const nextConfig: NextConfig = {
  output: "standalone",
  // 空字符串会被 Next 当成"设置了但为空"，这里只在非空时才带上，
  // 保证不设变量的构建产物与之前完全一致。
  ...(basePath ? { basePath } : {}),
  images: {
    remotePatterns: [
      {
        hostname: "dummyimage.com",
        protocol: "https",
      },
    ],
  },
  typedRoutes: true,
};

export default nextConfig;
