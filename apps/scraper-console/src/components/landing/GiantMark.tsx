type GiantMarkProps = {
  text: string;
  className?: string;
};

/**
 * 巨型裁切字标。
 *
 * 用系统字栈与紧字距。容器裁掉字的下沿。
 * 装饰用途，对辅助技术隐藏。
 */
export function GiantMark({ text, className }: GiantMarkProps) {
  return (
    <div aria-hidden="true" className={["overflow-hidden", className ?? ""].join(" ")}>
      <div
        className="whitespace-nowrap text-center font-bold"
        style={{
          color: "var(--footer-wordmark)",
          fontSize: "clamp(40px, 9vw, 132px)",
          lineHeight: 0.72,
          letterSpacing: "-0.035em",
          transform: "translateY(26%)",
        }}
      >
        {text}
      </div>
    </div>
  );
}
