/**
 * TypeScript types for the admin tenant management API.
 */

export interface Tenant {
  id: string;
  name: string;
  description: string | null;
  api_key_hash: string;
  api_key_prefix: string;
  status: "active" | "suspended" | "revoked";
  rate_limit_rpm: number;
  rate_limit_tpm: number;
  quota_monthly_tokens: number | null;
  quota_monthly_requests: number | null;
  max_concurrent_runs: number;
  allowed_models: { models: string[] } | null;
  sandbox_config: Record<string, unknown> | null;
  metadata_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  expires_at: string | null;
}

export interface CreateTenantRequest {
  name: string;
  description?: string;
  rate_limit_rpm?: number;
  rate_limit_tpm?: number;
  quota_monthly_tokens?: number | null;
  quota_monthly_requests?: number | null;
  max_concurrent_runs?: number;
  allowed_models?: string[];
  expires_at?: string;
}

export interface UpdateTenantRequest {
  name?: string;
  description?: string;
  rate_limit_rpm?: number;
  rate_limit_tpm?: number;
  quota_monthly_tokens?: number | null;
  quota_monthly_requests?: number | null;
  max_concurrent_runs?: number;
  allowed_models?: string[];
}

export interface UsageStats {
  total_requests: number;
  total_tokens: number;
  total_prompt_tokens: number;
  total_completion_tokens: number;
}

export interface QuotaPeriod {
  id: number;
  tenant_id: string;
  period_start: string;
  period_end: string;
  tokens_used: number;
  requests_used: number;
}
