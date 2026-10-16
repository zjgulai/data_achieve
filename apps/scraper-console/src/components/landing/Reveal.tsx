"use client";

import { useEffect, useRef, useState } from "react";
import type { CSSProperties, ReactNode } from "react";

type RevealProps = {
  children: ReactNode;
  /** 同组元素的下标。CSS 用它算错峰延迟。 */
  index?: number;
  className?: string;
};

/**
 * 滚动揭示容器。
 *
 * 进入视口后加 is-shown 类。
 * 过渡只在 prefers-reduced-motion: no-preference 下生效，见 globals.css。
 * 禁止动效时内容直接显示，不做位移。
 */
export function Reveal({ children, index = 0, className }: RevealProps) {
  const ref = useRef<HTMLDivElement>(null);
  const [shown, setShown] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    // 不支持 IntersectionObserver 时直接显示，避免内容被隐藏。
    // 用 timeout 异步置位，避开同步 setState 的级联渲染。
    if (typeof IntersectionObserver === "undefined") {
      const timer = window.setTimeout(() => setShown(true), 0);
      return () => window.clearTimeout(timer);
    }
    const observer = new IntersectionObserver(
      entries => {
        if (entries.some(entry => entry.isIntersecting)) {
          setShown(true);
          observer.disconnect();
        }
      },
      { rootMargin: "0px 0px -8% 0px", threshold: 0.05 }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const classes = ["landing-reveal", shown ? "is-shown" : "", className ?? ""]
    .filter(Boolean)
    .join(" ");

  return (
    <div
      ref={ref}
      className={classes}
      style={{ "--reveal-index": index } as CSSProperties}
    >
      {children}
    </div>
  );
}
