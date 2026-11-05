import { NextResponse, type NextRequest } from "next/server";
import { verifyAccessToken } from "./lib/jwt";

/**
 * 登录门禁：校验 access_token Cookie 的 JWT 签名与有效期。
 *
 * 2026-11-03 变更：原实现只检查 Cookie 是否存在，不验签——
 * 任意伪造值都能通过门禁。现改为真实验签（HS256），与 API 侧
 * core/security.py 使用同一个 JWT_SECRET。
 *
 * 密钥缺失时 fail closed（一律跳登录页），不退回"仅检查存在性"，
 * 否则一个配置疏漏就会让门禁重新失效。
 */
export async function middleware(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  const isLoginPage = pathname === "/login";

  const token = request.cookies.get("access_token")?.value;
  const valid = token ? await verifyAccessToken(token) : false;

  if (!valid && !isLoginPage) {
    const url = request.nextUrl.clone();
    url.pathname = "/login";
    url.search = `?next=${encodeURIComponent(pathname + search)}`;
    const redirect = NextResponse.redirect(url);
    // 清掉失效 Cookie，避免带着过期 token 反复跳转
    if (token) redirect.cookies.delete("access_token");
    return redirect;
  }

  if (valid && isLoginPage) {
    return NextResponse.redirect(new URL("/dashboard", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|.*\\..*).*)"],
};
