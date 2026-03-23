import { NextRequest, NextResponse } from "next/server";

import { getAdminSession, getBackendAuthorizationHeader } from "@/lib/admin-session";

function resolveBackendBaseUrl(): string | null {
  return process.env.PANEL_BACKEND_URL || process.env.NEXT_PUBLIC_PANEL_BACKEND_URL || null;
}

export async function POST(request: NextRequest) {
  const session = await getAdminSession();
  if (!session) {
    return NextResponse.json({ status: "error", detail: "admin_session_required" }, { status: 401 });
  }

  const baseUrl = resolveBackendBaseUrl();
  const authHeader = await getBackendAuthorizationHeader();
  if (!baseUrl || !authHeader) {
    return NextResponse.json({ status: "error", detail: "frontend_proxy_not_configured" }, { status: 503 });
  }

  const response = await fetch(`${baseUrl}/painel/api/clientes`, {
    method: "POST",
    headers: {
      Authorization: authHeader,
      "Content-Type": "application/json",
      ...(request.headers.get("x-request-id")
        ? { "X-Request-ID": request.headers.get("x-request-id") as string }
        : {}),
    },
    body: JSON.stringify(await request.json().catch(() => ({}))),
  });

  const payload = await response.json().catch(() => ({ status: "error", detail: "invalid_backend_response" }));
  return NextResponse.json(payload, { status: response.status });
}
