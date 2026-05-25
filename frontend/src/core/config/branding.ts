/**
 * Centralized branding configuration.
 *
 * All system name, logo, URLs, and other brand identity values
 * should be configured here. Components read from this config
 * so that rebranding only requires editing this single file.
 *
 * Environment variable overrides (optional):
 *   NEXT_PUBLIC_APP_NAME        - System display name
 *   NEXT_PUBLIC_APP_SHORT_NAME  - Abbreviated name (sidebar collapsed)
 *   NEXT_PUBLIC_APP_DESCRIPTION - Meta description
 *   NEXT_PUBLIC_APP_LOGO_PATH   - Path to logo SVG/PNG in /public
 *   NEXT_PUBLIC_APP_FAVICON     - Path to favicon in /public
 *   NEXT_PUBLIC_APP_URL         - Official website URL
 *   NEXT_PUBLIC_APP_GITHUB_URL  - GitHub repository URL
 *   NEXT_PUBLIC_APP_SUPPORT_EMAIL - Support email address
 */

export interface BrandingConfig {
  /** Full display name (e.g. "DeerFlow") */
  name: string;
  /** Short name for collapsed sidebar (e.g. "DF") */
  shortName: string;
  /** Meta description for SEO */
  description: string;
  /** Path to logo image relative to /public */
  logoPath: string;
  /** Path to favicon relative to /public */
  faviconPath: string;
  /** Official website URL */
  websiteUrl: string;
  /** GitHub repository URL */
  githubUrl: string;
  /** Issues/feedback URL */
  issuesUrl: string;
  /** Support email */
  supportEmail: string;
  /** Copyright holder name */
  copyrightHolder: string;
  /** License type */
  license: string;
  /** Tagline / slogan */
  tagline: string;
}

function getEnv(key: string): string | undefined {
  if (typeof process !== "undefined" && process.env) {
    return process.env[key];
  }
  return undefined;
}

export const branding: BrandingConfig = {
  name: getEnv("NEXT_PUBLIC_APP_NAME") ?? "DeerFlow",
  shortName: getEnv("NEXT_PUBLIC_APP_SHORT_NAME") ?? "DF",
  description:
    getEnv("NEXT_PUBLIC_APP_DESCRIPTION") ??
    "A LangChain-based framework for building super agents.",
  logoPath: getEnv("NEXT_PUBLIC_APP_LOGO_PATH") ?? "/images/deer.svg",
  faviconPath: getEnv("NEXT_PUBLIC_APP_FAVICON") ?? "/favicon.ico",
  websiteUrl: getEnv("NEXT_PUBLIC_APP_URL") ?? "https://deerflow.tech/",
  githubUrl:
    getEnv("NEXT_PUBLIC_APP_GITHUB_URL") ??
    "https://github.com/bytedance/deer-flow",
  issuesUrl:
    getEnv("NEXT_PUBLIC_APP_ISSUES_URL") ??
    "https://github.com/bytedance/deer-flow/issues",
  supportEmail:
    getEnv("NEXT_PUBLIC_APP_SUPPORT_EMAIL") ?? "support@deerflow.tech",
  copyrightHolder: getEnv("NEXT_PUBLIC_APP_COPYRIGHT") ?? "DeerFlow",
  license: "MIT",
  tagline: getEnv("NEXT_PUBLIC_APP_TAGLINE") ?? "Open Source Super Agent",
};
