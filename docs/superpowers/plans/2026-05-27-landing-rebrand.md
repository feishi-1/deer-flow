# Landing Page Rebrand Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace DeerFlow open-source landing page content with judicial bureau AI system content across 8 component files.

**Architecture:** Direct text replacement in existing components. No structural refactoring. Each file edited independently — no interdependencies between tasks.

**Tech Stack:** Next.js 16, React 19, TypeScript, Tailwind CSS v4, Shadcn UI

---

### Task 1: Hero Section — Replace content

**Files:**
- Modify: `frontend/src/components/landing/hero.tsx`

- [ ] **Step 1: Replace WordRotate words array**

Replace lines 41-56, the `words` prop of `<WordRotate>`:

```tsx
        <h1 className="flex items-center gap-2 text-4xl font-bold md:text-6xl">
          <WordRotate
            words={[
              "智能法规检索",
              "案件智能分析",
              "法律文书生成",
              "合同审查",
              "风险预警评估",
              "法律智能问答",
            ]}
          />{" "}
          <div>助力司法智能化</div>
        </h1>
```

- [ ] **Step 2: Replace description paragraph**

Replace lines 72-80, the `<p>` with `text-muted-foreground` class:

```tsx
        <p className="text-muted-foreground mt-8 scale-105 text-center text-2xl text-shadow-sm">
          基于大语言模型的企业级司法AI应用平台，为司法工作者提供法规检索、案件分析、
          <br />
          文书生成等智能化辅助服务，提升司法工作效率与质量。
        </p>
```

- [ ] **Step 3: Replace button text**

Replace line 83, the `<span>` inside the Button:

```tsx
            <span className="text-md">开始使用</span>
```

- [ ] **Step 4: Remove BytePlus partnership block**

Delete lines 60-71 (the entire `{env.NEXT_PUBLIC_STATIC_WEBSITE_ONLY && (...)}` block).

- [ ] **Step 5: Clean up unused imports**

Remove `import { env } from "@/env";` (line 10) — no longer used after removing BytePlus block.

Remove the entire `function BytePlusIcon(...)` definition (lines 92-136) — no longer referenced.

- [ ] **Step 6: Verify**

Run: `cd frontend && pnpm run typecheck`
Expected: No TypeScript errors

---

### Task 2: Header — Replace GitHub button with login

**Files:**
- Modify: `frontend/src/components/landing/header.tsx`

- [ ] **Step 1: Remove unused imports**

Remove lines 1, 5, 6, 7, 9:

Delete these imports entirely:
- `import { StarFilledIcon, GitHubLogoIcon } from "@radix-ui/react-icons";`
- `import { Button } from "@/components/ui/button";`
- `import { NumberTicker } from "@/components/ui/number-ticker";`
- `import { env } from "@/env";`

Add instead:
```tsx
import Link from "next/link";
```
(Check if `Link` is already imported — yes it is on line 2, so keep it)

Actually, looking at the file again:
- Line 1: `import { StarFilledIcon, GitHubLogoIcon } from "@radix-ui/react-icons";` — REMOVE
- Line 2: `import Link from "next/link";` — KEEP
- Line 4: `import { Button } from "@/components/ui/button";` — KEEP (still need Button for the login link)
- Line 5: `import { NumberTicker } from "@/components/ui/number-ticker";` — REMOVE
- Line 9: `import { env } from "@/env";` — REMOVE
- Line 4: Keep Button import

- [ ] **Step 2: Replace brand link target**

Replace lines 30-37, the `<a>` wrapping the brand name:

```tsx
        <Link href="/">
          <h1 className="font-serif text-xl">{branding.name}</h1>
        </Link>
```

- [ ] **Step 3: Remove Blog link**

Replace lines 38-53, the entire `<nav>` block:

```tsx
      <nav className="mr-8 ml-auto flex items-center gap-8 text-sm font-medium">
        <Link
          href={`/${lang}/docs`}
          className="text-secondary-foreground hover:text-foreground transition-colors"
        >
          {t.home.docs}
        </Link>
      </nav>
```

- [ ] **Step 4: Replace GitHub Star button with Login button**

Replace lines 52-77, the `<div>` containing the button and gradient glow:

```tsx
      <div className="relative">
        <div
          className="pointer-events-none absolute inset-0 z-0 h-full w-full rounded-full opacity-30 blur-2xl"
          style={{
            background: "linear-gradient(90deg, #ff80b5 0%, #9089fc 100%)",
            filter: "blur(16px)",
          }}
        />
        <Button
          variant="outline"
          size="sm"
          asChild
          className="group relative z-10"
        >
          <Link href="/login">登录系统</Link>
        </Button>
      </div>
```

- [ ] **Step 5: Remove StarCounter async component**

Delete the entire `async function StarCounter()` definition (lines 83-117).

- [ ] **Step 6: Remove unused HeaderProps fields**

Remove `homeURL` and `locale` from the `HeaderProps` type and function signature if they become unused. For now: keep `className` and `locale` (locale is used for `getI18n`). Remove `homeURL` from destructured props.

