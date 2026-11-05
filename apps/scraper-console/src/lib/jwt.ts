/**
 * HS256 JWT 验签（Edge Runtime 兼容）。
 *
 * 不使用 jose/jsonwebtoken：middleware 跑在 Edge Runtime，且项目依赖里
 * 没有 JWT 库，引入新依赖要重新锁包。Web Crypto 原生支持 HMAC-SHA256，
 * 足以完成验签。
 *
 * 与 API 侧对齐：apps/api/src/data_intelligence_hub/core/security.py
 *   jwt.encode(payload, settings.jwt_secret, algorithm="HS256")
 *   payload = {"sub": ..., "exp": ..., "type": "access"}
 */

export type AccessTokenPayload = {
  sub: string;
  exp: number;
  type?: string;
};

function base64UrlToBytes(input: string): Uint8Array {
  const pad = input.length % 4 === 0 ? "" : "=".repeat(4 - (input.length % 4));
  const b64 = (input + pad).replace(/-/g, "+").replace(/_/g, "/");
  const bin = atob(b64);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i += 1) out[i] = bin.charCodeAt(i);
  return out;
}

function decodeJsonSegment(segment: string): Record<string, unknown> | null {
  try {
    const text = new TextDecoder().decode(base64UrlToBytes(segment));
    const parsed = JSON.parse(text);
    return parsed && typeof parsed === "object" ? (parsed as Record<string, unknown>) : null;
  } catch {
    return null;
  }
}

/**
 * 校验签名 + 过期时间。
 * 密钥未配置时返回 false（fail closed），不降级为"仅检查存在性"。
 */
export async function verifyAccessToken(token: string): Promise<boolean> {
  const secret = process.env.JWT_SECRET;
  if (!secret) return false;

  const parts = token.split(".");
  if (parts.length !== 3) return false;

  const [headerB64, payloadB64, signatureB64] = parts;

  const header = decodeJsonSegment(headerB64);
  // 只接受 HS256，显式拒绝 none/RS256 等，防止算法混淆攻击
  if (!header || header.alg !== "HS256") return false;

  const payload = decodeJsonSegment(payloadB64);
  if (!payload) return false;

  // 过期校验（秒级时间戳）
  const exp = payload.exp;
  if (typeof exp !== "number" || exp * 1000 <= Date.now()) return false;

  // 类型校验
  if (payload.type !== undefined && payload.type !== "access") return false;

  try {
    const key = await crypto.subtle.importKey(
      "raw",
      new TextEncoder().encode(secret),
      { name: "HMAC", hash: "SHA-256" },
      false,
      ["verify"],
    );
    const signature = base64UrlToBytes(signatureB64);
    return await crypto.subtle.verify(
      "HMAC",
      key,
      signature as unknown as ArrayBuffer,
      new TextEncoder().encode(`${headerB64}.${payloadB64}`),
    );
  } catch {
    return false;
  }
}
