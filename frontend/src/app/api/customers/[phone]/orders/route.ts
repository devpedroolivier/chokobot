import { NextRequest, NextResponse } from "next/server";

import { getAdminSession, getBackendAuthorizationHeader } from "@/lib/admin-session";

function resolveBackendBaseUrl(): string | null {
  return process.env.PANEL_BACKEND_URL || process.env.NEXT_PUBLIC_PANEL_BACKEND_URL || null;
}

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ phone: string }> },
) {
  const session = await getAdminSession();
  if (!session) {
    return NextResponse.json({ status: "error", detail: "admin_session_required" }, { status: 401 });
  }

  const { phone } = await context.params;
  const baseUrl = resolveBackendBaseUrl();
  const authHeader = await getBackendAuthorizationHeader();
  if (!baseUrl || !authHeader) {
    return NextResponse.json({ status: "error", detail: "frontend_proxy_not_configured" }, { status: 503 });
  }

  const response = await fetch(
    `${baseUrl}/painel/api/clientes/${encodeURIComponent(phone)}/encomendas`,
    {
      cache: "no-store",
      headers: {
        Authorization: authHeader,
        ...(request.headers.get("x-request-id")
          ? { "X-Request-ID": request.headers.get("x-request-id") as string }
          : {}),
      },
    },
  );

  const payload = await response.json().catch(() => ({ items: [] }));
  return NextResponse.json(payload, { status: response.status });
}
