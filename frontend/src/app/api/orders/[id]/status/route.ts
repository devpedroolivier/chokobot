import { NextRequest, NextResponse } from "next/server";

import { getAdminSession, getBackendAuthorizationHeader } from "@/lib/admin-session";

function resolveBackendBaseUrl(): string | null {
  return process.env.PANEL_BACKEND_URL || process.env.NEXT_PUBLIC_PANEL_BACKEND_URL || null;
}

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ id: string }> },
) {
  const session = await getAdminSession();
  if (!session) {
    return NextResponse.json({ status: "error", detail: "admin_session_required" }, { status: 401 });
  }

  const { id } = await context.params;
  const baseUrl = resolveBackendBaseUrl();
  const authHeader = await getBackendAuthorizationHeader();
  if (!baseUrl || !authHeader) {
    return NextResponse.json({ status: "error", detail: "frontend_proxy_not_configured" }, { status: 503 });
  }

  const body = await request.json().catch(() => ({}));
  const status = String(body.status || "").trim();
  if (!status) {
    return NextResponse.json({ status: "error", detail: "status_required" }, { status: 400 });
  }

  const form = new URLSearchParams({ status }).toString();
  const response = await fetch(`${baseUrl}/painel/encomendas/${encodeURIComponent(id)}/status`, {
    method: "POST",
    headers: {
      Authorization: authHeader,
      "Content-Type": "application/x-www-form-urlencoded",
      ...(request.headers.get("x-request-id")
        ? { "X-Request-ID": request.headers.get("x-request-id") as string }
        : {}),
    },
    body: form,
  });

  const payload = await response.json().catch(() => ({ ok: false }));
  return NextResponse.json(payload, { status: response.status });
}
