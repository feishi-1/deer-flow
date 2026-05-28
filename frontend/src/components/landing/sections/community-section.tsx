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
