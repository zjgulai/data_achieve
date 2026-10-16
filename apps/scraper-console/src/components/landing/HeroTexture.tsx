"use client";

import { useId } from "react";

/** 纹理词汇。全部来自 DIH 自己的领域。 */
const WORDS = ["endpoint", "provider", "dataset", "run", "artifact"];

const ROW_COUNT = 9;

/**
 * 自有形状：圆角方块阵列。
 * 纹理只在这个形状内显示。形状与参考站无关。
 */
const CLIP_RECTS = [
  { x: 40, y: 26, width: 320, height: 196 },
  { x: 392, y: 8, width: 236, height: 232 },
  { x: 660, y: 52, width: 312, height: 164 },
  { x: 1004, y: 16, width: 156, height: 260 },
  { x: 152, y: 252, width: 392, height: 148 },
  { x: 596, y: 246, width: 472, height: 156 },
];

/** 拼一行词。词序按下标错开，避免行间对齐成格。 */
function rowText(row: number): string {
  const words: string[] = [];
  for (let i = 0; i < 8; i += 1) {
    words.push(WORDS[(row + i) % WORDS.length]);
  }
  return words.join("  ·  ");
}

/**
 * 首屏低对比度纹理。
 *
 * 内联 SVG 文字铺 DIH 语汇，裁进圆角方块阵列。
 * 呼吸节奏 7s，由 .landing-breathe 驱动。禁止动效时静止。
 */
export function HeroTexture() {
  const raw = useId();
  const clipId = `hero-texture-${raw.replace(/[^a-zA-Z0-9_-]/g, "")}`;

  return (
    <svg
      className="pointer-events-none absolute inset-0 h-full w-full"
      viewBox="0 0 1200 420"
      preserveAspectRatio="xMidYMid slice"
      aria-hidden="true"
    >
      <defs>
        <clipPath id={clipId}>
          {CLIP_RECTS.map(rect => (
            <rect
              key={`${rect.x}-${rect.y}`}
              x={rect.x}
              y={rect.y}
              width={rect.width}
              height={rect.height}
              rx={32}
            />
          ))}
        </clipPath>
      </defs>
      <g
        className="landing-breathe"
        clipPath={`url(#${clipId})`}
        opacity={0.12}
        fontSize={16}
        letterSpacing={3}
        style={{
          fill: "var(--action-primary)",
          fontFamily: "var(--font-mono)",
        }}
      >
        {Array.from({ length: ROW_COUNT }, (_, row) => (
          <text key={row} x={row % 2 === 0 ? 24 : -36} y={46 + row * 46}>
            {rowText(row)}
          </text>
        ))}
      </g>
    </svg>
  );
}
