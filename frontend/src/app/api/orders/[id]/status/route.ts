import { NextRequest, NextResponse } from "next/server";

import { getAdminSession, getBackendAuthorizationHeader } from "@/lib/admin-session";

const ALLOWED_STATUSES = new Set(["pendente", "em_preparo", "agendada", "retirada", "entregue"]);

function resolveBackendBaseUrl(): string | null {
  return process.env.PANEL_BACKEND_URL || process.env.NEXT_PUBLIC_PANEL_BACKEND_URL || null;
}

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ id: string }> },
) {
  const session = await getAdminSession();
  if (!session) {
    return NextResponse.json(
      { status: "error", detail: "admin_session_required" },
      { status: 401 },
    );
  }

  const { id } = await context.params;
  const baseUrl = resolveBackendBaseUrl();
  const authHeader = await getBackendAuthorizationHeader();

  if (!baseUrl || !authHeader) {
    return NextResponse.json(
      { status: "error", detail: "frontend_proxy_not_configured" },
      { status: 503 },
    );
  }

  const body = await request.json().catch(() => ({}));
  const status = String(body.status || "").trim();
  if (!ALLOWED_STATUSES.has(status)) {
    return NextResponse.json(
      { status: "error", detail: "invalid_status" },
      { status: 400 },
    );
  }

  const formBody = new URLSearchParams({ status });
  const response = await fetch(`${baseUrl}/painel/encomendas/${id}/status`, {
    method: "POST",
    headers: {
      Authorization: authHeader,
      "Content-Type": "application/x-www-form-urlencoded",
      ...(request.headers.get("x-request-id")
        ? { "X-Request-ID": request.headers.get("x-request-id") as string }
        : {}),
    },
    body: formBody.toString(),
  });

  const payload = await response.json().catch(() => ({ status: "error", detail: "invalid_backend_response" }));
  return NextResponse.json(payload, { status: response.status });
}
