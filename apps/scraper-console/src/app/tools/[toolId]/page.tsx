"use client";

import { use } from "react";
import { SkillDetail } from "@/components/skills/skill-detail";

type Props = Readonly<{
  // 键名必须与目录名 [toolId] 一致。Next.js 按目录名传参。
  params: Promise<{ toolId: string }>;
}>;

export default function SkillDetailPage({ params }: Props) {
  const { toolId } = use(params);
  return <SkillDetail platformId={toolId} />;
}
