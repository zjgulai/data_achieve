import { redirect } from "next/navigation";

/**
 * 根路由。
 *
 * 新 IA 里它是公开首页。首页由批次 5 实现。
 * 当前先指向能力目录，避免 /platforms 形成重定向链。
 */
export default function RootPage() {
  redirect("/tools");
}
