import { NextRequest, NextResponse } from "next/server";

import {
  createAdminSessionCookieValue,
  sessionCookieOptions,
  verifyPanelCredentials,
} from "@/lib/admin-session";
import { ADMIN_SESSION_COOKIE } from "@/lib/admin-session-constants";
import { resolveAdminPublicUrl } from "@/lib/public-url";

function resolveRedirectTarget(request: NextRequest, rawPath: string | null): URL {
  const safePath = rawPath && rawPath.startsWith("/") && !rawPath.startsWith("//") ? rawPath : "/";
  return resolveAdminPublicUrl(safePath, request.url);
}

function resolveLoginRedirect(request: NextRequest, error: string, nextPath: string | null): NextResponse {
  const target = resolveAdminPublicUrl("/login", request.url);
  target.searchParams.set("error", error);
  if (nextPath && nextPath.startsWith("/") && !nextPath.startsWith("//")) {
    target.searchParams.set("next", nextPath);
  }
  return NextResponse.redirect(target, { status: 303 });
}

export async function POST(request: NextRequest) {
  const formData = await request.formData();
  const username = String(formData.get("username") || "").trim();
  const password = String(formData.get("password") || "").trim();
  const nextPath = String(formData.get("next") || "").trim() || "/";

  if (!username || !password) {
    return resolveLoginRedirect(request, "missing_credentials", nextPath);
  }

  const verification = await verifyPanelCredentials(username, password);
  if (!verification.ok) {
    return resolveLoginRedirect(request, verification.error || "invalid_credentials", nextPath);
  }

  const cookieValue = await createAdminSessionCookieValue(username, password);
  if (!cookieValue) {
    return resolveLoginRedirect(request, "session_creation_failed", nextPath);
  }

  const response = NextResponse.redirect(resolveRedirectTarget(request, nextPath), { status: 303 });
  response.cookies.set(ADMIN_SESSION_COOKIE, cookieValue, sessionCookieOptions());
  return response;
}
