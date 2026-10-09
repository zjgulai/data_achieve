import { getPlatformMeta } from "@/lib/platforms/catalog";

/**
 * Letter-badge platform logo. Inline styled because the brand palette is
 * per-platform hex (the sanctioned exception to the no-raw-hex rule).
 */
export function PlatformLogo({ platform, size = 48 }: { platform: string; size?: number }) {
  const meta = getPlatformMeta(platform);
  const radius = Math.round(size * 0.2);
  const fontSize = size >= 44 ? 13 : size >= 32 ? 11 : 9;
  return (
    <span
      title={platform}
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        width: size,
        height: size,
        borderRadius: radius,
        background: meta.bg,
        color: meta.fg,
        fontSize,
        fontWeight: 700,
        lineHeight: 1,
        flexShrink: 0,
        letterSpacing: "-0.03em",
        fontFamily: "var(--font-sans)",
      }}
    >
      {meta.letter}
    </span>
  );
}
