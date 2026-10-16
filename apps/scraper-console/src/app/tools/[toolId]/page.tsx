"use client";

import { use } from "react";
import { SkillDetail } from "@/components/skills/skill-detail";

type Props = Readonly<{
  params: Promise<{ platformId: string }>;
}>;

export default function SkillDetailPage({ params }: Props) {
  const { platformId } = use(params);
  return <SkillDetail platformId={platformId} />;
}
