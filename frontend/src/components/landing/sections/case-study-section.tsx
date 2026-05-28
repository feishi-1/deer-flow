import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

import { Section } from "../section";

export function CaseStudySection({ className }: { className?: string }) {
  const scenarios = [
    {
      title: "法规智能检索",
      description:
        "快速查找法律法规、司法解释，精准定位相关条款，提升法规查阅效率",
    },
    {
      title: "案件智能分析",
      description:
        "自动梳理案件事实，提取关键要素与争议焦点，辅助判案决策",
    },
    {
      title: "法律文书生成",
      description:
        "一键生成起诉书、判决书、调解书等法律文书，减少重复劳动",
    },
    {
      title: "合同智能审查",
      description:
        "自动审查合同条款，识别法律风险点，提供专业修改建议",
    },
    {
      title: "法律知识问答",
      description:
        "解答各类法律专业问题，提供法条依据与相关判例参考",
    },
    {
      title: "智能风险预警",
      description:
        "基于大数据分析，识别潜在法律风险，提前预警并提供应对方案",
    },
  ];

  return (
    <Section
      className={className}
      title="应用场景"
      subtitle="覆盖司法工作全流程的智能化应用"
    >
      <div className="container-md mt-8 grid grid-cols-1 gap-4 px-4 md:grid-cols-2 md:px-20 lg:grid-cols-3">
        {scenarios.map((scenario) => (
          <Card key={scenario.title} className="group/card relative h-64 overflow-hidden">
            <div
              className="absolute inset-0 z-0 bg-cover bg-center bg-no-repeat transition-all duration-300 group-hover/card:scale-110 group-hover/card:brightness-90"
              style={{
                background:
                  "linear-gradient(135deg, #1e3a5f 0%, #2d1b69 50%, #1a1a2e 100%)",
              }}
            />
            <div
              className={cn(
                "flex h-full w-full translate-y-[calc(100%-60px)] flex-col items-center",
                "transition-all duration-300",
                "group-hover/card:translate-y-[calc(100%-128px)]",
              )}
            >
              <div
                className="flex w-full flex-col p-4"
                style={{
                  background:
                    "linear-gradient(to bottom, rgba(0, 0, 0, 0) 0%, rgba(0, 0, 0, 1) 100%)",
                }}
              >
                <div className="flex flex-col gap-2">
                  <h3 className="flex h-14 items-center text-xl font-bold text-shadow-black">
                    {scenario.title}
                  </h3>
                  <p className="box-shadow-black overflow-hidden text-sm text-white/85 text-shadow-black">
                    {scenario.description}
                  </p>
                </div>
              </div>
            </div>
          </Card>
        ))}
      </div>
    </Section>
  );
}
