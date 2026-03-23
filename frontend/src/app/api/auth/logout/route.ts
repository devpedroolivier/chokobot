import { NextResponse } from "next/server";

import { sessionCookieOptions } from "@/lib/admin-session";
import { ADMIN_SESSION_COOKIE } from "@/lib/admin-session-constants";

export async function POST(request: Request) {
  const response = NextResponse.redirect(new URL("/login?logged_out=1", request.url), { status: 303 });
  response.cookies.set(ADMIN_SESSION_COOKIE, "", {
    ...sessionCookieOptions(),
    maxAge: 0,
  });
  return response;
}
