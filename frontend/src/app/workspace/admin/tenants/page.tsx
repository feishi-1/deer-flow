"use client";

import { useQuery } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { listTenants } from "@/core/admin/api";

export default function TenantsPage() {
  const [statusFilter, setStatusFilter] = useState<string | undefined>();

  const { data, isLoading, error } = useQuery({
    queryKey: ["admin", "tenants", statusFilter],
    queryFn: () => listTenants({ status: statusFilter }),
  });

  return (
    <div className="container mx-auto py-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">API Tenants</h1>
          <p className="text-muted-foreground">
            Manage third-party API access and quotas
          </p>
        </div>
        <Link href="/workspace/admin/tenants/new">
          <Button>
            <Plus className="mr-2 h-4 w-4" />
            Create Tenant
          </Button>
        </Link>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Tenants</CardTitle>
          <CardDescription>
            All registered API tenants and their status
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading && <p>Loading...</p>}
          {error && <p className="text-red-500">Error loading tenants</p>}
          {data && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>API Key Prefix</TableHead>
                  <TableHead>RPM Limit</TableHead>
                  <TableHead>TPM Limit</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.tenants.map((tenant) => (
                  <TableRow key={tenant.id}>
                    <TableCell className="font-medium">{tenant.name}</TableCell>
                    <TableCell>
                      <span
                        className={`inline-flex rounded-full px-2 py-1 text-xs font-semibold ${
                          tenant.status === "active"
                            ? "bg-green-100 text-green-800"
                            : "bg-red-100 text-red-800"
                        }`}
                      >
                        {tenant.status}
                      </span>
                    </TableCell>
                    <TableCell className="font-mono text-sm">
                      {tenant.api_key_prefix}...
                    </TableCell>
                    <TableCell>{tenant.rate_limit_rpm}</TableCell>
                    <TableCell>{tenant.rate_limit_tpm}</TableCell>
                    <TableCell>
                      {new Date(tenant.created_at).toLocaleDateString()}
                    </TableCell>
                    <TableCell>
                      <Link href={`/workspace/admin/tenants/${tenant.id}`}>
                        <Button variant="ghost" size="sm">
                          View
                        </Button>
                      </Link>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
