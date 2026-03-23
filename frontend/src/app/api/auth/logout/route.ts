import { NextResponse } from "next/server";

import { sessionCookieOptions } from "@/lib/admin-session";
import { ADMIN_SESSION_COOKIE } from "@/lib/admin-session-constants";
import { resolveAdminPublicUrl } from "@/lib/public-url";

export async function POST(request: Request) {
  const target = resolveAdminPublicUrl("/login", request.url);
  target.searchParams.set("logged_out", "1");
  const response = NextResponse.redirect(target, { status: 303 });
  response.cookies.set(ADMIN_SESSION_COOKIE, "", {
    ...sessionCookieOptions(),
    maxAge: 0,
  });
  return response;
}
