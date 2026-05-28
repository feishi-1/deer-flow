"use client";

import { ShieldCheckIcon } from "lucide-react";

import { Section } from "../section";

export function SandboxSection({ className }: { className?: string }) {
  return (
    <Section
      className={className}
      title="技术保障"
      subtitle="面向政企场景打造，从数据安全到系统可靠性，全方位保障司法AI系统稳定运行"
    >
      <div className="mt-8 flex w-full max-w-6xl flex-col items-center gap-12 lg:flex-row lg:gap-16">
        <div className="w-full flex-1 flex items-center justify-center">
          <div className="flex flex-col items-center gap-4 text-center">
            <ShieldCheckIcon className="size-24 text-purple-400" />
            <h3 className="text-2xl font-bold">企业级安全保障</h3>
            <p className="text-muted-foreground max-w-sm">
              遵循政企安全标准，提供从基础设施到应用层的全方位安全防护
            </p>
          </div>
        </div>

        <div className="w-full flex-1 space-y-6">
          <div className="space-y-4">
            <p className="text-sm font-medium tracking-wider text-purple-400 uppercase">
              技术架构
            </p>
            <h2 className="text-4xl font-bold tracking-tight lg:text-5xl">
              安全 · 可靠 · 可控
            </h2>
          </div>

          <div className="flex flex-wrap gap-3 pt-4">
            {[
              "数据加密",
              "私有化部署",
              "高可用架构",
              "权限管控",
              "审计日志",
              "国产化适配",
            ].map((tag) => (
              <span
                key={tag}
                className="rounded-full border border-zinc-800 bg-zinc-900 px-4 py-2 text-sm text-zinc-300"
              >
                {tag}
              </span>
            ))}
          </div>
        </div>
      </div>
    </Section>
  );
}
