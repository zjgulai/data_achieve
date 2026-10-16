type AgentSpriteProps = {
  size?: number;
  className?: string;
};

/**
 * 自绘小机器人。
 *
 * 11 个矩形，单天线。轮廓是本项目自有设计。
 * 弹跳 1.2s step-end，眨眼 4.4s，由 globals.css 驱动。
 * 禁止动效时静止。
 */
export function AgentSprite({ size = 28, className }: AgentSpriteProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 28 28"
      aria-hidden="true"
      className={className}
      style={{ fill: "var(--action-primary)" }}
    >
      <g className="landing-hop">
        {/* 天线 */}
        <rect x="13.4" y="0.5" width="1.2" height="3.5" rx="0.6" />
        <rect x="12.2" y="0" width="3.6" height="2" rx="1" />
        {/* 头与眼 */}
        <rect x="4.5" y="3.5" width="19" height="10.5" rx="3" />
        <rect
          className="landing-blink"
          x="8.6"
          y="7"
          width="3.4"
          height="3.4"
          rx="0.8"
          style={{ fill: "var(--surface-canvas)" }}
        />
        <rect
          className="landing-blink"
          x="16"
          y="7"
          width="3.4"
          height="3.4"
          rx="0.8"
          style={{ fill: "var(--surface-canvas)" }}
        />
        {/* 身体与手臂 */}
        <rect x="6.5" y="14.5" width="15" height="9.5" rx="2.4" />
        <rect x="2.6" y="15.5" width="2.6" height="6.4" rx="1.2" />
        <rect x="22.8" y="15.5" width="2.6" height="6.4" rx="1.2" />
        {/* 胸口面板 */}
        <rect
          x="10.8"
          y="17.4"
          width="6.4"
          height="3.2"
          rx="0.9"
          style={{ fill: "var(--accent-1-pressed)" }}
        />
        {/* 腿 */}
        <rect x="9.2" y="23.6" width="3.2" height="3.6" rx="1.1" />
        <rect x="15.6" y="23.6" width="3.2" height="3.6" rx="1.1" />
      </g>
    </svg>
  );
}
