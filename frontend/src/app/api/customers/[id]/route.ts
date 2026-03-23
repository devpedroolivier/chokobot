import { NextRequest, NextResponse } from "next/server";

import { getAdminSession, getBackendAuthorizationHeader } from "@/lib/admin-session";

function resolveBackendBaseUrl(): string | null {
  return process.env.PANEL_BACKEND_URL || process.env.NEXT_PUBLIC_PANEL_BACKEND_URL || null;
}

async function forwardRequest(
  request: NextRequest,
  method: "PUT" | "DELETE",
  customerId: string,
) {
  const session = await getAdminSession();
  if (!session) {
    return NextResponse.json({ status: "error", detail: "admin_session_required" }, { status: 401 });
  }

  const baseUrl = resolveBackendBaseUrl();
  const authHeader = await getBackendAuthorizationHeader();
  if (!baseUrl || !authHeader) {
    return NextResponse.json({ status: "error", detail: "frontend_proxy_not_configured" }, { status: 503 });
  }

  const init: RequestInit = {
    method,
    headers: {
      Authorization: authHeader,
      ...(request.headers.get("x-request-id")
        ? { "X-Request-ID": request.headers.get("x-request-id") as string }
        : {}),
    },
  };

  if (method === "PUT") {
    init.headers = {
      ...init.headers,
      "Content-Type": "application/json",
    };
    init.body = JSON.stringify(await request.json().catch(() => ({})));
  }

  const response = await fetch(`${baseUrl}/painel/api/clientes/${customerId}`, init);
  const payload = await response.json().catch(() => ({ status: "error", detail: "invalid_backend_response" }));
  return NextResponse.json(payload, { status: response.status });
}

export async function PUT(
  request: NextRequest,
  context: { params: Promise<{ id: string }> },
) {
  const { id } = await context.params;
  return forwardRequest(request, "PUT", id);
}

export async function DELETE(
  request: NextRequest,
  context: { params: Promise<{ id: string }> },
) {
  const { id } = await context.params;
  return forwardRequest(request, "DELETE", id);
}