Replace lines 18-21:

```tsx
export async function Header({ className, locale }: HeaderProps) {
  const { locale: resolvedLocale, t } = await getI18n(locale);
```

And update the `HeaderProps` type on lines 12-16:

```tsx
export type HeaderProps = {
  className?: string;
  locale?: Locale;
};
```

- [ ] **Step 7: Verify**

Run: `cd frontend && pnpm run typecheck`
Expected: No TypeScript errors

---

### Task 3: Footer — Replace tagline

**Files:**
- Modify: `frontend/src/components/landing/footer.tsx`

- [ ] **Step 1: Replace tagline text**

Replace line 21-23, the `<p>` with `font-serif` class:

```tsx
        <p className="text-center font-serif text-lg md:text-xl">
          &quot;以科技赋能司法，用智能提升效率&quot;
        </p>
```

- [ ] **Step 2: Verify**

Run: `cd frontend && pnpm run typecheck`
Expected: No TypeScript errors

---

### Task 4: Case Study → 应用场景

**Files:**
- Modify: `frontend/src/components/landing/sections/case-study-section.tsx`

- [ ] **Step 1: Replace the entire file content**

Replace the current file with this complete rewrite:

```tsx
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
```

- [ ] **Step 2: Verify**

Run: `cd frontend && pnpm run typecheck`
Expected: No TypeScript errors

---

### Task 5: Skills → 核心能力

**Files:**
- Modify: `frontend/src/components/landing/sections/skills-section.tsx`

- [ ] **Step 1: Replace title and subtitle in Section component**

Replace lines 10-22, the `<Section>` opening tag props:

```tsx
  return (
    <Section
      className={cn("h-[calc(100vh-64px)] w-full bg-white/2", className)}
      title="核心能力"
      subtitle={
        <div>
          基于大语言模型技术，面向司法场景深度优化，
          <br />
          提供全方位的智能化法律辅助能力
        </div>
      }
    >
```

- [ ] **Step 2: Verify**

Run: `cd frontend && pnpm run typecheck`
Expected: No TypeScript errors

---

### Task 6: Sandbox → 技术保障

**Files:**
- Modify: `frontend/src/components/landing/sections/sandbox-section.tsx`

- [ ] **Step 1: Replace the entire file content**

Replace the current file with this complete rewrite:

```tsx
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
```

- [ ] **Step 2: Verify**

Run: `cd frontend && pnpm run typecheck`
Expected: No TypeScript errors

---

### Task 7: What's New → 系统特性

**Files:**
- Modify: `frontend/src/components/landing/sections/whats-new-section.tsx`

- [ ] **Step 1: Replace the entire file content**

Replace the current file with this complete rewrite:

```tsx
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
```

- [ ] **Step 2: Verify**

Run: `cd frontend && pnpm run typecheck`
Expected: No TypeScript errors

---

### Task 8: Community → 联系我们

**Files:**
- Modify: `frontend/src/components/landing/sections/community-section.tsx`

- [ ] **Step 1: Replace the entire file content**

Replace the current file with this complete rewrite:

```tsx
"use client";

import { MailIcon } from "lucide-react";
import Link from "next/link";

import { AuroraText } from "@/components/ui/aurora-text";
import { Button } from "@/components/ui/button";
import { branding } from "@/core/config/branding";

import { Section } from "../section";

export function CommunitySection() {
  return (
    <Section
      title={
        <AuroraText colors={["#60A5FA", "#A5FA60", "#A560FA"]}>
          联系我们
        </AuroraText>
      }
      subtitle="如需技术支持、定制开发或产品咨询，欢迎与我们联系"
    >
      <div className="flex justify-center">
        <Button className="text-xl" size="lg" asChild>
          <Link href={`mailto:${branding.supportEmail}`}>
            <MailIcon />
            联系技术支持
          </Link>
        </Button>
      </div>
    </Section>
  );
}
```

- [ ] **Step 2: Verify**

Run: `cd frontend && pnpm run typecheck`
Expected: No TypeScript errors

---

### Task 9: Full build verification

- [ ] **Step 1: Run typecheck on all changes**

```bash
cd frontend && pnpm run typecheck
```
Expected: Exit 0, no errors

- [ ] **Step 2: Run lint**

```bash
cd frontend && pnpm run lint
```
Expected: Clean or only pre-existing issues

- [ ] **Step 3: Run build**

```bash
cd frontend && pnpm run build
```
Expected: Successful build

- [ ] **Step 4: Commit all changes**

```bash
git add frontend/src/components/landing/hero.tsx \
        frontend/src/components/landing/header.tsx \
        frontend/src/components/landing/footer.tsx \
        frontend/src/components/landing/sections/case-study-section.tsx \
        frontend/src/components/landing/sections/skills-section.tsx \
        frontend/src/components/landing/sections/sandbox-section.tsx \
        frontend/src/components/landing/sections/whats-new-section.tsx \
        frontend/src/components/landing/sections/community-section.tsx \
        docs/superpowers/
git commit -m "feat: rebrand landing page for judicial bureau AI system"
```
