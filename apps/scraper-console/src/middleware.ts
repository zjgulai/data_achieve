import { NextResponse, type NextRequest } from "next/server";

/**
 * 登录门禁：没有 access_token Cookie 时把页面请求送到 /login。
 *
 * 只做存在性检查，不验签。API 仍是权限的最终判定者：
 * 过期或伪造的 Cookie 会让 API 返回 401，页面显示错误。
 */
export function middleware(request: NextRequest) {
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
  matcher: ["/((?!_next/static|_next/image|favicon.ico|.*\\..*).*)"],
};
