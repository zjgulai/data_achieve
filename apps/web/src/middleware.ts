import { NextResponse, type NextRequest } from "next/server";

/**
 * 登录校验：没有 access_token Cookie 的页面请求转到 /login。
 *
 * 只检查 Cookie 是否存在，不验签。API 仍是权限的最终判定者：
 * 过期或伪造的 Cookie 会让 API 返回 401，页面显示错误态。
 *
 * 与 apps/scraper-console/src/middleware.ts 同源。两个前端是同一套
 * 鉴权模型，未登录的表现必须一致，否则用户在两处看到不同行为。
 *
 * mock 模式（NEXT_PUBLIC_MOCK_API=true）下不拦截：本地开发与 CI 的
 * E2E 没有真实会话，拦截会让所有页面跳到登录页。构建期常量，
 * 与 lib/api/client.ts 的 mockApiEnabled 同源。
 */
const mockApiEnabled = process.env.NEXT_PUBLIC_MOCK_API === "true";

export function middleware(request: NextRequest) {
  if (mockApiEnabled) {
    return NextResponse.next();
  }

  const { pathname, search } = request.nextUrl;
  const hasToken = Boolean(request.cookies.get("access_token")?.value);
  const isLoginPage = pathname === "/login";

  if (!hasToken && !isLoginPage) {
    const url = request.nextUrl.clone();
    url.pathname = "/login";
    url.search = `?next=${encodeURIComponent(pathname + search)}`;
    return NextResponse.redirect(url);
  }

  if (hasToken && isLoginPage) {
    return NextResponse.redirect(new URL("/dashboard", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|icon.svg|.*\\..*).*)"],
};
