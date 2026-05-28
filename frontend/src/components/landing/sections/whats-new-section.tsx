"use client";

import MagicBento, { type BentoCardProps } from "@/components/ui/magic-bento";
import { cn } from "@/lib/utils";

import { Section } from "../section";

const COLOR = "#0a0a0a";
const features: BentoCardProps[] = [
  {
    color: COLOR,
    label: "智能",
    title: "智能问答",
    description: "基于大模型的精准法律问答，支持多轮深度对话",
  },
  {
    color: COLOR,
    label: "知识",
    title: "知识管理",
    description: "法律法规、案例判例的结构化知识库管理",
  },
  {
    color: COLOR,
    label: "安全",
    title: "权限控制",
    description: "基于角色的细粒度权限管理，保障数据安全",
  },
  {
    color: COLOR,
    label: "灵活",
    title: "多模型支持",
    description: "兼容主流大语言模型，灵活切换与配置",
  },
  {
    color: COLOR,
    label: "部署",
    title: "私有化部署",
    description: "数据不出内网，满足政企安全合规要求",
  },
  {
    color: COLOR,
    label: "更新",
    title: "持续更新",
    description: "法律法规知识库定期维护，保持时效性",
  },
];

export function WhatsNewSection({ className }: { className?: string }) {
  return (
    <Section
      className={cn("", className)}
      title="系统特性"
      subtitle="专为司法场景设计的全方位 AI 能力平台"
    >
      <div className="flex w-full items-center justify-center">
        <MagicBento data={features} />
      </div>
    </Section>
  );
}
