type Pill = { label: string; y: number };

/** 左侧：采集器入口。 */
const SOURCES: Pill[] = [
  { label: "社媒采集器", y: 40 },
  { label: "网页采集器", y: 136 },
  { label: "搜索采集器", y: 232 },
];

/** 右侧：平台目录分类。名称取自 catalog 分类。 */
const TARGETS: Pill[] = [
  { label: "国际社媒", y: 20 },
  { label: "中文社媒", y: 78 },
  { label: "电商", y: 136 },
  { label: "评价", y: 194 },
  { label: "开放网络", y: 252 },
];

const PILL_WIDTH = 200;
const PILL_HEIGHT = 48;
const SOURCE_X = 24;
const TARGET_X = 776;
const CENTER = { x: 400, y: 110, width: 200, height: 100 };

/** 扇线起点与终点。线宽 2px。 */
function connectorPath(x1: number, y1: number, x2: number, y2: number): string {
  return `M${x1} ${y1} L${x2} ${y2}`;
}

/**
 * 连接区几何图解：采集器 → DIH 中枢 → 平台目录。
 *
 * 2px 线与胶囊节点构成。玫瑰色连线做 8s 微光循环。
 * 禁止动效时连线保持静态亮度。
 */
export function ConnectDiagram({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 1000 320"
      role="img"
      aria-label="采集器经 DIH 中枢汇入平台目录"
      className={className}
      style={{ fontFamily: "var(--font-sans)" }}
    >
      {/* 胶囊节点 */}
      <g style={{ fill: "var(--surface-primary)", stroke: "var(--border-strong)" }} strokeWidth={2}>
        {SOURCES.map(pill => (
          <rect
            key={pill.label}
            x={SOURCE_X}
            y={pill.y}
            width={PILL_WIDTH}
            height={PILL_HEIGHT}
            rx={PILL_HEIGHT / 2}
          />
        ))}
        {TARGETS.map(pill => (
          <rect
            key={pill.label}
            x={TARGET_X}
            y={pill.y}
            width={PILL_WIDTH}
            height={PILL_HEIGHT}
            rx={PILL_HEIGHT / 2}
          />
        ))}
        <rect
          x={CENTER.x}
          y={CENTER.y}
          width={CENTER.width}
          height={CENTER.height}
          rx={28}
        />
      </g>

      {/* 连线与节点。玫瑰微光。 */}
      <g
        className="landing-glow"
        opacity={0.75}
        strokeWidth={2}
        style={{ stroke: "var(--action-primary)", fill: "var(--action-primary)" }}
      >
        {SOURCES.map((pill, index) => (
          <path
            key={pill.label}
            d={connectorPath(
              SOURCE_X + PILL_WIDTH,
              pill.y + PILL_HEIGHT / 2,
              CENTER.x,
              CENTER.y + 28 + index * 22
            )}
            fill="none"
          />
        ))}
        {TARGETS.map(pill => (
          <path
            key={pill.label}
            d={connectorPath(
              CENTER.x + CENTER.width,
              CENTER.y + CENTER.height / 2,
              TARGET_X,
              pill.y + PILL_HEIGHT / 2
            )}
            fill="none"
          />
        ))}
        {SOURCES.map(pill => (
          <circle
            key={pill.label}
            cx={SOURCE_X + PILL_WIDTH}
            cy={pill.y + PILL_HEIGHT / 2}
            r={3.5}
          />
        ))}
        <circle cx={CENTER.x + CENTER.width} cy={CENTER.y + CENTER.height / 2} r={3.5} />
      </g>

      {/* 文字 */}
      <g fontSize={15} style={{ fill: "var(--text-secondary)" }} textAnchor="middle">
        {SOURCES.map(pill => (
          <text key={pill.label} x={SOURCE_X + PILL_WIDTH / 2} y={pill.y + 30}>
            {pill.label}
          </text>
        ))}
        {TARGETS.map(pill => (
          <text key={pill.label} x={TARGET_X + PILL_WIDTH / 2} y={pill.y + 30}>
            {pill.label}
          </text>
        ))}
      </g>
      <text
        x={CENTER.x + CENTER.width / 2}
        y={CENTER.y + 46}
        textAnchor="middle"
        fontSize={19}
        fontWeight={600}
        style={{ fill: "var(--text-primary)" }}
      >
        DIH 中枢
      </text>
      <text
        x={CENTER.x + CENTER.width / 2}
        y={CENTER.y + 74}
        textAnchor="middle"
        fontSize={13}
        style={{ fill: "var(--text-tertiary)" }}
      >
        目录 · 运行 · 产物
      </text>
    </svg>
  );
}
