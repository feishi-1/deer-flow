# Landing Page Rebrand Design: XXX司法局AI应用系统

**Date:** 2026-05-27
**Status:** Approved
**Scope:** Frontend homepage content rebranding. Login page and backend are NOT affected.

## Overview

Replace DeerFlow's open-source technical product landing page content with content appropriate for an enterprise judicial bureau AI application system ("XXX司法局AI应用系统"). Page structure, animations, and visual effects are preserved. Only text content and minor layout adjustments are changed.

## Files Affected

| File | Change |
|------|--------|
| `src/app/page.tsx` | No structural changes |
| `src/components/landing/hero.tsx` | Replace rotating words, description, button text |
| `src/components/landing/header.tsx` | Remove GitHub Star button, replace with Login link; remove Blog; change brand link target |
| `src/components/landing/footer.tsx` | Replace tagline text |
| `src/components/landing/sections/case-study-section.tsx` | Replace case study cards with 6 judicial application scenarios; make non-clickable cards |
| `src/components/landing/sections/skills-section.tsx` | Replace title and subtitle |
| `src/components/landing/sections/sandbox-section.tsx` | Replace terminal animation with enterprise feature display |
| `src/components/landing/sections/whats-new-section.tsx` | Replace MagicBento cards with judicial system features |
| `src/components/landing/sections/community-section.tsx` | Replace GitHub link with support email contact |

## Section-by-Section Design

### 1. Hero (`hero.tsx`)

**Kept:** Galaxy background, FlickeringGrid mask, WordRotate animation, ChevronRight button
**Changed:**

- WordRotate words → `["智能法规检索", "案件智能分析", "法律文书生成", "合同审查", "风险预警评估", "法律智能问答"]`
- Title suffix → `"助力司法智能化"`
- Description text → `"基于大语言模型的企业级司法AI应用平台，为司法工作者提供法规检索、案件分析、文书生成等智能化辅助服务，提升司法工作效率与质量。"`
- Button text → `"开始使用"`
- Remove BytePlus partnership conditional block (NEXT_PUBLIC_STATIC_WEBSITE_ONLY check)

### 2. Header (`header.tsx`)

**Kept:** Fixed top bar with backdrop blur, brand name display, gradient divider
**Changed:**

- Brand logo link → point to `/` (home) instead of `branding.githubUrl`
- Remove Blog navigation link
- Replace "Star on GitHub" button with "登录系统" button linking to `/login`
- Remove StarCounter async component and related imports

### 3. Footer (`footer.tsx`)

**Kept:** Layout structure, license, copyright
**Changed:**

- Tagline → `"以科技赋能司法，用智能提升效率"`

### 4. Case Study → 应用场景 (`case-study-section.tsx`)

**Kept:** Section wrapper, 3-column grid, card hover animation
**Changed:**

- Section title → `"应用场景"`
- Section subtitle → `"覆盖司法工作全流程的智能化应用"`

Replace 6 cards with new content (no links, display-only):

1. **法规智能检索** — 快速查找法律法规、司法解释，精准定位相关条款，提升法规查阅效率
2. **案件智能分析** — 自动梳理案件事实，提取关键要素与争议焦点，辅助判案决策
3. **法律文书生成** — 一键生成起诉书、判决书、调解书等法律文书，减少重复劳动
4. **合同智能审查** — 自动审查合同条款，识别法律风险点，提供专业修改建议
5. **法律知识问答** — 解答各类法律专业问题，提供法条依据与相关判例参考
6. **智能风险预警** — 基于大数据分析，识别潜在法律风险，提前预警并提供应对方案

- Remove `Link` wrapping and `pathOfThread` imports
- Cards become pure presentation (no navigation on click)
- Background images replaced with gradient placeholder (original images reference deleted DeerFlow threads)

### 5. Skills → 核心能力 (`skills-section.tsx`)

**Kept:** ProgressiveSkillsAnimation component, full-height section
**Changed:**

- Title → `"核心能力"`
- Subtitle → `"基于大语言模型技术，面向司法场景深度优化，提供全方位的智能化法律辅助能力"`

### 6. Sandbox → 技术保障 (`sandbox-section.tsx`)

**Kept:** Two-column layout (left visual, right description + tags)
**Changed:**

- Title → `"技术保障"`
- Subtitle → `"面向政企场景打造，从数据安全到系统可靠性，全方位保障司法AI系统稳定运行"`
- Left column: Remove Terminal animation, replace with a simplified visual representation (icon + description)
- Right column feature tags → `["数据加密", "私有化部署", "高可用架构", "权限管控", "审计日志", "国产化适配"]`
- Remove AIO Sandbox external links and related text

### 7. What's New → 系统特性 (`whats-new-section.tsx`)

**Kept:** MagicBento grid layout, AuroraText animation on title
**Changed:**

- Title → `"系统特性"`
- Subtitle → `"专为司法场景设计的全方位 AI 能力平台"`

Replace 6 MagicBento cards:

| Label | Title | Description |
|-------|-------|-------------|
| 智能 | 智能问答 | 基于大模型的精准法律问答，支持多轮深度对话 |
| 知识 | 知识管理 | 法律法规、案例判例的结构化知识库管理 |
| 安全 | 权限控制 | 基于角色的细粒度权限管理，保障数据安全 |
| 灵活 | 多模型支持 | 兼容主流大语言模型，灵活切换与配置 |
| 部署 | 私有化部署 | 数据不出内网，满足政企安全合规要求 |
| 更新 | 持续更新 | 法律法规知识库定期维护，保持时效性 |

### 8. Community → 联系我们 (`community-section.tsx`)

**Kept:** Section wrapper, AuroraText animation on title
**Changed:**

- Title → `"联系我们"`
- Subtitle → `"如需技术支持、定制开发或产品咨询，欢迎与我们联系"`
- Replace GitHub button with `mailto:{branding.supportEmail}` button with text `"联系技术支持"`
- Remove GitHubLogoIcon import

## Implementation Notes

- All branding names/URLs read from `@/core/config/branding` (ENV-configured)
- No changes to Tailwind classes, animations, or component structure
- Login page (`src/app/(auth)/login/page.tsx`) is NOT modified
- Backend is NOT affected
- i18n translations (`src/core/i18n/locales/`) are NOT modified (the existing en-US/zh-CN translations contain workspace strings; landing page content is hardcoded and will be directly edited)

## Technical Constraints

- Maintain Server Component / Client Component boundaries (`"use client"` directives remain unchanged)
- CN-only content (no i18n needed for landing page, consistent with current hardcoded approach)
- Keep all existing animation libraries (motion, tw-animate-css, OGL/Galaxy)
