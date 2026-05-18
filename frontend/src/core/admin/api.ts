/**
 * Admin API client for tenant management and usage analytics.
 */

import { fetch } from "@/core/api/fetcher";
import { getBackendBaseURL } from "@/core/config";

import type {
  CreateTenantRequest,
  QuotaPeriod,
  Tenant,
  UpdateTenantRequest,
  UsageStats,
} from "./types";

const BASE_URL = getBackendBaseURL();

// ---------------------------------------------------------------------------
// Tenant Management
// ---------------------------------------------------------------------------

export async function listTenants(params?: {
  status?: string;
  limit?: number;
  offset?: number;
}): Promise<{ tenants: Tenant[]; total: number }> {
  const query = new URLSearchParams();
  if (params?.status) query.set("status", params.status);
  if (params?.limit) query.set("limit", params.limit.toString());
  if (params?.offset) query.set("offset", params.offset.toString());

  const res = await fetch(`${BASE_URL}/api/admin/tenants?${query.toString()}`);
  if (!res.ok) throw new Error(`Failed to list tenants: ${res.statusText}`);
  return res.json();
}

export async function getTenant(tenantId: string): Promise<{ tenant: Tenant }> {
  const res = await fetch(`${BASE_URL}/api/admin/tenants/${tenantId}`);
  if (!res.ok) throw new Error(`Failed to get tenant: ${res.statusText}`);
  return res.json();
}

export async function createTenant(
  data: CreateTenantRequest,
): Promise<{ tenant: Tenant; api_key: string; warning: string }> {
  const res = await fetch(`${BASE_URL}/api/admin/tenants`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(`Failed to create tenant: ${res.statusText}`);
  return res.json();
}

export async function updateTenant(
  tenantId: string,
  data: UpdateTenantRequest,
): Promise<{ tenant: Tenant; updated: boolean }> {
  const res = await fetch(`${BASE_URL}/api/admin/tenants/${tenantId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(`Failed to update tenant: ${res.statusText}`);
  return res.json();
}

export async function deleteTenant(tenantId: string): Promise<void> {
  const res = await fetch(`${BASE_URL}/api/admin/tenants/${tenantId}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error(`Failed to delete tenant: ${res.statusText}`);
}

export async function rotateApiKey(
  tenantId: string,
): Promise<{ api_key: string; api_key_prefix: string; warning: string }> {
  const res = await fetch(`${BASE_URL}/api/admin/tenants/${tenantId}/rotate`, {
    method: "POST",
  });
  if (!res.ok) throw new Error(`Failed to rotate API key: ${res.statusText}`);
  return res.json();
}

export async function suspendTenant(
  tenantId: string,
): Promise<{ status: string }> {
  const res = await fetch(`${BASE_URL}/api/admin/tenants/${tenantId}/suspend`, {
    method: "POST",
  });
  if (!res.ok) throw new Error(`Failed to suspend tenant: ${res.statusText}`);
  return res.json();
}

export async function resumeTenant(
  tenantId: string,
): Promise<{ status: string }> {
  const res = await fetch(`${BASE_URL}/api/admin/tenants/${tenantId}/resume`, {
    method: "POST",
  });
  if (!res.ok) throw new Error(`Failed to resume tenant: ${res.statusText}`);
  return res.json();
}

// ---------------------------------------------------------------------------
// Usage Analytics
// ---------------------------------------------------------------------------

export async function getTenantUsage(
  tenantId: string,
  params?: { start_date?: string; end_date?: string; limit?: number },
): Promise<{
  tenant_id: string;
  stats: UsageStats;
  records: unknown[];
  count: number;
}> {
  const query = new URLSearchParams();
  if (params?.start_date) query.set("start_date", params.start_date);
  if (params?.end_date) query.set("end_date", params.end_date);
  if (params?.limit) query.set("limit", params.limit.toString());

  const res = await fetch(
    `${BASE_URL}/api/admin/usage/tenants/${tenantId}?${query.toString()}`,
  );
  if (!res.ok) throw new Error(`Failed to get tenant usage: ${res.statusText}`);
  return res.json();
}

export async function getTenantQuotaHistory(
  tenantId: string,
  limit = 12,
): Promise<{ tenant_id: string; periods: QuotaPeriod[] }> {
  const res = await fetch(
    `${BASE_URL}/api/admin/usage/quota/${tenantId}?limit=${limit}`,
  );
  if (!res.ok)
    throw new Error(`Failed to get quota history: ${res.statusText}`);
  return res.json();
}

export async function getUsageSummary(params?: {
  start_date?: string;
  end_date?: string;
}): Promise<{
  summary: Array<{
    tenant_id: string;
    tenant_name: string;
    status: string;
    stats: UsageStats;
  }>;
}> {
  const query = new URLSearchParams();
  if (params?.start_date) query.set("start_date", params.start_date);
  if (params?.end_date) query.set("end_date", params.end_date);

  const res = await fetch(
    `${BASE_URL}/api/admin/usage/summary?${query.toString()}`,
  );
  if (!res.ok)
    throw new Error(`Failed to get usage summary: ${res.statusText}`);
  return res.json();
}
